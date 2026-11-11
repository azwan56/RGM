import json
import hashlib
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, UploadFile, File, Form
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
    has_apple_watch = bool(user and user.get("apple_watch_connected"))
    has_huawei = bool(user and user.get("huawei_connected"))
    has_suunto = bool(user and user.get("suunto_connected"))

    # NOTE: never fall back to another user's device credentials (privacy).

    if not user or (not has_garmin and not has_coros):
        if has_apple_watch or has_huawei or has_suunto:
            sync_time_iso = datetime.utcnow().isoformat() + "Z"
            recent_acts = LocalStore.get_recent_activities(uid, limit=100)
            latest_h = LocalStore.get_latest_health(uid)
            if has_suunto:
                brand_label = "颂拓 Suunto"
                w_mode = "suunto"
            elif has_huawei:
                brand_label = "华为手表"
                w_mode = "huawei"
            else:
                brand_label = "Apple Watch"
                w_mode = "apple_watch"
            if len(recent_acts) == 0:
                return {
                    "success": False,
                    "synced_activities": 0,
                    "synced_health": bool(latest_h),
                    "watch_mode": w_mode,
                    "last_sync_at": sync_time_iso,
                    "error": (
                        f"尚未导入 {brand_label} 跑步记录。\n\n"
                        f"因微信小程序无法在后台自动拉取 iPhone 本地「苹果健康 / 健身」数据，"
                        f"请前往底部【我的 → 手表连接与同步 → {brand_label}】，点击：\n"
                        f"•「📸 选运动截图一键导入」（支持苹果健康多日列表一次批量导入）\n"
                        f"• 或「📂 微信导入 GPX/TCX 轨迹」"
                    ),
                }
            return {
                "success": True,
                "synced_activities": len(recent_acts),
                "synced_health": bool(latest_h),
                "watch_mode": w_mode,
                "last_sync_at": sync_time_iso,
                "message": f"已刷新 {brand_label} 云端跑步数据（共 {len(recent_acts)} 条记录）。如需导入新记录，请点击「📸 选运动截图一键导入」或导入轨迹文件。"
            }
        return {
            "success": False, 
            "error": "尚未绑定运动手表。请先前往【我的】页面连接佳明、高驰、Apple Watch、华为或颂拓手表。"
        }

    try:
        all_activities: List[Dict[str, Any]] = []
        synced_health = False
        sync_time_iso = datetime.utcnow().isoformat() + "Z"
        profile_updates: Dict[str, Any] = {}
        garmin_adapter: Optional[GarminAdapter] = None
        coros_adapter: Optional[CorosAdapter] = None
        sync_errors: List[str] = []

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
                        if g_info.get("display_name") and not user.get("display_name"):
                            profile_updates["display_name"] = g_info["display_name"]
                        if g_info.get("weight_kg") and not user.get("weight_kg") and not user.get("weight"):
                            profile_updates["weight_kg"] = g_info["weight_kg"]
                        if g_info.get("height_cm") and not user.get("height_cm") and not user.get("height"):
                            profile_updates["height_cm"] = g_info["height_cm"]
                        if g_info.get("date_of_birth") and not user.get("date_of_birth"):
                            profile_updates["date_of_birth"] = g_info["date_of_birth"]
                        if g_info.get("gender") and not user.get("gender"):
                            profile_updates["gender"] = g_info["gender"]
                        if g_info.get("vo2max"):
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
                    if garmin_adapter.last_error:
                        sync_errors.append(garmin_adapter.last_error)

                    for i in range(7):
                        d = (date.today() - timedelta(days=i)).isoformat()
                        try:
                            h_metrics = garmin_adapter.fetch_daily_health_metrics(d)
                            if h_metrics:
                                if i == 0 and h_metrics.get("vo2_max") is None and profile_updates.get("vo2max"):
                                    h_metrics["vo2_max"] = profile_updates["vo2max"]
                                if any(h_metrics.get(k) is not None for k in [
                                    "resting_heart_rate", "sleep_score", "hrv_last_night_avg", "body_battery_max",
                                    "vo2_max", "steps", "active_calories", "nap_duration_seconds", "stress_avg", "hr_max"
                                ]):
                                    LocalStore.upsert_daily_health(uid, h_metrics)
                                    synced_health = True
                        except Exception as he:
                            logger.warning(f"[sync] Garmin health fetch error on {d} for {uid}: {he}")

                    profile_updates["garmin_last_sync_at"] = sync_time_iso
            except Exception as ge:
                logger.error(f"[sync] Garmin sync error for {uid}: {ge}")
                err_msg = str(ge)
                if "429" in err_msg or "rate limit" in err_msg.lower():
                    sync_errors.append("Garmin 官方接口访问频次超限(429)，请稍后重试")
                else:
                    sync_errors.append(f"Garmin 同步异常: {err_msg}")

        # 2. Sync COROS if connected
        if has_coros:
            try:
                account = user.get("coros_account")
                enc_pwd = user.get("coros_encrypted_password")
                domain = user.get("coros_domain") or "teamcnapi.coros.com"
                pwd = decrypt_string(enc_pwd)
                if not pwd:
                    sync_errors.append("高驰密码解密失败，请重新绑定高驰账号")
                else:
                    coros_adapter = CorosAdapter(account=account, password=pwd, domain=domain)
                    # Verify authentication upfront (proactively refreshes token or re-logs in without triggering 2FA SMS)
                    if not coros_adapter.login(trigger_2fa_sms=False):
                        err_msg = coros_adapter.last_error or "高驰授权凭证失效，请重新绑定"
                        logger.warning(f"[sync] COROS login failed for {uid}: {err_msg}")
                        sync_errors.append(err_msg if err_msg.startswith("高驰登录失败") else f"高驰登录失败: {err_msg}")
                    else:
                        try:
                            c_info = coros_adapter.fetch_user_profile_info()
                            if c_info.get("avatar_url") and not profile_updates.get("avatar_url"):
                                profile_updates["avatar_url"] = c_info["avatar_url"]
                            if c_info.get("display_name") and not user.get("display_name"):
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

                        for i in range(30):
                            d = (date.today() - timedelta(days=i)).isoformat()
                            try:
                                h_metrics = coros_adapter.fetch_daily_health_metrics(d)
                                if h_metrics and any(h_metrics.get(k) is not None for k in [
                                    "resting_heart_rate", "sleep_score", "sleep_duration_seconds",
                                    "body_battery_max", "vo2_max", "hrv_last_night_avg",
                                    "steps", "active_calories", "nap_duration_seconds", "stress_avg", "hr_max"
                                ]):
                                    LocalStore.upsert_daily_health(uid, h_metrics)
                                    synced_health = True
                            except Exception as he:
                                logger.warning(f"[sync] COROS health fetch error on {d} for {uid}: {he}")

                        if not c_acts and not synced_health and coros_adapter.last_error:
                            err_msg = coros_adapter.last_error
                            sync_errors.append(err_msg if err_msg.startswith("高驰登录失败") else f"高驰登录失败: {err_msg}")
                        else:
                            profile_updates["coros_last_sync_at"] = sync_time_iso
            except Exception as ce:
                logger.error(f"[sync] COROS sync error for {uid}: {ce}")
                sync_errors.append(f"COROS 同步异常: {str(ce)}")

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

        # Sort activities newest first so prefetch targets the true latest runs
        all_activities.sort(key=lambda x: str(x.get("start_time") or ""), reverse=True)

        # Check existing DB cache to avoid redundant detail API calls on already-cached activities
        existing_cache: Dict[str, Tuple[bool, bool]] = {}
        act_ids_all = [str(a.get("id") or "") for a in all_activities if a.get("id")]
        if act_ids_all:
            try:
                import sqlite3
                from utils.local_store import DB_PATH
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.cursor()
                    for chunk_start in range(0, len(act_ids_all), 200):
                        chunk = act_ids_all[chunk_start:chunk_start + 200]
                        ph = ",".join(["?"] * len(chunk))
                        cur.execute(
                            f"SELECT id, gps_track_data, segment_analysis_json FROM activities WHERE id IN ({ph})",
                            chunk,
                        )
                        for r_id, r_gps, r_seg in cur.fetchall():
                            existing_cache[str(r_id)] = (bool(r_gps), bool(r_seg))
            except Exception as ce_db:
                logger.debug(f"[sync] Existing cache lookup skipped: {ce_db}")

        # Auto-prefetch detailed telemetry/laps/GPS track:
        # - Latest 2 running activities (Garmin or COROS) missing segment_analysis or gps_track_data (Rule #1)
        # - Up to 5 latest outdoor activities missing gps_track_data
        run_prefetch_count = 0
        track_prefetch_count = 0
        segment_target_ids = set()

        for act in all_activities[:12]:
            act_id = str(act.get("id") or "")
            if not act_id:
                continue
            is_run = LocalStore.is_running_activity(act.get("sport_type"))
            is_outdoor = act.get("sport_type") in ["Run", "TrailRun", "Ride", "Hike", "Walk"]
            has_cached_gps, has_cached_seg = existing_cache.get(act_id, (False, False))

            need_run_detail = is_run and run_prefetch_count < 2 and (not has_cached_gps or not has_cached_seg)
            need_map_track = is_outdoor and track_prefetch_count < 5 and not has_cached_gps

            if is_run and run_prefetch_count < 2:
                run_prefetch_count += 1
                segment_target_ids.add(act_id)

            if not (need_run_detail or need_map_track):
                continue

            if act_id.startswith("garmin_") and garmin_adapter:
                try:
                    track_data = garmin_adapter.fetch_activity_gps_track(act_id)
                    if track_data:
                        act["gps_track_data"] = track_data
                        if track_data.get("laps") and not act.get("laps_data"):
                            act["laps_data"] = track_data["laps"]
                        if track_data.get("laps") and not act.get("splits_data"):
                            act["splits_data"] = track_data["laps"]
                        track_prefetch_count += 1
                except Exception as te:
                    logger.warning(f"[sync] Garmin detail/track prefetch failed for {act_id}: {te}")
            elif act_id.startswith("coros_") and coros_adapter:
                try:
                    track_data = coros_adapter.fetch_activity_gps_track(
                        act_id, sport_type_hint=act.get("coros_sport_type")
                    )
                    if track_data:
                        act["gps_track_data"] = track_data
                        if track_data.get("laps") and not act.get("laps_data"):
                            act["laps_data"] = track_data["laps"]
                        if track_data.get("km_splits") and not act.get("splits_data"):
                            act["splits_data"] = track_data["km_splits"]
                        track_prefetch_count += 1
                except Exception as cte:
                    logger.warning(f"[sync] COROS detail/track prefetch failed for {act_id}: {cte}")

        for act in all_activities:
            # Calculate TRIMP
            moving_mins = (act.get("moving_time_seconds") or 0) / 60.0

            avg_hr = act.get("average_heartrate")
            if avg_hr and avg_hr > rest_hr:
                act["trimp"] = calculate_trimp(moving_mins, avg_hr, rest_hr, max_hr, gender)
            else:
                act["trimp"] = round(moving_mins * 0.8, 1)

            act["user_id"] = uid
            act_id = str(act.get("id") or "")
            was_new = act_id not in existing_cache
            will_segment = act_id in segment_target_ids or bool(
                was_new and LocalStore.is_running_activity(act.get("sport_type")) and act.get("gps_track_data")
            )

            # Defer push notification until segmented critique is ready if we are running segment analysis
            LocalStore.upsert_activity(act, notify=(not will_segment), reconcile_plan=False)
            if will_segment:
                try:
                    seg_res = LocalStore.compute_and_cache_segment_analysis(act_id)
                    if seg_res and seg_res.get("updated_ai_journal"):
                        act["ai_journal"] = seg_res["updated_ai_journal"]
                except Exception as se_err:
                    logger.warning(f"[sync] Segment analysis failed for {act_id}: {se_err}")
                if was_new and act.get("ai_journal"):
                    try:
                        from utils.wechat import dispatch_canova_critique_push
                        dispatch_canova_critique_push(
                            user_id=uid,
                            activity=act,
                            critique=act["ai_journal"],
                        )
                    except Exception as pe:
                        logger.warning(f"[sync] Canova segmented critique push failed: {pe}")
            saved_count += 1

        if saved_count > 0:
            try:
                active_plan = LocalStore.get_user_active_training_plan(uid, reconcile=False)
                if active_plan:
                    LocalStore.reconcile_training_plan_activities(active_plan, uid)
            except Exception as rec_e:
                logger.warning(f"[sync] Batch plan reconciliation skipped for {uid}: {rec_e}")

        if saved_count == 0 and not synced_health and sync_errors:
            needs_rebind = bool(coros_adapter and (coros_adapter.needs_2fa or coros_adapter._login_failed))
            return {
                "success": False,
                "needs_rebind": needs_rebind,
                "error": "；".join(sync_errors)
            }

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


