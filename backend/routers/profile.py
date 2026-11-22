from fastapi import APIRouter, HTTPException, Request, Header, UploadFile, File, Query
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
from utils.running_metrics import get_age_from_dob, estimate_vo2max, compute_canova_athlete_matrix
from utils.encryption import decrypt_string, compute_age_group
from utils.security import (
    validate_uploaded_image_bytes,
    is_strict_auth_mode,
    enforce_rate_limit,
    get_client_ip,
    MAX_IMAGE_UPLOAD_BYTES,
)

logger = logging.getLogger("router_profile")
router = APIRouter()


def _verify_profile_access(request: Optional[Request], target_uid: str) -> None:
    """Enforces JWT ownership on profile endpoints (fail-closed in strict/production mode, and whenever a token is presented)."""
    if not request:
        return
    token_uid = getattr(request.state, "user_id", None)
    token_is_sa = bool(getattr(request.state, "is_super_admin", False))
    if is_strict_auth_mode() and not token_uid and not token_is_sa:
        raise HTTPException(status_code=401, detail="安全拦截：请先登录后访问个人档案")
    if token_uid and not token_is_sa and not LocalStore.is_super_admin(token_uid):
        if LocalStore.resolve_user_id(token_uid) != LocalStore.resolve_user_id(target_uid):
            raise HTTPException(status_code=403, detail="安全拦截：无权访问或修改他人个人档案")


def _cleanup_old_local_avatar(prev_avatar_url: Optional[str], new_filename: str) -> None:
    if not prev_avatar_url or "/api/avatars/" not in str(prev_avatar_url):
        return
    old_name = os.path.basename(str(prev_avatar_url).split("?")[0])
    if not old_name or old_name == new_filename or old_name.startswith("default-"):
        return
    avatars_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars"))
    old_path = os.path.abspath(os.path.join(avatars_dir, old_name))
    if old_path.startswith(avatars_dir + os.sep) and os.path.isfile(old_path):
        try:
            os.remove(old_path)
        except Exception:
            pass

class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    real_name: Optional[str] = None
    id_card: Optional[str] = None
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
    program: Optional[str] = None
    class_detail: Optional[str] = None
    class_name: Optional[str] = None
    gobi_experience: Optional[str] = None
    emergency_contact: Optional[str] = None
    clothing_size: Optional[str] = None
    shoe_size: Optional[str] = None
    health_declaration: Optional[Any] = None
    hide_gps_route: Optional[bool] = None
    hide_biometrics: Optional[bool] = None
    canova_critique_visibility: Optional[str] = None
    canova_critique_club_ids: Optional[List[str]] = None
    first_aid_cert_type: Optional[str] = None
    pacer_bio_tags: Optional[str] = None
    city: Optional[str] = None
    running_landmarks: Optional[List[str]] = None
    usual_time_slot: Optional[str] = None
    looking_for_buddy: Optional[bool] = None
    allow_buddy_search_scope: Optional[str] = None
    allow_club_search_scope: Optional[str] = None

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
    monthly_target: Optional[float] = None
    monthly_targets: Optional[Any] = None
    weekly_target: Optional[float] = None
    next_weekly_target: Optional[float] = None
    period_type: Optional[str] = "monthly"
    year: Optional[int] = None
    target_period: Optional[str] = None
    target_month: Optional[int] = None
    enforce_started_lock: Optional[bool] = True

