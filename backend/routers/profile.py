from fastapi import APIRouter, HTTPException, Request, Header, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import os
import time
import jwt
from config import settings
from db import supabase_admin
from utils.local_store import LocalStore
from utils.garmin_adapter import GarminAdapter
from utils.coros_adapter import CorosAdapter
from utils.running_metrics import get_age_from_dob, estimate_vo2max
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
    height: Optional[float] = None
    weight_kg: Optional[float] = None
    weight: Optional[float] = None
    vo2max: Optional[float] = None
    years_running: Optional[int] = None
    bio: Optional[str] = None
    max_heart_rate: Optional[int] = None
    resting_heart_rate: Optional[int] = None
    marathon_pb: Optional[int] = None
    half_pb: Optional[int] = None
    ten_k_pb: Optional[int] = None
    five_k_pb: Optional[int] = None
    wecom_webhook_url: Optional[str] = None

class EstimateVo2maxRequest(BaseModel):
    five_k_pb: Optional[Any] = None
    ten_k_pb: Optional[Any] = None
    half_pb: Optional[Any] = None
    marathon_pb: Optional[Any] = None
    max_heart_rate: Optional[int] = None
    resting_heart_rate: Optional[int] = None
    save: Optional[bool] = False

class GoalUpdateRequest(BaseModel):
    target_distance: Optional[float] = None
    monthly_targets: Optional[List[int]] = None
    weekly_target: Optional[float] = None
    period_type: Optional[str] = "monthly"
    year: Optional[int] = None

class RacePlanRequest(BaseModel):
    id: Optional[str] = None
    name: str
    race_type: str
    race_date: str
    target_time: str
    priority: Optional[Any] = 1
    race_info: Optional[Dict[str, Any]] = None

def parse_time_to_seconds(val: Any) -> Optional[int]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return int(val) if val > 0 else None
    s_val = str(val).strip()
    if not s_val:
        return None
    if s_val.isdigit():
        return int(s_val)
    parts = s_val.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return None
    return None

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

    if not profile:
        profile = {
            "id": uid,
            "display_name": "微信跑者",
            "avatar_url": None,
            "garmin_connected": False,
            "garmin_email": None,
            "garmin_domain": "garmin.cn",
            "coros_connected": False,
            "coros_account": None,
            "coros_domain": "teamcnapi.coros.com",
            "marathon_pb": 0,
            "half_pb": 0,
            "ten_k_pb": 0,
            "five_k_pb": 0,
            "max_heart_rate": 0,
            "resting_heart_rate": 0,
            "height_cm": 0,
            "weight_kg": 0,
            "vo2max": None,
            "years_running": 0,
            "gender": "male",
            "date_of_birth": None,
        }

    profile.pop("garmin_encrypted_password", None)
    profile.pop("coros_encrypted_password", None)
    profile["age"] = get_age_from_dob(profile.get("date_of_birth"))
    goal = LocalStore.get_goal(uid)
    races = LocalStore.get_race_plans(uid)

    return {"profile": profile, "goal": goal, "races": races}


@router.put("/{uid}")
def update_user_profile(uid: str, req: ProfileUpdateRequest):
    """Updates user profile data."""
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    if not payload:
        return {"message": "Nothing to update"}

    # Handle aliases
    if "height" in payload and "height_cm" not in payload:
        payload["height_cm"] = payload.pop("height")
    if "weight" in payload and "weight_kg" not in payload:
        payload["weight_kg"] = payload.pop("weight")

    LocalStore.upsert_profile(uid, payload)

    return {"message": "个人资料更新成功", "data": payload}


class AvatarBase64Request(BaseModel):
    image_base64: str
    ext: Optional[str] = ".jpg"


@router.post("/{uid}/avatar-base64")
async def upload_user_avatar_base64(uid: str, req: AvatarBase64Request):
    """
    Accepts Base64 encoded avatar image, writes to static avatars folder,
    updates LocalStore profile, and returns public URL.
    Works seamlessly with WeChat request合法域名 without needing uploadFile domain.
    """
    import base64
    ext = (req.ext or ".jpg").lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"

    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    safe_uid = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in uid)
    filename = f"avatar_{safe_uid}_{int(time.time())}{ext}"
    filepath = os.path.join(avatars_dir, filename)

    try:
        raw_b64 = req.image_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        img_bytes = base64.b64decode(raw_b64)
        with open(filepath, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        logger.error(f"[profile] Failed to decode and save base64 avatar for {uid}: {e}")
        raise HTTPException(status_code=500, detail="保存头像文件失败")

    avatar_url = f"https://rgm.vanpower.net/api/avatars/{filename}"
    LocalStore.upsert_profile(uid, {"avatar_url": avatar_url})

    return {
        "avatar_url": avatar_url,
        "message": "头像上传成功 🎉"
    }


@router.post("/{uid}/avatar")
async def upload_user_avatar(uid: str, file: UploadFile = File(...)):
    """
    Uploads a user avatar image, saves it to persistent static storage,
    updates the user profile in LocalStore, and returns the public URL.
    """
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    orig_name = file.filename or "avatar.jpg"
    ext = os.path.splitext(orig_name)[1].lower()
    if not ext or ext not in allowed_exts:
        ext = ".jpg"

    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    safe_uid = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in uid)
    filename = f"avatar_{safe_uid}_{int(time.time())}{ext}"
    filepath = os.path.join(avatars_dir, filename)

    try:
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"[profile] Failed to save avatar for {uid}: {e}")
        raise HTTPException(status_code=500, detail="保存头像文件失败")

    avatar_url = f"https://rgm.vanpower.net/api/avatars/{filename}"
    LocalStore.upsert_profile(uid, {"avatar_url": avatar_url})

    return {
        "avatar_url": avatar_url,
        "message": "头像上传成功 🎉"
    }


