from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, date, timedelta
from db import supabase_admin
from utils.local_store import LocalStore
from utils.running_metrics import (
    calculate_vdot,
    vdot_to_race_time,
    compute_ctl_atl_tsb,
    get_canova_zones
)

logger = logging.getLogger("router_science")
router = APIRouter()

def get_tsb_badge_info(tsb: float) -> Dict[str, str]:
    if tsb > 5:
        return {"category": "peak", "label": "巅峰", "color": "#22c55e"} # Green
    elif tsb >= -30:
        return {"category": "training", "label": "训练中", "color": "#0ea5e9"} # Blue
    elif tsb >= -50:
        return {"category": "fatigue", "label": "疲劳", "color": "#eab308"} # Yellow
    else:
        return {"category": "severe", "label": "严重疲劳", "color": "#ef4444"} # Red

@router.get("/metrics/{uid}")
def get_science_metrics(uid: str):
    """
    Returns deep science analytics:
    - CTL / ATL / TSB (Fitness, Fatigue, Form) curve for last 90 days with GCP color styling
    - VDOT running score & race predictions (5K, 10K, Half, Full)
    - Renato Canova pace zones
    """
    try:
        profile = LocalStore.get_profile(uid) or {}
        m_pb = profile.get("marathon_pb")
        zones = get_canova_zones(m_pb) if m_pb else {}

        activities = LocalStore.get_recent_activities(uid, limit=100)
        if not activities:
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
                "canova_zones": zones,
                "ctl_atl_tsb_history": []
            }
        
        # Build daily trimp map for last 90 days
        daily_trimp_map: Dict[str, float] = {}
        for i in range(90, -1, -1):
            d_str = (date.today() - timedelta(days=i)).isoformat()
            daily_trimp_map[d_str] = 0.0

        best_vdot = 0.0
        for act in activities:
            st = str(act.get("start_time", ""))[:10]
            if st in daily_trimp_map:
                daily_trimp_map[st] += float(act.get("trimp") or 0.0)

            dist = float(act.get("distance_meters") or 0)
            time_s = float(act.get("moving_time_seconds") or 0)
            if dist >= 4500 and time_s > 0:
                v = calculate_vdot(dist, time_s)
                if v > best_vdot:
                    best_vdot = v

        series = sorted(daily_trimp_map.items(), key=lambda x: x[0])
        ctl_atl_tsb = compute_ctl_atl_tsb(series)

        # Enrich with TSB colors and formatted short dates
        enriched_history = []
        for item in ctl_atl_tsb:
            d_obj = datetime.strptime(item["date"], "%Y-%m-%d").date()
            tsb_val = float(item["tsb"])
            b_info = get_tsb_badge_info(tsb_val)
            enriched_history.append({
                "date": item["date"],
                "short_date": d_obj.strftime("%m-%d"),
                "ctl": item["ctl"],
                "atl": item["atl"],
                "tsb": tsb_val,
                "tsb_category": b_info["category"],
                "tsb_label": b_info["label"],
                "tsb_color": b_info["color"],
                "trimp": item["trimp"]
            })

        latest_item = enriched_history[-1] if enriched_history else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}
        latest_tsb_badge = get_tsb_badge_info(latest_item["tsb"])

        def fmt_time(secs: int) -> str:
            if not secs or secs <= 0:
                return "—"
            h = int(secs // 3600)
            m = int((secs % 3600) // 60)
            s = int(secs % 60)
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"

        return {
            "current_ctl": latest_item["ctl"],
            "current_atl": latest_item["atl"],
            "current_tsb": latest_item["tsb"],
            "current_tsb_badge": latest_tsb_badge,
            "vdot": round(best_vdot, 1) if best_vdot > 0 else None,
            "race_predictions": {
                "five_k": fmt_time(vdot_to_race_time(best_vdot, 5000)) if best_vdot > 0 else "—",
                "ten_k": fmt_time(vdot_to_race_time(best_vdot, 10000)) if best_vdot > 0 else "—",
                "half_marathon": fmt_time(vdot_to_race_time(best_vdot, 21097.5)) if best_vdot > 0 else "—",
                "marathon": fmt_time(vdot_to_race_time(best_vdot, 42195)) if best_vdot > 0 else "—",
            },
            "canova_zones": zones,
            "ctl_atl_tsb_history": enriched_history
        }
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
            "ctl_atl_tsb_history": []
        }


@router.get("/health-trend/{uid}")
def get_health_trend(uid: str):
    """
    Returns 30-day health trends:
    - HRV (ms) vs Resting Heart Rate (bpm)
    - Body Battery (%) vs Sleep Quality Score (0-100)
    """
    trend = LocalStore.get_health_trend_30d(uid)
    return {"trend": trend}