class RacePlanRequest(BaseModel):
    id: Optional[str] = None
    name: str
    race_type: str
    race_date: str
    target_time: str
    priority: Optional[Any] = 1
    race_info: Optional[Dict[str, Any]] = None
    status: Optional[str] = "upcoming"
    finish_time: Optional[str] = None
    finish_notes: Optional[str] = None
    photo_url: Optional[str] = None
    photos: Optional[List[str]] = None
    was_official_pacer: Optional[bool] = None
    pacer_target_time: Optional[str] = None

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
def get_user_profile(
    uid: str,
    request: Request,
    include_miniapp_bundle: bool = Query(
        False,
        description="Bundle orgs, onboarding_status, yearly_stats, vdot, and support_tickets for MiniApp Profile",
    ),
):
    """Gets user profile, current year goal, and race plans (and optional MiniApp bundle)."""
    _verify_profile_access(request, uid)
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

    has_saved_coros_pwd = bool(profile.get("coros_encrypted_password"))
    for _secret_col in (
        "password_hash",
        "phone_hmac",
        "garmin_encrypted_password",
        "coros_encrypted_password",
        "wechat_openid",
        "wechat_unionid",
    ):
        profile.pop(_secret_col, None)
    profile["coros_has_saved_password"] = has_saved_coros_pwd
    if profile.get("coros_connected") and profile.get("coros_account"):
        from utils.coros_adapter import CorosAdapter
        c_state = CorosAdapter.get_cached_auth_state(
            profile.get("coros_account") or "",
            profile.get("coros_domain") or "teamcnapi.coros.com",
        )
        profile["coros_needs_reauth"] = bool(c_state.get("needs_reauth"))
        profile["coros_auth_error"] = c_state.get("blocked_error") or ""
    else:
        profile["coros_needs_reauth"] = False
        profile["coros_auth_error"] = ""
    profile["age"] = get_age_from_dob(profile.get("date_of_birth"))
    profile["age_group"] = compute_age_group(profile.get("date_of_birth"))
    dob_val = profile.get("date_of_birth") or ""
    profile["birth_year"] = dob_val[:4] if len(dob_val) >= 4 and dob_val[:4].isdigit() else ""
    owner_uid = profile.get("id") or uid
    clubs = LocalStore.get_user_clubs(owner_uid) or []
    organizations: Optional[List[Dict[str, Any]]] = None
    if include_miniapp_bundle:
        organizations = LocalStore.get_user_organizations(owner_uid)
    profile["is_coach_or_owner"] = LocalStore.is_user_coach_or_owner(
        owner_uid, preloaded_clubs=clubs, preloaded_orgs=organizations
    )
    profile["hide_gps_route"] = bool(profile.get("hide_gps_route"))
    profile["hide_biometrics"] = bool(profile.get("hide_biometrics"))
    profile["canova_critique_visibility"] = LocalStore.normalize_canova_critique_visibility(
        profile.get("canova_critique_visibility")
    )
    profile["canova_critique_club_ids"] = LocalStore.parse_canova_critique_club_ids(
        profile.get("canova_critique_club_ids")
    )
    profile["first_aid_cert_type"] = profile.get("first_aid_cert_type") or ""
    profile["pacer_bio_tags"] = profile.get("pacer_bio_tags") or ""
    profile["city"] = profile.get("city") or ""
    profile["running_landmarks"] = LocalStore.parse_running_landmarks(profile.get("running_landmarks"))
    profile["usual_time_slot"] = profile.get("usual_time_slot") or ""
    lfb_val = profile.get("looking_for_buddy")
    profile["looking_for_buddy"] = True if lfb_val is None else bool(lfb_val)
    profile["allow_buddy_search_scope"] = LocalStore.normalize_buddy_search_scope(
        profile.get("allow_buddy_search_scope")
    )
    profile["allow_club_search_scope"] = LocalStore.normalize_club_search_scope(
        profile.get("allow_club_search_scope")
    )
    goal = LocalStore.get_goal(owner_uid)
    races = LocalStore.get_race_plans(owner_uid)

    payload: Dict[str, Any] = {"profile": profile, "goal": goal, "races": races, "clubs": clubs}
    if include_miniapp_bundle:
        today_bj = LocalStore.get_beijing_today()
        yearly_stats = LocalStore.get_yearly_stats(owner_uid, year=today_bj.year, goal_info=goal)
        support_tickets = LocalStore.get_user_support_tickets(owner_uid)

        local_acts = LocalStore.get_recent_activities(
            owner_uid,
            limit=100,
            include_splits=False,
            include_critiques=False,
            include_route_preview=False,
            profile=profile,
        )
        vdot_val: Optional[float] = None
        try:
            health_bundle = LocalStore.get_health_bundle_30d(owner_uid)
            health_data = health_bundle.get("latest_health")
            has_watch_vo2 = bool(
                (health_data and health_data.get("vo2_max") and float(health_data.get("vo2_max") or 0) > 0)
                or (profile.get("vo2max") is not None and float(profile.get("vo2max") or 0) > 0)
            )
            v_meta_pb = LocalStore.resolve_verified_runner_profile_and_pbs(
                owner_uid,
                profile=profile,
                recent_acts=local_acts,
                query_activities=(len(local_acts) >= 100),
            )
            has_verified_pb = bool(
                v_meta_pb.get("verified_mp_sec")
                or v_meta_pb.get("verified_hp_sec")
                or v_meta_pb.get("verified_10k_sec")
                or v_meta_pb.get("verified_5k_sec")
            )
            if local_acts or has_watch_vo2 or has_verified_pb:
                ctl_val = 0.0
                tsb_val = 0.0
                if local_acts:
                    try:
                        from utils.metrics_domain import MetricsDomainService
                        load_summary = MetricsDomainService.compute_load_and_form(
                            activities=local_acts,
                            profile=profile,
                            window_days=30,
                            warmup_days=180,
                        )
                        ctl_val = float(load_summary.get("current_ctl") or 0.0)
                        tsb_val = float(load_summary.get("current_tsb") or 0.0)
                    except Exception:
                        pass
                clean_prof = {
                    **profile,
                    "marathon_pb": v_meta_pb.get("verified_mp_sec"),
                    "half_pb": v_meta_pb.get("verified_hp_sec"),
                    "ten_k_pb": v_meta_pb.get("verified_10k_sec"),
                    "five_k_pb": v_meta_pb.get("verified_5k_sec"),
                    "peak_vdot": v_meta_pb.get("peak_vdot"),
                    "peak_endurance_vdot": v_meta_pb.get("peak_endurance_vdot"),
                }
                trend_30d = health_bundle.get("trend_30d") or ([health_data] if health_data else [])
                canova_mat = compute_canova_athlete_matrix(
                    profile=clean_prof,
                    activities=local_acts,
                    current_ctl=ctl_val,
                    current_tsb=tsb_val,
                    health_trend=trend_30d,
                )
                eff_v = canova_mat.get("effective_vdot")
                if eff_v and float(eff_v) > 0:
                    vdot_val = round(float(eff_v), 1)
        except Exception as ve:
            logger.warning(f"[profile] Bundle VDOT calc skipped: {ve}")
        if vdot_val is None and profile.get("vo2max") is not None:
            try:
                vdot_val = round(float(profile["vo2max"]), 1)
            except Exception:
                pass

        onboarding_status = LocalStore.get_user_onboarding_status(
            owner_uid,
            preloaded_profile=profile,
            preloaded_clubs=clubs,
            preloaded_goal=goal,
            preloaded_has_activities=True if local_acts else None,
        )
        payload.update({
            "organizations": organizations or [],
            "onboarding_status": onboarding_status,
            "yearly_stats": yearly_stats,
            "vdot": vdot_val,
            "support_tickets": support_tickets,
        })

    return payload