# ── Apple HealthKit import (iOS) ──────────────────────────────────────────────

class HKRoutePoint(BaseModel):
    lat: float
    lon: float
    alt: Optional[float] = None
    hr: Optional[int] = None
    t: Optional[float] = None
    cad: Optional[float] = None


class HKWorkout(BaseModel):
    uuid: str
    start_time: str                     # ISO8601 with timezone
    duration_seconds: int
    distance_meters: float = 0.0
    average_heartrate: Optional[int] = None
    max_heartrate: Optional[int] = None
    elevation_gain_meters: Optional[float] = None
    calories: Optional[int] = None
    average_cadence: Optional[float] = None
    source_name: Optional[str] = None
    device_name: Optional[str] = None
    bundle_id: Optional[str] = None
    is_indoor: Optional[bool] = None
    route: Optional[List[HKRoutePoint]] = None


class HKDailyHealth(BaseModel):
    date: str                           # YYYY-MM-DD
    resting_heart_rate: Optional[int] = None
    hrv_ms: Optional[float] = None
    sleep_duration_seconds: Optional[int] = None
    vo2_max: Optional[float] = None
    steps: Optional[int] = None
    active_calories: Optional[int] = None
    nap_duration_seconds: Optional[int] = None
    stress_avg: Optional[int] = None
    stress_max: Optional[int] = None
    hr_min: Optional[int] = None
    hr_max: Optional[int] = None


class HealthKitImportRequest(BaseModel):
    uid: str
    watch_brand: Optional[str] = None   # "apple_watch" | "huawei" | None
    workouts: List[HKWorkout] = []
    daily_health: List[HKDailyHealth] = []


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    import math
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _build_hk_track(activity_id: str, route: List[HKRoutePoint]) -> Optional[Dict[str, Any]]:
    """Builds the same track payload shape as Garmin tracks (GCJ-02 points + elevation profile + telemetry_series)."""
    from utils.geo_utils import wgs84_to_gcj02, downsample_points
    if not route or len(route) < 2:
        return None
    gcj_points: List[Dict[str, Any]] = []
    profile: List[Dict[str, Any]] = []
    telemetry_raw: List[Dict[str, Any]] = []
    cum = 0.0
    prev = None
    t0 = next((p.t for p in route if p.t is not None), None)
    for p in route:
        step_m = 0.0
        dt_s = None
        if prev is not None:
            step_m = _haversine_m(prev.lat, prev.lon, p.lat, p.lon)
            cum += step_m
            if p.t is not None and prev.t is not None and p.t > prev.t:
                dt_s = p.t - prev.t
        prev = p
        g_lat, g_lng = wgs84_to_gcj02(p.lat, p.lon)
        gcj_points.append({"latitude": round(g_lat, 6), "longitude": round(g_lng, 6)})
        dist_km_val = round(cum / 1000.0, 3)
        if p.alt is not None:
            profile.append({"dist_km": round(cum / 1000.0, 2), "elevation_m": round(p.alt, 1), "hr": p.hr})
        if t0 is not None and p.t is not None:
            el_s = round(max(0.0, p.t - t0), 1)
            inst_pace = None
            if dt_s and dt_s > 0.2 and step_m > 0.5:
                spd = step_m / dt_s
                if 0.8 <= spd <= 8.0:
                    inst_pace = int(round(1000.0 / spd))
            telemetry_raw.append({
                "dist_km": dist_km_val,
                "elapsed_s": el_s,
                "pace_sec": inst_pace,
                "hr": p.hr,
                "cadence": int(round(p.cad)) if p.cad else None,
                "elevation_m": round(p.alt, 1) if p.alt is not None else None,
            })
    pts = downsample_points(gcj_points, max_points=250)
    min_lat = min(x["latitude"] for x in pts); max_lat = max(x["latitude"] for x in pts)
    min_lng = min(x["longitude"] for x in pts); max_lng = max(x["longitude"] for x in pts)
    return {
        "activity_id": activity_id,
        "total_points": len(pts),
        "original_point_count": len(route),
        "center": {"latitude": round((min_lat + max_lat) / 2, 6), "longitude": round((min_lng + max_lng) / 2, 6)},
        "bounds": {
            "min_lat": min_lat, "max_lat": max_lat, "min_lng": min_lng, "max_lng": max_lng,
            "southwest": {"latitude": min_lat, "longitude": min_lng},
            "northeast": {"latitude": max_lat, "longitude": max_lng},
        },
        "start_point": pts[0],
        "end_point": pts[-1],
        "points": pts,
        "elevation_profile": downsample_points(profile, max_points=120) if profile else [],
        "telemetry_series": downsample_points(telemetry_raw, max_points=600) if telemetry_raw else [],
    }


def _to_beijing_iso(ts: str) -> str:
    from datetime import timezone
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        bj = dt.astimezone(timezone(timedelta(hours=8)))
        return bj.replace(microsecond=0).isoformat()
    except Exception:
        return ts


def _detect_hk_watch_source(w: HKWorkout, fallback_brand: Optional[str] = None) -> str:
    """Returns 'apple_watch', 'huawei', 'garmin', 'coros', or '' based on workout metadata."""
    combined = f"{w.source_name or ''} {w.device_name or ''} {w.bundle_id or ''}".lower()
    if any(k in combined for k in ("huawei", "华为", "hihonor", "荣耀")):
        return "huawei"
    if "garmin" in combined or "connect" in combined:
        return "garmin"
    if "coros" in combined or "高驰" in combined:
        return "coros"
    if any(k in combined for k in ("watch", "apple", "体能训练", "workout", "com.apple.health")):
        return "apple_watch"
    return fallback_brand or ""


