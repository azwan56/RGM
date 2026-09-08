from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, date, timedelta
from db import supabase_admin
from utils.encryption import decrypt_string
from utils.garmin_adapter import GarminAdapter
from utils.coros_adapter import CorosAdapter
from utils.running_metrics import calculate_trimp
from utils.local_store import LocalStore

logger = logging.getLogger("router_sync")
router = APIRouter()

class SyncTriggerRequest(BaseModel):
    uid: str
    start_date: Optional[str] = None

def sync_single_user(uid: str, start_date: Optional[str] = None) -> Dict[str, Any]:
    """Core synchronization task for a single user supporting both Garmin and COROS."""
    user = LocalStore.get_profile(uid)
    if not user and supabase_admin:
        try:
            p_res = supabase_admin.table("profiles").select("*").eq("id", uid).execute()
            if p_res.data and len(p_res.data) > 0:
                user = p_res.data[0]
                LocalStore.upsert_profile(uid, user)
        except Exception as e:
            logger.warning(f"[sync] Supabase user query fallback: {e}")

    has_garmin = bool(user and user.get("garmin_connected") and user.get("garmin_encrypted_password"))
    has_coros = bool(user and user.get("coros_connected") and user.get("coros_encrypted_password"))

    if not has_garmin and not has_coros:
        # Fallback check if any syncable user exists (for dev/demo purpose)
        users = LocalStore.get_all_syncable_users()
        if users:
            uid = users[0]["id"]
            user = LocalStore.get_profile(uid)
            has_garmin = bool(user and user.get("garmin_connected") and user.get("garmin_encrypted_password"))
            has_coros = bool(user and user.get("coros_connected") and user.get("coros_encrypted_password"))

    if not user or (not has_garmin and not has_coros):
        return {
            "success": False, 
            "error": "尚未绑定 Garmin 或 COROS 运动设备。请先前往【我的】页面绑定 Garmin (佳明) 或 COROS (高驰) 账号进行连接。"
        }

    try:
        all_activities: List[Dict[str, Any]] = []
        synced_health = False
        sync_time_iso = datetime.utcnow().isoformat() + "Z"
        profile_updates: Dict[str, Any] = {}

        # 1. Sync Garmin if connected
        if has_garmin:
            try:
                email = user.get("garmin_email")
                enc_pwd = user.get("garmin_encrypted_password")
                domain = user.get("garmin_domain") or "garmin.cn"
                pwd = decrypt_string(enc_pwd)
                if pwd:
                    garmin_adapter = GarminAdapter(email=email, password=pwd, domain=domain)
                    try:
                        g_info = garmin_adapter.fetch_user_profile_info()
                        if g_info.get("avatar_url") and not profile_updates.get("avatar_url"):
                            profile_updates["avatar_url"] = g_info["avatar_url"]
                        if g_info.get("display_name") and (not user.get("display_name") or user.get("display_name") in ["跑者", "Alex", "微信跑者"]):
                            profile_updates["display_name"] = g_info["display_name"]
                        if g_info.get("weight_kg") and not user.get("weight_kg") and not user.get("weight"):
                            profile_updates["weight_kg"] = g_info["weight_kg"]
                        if g_info.get("height_cm") and not user.get("height_cm") and not user.get("height"):
                            profile_updates["height_cm"] = g_info["height_cm"]
                        if g_info.get("date_of_birth") and not user.get("date_of_birth"):
                            profile_updates["date_of_birth"] = g_info["date_of_birth"]
                        if g_info.get("gender") and not user.get("gender"):
                            profile_updates["gender"] = g_info["gender"]
                        if g_info.get("vo2max") and not user.get("vo2max"):
                            profile_updates["vo2max"] = g_info["vo2max"]
                        if g_info.get("max_heart_rate") and (not user.get("max_heart_rate") or user.get("max_heart_rate") == 190):
                            profile_updates["max_heart_rate"] = g_info["max_heart_rate"]
                        if g_info.get("resting_heart_rate") and (not user.get("resting_heart_rate") or user.get("resting_heart_rate") == 56):
                            profile_updates["resting_heart_rate"] = g_info["resting_heart_rate"]
                    except Exception as pe:
                        logger.warning(f"[sync] Garmin profile fetch error: {pe}")

                    year_start = start_date or f"{date.today().year}-01-01"
                    g_acts = garmin_adapter.fetch_activities_by_date(start_date=year_start)
                    if not g_acts:
                        g_acts = garmin_adapter.fetch_recent_activities(limit=100)
                    all_activities.extend(g_acts)

                    for i in range(7):
                        d = (date.today() - timedelta(days=i)).isoformat()
                        try:
                            h_metrics = garmin_adapter.fetch_daily_health_metrics(d)
                            if h_metrics and any(h_metrics.get(k) is not None for k in ["resting_heart_rate", "sleep_score", "hrv_last_night_avg", "body_battery_max"]):
                                LocalStore.upsert_daily_health(uid, h_metrics)
                                synced_health = True
                        except Exception as he:
                            logger.warning(f"[sync] Garmin health fetch error on {d} for {uid}: {he}")

                    profile_updates["garmin_last_sync_at"] = sync_time_iso
            except Exception as ge:
                logger.error(f"[sync] Garmin sync error for {uid}: {ge}")

        # 2. Sync COROS if connected
        if has_coros:
            try:
                account = user.get("coros_account")
                enc_pwd = user.get("coros_encrypted_password")
                domain = user.get("coros_domain") or "teamcnapi.coros.com"
                pwd = decrypt_string(enc_pwd)
                if pwd:
                    coros_adapter = CorosAdapter(account=account, password=pwd, domain=domain)
                    try:
                        c_info = coros_adapter.fetch_user_profile_info()
                        if c_info.get("avatar_url") and not profile_updates.get("avatar_url"):
                            profile_updates["avatar_url"] = c_info["avatar_url"]
                        if c_info.get("display_name") and (not user.get("display_name") or user.get("display_name") in ["跑者", "Alex", "微信跑者"]):
                            profile_updates["display_name"] = c_info["display_name"]
                        if c_info.get("weight_kg"):
                            profile_updates["weight_kg"] = c_info["weight_kg"]
                        if c_info.get("height_cm"):
                            profile_updates["height_cm"] = c_info["height_cm"]
                        if c_info.get("date_of_birth"):
                            profile_updates["date_of_birth"] = c_info["date_of_birth"]
                        if c_info.get("gender"):
                            profile_updates["gender"] = c_info["gender"]
                        if c_info.get("vo2max"):
                            profile_updates["vo2max"] = c_info["vo2max"]
                        if c_info.get("max_heart_rate"):
                            profile_updates["max_heart_rate"] = c_info["max_heart_rate"]
                        if c_info.get("resting_heart_rate"):
                            profile_updates["resting_heart_rate"] = c_info["resting_heart_rate"]
                    except Exception as pe:
                        logger.warning(f"[sync] COROS profile fetch error: {pe}")

                    year_start = start_date or f"{date.today().year}-01-01"
                    c_acts = coros_adapter.fetch_activities_by_date(start_date=year_start)
                    if not c_acts:
                        c_acts = coros_adapter.fetch_recent_activities(limit=100)
                    all_activities.extend(c_acts)

                    for i in range(7):
                        d = (date.today() - timedelta(days=i)).isoformat()
                        try:
                            h_metrics = coros_adapter.fetch_daily_health_metrics(d)
                            if h_metrics and any(h_metrics.get(k) is not None for k in ["resting_heart_rate", "sleep_score", "vo2_max", "hrv_last_night_avg"]):
                                LocalStore.upsert_daily_health(uid, h_metrics)
                                synced_health = True
                        except Exception as he:
                            logger.warning(f"[sync] COROS health fetch error on {d} for {uid}: {he}")

                    profile_updates["coros_last_sync_at"] = sync_time_iso
            except Exception as ce:
                logger.error(f"[sync] COROS sync error for {uid}: {ce}")

        # 3. Apply profile updates
        if profile_updates:
            LocalStore.upsert_profile(uid, profile_updates)
            if supabase_admin:
                try:
                    supabase_admin.table("profiles").update(profile_updates).eq("id", uid).execute()
                except Exception as se:
                    logger.warning(f"[sync] Supabase profile update error: {se}")

        # 4. Process and upsert activities
        saved_count = 0
        rest_hr = user.get("resting_heart_rate") or 60
        max_hr = user.get("max_heart_rate") or 190
        gender = user.get("gender") or "male"

        for act in all_activities:
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

        return {
            "success": True,
            "synced_activities": saved_count,
            "synced_health": synced_health,
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
    result = sync_single_user(req.uid, start_date=req.start_date)
    return result