@router.put("/{uid}")
def update_user_profile(uid: str, req: ProfileUpdateRequest, request: Request):
    """Updates user profile data."""
    _verify_profile_access(request, uid)
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    if not payload:
        return {"message": "Nothing to update"}

    # Handle aliases
    if "height" in payload and "height_cm" not in payload:
        payload["height_cm"] = payload.pop("height")
    if "weight" in payload and "weight_kg" not in payload:
        payload["weight_kg"] = payload.pop("weight")

    ugc_parts = [str(payload[k]).strip() for k in ("display_name", "bio", "injury_history", "notes") if payload.get(k)]
    if ugc_parts:
        from utils.wechat import wechat_client
        prof_cur = LocalStore.get_profile(uid) or {}
        wechat_client.ensure_ugc_text_safe("\n".join(ugc_parts), openid=prof_cur.get("wechat_openid"), scene=1)

    LocalStore.upsert_profile(uid, payload)

    return {"message": "个人资料更新成功", "data": payload}


@router.post("/{uid}/purge-privacy")
def purge_user_privacy_endpoint(uid: str, request: Request):
    """
    Permanently wipes all sensitive privacy and personal identity data for the runner.
    Athletic logs and historical mileage are retained with an anonymized persona.
    """
    _verify_profile_access(request, uid)
    if not uid:
        raise HTTPException(status_code=400, detail="缺少用户标识")
    result = LocalStore.purge_user_privacy_data(uid)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "用户不存在"))
    return result


@router.delete("/{uid}")
@router.post("/{uid}/delete-account")
def delete_user_account_endpoint(uid: str, request: Request):
    """
    App Store Guideline 5.1.1(v) & PIPL compliant complete account deletion.
    Permanently deletes user credentials, personal identity, GPS tracks, biometrics, and memberships.
    """
    _verify_profile_access(request, uid)
    if not uid:
        raise HTTPException(status_code=400, detail="缺少用户标识")
    result = LocalStore.delete_user_account_completely(uid)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "用户不存在"))
    return {"success": True, "message": "账号及全部个人数据已永久删除注销", "uid": uid}