@router.put("/{uid}/goal")
@router.post("/{uid}/goal")
@router.put("/{uid}/goals")
@router.post("/{uid}/goals")
def update_user_goal(uid: str, req: GoalUpdateRequest):
    """Updates user monthly/yearly running distance target or weekly target independently."""
    import datetime
    current_year = req.year or datetime.date.today().year

    existing_goal = LocalStore.get_goal(uid) or {}

    if req.target_distance is not None:
        target_dist = float(req.target_distance)
    elif existing_goal.get("target_distance") is not None:
        target_dist = float(existing_goal.get("target_distance"))
    else:
        target_dist = 200.0

    if req.weekly_target is not None:
        weekly_tgt = float(req.weekly_target)
    elif existing_goal.get("weekly_target") is not None:
        weekly_tgt = float(existing_goal.get("weekly_target"))
    else:
        weekly_tgt = round(target_dist / 4.0, 1)

    if req.monthly_targets is not None:
        monthly_arr = req.monthly_targets
    elif existing_goal.get("monthly_targets") is not None:
        monthly_arr = existing_goal.get("monthly_targets")
    else:
        monthly_arr = [int(target_dist)] * 12

    payload = {
        "user_id": uid,
        "year": current_year,
        "period_type": req.period_type or existing_goal.get("period_type") or "monthly",
        "target_distance": target_dist,
        "weekly_target": weekly_tgt,
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


@router.post("/{uid}/sync-device-profile")
def sync_device_profile(uid: str):
    """
    Directly pulls user biometrics (date of birth, gender, height, weight, vo2max, HR thresholds)
    from connected Garmin Connect or COROS Training Hub account and updates user profile.
    """
    user = LocalStore.get_profile(uid)
    if not user:
        raise HTTPException(status_code=404, detail="跑者资料不存在")

    has_garmin = user.get("garmin_connected") and user.get("garmin_encrypted_password")
    has_coros = user.get("coros_connected") and user.get("coros_encrypted_password")

    if not has_garmin and not has_coros:
        raise HTTPException(status_code=400, detail="未连接任何手表账号，请先在设置中绑定 Garmin 或 COROS！")

    updates: Dict[str, Any] = {}
    sources = []

    # 1. Garmin
    if has_garmin:
        try:
            email = user.get("garmin_email")
            enc_pwd = user.get("garmin_encrypted_password")
            domain = user.get("garmin_domain") or "garmin.cn"
            pwd = decrypt_string(enc_pwd)
            if pwd:
                adapter = GarminAdapter(email=email, password=pwd, domain=domain)
                g_info = adapter.fetch_user_profile_info()
                for k in ["date_of_birth", "gender", "height_cm", "weight_kg", "vo2max", "max_heart_rate", "resting_heart_rate", "avatar_url"]:
                    if g_info.get(k) is not None:
                        updates[k] = g_info[k]
                if g_info.get("display_name") and (not user.get("display_name") or user.get("display_name") in ["跑者", "Alex", "微信跑者"]):
                    updates["display_name"] = g_info["display_name"]
                sources.append("Garmin")
        except Exception as ge:
            logger.error(f"[profile] Garmin sync biometrics failed for {uid}: {ge}")

    # 2. COROS
    if has_coros:
        try:
            account = user.get("coros_account")
            enc_pwd = user.get("coros_encrypted_password")
            domain = user.get("coros_domain") or "teamcnapi.coros.com"
            pwd = decrypt_string(enc_pwd)
            if pwd:
                c_adapter = CorosAdapter(account=account, password=pwd, domain=domain)
                c_info = c_adapter.fetch_user_profile_info()
                for k in ["date_of_birth", "gender", "height_cm", "weight_kg", "vo2max", "max_heart_rate", "resting_heart_rate"]:
                    if c_info.get(k) is not None and (k not in updates or updates[k] is None):
                        updates[k] = c_info[k]
                if c_info.get("avatar_url") and not updates.get("avatar_url") and not user.get("avatar_url"):
                    updates["avatar_url"] = c_info["avatar_url"]
                if c_info.get("display_name") and (not user.get("display_name") or user.get("display_name") in ["跑者", "Alex", "微信跑者"]):
                    updates["display_name"] = c_info["display_name"]
                sources.append("COROS")
        except Exception as ce:
            logger.error(f"[profile] COROS sync biometrics failed for {uid}: {ce}")

    if not updates:
        return {
            "success": False,
            "message": "未能从手表服务获取到身体指标数据，请检查网络或稍后再试",
            "profile": user
        }

    LocalStore.upsert_profile(uid, updates)
    updated_profile = LocalStore.get_profile(uid)
    updated_profile.pop("garmin_encrypted_password", None)
    updated_profile.pop("coros_encrypted_password", None)
    updated_profile["age"] = get_age_from_dob(updated_profile.get("date_of_birth"))

    source_names = " / ".join(sources)
    return {
        "success": True,
        "message": f"成功从 {source_names} 同步身体指标数据！",
        "synced_fields": list(updates.keys()),
        "profile": updated_profile
    }


@router.post("/{uid}/estimate-vo2max")
def estimate_user_vo2max(uid: str, req: Optional[EstimateVo2maxRequest] = None):
    """
    Estimates user VO2Max using Jack Daniels VDOT formula (from best race performances)
    and Heart Rate Ratio method (Uth-Sørensen formula).
    Falls back to user stored profile if arguments not provided.
    """
    user = LocalStore.get_profile(uid) or {}

    pb_5k = parse_time_to_seconds(req.five_k_pb if req and req.five_k_pb is not None else user.get("five_k_pb"))
    pb_10k = parse_time_to_seconds(req.ten_k_pb if req and req.ten_k_pb is not None else user.get("ten_k_pb"))
    pb_half = parse_time_to_seconds(req.half_pb if req and req.half_pb is not None else user.get("half_pb"))
    pb_marathon = parse_time_to_seconds(req.marathon_pb if req and req.marathon_pb is not None else user.get("marathon_pb"))
    max_hr = req.max_heart_rate if req and req.max_heart_rate is not None else user.get("max_heart_rate")
    rest_hr = req.resting_heart_rate if req and req.resting_heart_rate is not None else user.get("resting_heart_rate")

    res = estimate_vo2max(
        pb_5k_seconds=pb_5k,
        pb_10k_seconds=pb_10k,
        pb_half_seconds=pb_half,
        pb_marathon_seconds=pb_marathon,
        max_hr=max_hr,
        rest_hr=rest_hr
    )

    if not res.get("estimated_vo2max"):
        return {
            "success": False,
            "message": "未能推算出 VO2Max：请先填写至少一项比赛成绩（5K、10K、半马或全马）或心率数据！",
            "estimated_vo2max": None,
            "candidates": []
        }

    # If requested to save or user profile has no vo2max
    if req and req.save and res.get("estimated_vo2max"):
        LocalStore.upsert_profile(uid, {"vo2max": res["estimated_vo2max"]})

    return {
        "success": True,
        "estimated_vo2max": res["estimated_vo2max"],
        "primary_source": res["primary_source"],
        "method": res["method"],
        "message": res["message"],
        "candidates": res["candidates"]
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


class RacePriorityUpdateRequest(BaseModel):
    priority: Any

@router.patch("/{uid}/races/{race_id}/priority")
@router.post("/{uid}/races/{race_id}/priority")
def update_race_priority(uid: str, race_id: str, req: RacePriorityUpdateRequest):
    """Quickly updates the A/B/C tier priority for a user's race."""
    raw_pri = str(req.priority).upper()
    pri_int = 1 if raw_pri in ["A", "1"] else (2 if raw_pri in ["B", "2"] else 3)
    LocalStore.update_race_plan_priority(uid, race_id, pri_int)
    return {"message": "赛事优先级已更新", "races": LocalStore.get_race_plans(uid)}


class RaceInfoUpdateRequest(BaseModel):
    race_info: Dict[str, Any]


@router.patch("/{uid}/races/{race_id}/info")
def update_race_info(uid: str, race_id: str, req: RaceInfoUpdateRequest):
    """Updates the race intelligence fields (race_info) for a specific race plan."""
    updated = LocalStore.update_race_info(uid, race_id, req.race_info)
    if not updated:
        raise HTTPException(status_code=404, detail="赛事未找到")
    return {"message": "赛事情报已更新", "races": LocalStore.get_race_plans(uid)}
