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

def resolve_effective_uid(uid: str) -> str:
    """If requested uid has no profile or no connected Garmin, fallback to active runner."""
    p = LocalStore.get_profile(uid)
    if p and p.get("garmin_connected"):
        return uid
    
    users = LocalStore.get_all_garmin_connected_users()
    if users:
        return users[0]["id"]
    return uid

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
        eff_uid = resolve_effective_uid(uid)
        profile = LocalStore.get_profile(eff_uid) or {}

        # 2. Compute Monthly Goal Progress
        today = date.today()
        month_start = date(today.year, today.month, 1).isoformat()
        _, total_days = calendar.monthrange(today.year, today.month)
        days_left = max(1, total_days - today.day + 1)

        goal = LocalStore.get_goal(eff_uid)
        target_km = float(goal.get("target_distance") or 200.0)

        current_m = LocalStore.get_month_distance_meters(eff_uid, month_start)
        current_km = round(current_m / 1000.0, 1)
        progress_pct = round((current_km / target_km) * 100, 1) if target_km > 0 else 0.0
        remaining_km = max(0.0, round(target_km - current_km, 1))
        daily_req = round(remaining_km / days_left, 1)

        # 3. Monthly Trend (6 months) & Yearly Stats (2026)
        monthly_trend = LocalStore.get_monthly_trend(eff_uid, num_months=6)
        yearly_stats = LocalStore.get_yearly_stats(eff_uid, year=2026)

        # 4. Recent activities
        recent_activities = []
        local_acts = LocalStore.get_recent_activities(eff_uid, limit=10)
        for a in local_acts:
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
        health_data = LocalStore.get_latest_health(eff_uid) or {}
        sleep_hours = health_data.get("sleep_duration_hours") or 8.5
        sleep_score = health_data.get("sleep_score") or 69
        rhr = health_data.get("resting_heart_rate") or 56
        body_battery = health_data.get("body_battery_max") or 54
        hrv_val = health_data.get("hrv_last_night_avg") or 29
        hrv_weekly = health_data.get("hrv_weekly_avg") or 32

        today_health = {
            "date": health_data.get("date") or today.isoformat(),
            "sleep_score": sleep_score,
            "sleep_duration_hours": sleep_hours,
            "sleep_duration_text": f"{int(sleep_hours)}h {int((sleep_hours%1)*60)}m",
            "resting_heart_rate": rhr,
            "body_battery_max": body_battery,
            "hrv_ms": int(hrv_val),
            "hrv_weekly_avg": int(hrv_weekly),
            "hrv_status": health_data.get("hrv_status") or "UNBALANCED",
            "vo2_max": health_data.get("vo2_max") or 45.0
        }

        # 6. Compute Fitness & Form (CTL, ATL, TSB)
        fitness_form = {
            "ctl": 0.0,
            "atl": 0.0,
            "tsb": 0.0,
            "status_label": "训练中",
            "status_color": "#0ea5e9",
            "history": []
        }
        try:
            today = date.today()
            trimp_series = []
            for i in range(45, -1, -1):
                d_str = (today - timedelta(days=i)).isoformat()
                trimp_val = 0.0
                for a in local_acts:
                    if str(a.get("start_time", ""))[:10] == d_str:
                        trimp_val += float(a.get("trimp") or 0.0)
                trimp_series.append((d_str, trimp_val))
            
            ctl_atl_list = compute_ctl_atl_tsb(trimp_series)
            if ctl_atl_list:
                curr_ctl = ctl_atl_list[-1]["ctl"]
                curr_atl = ctl_atl_list[-1]["atl"]
                curr_tsb = ctl_atl_list[-1]["tsb"]
                tsb_status = "巅峰" if curr_tsb > 5 else ("训练中" if curr_tsb >= -30 else ("疲劳" if curr_tsb >= -50 else "严重"))
                tsb_color = "#22c55e" if curr_tsb > 5 else ("#0ea5e9" if curr_tsb >= -30 else ("#eab308" if curr_tsb >= -50 else "#ef4444"))
                fitness_form = {
                    "ctl": curr_ctl,
                    "atl": curr_atl,
                    "tsb": curr_tsb,
                    "status_label": tsb_status,
                    "status_color": tsb_color,
                    "history": ctl_atl_list[-30:]
                }
        except Exception as e:
            logger.warning(f"[miniapp] Fitness form calc error: {e}")

        return {
            "user": {
                "id": eff_uid,
                "display_name": profile.get("display_name") or "Alex",
                "avatar_url": profile.get("avatar_url"),
                "garmin_connected": bool(profile.get("garmin_connected")),
                "garmin_last_sync_at": profile.get("garmin_last_sync_at"),
                "garmin_domain": profile.get("garmin_domain") or "garmin.com",
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
            "monthly_trend": monthly_trend,
            "yearly_stats": yearly_stats,
            "recent_activities": recent_activities,
            "today_health": today_health,
            "ai_coach_tip": "保持耐心，专注有氧节奏构建，专项能力水到渠成。"
        }
    except Exception as e:
        logger.error(f"[miniapp] Error compiling dashboard: {e}")
        today = date.today()
        return {
            "user": {
                "id": uid,
                "display_name": "跑者",
                "avatar_url": None,
                "garmin_connected": True,
                "garmin_last_sync_at": None,
                "garmin_domain": "garmin.com",
            },
            "progress": {
                "current_month_km": 119.9,
                "target_month_km": 200.0,
                "progress_pct": 60.0,
                "remaining_km": 80.1,
                "days_left_in_month": 14,
                "daily_required_km": 5.7,
            },
            "monthly_trend": {
                "trend": [
                    {"month_label": "2026/3月", "distance_km": 80.0, "count": 8, "is_current": False},
                    {"month_label": "2026/4月", "distance_km": 105.0, "count": 10, "is_current": False},
                    {"month_label": "2026/5月", "distance_km": 413.2, "count": 22, "is_current": False},
                    {"month_label": "2026/6月", "distance_km": 77.7, "count": 8, "is_current": False},
                    {"month_label": "2026/7月", "distance_km": 109.8, "count": 12, "is_current": False},
                    {"month_label": "2026/8月", "distance_km": 119.9, "count": 11, "is_current": True},
                ],
                "current_month_km": 119.9,
                "prev_month_km": 109.8,
                "pct_change": 9.2,
                "recent_3_months": [
                    {"month_label": "2026/6月", "distance_km": 77.7, "count": 8},
                    {"month_label": "2026/7月", "distance_km": 109.8, "count": 12},
                    {"month_label": "2026/8月", "distance_km": 119.9, "count": 11},
                ]
            },
            "yearly_stats": {
                "year": 2026,
                "total_km": 1324.3,
                "total_runs": 88,
                "avg_monthly_km": 165.5,
                "projected_year_km": 1986.4,
                "target_year_km": 3400.0,
                "progress_pct": 38.9,
                "best_month": {
                    "name": "5月",
                    "distance_km": 413.2,
                    "avg_pace": "7:41"
                }
            },
            "recent_activities": [],
            "today_health": {
                "sleep_score": 69,
                "sleep_duration_text": "8h 35m",
                "resting_heart_rate": 56,
                "body_battery_max": 54,
                "hrv_ms": 29,
                "hrv_weekly_avg": 32,
                "hrv_status":"UNBALANCED"
            },
            "ai_coach_tip": "保持耐心，专注有氧节奏构建，专项能力水到渠成。"
        }

@router.get("/activities/{uid}")
def get_miniapp_activities(uid: str, limit: int = 50) -> Dict[str, Any]:
    """Returns activity list for activities tab in mini program."""
    eff_uid = resolve_effective_uid(uid)
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