@router.post("/healthkit")
def import_healthkit(req: HealthKitImportRequest, request: Request):
    """
    Imports Apple HealthKit running workouts (with GPS route / heart rate / cadence) and daily
    health metrics uploaded by the iOS app. Supports native Apple Watch workouts as well as
    Huawei Watch workouts bridged via iOS HealthKit.
    Enforces single-watch exclusivity and skips any workout already present from Garmin/COROS.
    """
    import sqlite3
    from utils.local_store import DB_PATH

    token_uid = getattr(request.state, "user_id", None)
    if not token_uid:
        raise HTTPException(status_code=401, detail="请先登录")
    if token_uid != req.uid:
        raise HTTPException(status_code=403, detail="无权为其他账号导入数据")

    uid = req.uid
    profile = LocalStore.get_profile(uid) or {}

    # Single-watch exclusivity guard: if user already bound another watch brand, reject HealthKit workout import
    if profile.get("garmin_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【佳明 Garmin】，每个账号仅限连接一个运动手表。如需切换手表，请先解绑佳明账号。"
        )
    if profile.get("coros_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【高驰 COROS】，每个账号仅限连接一个运动手表。如需切换手表，请先解绑高驰账号。"
        )
    if req.watch_brand == "apple_watch" and profile.get("huawei_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【华为手表】，每个账号仅限连接一个运动手表。如需切换为 Apple Watch，请先解绑华为手表。"
        )
    elif req.watch_brand == "huawei" and profile.get("apple_watch_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【Apple Watch】，每个账号仅限连接一个运动手表。如需切换为华为手表，请先解绑 Apple Watch。"
        )

    max_hr = float(profile.get("max_heart_rate") or 190)
    rest_hr = float(profile.get("resting_heart_rate") or 56)
    gender = str(profile.get("gender") or "male")

    # Preload existing non-HealthKit activities to prevent duplicate imports across channels
    existing_non_hk_times: List[datetime] = []
    existing_by_date_hk: Dict[str, List[Dict[str, Any]]] = {}
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT id, start_time, distance_meters, average_heartrate, avg_pace_str, gps_track_data FROM activities WHERE user_id = ?",
                (uid,)
            )
            for row in cur.fetchall():
                r_dict = dict(row)
                r_id = str(r_dict.get("id") or "")
                st_str = str(r_dict.get("start_time") or "")
                if st_str:
                    existing_by_date_hk.setdefault(st_str[:10], []).append(r_dict)
                    if not r_id.startswith("hk_") and "_img_" not in r_id:
                        try:
                            existing_non_hk_times.append(datetime.fromisoformat(st_str.replace("Z", "+00:00")))
                        except Exception:
                            pass
    except Exception:
        pass

    imported = 0
    skipped_duplicates = 0
    with_gps = 0
    saw_apple_watch = (req.watch_brand == "apple_watch")
    saw_huawei = (req.watch_brand == "huawei")

    for w in req.workouts[:500]:
        if w.duration_seconds <= 0:
            continue

        src = _detect_hk_watch_source(w, req.watch_brand)
        # Never import workouts that Garmin Connect or COROS wrote into Apple Health
        if src in ("garmin", "coros"):
            skipped_duplicates += 1
            continue

        bj_start_str = _to_beijing_iso(w.start_time)
        bj_date_key = bj_start_str[:10]
        w_dist_m = float(w.distance_meters or 0.0)
        tol_m = max(200.0, w_dist_m * 0.03)

        # Skip if an activity within ±15 minutes already exists from another watch source
        try:
            w_dt = datetime.fromisoformat(bj_start_str.replace("Z", "+00:00"))
            if any(abs((w_dt - ex_dt).total_seconds()) <= 900 for ex_dt in existing_non_hk_times):
                skipped_duplicates += 1
                continue
        except Exception:
            pass

        # Check same-day records for distance match or coarse screenshot summary replacement
        same_day_ex = existing_by_date_hk.get(bj_date_key, [])
        skip_hk_item = False
        stale_img_ids: List[str] = []
        for ex in same_day_ex:
            ex_id = str(ex.get("id") or "")
            ex_m = float(ex.get("distance_meters") or 0.0)
            if not ex_id.startswith("hk_") and "_img_" not in ex_id and abs(ex_m - w_dist_m) <= tol_m:
                skip_hk_item = True
                break
            if "_img_" in ex_id and (abs(ex_m - w_dist_m) <= tol_m or _is_daily_summary_activity(ex)):
                stale_img_ids.append(ex_id)
        if skip_hk_item:
            skipped_duplicates += 1
            continue
        if stale_img_ids:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    for old_id in stale_img_ids:
                        conn.execute("DELETE FROM activities WHERE id = ? AND user_id = ?", (old_id, uid))
                    conn.commit()
                existing_by_date_hk[bj_date_key] = [ex for ex in same_day_ex if str(ex.get("id")) not in stale_img_ids]
            except Exception:
                pass

        act_id = f"hk_{w.uuid}"
        km = (w.distance_meters or 0) / 1000.0
        pace = "—"
        if km > 0.05:
            sec = int(round(w.duration_seconds / km))
            pace = f"{sec // 60}:{sec % 60:02d} /km"
        trimp = None
        if w.average_heartrate:
            trimp = calculate_trimp(w.duration_seconds / 60.0, float(w.average_heartrate), rest_hr, max_hr, gender)
        track = _build_hk_track(act_id, w.route or [])
        if track:
            with_gps += 1
        elev = w.elevation_gain_meters
        if elev is None and w.route:
            alts = [p.alt for p in w.route if p.alt is not None]
            elev = round(sum(max(0.0, b - a) for a, b in zip(alts, alts[1:])), 1) if len(alts) > 1 else None

        base_run_name = "室内跑步" if w.is_indoor else "户外跑步"
        if src == "apple_watch":
            saw_apple_watch = True
            run_name = f"Apple Watch {base_run_name}"
        elif src == "huawei":
            saw_huawei = True
            run_name = f"华为手表 {base_run_name}"
        else:
            run_name = base_run_name

        act = {
            "id": act_id,
            "user_id": uid,
            "name": run_name,
            "sport_type": "treadmill_running" if w.is_indoor else "Run",
            "start_time": bj_start_str,
            "distance_meters": round(w.distance_meters or 0, 1),
            "moving_time_seconds": w.duration_seconds,
            "elapsed_time_seconds": w.duration_seconds,
            "elevation_gain_meters": elev,
            "average_heartrate": w.average_heartrate,
            "max_heartrate": w.max_heartrate,
            "average_cadence": w.average_cadence,
            "avg_pace_str": pace,
            "calories": w.calories,
            "trimp": trimp,
        }
        if track:
            act["gps_track_data"] = track
        try:
            is_recent = False
            try:
                st = datetime.fromisoformat(act["start_time"].replace("Z", "+00:00"))
                is_recent = (datetime.now(st.tzinfo) - st) < timedelta(hours=24)
            except Exception:
                pass
            LocalStore.upsert_activity(act, notify=is_recent, reconcile_plan=False)
            imported += 1
        except Exception as e:
            logger.warning(f"[healthkit] upsert failed for {act_id}: {e}")

    if imported > 0:
        try:
            active_plan = LocalStore.get_user_active_training_plan(uid, reconcile=False)
            if active_plan:
                LocalStore.reconcile_training_plan_activities(active_plan, uid)
        except Exception as rec_e:
            logger.warning(f"[healthkit] Batch plan reconciliation skipped for {uid}: {rec_e}")

    health_days = 0
    latest_rhr = None
    latest_vo2 = None
    for h in sorted(req.daily_health, key=lambda x: x.date)[-60:]:
        metrics = {
            "date": h.date,
            "resting_heart_rate": h.resting_heart_rate,
            "vo2_max": h.vo2_max,
            "sleep_duration_seconds": h.sleep_duration_seconds,
            "sleep_duration_hours": round(h.sleep_duration_seconds / 3600.0, 2) if h.sleep_duration_seconds else None,
            "hrv_last_night_avg": h.hrv_ms,
            "steps": h.steps,
            "active_calories": h.active_calories,
            "nap_duration_seconds": h.nap_duration_seconds,
            "stress_avg": h.stress_avg,
            "stress_max": h.stress_max,
            "hr_min": h.hr_min,
            "hr_max": h.hr_max,
            "allow_non_hrv_sleep": True,
        }
        if all(v is None for k, v in metrics.items() if k not in ("date", "allow_non_hrv_sleep")):
            continue
        LocalStore.upsert_daily_health(uid, metrics)
        health_days += 1
        if h.resting_heart_rate:
            latest_rhr = h.resting_heart_rate
        if h.vo2_max:
            latest_vo2 = h.vo2_max

    now_iso = datetime.utcnow().isoformat() + "Z"
    profile_updates: Dict[str, Any] = {}
    if latest_rhr:
        profile_updates["resting_heart_rate"] = latest_rhr
    if latest_vo2:
        profile_updates["vo2max"] = latest_vo2
    if saw_huawei:
        profile_updates["huawei_connected"] = 1
        profile_updates["huawei_last_sync_at"] = now_iso
        if not profile.get("huawei_account"):
            profile_updates["huawei_account"] = "华为运动健康 App"
    elif saw_apple_watch:
        profile_updates["apple_watch_connected"] = 1
        profile_updates["apple_watch_last_sync_at"] = now_iso
    if profile_updates:
        LocalStore.upsert_profile(uid, profile_updates)

    return {
        "success": True,
        "imported_workouts": imported,
        "skipped_duplicates": skipped_duplicates,
        "workouts_with_gps": with_gps,
        "health_days": health_days,
        "message": f"已导入 {imported} 条跑步记录（{with_gps} 条含 GPS 轨迹），{health_days} 天健康数据",
    }


class TrackFileImportRequest(BaseModel):
    uid: str
    filename: str
    content_base64: str
    source_brand: Optional[str] = "huawei"


