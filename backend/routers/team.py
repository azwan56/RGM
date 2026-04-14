"""
Team & Challenge Router — team management and group challenges.

Firestore schema:
  teams/{team_id}:           name, description, created_by, members[], invite_code
  challenges/{challenge_id}: team_id, title, type, target_value, start/end_date
  challenges/{id}/participants/{uid}: current_value, last_sync, rank
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from firebase_config import db
from datetime import datetime, date
import random
import string

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────────

class CreateTeamRequest(BaseModel):
    uid: str
    name: str
    description: Optional[str] = ""

class JoinTeamRequest(BaseModel):
    uid: str
    invite_code: str

class CreateChallengeRequest(BaseModel):
    uid: str
    team_id: str
    title: str
    type: str = "total_km"  # total_km | run_count | avg_pace | streak_days
    target_value: float = 100
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    description: Optional[str] = ""

class SyncChallengeRequest(BaseModel):
    uid: str
    challenge_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gen_invite_code(length: int = 6) -> str:
    """Generate a unique uppercase alphanumeric invite code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _get_display_name(uid: str) -> str:
    """Get user's display name from Firestore."""
    doc = db.collection("users").document(uid).get()
    if doc.exists:
        d = doc.to_dict()
        return (d.get("display_name") or d.get("strava_name")
                or d.get("email", "").split("@")[0] or f"Runner #{uid[:6]}")
    return f"Runner #{uid[:6]}"


# ── Team CRUD ─────────────────────────────────────────────────────────────────

@router.post("/create")
def create_team(req: CreateTeamRequest):
    """Create a new team with a unique invite code."""
    # Generate unique invite code
    invite_code = _gen_invite_code()
    while True:
        existing = list(db.collection("teams")
                         .where("invite_code", "==", invite_code)
                         .limit(1).stream())
        if not existing:
            break
        invite_code = _gen_invite_code()

    team_ref = db.collection("teams").document()
    team_data = {
        "name": req.name,
        "description": req.description,
        "created_by": req.uid,
        "created_at": datetime.now().isoformat(),
        "members": [req.uid],
        "member_count": 1,
        "invite_code": invite_code,
    }
    team_ref.set(team_data)

    return {
        "team_id": team_ref.id,
        "invite_code": invite_code,
        "message": "Team created successfully",
    }


@router.post("/join")
def join_team(req: JoinTeamRequest):
    """Join a team using its invite code."""
    # Find team by invite code
    docs = list(db.collection("teams")
                  .where("invite_code", "==", req.invite_code.upper().strip())
                  .limit(1).stream())

    if not docs:
        raise HTTPException(status_code=404, detail="无效的邀请码")

    team_doc = docs[0]
    team_data = team_doc.to_dict()
    team_id = team_doc.id

    if req.uid in team_data.get("members", []):
        return {"team_id": team_id, "message": "你已经在这个团队中了"}

    members = team_data.get("members", [])
    if len(members) >= 50:
        raise HTTPException(status_code=400, detail="团队已满（上限 50 人）")

    # Add member
    from google.cloud.firestore_v1 import ArrayUnion
    db.collection("teams").document(team_id).update({
        "members": ArrayUnion([req.uid]),
        "member_count": len(members) + 1,
    })

    return {"team_id": team_id, "message": f"成功加入团队「{team_data['name']}」"}


