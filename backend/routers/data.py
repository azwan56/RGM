"""
Data router — provides read-only API endpoints that replace direct
browser-to-Firestore reads.  This allows Chinese users (behind GFW)
to load data via the Render backend instead of connecting directly
to firestore.googleapis.com (which is blocked).

Data flow: Browser → Render backend → Firestore (both outside GFW)
"""

from fastapi import APIRouter, Request
from firebase_config import db

router = APIRouter()


# ── Dashboard init (profile + goals + strava status) ──────────────────────────

@router.get("/init/{uid}")
def get_dashboard_init(uid: str):
    """Combined endpoint for dashboard initial load — avoids multiple Firestore round-trips."""
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        return {"profile": None, "goal": None, "strava_connected": False}

    data = user_doc.to_dict() or {}

    # Strip sensitive tokens
    safe = {k: v for k, v in data.items()
            if not k.startswith("strava_access") and not k.startswith("strava_refresh")}

    # Goal
    goal_doc = db.collection("users").document(uid).collection("goals").document("current").get()
    goal = goal_doc.to_dict() if goal_doc.exists else None

    return {
        "profile": safe,
        "goal": goal,
        "strava_connected": bool(data.get("strava_connected")),
        "display_name": (
            data.get("display_name") or data.get("strava_name")
            or (data.get("email", "").split("@")[0] if data.get("email") else "")
        ),
    }


# ── Leaderboard stats for a single user ───────────────────────────────────────

@router.get("/stats/{uid}")
def get_user_stats(uid: str):
    """Returns the leaderboard document for a single user (used by RunningStatsPanel)."""
    doc = db.collection("leaderboard").document(uid).get()
    if not doc.exists:
        return {}
    return doc.to_dict()


# ── Leaderboard list ──────────────────────────────────────────────────────────

@router.get("/leaderboard")
def get_leaderboard(period: str = "monthly", limit_n: int = 20):
    """Returns sorted leaderboard entries for the given period (monthly or weekly)."""
    docs = (db.collection("leaderboard")
              .where("period", "==", period)
              .order_by("total_distance_km", direction="DESCENDING")
              .limit(limit_n)
              .stream())
    return {"entries": [d.to_dict() for d in docs]}


# ── Activities list for a month ───────────────────────────────────────────────

@router.get("/activities/{uid}")
def get_activities(uid: str, start: str = "", end: str = ""):
    """
    Returns activities for a user within a date range.
    start/end format: 'YYYY-MM-DDT00:00:00'
    """
    q = db.collection("users").document(uid).collection("activities")

    if start and end:
        q = (q.where("start_date_local", ">=", start)
              .where("start_date_local", "<", end)
              .order_by("start_date_local", direction="DESCENDING"))
    else:
        q = q.order_by("start_date_local", direction="DESCENDING").limit(50)

    docs = q.stream()
    return {"activities": [d.to_dict() for d in docs]}


# ── Single activity ───────────────────────────────────────────────────────────

@router.get("/activity/{uid}/{activity_id}")
def get_single_activity(uid: str, activity_id: str):
    """Returns a single activity document."""
    doc = db.collection("users").document(uid).collection("activities").document(activity_id).get()
    if not doc.exists:
        return {"activity": None}
    return {"activity": doc.to_dict()}
