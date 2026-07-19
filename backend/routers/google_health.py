from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from firebase_config import db
import requests
import os
import time
from datetime import datetime, timedelta
import pytz

router = APIRouter()

class ConnectRequest(BaseModel):
    code: str
    redirect_uri: str

class SyncRequest(BaseModel):
    days: int = 14

def get_google_access_token(uid: str) -> str:
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    data = user_doc.to_dict() or {}
    
    expires_at = data.get("google_token_expires_at", 0)
    # If token is still valid (with 5-minute buffer), return it
    if expires_at > time.time() + 300:
        access_token = data.get("google_access_token")
        if access_token:
            return access_token
        
    refresh_token = data.get("google_refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Google Health not connected (missing refresh token)")
        
    client_id = os.getenv("GOOGLE_HEALTH_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_HEALTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google Health credentials missing in environment variables")
        
    # Refresh the token
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    
    res = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=10)
    if not res.ok:
        raise HTTPException(status_code=400, detail=f"Failed to refresh Google token: {res.text}")
        
    res_data = res.json()
    new_access_token = res_data["access_token"]
    new_expires_at = int(time.time() + res_data["expires_in"])
    
    update_dict = {
        "google_access_token": new_access_token,
        "google_token_expires_at": new_expires_at
    }
    # Google does not always return a new refresh token during refresh, keep the old one if absent
    if "refresh_token" in res_data:
        update_dict["google_refresh_token"] = res_data["refresh_token"]
        
    user_ref.update(update_dict)
    return new_access_token


def sync_google_health_data(uid: str, days: int = 14):
    access_token = get_google_access_token(uid)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Calculate range in UTC (civil dates)
    now = datetime.now(pytz.utc)
    start_time = now - timedelta(days=days)
    
    range_payload = {
        "range": {
            "start": {
                "date": {
                    "year": start_time.year,
                    "month": start_time.month,
                    "day": start_time.day
                }
            },
            "end": {
                "date": {
                    "year": now.year,
                    "month": now.month,
                    "day": now.day
                }
            }
        },
        "windowSizeDays": 1
    }
    
    # Initialize empty daily data dict for parsing
    daily_data = {}
    for i in range(days + 1):
        dt_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_data[dt_str] = {
            "sleep_duration_sec": 0,
            "sleep_score": 0,
            "resting_heart_rate": 0,
            "heart_rate_variability": 0
        }
        
    def parse_rollup_date(dp):
        date_obj = dp.get("date")
        if isinstance(date_obj, dict):
            y = date_obj.get("year")
            m = date_obj.get("month")
            d = date_obj.get("day")
            if y and m and d:
                return f"{y:04d}-{m:02d}-{d:02d}"
        date_str = dp.get("date")
        if isinstance(date_str, str):
            return date_str[:10]
        return None

    # 1. Fetch Sleep Data
    try:
        sleep_res = requests.post(
            "https://health.googleapis.com/v4/users/me/dataTypes/sleep/dataPoints:dailyRollUp",
            headers=headers,
            json=range_payload,
            timeout=15
        )
        if sleep_res.ok:
            points = sleep_res.json().get("rollupDataPoints", [])
            for dp in points:
                date_str = parse_rollup_date(dp)
                if date_str in daily_data:
                    val = dp.get("value", {})
                    duration = 0
                    score = 0
                    if isinstance(val, dict):
                        # Support multiple fields returned by different API revisions
                        duration = val.get("sleepDurationSeconds") or val.get("durationSeconds") or val.get("duration") or 0
                        if isinstance(duration, str) and duration.endswith("s"):
                            duration = int(float(duration[:-1]))
                        score = val.get("sleepScore") or val.get("score") or 0
                    else:
                        duration = val if isinstance(val, (int, float)) else 0
                    
                    if duration:
                        daily_data[date_str]["sleep_duration_sec"] = int(duration)
                    if score:
                        daily_data[date_str]["sleep_score"] = int(score)
        else:
            print(f"[Google Health Sync] Sleep API returned status {sleep_res.status_code}: {sleep_res.text}")
    except Exception as e:
        print(f"[Google Health Sync] Error fetching sleep: {e}")

    # 2. Fetch Resting Heart Rate
    try:
        rhr_res = requests.post(
            "https://health.googleapis.com/v4/users/me/dataTypes/daily-resting-heart-rate/dataPoints:dailyRollUp",
            headers=headers,
            json=range_payload,
            timeout=15
        )
        if rhr_res.ok:
            points = rhr_res.json().get("rollupDataPoints", [])
            for dp in points:
                date_str = parse_rollup_date(dp)
                if date_str in daily_data:
                    val = dp.get("value", {})
                    rhr = 0
                    if isinstance(val, dict):
                        bpm_min = val.get("beatsPerMinuteMin")
                        bpm_max = val.get("beatsPerMinuteMax")
                        if bpm_min and bpm_max:
                            rhr = int((bpm_min + bpm_max) / 2)
                        elif bpm_min:
                            rhr = int(bpm_min)
                    else:
                        rhr = val if isinstance(val, (int, float)) else 0
                    if rhr:
                        daily_data[date_str]["resting_heart_rate"] = rhr
        else:
            print(f"[Google Health Sync] RHR API returned status {rhr_res.status_code}: {rhr_res.text}")
    except Exception as e:
        print(f"[Google Health Sync] Error fetching RHR: {e}")

    # 3. Fetch HRV Data
    try:
        hrv_res = requests.post(
            "https://health.googleapis.com/v4/users/me/dataTypes/daily-heart-rate-variability/dataPoints:dailyRollUp",
            headers=headers,
            json=range_payload,
            timeout=15
        )
        if hrv_res.ok:
            points = hrv_res.json().get("rollupDataPoints", [])
            for dp in points:
                date_str = parse_rollup_date(dp)
                if date_str in daily_data:
                    val = dp.get("value", {})
                    hrv = 0
                    if isinstance(val, dict):
                        hrv_min = val.get("averageHeartRateVariabilityMillisecondsMin")
                        hrv_max = val.get("averageHeartRateVariabilityMillisecondsMax")
                        if hrv_min and hrv_max:
                            hrv = int((hrv_min + hrv_max) / 2)
                        elif hrv_min:
                            hrv = int(hrv_min)
                    else:
                        hrv = val if isinstance(val, (int, float)) else 0
                    if hrv:
                        daily_data[date_str]["heart_rate_variability"] = hrv
        else:
            print(f"[Google Health Sync] HRV API returned status {hrv_res.status_code}: {hrv_res.text}")
    except Exception as e:
        print(f"[Google Health Sync] Error fetching HRV: {e}")

    # Write to Firestore
    user_ref = db.collection("users").document(uid)
    batch = db.batch()
    synced_count = 0
    
    for date_str, metrics in daily_data.items():
        if metrics["sleep_duration_sec"] > 0 or metrics["resting_heart_rate"] > 0 or metrics["heart_rate_variability"] > 0:
            doc_ref = user_ref.collection("daily_recovery").document(date_str)
            metrics["date"] = date_str
            metrics["last_sync"] = datetime.now(pytz.utc).isoformat()
            batch.set(doc_ref, metrics, merge=True)
            synced_count += 1
            
    batch.commit()
    return synced_count