def _parse_fit_bytes(raw: bytes) -> Dict[str, Any]:
    """
    Pure-Python binary .FIT workout file parser (supports Suunto App, Garmin, COROS FIT exports).
    Extracts session summary (distance, duration, HR, cadence, ascent, calories) and GPS track points.
    """
    import struct
    from datetime import timezone

    if len(raw) < 14 or raw[8:12] != b".FIT":
        raise ValueError("不是有效的 FIT 二进制文件")

    header_size = raw[0]
    data_size = struct.unpack("<I", raw[4:8])[0]
    end_pos = min(len(raw), header_size + data_size)
    pos = header_size

    FIT_EPOCH_OFFSET = 631065600  # 1989-12-31 00:00:00 UTC
    SEMICIRCLE_TO_DEG = 180.0 / 2147483648.0

    local_defs: Dict[int, Dict[str, Any]] = {}
    route: List[HKRoutePoint] = []
    timestamps: List[datetime] = []
    hrs: List[int] = []
    cadences: List[float] = []
    total_dist_m = 0.0
    total_dur_s = 0
    calories: Optional[int] = None
    session_ascent: Optional[float] = None
    session_start_dt: Optional[datetime] = None

    def _read_int(buf: bytes, endian: str, base_type: int):
        bt = base_type & 0x1F
        try:
            if bt in (0, 2, 10, 13):  # enum, uint8, uint8z, byte
                v = buf[0]
                return None if v in (0xFF, 0x00 if bt == 10 else -1) else v
            if bt == 1:  # sint8
                v = struct.unpack(endian + "b", buf[:1])[0]
                return None if v == 0x7F else v
            if bt == 3:  # sint16
                v = struct.unpack(endian + "h", buf[:2])[0]
                return None if v == 0x7FFF else v
            if bt in (4, 11):  # uint16, uint16z
                v = struct.unpack(endian + "H", buf[:2])[0]
                return None if v in (0xFFFF, 0 if bt == 11 else -1) else v
            if bt == 5:  # sint32
                v = struct.unpack(endian + "i", buf[:4])[0]
                return None if v == 0x7FFFFFFF else v
            if bt in (6, 12):  # uint32, uint32z
                v = struct.unpack(endian + "I", buf[:4])[0]
                return None if v in (0xFFFFFFFF, 0 if bt == 12 else -1) else v
        except Exception:
            return None
        return None

    while pos < end_pos:
        rec_hdr = raw[pos]
        pos += 1

        # Definition message
        if (rec_hdr & 0x40) != 0 and (rec_hdr & 0x80) == 0:
            local_num = rec_hdr & 0x0F
            has_dev = (rec_hdr & 0x20) != 0
            if pos + 5 > end_pos:
                break
            arch = raw[pos + 1]
            endian = ">" if arch == 1 else "<"
            global_mesg_num = struct.unpack(endian + "H", raw[pos + 2 : pos + 4])[0]
            num_fields = raw[pos + 4]
            pos += 5
            fields = []
            for _ in range(num_fields):
                if pos + 3 > end_pos:
                    break
                f_num, f_size, f_type = raw[pos], raw[pos + 1], raw[pos + 2]
                fields.append((f_num, f_size, f_type))
                pos += 3
            dev_fields = []
            if has_dev and pos < end_pos:
                num_dev = raw[pos]
                pos += 1
                for _ in range(num_dev):
                    if pos + 3 > end_pos:
                        break
                    df_num, df_size, df_idx = raw[pos], raw[pos + 1], raw[pos + 2]
                    dev_fields.append((df_num, df_size, df_idx))
                    pos += 3
            local_defs[local_num] = {
                "endian": endian,
                "global_num": global_mesg_num,
                "fields": fields,
                "dev_fields": dev_fields,
            }
            continue

        # Data message (normal or compressed timestamp)
        if (rec_hdr & 0x80) != 0:
            local_num = (rec_hdr >> 5) & 0x03
        else:
            local_num = rec_hdr & 0x0F

        defn = local_defs.get(local_num)
        if not defn:
            break

        endian = defn["endian"]
        gnum = defn["global_num"]
        vals: Dict[int, Any] = {}
        for f_num, f_size, f_type in defn["fields"]:
            if pos + f_size > end_pos:
                pos = end_pos
                break
            chunk = raw[pos : pos + f_size]
            pos += f_size
            if gnum in (18, 20):
                vals[f_num] = _read_int(chunk, endian, f_type)
        for _, df_size, _ in defn["dev_fields"]:
            pos += df_size

        if gnum == 20:  # record (track point)
            ts_val = vals.get(253)
            if ts_val is not None and ts_val > 100000000:
                timestamps.append(datetime.fromtimestamp(ts_val + FIT_EPOCH_OFFSET, tz=timezone.utc))
            hr_v = vals.get(3)
            hr_clean = int(hr_v) if (hr_v is not None and 35 <= int(hr_v) <= 230) else None
            if hr_clean is not None:
                hrs.append(hr_clean)
            cad_v = vals.get(4)
            if cad_v is not None and 40 <= int(cad_v) <= 125:
                cadences.append(float(cad_v) * 2.0)
            dist_v = vals.get(5)
            if dist_v is not None and dist_v > 0:
                d_m = float(dist_v) / 100.0
                if d_m > total_dist_m:
                    total_dist_m = d_m
            alt_v = vals.get(78) if vals.get(78) is not None else vals.get(2)
            alt_m = round((float(alt_v) / 5.0) - 500.0, 1) if alt_v is not None else None
            lat_sc = vals.get(0)
            lon_sc = vals.get(1)
            if lat_sc is not None and lon_sc is not None:
                lat_deg = lat_sc * SEMICIRCLE_TO_DEG
                lon_deg = lon_sc * SEMICIRCLE_TO_DEG
                if -90.0 <= lat_deg <= 90.0 and -180.0 <= lon_deg <= 180.0:
                    pt_t = float(ts_val + FIT_EPOCH_OFFSET) if (ts_val is not None and ts_val > 100000000) else None
                    pt_cad = (float(cad_v) * 2.0) if (cad_v is not None and 40 <= int(cad_v) <= 125) else None
                    route.append(HKRoutePoint(lat=lat_deg, lon=lon_deg, alt=alt_m, hr=hr_clean, t=pt_t, cad=pt_cad))
        elif gnum == 18:  # session (workout summary)
            st_val = vals.get(2) or vals.get(253)
            if st_val is not None and st_val > 100000000:
                session_start_dt = datetime.fromtimestamp(st_val + FIT_EPOCH_OFFSET, tz=timezone.utc)
            dur_val = vals.get(8) or vals.get(7)
            if dur_val is not None and dur_val > 0:
                total_dur_s = int(round(float(dur_val) / 1000.0))
            dist_val = vals.get(9)
            if dist_val is not None and dist_val > 0:
                total_dist_m = max(total_dist_m, float(dist_val) / 100.0)
            cal_val = vals.get(11)
            if cal_val is not None and cal_val > 0:
                calories = int(cal_val)
            asc_val = vals.get(22)
            if asc_val is not None and asc_val >= 0:
                session_ascent = float(asc_val)

    if len(route) >= 2 and total_dist_m <= 0:
        for a, b in zip(route, route[1:]):
            total_dist_m += _haversine_m(a.lat, a.lon, b.lat, b.lon)

    _cn_tz = timezone(timedelta(hours=8))
    if session_start_dt:
        start_iso = session_start_dt.astimezone(_cn_tz).isoformat(timespec="seconds")
    elif timestamps:
        timestamps.sort()
        _t0 = timestamps[0]
        start_iso = (_t0.astimezone(_cn_tz) if _t0.tzinfo else _t0).isoformat(timespec="seconds")
    else:
        start_iso = datetime.now(_cn_tz).isoformat(timespec="seconds")

    if total_dur_s <= 0 and len(timestamps) >= 2:
        timestamps.sort()
        total_dur_s = max(1, int((timestamps[-1] - timestamps[0]).total_seconds()))
    if total_dur_s <= 0 and total_dist_m > 0:
        total_dur_s = int(total_dist_m * 0.36)

    alts = [p.alt for p in route if p.alt is not None]
    elev_gain = session_ascent if session_ascent is not None else (
        round(sum(max(0.0, b - a) for a, b in zip(alts, alts[1:])), 1) if len(alts) > 1 else None
    )

    return {
        "start_time": start_iso,
        "duration_seconds": total_dur_s,
        "distance_meters": round(total_dist_m, 1),
        "average_heartrate": int(round(sum(hrs) / len(hrs))) if hrs else None,
        "max_heartrate": max(hrs) if hrs else None,
        "average_cadence": round(sum(cadences) / len(cadences), 1) if cadences else None,
        "elevation_gain_meters": elev_gain,
        "calories": calories,
        "route": route,
    }