class AvatarBase64Request(BaseModel):
    image_base64: str
    ext: Optional[str] = ".jpg"


@router.post("/{uid}/avatar-base64")
async def upload_user_avatar_base64(uid: str, req: AvatarBase64Request, request: Request):
    """
    Accepts Base64 encoded avatar image, validates magic bytes & size, writes to static avatars folder,
    updates LocalStore profile, and returns public URL.
    """
    _verify_profile_access(request, uid)
    import base64
    raw_ext = (req.ext or ".jpg").lower()
    if not raw_ext.startswith("."):
        raw_ext = f".{raw_ext}"

    raw_b64 = (req.image_base64 or "").strip()
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    if len(raw_b64) > (MAX_IMAGE_UPLOAD_BYTES * 4 // 3) + 4096:
        raise HTTPException(status_code=413, detail="头像图片超过 10MB 上限")

    try:
        img_bytes = base64.b64decode(raw_b64, validate=False)
    except Exception as e:
        logger.error(f"[profile] Failed to decode base64 avatar for {uid}: {e}")
        raise HTTPException(status_code=400, detail="头像 Base64 编码无效")

    ext = validate_uploaded_image_bytes(img_bytes, f"avatar{raw_ext}")

    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    prev_prof = LocalStore.get_profile(uid) or {}
    safe_uid = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in uid)
    filename = f"avatar_{safe_uid}_{int(time.time())}{ext}"
    filepath = os.path.join(avatars_dir, filename)

    try:
        with open(filepath, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        logger.error(f"[profile] Failed to save base64 avatar for {uid}: {e}")
        raise HTTPException(status_code=500, detail="保存头像文件失败")

    avatar_url = f"https://rgm.vanpower.net/api/avatars/{filename}"
    LocalStore.upsert_profile(uid, {"avatar_url": avatar_url})
    _cleanup_old_local_avatar(prev_prof.get("avatar_url"), filename)

    return {
        "avatar_url": avatar_url,
        "message": "头像上传成功 🎉"
    }


@router.post("/{uid}/avatar")
async def upload_user_avatar(uid: str, request: Request, file: UploadFile = File(...)):
    """
    Uploads a user avatar image, saves it to persistent static storage,
    updates the user profile in LocalStore, and returns the public URL.
    """
    _verify_profile_access(request, uid)
    orig_name = file.filename or "avatar.jpg"
    contents = await file.read(MAX_IMAGE_UPLOAD_BYTES + 1)
    ext = validate_uploaded_image_bytes(contents, orig_name)

    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    prev_prof = LocalStore.get_profile(uid) or {}
    safe_uid = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in uid)
    filename = f"avatar_{safe_uid}_{int(time.time())}{ext}"
    filepath = os.path.join(avatars_dir, filename)

    try:
        with open(filepath, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"[profile] Failed to save avatar for {uid}: {e}")
        raise HTTPException(status_code=500, detail="保存头像文件失败")

    avatar_url = f"https://rgm.vanpower.net/api/avatars/{filename}"
    LocalStore.upsert_profile(uid, {"avatar_url": avatar_url})
    _cleanup_old_local_avatar(prev_prof.get("avatar_url"), filename)

    return {
        "avatar_url": avatar_url,
        "message": "头像上传成功 🎉"
    }


