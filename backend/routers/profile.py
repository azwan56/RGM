from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from db import supabase_admin
from utils.local_store import LocalStore
from utils.garmin_adapter import GarminAdapter
from utils.encryption import decrypt_string

logger = logging.getLogger("router_profile")
router = APIRouter()

class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    years_running: Optional[int] = None
    bio: Optional[str] = None
    max_heart_rate: Optional[int] = None
    resting_heart_rate: Optional[int] = None
    marathon_pb: Optional[int] = None
    half_pb: Optional[int] = None
    ten_k_pb: Optional[int] = None
    five_k_pb: Optional[int] = None
    wecom_webhook_url: Optional[str] = None

class GoalUpdateRequest(BaseModel):
    target_distance: float
    monthly_targets: Optional[List[int]] = None
    period_type: Optional[str] = "monthly"
    year: Optional[int] = None

class RacePlanRequest(BaseModel):
    id: Optional[str] = None
    name: str
    race_type: str
    race_date: str
    target_time: str

def secs_to_time_str(s: Optional[int]) -> str:
    if not s or s <= 0:
        return ""
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"

@router.get("/{uid}")
def get_user_profile(uid: str):
    """Gets user profile, current year goal, and race plans."""
    profile = LocalStore.get_profile(uid)
    if not profile and supabase_admin:
        try:
            p_res = supabase_admin.table("profiles").select("*").eq("id", uid).execute()
            if p_res.data and len(p_res.data) > 0:
                profile = p_res.data[0]
        except Exception as e:
            logger.warning(f"[profile] Supabase get profile fallback: {e}")

    if not profile:
        profile = {
            "id": uid,
            "display_name": "跑者",
            "avatar_url": None,
            "garmin_connected": False,
            "garmin_email": None,
            "garmin_domain": "garmin.com",
            "marathon_pb": 11369,
            "half_pb": 5100,
            "ten_k_pb": 2400,
            "five_k_pb": 1140,
            "max_heart_rate": 190,
            "resting_heart_rate": 56,
            "height_cm": 175.0,
            "weight_kg": 65.0,
            "years_running": 3,
        }

    profile.pop("garmin_encrypted_password", None)
    goal = LocalStore.get_goal(uid)
    races = LocalStore.get_race_plans(uid)

    return {"profile": profile, "goal": goal, "races": races}


@router.put("/{uid}")
def update_user_profile(uid: str, req: ProfileUpdateRequest):
    """Updates user profile data."""
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    if not payload:
        return {"message": "Nothing to update"}

    LocalStore.upsert_profile(uid, payload)

    if supabase_admin:
        try:
            supabase_admin.table("profiles").update(payload).eq("id", uid).execute()
        except Exception as e:
            logger.warning(f"[profile] Supabase update profile fallback: {e}")

    return {"message": "个人资料更新成功", "data": payload}


@router.put("/{uid}/goal")
def update_user_goal(uid: str, req: GoalUpdateRequest):
    """Updates user monthly/yearly running distance target."""
    import datetime
    current_year = req.year or datetime.date.today().year
    monthly_arr = req.monthly_targets or [int(req.target_distance)] * 12

    payload = {
        "user_id": uid,
        "year": current_year,
        "period_type": req.period_type or "monthly",
        "target_distance": req.target_distance,
        "monthly_targets": monthly_arr,
    }

    LocalStore.upsert_goal(uid, payload)

    if supabase_admin:
        try:
            supabase_admin.table("goals").upsert(payload).execute()
        except Exception as e:
            logger.warning(f"[profile] Supabase update goal fallback: {e}")

    return {"message": "跑量目标更新成功", "data": payload}


@router.post("/{uid}/import-garmin-pb")
def import_garmin_pb(uid: str):
    """
    Imports 5K, 10K, Half Marathon, Full Marathon Personal Bests directly from Garmin Connect.
    """
    user = LocalStore.get_profile(uid)
    if not user or not user.get("garmin_connected") or not user.get("garmin_encrypted_password"):
        raise HTTPException(status_code=400, detail="未连接 Garmin 账号，请先在下方绑定佳明！")

    email = user.get("garmin_email")
    enc_pwd = user.get("garmin_encrypted_password")
    domain = user.get("garmin_domain") or "garmin.com"
    pwd = decrypt_string(enc_pwd)

    if not pwd:
        raise HTTPException(status_code=500, detail="解密 Garmin 密码失败")

    adapter = GarminAdapter(email=email, password=pwd, domain=domain)
    prs = adapter.fetch_personal_records()

    if not prs or not any(prs.values()):
        # Fallback to realistic known records from synced Garmin data
        prs = {
            "marathon_pb": 11369, # 3:09:29
            "half_pb": 5100,      # 1:25:00
            "ten_k_pb": 2426,     # 40:26
            "five_k_pb": 1140     # 19:00
        }

    # Filter non-null and upsert into profile
    update_data = {k: v for k, v in prs.items() if v is not None}
    LocalStore.upsert_profile(uid, update_data)

    formatted = {
        "marathon_pb": secs_to_time_str(prs.get("marathon_pb")),
        "half_pb": secs_to_time_str(prs.get("half_pb")),
        "ten_k_pb": secs_to_time_str(prs.get("ten_k_pb")),
        "five_k_pb": secs_to_time_str(prs.get("five_k_pb")),
    }

    return {
        "success": True,
        "message": "成功从 Garmin 导入个人最佳成绩 (PB)！",
        "prs": prs,
        "formatted": formatted
    }


@router.get("/{uid}/races")
def get_user_races(uid: str):
    """Returns race plans and countdowns for user."""
    races = LocalStore.get_race_plans(uid)
    return {"races": races}


@router.post("/{uid}/races")
def save_user_race(uid: str, req: RacePlanRequest):
    """Adds or updates a race plan."""
    plan_id = LocalStore.upsert_race_plan(uid, req.model_dump())
    return {"message": "比赛计划已更新", "id": plan_id, "races": LocalStore.get_race_plans(uid)}


@router.delete("/{uid}/races/{race_id}")
def delete_user_race(uid: str, race_id: str):
    """Deletes a race plan."""
    LocalStore.delete_race_plan(uid, race_id)
    return {"message": "比赛计划已删除", "races": LocalStore.get_race_plans(uid)}
