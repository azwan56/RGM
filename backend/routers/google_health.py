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
    user_ref = db.collection("users").document(uid)
    try:
        count = _sync_google_health_data_inner(uid, days)
        user_ref.update({"google_health_sync_error": None})
        return count
    except Exception as e:
        import traceback
        err_str = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[Google Health Sync] Error for user {uid}: {err_str}")
        user_ref.update({"google_health_sync_error": err_str})
        raise e

def _sync_google_health_data_inner(uid: str, days: int = 14):
    access_token = get_google_access_token(uid)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Calculate range in UTC (civil dates)
    now = datetime.now(pytz.utc)
    start_time = now - timedelta(days=days)
    
    start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    start_date = start_time.strftime("%Y-%m-%d")
    
    # Initialize empty daily data dict for parsing
    daily_data = {}
    for i in range(days + 2): # extra day padding to prevent index errors
        dt_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_data[dt_str] = {
            "sleep_duration_sec": 0,
            "sleep_score": 0,
            "resting_heart_rate": 0,
            "heart_rate_variability": 0
        }

    # 1. Fetch Sleep Data
    try:
        sleep_url = "https://health.googleapis.com/v4/users/me/dataTypes/sleep/dataPoints"
        sleep_params = {"filter": f'sleep.interval.end_time >= "{start_iso}"'}
        sleep_res = requests.get(sleep_url, headers=headers, params=sleep_params, timeout=15)
        if sleep_res.ok:
            points = sleep_res.json().get("dataPoints", [])
            parsed_sessions = []
            
            for dp in points:
                sleep_obj = dp.get("sleep", {})
                interval = sleep_obj.get("interval", {})
                end_time_str = interval.get("endTime")
                start_time_str = interval.get("startTime")
                if start_time_str and end_time_str:
                    s_dt = datetime.strptime(start_time_str[:19], "%Y-%m-%dT%H:%M:%S")
                    e_dt = datetime.strptime(end_time_str[:19], "%Y-%m-%dT%H:%M:%S")
                    
                    offset_str = interval.get("endUtcOffset", "0s")
                    offset_sec = int(offset_str.replace("s", ""))
                    local_e_dt = e_dt + timedelta(seconds=offset_sec)
                    date_str = local_e_dt.strftime("%Y-%m-%d")
                    
                    platform = dp.get("dataSource", {}).get("platform", "UNKNOWN")
                    summary = sleep_obj.get("summary", {})
                    mins_asleep = int(summary.get("minutesAsleep", 0))
                    
                    parsed_sessions.append({
                        "start": s_dt,
                        "end": e_dt,
                        "date_str": date_str,
                        "mins_asleep": mins_asleep,
                        "platform": platform
                    })
            
            # Sort by start time to process sequentially
            parsed_sessions.sort(key=lambda x: x["start"])
            
            # Deduplicate overlapping sessions
            unique_sessions = []
            for s in parsed_sessions:
                overlap_idx = -1
                for idx, u in enumerate(unique_sessions):
                    # Overlap condition: start1 < end2 and start2 < end1
                    if s["start"] < u["end"] and u["start"] < s["end"]:
                        overlap_idx = idx
                        break
                
                if overlap_idx != -1:
                    existing = unique_sessions[overlap_idx]
                    # Prioritize FITBIT over other platforms
                    if s["platform"] == "FITBIT" and existing["platform"] != "FITBIT":
                        unique_sessions[overlap_idx] = s
                    elif existing["platform"] == "FITBIT" and s["platform"] != "FITBIT":
                        pass
                    else:
                        # Keep the longer session
                        if s["mins_asleep"] > existing["mins_asleep"]:
                            unique_sessions[overlap_idx] = s
                else:
                    unique_sessions.append(s)
            
            # Save deduplicated sessions into daily_data
            for s in unique_sessions:
                date_str = s["date_str"]
                if date_str in daily_data:
                    daily_data[date_str]["sleep_duration_sec"] += s["mins_asleep"] * 60
                    total_mins = daily_data[date_str]["sleep_duration_sec"] / 60.0
                    daily_data[date_str]["sleep_score"] = int(min(100, max(0, (total_mins / 480.0) * 100)))
        else:
            print(f"[Google Health Sync] Sleep API returned status {sleep_res.status_code}: {sleep_res.text}")
    except Exception as e:
        print(f"[Google Health Sync] Error fetching sleep: {e}")

    # 2. Fetch Resting Heart Rate
    try:
        rhr_url = "https://health.googleapis.com/v4/users/me/dataTypes/daily-resting-heart-rate/dataPoints"
        rhr_params = {"filter": f'daily_resting_heart_rate.date >= "{start_date}"'}
        rhr_res = requests.get(rhr_url, headers=headers, params=rhr_params, timeout=15)
        if rhr_res.ok:
            points = rhr_res.json().get("dataPoints", [])
            for dp in points:
                rhr_obj = dp.get("dailyRestingHeartRate", {})
                date_obj = rhr_obj.get("date", {})
                if date_obj.get("year") and date_obj.get("month") and date_obj.get("day"):
                    date_str = f"{date_obj['year']:04d}-{date_obj['month']:02d}-{date_obj['day']:02d}"
                    if date_str in daily_data:
                        platform = dp.get("dataSource", {}).get("platform", "UNKNOWN")
                        bpm_val = int(rhr_obj.get("beatsPerMinute", 0))
                        
                        existing_rhr = daily_data[date_str]["resting_heart_rate"]
                        existing_platform = daily_data[date_str].get("_rhr_platform", "NONE")
                        
                        # Prioritize FITBIT over HEALTH_KIT or others
                        if existing_rhr == 0 or (platform == "FITBIT" and existing_platform != "FITBIT"):
                            daily_data[date_str]["resting_heart_rate"] = bpm_val
                            daily_data[date_str]["_rhr_platform"] = platform
        else:
            print(f"[Google Health Sync] RHR API returned status {rhr_res.status_code}: {rhr_res.text}")
    except Exception as e:
        print(f"[Google Health Sync] Error fetching RHR: {e}")

    # 3. Fetch HRV Data
    try:
        hrv_url = "https://health.googleapis.com/v4/users/me/dataTypes/daily-heart-rate-variability/dataPoints"
        hrv_params = {"filter": f'daily_heart_rate_variability.date >= "{start_date}"'}
        hrv_res = requests.get(hrv_url, headers=headers, params=hrv_params, timeout=15)
        if hrv_res.ok:
            points = hrv_res.json().get("dataPoints", [])
            for dp in points:
                hrv_obj = dp.get("dailyHeartRateVariability", {})
                date_obj = hrv_obj.get("date", {})
                if date_obj.get("year") and date_obj.get("month") and date_obj.get("day"):
                    date_str = f"{date_obj['year']:04d}-{date_obj['month']:02d}-{date_obj['day']:02d}"
                    if date_str in daily_data:
                        platform = dp.get("dataSource", {}).get("platform", "UNKNOWN")
                        hrv_val = int(hrv_obj.get("averageHeartRateVariabilityMilliseconds", 0.0))
                        
                        existing_hrv = daily_data[date_str]["heart_rate_variability"]
                        existing_platform = daily_data[date_str].get("_hrv_platform", "NONE")
                        
                        # Prioritize FITBIT over HEALTH_KIT or others
                        if existing_hrv == 0 or (platform == "FITBIT" and existing_platform != "FITBIT"):
                            daily_data[date_str]["heart_rate_variability"] = hrv_val
                            daily_data[date_str]["_hrv_platform"] = platform
        else:
            print(f"[Google Health Sync] HRV API returned status {hrv_res.status_code}: {hrv_res.text}")
    except Exception as e:
        print(f"[Google Health Sync] Error fetching HRV: {e}")

    # Write to Firestore
    user_ref = db.collection("users").document(uid)
    batch = db.batch()
    synced_count = 0
    
    for date_str, metrics in daily_data.items():
        # Remove helper keys before saving
        metrics.pop("_rhr_platform", None)
        metrics.pop("_hrv_platform", None)
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
