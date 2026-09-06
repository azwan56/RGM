"""
Dedicated High-Performance Endpoints for WeChat Mini Program & Web Dashboard
Reduces network roundtrips by bundling essential dashboard data into single fast responses.
Includes smart user mapping so newly opened Mini Programs automatically resolve to the active runner profile.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime, date, timedelta
import calendar
import logging
from db import supabase_admin
from utils.local_store import LocalStore
from utils.running_metrics import compute_ctl_atl_tsb

logger = logging.getLogger("router_miniapp")
router = APIRouter()

@router.get("/dashboard/{uid}")
def get_miniapp_dashboard_data(uid: str) -> Dict[str, Any]:
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
        eff_uid = uid
        profile = LocalStore.get_profile(eff_uid) or {}
        if not profile:
            profile = {
                "id": eff_uid,
                "display_name": "微信跑者",
                "garmin_connected": False
            }
            LocalStore.upsert_profile(eff_uid, profile)

        # 2. Compute Monthly Goal Progress
        today = date.today()
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

        # 2.1 Weekly Progress
        weekly_progress = LocalStore.get_weekly_stats(eff_uid, target_km=goal.get("weekly_target"))

        # 3. Monthly Trend (6 months) & Yearly Stats (2026)
        monthly_trend = LocalStore.get_monthly_trend(eff_uid, num_months=6)
        yearly_stats = LocalStore.get_yearly_stats(eff_uid, year=2026)

        # 4. Recent activities
        recent_activities = []
        local_acts = LocalStore.get_recent_activities(eff_uid, limit=100)
        for a in local_acts[:10]:
            dist_m = float(a.get("distance_meters") or 0)
            dist_km = round(dist_m / 1000.0, 2)
            recent_activities.append({
                "id": a["id"],
                "name": a["name"],
                "start_time": a["start_time"],
                "distance_meters": dist_m,
                "distance_km": dist_km,
                "moving_time_seconds": a.get("moving_time_seconds") or 0,
                "avg_pace_str": a.get("avg_pace_str") or "—",
                "average_heartrate": a.get("average_heartrate"),
                "trimp": a.get("trimp"),
                "ai_journal": a.get("ai_journal")
            })

        # 5. Today's Health Snapshot (4-grid card data)
        health_data = LocalStore.get_latest_health(eff_uid)
        if health_data:
            sleep_hours = health_data.get("sleep_duration_hours")
            sleep_sec = health_data.get("sleep_duration_seconds")
            sleep_score = health_data.get("sleep_score")
            rhr = health_data.get("resting_heart_rate")
            body_battery = health_data.get("body_battery_max")
            hrv_val = health_data.get("hrv_last_night_avg")
            hrv_weekly = health_data.get("hrv_weekly_avg")

            sleep_text = None
            if sleep_sec and sleep_sec > 0:
                hours = int(sleep_sec // 3600)
                mins = int((sleep_sec % 3600) // 60)
                sleep_text = f"{hours}h {mins}m"
            elif sleep_hours and sleep_hours > 0:
                hours = int(sleep_hours)
                mins = int(round((sleep_hours % 1) * 60))
                sleep_text = f"{hours}h {mins}m"

            today_health = {
                "date": health_data.get("date") or today.isoformat(),
                "sleep_score": sleep_score,
                "sleep_duration_hours": sleep_hours,
                "sleep_duration_seconds": sleep_sec,
                "sleep_duration_text": sleep_text,
                "resting_heart_rate": rhr,
                "body_battery_max": body_battery,
                "hrv_ms": int(hrv_val) if hrv_val is not None else None,
                "hrv_weekly_avg": int(hrv_weekly) if hrv_weekly is not None else None,
                "hrv_status": health_data.get("hrv_status") or "BALANCED",
                "vo2_max": health_data.get("vo2_max")
            }
        else:
            today_health = None

        # 6. Compute Fitness & Form (CTL, ATL, TSB) - 90 days EWMA
        fitness_form = {
            "ctl": 0.0,
            "atl": 0.0,
            "tsb": 0.0,
            "status_label": "未连接",
            "status_color": "#6b7280",
            "history": []
        }
        if local_acts:
            try:
                today = date.today()
                daily_trimp_map = { (today - timedelta(days=i)).isoformat(): 0.0 for i in range(90, -1, -1) }
                for a in local_acts:
                    st = str(a.get("start_time", ""))[:10]
                    if st in daily_trimp_map:
                        daily_trimp_map[st] += float(a.get("trimp") or 0.0)
                
                series = sorted(daily_trimp_map.items(), key=lambda x: x[0])
                ctl_atl_list = compute_ctl_atl_tsb(series)
                
                enriched_history = []
                for item in ctl_atl_list:
                    d_obj = datetime.strptime(item["date"], "%Y-%m-%d").date()
                    tsb_val = float(item["tsb"])
                    color = "#22c55e" if tsb_val > 5 else ("#1890ff" if tsb_val >= -30 else ("#eab308" if tsb_val >= -50 else "#ef4444"))
                    label = "巅峰" if tsb_val > 5 else ("训练中" if tsb_val >= -30 else ("疲劳" if tsb_val >= -50 else "严重"))
                    enriched_history.append({
                        "date": item["date"],
                        "short_date": d_obj.strftime("%m-%d"),
                        "ctl": item["ctl"],
                        "atl": item["atl"],
                        "tsb": tsb_val,
                        "tsb_color": color,
                        "tsb_label": label,
                        "trimp": item["trimp"]
                    })
                
                if enriched_history:
                    latest = enriched_history[-1]
                    fitness_form = {
                        "ctl": latest["ctl"],
                        "atl": latest["atl"],
                        "tsb": latest["tsb"],
                        "status_label": latest["tsb_label"],
                        "status_color": latest["tsb_color"],
                        "history": enriched_history[-30:] # recent 30 days
                    }
            except Exception as e:
                logger.warning(f"[miniapp] Fitness form calc error: {e}")

        return {
            "user": {
                "id": eff_uid,
                "display_name": profile.get("display_name") or "跑者",
                "avatar_url": profile.get("avatar_url"),
                "garmin_connected": bool(profile.get("garmin_connected")),
                "garmin_last_sync_at": profile.get("garmin_last_sync_at"),
                "garmin_domain": profile.get("garmin_domain") or "garmin.com",
                "coros_connected": bool(profile.get("coros_connected")),
                "coros_account": profile.get("coros_account"),
                "coros_domain": profile.get("coros_domain") or "teamcnapi.coros.com",
                "coros_last_sync_at": profile.get("coros_last_sync_at"),
            },
            "fitness_form": fitness_form,
            "progress": {
                "current_month_km": current_km,
                "target_month_km": target_km,
                "progress_pct": progress_pct,
                "remaining_km": remaining_km,
                "days_left_in_month": days_left,
                "daily_required_km": daily_req,
            },
            "weekly_progress": weekly_progress,
            "monthly_trend": monthly_trend,
            "yearly_stats": yearly_stats,
            "recent_activities": recent_activities,
            "today_health": today_health,
            "ai_coach_tip": "保持耐心，专注有氧节奏构建，专项能力水到渠成。"
        }
    except Exception as e:
        logger.error(f"[miniapp] Error compiling dashboard: {e}")
        today = date.today()
        iso_year, iso_week, _ = today.isocalendar()
        return {
            "user": {
                "id": uid,
                "display_name": "跑者",
                "avatar_url": None,
                "garmin_connected": False,
                "garmin_last_sync_at": None,
                "garmin_domain": "garmin.com",
                "coros_connected": False,
                "coros_account": None,
                "coros_domain": "teamcnapi.coros.com",
                "coros_last_sync_at": None,
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
                "year": now.year,
                "total_km": 0.0,
                "total_runs": 0,
                "avg_monthly_km": 0.0,
                "projected_year_km": 0.0,
                "target_year_km": 2400.0,
                "progress_pct": 0.0,
                "best_month": {
                    "name": f"{now.month}月",
                    "distance_km": 0.0,
                    "avg_pace": "—"
                }
            },
            "recent_activities": [],
            "today_health": None,
            "ai_coach_tip": "欢迎使用 RGM 跑团助手！请在【我的】页面绑定佳明设备以开启全自动化训练分析。"
        }

@router.get("/activities/{uid}")
def get_miniapp_activities(uid: str, limit: int = 50) -> Dict[str, Any]:
    """Returns activity list for activities tab in mini program."""
    eff_uid = uid
    acts = LocalStore.get_recent_activities(eff_uid, limit=limit)
    formatted = []
    for a in acts:
        dist_m = float(a.get("distance_meters") or 0)
        formatted.append({
            "id": a["id"],
            "name": a["name"],
            "start_time": a["start_time"],
            "distance_meters": dist_m,
            "distance_km": round(dist_m / 1000.0, 2),
            "moving_time_seconds": a.get("moving_time_seconds") or 0,
            "avg_pace_str": a.get("avg_pace_str") or "—",
            "average_heartrate": a.get("average_heartrate"),
            "trimp": a.get("trimp"),
            "ai_journal": a.get("ai_journal")
        })
    return {"activities": formatted}