def _parse_gpx_or_tcx_bytes(raw: bytes) -> Dict[str, Any]:
    """
    Parses a FIT binary file or GPX / TCX XML file (exported by Suunto App, Huawei Health, Apple Watch, etc.)
    and returns extracted workout summary + route points.
    """
    from utils.security import safe_decompress_gzip, safe_parse_xml_text

    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="运动原始文件过大，最大支持 25MB")

    if raw[:2] == b"\x1f\x8b":
        raw = safe_decompress_gzip(raw)

    # Check if binary FIT file (bytes 8..12 == b'.FIT')
    if len(raw) >= 14 and raw[8:12] == b".FIT":
        return _parse_fit_bytes(raw)

    text = raw.decode("utf-8", errors="ignore").strip()
    root = safe_parse_xml_text(text)

    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag

    root_tag = _strip_ns(root.tag).lower()
    route: List[HKRoutePoint] = []
    timestamps: List[datetime] = []
    hrs: List[int] = []
    cadences: List[float] = []
    total_dist_m = 0.0
    total_dur_s = 0
    calories = None

    if root_tag == "gpx":
        for trkpt in root.iter():
            if _strip_ns(trkpt.tag) != "trkpt":
                continue
            try:
                lat = float(trkpt.attrib["lat"])
                lon = float(trkpt.attrib["lon"])
            except Exception:
                continue
            alt = None
            hr_val = None
            cad_val = None
            for child in trkpt.iter():
                cname = _strip_ns(child.tag).lower()
                if cname == "ele" and child.text:
                    try:
                        alt = float(child.text.strip())
                    except Exception:
                        pass
                elif cname == "time" and child.text:
                    try:
                        ts = datetime.fromisoformat(child.text.strip().replace("Z", "+00:00"))
                        timestamps.append(ts)
                    except Exception:
                        pass
                elif cname in ("hr", "heartrate", "value") and child.text:
                    try:
                        v = int(float(child.text.strip()))
                        if 35 <= v <= 230:
                            hr_val = v
                    except Exception:
                        pass
                elif cname in ("cad", "cadence", "runcadence") and child.text:
                    try:
                        c = float(child.text.strip())
                        # GPX TrackPointExtension cad is often single-foot rpm (e.g. 85 -> 170 spm)
                        if 45 <= c <= 115:
                            c *= 2.0
                        if 100 <= c <= 240:
                            cad_val = c
                    except Exception:
                        pass
            if hr_val is not None:
                hrs.append(hr_val)
            if cad_val is not None:
                cadences.append(cad_val)
            pt_t = timestamps[-1].timestamp() if timestamps else None
            route.append(HKRoutePoint(lat=lat, lon=lon, alt=alt, hr=hr_val, t=pt_t, cad=cad_val))
    elif root_tag == "trainingcenterdatabase":
        # TCX format (commonly exported by Huawei Health App)
        for elem in root.iter():
            ename = _strip_ns(elem.tag)
            if ename == "Lap":
                for sub in elem:
                    sname = _strip_ns(sub.tag)
                    if sname == "TotalTimeSeconds" and sub.text:
                        try:
                            total_dur_s += int(round(float(sub.text.strip())))
                        except Exception:
                            pass
                    elif sname == "DistanceMeters" and sub.text:
                        try:
                            total_dist_m += float(sub.text.strip())
                        except Exception:
                            pass
                    elif sname == "Calories" and sub.text:
                        try:
                            calories = (calories or 0) + int(round(float(sub.text.strip())))
                        except Exception:
                            pass
            elif ename == "Trackpoint":
                lat = None
                lon = None
                alt = None
                hr_val = None
                cad_val = None
                for sub in elem.iter():
                    sname = _strip_ns(sub.tag).lower()
                    if sname == "latitude" or sname == "latitudedegrees":
                        if sub.text:
                            try:
                                lat = float(sub.text.strip())
                            except Exception:
                                pass
                    elif sname == "longitude" or sname == "longitudedegrees":
                        if sub.text:
                            try:
                                lon = float(sub.text.strip())
                            except Exception:
                                pass
                    elif sname == "altitudemeters" and sub.text:
                        try:
                            alt = float(sub.text.strip())
                        except Exception:
                            pass
                    elif sname == "time" and sub.text:
                        try:
                            ts = datetime.fromisoformat(sub.text.strip().replace("Z", "+00:00"))
                            timestamps.append(ts)
                        except Exception:
                            pass
                    elif sname == "heartratebpm":
                        for vnode in sub.iter():
                            if _strip_ns(vnode.tag).lower() == "value" and vnode.text:
                                try:
                                    v = int(float(vnode.text.strip()))
                                    if 35 <= v <= 230:
                                        hr_val = v
                                except Exception:
                                    pass
                    elif sname in ("cadence", "runcadence") and sub.text:
                        try:
                            c = float(sub.text.strip())
                            if 45 <= c <= 115:
                                c *= 2.0
                            if 100 <= c <= 240:
                                cad_val = c
                        except Exception:
                            pass
                if hr_val is not None:
                    hrs.append(hr_val)
                if cad_val is not None:
                    cadences.append(cad_val)
                if lat is not None and lon is not None:
                    pt_t = timestamps[-1].timestamp() if timestamps else None
                    route.append(HKRoutePoint(lat=lat, lon=lon, alt=alt, hr=hr_val, t=pt_t, cad=cad_val))
    else:
        raise ValueError("不支持的文件格式，请导入 GPX 或 TCX 运动轨迹文件")

    if len(route) >= 2 and total_dist_m <= 0:
        for a, b in zip(route, route[1:]):
            total_dist_m += _haversine_m(a.lat, a.lon, b.lat, b.lon)

    _cn_tz = timezone(timedelta(hours=8))
    if timestamps:
        timestamps.sort()
        _t0 = timestamps[0]
        start_iso = (_t0.astimezone(_cn_tz) if _t0.tzinfo else _t0).isoformat(timespec="seconds")
        if total_dur_s <= 0 and len(timestamps) >= 2:
            total_dur_s = max(1, int((timestamps[-1] - timestamps[0]).total_seconds()))
    else:
        start_iso = datetime.now(_cn_tz).isoformat(timespec="seconds")

    if total_dur_s <= 0 and total_dist_m > 0:
        total_dur_s = int(total_dist_m * 0.36)  # ~6:00/km fallback

    alts = [p.alt for p in route if p.alt is not None]
    elev_gain = round(sum(max(0.0, b - a) for a, b in zip(alts, alts[1:])), 1) if len(alts) > 1 else None

    return {
        "start_time": start_iso,
        "duration_seconds": total_dur_s,
        "distance_meters": round(total_dist_m, 1),
        "average_heartrate": int(round(sum(hrs) / len(hrs))) if hrs else None,
        "max_heartrate": max(hrs) if hrs else None,
        "average_cadence": round(sum(cadences) / len(cadences), 1) if cadences else None,
        "elevation_gain_meters": elev_gain,
        "calories": calories,
        "route": route,
    }


@router.post("/import-track-file")
def import_track_file(req: TrackFileImportRequest, request: Request):
    """
    Imports a FIT, GPX or TCX workout file exported from Huawei Health (华为运动健康) or Apple Watch,
    extracting the full GPS route, elevation profile, heart rate, and cadence.
    """
    import base64
    import hashlib
    import sqlite3
    from utils.local_store import DB_PATH

    token_uid = getattr(request.state, "user_id", None)
    if not req.uid or not req.uid.strip():
        raise HTTPException(status_code=401, detail="请先登录")
    if token_uid and token_uid != req.uid:
        raise HTTPException(status_code=403, detail="无权为其他账号导入数据")

    try:
        raw_bytes = base64.b64decode(req.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="轨迹文件编码无法解析")

    try:
        parsed = _parse_gpx_or_tcx_bytes(raw_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析 FIT/GPX/TCX 轨迹文件失败：{str(e)}")

    uid = req.uid
    profile = LocalStore.get_profile(uid) or {}
    raw_brand = (req.source_brand or "huawei").strip().lower()
    if raw_brand == "apple_watch":
        target_brand = "apple_watch"
        other_checks = [("garmin_connected", "佳明 Garmin"), ("coros_connected", "高驰 COROS")]
        brand_prefix = "aw"
        brand_label = "Apple Watch"
    elif raw_brand == "suunto":
        target_brand = "suunto"
        other_checks = [("garmin_connected", "佳明 Garmin"), ("coros_connected", "高驰 COROS")]
        brand_prefix = "st"
        brand_label = "颂拓 Suunto"
    else:
        target_brand = "huawei"
        other_checks = [("garmin_connected", "佳明 Garmin"), ("coros_connected", "高驰 COROS")]
        brand_prefix = "hw"
        brand_label = "华为手表"

    for flag, label in other_checks:
        if profile.get(flag):
            raise HTTPException(
                status_code=400,
                detail=f"当前账号已连接【{label}】。每个账号仅限连接一个运动手表，请先解绑【{label}】后再切换。"
            )

    max_hr = float(profile.get("max_heart_rate") or 190)
    rest_hr = float(profile.get("resting_heart_rate") or 56)
    gender = str(profile.get("gender") or "male")

    bj_start = _to_beijing_iso(parsed["start_time"])
    bj_date = bj_start[:10]
    dur_s = int(parsed["duration_seconds"] or 0)
    dist_m = float(parsed["distance_meters"] or 0.0)
    km = dist_m / 1000.0

    digest = hashlib.md5(f"{uid}:{bj_start}:{parsed['distance_meters']}".encode("utf-8")).hexdigest()[:12]
    act_id = f"{brand_prefix}_{digest}"

    # Check if there is an existing workout on the same day to deduplicate or enrich with GPS track
    already_has_same_track = False
    stale_screenshot_ids_to_delete: List[str] = []
    try:
        target_dt = datetime.fromisoformat(bj_start)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, start_time, distance_meters, average_heartrate, avg_pace_str, gps_track_data FROM activities WHERE user_id = ? AND substr(start_time, 1, 10) = ?",
                (uid, bj_date),
            )
            for row in cur.fetchall():
                r_id = str(row["id"] or "")
                ex_m = float(row["distance_meters"] or 0.0)
                has_gps = bool(row["gps_track_data"])
                tol_m = max(200.0, dist_m * 0.03)
                # 1. Exact/near-exact distance match on same day
                if abs(ex_m - dist_m) <= tol_m:
                    if has_gps:
                        act_id = r_id
                        already_has_same_track = True
                        break
                    else:
                        # Enrich existing HealthKit / screenshot record with full GPS track
                        act_id = r_id
                        break
                # 2. HealthKit record within ±5 minutes
                if r_id.startswith("hk_"):
                    try:
                        r_dt = datetime.fromisoformat(str(row["start_time"]).replace("Z", "+00:00"))
                        if abs((r_dt - target_dt).total_seconds()) <= 300:
                            act_id = r_id
                            break
                    except Exception:
                        pass
                # 3. Coarse daily summary from Apple Health list on the same day -> remove so it won't double-count
                if (
                    "_img_" in r_id
                    and not has_gps
                    and not row["average_heartrate"]
                    and str(row["avg_pace_str"] or "").startswith("6:00")
                    and str(row["start_time"] or "")[11:16] == "07:30"
                ):
                    stale_screenshot_ids_to_delete.append(r_id)
    except Exception:
        pass

    pace = "—"
    if km > 0.05 and dur_s > 0:
        sec = int(round(dur_s / km))
        pace = f"{sec // 60}:{sec % 60:02d} /km"

    avg_hr = parsed["average_heartrate"]
    pts_count = len(parsed["route"])

    if already_has_same_track:
        return {
            "success": True,
            "status": "duplicate",
            "imported": 0,
            "skipped_duplicates": 1,
            "activity_id": act_id,
            "distance_km": round(km, 2),
            "gps_points": pts_count,
            "activity": {
                "id": act_id,
                "distance_km": round(km, 2),
                "duration_sec": dur_s,
                "avg_pace_str": pace.replace(" /km", ""),
                "avg_hr": avg_hr,
            },
            "message": f"该 {brand_label} 跑步轨迹（{round(km, 2)} km）已存在于您的记录中，已自动跳过重复导入 ✓",
        }

    if stale_screenshot_ids_to_delete:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                for old_id in stale_screenshot_ids_to_delete:
                    if old_id != act_id:
                        cur.execute("DELETE FROM activities WHERE id = ? AND user_id = ?", (old_id, uid))
                conn.commit()
        except Exception:
            pass

    trimp = calculate_trimp(dur_s / 60.0, float(avg_hr), rest_hr, max_hr, gender) if avg_hr and dur_s > 0 else None
    track = _build_hk_track(act_id, parsed["route"])

    act = {
        "id": act_id,
        "user_id": uid,
        "name": f"{brand_label} 户外跑步",
        "sport_type": "Run",
        "start_time": bj_start,
        "distance_meters": dist_m,
        "moving_time_seconds": dur_s,
        "elapsed_time_seconds": dur_s,
        "elevation_gain_meters": parsed["elevation_gain_meters"],
        "average_heartrate": avg_hr,
        "max_heartrate": parsed["max_heartrate"],
        "average_cadence": parsed["average_cadence"],
        "avg_pace_str": pace,
        "calories": parsed["calories"],
        "trimp": trimp,
    }
    if track:
        act["gps_track_data"] = track

    LocalStore.upsert_activity(act, notify=False)
    try:
        LocalStore.compute_and_cache_segment_analysis(act_id)
    except Exception:
        pass

    now_iso = datetime.utcnow().isoformat() + "Z"
    if target_brand == "suunto":
        st_updates = {
            "suunto_connected": 1,
            "suunto_last_sync_at": now_iso,
        }
        if not profile.get("suunto_account"):
            st_updates["suunto_account"] = "Suunto App"
        LocalStore.upsert_profile(uid, st_updates)
    elif target_brand == "huawei":
        hw_updates = {
            "huawei_connected": 1,
            "huawei_last_sync_at": now_iso,
        }
        if not profile.get("huawei_account"):
            hw_updates["huawei_account"] = "华为运动健康 App"
        LocalStore.upsert_profile(uid, hw_updates)
    else:
        LocalStore.upsert_profile(uid, {
            "apple_watch_connected": 1,
            "apple_watch_last_sync_at": now_iso,
        })

    return {
        "success": True,
        "status": "success",
        "imported": 1,
        "activity_id": act_id,
        "distance_km": round(km, 2),
        "gps_points": pts_count,
        "activity": {
            "id": act_id,
            "distance_km": round(km, 2),
            "duration_sec": dur_s,
            "avg_pace_str": pace.replace(" /km", ""),
            "avg_hr": avg_hr,
        },
        "message": f"成功导入 {brand_label} 跑步记录（{round(km, 2)} km，含 {pts_count} 个 GPS 轨迹点）✓",
    }


