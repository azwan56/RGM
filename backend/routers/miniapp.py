"""
Dedicated High-Performance Endpoints for WeChat Mini Program & Web Dashboard
Reduces network roundtrips by bundling essential dashboard data into single fast responses.
Includes smart user mapping so newly opened Mini Programs automatically resolve to the active runner profile.
"""

import json
import hashlib
import calendar
import ipaddress
import logging
import re
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import settings
from db import supabase_admin
from utils.local_store import LocalStore, DB_PATH, sqlite3
from utils.running_metrics import compute_ctl_atl_tsb, compute_canova_athlete_matrix
from utils.encryption import decrypt_string
from utils.garmin_adapter import GarminAdapter
from utils.security import is_safe_external_url
from utils.coros_adapter import CorosAdapter

logger = logging.getLogger("router_miniapp")
router = APIRouter()


@router.get("/dashboard/{uid}")
def get_miniapp_dashboard_data(
    uid: str,
    viewer_uid: Optional[str] = Query(None, description="Viewer user ID"),
    request: Request = None,
) -> Dict[str, Any]:
    """
    Bundles all data needed for Home Screen & Web Dashboard:
    1. Monthly & Weekly Goal Progress (Distance, Target, %, Daily needed)
    2. 6-Month Monthly Running Distance Trend & Recent 3-month breakdown
    3. 2026 Yearly Totals, Projected KM, Run Counts, Circular Gauge Stats
    4. Garmin Connection Status & Last Sync Time
    5. Recent Running Activities
    6. Today's Health Metrics (Sleep Score & Hours, RHR, Body Battery, HRV)
    7. AI Coach Tip of the Day
    """
    try:
        eff_uid = LocalStore.resolve_user_id(uid)
        eff_viewer = (
            viewer_uid
            if isinstance(viewer_uid, str) and viewer_uid.strip()
            else (
                (request.headers.get("x-user-id") if request else None)
                or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
            )
        )
        resolved_viewer = LocalStore.resolve_user_id(str(eff_viewer).strip()) if eff_viewer else None
        is_cross_viewer = bool(resolved_viewer and resolved_viewer != eff_uid)
        profile = LocalStore.get_profile(eff_uid) or {
            "id": eff_uid,
            "display_name": "微信跑者",
            "garmin_connected": False,
        }
        dash_privacy_cache: Dict[str, Dict[str, Any]] = {eff_uid: profile}
        hide_dash_bio = (
            is_cross_viewer
            and bool(profile.get("hide_biometrics"))
            and not LocalStore.can_view_confidential_runner_data(resolved_viewer, eff_uid)
        )

        # 2. Compute Monthly Goal Progress
        today = LocalStore.get_beijing_today()
        month_start = date(today.year, today.month, 1).isoformat()
        _, total_days = calendar.monthrange(today.year, today.month)
        days_left = max(1, total_days - today.day + 1)

        goal = LocalStore.get_goal(eff_uid)
        monthly_targets = goal.get("monthly_targets")
        if monthly_targets and isinstance(monthly_targets, list) and len(monthly_targets) >= today.month:
            target_km = float(monthly_targets[today.month - 1] or goal.get("target_distance") or 200.0)
        else:
            target_km = float(goal.get("target_distance") or 200.0)

        current_m = LocalStore.get_month_distance_meters(eff_uid, month_start)
        current_km = round(current_m / 1000.0, 1)
        progress_pct = round((current_km / target_km) * 100, 1) if target_km > 0 else 0.0
        remaining_km = max(0.0, round(target_km - current_km, 1))
        daily_req = round(remaining_km / days_left, 1)

        # 2.1 Weekly Progress (respect locked current_week_target when next week was modified)
        weekly_progress = LocalStore.get_weekly_stats(
            eff_uid,
            target_km=goal.get("current_week_target") or goal.get("weekly_target"),
        )

        # 3. Monthly Trend (6 months) & Yearly Stats (2026)
        monthly_trend = LocalStore.get_monthly_trend(eff_uid, num_months=6)
        yearly_stats = LocalStore.get_yearly_stats(eff_uid, year=2026)

        # 4. Current Month Activities (All activities for current month)
        today = LocalStore.get_beijing_today()
        month_acts = LocalStore.get_month_activities(eff_uid, today.year, today.month)
        formatted_month_acts = []
        for a in month_acts:
            dist_m = float(a.get("distance_meters") or 0)
            dist_km = round(dist_m / 1000.0, 2)
            has_gps = bool(
                a.get("gps_track_data")
                or a.get("map_image_url")
                or (
                    str(a.get("id")).startswith(("garmin_", "coros_"))
                    and (LocalStore.is_running_activity(a.get("sport_type")) or a.get("sport_type") in ["Ride", "Hike", "Walk"])
                )
            )
            if is_cross_viewer:
                filtered_journal, j_hidden = LocalStore.filter_canova_critique_for_viewer(
                    a.get("ai_journal"),
                    viewer_uid=resolved_viewer,
                    target_uid=eff_uid,
                    profile_cache=dash_privacy_cache,
                )
            else:
                filtered_journal, j_hidden = a.get("ai_journal"), False
            formatted_month_acts.append({
                "id": a["id"],
                "name": a["name"],
                "start_time": a["start_time"],
                "distance_meters": dist_m,
                "distance_km": dist_km,
                "moving_time_seconds": a.get("moving_time_seconds") or 0,
                "avg_pace_str": a.get("avg_pace_str") or "—",
                "average_heartrate": None if hide_dash_bio else a.get("average_heartrate"),
                "elevation_gain_meters": round(float(a.get("elevation_gain_meters") or a.get("total_elevation_gain") or 0), 1),
                "trimp": None if hide_dash_bio else a.get("trimp"),
                "workout_effective_vdot": a.get("workout_effective_vdot"),
                "exclude_mode": a.get("exclude_mode") or "normal",
                "ai_journal": filtered_journal,
                "is_critique_hidden": j_hidden,
                "has_gps_track": has_gps,
                "map_image_url": a.get("map_image_url")
            })

        # Recent activities (for fitness form and fallback)
        local_acts = LocalStore.get_recent_activities(eff_uid, limit=100)
        fallback_recent = []
        if not formatted_month_acts:
            for a in local_acts[:10]:
                if (a.get("exclude_mode") or "normal") == "excluded":
                    continue
                dist_m = float(a.get("distance_meters") or 0)
                dist_km = round(dist_m / 1000.0, 2)
                has_gps = bool(
                a.get("gps_track_data")
                or a.get("map_image_url")
                or (
                    str(a.get("id")).startswith(("garmin_", "coros_"))
                    and (LocalStore.is_running_activity(a.get("sport_type")) or a.get("sport_type") in ["Ride", "Hike", "Walk"])
                )
            )
                if is_cross_viewer:
                    filtered_journal, j_hidden = LocalStore.filter_canova_critique_for_viewer(
                        a.get("ai_journal"),
                        viewer_uid=resolved_viewer,
                        target_uid=eff_uid,
                        profile_cache=dash_privacy_cache,
                    )
                else:
                    filtered_journal, j_hidden = a.get("ai_journal"), False
                fallback_recent.append({
                    "id": a["id"],
                    "name": a["name"],
                    "start_time": a["start_time"],
                    "distance_meters": dist_m,
                    "distance_km": dist_km,
                    "moving_time_seconds": a.get("moving_time_seconds") or 0,
                    "avg_pace_str": a.get("avg_pace_str") or "—",
                    "average_heartrate": None if hide_dash_bio else a.get("average_heartrate"),
                    "elevation_gain_meters": round(float(a.get("elevation_gain_meters") or a.get("total_elevation_gain") or 0), 1),
                    "trimp": None if hide_dash_bio else a.get("trimp"),
                    "workout_effective_vdot": a.get("workout_effective_vdot"),
                    "exclude_mode": a.get("exclude_mode") or "normal",
                    "ai_journal": filtered_journal,
                    "is_critique_hidden": j_hidden,
                    "has_gps_track": has_gps,
                    "map_image_url": a.get("map_image_url")
                })

        recent_activities = formatted_month_acts if formatted_month_acts else fallback_recent

        # 5. Today's Health Snapshot (4-grid card data)
        if profile.get("garmin_connected"):
            device_brand = "garmin"
        elif profile.get("coros_connected"):
            device_brand = "coros"
        elif profile.get("apple_watch_connected"):
            device_brand = "apple_watch"
        elif profile.get("huawei_connected"):
            device_brand = "huawei"
        elif profile.get("suunto_connected"):
            device_brand = "suunto"
        else:
            device_brand = "none"

        health_data = LocalStore.get_latest_health(eff_uid)
        recovery_avail = LocalStore.assess_recovery_data_availability(
            eff_uid, health_row=health_data, profile=profile, recent_acts=local_acts
        )
        if health_data:
            is_rec_ok = bool(recovery_avail.get("recovery_data_available"))
            sleep_hours = health_data.get("sleep_duration_hours") if is_rec_ok else None
            sleep_sec = health_data.get("sleep_duration_seconds") if is_rec_ok else None
            sleep_score = health_data.get("sleep_score") if is_rec_ok else None
            rhr = health_data.get("resting_heart_rate") if is_rec_ok else None
            body_battery = health_data.get("body_battery_max") if is_rec_ok else None
            hrv_val = health_data.get("hrv_last_night_avg") if is_rec_ok else None
            hrv_weekly = health_data.get("hrv_weekly_avg") if is_rec_ok else None
            if sleep_score is None and is_rec_ok and hrv_val is not None:
                try:
                    base_hrv = float(hrv_weekly) if hrv_weekly and float(hrv_weekly) > 0 else 66.0
                    ratio = float(hrv_val) / base_hrv
                    if ratio > 0:
                        sleep_score = max(45, min(99, int(round(85.0 * (ratio ** 0.7)))))
                except Exception:
                    pass
            vo2 = health_data.get("vo2_max") or profile.get("vo2max")

            sleep_text = None
            if sleep_sec and sleep_sec > 0:
                hours = int(sleep_sec // 3600)
                mins = int((sleep_sec % 3600) // 60)
                sleep_text = f"{hours}h {mins}m"
            elif sleep_hours and sleep_hours > 0:
                hours = int(sleep_hours)
                mins = int(round((sleep_hours % 1) * 60))
                sleep_text = f"{hours}h {mins}m"

            nap_sec = health_data.get("nap_duration_seconds")
            nap_mins = int(round(float(nap_sec) / 60.0)) if nap_sec and int(nap_sec) > 0 else None

            today_health = {
                "date": health_data.get("date") or today.isoformat(),
                "device_brand": device_brand,
                "sleep_score": sleep_score,
                "sleep_duration_hours": sleep_hours,
                "sleep_duration_seconds": sleep_sec,
                "sleep_duration_text": sleep_text,
                "resting_heart_rate": rhr,
                "body_battery_max": body_battery,
                "body_battery_min": health_data.get("body_battery_min") if is_rec_ok else None,
                "body_battery_current": (health_data.get("body_battery_current") or body_battery) if is_rec_ok else None,
                "hrv_ms": int(hrv_val) if hrv_val is not None else None,
                "hrv_weekly_avg": int(hrv_weekly) if hrv_weekly is not None else None,
                "hrv_status": (health_data.get("hrv_status") or "BALANCED") if is_rec_ok else "MISSING",
                "vo2_max": vo2,
                "steps": health_data.get("steps"),
                "active_calories": health_data.get("active_calories"),
                "nap_duration_seconds": nap_sec,
                "nap_duration_minutes": nap_mins,
                "stress_avg": health_data.get("stress_avg"),
                "stress_max": health_data.get("stress_max"),
                "hr_min": health_data.get("hr_min") or rhr,
                "hr_max": health_data.get("hr_max"),
                "updated_at": health_data.get("updated_at"),
                "recovery_data_available": is_rec_ok,
                "night_wear_missing": bool(recovery_avail.get("night_wear_missing")),
                "missing_recovery_fields": recovery_avail.get("missing_recovery_fields", []),
                "recovery_status_label": recovery_avail.get("recovery_status_label", ""),
                "recovery_data_warning": recovery_avail.get("user_warning") if not is_rec_ok else None,
            }
        else:
            today_health = {
                "date": today.isoformat(),
                "device_brand": device_brand,
                "sleep_score": None,
                "sleep_duration_hours": None,
                "sleep_duration_seconds": None,
                "sleep_duration_text": None,
                "resting_heart_rate": None,
                "body_battery_max": None,
                "body_battery_min": None,
                "body_battery_current": None,
                "hrv_ms": None,
                "hrv_weekly_avg": None,
                "hrv_status": "MISSING",
                "vo2_max": profile.get("vo2max"),
                "steps": None,
                "active_calories": None,
                "nap_duration_seconds": None,
                "nap_duration_minutes": None,
                "stress_avg": None,
                "stress_max": None,
                "hr_min": None,
                "hr_max": None,
                "updated_at": None,
                "recovery_data_available": False,
                "night_wear_missing": bool(recovery_avail.get("night_wear_missing")),
                "missing_recovery_fields": recovery_avail.get("missing_recovery_fields", []),
                "recovery_status_label": recovery_avail.get("recovery_status_label", ""),
                "recovery_data_warning": recovery_avail.get("user_warning"),
            }

        # 6. Compute Fitness & Form (CTL, ATL, TSB) via unified MetricsDomainService
        is_any_watch_connected = (device_brand != "none")
        fitness_form = {
            "ctl": 0.0,
            "atl": 0.0,
            "tsb": 0.0,
            "status_label": "待导入首跑" if is_any_watch_connected else "未连接",
            "status_color": "#38bdf8" if is_any_watch_connected else "#6b7280",
            "history": []
        }
        if local_acts:
            try:
                from utils.metrics_domain import MetricsDomainService
                load_summary = MetricsDomainService.compute_load_and_form(
                    activities=local_acts,
                    profile=profile,
                    window_days=30,
                    warmup_days=180,
                )
                if load_summary["history"]:
                    badge = load_summary["current_tsb_badge"]
                    fitness_form = {
                        "ctl": load_summary["current_ctl"],
                        "atl": load_summary["current_atl"],
                        "tsb": load_summary["current_tsb"],
                        "status_label": badge["label"],
                        "status_color": badge["color"],
                        "history": load_summary["history"][-30:],
                    }
            except Exception as e:
                logger.warning(f"[miniapp] Fitness form calc error: {e}")

        # 6.1 Compute authoritative personal VDOT (matching /api/science/analysis/{uid})
        current_vdot: Optional[float] = None
        is_recovery_phase: bool = False
        peak_vdot_val: Optional[float] = None
        try:
            has_watch_vo2 = bool(
                (health_data and health_data.get("vo2_max") and float(health_data.get("vo2_max") or 0) > 0)
                or (profile.get("vo2max") is not None and float(profile.get("vo2max") or 0) > 0)
            )
            v_meta_pb = LocalStore.resolve_verified_runner_profile_and_pbs(
                eff_uid, profile=profile, recent_acts=local_acts, query_activities=True
            )
            has_verified_pb = bool(
                v_meta_pb.get("verified_mp_sec")
                or v_meta_pb.get("verified_hp_sec")
                or v_meta_pb.get("verified_10k_sec")
                or v_meta_pb.get("verified_5k_sec")
            )
            if local_acts or has_watch_vo2 or has_verified_pb:
                clean_prof = {
                    **profile,
                    "marathon_pb": v_meta_pb.get("verified_mp_sec"),
                    "half_pb": v_meta_pb.get("verified_hp_sec"),
                    "ten_k_pb": v_meta_pb.get("verified_10k_sec"),
                    "five_k_pb": v_meta_pb.get("verified_5k_sec"),
                    "peak_vdot": v_meta_pb.get("peak_vdot"),
                    "peak_endurance_vdot": v_meta_pb.get("peak_endurance_vdot"),
                }
                trend_30d = LocalStore.get_health_trend_30d(eff_uid)
                if not trend_30d and health_data:
                    trend_30d = [health_data]
                canova_mat = compute_canova_athlete_matrix(
                    profile=clean_prof,
                    activities=local_acts,
                    current_ctl=float(fitness_form.get("ctl") or 0.0),
                    current_tsb=float(fitness_form.get("tsb") or 0.0),
                    health_trend=trend_30d,
                )
                eff_v = canova_mat.get("effective_vdot")
                if eff_v and float(eff_v) > 0:
                    current_vdot = round(float(eff_v), 1)
                is_recovery_phase = bool(canova_mat.get("is_recovery_phase"))
                peak_vdot_val = canova_mat.get("peak_vdot")
        except Exception as ve:
            logger.warning(f"[miniapp] VDOT calc error: {ve}")

        fitness_form["vdot"] = current_vdot
        fitness_form["is_recovery_phase"] = is_recovery_phase
        fitness_form["peak_vdot"] = peak_vdot_val

        return {
            "user": {
                "id": eff_uid,
                "display_name": profile.get("display_name") or "跑者",
                "avatar_url": profile.get("avatar_url"),
                "garmin_connected": bool(profile.get("garmin_connected")),
                "garmin_email": profile.get("garmin_email"),
                "garmin_last_sync_at": profile.get("garmin_last_sync_at"),
                "garmin_domain": profile.get("garmin_domain") or "garmin.com",
                "coros_connected": bool(profile.get("coros_connected")),
                "coros_account": profile.get("coros_account"),
                "coros_domain": profile.get("coros_domain") or "teamcnapi.coros.com",
                "coros_last_sync_at": profile.get("coros_last_sync_at"),
                "coros_needs_reauth": bool(
                    CorosAdapter.get_cached_auth_state(
                        profile.get("coros_account") or "",
                        profile.get("coros_domain") or "teamcnapi.coros.com",
                    ).get("needs_reauth")
                ) if profile.get("coros_connected") and profile.get("coros_account") else False,
                "apple_watch_connected": bool(profile.get("apple_watch_connected")),
                "huawei_connected": bool(profile.get("huawei_connected")),
                "huawei_account": profile.get("huawei_account"),
                "suunto_connected": bool(profile.get("suunto_connected")),
                "suunto_account": profile.get("suunto_account"),
                "suunto_last_sync_at": profile.get("suunto_last_sync_at"),
                "resting_heart_rate": profile.get("resting_heart_rate"),
                "max_heart_rate": profile.get("max_heart_rate"),
                "vo2max": profile.get("vo2max"),
                "hide_gps_route": bool(profile.get("hide_gps_route")),
                "hide_biometrics": bool(profile.get("hide_biometrics")),
                "canova_critique_visibility": LocalStore.normalize_canova_critique_visibility(
                    profile.get("canova_critique_visibility")
                ),
                "canova_critique_club_ids": LocalStore.parse_canova_critique_club_ids(
                    profile.get("canova_critique_club_ids")
                ),
                "is_coach_or_owner": LocalStore.is_user_coach_or_owner(eff_uid),
            },
            "vdot": current_vdot,
            "fitness_form": fitness_form,
            "progress": {
                "current_month_km": current_km,
                "target_month_km": target_km,
                "progress_pct": progress_pct,
                "remaining_km": remaining_km,
                "days_left_in_month": days_left,
                "daily_required_km": daily_req,
            },
            "goal": goal,
            "weekly_progress": weekly_progress,
            "today_workout": weekly_progress.get("today_workout") if weekly_progress else None,
            "monthly_trend": monthly_trend,
            "yearly_stats": yearly_stats,
            "current_month_activities": formatted_month_acts,
            "current_month_info": {
                "year": today.year,
                "month": today.month,
                "month_label": f"{today.year}年{today.month}月",
                "total_count": len(formatted_month_acts),
                "total_km": round(sum(a["distance_km"] for a in formatted_month_acts), 1),
            },
            "recent_activities": recent_activities,
            "today_health": today_health,
            "recovery_data_availability": recovery_avail,
            "club_feed_summary": LocalStore.get_user_club_feed_summary(eff_uid),
            "ai_coach_tip": (
                recovery_avail.get("user_warning")
                if recovery_avail.get("night_wear_missing")
                else "保持耐心，专注有氧节奏构建，专项能力水到渠成。"
            )
        }
    except Exception as e:
        logger.error(f"[miniapp] Error compiling dashboard: {e}")
        today = LocalStore.get_beijing_today()
        iso_year, iso_week, _ = today.isocalendar()
        return {
            "user": {
                "id": uid,
                "display_name": "跑者",
                "avatar_url": None,
                "garmin_connected": False,
                "garmin_email": None,
                "garmin_last_sync_at": None,
                "garmin_domain": "garmin.com",
                "coros_connected": False,
                "coros_account": None,
                "coros_domain": "teamcnapi.coros.com",
                "coros_last_sync_at": None,
                "apple_watch_connected": False,
                "huawei_connected": False,
                "huawei_account": None,
                "suunto_connected": False,
                "suunto_account": None,
                "suunto_last_sync_at": None,
                "resting_heart_rate": None,
                "max_heart_rate": None,
                "vo2max": None,
            },
            "progress": {
                "current_month_km": 0.0,
                "target_month_km": 200.0,
                "progress_pct": 0.0,
                "remaining_km": 200.0,
                "days_left_in_month": 14,
                "daily_required_km": 0.0,
            },
            "weekly_progress": {
                "week_number": iso_week,
                "week_label": f"第{iso_week}周",
                "week_start": "",
                "week_end": "",
                "current_week_km": 0.0,
                "target_week_km": 50.0,
                "total_runs": 0,
                "progress_pct": 0.0,
                "remaining_km": 50.0,
                "days_left_in_week": 7,
                "daily_required_km": 7.1,
                "daily_breakdown": []
            },
            "monthly_trend": {
                "trend": [],
                "current_month_km": 0.0,
                "prev_month_km": 0.0,
                "pct_change": 0.0,
                "recent_3_months": []
            },
            "yearly_stats": {
                "year": today.year,
                "total_km": 0.0,
                "total_runs": 0,
                "avg_monthly_km": 0.0,
                "projected_year_km": 0.0,
                "target_year_km": 2400.0,
                "progress_pct": 0.0,
                "best_month": {
                    "name": f"{today.month}月",
                    "distance_km": 0.0,
                    "avg_pace": "—"
                }
            },
            "recent_activities": [],
            "today_health": None,
            "ai_coach_tip": "欢迎使用 RGM 跑团助手！请在【我的】页面绑定佳明设备以开启全自动化训练分析。"
        }

@router.get("/activities/{uid}")
def get_miniapp_activities(
    uid: str,
    limit: int = 50,
    viewer_uid: Optional[str] = Query(None, description="Viewer user ID"),
    request: Request = None,
) -> Dict[str, Any]:
    """Returns activity list for activities tab in mini program."""
    eff_viewer = (
        viewer_uid
        if isinstance(viewer_uid, str) and viewer_uid.strip()
        else (
            (request.headers.get("x-user-id") if request else None)
            or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
        )
    )
    if eff_viewer and not LocalStore.can_view_specific_workout_records(eff_viewer, uid):
        raise HTTPException(
            status_code=403,
            detail="不在同一跑团的用户之间仅可查看基本状态，不能相互查看具体的运动记录",
        )
    eff_uid = uid
    canon_uid = LocalStore.resolve_user_id(uid)
    resolved_viewer = LocalStore.resolve_user_id(str(eff_viewer).strip()) if eff_viewer else None
    is_cross_viewer = bool(resolved_viewer and resolved_viewer != canon_uid)
    owner_prof_acts = (LocalStore.get_profile(canon_uid) or {}) if is_cross_viewer else {}
    act_privacy_cache: Dict[str, Dict[str, Any]] = {canon_uid: owner_prof_acts} if owner_prof_acts else {}
    hide_bio_viewer = (
        is_cross_viewer
        and bool(owner_prof_acts.get("hide_biometrics"))
        and not LocalStore.can_view_confidential_runner_data(resolved_viewer, canon_uid)
    )
    acts = LocalStore.get_recent_activities(eff_uid, limit=limit)
    formatted = []
    for a in acts:
        dist_m = float(a.get("distance_meters") or 0)
        has_gps = bool(
            a.get("gps_track_data")
            or a.get("map_image_url")
            or (
                str(a.get("id")).startswith(("garmin_", "coros_"))
                and (LocalStore.is_running_activity(a.get("sport_type")) or a.get("sport_type") in ["Ride", "Hike", "Walk"])
            )
        )
        if is_cross_viewer:
            filtered_j, j_hidden = LocalStore.filter_canova_critique_for_viewer(
                a.get("ai_journal"),
                viewer_uid=resolved_viewer,
                target_uid=canon_uid,
                profile_cache=act_privacy_cache,
            )
        else:
            filtered_j, j_hidden = a.get("ai_journal"), False
        formatted.append({
            "id": a["id"],
            "name": a["name"],
            "start_time": a["start_time"],
            "distance_meters": dist_m,
            "distance_km": round(dist_m / 1000.0, 2),
            "moving_time_seconds": a.get("moving_time_seconds") or 0,
            "avg_pace_str": a.get("avg_pace_str") or "—",
            "average_heartrate": None if hide_bio_viewer else a.get("average_heartrate"),
            "elevation_gain_meters": round(float(a.get("elevation_gain_meters") or a.get("total_elevation_gain") or 0), 1),
            "trimp": None if hide_bio_viewer else a.get("trimp"),
            "workout_effective_vdot": a.get("workout_effective_vdot"),
            "exclude_mode": a.get("exclude_mode") or "normal",
            "ai_journal": filtered_j,
            "is_critique_hidden": j_hidden,
            "has_gps_track": has_gps,
            "map_image_url": a.get("map_image_url")
        })
    return {"activities": formatted}


@router.get("/activities/month/{uid}")
def get_user_month_activities(
    uid: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    viewer_uid: Optional[str] = Query(None, description="Viewer user ID"),
    request: Request = None,
) -> Dict[str, Any]:
    """Returns all running activities for a specific month with summary statistics."""
    eff_viewer = (
        viewer_uid
        if isinstance(viewer_uid, str) and viewer_uid.strip()
        else (
            (request.headers.get("x-user-id") if request else None)
            or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
        )
    )
    if eff_viewer and not LocalStore.can_view_specific_workout_records(eff_viewer, uid):
        raise HTTPException(
            status_code=403,
            detail="不在同一跑团的用户之间仅可查看基本状态，不能相互查看具体的运动记录",
        )
    eff_uid = LocalStore.resolve_user_id(uid)
    resolved_viewer = LocalStore.resolve_user_id(str(eff_viewer).strip()) if eff_viewer else None
    is_cross_viewer = bool(resolved_viewer and resolved_viewer != eff_uid)
    owner_prof_m = (LocalStore.get_profile(eff_uid) or {}) if is_cross_viewer else {}
    month_privacy_cache: Dict[str, Dict[str, Any]] = {eff_uid: owner_prof_m} if owner_prof_m else {}
    hide_bio_viewer = (
        is_cross_viewer
        and bool(owner_prof_m.get("hide_biometrics"))
        and not LocalStore.can_view_confidential_runner_data(resolved_viewer, eff_uid)
    )
    today = LocalStore.get_beijing_today()
    target_year = year or today.year
    target_month = month or today.month

    acts = LocalStore.get_month_activities(eff_uid, target_year, target_month)
    formatted = []
    total_meters = 0.0
    for a in acts:
        if not LocalStore.is_running_activity(a.get("sport_type")):
            continue
        dist_m = float(a.get("distance_meters") or 0)
        total_meters += dist_m
        dist_km = round(dist_m / 1000.0, 2)
        has_gps = bool(
            a.get("gps_track_data")
            or a.get("map_image_url")
            or (
                str(a.get("id")).startswith(("garmin_", "coros_"))
                and (LocalStore.is_running_activity(a.get("sport_type")) or a.get("sport_type") in ["Ride", "Hike", "Walk"])
            )
        )
        if is_cross_viewer:
            filtered_j, j_hidden = LocalStore.filter_canova_critique_for_viewer(
                a.get("ai_journal"),
                viewer_uid=resolved_viewer,
                target_uid=eff_uid,
                profile_cache=month_privacy_cache,
            )
        else:
            filtered_j, j_hidden = a.get("ai_journal"), False
        formatted.append({
            "id": a["id"],
            "name": a["name"],
            "start_time": a["start_time"],
            "distance_meters": dist_m,
            "distance_km": dist_km,
            "moving_time_seconds": a.get("moving_time_seconds") or 0,
            "avg_pace_str": a.get("avg_pace_str") or "—",
            "average_heartrate": None if hide_bio_viewer else a.get("average_heartrate"),
            "elevation_gain_meters": round(float(a.get("elevation_gain_meters") or a.get("total_elevation_gain") or 0), 1),
            "trimp": None if hide_bio_viewer else a.get("trimp"),
            "workout_effective_vdot": a.get("workout_effective_vdot"),
            "exclude_mode": a.get("exclude_mode") or "normal",
            "ai_journal": filtered_j,
            "is_critique_hidden": j_hidden,
            "has_gps_track": has_gps,
            "map_image_url": a.get("map_image_url")
        })

    return {
        "year": target_year,
        "month": target_month,
        "month_label": f"{target_year}年{target_month}月",
        "total_count": len(formatted),
        "total_km": round(total_meters / 1000.0, 1),
        "activities": formatted
    }


@router.get("/activities/{act_id}/track")
def get_activity_track(
    act_id: str,
    request: Request = None,
    uid: Optional[str] = Query(None, description="Viewer user ID"),
    viewer_uid: Optional[str] = Query(None, description="Viewer user ID alias")
) -> Dict[str, Any]:
    """
    Returns GPS track polyline coordinates (GCJ-02), bounds, elevation profile, and structured
    Workout / Preset-Race Segment Diagnosis (`segment_analysis`) for an activity.
    Automatically fetches and caches granular telemetry + splits on-the-fly for Garmin and COROS
    (via COROS Web Training Hub, zero mobile kickout).
    Enforces strict confidentiality: Self / Mentor (师傅) / Coach (教练) always see segment_analysis;
    if hide_gps_route or hide_biometrics is enabled, other viewers cannot see segment_analysis.
    """
    try:
        track_row = LocalStore.get_activity_gps_track(act_id)
        if not track_row:
            raise HTTPException(status_code=404, detail="运动记录不存在")

        raw_viewer = (
            viewer_uid
            if isinstance(viewer_uid, str) and viewer_uid.strip()
            else (
                uid
                if isinstance(uid, str) and uid.strip()
                else (
                    (request.headers.get("x-user-id") if request else None)
                    or getattr(getattr(request, "state", None), "user_id", None)
                    or ""
                )
            )
        )
        eff_viewer = str(raw_viewer).strip() or None
        owner_uid = track_row.get("user_id")
        if eff_viewer and owner_uid and not LocalStore.can_view_specific_workout_records(eff_viewer, owner_uid):
            raise HTTPException(
                status_code=403,
                detail="不在同一跑团的用户之间仅可查看基本状态，不能相互查看具体运动记录与轨迹",
            )
        owner_prof = (LocalStore.get_profile(owner_uid) or {}) if owner_uid else {}

        hide_gps = bool(owner_prof.get("hide_gps_route"))
        hide_bio = bool(owner_prof.get("hide_biometrics"))
        has_privacy_hide = hide_gps or hide_bio
        can_view = (
            LocalStore.can_view_confidential_runner_data(eff_viewer, owner_uid)
            if (owner_uid and eff_viewer)
            else False
        )

        is_gps_hidden = bool(hide_gps and not can_view)
        is_bio_hidden = bool(hide_bio and not can_view)
        is_segment_hidden = bool(has_privacy_hide and not can_view)

        track_data = track_row.get("gps_track_data")
        if isinstance(track_data, str):
            try:
                track_data = json.loads(track_data)
            except Exception:
                track_data = None

        cached_seg = track_row.get("segment_analysis_json")
        if isinstance(cached_seg, str):
            try:
                cached_seg = json.loads(cached_seg)
            except Exception:
                cached_seg = None

        def _has_nonempty_json_items(raw_val: Any) -> bool:
            if isinstance(raw_val, list):
                return len(raw_val) >= 2
            if isinstance(raw_val, str) and raw_val.strip() not in ("", "[]", "null"):
                try:
                    parsed_v = json.loads(raw_val)
                    return isinstance(parsed_v, list) and len(parsed_v) >= 2
                except Exception:
                    return False
            return False

        # Determine if we should fetch granular detail on-demand from Garmin or COROS Web Hub
        has_granular_in_track = bool(
            isinstance(track_data, dict)
            and (track_data.get("laps") or track_data.get("km_splits") or track_data.get("telemetry_series"))
        )
        has_laps_col = _has_nonempty_json_items(track_row.get("laps_data"))
        need_detail_fetch = (not is_gps_hidden or not is_segment_hidden) and (
            not track_data or (not has_granular_in_track and not has_laps_col and not (isinstance(cached_seg, dict) and cached_seg.get("has_granular_splits")))
        )

        if need_detail_fetch and owner_uid:
            user = owner_prof or LocalStore.get_profile(owner_uid) or {}
            act_id_str = str(act_id)
            if act_id_str.startswith("garmin_") and user.get("garmin_connected") and user.get("garmin_encrypted_password"):
                try:
                    pwd = decrypt_string(user["garmin_encrypted_password"])
                    domain = user.get("garmin_domain") or "garmin.cn"
                    adapter = GarminAdapter(user["garmin_email"], pwd, domain=domain)
                    fetched_track = adapter.fetch_activity_gps_track(act_id_str)
                    if fetched_track:
                        track_data = fetched_track
                        laps_list = fetched_track.get("laps")
                        LocalStore.save_activity_streams(
                            act_id_str,
                            user_id=owner_uid,
                            gps_track_data=fetched_track,
                            laps_data=laps_list if laps_list else None,
                            splits_data=laps_list if laps_list else None,
                        )
                        logger.info(f"[miniapp] Cached fetched Garmin detail+track for {act_id_str}")
                except Exception as fe:
                    logger.warning(f"[miniapp] On-demand Garmin detail fetch failed for {act_id_str}: {fe}")
            elif act_id_str.startswith("coros_") and user.get("coros_connected") and user.get("coros_encrypted_password"):
                try:
                    pwd = decrypt_string(user["coros_encrypted_password"])
                    account = user.get("coros_account") or ""
                    domain = user.get("coros_domain") or "teamcnapi.coros.com"
                    if pwd and account:
                        c_adapter = CorosAdapter(account=account, password=pwd, domain=domain)
                        fetched_track = c_adapter.fetch_activity_gps_track(act_id_str)
                        if fetched_track:
                            track_data = fetched_track
                            laps_list = fetched_track.get("laps")
                            splits_list = fetched_track.get("km_splits")
                            LocalStore.save_activity_streams(
                                act_id_str,
                                user_id=owner_uid,
                                gps_track_data=fetched_track,
                                laps_data=laps_list if laps_list else None,
                                splits_data=splits_list if splits_list else None,
                            )
                            logger.info(f"[miniapp] Cached fetched COROS Web detail+track for {act_id_str}")
                except Exception as cfe:
                    logger.warning(f"[miniapp] On-demand COROS detail fetch failed for {act_id_str}: {cfe}")

        # Compute & cache segment_analysis for running activities (when authorized to view)
        segment_analysis = None
        raw_journal = track_row.get("ai_journal")
        if not is_segment_hidden and LocalStore.is_running_activity(track_row.get("sport_type")):
            segment_analysis = LocalStore.compute_and_cache_segment_analysis(
                act_id, track_override=track_data if isinstance(track_data, dict) else None
            )
            if isinstance(segment_analysis, dict) and segment_analysis.get("updated_ai_journal"):
                raw_journal = segment_analysis["updated_ai_journal"]

        crit_cache: Dict[str, Dict[str, Any]] = {owner_uid: owner_prof} if owner_uid else {}
        ai_journal_out, is_critique_hidden = LocalStore.filter_canova_critique_for_viewer(
            raw_journal,
            viewer_uid=eff_viewer,
            target_uid=owner_uid,
            profile_cache=crit_cache,
        )

        segment_analysis_out = None
        if not is_segment_hidden and isinstance(segment_analysis, dict):
            segment_analysis_out = dict(segment_analysis)
            if is_critique_hidden:
                segment_analysis_out["concise_critique"] = None
                segment_analysis_out["coach_advice"] = None
                if "updated_ai_journal" in segment_analysis_out:
                    segment_analysis_out["updated_ai_journal"] = None
            elif is_bio_hidden:
                if segment_analysis_out.get("concise_critique"):
                    segment_analysis_out["concise_critique"] = LocalStore.sanitize_canova_critique_biometrics(
                        segment_analysis_out["concise_critique"]
                    )
                if segment_analysis_out.get("coach_advice"):
                    segment_analysis_out["coach_advice"] = LocalStore.sanitize_canova_critique_biometrics(
                        segment_analysis_out["coach_advice"]
                    )
                if segment_analysis_out.get("updated_ai_journal"):
                    segment_analysis_out["updated_ai_journal"] = LocalStore.sanitize_canova_critique_biometrics(
                        segment_analysis_out["updated_ai_journal"]
                    )

        dist_m = float(track_row.get("distance_meters") or 0)
        act_payload = {
            "id": track_row["id"],
            "name": track_row.get("name"),
            "sport_type": track_row.get("sport_type"),
            "start_time": track_row.get("start_time"),
            "distance_meters": dist_m,
            "distance_km": round(dist_m / 1000.0, 2),
            "moving_time_seconds": track_row.get("moving_time_seconds") or 0,
            "elevation_gain_meters": track_row.get("elevation_gain_meters"),
            "avg_pace_str": track_row.get("avg_pace_str"),
            "average_heartrate": None if is_bio_hidden else track_row.get("average_heartrate"),
            "ai_journal": ai_journal_out,
            "is_critique_hidden": is_critique_hidden,
        }

        if is_gps_hidden:
            return {
                "success": True,
                "is_gps_hidden": True,
                "is_biometrics_hidden": is_bio_hidden,
                "is_segment_hidden": is_segment_hidden,
                "is_critique_hidden": is_critique_hidden,
                "has_track": False,
                "track": None,
                "has_segment_analysis": False,
                "segment_analysis": None,
                "map_image_url": None,
                "message": "该跑者已将运动轨迹与分段诊断设为保密（仅本人、师傅及教练可见）",
                "activity": act_payload,
            }

        # Prepare sanitized public track payload (strip heavy telemetry_series; scrub HR if is_bio_hidden)
        public_track = None
        has_gps_points = False
        if isinstance(track_data, dict):
            pts = track_data.get("points") or []
            has_gps_points = len(pts) >= 2
            if has_gps_points:
                try:
                    from utils.geo_utils import smooth_sparse_stadium_track
                    pts = smooth_sparse_stadium_track(pts, max_output_points=900)
                except Exception:
                    pass
                elev_prof = track_data.get("elevation_profile") or []
                if is_bio_hidden and elev_prof:
                    elev_prof = [{k: v for k, v in ep.items() if k != "hr"} for ep in elev_prof if isinstance(ep, dict)]
                public_track = {
                    "activity_id": track_data.get("activity_id") or act_id,
                    "total_points": track_data.get("total_points") or len(pts),
                    "original_point_count": track_data.get("original_point_count") or len(pts),
                    "center": track_data.get("center"),
                    "bounds": track_data.get("bounds"),
                    "start_point": track_data.get("start_point") or pts[0],
                    "end_point": track_data.get("end_point") or pts[-1],
                    "points": pts,
                    "elevation_profile": elev_prof,
                }

        return {
            "success": True,
            "is_gps_hidden": False,
            "is_biometrics_hidden": is_bio_hidden,
            "is_segment_hidden": is_segment_hidden,
            "is_critique_hidden": is_critique_hidden,
            "activity": act_payload,
            "has_track": has_gps_points,
            "track": public_track,
            "has_segment_analysis": bool(segment_analysis_out) and not is_segment_hidden,
            "segment_analysis": None if is_segment_hidden else segment_analysis_out,
            "segment_hidden_message": "该跑者已开启运动隐私保护，分段诊断仅对本人、师傅及教练开放" if is_segment_hidden else None,
            "map_image_url": track_row.get("map_image_url"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[miniapp] Error getting activity track for {act_id}: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"获取轨迹失败: {str(e)}"
        }


class SupportTicketCreateRequest(BaseModel):
    uid: Optional[str] = None
    user_id: Optional[str] = None
    category: Optional[str] = "device_sync"
    content: str
    contact_info: Optional[str] = None
    client_env: Optional[str] = "mp-weixin"
    device_info: Optional[Dict[str, Any]] = None


@router.post("/support/tickets")
def create_miniapp_support_ticket(req: SupportTicketCreateRequest):
    """
    Creates a user technical support / feedback ticket with automatic diagnostic context
    (UID, connected watch status, joined clubs, activity count).
    """
    from utils.local_store import LocalStore

    target_uid = (req.uid or req.user_id or "").strip()
    if not target_uid:
        raise HTTPException(status_code=400, detail="缺少用户标识")
    if not req.content or len(req.content.strip()) < 2:
        raise HTTPException(status_code=400, detail="请填写问题或反馈内容（至少 2 个字）")

    ticket = LocalStore.create_support_ticket(
        user_id=target_uid,
        category=(req.category or "device_sync").strip(),
        content=req.content.strip(),
        contact_info=req.contact_info,
        client_env=req.client_env,
        device_info=req.device_info,
    )
    return {
        "success": True,
        "ticket": ticket,
        "message": "反馈已提交！已自动附带您的设备与账号诊断信息，管理员将在后台尽快为您核查回复。",
    }


@router.get("/support/tickets")
def list_miniapp_support_tickets(
    uid: Optional[str] = Query(None, description="User ID"),
    user_id: Optional[str] = Query(None, description="User ID alias"),
):
    """
    Returns the user's submitted support tickets and any administrator replies.
    """
    from utils.local_store import LocalStore

    target_uid = (uid or user_id or "").strip()
    if not target_uid:
        return {"tickets": []}
    tickets = LocalStore.get_user_support_tickets(target_uid)
    return {"tickets": tickets}


class FaceFocusDetectRequest(BaseModel):
    image_base64: str


def _detect_photo_face_focus(img_bytes: bytes) -> Dict[str, Any]:
    """
    Detects the primary runner's face / head center (focus_x, focus_y in [0.0, 1.0])
    using OpenCV Haar cascades (frontalface, profileface, upperbody) with a smart
    portrait head-zone fallback so the runner's face is never cropped off.
    """
    if not img_bytes or len(img_bytes) < 100:
        return {"face_detected": False, "focus_x": 0.5, "focus_y": 0.20, "width": 0, "height": 0}
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None or img.size == 0:
            return {"face_detected": False, "focus_x": 0.5, "focus_y": 0.20, "width": 0, "height": 0}

        orig_h, orig_w = img.shape[:2]
        max_dim = 640
        scale = min(1.0, float(max_dim) / float(max(orig_h, orig_w)))
        if scale < 1.0:
            work_img = cv2.resize(img, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_AREA)
        else:
            work_img = img

        wh, ww = work_img.shape[:2]
        gray = cv2.cvtColor(work_img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        cascade_names = [
            "haarcascade_frontalface_default.xml",
            "haarcascade_frontalface_alt2.xml",
            "haarcascade_profileface.xml",
        ]

        best_box = None
        for cname in cascade_names:
            cpath = cv2.data.haarcascades + cname
            detector = cv2.CascadeClassifier(cpath)
            if detector.empty():
                continue
            min_s = max(24, int(min(ww, wh) * 0.06))
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(min_s, min_s),
            )
            if faces is not None and len(faces) > 0:
                # Score faces by area and proximity to upper-center (where the main runner's head usually is)
                def _face_score(box):
                    bx, by, bw, bh = box
                    cx = (bx + bw / 2.0) / float(ww)
                    cy = (by + bh / 2.0) / float(wh)
                    area_ratio = (bw * bh) / float(ww * wh)
                    center_bias = 1.0 - 0.6 * abs(cx - 0.5) - 0.4 * max(0.0, cy - 0.55)
                    return area_ratio * max(0.2, center_bias)

                best_box = max(faces, key=_face_score)
                break

        if best_box is not None:
            bx, by, bw, bh = best_box
            fx = round(float(bx + bw / 2.0) / float(ww), 3)
            fy = round(float(by + bh / 2.0) / float(wh), 3)
            return {
                "face_detected": True,
                "focus_x": max(0.08, min(0.92, fx)),
                "focus_y": max(0.08, min(0.85, fy)),
                "width": orig_w,
                "height": orig_h,
            }

        # Fallback: try upperbody cascade or skin-tone cluster in upper 55% of portrait image
        ub_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_upperbody.xml")
        if not ub_detector.empty():
            min_ub = max(40, int(min(ww, wh) * 0.12))
            ubs = ub_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(min_ub, min_ub))
            if ubs is not None and len(ubs) > 0:
                bx, by, bw, bh = max(ubs, key=lambda b: b[2] * b[3])
                # Head is in the upper 35% of the upperbody box
                fx = round(float(bx + bw / 2.0) / float(ww), 3)
                fy = round(float(by + bh * 0.32) / float(wh), 3)
                return {
                    "face_detected": True,
                    "focus_x": max(0.08, min(0.92, fx)),
                    "focus_y": max(0.08, min(0.85, fy)),
                    "width": orig_w,
                    "height": orig_h,
                }

        # Smart portrait head-priority fallback (prevents cutting off head on vertical running photos)
        default_fy = 0.18 if orig_h > orig_w else 0.30
        return {
            "face_detected": False,
            "focus_x": 0.5,
            "focus_y": default_fy,
            "width": orig_w,
            "height": orig_h,
        }
    except Exception as e:
        logger.warning(f"[miniapp] Face focus detection warning: {e}")
        return {"face_detected": False, "focus_x": 0.5, "focus_y": 0.18, "width": 0, "height": 0}


@router.post("/detect-face-focus")
def detect_face_focus_endpoint(req: FaceFocusDetectRequest) -> Dict[str, Any]:
    """
    Detects face center coordinates (focus_x, focus_y in [0.0, 1.0]) from a base64 image
    so the share card canvas can automatically center the runner's face.
    """
    import base64

    raw_b64 = (req.image_base64 or "").strip()
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(raw_b64)
    except Exception:
        return {"success": False, "face_detected": False, "focus_x": 0.5, "focus_y": 0.18}

    res = _detect_photo_face_focus(img_bytes)
    return {"success": True, **res}


@router.get("/personal-share-card/{uid}")
def get_personal_share_card_data(
    uid: str,
    request: Request = None,
    activity_id: Optional[str] = Query(None, description="Optional specific activity ID"),
    race_id: Optional[str] = Query(None, description="Optional completed race ID or name"),
    target_date: Optional[str] = Query(None, description="Optional YYYY-MM-DD date"),
    club_id: Optional[str] = Query(None, description="Optional preferred club ID for invite QR"),
    viewer_uid: Optional[str] = Query(None, description="Optional viewer user ID"),
    env_version: Optional[str] = Query("release", description="WeChat QR code env_version"),
) -> Dict[str, Any]:
    """
    Bundles all data needed for the Personal Moments Share Card (个人分享朋友圈卡片)
    for BOTH Daily Workouts (日常训练打卡) and Completed Races (已完赛赛事纪念战报):
    1. Today's Plan OR Race Target (当天计划 / 赛事目标)
    2. Actual Completed Running / Race Data (实际完成的数据)
    3. Canova Coach's Commentary (Canova 教练的点评 - multiple tactical perspectives)
    4. GPS Route Polyline & Elevation Profile for Photo Overlay (地图轨迹与海拔剖面叠加数据)
    5. Official WeChat Invitation QR Code Base64 (邀请二维码) + Auto Face Focus for saved race photos
    """
    import os
    import base64
    import hashlib
    import math
    import requests as ext_req
    from utils.wechat import wechat_client

    eff_uid = LocalStore.resolve_user_id(uid)
    profile = LocalStore.get_profile(eff_uid) or {}
    today_iso = LocalStore.get_beijing_today().isoformat()
    avatar_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
    race_photos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "race_photos")
    os.makedirs(avatar_dir, exist_ok=True)

    def _resolve_img_bytes(img_url: Optional[str]) -> bytes:
        if not img_url:
            return b""
        u = img_url.strip()
        if "/api/avatars/" in u:
            fname = os.path.basename(u.split("?")[0])
            local_p = os.path.join(avatar_dir, fname)
            if os.path.exists(local_p) and os.path.getsize(local_p) > 200:
                with open(local_p, "rb") as f:
                    return f.read()
        if "/api/race-photos/" in u:
            fname = os.path.basename(u.split("?")[0])
            local_rp = os.path.join(race_photos_dir, fname)
            if os.path.exists(local_rp) and os.path.getsize(local_rp) > 200:
                with open(local_rp, "rb") as f:
                    return f.read()
        if u.startswith("http") and is_safe_external_url(u):
            cache_name = f"poster_cache_{hashlib.md5(u.encode('utf-8')).hexdigest()[:16]}.jpg"
            cache_p = os.path.join(avatar_dir, cache_name)
            if not os.path.exists(cache_p) or os.path.getsize(cache_p) < 200:
                try:
                    r = ext_req.get(u, timeout=5, allow_redirects=False)
                    if r.status_code == 200 and 200 < len(r.content) <= 10 * 1024 * 1024:
                        with open(cache_p, "wb") as f:
                            f.write(r.content)
                except Exception:
                    pass
            if os.path.exists(cache_p) and os.path.getsize(cache_p) > 200:
                with open(cache_p, "rb") as f:
                    return f.read()
        return b""

    def _resolve_img_b64(img_url: Optional[str]) -> str:
        raw = _resolve_img_bytes(img_url)
        return base64.b64encode(raw).decode("ascii") if raw else ""

    # 1. Fetch recent running activities & completed races
    all_recent = LocalStore.get_recent_activities(eff_uid, limit=50)
    run_acts = [a for a in all_recent if LocalStore.is_running_activity(a.get("sport_type"))]
    if not run_acts and all_recent:
        run_acts = all_recent[:10]

    all_races = LocalStore.get_race_plans(eff_uid) or []
    completed_races_list = [
        r for r in all_races if r.get("is_completed") or r.get("status") == "completed" or bool(r.get("finish_time"))
    ]

    selected_race: Optional[Dict[str, Any]] = None
    if race_id:
        for r in all_races:
            if str(r.get("id")) == str(race_id) or str(r.get("name")) == str(race_id):
                selected_race = r
                break

    card_mode = "race" if selected_race else "workout"

    selected_act: Optional[Dict[str, Any]] = None
    if selected_race:
        r_date = str(selected_race.get("race_date") or "")[:10]
        r_info = selected_race.get("race_info") or {}
        r_type_str = str(selected_race.get("race_type") or "")
        if r_info.get("race_distance_km"):
            expected_km = float(r_info["race_distance_km"])
        elif "全马" in r_type_str or "Full" in r_type_str:
            expected_km = 42.195
        elif "半马" in r_type_str or "Half" in r_type_str:
            expected_km = 21.0975
        elif "10" in r_type_str:
            expected_km = 10.0
        elif "5" in r_type_str:
            expected_km = 5.0
        else:
            expected_km = 21.0

        matched = LocalStore.find_matched_activity_for_race(
            eff_uid, r_date, min_distance_km=max(3.0, expected_km * 0.5)
        )
        if not matched and r_date:
            matched = LocalStore.find_matched_activity_for_race(eff_uid, r_date, min_distance_km=1.0)
        if matched and matched.get("id"):
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM activities WHERE id = ?", (matched["id"],))
                row = c.fetchone()
                if row:
                    selected_act = dict(row)
    else:
        if activity_id:
            for a in run_acts:
                if str(a.get("id")) == str(activity_id):
                    selected_act = a
                    break
            if not selected_act:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    c.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
                    row = c.fetchone()
                    if row:
                        selected_act = dict(row)
                        act_owner_uid = selected_act.get("user_id")
                        if act_owner_uid:
                            resolved_owner = LocalStore.resolve_user_id(str(act_owner_uid))
                            if resolved_owner and resolved_owner != eff_uid:
                                eff_uid = resolved_owner
                                profile = LocalStore.get_profile(eff_uid) or profile

        if not selected_act and target_date:
            for a in run_acts:
                if str(a.get("start_time") or "")[:10] == target_date[:10]:
                    selected_act = a
                    break

        if not selected_act and run_acts:
            for a in run_acts:
                if str(a.get("start_time") or "")[:10] == today_iso:
                    selected_act = a
                    break
            if not selected_act:
                selected_act = run_acts[0]

    eff_date = (
        str(selected_race.get("race_date") or "")[:10]
        if selected_race
        else (
            target_date[:10]
            if target_date
            else (str(selected_act.get("start_time") or "")[:10] if selected_act else today_iso)
        )
    )
    if not eff_date:
        eff_date = today_iso

    # 2. Resolve Day Plan OR Race Target
    goal = LocalStore.get_goal(eff_uid)
    weekly_target = float(goal.get("current_week_target") or goal.get("weekly_target") or 50.0)
    fallback_daily_km = round(max(5.0, min(16.0, weekly_target / 5.0)), 1)

    default_photo_b64 = ""
    default_photo_focus = {"face_detected": False, "focus_x": 0.5, "focus_y": 0.18, "width": 0, "height": 0}
    race_photos_list: List[str] = []

    if selected_race:
        r_info = selected_race.get("race_info") or {}
        r_type_str = str(selected_race.get("race_type") or "马拉松")
        if r_info.get("race_distance_km"):
            r_target_km = float(r_info["race_distance_km"])
        elif "全马" in r_type_str or "Full" in r_type_str:
            r_target_km = 42.2
        elif "半马" in r_type_str or "Half" in r_type_str:
            r_target_km = 21.1
        elif "10" in r_type_str:
            r_target_km = 10.0
        elif "5" in r_type_str:
            r_target_km = 5.0
        elif selected_act:
            r_target_km = round(float(selected_act.get("distance_meters") or 0) / 1000.0, 1) or 21.1
        else:
            r_target_km = 42.2

        pri_raw = str(selected_race.get("priority") or "1")
        pri_label = "A标核心赛" if pri_raw in ("1", "A") else ("B标以赛代练" if pri_raw in ("2", "B") else "C标拉练赛")
        target_t = selected_race.get("target_time") or "顺利完赛"
        finish_t = selected_race.get("finish_time") or (
            LocalStore.seconds_to_time_str(int(selected_act.get("moving_time_seconds") or 0)) if selected_act else "—"
        )
        perf_badge = selected_race.get("performance_badge") or "顺利完赛 🏅"
        diff_str = selected_race.get("diff_str") or ""

        day_plan = {
            "is_race": True,
            "card_header_label": "🏁 赛前目标",
            "badge_text": perf_badge,
            "has_scheduled_plan": True,
            "date": eff_date,
            "plan_title": selected_race.get("finish_notes") or f"{eff_date} · {selected_race.get('name')} 官方完赛纪念",
            "phase": pri_label,
            "week_title": f"比目标 {diff_str}" if diff_str else "",
            "workout_type": "race",
            "title": f"{selected_race.get('name')} ({r_type_str})",
            "distance_km": round(r_target_km, 1),
            "target_pace": f"目标 {target_t}",
            "target_hr_zone": f"完赛 {finish_t}",
            "description": selected_race.get("finish_notes") or "全力以赴，突破自我！",
            "coach_notes": "",
        }

        # Check saved race photos & run automatic face focus detection on primary race photo
        raw_photos = selected_race.get("photos") or []
        if isinstance(raw_photos, str):
            try:
                raw_photos = json.loads(raw_photos)
            except Exception:
                raw_photos = []
        if selected_race.get("photo_url") and selected_race["photo_url"] not in raw_photos:
            raw_photos = [selected_race["photo_url"]] + list(raw_photos)
        race_photos_list = [p for p in raw_photos if p]
        if race_photos_list:
            p_bytes = _resolve_img_bytes(race_photos_list[0])
            if p_bytes:
                default_photo_b64 = base64.b64encode(p_bytes).decode("ascii")
                default_photo_focus = _detect_photo_face_focus(p_bytes)
    else:
        active_plan = LocalStore.get_user_active_training_plan(eff_uid)
        matched_plan_day: Optional[Dict[str, Any]] = None
        plan_meta = {
            "plan_id": None,
            "plan_title": "Canova 科学耐力周期计划",
            "phase": "有氧基础构建期",
            "week_title": "",
        }
        if active_plan:
            plan_meta["plan_id"] = active_plan.get("id")
            plan_meta["plan_title"] = active_plan.get("title") or "Canova 科学耐力周期计划"
            sched = active_plan.get("schedule_data") or {}
            for w in (sched.get("weeks") or []):
                for d_idx, day in enumerate(w.get("days") or []):
                    if str(day.get("date") or "")[:10] == eff_date:
                        matched_plan_day = day
                        plan_meta["phase"] = w.get("phase") or "专项耐力周期"
                        plan_meta["week_title"] = w.get("week_title") or f"第{w.get('week_index', 1)}周"
                        break
                if matched_plan_day:
                    break

        if matched_plan_day:
            p_dist = float(matched_plan_day.get("distance_km") or 0.0)
            p_type = str(matched_plan_day.get("workout_type") or "easy_run")
            if p_dist <= 0 and selected_act:
                p_title = matched_plan_day.get("title") or "主动恢复与有氧慢跑"
                p_dist = round(float(selected_act.get("distance_meters") or 0) / 1000.0, 1) or fallback_daily_km
                p_pace = matched_plan_day.get("target_pace") or "轻松体感配速"
                p_hr = matched_plan_day.get("target_hr_zone") or "Zone 1-2 (恢复区)"
            else:
                p_title = matched_plan_day.get("title") or "有氧耐力训练"
                p_pace = matched_plan_day.get("target_pace") or "5:30-6:15 /km"
                p_hr = matched_plan_day.get("target_hr_zone") or "Zone 2 (有氧耐力区)"
            clean_hr = str(p_hr).replace("心率：", "").replace("心率:", "").replace("心率", "").strip()
            day_plan = {
                "is_race": False,
                "card_header_label": "📋 当天计划",
                "badge_text": "",
                "has_scheduled_plan": True,
                "date": eff_date,
                "plan_title": plan_meta["plan_title"],
                "phase": plan_meta["phase"],
                "week_title": plan_meta["week_title"],
                "workout_type": p_type,
                "title": p_title,
                "distance_km": round(p_dist, 1),
                "target_pace": p_pace,
                "target_hr_zone": clean_hr,
                "description": matched_plan_day.get("description") or "保持均匀呼吸与稳定步频，专注有氧底座积累。",
                "coach_notes": matched_plan_day.get("coach_notes") or "",
                "feeling_tag": matched_plan_day.get("feeling_tag") or "",
                "rpe": matched_plan_day.get("rpe"),
                "athlete_notes": matched_plan_day.get("athlete_notes") or "",
            }
            # Load runner's uploaded workout check-in photos as default share card photo if present
            raw_w_photos = matched_plan_day.get("workout_photos") or []
            if isinstance(raw_w_photos, str):
                try:
                    raw_w_photos = json.loads(raw_w_photos)
                except Exception:
                    raw_w_photos = []
            if matched_plan_day.get("photo_url") and matched_plan_day["photo_url"] not in raw_w_photos:
                raw_w_photos = [matched_plan_day["photo_url"]] + list(raw_w_photos)
            race_photos_list = [p for p in raw_w_photos if p]
            if race_photos_list:
                p_bytes = _resolve_img_bytes(race_photos_list[0])
                if p_bytes:
                    default_photo_b64 = base64.b64encode(p_bytes).decode("ascii")
                    default_photo_focus = _detect_photo_face_focus(p_bytes)
        else:
            day_plan = {
                "is_race": False,
                "card_header_label": "📋 当天计划",
                "badge_text": "",
                "has_scheduled_plan": False,
                "date": eff_date,
                "plan_title": f"周目标 {weekly_target:.0f}km · 科学耐力打卡",
                "phase": "日常有氧周期",
                "week_title": "",
                "workout_type": "easy_run",
                "title": "有氧耐力基础跑",
                "distance_km": fallback_daily_km,
                "target_pace": "稳态有氧配速",
                "target_hr_zone": "135-155 bpm",
                "description": "依据 Canova 有氧容量原则，以稳定心率完成日常耐力积累。",
                "coach_notes": "",
            }

    # 3. Format Actual Completed Activity / Race Data & GPS/Elevation Overlay
    actual_data: Dict[str, Any] = {
        "has_activity": False,
        "id": "",
        "name": selected_race.get("name") if selected_race else "今日训练待同步",
        "date": eff_date,
        "start_time": eff_date,
        "distance_km": 0.0,
        "moving_time_seconds": 0,
        "duration_str": "00:00",
        "avg_pace_str": "—",
        "average_heartrate": None,
        "max_heartrate": None,
        "average_cadence": None,
        "elevation_gain_meters": 0.0,
        "trimp": 0.0,
        "calories": 0,
        "completion_pct": 0,
    }

    track_overlay: Dict[str, Any] = {
        "has_gps_track": False,
        "has_elevation_profile": False,
        "points": [],
        "elevation_profile": [],
        "min_elev": 0.0,
        "max_elev": 0.0,
        "elevation_gain_m": 0.0,
    }

    raw_caller = (
        getattr(getattr(request, "state", None), "user_id", None)
        or (request.headers.get("x-user-id") if request else None)
        or (viewer_uid if isinstance(viewer_uid, str) and viewer_uid.strip() else None)
    )
    caller_uid = LocalStore.resolve_user_id(str(raw_caller).strip()) if raw_caller else None
    can_view_confidential = (
        LocalStore.can_view_confidential_runner_data(caller_uid, eff_uid)
        if caller_uid
        else False
    )
    is_bio_hidden = bool(profile.get("hide_biometrics")) and not can_view_confidential
    can_view_critique = (
        LocalStore.can_view_canova_critique(caller_uid, eff_uid, club_id=club_id)
        if caller_uid
        else False
    )
    is_critique_hidden = not can_view_critique

    if selected_act:
        act_id = str(selected_act["id"])
        dist_m = float(selected_act.get("distance_meters") or 0.0)
        dist_km = round(dist_m / 1000.0, 2)
        mov_s = int(selected_act.get("moving_time_seconds") or selected_act.get("elapsed_time_seconds") or 0)
        hrs = mov_s // 3600
        mins = (mov_s % 3600) // 60
        secs = mov_s % 60
        dur_str = (
            selected_race.get("finish_time")
            if (selected_race and selected_race.get("finish_time"))
            else (f"{hrs}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}")
        )
        elev_gain = round(float(selected_act.get("elevation_gain_meters") or selected_act.get("total_elevation_gain") or 0.0), 1)
        if selected_race and elev_gain <= 0:
            r_info_elev = (selected_race.get("race_info") or {}).get("elevation_gain_m")
            if r_info_elev:
                elev_gain = round(float(r_info_elev), 1)

        avg_hr = None if is_bio_hidden else selected_act.get("average_heartrate")
        max_hr = None if is_bio_hidden else selected_act.get("max_heartrate")
        trimp_val = round(float(selected_act.get("trimp") or 0.0), 1)
        plan_km = float(day_plan.get("distance_km") or 0.0)
        comp_pct = 100 if selected_race else (int(round((dist_km / plan_km) * 100)) if plan_km > 0 else (100 if dist_km > 0 else 0))

        actual_data = {
            "has_activity": True,
            "id": act_id,
            "name": selected_race.get("name") if selected_race else (selected_act.get("name") or "户外跑步"),
            "date": str(selected_act.get("start_time") or eff_date)[:10],
            "start_time": str(selected_act.get("start_time") or "")[:16].replace("T", " "),
            "distance_km": dist_km,
            "moving_time_seconds": mov_s,
            "duration_str": dur_str,
            "avg_pace_str": (selected_act.get("avg_pace_str") or "—").replace(" /km", "").replace("/km", "").strip(),
            "average_heartrate": int(avg_hr) if avg_hr else None,
            "max_heartrate": int(max_hr) if max_hr else None,
            "average_cadence": selected_act.get("average_cadence"),
            "elevation_gain_meters": elev_gain,
            "trimp": trimp_val,
            "calories": int(selected_act.get("calories") or 0),
            "completion_pct": comp_pct,
        }

        try:
            track_resp = get_activity_track(act_id, request=None, uid=caller_uid or "", viewer_uid=caller_uid or "")
            tr_obj = track_resp.get("track") if isinstance(track_resp, dict) else None
            if isinstance(tr_obj, dict):
                raw_pts = tr_obj.get("points") or []
                if raw_pts and len(raw_pts) >= 2:
                    step = max(1, len(raw_pts) // 150)
                    sampled_pts = raw_pts[::step]
                    if sampled_pts[-1] != raw_pts[-1]:
                        sampled_pts.append(raw_pts[-1])
                    track_overlay["points"] = [
                        {
                            "lat": float(p.get("latitude") or p.get("lat")),
                            "lng": float(p.get("longitude") or p.get("lng") or p.get("lon")),
                        }
                        for p in sampled_pts
                        if (p.get("latitude") or p.get("lat")) is not None
                    ]
                    track_overlay["has_gps_track"] = len(track_overlay["points"]) >= 2

                raw_elev = tr_obj.get("elevation_profile") or []
                if raw_elev and len(raw_elev) >= 2:
                    e_step = max(1, len(raw_elev) // 80)
                    sampled_elev = raw_elev[::e_step]
                    if sampled_elev[-1] != raw_elev[-1]:
                        sampled_elev.append(raw_elev[-1])
                    elev_list = [
                        {
                            "dist_km": round(float(e.get("dist_km") or 0.0), 2),
                            "elevation_m": round(float(e.get("elevation_m") or 0.0), 1),
                        }
                        for e in sampled_elev
                    ]
                    e_vals = [x["elevation_m"] for x in elev_list]
                    track_overlay["elevation_profile"] = elev_list
                    track_overlay["has_elevation_profile"] = True
                    track_overlay["min_elev"] = round(min(e_vals), 1)
                    track_overlay["max_elev"] = round(max(e_vals), 1)
                    track_overlay["elevation_gain_m"] = elev_gain
        except Exception as te:
            logger.warning(f"[miniapp] Share card track load warning for {act_id}: {te}")

    elif selected_race:
        # Completed race without a matched watch activity (manual race entry)
        r_dist_km = float(day_plan.get("distance_km") or 42.2)
        f_time_str = str(selected_race.get("finish_time") or selected_race.get("target_time") or "3:30:00")
        f_secs = LocalStore.time_str_to_seconds(f_time_str) or 12600
        pace_s = int(round(f_secs / max(1.0, r_dist_km)))
        calc_pace = f"{pace_s // 60}:{pace_s % 60:02d}"
        r_info_obj = selected_race.get("race_info") or {}
        r_elev = round(float(r_info_obj.get("elevation_gain_m") or (180.0 if r_dist_km >= 20 else 65.0)), 1)

        actual_data = {
            "has_activity": True,
            "id": str(selected_race.get("id") or "race"),
            "name": selected_race.get("name") or "完赛纪念",
            "date": eff_date,
            "start_time": eff_date,
            "distance_km": r_dist_km,
            "moving_time_seconds": f_secs,
            "duration_str": f_time_str,
            "avg_pace_str": calc_pace,
            "average_heartrate": None if is_bio_hidden else 162,
            "max_heartrate": None if is_bio_hidden else 182,
            "average_cadence": 180,
            "elevation_gain_meters": r_elev,
            "trimp": round(r_dist_km * 4.8, 1),
            "calories": int(r_dist_km * 62),
            "completion_pct": 100,
        }

    # 4. Build Canova Coach Commentary (3 options + default)
    def _clean_ai_terms(txt: str) -> str:
        if not txt:
            return ""
        return (
            txt.replace("AI教练", "Canova 教练")
            .replace("AI 教练", "Canova 教练")
            .replace("人工智能", "科学耐力")
            .replace("AI", "Canova")
            .strip()
        )

    plan_title_short = day_plan["title"]
    plan_km = day_plan["distance_km"]
    act_km = actual_data["distance_km"]
    act_pace = actual_data["avg_pace_str"]
    act_hr = actual_data["average_heartrate"]
    act_elev = actual_data["elevation_gain_meters"]
    comp_pct = actual_data["completion_pct"]

    if selected_race:
        r_name = selected_race.get("name") or "本次赛事"
        t_time = selected_race.get("target_time") or "赛前目标"
        f_time = actual_data["duration_str"]
        diff_s = selected_race.get("diff_seconds")
        diff_label = selected_race.get("diff_str") or ""
        if diff_s is not None and diff_s <= 0:
            race_verdict = f"祝贺在【{r_name}】以 {f_time} 强势完赛，成功达成赛前目标（{t_time}，{diff_label or '精准兑现'}）！"
        else:
            race_verdict = f"祝贺在【{r_name}】以 {f_time} 坚韧冲线（赛前目标 {t_time}），用脚步兑现了整个备赛周期的汗水！"

        commentary_exec = (
            f"{race_verdict}全程 {act_km}km 平均配速 {act_pace}/km"
            f"{f'，平均心率 {act_hr} bpm' if act_hr else ''}"
            f"{f'，克服累计爬升 +{act_elev:.0f}m' if act_elev >= 15 else ''}。"
            f"从 Canova 专项周期视角看，前半程克制稳健、后半程抗衰减能力出色，是一场教科书级的科学实战！"
        )
        commentary_phys = (
            f"【{r_name}】赛后生理与恢复处方：全程 {act_km}km 高强度输出消耗了大量肌糖原并伴随肌纤维微损伤。"
            f"未来 72 小时请执行再生恢复协议（充足睡眠、优质蛋白碳水补充与轻柔泡沫轴放松），建议休整 5~7 天后再开启下一周期有氧慢跑。"
        )
        notes_clean = _clean_ai_terms(str(selected_race.get("finish_notes") or ""))
        commentary_journal = (
            f"跑者完赛感言：“{notes_clean}” —— Canova 教练寄语：每一场完赛都是有氧底座与意志力的勋章，享受属于你的荣耀时刻！"
            if notes_clean
            else commentary_exec
        )
        commentary_options = [
            {"key": "exec", "label": "🏆 完赛目标复盘", "text": commentary_exec},
            {"key": "phys", "label": "❤️ 赛后恢复处方", "text": commentary_phys},
            {"key": "journal", "label": "🏅 完赛感言与致敬", "text": commentary_journal},
        ]
    else:
        exec_label = "📊 计划执行复盘"
        if actual_data["has_activity"]:
            from utils.workout_segmentation import has_large_plan_discrepancy, parse_pace_str_to_sec

            def _extract_journal_text(raw_val: Any) -> str:
                if not raw_val:
                    return ""
                obj = raw_val
                if isinstance(obj, str):
                    s = obj.strip()
                    if s.startswith("{") and s.endswith("}"):
                        try:
                            parsed = json.loads(s)
                            if isinstance(parsed, dict):
                                obj = parsed
                        except Exception:
                            pass
                if isinstance(obj, dict):
                    for k in ("summary", "critique", "coach_comment", "commentary", "content", "text", "verdict"):
                        v = obj.get(k)
                        if isinstance(v, str) and v.strip():
                            return v.strip()
                    return ""
                return str(obj).strip()

            hr_clause = f"，平均心率 {act_hr} bpm" if act_hr else ""
            elev_clause = f"，克服累计爬升 +{act_elev:.0f}m" if act_elev >= 15 else ""
            if act_hr and act_hr <= 148:
                phys_verdict = "心率稳居有氧燃脂与毛细血管扩张甜区，线粒体有氧底座扎实推进。"
            elif act_hr and act_hr <= 165:
                phys_verdict = "心率处于稳态有氧至乳酸阈值过渡区间，专项抗疲劳耐力得到有效刺激。"
            elif act_hr:
                phys_verdict = "高心率输出充分调动了最大摄氧量与神经肌肉募集，跑后需重点做好糖原补充与睡眠恢复。"
            else:
                phys_verdict = "配速输出平稳，步频节奏连贯，很好地贯彻了周期化耐力积累原则。"

            act_pace_sec = parse_pace_str_to_sec(act_pace)
            if act_pace_sec is None and act_km > 0.1 and actual_data.get("moving_time_seconds"):
                p_cand = int(round(float(actual_data["moving_time_seconds"]) / act_km))
                if 90 <= p_cand <= 1200:
                    act_pace_sec = p_cand

            large_discrepancy = True
            if day_plan.get("has_scheduled_plan") and matched_plan_day:
                try:
                    planned_km_val = float(matched_plan_day.get("distance_km") or day_plan.get("distance_km") or 0.0)
                    large_discrepancy = has_large_plan_discrepancy(
                        planned_day=matched_plan_day,
                        activity=selected_act or actual_data,
                        eval_total_km=float(act_km or 0.0),
                        eval_main_km=float(act_km or 0.0),
                        planned_main_km=planned_km_val,
                        eval_pace_sec=act_pace_sec,
                    )
                except Exception as disc_err:
                    logger.warning(f"[miniapp] Plan discrepancy eval fallback for {eff_uid}: {disc_err}")
                    large_discrepancy = False
            if large_discrepancy:
                exec_label = "📊 训练效果复盘"
                if act_km >= 20:
                    effect_intro = f"今日高质量完成 {act_km}km 长距离耐力拉练（平均配速 {act_pace}/km{hr_clause}{elev_clause}）。"
                elif act_km >= 10:
                    effect_intro = f"今日扎实完成 {act_km}km 专项有氧训练（平均配速 {act_pace}/km{hr_clause}{elev_clause}）。"
                else:
                    effect_intro = f"今日完成 {act_km}km 跑步训练（平均配速 {act_pace}/km{hr_clause}{elev_clause}）。"
                commentary_exec = f"{effect_intro}{phys_verdict}"
            else:
                if comp_pct >= 95:
                    exec_verdict = f"今日课目【{plan_title_short}】高质量达成（完成率 {comp_pct}%）！"
                elif comp_pct >= 75:
                    exec_verdict = f"今日课目【{plan_title_short}】稳健完成 {comp_pct}%，训练节奏控制得当。"
                else:
                    exec_verdict = f"今日完成跑量 {act_km}km，根据身体体感灵活调整负荷非常明智。"

                commentary_exec = (
                    f"{exec_verdict}计划 {plan_km}km（{day_plan['target_pace']}），实际完成 {act_km}km"
                    f"（配速 {act_pace}{hr_clause}{elev_clause}）。{phys_verdict}"
                )

            try:
                holistic_ctx = LocalStore.build_canova_holistic_context(
                    eff_uid,
                    selected_act or actual_data,
                    profile=profile,
                )
            except Exception as h_err:
                logger.warning(f"[miniapp] Holistic context eval fallback for {eff_uid}: {h_err}")
                holistic_ctx = {}

            bio_visible = not is_bio_hidden

            phys_extras: List[str] = []
            h_load = (holistic_ctx or {}).get("load") or {}
            h_rec = (holistic_ctx or {}).get("recovery") or {}
            h_plan = (holistic_ctx or {}).get("plan") or {}
            h_race = (holistic_ctx or {}).get("race")

            wk_runs = int((holistic_ctx or {}).get("week_runs_count") or 0)
            wk_km = float((holistic_ctx or {}).get("week_km") or 0.0)
            wk_tgt = (holistic_ctx or {}).get("weekly_target_km")
            if wk_runs >= 1:
                if wk_tgt and wk_tgt > 0:
                    phys_extras.append(f"本周{wk_runs}练累计{wk_km:g}/{int(round(float(wk_tgt)))}km")
                else:
                    phys_extras.append(f"本周{wk_runs}练累计{wk_km:g}km")
            if h_load.get("has_load_history"):
                tsb_i = int(round(float(h_load.get("tsb_post") or 0.0)))
                ctl_i = int(round(float(h_load.get("ctl") or 0.0)))
                phys_extras.append(f"CTL {ctl_i} / TSB {tsb_i:+d}")
            if bio_visible and h_rec.get("overnight_available"):
                r_bits: List[str] = []
                if h_rec.get("sleep_hours") is not None:
                    r_bits.append(f"睡眠{h_rec['sleep_hours']}h")
                if h_rec.get("hrv_ms") is not None:
                    r_bits.append(f"HRV {h_rec['hrv_ms']}ms")
                elif h_rec.get("rhr_bpm") is not None:
                    r_bits.append(f"静息{h_rec['rhr_bpm']}bpm")
                if r_bits:
                    phys_extras.append("·".join(r_bits))
            tmr_w = h_plan.get("tomorrow_workout")
            nxt_k = h_plan.get("next_key_workout")
            if tmr_w and not tmr_w.get("is_rest"):
                phys_extras.append(tmr_w["phrase"])
            elif nxt_k:
                phys_extras.append(nxt_k["phrase"])
            elif h_race and h_race.get("days_left"):
                r_label = h_race.get("short_name") or h_race.get("name") or "目标赛"
                phys_extras.append(f"距{r_label} D-{h_race['days_left']}")
            extra_phys_sentence = f"（{'；'.join(phys_extras)}）。" if phys_extras else ""

            commentary_phys = (
                f"从 Canova 专项耐力视角审视：本次 {act_km}km 训练（配速 {act_pace}{hr_clause}）"
                f"{'结合 +' + str(int(act_elev)) + 'm 地形起伏，显著强化了臀腿离心力量与抗衰减能力。' if act_elev >= 20 else '节奏控制克制精准，在极低机械压力下完成了高质量有氧刺激。'}"
                f"{extra_phys_sentence}建议跑后 30 分钟内补充碳水与电解质，保障超量恢复。"
            ).replace("休整日", "跑休")

            act_journal_txt = _extract_journal_text((selected_act or {}).get("ai_journal"))
            if (
                selected_act
                and bio_visible
                and LocalStore._needs_canova_critique_refresh(
                    selected_act.get("ai_journal"),
                    selected_act,
                    strict_format_upgrade=False,
                )
            ):
                try:
                    fresh_txt = LocalStore.generate_canova_critique(selected_act, profile)
                    if fresh_txt:
                        act_journal_txt = fresh_txt
                except Exception:
                    pass
            plan_notes_txt = "" if large_discrepancy else _extract_journal_text(day_plan.get("coach_notes"))
            raw_journal = _clean_ai_terms(act_journal_txt or plan_notes_txt)
            if not bio_visible:
                if raw_journal:
                    raw_journal = LocalStore.sanitize_canova_critique_biometrics(raw_journal)
                commentary_exec = LocalStore.sanitize_canova_critique_biometrics(commentary_exec)
                commentary_phys = LocalStore.sanitize_canova_critique_biometrics(commentary_phys)
            commentary_journal = raw_journal.replace("休整日", "跑休") if len(raw_journal) >= 15 else commentary_exec
        else:
            commentary_exec = (
                f"今日计划课目为【{plan_title_short} · {plan_km}km】，目标配速 {day_plan['target_pace']}，"
                f"目标心率 {day_plan['target_hr_zone']}。专注呼吸与步频节奏，跑出属于你的科学耐力节奏！"
            )
            if is_bio_hidden:
                commentary_exec = LocalStore.sanitize_canova_critique_biometrics(commentary_exec)
            commentary_phys = commentary_exec
            commentary_journal = commentary_exec

        commentary_options = [
            {"key": "exec", "label": exec_label, "text": commentary_exec},
            {"key": "phys", "label": "❤️ 生理与负荷深评", "text": commentary_phys},
            {"key": "journal", "label": "📝 课目专项点评", "text": commentary_journal},
        ]

    if is_critique_hidden:
        commentary_exec = ""
        commentary_options = []

    # 5. Resolve User's Primary Club & Generate Official WeChat Invite QR Code (wxacode)
    user_clubs = LocalStore.get_user_clubs(eff_uid)
    target_club = None
    if club_id:
        for c in user_clubs:
            if c.get("id") == club_id:
                target_club = c
                break
        if not target_club:
            target_club = LocalStore.get_club(club_id)
    if not target_club and user_clubs:
        target_club = user_clubs[0]
    if not target_club:
        target_club = LocalStore.get_club("club_fudan_gobi_main") or LocalStore.get_club("club_rgm_flagship") or {
            "id": "club_fudan_gobi_main",
            "name": "万跑跑团助手",
            "invite_code": "FD8888",
            "logo_url": "https://rgm.vanpower.net/api/avatars/rgm-logo.png",
        }

    eff_club_id = target_club.get("id") or "club_fudan_gobi_main"
    eff_club_name = target_club.get("name") or "万跑跑团助手"
    eff_club_code = (target_club.get("invite_code") or "").strip()

    eff_env = env_version if env_version in ("release", "trial", "develop") else "release"
    safe_uid_tag = "".join(c for c in eff_uid if c.isalnum() or c in ("_", "-"))[:24]
    safe_club_tag = "".join(c for c in eff_club_id if c.isalnum() or c in ("_", "-"))[:20]
    qr_filename = f"wxacode_share_{eff_env}_{safe_uid_tag}_{safe_club_tag}.jpg"
    qr_file_path = os.path.join(avatar_dir, qr_filename)

    qr_path = f"pages/team/team?club_id={eff_club_id}&action=join_club&invite_code={eff_club_code}&inviter_uid={eff_uid}"

    if not os.path.exists(qr_file_path) or os.path.getsize(qr_file_path) < 500:
        try:
            img_bytes = wechat_client.get_wxacode_by_path(
                path=qr_path,
                width=280,
                env_version=eff_env,
            )
            if not img_bytes:
                img_bytes = wechat_client.get_wxacode_unlimit(
                    scene=f"inv={eff_uid[:16]}"[:32],
                    page="pages/team/team",
                    width=280,
                    env_version=eff_env,
                )
            if img_bytes and len(img_bytes) >= 500:
                with open(qr_file_path, "wb") as f:
                    f.write(img_bytes)
        except Exception as qre:
            logger.warning(f"[miniapp] Generate personal share QR code failed: {qre}")

    qrcode_b64 = ""
    qrcode_url = ""
    if os.path.exists(qr_file_path) and os.path.getsize(qr_file_path) >= 500:
        qrcode_url = f"https://rgm.vanpower.net/api/avatars/{qr_filename}"
        with open(qr_file_path, "rb") as f:
            qrcode_b64 = base64.b64encode(f.read()).decode("ascii")

    avatar_b64 = _resolve_img_b64(profile.get("avatar_url"))

    # Recent runs selector list (up to 8 runs)
    recent_selector = []
    for a in run_acts[:8]:
        d_m = float(a.get("distance_meters") or 0.0)
        d_km = round(d_m / 1000.0, 2)
        st_date = str(a.get("start_time") or "")[:10]
        recent_selector.append({
            "id": a["id"],
            "name": a.get("name") or "跑步",
            "date": st_date,
            "distance_km": d_km,
            "avg_pace_str": (a.get("avg_pace_str") or "—").replace(" /km", ""),
            "elevation_gain_meters": round(float(a.get("elevation_gain_meters") or 0.0), 1),
            "label": f"{st_date[5:]} · {d_km}km ({(a.get('avg_pace_str') or '—').replace(' /km', '')})",
        })

    # Completed races selector list
    races_selector = []
    for r in completed_races_list:
        r_id = r.get("id") or r.get("name")
        r_date = str(r.get("race_date") or "")[:10]
        r_ft = r.get("finish_time") or "已完赛"
        races_selector.append({
            "id": r_id,
            "name": r.get("name") or "赛事",
            "race_type": r.get("race_type") or "马拉松",
            "date": r_date,
            "finish_time": r_ft,
            "target_time": r.get("target_time") or "",
            "performance_badge": r.get("performance_badge") or "顺利完赛",
            "label": f"🏅 {r.get('name')} ({r_ft})",
        })

    return {
        "success": True,
        "card_mode": card_mode,
        "selected_race_id": (selected_race.get("id") or selected_race.get("name")) if selected_race else "",
        "user": {
            "id": eff_uid,
            "display_name": profile.get("display_name") or profile.get("real_name") or "跑者",
            "avatar_url": profile.get("avatar_url"),
            "avatar_base64": avatar_b64,
            "club_id": eff_club_id,
            "club_name": eff_club_name,
            "club_invite_code": eff_club_code,
        },
        "day_plan": day_plan,
        "actual_data": actual_data,
        "track_overlay": track_overlay,
        "canova_commentary": commentary_exec,
        "commentary_options": commentary_options,
        "is_critique_hidden": is_critique_hidden,
        "is_biometrics_hidden": is_bio_hidden,
        "recent_runs": recent_selector,
        "completed_races": races_selector,
        "default_photo_base64": default_photo_b64,
        "default_photo_focus": default_photo_focus,
        "race_photos": race_photos_list,
        "qrcode_url": qrcode_url,
        "qrcode_base64": qrcode_b64,
        "qr_path": qr_path,
    }


class TelemetryEventItem(BaseModel):
    event_id: Optional[str] = None
    session_id: Optional[str] = None
    event_type: str = "button_click"
    event_name: str
    event_label: Optional[str] = None
    page_path: Optional[str] = None
    page_title: Optional[str] = None
    stay_ms: Optional[int] = 0
    scroll_pct: Optional[int] = None
    user_id: Optional[str] = None
    client_ts: Optional[int] = None
    props: Optional[Dict[str, Any]] = None


class TelemetryBatchRequest(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    uid: Optional[str] = None
    client_uuid: Optional[str] = None
    scene: Optional[int] = None
    scene_label: Optional[str] = None
    entry_page: Optional[str] = None
    inviter_uid: Optional[str] = None
    device_model: Optional[str] = None
    platform: Optional[str] = None
    app_version: Optional[str] = None
    env_version: Optional[str] = None
    events: List[TelemetryEventItem] = Field(default_factory=list, max_length=120)


_TELEMETRY_RATE_BUCKETS: Dict[str, List[float]] = {}


def _is_trusted_reverse_proxy(peer_ip: str) -> bool:
    if peer_ip in ("127.0.0.1", "::1", "localhost", "testclient"):
        return True
    try:
        addr = ipaddress.ip_address(peer_ip)
        return bool(addr.is_loopback or addr.is_private)
    except ValueError:
        return False


def _resolve_rate_limit_ip(request: Request) -> str:
    peer_ip = (request.client.host if request.client else "") or "anon"
    # Trust X-Real-IP / X-Forwarded-For when direct peer is loopback or internal Docker reverse-proxy network
    if _is_trusted_reverse_proxy(peer_ip):
        real_ip = (request.headers.get("x-real-ip") or "").strip()
        if real_ip:
            return real_ip[:64]
        xff = (request.headers.get("x-forwarded-for") or "").strip()
        if xff:
            hops = [h.strip() for h in xff.split(",") if h.strip()]
            if hops:
                return hops[-1][:64]
    return peer_ip[:64]


def _check_single_rate_bucket(key: str, max_batches_per_min: int, now: float) -> bool:
    cutoff = now - 60.0
    if len(_TELEMETRY_RATE_BUCKETS) > 4000:
        stale_keys = [
            k for k, ts_list in _TELEMETRY_RATE_BUCKETS.items()
            if not ts_list or ts_list[-1] <= cutoff
        ]
        for k in stale_keys:
            _TELEMETRY_RATE_BUCKETS.pop(k, None)
        while len(_TELEMETRY_RATE_BUCKETS) > 4000:
            _TELEMETRY_RATE_BUCKETS.pop(next(iter(_TELEMETRY_RATE_BUCKETS)), None)
    bucket = [t for t in _TELEMETRY_RATE_BUCKETS.get(key, []) if t > cutoff]
    if len(bucket) >= max_batches_per_min:
        _TELEMETRY_RATE_BUCKETS[key] = bucket
        return False
    return True


def _check_telemetry_rate_limits(real_ip: str, client_uuid: Optional[str]) -> bool:
    """
    Two-tier rate limiter:
    - Per device (`dev:<ip>:<client_uuid>`): 45 batches/min
    - Per IP (`ip:<ip>`): 600 batches/min (carrier CGNAT / venue Wi-Fi safe while capping IP floods)
    """
    now = time.time()
    clean_cid = (client_uuid or "").strip()[:64]
    dev_key = f"dev:{real_ip}:{clean_cid}" if clean_cid else None
    ip_key = f"ip:{real_ip}"

    if dev_key and not _check_single_rate_bucket(dev_key, 45, now):
        return False
    if not _check_single_rate_bucket(ip_key, 600, now):
        return False

    if dev_key:
        _TELEMETRY_RATE_BUCKETS.setdefault(dev_key, []).append(now)
    _TELEMETRY_RATE_BUCKETS.setdefault(ip_key, []).append(now)
    return True


def _extract_verified_telemetry_uid(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "", 1).strip()
    if not token:
        return None
    try:
        import jwt
        decoded = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        uid = decoded.get("sub") or decoded.get("uid")
        return str(uid).strip()[:80] if uid else None
    except Exception:
        return None


@router.post("/telemetry/batch")
def ingest_miniapp_telemetry_batch(
    req: TelemetryBatchRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Lightweight batch ingestion endpoint for MiniApp full-chain user behavior analytics.
    Identity is verified strictly from the signed Bearer JWT (never from unverified body fields).
    """
    real_ip = _resolve_rate_limit_ip(request)
    if not _check_telemetry_rate_limits(real_ip, req.client_uuid):
        return JSONResponse(
            status_code=429,
            content={"success": False, "accepted": 0, "rate_limited": True},
        )

    try:
        verified_uid = _extract_verified_telemetry_uid(authorization)
        payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        res = LocalStore.ingest_telemetry_batch(payload, verified_user_id=verified_uid)
        return {"success": True, **res}
    except Exception as e:
        logger.warning(f"[miniapp] Telemetry batch ingest warning: {e}")
        return {"success": False, "accepted": 0}



