"""
Strava Webhook Router — handles push events for real-time activity sync.

GET  /api/webhook/strava  — Subscription validation (hub.challenge echo)
POST /api/webhook/strava  — Event receiver (activity create/update/delete)
"""

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from firebase_config import db
import os
import requests
from datetime import datetime

router = APIRouter()

VERIFY_TOKEN = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "")


# ── GET: Subscription Validation ─────────────────────────────────────────────

@router.get("/strava")
def webhook_validation(request: Request):
    """
    Strava sends a GET request with hub.challenge to validate the callback URL.
    We must echo hub.challenge back in JSON to confirm the subscription.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and VERIFY_TOKEN and token == VERIFY_TOKEN and challenge:
        print(f"[webhook] Subscription validated: challenge={challenge}")
        return {"hub.challenge": challenge}

    return JSONResponse(status_code=403, content={"error": "Verification failed"})


# ── POST: Event Receiver ─────────────────────────────────────────────────────

@router.post("/strava")
def webhook_event(request_body: dict, background_tasks: BackgroundTasks):
    """
    Receives Strava webhook events. Must respond 200 within 2 seconds.
    Actual processing is done asynchronously in the background.
    """
    object_type = request_body.get("object_type")
    aspect_type = request_body.get("aspect_type")
    object_id = request_body.get("object_id")
    owner_id = request_body.get("owner_id")  # strava_athlete_id
    event_time = request_body.get("event_time")

    print(f"[webhook] Event: {aspect_type} {object_type} id={object_id} owner={owner_id}")

    # Only process activity create/update events
    if object_type == "activity" and aspect_type in ("create", "update"):
        background_tasks.add_task(
            _process_activity_event, owner_id, object_id, aspect_type
        )

    return {"status": "ok"}


# ── Background Processing ────────────────────────────────────────────────────

from typing import Optional

def _find_uid_by_strava_id(strava_athlete_id: int) -> Optional[str]:
    """Finds the Firebase UID for a given Strava athlete ID."""
    docs = (db.collection("users")
              .where("strava_athlete_id", "==", strava_athlete_id)
              .limit(1)
              .stream())
    for doc in docs:
        return doc.id
    return None


def _process_activity_event(strava_athlete_id: int, activity_id: int, aspect_type: str):
    """
    Background task: resolves Strava athlete ID → Firebase UID,
    then triggers a sync for that user.
    """
    try:
        uid = _find_uid_by_strava_id(strava_athlete_id)
        if not uid:
            print(f"[webhook] No user found for strava_athlete_id={strava_athlete_id}")
            return

        # Log the webhook event (read once to avoid double Firestore read)
        try:
            log_ref = (db.collection("users").document(uid)
                         .collection("meta").document("webhook_log"))
            log_snap = log_ref.get()
            prev_total = (log_snap.to_dict() or {}).get("total_events", 0) if log_snap.exists else 0
            log_ref.set({
                "last_event": aspect_type,
                "last_activity_id": activity_id,
                "last_event_time": datetime.now().isoformat(),
                "total_events": prev_total + 1,
            }, merge=True)
        except Exception as e:
            print(f"[webhook] Log write failed: {e}")

        # Refresh token and fetch the specific activity
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()
        if not user_doc.exists:
            return

        user_data = user_doc.to_dict()
        refresh_token = user_data.get("strava_refresh_token")
        if not refresh_token:
            return

        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        if not client_id or not client_secret:
            return

        # Refresh access token
        token_resp = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        })
        if not token_resp.ok:
            print(f"[webhook] Token refresh failed for uid={uid}")
            return

        new_token = token_resp.json()
        access_token = new_token["access_token"]
        user_ref.update({
            "strava_access_token": access_token,
            "strava_refresh_token": new_token["refresh_token"],
            "strava_expires_at": new_token["expires_at"],
        })

        # Fetch the specific activity
        act_resp = requests.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if not act_resp.ok:
            print(f"[webhook] Failed to fetch activity {activity_id}: {act_resp.status_code}")
            return

        act = act_resp.json()
        if act.get("type") != "Run":
            print(f"[webhook] Skipping non-run activity {activity_id} (type={act.get('type')})")
            return

        # Save activity using the same format as sync.py
        from routers.sync import _build_act_doc, get_period_start, _update_yearly_leaderboard

        # Determine period
        goal_snap = user_ref.collection("goals").document("current").get()
        period = "monthly"
        if goal_snap.exists:
            period = goal_snap.to_dict().get("period", "monthly")
        period_start = get_period_start(period)

        act_doc = _build_act_doc(act, period, period_start)
        act_ref = user_ref.collection("activities").document(str(activity_id))
        act_ref.set(act_doc, merge=True)

        print(f"[webhook] Synced activity {activity_id} for uid={uid} "
              f"({act_doc['distance_km']}km, {act_doc['avg_pace']}/km)")

        # Update both period and yearly leaderboards
        display_name = (
            user_data.get("display_name")
            or user_data.get("strava_name")
            or user_data.get("email", "").split("@")[0]
            or f"Runner #{uid[:6]}"
        )

        # Update current period leaderboard (re-aggregate from all activities)
        try:
            from routers.sync import pace_str
            all_acts = (user_ref.collection("activities")
                        .where("period_start", "==", period_start.isoformat())
                        .stream())
            p_dist, p_time, p_hr_sum, p_hr_cnt, p_runs = 0.0, 0, 0, 0, 0
            for adoc in all_acts:
                ad = adoc.to_dict()
                p_dist += ad.get("distance_km", 0) * 1000
                p_time += ad.get("moving_time", 0)
                p_runs += 1
                hr = ad.get("avg_heart_rate", 0) or 0
                if hr:
                    p_hr_sum += hr
                    p_hr_cnt += 1

            goal_snap_data = goal_snap.to_dict() if goal_snap.exists else {}
            target_dist = goal_snap_data.get("target_distance", 0)
            km = p_dist / 1000
            pct = round((km / target_dist) * 100) if target_dist > 0 else 0

            db.collection("leaderboard").document(uid).set({
                "uid": uid,
                "display_name": display_name,
                "email": user_data.get("email", ""),
                "total_distance_km": round(km, 2),
                "avg_pace": pace_str(p_dist, p_time),
                "avg_heart_rate": round(p_hr_sum / p_hr_cnt) if p_hr_cnt else 0,
                "goal_completion_percentage": min(pct, 100),
                "run_count": p_runs,
                "period": period,
                "period_start": period_start.isoformat(),
                "last_sync": datetime.now().isoformat(),
            }, merge=True)
        except Exception as e:
            print(f"[webhook] Period leaderboard update failed: {e}")

        _update_yearly_leaderboard(uid, user_data, display_name)

    except Exception as e:
        print(f"[webhook] Processing failed: {e}")
