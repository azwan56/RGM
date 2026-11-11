from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, date, timedelta
from db import supabase_admin
from utils.local_store import LocalStore
from utils.metrics_domain import MetricsDomainService, get_tsb_badge_info
from utils.running_metrics import (
    calculate_vdot,
    calculate_workout_effective_vdot,
    vdot_to_race_time,
    compute_ctl_atl_tsb,
    get_canova_zones,
    simulate_taper_7d,
    compute_canova_athlete_matrix,
    predict_realistic_race_times,
)

logger = logging.getLogger("router_science")
router = APIRouter()


class ActivityExcludeModeRequest(BaseModel):
    user_id: str
    exclude_mode: str = "normal"  # 'normal' | 'ignore_vdot' | 'excluded'


@router.get("/metrics/{uid}")
def get_science_metrics(
    uid: str,
    viewer_uid: Optional[str] = None,
    request: Request = None,
):
    """
    Returns deep science analytics:
    - CTL / ATL / TSB (Fitness, Fatigue, Form) curve for last 90 days with GCP color styling
    - Effective VDOT & race predictions (5K, 10K, Half, Full)
    - Renato Canova 5-dimension specificity matrix & runner endurance retention diagnosis
    - 7-day Taper Simulator (3 scenarios)
    - Supports cross-view drill-down by certified Coach or bound 1-on-1 Mentor via viewer_uid
    - When viewer_uid and uid are NOT in the same running club (and viewer is not Super Admin),
      returns only basic status (`basic_status_only=True`) without specific workout records or curves.
    """
    try:
        canonical_uid = LocalStore.resolve_user_id(uid)
        eff_viewer = (
            viewer_uid
            if isinstance(viewer_uid, str) and viewer_uid.strip()
            else (
                (request.headers.get("x-user-id") if request else None)
                or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
            )
        )
        if eff_viewer:
            canonical_viewer = LocalStore.resolve_user_id(eff_viewer)
            if canonical_viewer != canonical_uid:
                if not LocalStore.can_view_specific_workout_records(canonical_viewer, canonical_uid):
                    basic_st = LocalStore.get_runner_basic_status(canonical_uid, viewer_uid=canonical_viewer)
                    return {
                        "basic_status_only": True,
                        "privacy_notice": "不在同一跑团的用户之间仅可查看基本状态，不能相互查看具体运动记录与详细生理曲线",
                        "basic_status": basic_st,
                        "student_profile": {
                            "id": canonical_uid,
                            "display_name": basic_st.get("display_name") or "跑者",
                            "avatar_url": basic_st.get("avatar_url") or "",
                        },
                        "current_ctl": 0.0,
                        "current_atl": 0.0,
                        "current_tsb": 0.0,
                        "current_tsb_badge": {
                            "category": "basic",
                            "label": "已绑表" if basic_st.get("watch_bound") else "未绑表",
                            "color": "#10b981" if basic_st.get("watch_bound") else "#f59e0b",
                        },
                        "vdot": None,
                        "vo2max": None,
                        "race_predictions": {
                            "five_k": "—",
                            "ten_k": "—",
                            "half_marathon": "—",
                            "marathon": "—",
                        },
                        "canova_zones": {},
                        "canova_matrix": None,
                        "taper_simulation": None,
                        "ctl_atl_tsb_history": [],
                    }
                profile_chk = LocalStore.get_profile(canonical_uid) or {}
                if bool(profile_chk.get("hide_biometrics")) and not LocalStore.can_view_confidential_runner_data(canonical_viewer, canonical_uid):
                    raise HTTPException(
                        status_code=403,
                        detail="该队员已将 HRV 与生理恢复数据设为保密（仅对本人、认证教练和 1对1 师傅开放）"
                    )

        profile = LocalStore.get_profile(canonical_uid) or {}
        student_profile = {
            "id": canonical_uid,
            "display_name": profile.get("display_name") or "跑者",
            "avatar_url": profile.get("avatar_url") or "",
        }
        m_pb = profile.get("marathon_pb")
        zones = get_canova_zones(m_pb) if m_pb else {}
        rest_hr = float(profile.get("resting_heart_rate") or 58.0)
        max_hr = float(profile.get("max_heart_rate") or 190.0)
        health_trend = LocalStore.get_health_trend_30d(canonical_uid)

        activities = LocalStore.get_recent_activities(canonical_uid, limit=250)
        v_meta = LocalStore.resolve_verified_runner_profile_and_pbs(
            canonical_uid, profile=profile, recent_acts=activities, query_activities=True
        )
        clean_profile = {
            **profile,
            "marathon_pb": v_meta.get("verified_mp_sec"),
            "half_pb": v_meta.get("verified_hp_sec"),
            "ten_k_pb": v_meta.get("verified_10k_sec"),
            "five_k_pb": v_meta.get("verified_5k_sec"),
            "peak_vdot": v_meta.get("peak_vdot"),
            "peak_endurance_vdot": v_meta.get("peak_endurance_vdot"),
        }
        zones = get_canova_zones(v_meta.get("verified_mp_sec")) if v_meta.get("verified_mp_sec") else {}
        if not activities:
            empty_matrix = compute_canova_athlete_matrix(clean_profile, [], 0.0, 0.0, health_trend)
            empty_preds = predict_realistic_race_times(empty_matrix)
            return {
                "student_profile": student_profile,
                "current_ctl": 0.0,
                "current_atl": 0.0,
                "current_tsb": 0.0,
                "current_tsb_badge": {"category": "none", "label": "未连接", "color": "#6b7280"},
                "vdot": empty_matrix.get("effective_vdot"),
                "vo2max": empty_matrix.get("watch_vo2max"),
                "race_predictions": empty_preds,
                "canova_zones": zones,
                "canova_matrix": empty_matrix,
                "taper_simulation": simulate_taper_7d(0.0, 0.0),
                "ctl_atl_tsb_history": []
            }
        
        # Unified CTL/ATL/TSB calculation via MetricsDomainService (Beijing timezone, 180d warmup, skips excluded)
        load_summary = MetricsDomainService.compute_load_and_form(
            activities=activities,
            profile=clean_profile,
            window_days=90,
            warmup_days=180,
        )
        enriched_history = load_summary["history"]
        latest_item = {
            "ctl": load_summary["current_ctl"],
            "atl": load_summary["current_atl"],
            "tsb": load_summary["current_tsb"],
        }
        latest_tsb_badge = load_summary["current_tsb_badge"]
        best_vdot = float(load_summary["best_vdot"] or 0.0)

        canova_matrix = compute_canova_athlete_matrix(
            profile=clean_profile,
            activities=activities,
            current_ctl=float(latest_item["ctl"]),
            current_tsb=float(latest_item["tsb"]),
            health_trend=health_trend,
        )
        eff_vdot = canova_matrix.get("effective_vdot") or (round(best_vdot, 1) if best_vdot > 0 else None)
        if canova_matrix.get("effective_vdot") is None and eff_vdot:
            canova_matrix["effective_vdot"] = eff_vdot
        taper_sim = simulate_taper_7d(float(latest_item["ctl"]), float(latest_item["atl"]))

        race_preds = predict_realistic_race_times(canova_matrix)
        pred_m_sec = int(race_preds.get("marathon_seconds") or 0)
        dynamic_zones = get_canova_zones(pred_m_sec) if pred_m_sec > 0 else zones
        return {
            "student_profile": student_profile,
            "current_ctl": latest_item["ctl"],
            "current_atl": latest_item["atl"],
            "current_tsb": latest_item["tsb"],
            "current_tsb_badge": latest_tsb_badge,
            "vdot": round(float(eff_vdot), 1) if eff_vdot and float(eff_vdot) > 0 else None,
            "vo2max": canova_matrix.get("watch_vo2max"),
            "race_predictions": race_preds,
            "canova_zones": dynamic_zones,
            "canova_matrix": canova_matrix,
            "taper_simulation": taper_sim,
            "ctl_atl_tsb_history": enriched_history
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[science] Metrics calculation fallback: {e}")
        return {
            "current_ctl": 0.0,
            "current_atl": 0.0,
            "current_tsb": 0.0,
            "current_tsb_badge": {"category": "none", "label": "未连接", "color": "#6b7280"},
            "vdot": None,
            "race_predictions": {
                "five_k": "—",
                "ten_k": "—",
                "half_marathon": "—",
                "marathon": "—",
            },
            "canova_zones": {},
            "canova_matrix": None,
            "taper_simulation": None,
            "ctl_atl_tsb_history": []
        }


@router.get("/health-trend/{uid}")
def get_health_trend(
    uid: str,
    viewer_uid: Optional[str] = None,
    request: Request = None,
):
    """
    Returns 30-day health trends:
    - HRV (ms) vs Resting Heart Rate (bpm)
    - Body Battery (%) vs Sleep Quality Score (0-100)
    """
    canonical_uid = LocalStore.resolve_user_id(uid)
    eff_viewer = (
        viewer_uid
        if isinstance(viewer_uid, str) and viewer_uid.strip()
        else (
            (request.headers.get("x-user-id") if request else None)
            or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
        )
    )
    if eff_viewer:
        canonical_viewer = LocalStore.resolve_user_id(eff_viewer)
        if canonical_viewer != canonical_uid:
            if not LocalStore.can_view_specific_workout_records(canonical_viewer, canonical_uid):
                return {"trend": [], "basic_status_only": True, "is_biometrics_hidden": True}
            profile_chk = LocalStore.get_profile(canonical_uid) or {}
            if bool(profile_chk.get("hide_biometrics")) and not LocalStore.can_view_confidential_runner_data(canonical_viewer, canonical_uid):
                return {"trend": [], "is_biometrics_hidden": True}
    trend = LocalStore.get_health_trend_30d(canonical_uid)
    return {"trend": trend}


@router.post("/activities/{activity_id}/exclude-mode")
def update_activity_exclude_mode(activity_id: str, req: ActivityExcludeModeRequest):
    """
    Sets exclude_mode on a running activity:
    - 'normal': 正常计入跑量、负荷与等效 VDOT
    - 'ignore_vdot': 陪跑/慢摇模式（计入跑量，不计入等效 VDOT）
    - 'excluded': 忽略此记录（多表重复或心率异常，不计入跑量、榜单与负荷）
    """
    res = LocalStore.set_activity_exclude_mode(req.user_id, activity_id, req.exclude_mode)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error") or "更新失败")
    return res


@router.get("/personal-report/{uid}")
def get_personal_periodic_report(
    uid: str,
    period_type: str = Query("week", pattern="^(week|month)$", description="统计周期: week 或 month"),
    year: Optional[int] = Query(None, description="年份，如 2026"),
    period_index: Optional[int] = Query(None, description="周序号(1-53)或月份(1-12)"),
    trail_mode: str = Query("include", pattern="^(include|exclude_pace|exclude_all)$", description="越野跑统计口径: include(默认包含), exclude_pace(仅去除越野配速), exclude_all(去除越野跑量与配速)"),
    viewer_uid: Optional[str] = Query(None, description="查看人 UID"),
    request: Request = None,
):
    """
    个人跑步周报与月报查询与海报生成数据接口。
    """
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
            detail="不在同一跑团的用户之间仅可查看基本状态，不能相互查看具体的运动记录与周月报明细",
        )
    try:
        return LocalStore.get_user_periodic_report(
            uid=uid,
            period_type=period_type,
            year=year,
            period_index=period_index,
            trail_mode=trail_mode
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成个人周报/月报失败: {str(e)}")


# ── Official Marathon Pacer Evaluation & AI Prescription Endpoints ──

class PacerAiPrescriptionRequest(BaseModel):
    event_name: Optional[str] = None
    distance_type: Optional[str] = "fm"
    target_group: Optional[str] = None
    custom_distance_km: Optional[float] = None
    custom_target_time: Optional[str] = None
    custom_target_pace: Optional[str] = None
    race_date: Optional[str] = None
    viewer_uid: Optional[str] = None


@router.get("/pacer-presets")
def get_pacer_evaluation_presets():
    """Returns curated road marathon events, generic strictness templates, and standard official pacer groups."""
    from utils.pacer_evaluator import PACER_GROUP_PRESETS, get_pacer_preset_events
    return {
        "events": get_pacer_preset_events(),
        "groups": PACER_GROUP_PRESETS,
    }


@router.get("/pacer-eval/{uid}")
def get_runner_pacer_evaluation(
    uid: str,
    event_name: Optional[str] = Query(None, description="目标赛事名称，如 上海马拉松"),
    distance_type: Optional[str] = Query(None, description="项目类型: fm | hm | 10k | custom"),
    target_group: Optional[str] = Query(None, description="目标兔组代码，如 300 / 330 / 400 / auto"),
    custom_distance_km: Optional[float] = Query(None, description="自定义拉练距离(km)"),
    custom_target_time: Optional[str] = Query(None, description="自定义目标完赛时间"),
    custom_target_pace: Optional[str] = Query(None, description="自定义目标配速，如 5:00"),
    race_date: Optional[str] = Query(None, description="比赛日期 YYYY-MM-DD"),
    viewer_uid: Optional[str] = Query(None, description="跨视角查看人 UID"),
    club_id: Optional[str] = Query(None, description="所属跑团 ID（用于隐私鉴权）"),
    allow_web_search: bool = Query(True, description="冷门赛事是否允许百炼联网检索规程"),
):
    """
    Evaluates a runner's suitability as an Official Marathon / Road Race Pacer across 6 dimensions,
    dual gatekeepers (current fitness safety vs official certificate), and all pacer group tiers.
    """
    from utils.pacer_evaluator import evaluate_runner_pacer_fitness
    try:
        return evaluate_runner_pacer_fitness(
            uid=uid,
            event_name=event_name,
            distance_type=distance_type,
            target_group=target_group,
            custom_distance_km=custom_distance_km,
            custom_target_time=custom_target_time,
            custom_target_pace=custom_target_pace,
            race_date=race_date,
            viewer_uid=viewer_uid,
            club_id=club_id,
            allow_web_search=allow_web_search,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[science] Pacer evaluation failed for {uid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"官方兔子胜任力评估失败: {str(e)}")


@router.post("/pacer-ai-prescription/{uid}")
def create_pacer_ai_prescription(uid: str, req: PacerAiPrescriptionRequest):
    """
    Generates an on-demand 4-week blind-pacing training prescription and an ~180-word
    Official Pacer Recruitment self-recommendation statement.
    """
    from utils.pacer_evaluator import evaluate_runner_pacer_fitness, generate_pacer_ai_prescription
    try:
        eval_res = evaluate_runner_pacer_fitness(
            uid=uid,
            event_name=req.event_name,
            distance_type=req.distance_type,
            target_group=req.target_group,
            custom_distance_km=req.custom_distance_km,
            custom_target_time=req.custom_target_time,
            custom_target_pace=req.custom_target_pace,
            race_date=req.race_date,
            viewer_uid=req.viewer_uid,
            allow_web_search=False,
        )
        return generate_pacer_ai_prescription(eval_res)
    except Exception as e:
        logger.error(f"[science] Pacer AI prescription failed for {uid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成官兔AI处方与自荐语失败: {str(e)}")