class ScreenshotImportRequest(BaseModel):
    uid: str
    image_base64: str
    filename: Optional[str] = "screenshot.jpg"
    source_brand: Optional[str] = "huawei"


def _parse_flexible_date(raw_date: str, bj_today: date) -> Optional[str]:
    """Normalize various date strings from screenshots into YYYY-MM-DD."""
    import re
    if not raw_date:
        return None
    s = str(raw_date).strip()
    if s in ("今天", "今日", "Today", "today"):
        return bj_today.isoformat()
    if s in ("昨天", "昨日", "Yesterday", "yesterday"):
        return (bj_today - timedelta(days=1)).isoformat()
    if s in ("前天",):
        return (bj_today - timedelta(days=2)).isoformat()

    # Match YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD, YYYY年MM月DD日
    m_full = re.search(r"(20\d{2})[-/.年\s](\d{1,2})[-/.月\s](\d{1,2})", s)
    if m_full:
        try:
            d = date(int(m_full.group(1)), int(m_full.group(2)), int(m_full.group(3)))
            return d.isoformat()
        except Exception:
            pass

    # Match MM-DD, MM/DD, MM.DD, MM月DD日 (no year)
    m_md = re.search(r"(\d{1,2})[-/.月](\d{1,2})日?", s)
    if m_md:
        try:
            month_v = int(m_md.group(1))
            day_v = int(m_md.group(2))
            yr = bj_today.year
            cand = date(yr, month_v, day_v)
            if cand > bj_today + timedelta(days=2):
                cand = date(yr - 1, month_v, day_v)
            return cand.isoformat()
        except Exception:
            pass
    return None


def _parse_flexible_duration_sec(val: Any) -> Optional[int]:
    """Parse duration into seconds from int/float or 'HH:MM:SS' / 'MM:SS' / 'X小时Y分Z秒'."""
    import re
    if val is None:
        return None
    if isinstance(val, (int, float)):
        v = int(round(float(val)))
        return v if v > 0 else None
    s = str(val).strip()
    if not s:
        return None
    if s.isdigit():
        v = int(s)
        return v if v > 0 else None
    # HH:MM:SS or MM:SS
    parts = s.split(":")
    if len(parts) == 3 and all(p.strip().isdigit() for p in parts):
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    if len(parts) == 2 and all(p.strip().isdigit() for p in parts):
        return int(parts[0]) * 60 + int(parts[1])
    # Chinese format like 1小时05分20秒 or 48分30秒
    h_m = re.search(r"(\d+)\s*(?:小时|h|hr)", s, re.I)
    m_m = re.search(r"(\d+)\s*(?:分钟|分|min|m(?!s))", s, re.I)
    s_m = re.search(r"(\d+)\s*(?:秒|sec|s)", s, re.I)
    if h_m or m_m or s_m:
        total = (int(h_m.group(1)) * 3600 if h_m else 0) + (int(m_m.group(1)) * 60 if m_m else 0) + (int(s_m.group(1)) if s_m else 0)
        return total if total > 0 else None
    return None


def _parse_pace_to_sec_per_km(pace_val: Any) -> Optional[int]:
    """Parse pace string like 5'30\", 5:30, 5分30秒 into seconds per km."""
    import re
    if not pace_val:
        return None
    s = str(pace_val).strip()
    m = re.search(r"(\d{1,2})\s*['′:分]\s*(\d{1,2})", s)
    if m:
        mins = int(m.group(1))
        secs = int(m.group(2))
        if 2 <= mins <= 20 and 0 <= secs < 60:
            return mins * 60 + secs
    return None