@router.put("/{uid}/goal")
@router.post("/{uid}/goal")
@router.put("/{uid}/goals")
@router.post("/{uid}/goals")
def update_user_goal(uid: str, req: GoalUpdateRequest, request: Request):
    """Updates user monthly/yearly running distance target or weekly target independently.
    Started weekly and monthly plans are locked and cannot be modified; only unstarted plans can be updated.
    """
    _verify_profile_access(request, uid)
    import datetime
    today = datetime.date.today()
    current_year = req.year or today.year

    if req.target_period == "current_week":
        raise HTTPException(
            status_code=400,
            detail="本周计划已开始，不能更改！仅可申报或修改下周（未开始）的周计划。"
        )
    if req.target_month is not None:
        if current_year < today.year or (current_year == today.year and int(req.target_month) <= today.month):
            raise HTTPException(
                status_code=400,
                detail=f"{req.target_month}月计划已开始，不能更改！仅可申报或修改未开始的月份计划。"
            )

    existing_goal = LocalStore.get_goal(uid) or {}

    req_dist = req.target_distance if req.target_distance is not None else req.monthly_target
    if req_dist is not None:
        target_dist = float(req_dist)
    elif existing_goal.get("target_distance") is not None:
        target_dist = float(existing_goal.get("target_distance"))
    else:
        target_dist = 200.0

    requested_weekly = req.next_weekly_target if req.next_weekly_target is not None else req.weekly_target
    if requested_weekly is not None:
        weekly_tgt = float(requested_weekly)
    elif existing_goal.get("weekly_target") is not None:
        weekly_tgt = float(existing_goal.get("weekly_target"))
    else:
        weekly_tgt = round(target_dist / 4.0, 1)

    if req.monthly_targets is not None:
        if isinstance(req.monthly_targets, dict):
            monthly_arr = [int(float(req.monthly_targets.get(str(m), req.monthly_targets.get(m, target_dist)))) for m in range(1, 13)]
        elif isinstance(req.monthly_targets, list):
            monthly_arr = [int(float(v)) for v in req.monthly_targets]
        else:
            monthly_arr = [int(target_dist)] * 12
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
        "next_weekly_target": weekly_tgt,
        "monthly_targets": monthly_arr,
    }

    enforce_lock = True if req.enforce_started_lock is None else bool(req.enforce_started_lock)
    LocalStore.upsert_goal(uid, payload, enforce_started_lock=enforce_lock)
    saved_goal = LocalStore.get_goal(uid) or payload

    if supabase_admin:
        try:
            supabase_admin.table("goals").upsert({
                "user_id": uid,
                "year": current_year,
                "period_type": saved_goal.get("period_type") or "monthly",
                "target_distance": saved_goal.get("target_distance") or target_dist,
                "weekly_target": saved_goal.get("weekly_target") or weekly_tgt,
                "monthly_targets": saved_goal.get("monthly_targets") or monthly_arr,
            }).execute()
        except Exception as e:
            logger.warning(f"[profile] Supabase update goal fallback: {e}")

    return {
        "message": "未开始的周/月计划已更新（已开始的当前周及已开始月份已锁定保持不变）",
        "data": saved_goal,
        "goal": saved_goal,
    }