@router.get("/{team_id}")
def get_team(team_id: str):
    """Get team details with member info."""
    doc = db.collection("teams").document(team_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Team not found")

    data = doc.to_dict()
    data["team_id"] = team_id

    # Enrich member info
    members_info = []
    for uid in data.get("members", []):
        members_info.append({
            "uid": uid,
            "display_name": _get_display_name(uid),
        })
    data["members_info"] = members_info

    return data


@router.get("/my-teams/{uid}")
def get_my_teams(uid: str):
    """Get all teams the user belongs to."""
    docs = db.collection("teams").where("members", "array_contains", uid).stream()
    teams = []
    for doc in docs:
        d = doc.to_dict()
        d["team_id"] = doc.id
        teams.append({
            "team_id": doc.id,
            "name": d.get("name", ""),
            "description": d.get("description", ""),
            "member_count": d.get("member_count", len(d.get("members", []))),
            "invite_code": d.get("invite_code", ""),
        })
    return {"teams": teams}


# ── Challenge CRUD ────────────────────────────────────────────────────────────

@router.post("/{team_id}/challenge")
def create_challenge(team_id: str, req: CreateChallengeRequest):
    """Create a new challenge for a team."""
    # Verify team exists and user is a member
    team_doc = db.collection("teams").document(team_id).get()
    if not team_doc.exists:
        raise HTTPException(status_code=404, detail="Team not found")

    team_data = team_doc.to_dict()
    if req.uid not in team_data.get("members", []):
        raise HTTPException(status_code=403, detail="You are not a member of this team")

    challenge_ref = db.collection("challenges").document()
    challenge_data = {
        "team_id": team_id,
        "team_name": team_data.get("name", ""),
        "title": req.title,
        "type": req.type,
        "target_value": req.target_value,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "description": req.description,
        "created_by": req.uid,
        "created_at": datetime.now().isoformat(),
        "participant_count": 0,
        "status": "active",
    }
    challenge_ref.set(challenge_data)

    # Auto-enroll creator
    challenge_ref.collection("participants").document(req.uid).set({
        "uid": req.uid,
        "display_name": _get_display_name(req.uid),
        "current_value": 0,
        "last_sync": None,
        "joined_at": datetime.now().isoformat(),
    })
    challenge_ref.update({"participant_count": 1})

    return {
        "challenge_id": challenge_ref.id,
        "message": "Challenge created",
    }


@router.get("/{team_id}/challenges")
def get_team_challenges(team_id: str):
    """Get all challenges for a team."""
    docs = (db.collection("challenges")
              .where("team_id", "==", team_id)
              .stream())

    today = date.today().isoformat()
    challenges = []
    for doc in docs:
        d = doc.to_dict()
        d["challenge_id"] = doc.id

        # Determine status
        if d.get("end_date", "") < today:
            d["status"] = "ended"
        elif d.get("start_date", "") > today:
            d["status"] = "upcoming"
        else:
            d["status"] = "active"

        challenges.append(d)

    # Sort: active first, then upcoming, then ended
    order = {"active": 0, "upcoming": 1, "ended": 2}
    challenges.sort(key=lambda c: order.get(c["status"], 3))

    return {"challenges": challenges}


@router.get("/challenge/{challenge_id}/leaderboard")
def get_challenge_leaderboard(challenge_id: str):
    """Get the leaderboard for a specific challenge."""
    challenge_doc = db.collection("challenges").document(challenge_id).get()
    if not challenge_doc.exists:
        raise HTTPException(status_code=404, detail="Challenge not found")

    challenge_data = challenge_doc.to_dict()
    challenge_data["challenge_id"] = challenge_id

    # Get participants
    parts = list(db.collection("challenges").document(challenge_id)
                   .collection("participants").stream())

    entries = [p.to_dict() for p in parts]
    entries.sort(key=lambda e: e.get("current_value", 0), reverse=True)

    # Assign ranks
    for i, entry in enumerate(entries):
        entry["rank"] = i + 1

    return {
        "challenge": challenge_data,
        "leaderboard": entries,
    }


@router.post("/challenge/{challenge_id}/join")
def join_challenge(challenge_id: str, req: SyncChallengeRequest):
    """Join a challenge (must be a member of the team)."""
    challenge_doc = db.collection("challenges").document(challenge_id).get()
    if not challenge_doc.exists:
        raise HTTPException(status_code=404, detail="Challenge not found")

    challenge_data = challenge_doc.to_dict()
    team_doc = db.collection("teams").document(challenge_data["team_id"]).get()
    if not team_doc.exists or req.uid not in team_doc.to_dict().get("members", []):
        raise HTTPException(status_code=403, detail="You must be a team member to join")

    part_ref = (db.collection("challenges").document(challenge_id)
                  .collection("participants").document(req.uid))
    if part_ref.get().exists:
        return {"message": "Already participating"}

    part_ref.set({
        "uid": req.uid,
        "display_name": _get_display_name(req.uid),
        "current_value": 0,
        "last_sync": None,
        "joined_at": datetime.now().isoformat(),
    })

    # Increment participant count
    from google.cloud.firestore_v1 import Increment
    db.collection("challenges").document(challenge_id).update({
        "participant_count": Increment(1),
    })

    return {"message": "Joined challenge"}


@router.post("/challenge/{challenge_id}/sync")
def sync_challenge_progress(req: SyncChallengeRequest):
    """Sync a participant's progress in a challenge. Calculates from activities."""
    challenge_id = req.challenge_id
    challenge_doc = db.collection("challenges").document(challenge_id).get()
    if not challenge_doc.exists:
        raise HTTPException(status_code=404, detail="Challenge not found")

    challenge_data = challenge_doc.to_dict()
    start_date = challenge_data.get("start_date", "")
    end_date = challenge_data.get("end_date", "")
    challenge_type = challenge_data.get("type", "total_km")

    # Fetch activities in challenge date range
    acts = list(db.collection("users").document(req.uid)
                  .collection("activities")
                  .where("start_date_local", ">=", start_date)
                  .where("start_date_local", "<=", end_date + "T23:59:59")
                  .stream())

    # Calculate value based on challenge type
    value = 0.0
    if challenge_type == "total_km":
        value = sum(a.to_dict().get("distance_km", 0) for a in acts)
    elif challenge_type == "run_count":
        value = len(acts)
    elif challenge_type == "avg_pace":
        total_dist = sum(a.to_dict().get("distance_km", 0) for a in acts)
        total_time = sum(a.to_dict().get("moving_time", 0) for a in acts)
        if total_dist > 0 and total_time > 0:
            sec_per_km = total_time / total_dist
            value = round(sec_per_km / 60, 2)  # minutes per km
    elif challenge_type == "streak_days":
        dates = set()
        for a in acts:
            d = a.to_dict().get("start_date_local", "")[:10]
            if d:
                dates.add(d)
        # Count consecutive days
        if dates:
            sorted_dates = sorted(dates)
            streak = 1
            max_streak = 1
            for i in range(1, len(sorted_dates)):
                from datetime import timedelta
                d1 = date.fromisoformat(sorted_dates[i-1])
                d2 = date.fromisoformat(sorted_dates[i])
                if (d2 - d1).days == 1:
                    streak += 1
                    max_streak = max(max_streak, streak)
                else:
                    streak = 1
            value = max_streak

    value = round(value, 2)

    # Update participant progress
    part_ref = (db.collection("challenges").document(challenge_id)
                  .collection("participants").document(req.uid))
    part_ref.set({
        "current_value": value,
        "last_sync": datetime.now().isoformat(),
        "display_name": _get_display_name(req.uid),
    }, merge=True)

    return {
        "current_value": value,
        "target_value": challenge_data.get("target_value", 0),
        "type": challenge_type,
    }
