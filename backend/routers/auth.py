from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import requests
import os
from firebase_config import db
from utils.strava_config import STRAVA_OAUTH_TOKEN_URL

router = APIRouter()

class StravaAuthRequest(BaseModel):
    code: str
    uid: str

@router.post("/strava")
def auth_strava(request: StravaAuthRequest):
    """
    Exchanges the Strava OAuth code for an access/refresh token
    and saves it to the Firebase DB under the user's UID.
    """
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Strava credentials not configured on backend.")

    # Exchange code for token
    url = STRAVA_OAUTH_TOKEN_URL
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": request.code,
        "grant_type": "authorization_code"
    }
    
    response = requests.post(url, data=payload)
    data = response.json()
    
    if not response.ok or "access_token" not in data:
        raise HTTPException(status_code=400, detail=f"Failed to authenticate with Strava: {data}")

    athlete = data.get("athlete", {})
    strava_name = " ".join(filter(None, [
        athlete.get("firstname", ""),
        athlete.get("lastname", ""),
    ])).strip() or None

    # Extract weight from Strava (in kg), sex for gender mapping
    strava_weight = athlete.get("weight")  # kg, float or None
    strava_sex = athlete.get("sex")  # "M" or "F" or None
    gender_map = {"M": "male", "F": "female"}

    # Build update payload — only set fields Strava actually provides
    strava_fields: dict = {
        "strava_access_token":  data["access_token"],
        "strava_refresh_token": data["refresh_token"],
        "strava_expires_at":    data["expires_at"],
        "strava_athlete_id":    athlete.get("id"),
        "strava_connected":     True,
        "strava_name":          strava_name,
        "strava_profile_url":   athlete.get("profile"),  # avatar URL
    }
    if strava_weight and strava_weight > 0:
        strava_fields["weight_kg"] = round(strava_weight, 1)

    # Save to Firestore — include name so leaderboard can show it immediately
    user_ref = db.collection("users").document(request.uid)

    if strava_sex and strava_sex in gender_map:
        # Only set gender if not already set by user
        existing = user_ref.get()
        if existing.exists and not existing.to_dict().get("gender"):
            strava_fields["gender"] = gender_map[strava_sex]

    user_ref.set(strava_fields, merge=True)

    # Also keep leaderboard name in sync
    try:
        lb_data = db.collection("leaderboard").document(request.uid).get()
        if lb_data.exists:
            db.collection("leaderboard").document(request.uid).set(
                {"display_name": strava_name or f"Runner #{request.uid[:6]}"},
                merge=True
            )
    except Exception:
        pass

    return {"message": "Strava connected successfully", "athlete_id": athlete.get("id"), "name": strava_name}


# ── Welcome Email ────────────────────────────────────────────────────────────

class WelcomeEmailRequest(BaseModel):
    uid: str
    email: str
    display_name: Optional[str] = None


def _send_welcome_email_task(uid: str, email: str, display_name: Optional[str]):
    """Background task: send welcome email and mark as sent in Firestore."""
    try:
        from utils.email import send_welcome_email
        name = display_name or email.split("@")[0]
        ok = send_welcome_email(email, name)
        if ok:
            db.collection("users").document(uid).set(
                {"welcome_email_sent": True}, merge=True
            )
    except Exception as e:
        print(f"[auth] Welcome email background task failed: {e}")


@router.post("/welcome-email")
def send_welcome(request: WelcomeEmailRequest, background_tasks: BackgroundTasks):
    """
    Sends a one-time welcome email to a newly registered user.
    Idempotent: checks Firestore flag to avoid duplicate sends.
    """
    # Check if already sent
    user_ref = db.collection("users").document(request.uid)
    user_doc = user_ref.get()
    if user_doc.exists and user_doc.to_dict().get("welcome_email_sent"):
        return {"message": "Welcome email already sent", "skipped": True}

    # Fire in background so response is instant
    background_tasks.add_task(
        _send_welcome_email_task,
        request.uid,
        request.email,
        request.display_name,
    )
    return {"message": "Welcome email queued", "skipped": False}

