"""
Admin Router — management endpoints for webhook registration, sync-all, and status.

All endpoints require ADMIN_SECRET header for authentication.
"""

from fastapi import APIRouter, HTTPException, Request
from firebase_config import db
import os
import requests
from datetime import datetime

router = APIRouter()

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")


def _check_admin(request: Request):
    """Validates admin authorization via X-Admin-Secret header."""
    token = request.headers.get("X-Admin-Secret", "")
    if not ADMIN_SECRET or token != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Admin access denied")


# ── Webhook Subscription Management ──────────────────────────────────────────

@router.post("/register-webhook")
def register_webhook(request: Request):
    """
    Registers a Strava webhook subscription for real-time activity push events.
    Requires BACKEND_PUBLIC_URL and STRAVA_WEBHOOK_VERIFY_TOKEN env vars.
    """
    _check_admin(request)

    backend_url = os.getenv("BACKEND_PUBLIC_URL", "")
    verify_token = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "")
    client_id = os.getenv("STRAVA_CLIENT_ID", "")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET", "")

    if not backend_url:
        raise HTTPException(status_code=400, detail="BACKEND_PUBLIC_URL not configured")
    if not verify_token:
        raise HTTPException(status_code=400, detail="STRAVA_WEBHOOK_VERIFY_TOKEN not configured")
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Strava credentials not configured")

    callback_url = f"{backend_url.rstrip('/')}/api/webhook/strava"

    resp = requests.post(
        "https://www.strava.com/api/v3/push_subscriptions",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "callback_url": callback_url,
            "verify_token": verify_token,
        },
        timeout=30,
    )

    if resp.ok:
        result = resp.json()
        # Save subscription info to Firestore
        db.collection("system").document("webhook_subscription").set({
            "subscription_id": result.get("id"),
            "callback_url": callback_url,
            "registered_at": datetime.now().isoformat(),
            "active": True,
        })
        return {"message": "Webhook registered successfully", "subscription": result}
    else:
        return {
            "error": f"Strava returned {resp.status_code}",
            "detail": resp.text,
            "hint": "If subscription already exists, use GET /webhook-status to check.",
        }


@router.get("/webhook-status")
def webhook_status(request: Request):
    """
    Queries the current Strava webhook subscription status.
    """
    _check_admin(request)

    client_id = os.getenv("STRAVA_CLIENT_ID", "")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Strava credentials not configured")

    resp = requests.get(
        "https://www.strava.com/api/v3/push_subscriptions",
        params={"client_id": client_id, "client_secret": client_secret},
        timeout=15,
    )

    # Also check Firestore for local registration info
    local_doc = db.collection("system").document("webhook_subscription").get()
    local_info = local_doc.to_dict() if local_doc.exists else None

    return {
        "strava_subscriptions": resp.json() if resp.ok else [],
        "strava_status_code": resp.status_code,
        "local_registration": local_info,
    }


@router.delete("/delete-webhook")
def delete_webhook(request: Request, subscription_id: int):
    """Deletes a Strava webhook subscription by ID."""
    _check_admin(request)

    client_id = os.getenv("STRAVA_CLIENT_ID", "")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET", "")

    resp = requests.delete(
        f"https://www.strava.com/api/v3/push_subscriptions/{subscription_id}",
        data={"client_id": client_id, "client_secret": client_secret},
        timeout=15,
    )

    if resp.ok or resp.status_code == 204:
        db.collection("system").document("webhook_subscription").set(
            {"active": False, "deleted_at": datetime.now().isoformat()}, merge=True
        )
        return {"message": f"Subscription {subscription_id} deleted"}
    else:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)


# ── Manual Sync All ──────────────────────────────────────────────────────────

@router.post("/sync-all")
def sync_all_users(request: Request):
    """
    Manually triggers a sync for all Strava-connected users.
    Runs synchronously — use for small user counts or debugging.
    """
    _check_admin(request)
    from scheduler import run_daily_sync
    result = run_daily_sync()
    return result



# ── Discord Notification Test ────────────────────────────────────────────────

@router.post("/test-discord-notify")
def test_discord_notify(request: Request, uid: str, activity_date: str = ""):
    """
    Admin: sends a Discord notification (with AI coach tip) for a user's latest activity.
    Runs on the server so Gemini API is reachable.

    Query params:
        uid           - Firestore user ID (required)
        activity_date - YYYY-MM-DD to target a specific date (optional, defaults to latest)
    """
    _check_admin(request)

    # Fetch user
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail=f"User {uid} not found")
    user_data = user_doc.to_dict()

    if not user_data.get("discord_webhook_url"):
        raise HTTPException(status_code=400, detail="User has no discord_webhook_url in profile")

    # Fetch activities
    acts_ref = (db.collection("users").document(uid)
                .collection("activities")
                .order_by("start_date_local", direction="DESCENDING")
                .limit(10)
                .stream())
    activities = [(a.id, a.to_dict()) for a in acts_ref]
    if not activities:
        raise HTTPException(status_code=404, detail="No activities found for this user")

    # Find target activity
    target_act = None
    if activity_date:
        for _, act in activities:
            if act.get("start_date_local", "")[:10] == activity_date:
                target_act = act
                break
        if not target_act:
            raise HTTPException(status_code=404, detail=f"No activity found for date {activity_date}")
    else:
        target_act = activities[0][1]

    # Send Discord notification (Gemini runs server-side here ✓)
    from utils.discord import send_activity_discord_notification
    ok = send_activity_discord_notification(target_act, user_data)

    return {
        "success": ok,
        "activity": {
            "name": target_act.get("name"),
            "date": target_act.get("start_date_local", "")[:10],
            "distance_km": target_act.get("distance_km"),
            "avg_pace": target_act.get("avg_pace"),
        },
        "discord_webhook": user_data.get("discord_webhook_url", "")[:40] + "...",
    }