def _extract_runs_from_screenshot_bytes(raw_bytes: bytes, filename: str = "screenshot.jpg") -> List[Dict[str, Any]]:
    """
    Call multimodal model to extract one or multiple running records from a screenshot
    (Apple Health list, Huawei Health summary/list, Suunto, Apple Fitness, Keep, etc.).
    """
    import base64
    import calendar
    import re
    import httpx
    from config import settings

    if not raw_bytes or len(raw_bytes) < 64:
        raise ValueError("图片内容为空或已损坏")

    ext = (filename or "screenshot.jpg").lower().rsplit(".", 1)[-1]
    mime = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
    b64_str = base64.b64encode(raw_bytes).decode("utf-8")

    bj_now = datetime.utcnow() + timedelta(hours=8)
    bj_today = bj_now.date()

    prompt = (
        f"今天是北京时间 {bj_today.isoformat()}（年份默认为 {bj_today.year} 年）。\n"
        "请仔细识别这张运动或健康截图中的跑步/运动记录。截图可能是以下任意一种：\n"
        "1. 苹果健康（Apple Health）「所有已记录的数据」列表（包含多行【公里数 + 具体某月某日】，例如多天的距离列表）；\n"
        "2. 华为运动健康（Huawei Health）、Suunto App、Apple Watch 体能训练、Keep、佳明、高驰的单次跑步详情截图或运动记录列表截图。\n\n"
        "请提取图中所有可见的单次跑步或单日记录，只输出严格的 JSON 对象，不要包含任何 Markdown 代码块或多余解释，格式如下：\n"
        "{\n"
        '  "records": [\n'
        "    {\n"
        '      "date": "YYYY-MM-DD",\n'
        '      "start_time_hm": "HH:MM",\n'
        '      "distance_km": 10.6,\n'
        '      "duration_seconds": null,\n'
        '      "avg_pace_str": null,\n'
        '      "average_heartrate": null,\n'
        '      "average_cadence": null,\n'
        '      "calories": null,\n'
        '      "sport_name": "户外跑步",\n'
        '      "is_summary_header": false\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "重要规则（必须严格遵守）：\n"
        "- 【严禁提取月度/周度/年度汇总标题栏】：运动列表顶部常见的“2026年10月 跑步 34.73公里”、“9月 75.29公里”、“本月总距离”、“本周累计”、“总跑量”等属于阶段汇总数字，绝对不是单次跑步记录！请直接忽略，或将其 is_summary_header 设为 true。\n"
        "- 【严禁编造月底日期】：如果某一行只有年份和月份（如“2026年10月”或“9月”）而没有具体的“几日”，说明它是月度汇总，绝对不要把它编造成 10月31日 或 9月30日！\n"
        f"- 如果图中日期未标注年份（如“10月18日”），默认使用 {bj_today.year} 年；若写“今天”则为 {bj_today.isoformat()}，“昨天”则为 {(bj_today - timedelta(days=1)).isoformat()}。晚于今天（{bj_today.isoformat()}）的未来日期一律忽略。\n"
        "- 如果图中未显示具体几点几分，start_time_hm 填 \"07:30\"。\n"
        "- 如果图中是苹果健康距离列表，只显示了公里数和日期，没有配速/用时/心率，则 duration_seconds、avg_pace_str、average_heartrate 填 null 即可，切勿编造。\n"
        "- 如果图中显示了用时（如 00:52:10 或 52分10秒），请换算为总秒数填入 duration_seconds。\n"
        "- 如果图中显示了配速（如 5'12\" 或 5:12/km），填入 avg_pace_str（格式如 \"5:12\"）。\n"
        "- 请确保只提取具有明确【某月某日】的有效单日/单次记录（距离 > 0.1 km）。"
    )

    api_key = settings.OPENAI_API_KEY
    base_url = (settings.OPENAI_API_BASE or "").rstrip("/")
    if not api_key or not base_url:
        raise ValueError("服务端视觉识别配置缺失，请联系管理员")

    models_to_try = ["qwen3.8-flash", "qwen3-vl-plus", "qwen3.5-ocr"]
    raw_content = None
    last_err = None

    with httpx.Client(timeout=45.0) as client:
        for model_name in models_to_try:
            try:
                payload = {
                    "model": model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_str}"}},
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "enable_thinking": False,
                }
                resp = client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw_content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    if raw_content and raw_content.strip():
                        break
                else:
                    last_err = f"{model_name} HTTP {resp.status_code}: {resp.text[:160]}"
                    logger.warning(f"[screenshot-import] {last_err}")
            except Exception as e:
                last_err = f"{model_name} error: {e}"
                logger.warning(f"[screenshot-import] {last_err}")

    if not raw_content:
        raise ValueError(f"未能从截图中识别出运动数据（{last_err or '响应为空'}）")

    cleaned = raw_content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    # Extract first JSON object or array
    m_json = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if m_json:
        cleaned = m_json.group(1)

    try:
        parsed_json = json.loads(cleaned)
    except Exception as e:
        logger.error(f"[screenshot-import] JSON parse error: {e} | raw: {raw_content[:300]}")
        raise ValueError("截图数据格式解析失败，请确保截图清晰完整")

    raw_records = parsed_json.get("records") if isinstance(parsed_json, dict) else (parsed_json if isinstance(parsed_json, list) else [])
    if not isinstance(raw_records, list) or len(raw_records) == 0:
        raise ValueError("截图中未检测到有效的跑步距离记录，请上传包含公里数和日期的运动截图")

    summary_keywords = ("汇总", "累计", "总计", "月度", "周跑量", "月跑量", "总距离", "总里程", "目标")
    normalized: List[Dict[str, Any]] = []
    for item in raw_records:
        if not isinstance(item, dict):
            continue
        if item.get("is_summary_header") is True:
            continue
        sport_name_raw = str(item.get("sport_name") or "户外跑步").strip() or "户外跑步"
        if any(kw in sport_name_raw for kw in summary_keywords):
            continue

        raw_date_str = str(item.get("date") or "").strip()
        # Reject month-only strings like "2026-10", "2026年10月", "10月"
        if re.match(r"^(?:20\d{2}[-/.年\s]?)?\d{1,2}月?$", raw_date_str):
            continue

        try:
            dist_km = float(item.get("distance_km") or 0)
        except Exception:
            continue
        if dist_km < 0.1 or dist_km > 300.0:
            continue

        norm_date = _parse_flexible_date(raw_date_str, bj_today)
        if not norm_date:
            continue
        try:
            rec_dt = date.fromisoformat(norm_date)
        except Exception:
            continue

        # Never allow future dates (e.g. LLM turning "10月 34.73公里" into 2026-10-31 when today is 2026-10-18)
        if rec_dt > bj_today:
            logger.info(f"[screenshot-import] skipping future date record: {norm_date} ({dist_km} km)")
            continue

        raw_hm = str(item.get("start_time_hm") or "07:30").strip()
        m_hm = re.search(r"(\d{1,2}):(\d{2})", raw_hm)
        if m_hm:
            hh = min(23, max(0, int(m_hm.group(1))))
            mm = min(59, max(0, int(m_hm.group(2))))
            norm_hm = f"{hh:02d}:{mm:02d}"
        else:
            norm_hm = "07:30"

        dur_s = _parse_flexible_duration_sec(item.get("duration_seconds"))
        pace_sec = _parse_pace_to_sec_per_km(item.get("avg_pace_str"))

        if (not dur_s or dur_s <= 0) and pace_sec and pace_sec > 0:
            dur_s = int(round(dist_km * pace_sec))
        if not dur_s or dur_s <= 0:
            # Default 6:00/km estimation when screenshot only shows distance (e.g. Apple Health distance list)
            dur_s = int(round(dist_km * 360))
            has_exact_duration = False
        else:
            has_exact_duration = True

        # Guard against monthly summary headers that LLM mapped to last day of a past month (e.g. 2026-09-30 75.29km with no duration/pace)
        last_day_of_month = calendar.monthrange(rec_dt.year, rec_dt.month)[1]
        if not has_exact_duration and norm_hm == "07:30":
            if dist_km > 43.0 or (rec_dt.day == last_day_of_month and dist_km > 30.0 and len(raw_records) >= 2):
                logger.info(f"[screenshot-import] skipping suspected monthly header: {norm_date} ({dist_km} km)")
                continue

        sec_per_km = int(round(dur_s / dist_km)) if dist_km > 0 else 360
        pace_str = f"{sec_per_km // 60}:{sec_per_km % 60:02d} /km"

        avg_hr = None
        if item.get("average_heartrate") is not None:
            try:
                hr_v = int(round(float(item.get("average_heartrate"))))
                if 40 <= hr_v <= 230:
                    avg_hr = hr_v
            except Exception:
                pass

        avg_cad = None
        if item.get("average_cadence") is not None:
            try:
                cad_v = float(item.get("average_cadence"))
                if 45 <= cad_v <= 115:
                    cad_v *= 2.0
                if 100 <= cad_v <= 250:
                    avg_cad = round(cad_v, 1)
            except Exception:
                pass

        cals = None
        if item.get("calories") is not None:
            try:
                c_v = float(item.get("calories"))
                if 5 <= c_v <= 10000:
                    cals = round(c_v, 1)
            except Exception:
                pass

        normalized.append({
            "date": norm_date,
            "start_time_hm": norm_hm,
            "distance_km": round(dist_km, 2),
            "distance_meters": round(dist_km * 1000.0, 1),
            "duration_seconds": dur_s,
            "has_exact_duration": has_exact_duration,
            "avg_pace_str": pace_str,
            "average_heartrate": avg_hr,
            "average_cadence": avg_cad,
            "calories": cals,
            "sport_name": sport_name_raw,
        })

    if not normalized:
        raise ValueError("未能从截图中提取到有效单日跑步记录（需包含具体日期及 ≥ 0.1 km 距离），请重试")

    # Intra-screenshot deduplication: avoid duplicate rows within the same image
    deduped_in_img: List[Dict[str, Any]] = []
    for cand in normalized:
        is_dup_in_img = False
        for existing_cand in deduped_in_img:
            if existing_cand["date"] == cand["date"]:
                tol_km = max(0.2, cand["distance_km"] * 0.03)
                # Same date and nearly identical distance
                if abs(existing_cand["distance_km"] - cand["distance_km"]) <= tol_km:
                    if cand["has_exact_duration"] and not existing_cand["has_exact_duration"]:
                        existing_cand.update(cand)
                    is_dup_in_img = True
                    break
                # Both are daily summary rows (no duration/pace, 07:30 default) on the same date -> keep larger/latest
                if (
                    not existing_cand["has_exact_duration"]
                    and not cand["has_exact_duration"]
                    and existing_cand["start_time_hm"] == "07:30"
                    and cand["start_time_hm"] == "07:30"
                ):
                    if cand["distance_km"] > existing_cand["distance_km"]:
                        existing_cand.update(cand)
                    is_dup_in_img = True
                    break
        if not is_dup_in_img:
            deduped_in_img.append(cand)

    # Sort chronologically (oldest first)
    deduped_in_img.sort(key=lambda r: (r["date"], r["start_time_hm"]))
    return deduped_in_img


def _is_screenshot_activity(ex: Dict[str, Any]) -> bool:
    return "_img_" in str(ex.get("id") or "")


def _is_daily_summary_activity(ex: Dict[str, Any]) -> bool:
    """True if activity was imported from an Apple Health daily distance list (no GPS, no HR, 6:00/km fallback at 07:30)."""
    return (
        _is_screenshot_activity(ex)
        and not ex.get("gps_track_data")
        and not ex.get("average_heartrate")
        and str(ex.get("avg_pace_str") or "").startswith("6:00")
        and str(ex.get("start_time") or "")[11:16] == "07:30"
    )