@router.post("/{uid}/import-garmin-pb")
def import_garmin_pb(uid: str, request: Request):
    """
    Imports 5K, 10K, Half Marathon, Full Marathon Personal Bests directly from Garmin Connect.
    """
    _verify_profile_access(request, uid)
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
    prs = adapter.fetch_personal_records() or {}

    if not any(prs.values()):
        return {
            "success": False,
            "message": "未在您的 Garmin 账号中读取到官方最佳成绩纪录（PB），您可在下方手动填写或先同步历史跑步活动。",
            "prs": {},
            "formatted": {
                "marathon_pb": secs_to_time_str(user.get("marathon_pb")),
                "half_pb": secs_to_time_str(user.get("half_pb")),
                "ten_k_pb": secs_to_time_str(user.get("ten_k_pb")),
                "five_k_pb": secs_to_time_str(user.get("five_k_pb")),
            },
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
def sync_device_profile(uid: str, request: Request):
    """
    Directly pulls user biometrics (date of birth, gender, height, weight, vo2max, HR thresholds)
    from connected Garmin Connect or COROS Training Hub account and updates user profile.
    """
    _verify_profile_access(request, uid)
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
                if g_info.get("display_name") and not user.get("display_name"):
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
                if c_info.get("display_name") and not user.get("display_name"):
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
def estimate_user_vo2max(uid: str, request: Request, req: Optional[EstimateVo2maxRequest] = None):
    """
    Estimates user VO2Max using Jack Daniels VDOT formula (from best race performances)
    and Heart Rate Ratio method (Uth-Sørensen formula).
    When the user already has watch-synced VO2Max data, returns the watch VO2Max directly without recalculating.
    """
    _verify_profile_access(request, uid)
    user = LocalStore.get_profile(uid) or {}
    health = LocalStore.get_latest_health(uid) or {}
    has_watch = bool(
        user.get("garmin_connected")
        or user.get("coros_connected")
        or user.get("apple_health_connected")
        or user.get("huawei_health_connected")
        or health.get("vo2_max")
    )
    watch_vo2 = health.get("vo2_max") or user.get("vo2max")
    if has_watch and watch_vo2 is not None and float(watch_vo2) > 0:
        w_val = round(float(watch_vo2), 1)
        if health.get("vo2_max") and user.get("vo2max") != w_val:
            LocalStore.upsert_profile(uid, {"vo2max": w_val})
        return {
            "success": True,
            "estimated_vo2max": w_val,
            "primary_source": "运动手表同步数据",
            "method": "手表实测 VO2Max 直读（不另作推算）",
            "message": f"检测到已同步手表 VO2Max 数据 ({w_val})，直接使用手表数据，不另作推算。",
            "candidates": [{"source": "运动手表实测", "method": "手表直读", "value": w_val}],
        }

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
def get_user_races(uid: str, request: Request):
    """Returns race plans and countdowns for user."""
    _verify_profile_access(request, uid)
    races = LocalStore.get_race_plans(uid)
    return {"races": races}


@router.post("/{uid}/races")
def save_user_race(uid: str, req: RacePlanRequest, request: Request):
    """Adds or updates a race plan."""
    _verify_profile_access(request, uid)
    plan_id = LocalStore.upsert_race_plan(uid, req.model_dump())
    return {"message": "比赛计划已更新", "id": plan_id, "races": LocalStore.get_race_plans(uid)}


@router.delete("/{uid}/races/{race_id}")
def delete_user_race(uid: str, race_id: str, request: Request):
    """Deletes a race plan."""
    _verify_profile_access(request, uid)
    LocalStore.delete_race_plan(uid, race_id)
    return {"message": "比赛计划已删除", "races": LocalStore.get_race_plans(uid)}


class RacePriorityUpdateRequest(BaseModel):
    priority: Any

@router.patch("/{uid}/races/{race_id}/priority")
@router.put("/{uid}/races/{race_id}/priority")
@router.post("/{uid}/races/{race_id}/priority")
def update_race_priority(uid: str, race_id: str, req: RacePriorityUpdateRequest, request: Request):
    """Quickly updates the A/B/C tier priority for a user's race."""
    _verify_profile_access(request, uid)
    raw_pri = str(req.priority).upper()
    pri_int = 1 if raw_pri in ["A", "1"] else (2 if raw_pri in ["B", "2"] else 3)
    LocalStore.update_race_plan_priority(uid, race_id, pri_int)
    return {"message": "赛事优先级已更新", "races": LocalStore.get_race_plans(uid)}


class RaceInfoUpdateRequest(BaseModel):
    race_info: Dict[str, Any]


@router.put("/{uid}/races/{race_id}/info")
@router.patch("/{uid}/races/{race_id}/info")
def update_race_info(uid: str, race_id: str, req: RaceInfoUpdateRequest, request: Request):
    """Updates the race intelligence fields (race_info) for a specific race plan."""
    _verify_profile_access(request, uid)
    updated = LocalStore.update_race_info(uid, race_id, req.race_info)
    if not updated:
        raise HTTPException(status_code=404, detail="赛事未找到")
    return {"message": "赛事情报已更新", "races": LocalStore.get_race_plans(uid)}


class RaceLookupRequest(BaseModel):
    race_name: str
    race_type: Optional[str] = None
    target_time: Optional[str] = None
    race_date: Optional[str] = None
    race_id: Optional[str] = None
    user_id: Optional[str] = None


@router.post("/race-intel-lookup")
def lookup_race_intelligence(req: RaceLookupRequest, request: Request = None):
    """
    Searches for official race intelligence (distance, elevation gain/loss, difficulty, weather, race level, etc.)
    using the multi-group Official Race Catalog and live web search grounded LLM inference.
    Only persists to race_plans explicitly owned by the verified user.
    """
    enforce_rate_limit("race_intel", get_client_ip(request), max_calls=15, window_seconds=3600)
    from utils.race_intel import fetch_race_intelligence
    from utils.local_store import DB_PATH, sqlite3

    token_uid = getattr(getattr(request, "state", None), "user_id", None) if request else None
    token_is_sa = bool(getattr(getattr(request, "state", None), "is_super_admin", False)) if request else False
    eff_uid = req.user_id or token_uid
    if eff_uid and token_uid and not token_is_sa and not LocalStore.is_super_admin(token_uid):
        if LocalStore.resolve_user_id(token_uid) != LocalStore.resolve_user_id(eff_uid):
            raise HTTPException(status_code=403, detail="安全拦截：无权操作他人赛事计划")

    eff_target_time = req.target_time
    eff_race_date = req.race_date
    matched_rows = []

    if eff_uid and req.race_id:
        try:
            canon_uid = LocalStore.resolve_user_id(eff_uid)
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT id, user_id, name, race_type, race_date, target_time FROM race_plans WHERE (user_id = ? OR user_id = ?) AND id = ?",
                    (eff_uid, canon_uid, req.race_id),
                )
                matched_rows = [dict(r) for r in c.fetchall()]
                if matched_rows:
                    first = matched_rows[0]
                    eff_target_time = eff_target_time or first.get("target_time")
                    eff_race_date = eff_race_date or first.get("race_date")
        except Exception as e:
            logger.warning(f"[race-intel-lookup] Pre-query race_plans failed: {e}")

    res = fetch_race_intelligence(
        race_name=req.race_name,
        race_type=req.race_type,
        target_time=eff_target_time,
        race_date=eff_race_date,
        uid=eff_uid,
    )

    if res.get("success") and res.get("race_info") and matched_rows:
        try:
            for r in matched_rows:
                LocalStore.update_race_info(r["user_id"], r["id"], res["race_info"])
        except Exception as e:
            logger.warning(f"[race-intel-lookup] Auto-save race_info failed: {e}")

    return res


