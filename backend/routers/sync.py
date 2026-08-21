from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, date
from db import supabase_admin
from utils.encryption import decrypt_string
from utils.garmin_adapter import GarminAdapter
from utils.running_metrics import calculate_trimp
from utils.local_store import LocalStore

logger = logging.getLogger("router_sync")
router = APIRouter()

class SyncTriggerRequest(BaseModel):
    uid: str

def sync_single_user(uid: str) -> Dict[str, Any]:
    """Core synchronization task for a single user with smart fallback."""
    user = LocalStore.get_profile(uid)
    if not user and supabase_admin:
        try:
            p_res = supabase_admin.table("profiles").select("*").eq("id", uid).execute()
            if p_res.data and len(p_res.data) > 0:
                user = p_res.data[0]
                LocalStore.upsert_profile(uid, user)
        except Exception as e:
            logger.warning(f"[sync] Supabase user query fallback: {e}")

    if not user or not user.get("garmin_connected"):
        users = LocalStore.get_all_garmin_connected_users()
        if users:
            uid = users[0]["id"]
            user = LocalStore.get_profile(uid)

    if not user:
        return {"success": False, "error": "尚未绑定 Garmin 账号。请先前往【跑者档案与目标】或点击右上角【绑定 Garmin 账号】进行连接。"}

    if not user.get("garmin_connected") or not user.get("garmin_encrypted_password"):
        return {"success": False, "error": "尚未绑定 Garmin 账号。请先点击【绑定 Garmin 账号】进行连接。"}

    try:
        email = user.get("garmin_email")
        enc_pwd = user.get("garmin_encrypted_password")
        domain = user.get("garmin_domain") or "garmin.com"
        password = decrypt_string(enc_pwd)

        if not password:
            return {"success": False, "error": "Failed to decrypt Garmin credentials"}

        # 2. Login to Garmin
        adapter = GarminAdapter(email=email, password=password, domain=domain)
        activities = adapter.fetch_recent_activities(limit=30)
        
        # 3. Process and upsert activities
        saved_count = 0
        rest_hr = user.get("resting_heart_rate") or 60
        max_hr = user.get("max_heart_rate") or 190
        gender = user.get("gender") or "male"

        for act in activities:
            # Calculate TRIMP
            moving_mins = (act.get("moving_time_seconds") or 0) / 60.0
            avg_hr = act.get("average_heartrate")
            if avg_hr and avg_hr > rest_hr:
                act["trimp"] = calculate_trimp(moving_mins, avg_hr, rest_hr, max_hr, gender)
            else:
                act["trimp"] = round(moving_mins * 0.8, 1)

            act["user_id"] = uid
            LocalStore.upsert_activity(act)
            saved_count += 1

        # 4. Fetch daily health metrics
        health = adapter.fetch_daily_health_metrics()
        if health:
            LocalStore.upsert_daily_health(uid, health)

        # 5. Update last sync time
        sync_time_iso = datetime.utcnow().isoformat() + "Z"
        LocalStore.upsert_profile(uid, {"garmin_last_sync_at": sync_time_iso})

        return {
            "success": True,
            "synced_activities": saved_count,
            "synced_health": bool(health),
            "last_sync_at": sync_time_iso,
        }
    except Exception as e:
        logger.error(f"[sync] Error during synchronization for user {uid}: {e}")
        return {"success": False, "error": str(e)}

@router.post("/trigger")
def trigger_sync(req: SyncTriggerRequest):
    """
    Synchronous trigger for manual sync button in frontend and miniapp.
    """
    result = sync_single_user(req.uid)
    return result