def _process_screenshot_import(uid: str, raw_bytes: bytes, filename: str, source_brand: str) -> Dict[str, Any]:
    import hashlib
    import sqlite3
    from utils.local_store import DB_PATH

    profile = LocalStore.get_profile(uid) or {}
    raw_brand = (source_brand or "huawei").strip().lower()
    if raw_brand == "apple_watch":
        target_brand = "apple_watch"
        brand_prefix = "aw"
        brand_label = "Apple Watch"
    elif raw_brand == "suunto":
        target_brand = "suunto"
        brand_prefix = "st"
        brand_label = "颂拓 Suunto"
    else:
        target_brand = "huawei"
        brand_prefix = "hw"
        brand_label = "华为手表"

    for flag, label in [("garmin_connected", "佳明 Garmin"), ("coros_connected", "高驰 COROS")]:
        if profile.get(flag):
            raise HTTPException(
                status_code=400,
                detail=f"当前账号已连接【{label}】。每个账号仅限连接一个运动手表，请先解绑【{label}】后再切换。"
            )

    try:
        records = _extract_runs_from_screenshot_bytes(raw_bytes, filename=filename)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"[screenshot-import] unexpected error for {uid}: {e}")
        raise HTTPException(status_code=400, detail=f"识别运动截图失败：{str(e)}")

    max_hr = float(profile.get("max_heart_rate") or 190)
    rest_hr = float(profile.get("resting_heart_rate") or 56)
    gender = str(profile.get("gender") or "male")

    # Load existing activities for smart deduplication
    existing_by_date: Dict[str, List[Dict[str, Any]]] = {}
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, start_time, distance_meters, moving_time_seconds, average_heartrate, avg_pace_str, gps_track_data FROM activities WHERE user_id = ?",
                (uid,),
            )
            for row in cur.fetchall():
                st = str(row["start_time"] or "")
                d_key = st[:10]
                existing_by_date.setdefault(d_key, []).append(dict(row))
    except Exception as e:
        logger.warning(f"[screenshot-import] existing query warning: {e}")

    imported_count = 0
    updated_count = 0
    skipped_count = 0
    imported_km_sum = 0.0
    result_items = []
    cleared_dates_in_batch = set()

    for rec in records:
        rec_date = rec["date"]
        rec_hm = rec["start_time_hm"]
        dist_m = rec["distance_meters"]
        dist_km = rec["distance_km"]
        dur_s = rec["duration_seconds"]
        avg_hr = rec["average_heartrate"]
        pace_str = rec["avg_pace_str"]
        has_exact_dur = bool(rec.get("has_exact_duration"))
        rec_is_daily_summary = (not has_exact_dur and rec_hm == "07:30" and not avg_hr)

        bj_start = f"{rec_date}T{rec_hm}:00+08:00"
        digest = hashlib.md5(f"{uid}:{rec_date}:{dist_km:.2f}".encode("utf-8")).hexdigest()[:10]
        act_id = f"{brand_prefix}_img_{digest}"

        same_day_list = existing_by_date.get(rec_date, [])
        tol_m = max(200.0, dist_m * 0.03)

        # 1. Check if same date already has an activity with nearly identical distance (±200m or ±3%)
        matched_existing = None
        for ex in same_day_list:
            ex_m = float(ex.get("distance_meters") or 0.0)
            if abs(ex_m - dist_m) <= tol_m:
                matched_existing = ex
                break

        if matched_existing:
            ex_id = matched_existing["id"]
            # Only upgrade in-place if existing lacks GPS AND new screenshot provides HR or exact duration that existing lacked
            is_upgrade = (
                not matched_existing.get("gps_track_data")
                and (
                    (bool(avg_hr) and not matched_existing.get("average_heartrate"))
                    or (has_exact_dur and _is_daily_summary_activity(matched_existing))
                )
            )
            if not is_upgrade:
                skipped_count += 1
                result_items.append({
                    "id": ex_id,
                    "date": rec_date,
                    "distance_km": dist_km,
                    "duration_sec": dur_s,
                    "avg_pace_str": pace_str.replace(" /km", ""),
                    "avg_hr": avg_hr or matched_existing.get("average_heartrate"),
                    "status": "duplicate_skipped",
                })
                continue
            else:
                act_id = ex_id

        # 2. Same-day conflict resolution when distances differ
        ids_to_delete_on_day: List[str] = []
        if not matched_existing and same_day_list:
            if rec_is_daily_summary:
                # If the day already has a non-screenshot real workout (Garmin/COROS/HealthKit/GPX), skip coarse daily summary
                has_real_non_img = any(not _is_screenshot_activity(ex) or ex.get("gps_track_data") for ex in same_day_list)
                if has_real_non_img:
                    skipped_count += 1
                    result_items.append({
                        "id": same_day_list[0]["id"],
                        "date": rec_date,
                        "distance_km": dist_km,
                        "duration_sec": dur_s,
                        "avg_pace_str": pace_str.replace(" /km", ""),
                        "avg_hr": avg_hr,
                        "status": "duplicate_skipped",
                    })
                    continue
                # Otherwise replace any earlier screenshot records on this date (e.g. 5.1km -> 6.2km updated daily total)
                for ex in same_day_list:
                    if _is_screenshot_activity(ex):
                        ids_to_delete_on_day.append(str(ex["id"]))
            else:
                # New record is a specific workout with duration/pace:
                # Remove any coarse Apple Health daily summary on the same date so they don't stack
                for ex in same_day_list:
                    if _is_daily_summary_activity(ex):
                        ids_to_delete_on_day.append(str(ex["id"]))
                    elif (
                        _is_screenshot_activity(ex)
                        and rec_date not in cleared_dates_in_batch
                        and str(ex.get("start_time") or "")[11:16] == rec_hm
                        and rec_hm != "07:30"
                    ):
                        # Same date and exact same HH:MM start time from an earlier screenshot
                        ids_to_delete_on_day.append(str(ex["id"]))

        if ids_to_delete_on_day:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.cursor()
                    for old_id in ids_to_delete_on_day:
                        if old_id != act_id:
                            cur.execute("DELETE FROM activities WHERE id = ? AND user_id = ?", (old_id, uid))
                    conn.commit()
                existing_by_date[rec_date] = [ex for ex in same_day_list if str(ex.get("id")) not in ids_to_delete_on_day]
                updated_count += 1
            except Exception as e:
                logger.warning(f"[screenshot-import] cleanup old same-day record error: {e}")

        cleared_dates_in_batch.add(rec_date)

        trimp = calculate_trimp(dur_s / 60.0, float(avg_hr), rest_hr, max_hr, gender) if avg_hr and dur_s > 0 else None
        act = {
            "id": act_id,
            "user_id": uid,
            "name": f"{brand_label} {rec['sport_name']}",
            "sport_type": "Run",
            "start_time": bj_start,
            "distance_meters": dist_m,
            "moving_time_seconds": dur_s,
            "elapsed_time_seconds": dur_s,
            "elevation_gain_meters": None,
            "average_heartrate": avg_hr,
            "max_heartrate": None,
            "average_cadence": rec["average_cadence"],
            "avg_pace_str": pace_str,
            "calories": rec["calories"],
            "trimp": trimp,
        }
        LocalStore.upsert_activity(act, notify=False)
        existing_by_date.setdefault(rec_date, []).append(act)
        imported_count += 1
        imported_km_sum += dist_km
        result_items.append({
            "id": act_id,
            "date": rec_date,
            "distance_km": dist_km,
            "duration_sec": dur_s,
            "avg_pace_str": pace_str.replace(" /km", ""),
            "avg_hr": avg_hr,
            "status": "updated" if (ids_to_delete_on_day or matched_existing) else "imported",
        })

    now_iso = datetime.utcnow().isoformat() + "Z"
    if target_brand == "suunto":
        st_updates = {
            "suunto_connected": 1,
            "suunto_last_sync_at": now_iso,
        }
        if not profile.get("suunto_account"):
            st_updates["suunto_account"] = "Suunto App"
        LocalStore.upsert_profile(uid, st_updates)
    elif target_brand == "huawei":
        hw_updates = {
            "huawei_connected": 1,
            "huawei_last_sync_at": now_iso,
        }
        if not profile.get("huawei_account"):
            hw_updates["huawei_account"] = "华为运动健康 App"
        LocalStore.upsert_profile(uid, hw_updates)
    else:
        LocalStore.upsert_profile(uid, {
            "apple_watch_connected": 1,
            "apple_watch_last_sync_at": now_iso,
        })

    if imported_count > 0 and skipped_count > 0:
        if updated_count > 0:
            msg = f"已更新/导入 {imported_count} 条跑步记录（{round(imported_km_sum, 1)} km），自动跳过 {skipped_count} 条已存在记录 ✓"
        else:
            msg = f"成功导入 {imported_count} 条跑步记录（共 {round(imported_km_sum, 1)} km），另有 {skipped_count} 条同日记录已存在自动跳过 ✓"
    elif imported_count > 0:
        msg = f"成功识别并导入 {imported_count} 条 {brand_label} 跑步记录（累计 {round(imported_km_sum, 1)} km）✓"
    else:
        msg = f"识别到 {len(records)} 条跑步记录，但均已存在于您的运动记录中，已自动跳过重复导入 ✓"

    return {
        "success": True,
        "status": "success",
        "imported": imported_count,
        "skipped_duplicates": skipped_count,
        "total_recognized": len(records),
        "total_distance_km": round(imported_km_sum, 2),
        "records": result_items,
        "message": msg,
    }


@router.post("/import-screenshot")
def import_screenshot_json(req: ScreenshotImportRequest, request: Request):
    """Import one or multiple running records from a base64-encoded screenshot."""
    import base64

    token_uid = getattr(request.state, "user_id", None)
    if not req.uid or not req.uid.strip():
        raise HTTPException(status_code=401, detail="请先登录")
    if token_uid and token_uid != req.uid:
        raise HTTPException(status_code=403, detail="无权为其他账号导入数据")

    b64_clean = (req.image_base64 or "").strip()
    if "," in b64_clean and b64_clean.startswith("data:"):
        b64_clean = b64_clean.split(",", 1)[1]

    try:
        raw_bytes = base64.b64decode(b64_clean)
    except Exception:
        raise HTTPException(status_code=400, detail="截图图片编码无法解析")

    return _process_screenshot_import(
        uid=req.uid.strip(),
        raw_bytes=raw_bytes,
        filename=req.filename or "screenshot.jpg",
        source_brand=req.source_brand or "huawei",
    )


@router.post("/import-screenshot-upload")
async def import_screenshot_upload(
    request: Request,
    file: UploadFile = File(...),
    uid: str = Form(...),
    source_brand: str = Form("huawei"),
):
    """Import one or multiple running records from a multipart uploaded screenshot (via uni.uploadFile)."""
    token_uid = getattr(request.state, "user_id", None)
    if not uid or not uid.strip():
        raise HTTPException(status_code=401, detail="请先登录")
    if token_uid and token_uid != uid:
        raise HTTPException(status_code=403, detail="无权为其他账号导入数据")

    raw_bytes = await file.read()
    return _process_screenshot_import(
        uid=uid.strip(),
        raw_bytes=raw_bytes,
        filename=file.filename or "screenshot.jpg",
        source_brand=source_brand or "huawei",
    )


