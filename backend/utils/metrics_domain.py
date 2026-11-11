"""
Unified Physiological Metrics Domain Service (`MetricsDomainService`)
Ensures 100% parity across Web (`/api/science/metrics`) and WeChat Mini-Program (`/api/miniapp/home`)
for CTL / ATL / TSB (EWMA Training Load), TSB 4-tier status badges, Beijing timezone boundaries,
180-day warm-up window, and excluded-activity filtering.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.local_store import LocalStore, get_beijing_today
from utils.running_metrics import calculate_trimp, calculate_vdot, compute_ctl_atl_tsb


def get_tsb_badge_info(tsb: float) -> Dict[str, str]:
    """Unified 4-tier TSB form status badge across Web and Mini-Program."""
    if tsb > 5:
        return {"category": "peak", "label": "巅峰", "color": "#22c55e"}
    if tsb >= -30:
        return {"category": "training", "label": "训练中", "color": "#0ea5e9"}
    if tsb >= -50:
        return {"category": "fatigue", "label": "疲劳", "color": "#eab308"}
    return {"category": "severe", "label": "严重疲劳", "color": "#ef4444"}


class MetricsDomainService:
    """Single source of truth for runner training load (CTL/ATL/TSB) & realized VDOT."""

    get_tsb_badge_info = staticmethod(get_tsb_badge_info)

    @staticmethod
    def compute_load_and_form(
        activities: List[Dict[str, Any]],
        profile: Optional[Dict[str, Any]] = None,
        window_days: int = 90,
        warmup_days: int = 180,
        today: Optional[date] = None,
    ) -> Dict[str, Any]:
        eff_today = today or get_beijing_today()
        eff_warmup = max(window_days, warmup_days)
        prof = profile or {}
        rest_hr = float(prof.get("resting_heart_rate") or 58.0)
        max_hr = float(prof.get("max_heart_rate") or 190.0)
        gender = str(prof.get("gender") or "male")

        daily_trimp_map: Dict[str, float] = {
            (eff_today - timedelta(days=i)).isoformat(): 0.0
            for i in range(eff_warmup, -1, -1)
        }

        best_vdot = 0.0
        valid_count = 0
        for act in activities or []:
            ex_mode = str(act.get("exclude_mode") or "normal").strip().lower()
            if ex_mode == "excluded" or act.get("is_excluded"):
                continue

            valid_count += 1
            st = str(act.get("start_time") or "")[:10]
            trimp_val = float(act.get("trimp") or 0.0)
            if trimp_val <= 0:
                dur_min = float(act.get("moving_time_seconds") or act.get("duration_seconds") or 0.0) / 60.0
                avg_hr = float(act.get("average_heartrate") or 0.0)
                if dur_min > 0 and avg_hr > rest_hr:
                    trimp_val = calculate_trimp(dur_min, avg_hr, rest_hr, max_hr, gender)

            if st in daily_trimp_map:
                daily_trimp_map[st] += trimp_val

            dist = float(act.get("distance_meters") or 0.0)
            time_s = float(act.get("moving_time_seconds") or act.get("duration_seconds") or 0.0)
            if (
                ex_mode != "ignore_vdot"
                and dist >= 3000
                and time_s > 0
                and LocalStore.is_running_activity(act.get("sport_type"))
            ):
                pace_s_km = time_s / (dist / 1000.0)
                if 165.0 <= pace_s_km <= 480.0:
                    v = calculate_vdot(dist, time_s)
                    if v and v > best_vdot:
                        best_vdot = v

        if valid_count == 0:
            return {
                "current_ctl": 0.0,
                "current_atl": 0.0,
                "current_tsb": 0.0,
                "current_tsb_badge": {"category": "none", "label": "未连接", "color": "#6b7280"},
                "best_vdot": None,
                "history": [],
            }

        series = sorted(daily_trimp_map.items(), key=lambda x: x[0])
        raw_curve = compute_ctl_atl_tsb(series)

        enriched: List[Dict[str, Any]] = []
        for item in raw_curve:
            d_obj = datetime.strptime(item["date"], "%Y-%m-%d").date()
            tsb_val = float(item["tsb"])
            b_info = get_tsb_badge_info(tsb_val)
            enriched.append(
                {
                    "date": item["date"],
                    "short_date": d_obj.strftime("%m-%d"),
                    "ctl": item["ctl"],
                    "atl": item["atl"],
                    "tsb": tsb_val,
                    "tsb_category": b_info["category"],
                    "tsb_label": b_info["label"],
                    "tsb_color": b_info["color"],
                    "trimp": item["trimp"],
                }
            )

        sliced_history = enriched[-(window_days + 1) :] if window_days >= 0 else enriched
        latest = sliced_history[-1] if sliced_history else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}
        latest_badge = get_tsb_badge_info(float(latest["tsb"]))

        return {
            "current_ctl": float(latest["ctl"]),
            "current_atl": float(latest["atl"]),
            "current_tsb": float(latest["tsb"]),
            "current_tsb_badge": latest_badge,
            "best_vdot": round(best_vdot, 1) if best_vdot > 0 else None,
            "history": sliced_history,
        }