@router.post("/{uid}/races/lookup-info")
def lookup_user_race_intelligence(uid: str, req: RaceLookupRequest, request: Request):
    """User-scoped alias for race intelligence auto-search."""
    _verify_profile_access(request, uid)
    req.user_id = uid
    return lookup_race_intelligence(req, request)


# ── Race Completion & Photo Endpoints ──

class RaceCompleteRequest(BaseModel):
    status: Optional[str] = "completed"  # "completed" | "upcoming"
    finish_time: Optional[str] = None
    finish_notes: Optional[str] = None
    photo_url: Optional[str] = None
    was_official_pacer: Optional[bool] = None
    pacer_target_time: Optional[str] = None


@router.post("/{uid}/races/{race_id}/complete")
@router.put("/{uid}/races/{race_id}/complete")
@router.patch("/{uid}/races/{race_id}/complete")
def complete_user_race(uid: str, race_id: str, req: RaceCompleteRequest, request: Request):
    """
    Marks a race as completed (or reverts to upcoming), recording actual finish time,
    personal notes/reflection, official pacer badge, and optional finisher photo URL.
    """
    _verify_profile_access(request, uid)
    success = LocalStore.update_race_completion(
        uid=uid,
        race_id=race_id,
        status=req.status or "completed",
        finish_time=req.finish_time,
        finish_notes=req.finish_notes,
        photo_url=req.photo_url,
        was_official_pacer=req.was_official_pacer,
        pacer_target_time=req.pacer_target_time,
    )
    if not success:
        raise HTTPException(status_code=404, detail="未找到对应的比赛记录")
    
    return {
        "message": "赛事完赛记录已更新 🎉" if req.status == "completed" else "赛事状态已恢复为备战中",
        "races": LocalStore.get_race_plans(uid)
    }


@router.get("/{uid}/races/{race_id}/matched-activity")
def get_matched_activity_for_race(uid: str, race_id: str, request: Request, race_date: Optional[str] = None):
    """
    Searches runner's synced Garmin/COROS activities on the race date (±1 day)
    to auto-suggest actual finish time, elapsed duration, distance, and pace.
    """
    _verify_profile_access(request, uid)
    date_to_query = race_date
    if not date_to_query:
        races = LocalStore.get_race_plans(uid)
        matched_race = next((r for r in races if r.get("id") == race_id or r.get("name") == race_id), None)
        if matched_race and matched_race.get("race_date"):
            date_to_query = str(matched_race["race_date"])[:10]

    if not date_to_query:
        return {"matched": False, "activity": None, "message": "无法确定比赛日期"}

    act = LocalStore.find_matched_activity_for_race(uid, date_to_query)
    if act:
        return {
            "matched": True,
            "activity": act,
            "message": f"找到匹配的运动记录: {act.get('name')} ({act.get('distance_km')}km, 用时 {act.get('formatted_time')})"
        }
    return {"matched": False, "activity": None, "message": "未在比赛日找到匹配的手表运动记录"}


class RacePhotoBase64Request(BaseModel):
    image_base64: str
    ext: Optional[str] = ".jpg"