@router.post("/connect")
def connect_google_health(req: ConnectRequest, request: Request):
    uid = request.state.uid
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    client_id = os.getenv("GOOGLE_HEALTH_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_HEALTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google Health credentials missing in backend environment")
        
    # Exchange auth code for tokens
    payload = {
        "code": req.code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": req.redirect_uri,
        "grant_type": "authorization_code"
    }
    
    res = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=10)
    if not res.ok:
        raise HTTPException(status_code=400, detail=f"Failed to exchange Google OAuth code: {res.text}")
        
    token_data = res.json()
    
    user_ref = db.collection("users").document(uid)
    update_data = {
        "google_health_connected": True,
        "google_access_token": token_data["access_token"],
        "google_token_expires_at": int(time.time() + token_data["expires_in"]),
    }
    
    # Store refresh token if returned (typically on first consent only)
    if "refresh_token" in token_data:
        update_data["google_refresh_token"] = token_data["refresh_token"]
        
    user_ref.update(update_data)
    
    # Trigger initial sync for the past 14 days
    try:
        sync_google_health_data(uid, days=14)
    except Exception as e:
        print(f"[Google Health Connect] Initial sync failed: {e}")
        
    return {"message": "Google Health connected successfully"}


@router.post("/sync")
def trigger_google_health_sync(req: SyncRequest, request: Request):
    uid = request.state.uid
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        count = sync_google_health_data(uid, days=req.days)
        return {"message": "Google Health sync completed", "synced_days": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Health sync failed: {str(e)}")


@router.get("/recovery-status")
def get_recovery_status(request: Request, days: int = 30):
    uid = request.state.uid
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_data = user_doc.to_dict() or {}
    connected = user_data.get("google_health_connected", False)
    
    if not connected:
        return {"connected": False, "recovery_history": []}
        
    # Get recovery history from subcollection
    now_date = datetime.now().date()
    cutoff_date = (now_date - timedelta(days=days)).strftime("%Y-%m-%d")
    
    docs = (user_ref.collection("daily_recovery")
            .where("date", ">=", cutoff_date)
            .order_by("date")
            .stream())
            
    history = []
    for d in docs:
        history.append(d.to_dict())
        
    return {
        "connected": True,
        "recovery_history": history
    }