@router.post("/{uid}/races/{race_id}/photo-base64")
async def upload_race_photo_base64(uid: str, race_id: str, req: RacePhotoBase64Request, request: Request):
    """
    Uploads a finisher certificate or race photo via Base64.
    Works seamlessly with WeChat request合法域名 without needing uploadFile domain.
    """
    _verify_profile_access(request, uid)
    import base64
    raw_ext = (req.ext or ".jpg").lower()
    if not raw_ext.startswith("."):
        raw_ext = f".{raw_ext}"

    raw_b64 = (req.image_base64 or "").strip()
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    if len(raw_b64) > (MAX_IMAGE_UPLOAD_BYTES * 4 // 3) + 4096:
        raise HTTPException(status_code=413, detail="照片体积超过 10MB 上限")
    try:
        img_bytes = base64.b64decode(raw_b64)
    except Exception as e:
        logger.error(f"[profile] Failed to decode base64 race photo for {uid}/{race_id}: {e}")
        raise HTTPException(status_code=400, detail="照片 Base64 编码格式无效")

    ext = validate_uploaded_image_bytes(img_bytes, f"race{raw_ext}")

    photos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "race_photos")
    os.makedirs(photos_dir, exist_ok=True)

    safe_uid = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in uid)
    safe_race_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in race_id)
    filename = f"race_{safe_uid}_{safe_race_id}_{int(time.time())}{ext}"
    filepath = os.path.join(photos_dir, filename)

    try:
        with open(filepath, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        logger.error(f"[profile] Failed to save base64 race photo for {uid}/{race_id}: {e}")
        raise HTTPException(status_code=500, detail="保存赛事照片失败")

    photo_url = f"https://rgm.vanpower.net/api/race-photos/{filename}"
    photos = LocalStore.add_race_photo(uid, race_id, photo_url)

    return {
        "photo_url": photo_url,
        "photos": photos,
        "message": "完赛照片上传成功 📸",
        "races": LocalStore.get_race_plans(uid)
    }


@router.post("/{uid}/races/{race_id}/photo")
async def upload_race_photo(uid: str, race_id: str, request: Request, file: UploadFile = File(...)):
    """
    Uploads a finisher photo or race certificate file via multipart/form-data.
    """
    _verify_profile_access(request, uid)
    orig_name = file.filename or "race.jpg"
    contents = await file.read(MAX_IMAGE_UPLOAD_BYTES + 1)
    ext = validate_uploaded_image_bytes(contents, orig_name)

    photos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "race_photos")
    os.makedirs(photos_dir, exist_ok=True)

    safe_uid = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in uid)
    safe_race_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in race_id)
    filename = f"race_{safe_uid}_{safe_race_id}_{int(time.time())}{ext}"
    filepath = os.path.join(photos_dir, filename)

    try:
        with open(filepath, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"[profile] Failed to save race photo for {uid}/{race_id}: {e}")
        raise HTTPException(status_code=500, detail="保存赛事照片失败")

    photo_url = f"https://rgm.vanpower.net/api/race-photos/{filename}"
    photos = LocalStore.add_race_photo(uid, race_id, photo_url)

    return {
        "photo_url": photo_url,
        "photos": photos,
        "message": "完赛照片上传成功 📸",
        "races": LocalStore.get_race_plans(uid)
    }


class RacePhotoDeleteRequest(BaseModel):
    photo_url: str


@router.delete("/{uid}/races/{race_id}/photo")
def delete_race_photo(uid: str, race_id: str, req: RacePhotoDeleteRequest, request: Request):
    """Deletes a photo from the race record."""
    _verify_profile_access(request, uid)
    photos = LocalStore.delete_race_photo(uid, race_id, req.photo_url)
    return {
        "message": "照片已删除",
        "photos": photos,
        "races": LocalStore.get_race_plans(uid)
    }


class OnboardingActionRequest(BaseModel):
    action: str # "skip_club_solo", "skip_device", "skip_history", "complete_onboarding"
    payload: Optional[Dict[str, Any]] = None


@router.get("/{uid}/onboarding-status")
def get_onboarding_status_endpoint(uid: str, request: Request):
    """Returns user step-by-step setup and onboarding completion status."""
    _verify_profile_access(request, uid)
    return LocalStore.get_user_onboarding_status(uid)


@router.post("/{uid}/onboarding-action")
def update_onboarding_action_endpoint(uid: str, req: OnboardingActionRequest, request: Request):
    """Updates user onboarding state or marks steps skipped / completed."""
    _verify_profile_access(request, uid)
    return LocalStore.update_onboarding_action(uid, req.action, req.payload)


