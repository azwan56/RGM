"""
Official Marathon & Road Race Pacer ("官方配速员 / 官兔") Evaluation Engine for RGM.

Capabilities:
1. Supports Full Marathon (FM), Half Marathon (HM), 10K Road Race standard pacer groups,
   plus Custom Distance & Pace mode (for club 20-35km LSD group-run pacer selection).
2. Event-specific dynamic calibration via race_intel.py (World Athletics Platinum / Gold / Mass / Club LSD,
   course elevation D+, sub-plateau altitude, and heat/humidity stress).
3. Dual independent gatekeepers:
   - Fitness Safety Gate (当期体能安全红线: prevents out-of-shape veterans from bonking)
   - Official Certificate Gate (组委会证书初审红线: distinguishes official pacer vs private/club pacer)
   - Plus 14-day back-to-back race conflict & age (20-60) checks.
4. Six-dimension quantitative scoring (0-100) + Weak-link barrel penalty:
   - S1 (25%): Speed & VDOT Margin (硬实力与配速冗余)
   - S2 (25%): Pacing Stability / Metronome Index via Top-N Cruise Portfolio (巡航控速精准度·代表作择优制)
   - S3 (20%): Training Readiness & Endurance Base (训练水平与专项耐力储备)
   - S4 (15%): Race Experience & Execution Track Record (赛事履历与完赛经验)
   - S5 (10%): Pacing & Leadership Credentials (领跑实战与官方/急救资质)
   - S6 ( 5%): Autonomic Recovery & Reliability (生理恢复与出战可靠性, privacy-safe)
5. Outputs all-group suitability matrix, 6-month mileage bars, showcase steady-run 1km split curve,
   club-wide batch candidate radar, and on-demand AI blind-pacing prescription & recruitment bio.
"""

from __future__ import annotations

import json
import logging
import math
import re
import statistics
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from utils.local_store import DB_PATH, LocalStore, sqlite3
from utils.race_intel import OFFICIAL_ROAD_CATALOG, fetch_race_intelligence
from utils.running_metrics import (
    _assess_long_run_anti_fade,
    calculate_vdot,
    compute_canova_athlete_matrix,
    compute_ctl_atl_tsb,
    format_duration,
    get_age_from_dob,
    predict_realistic_race_times,
    vdot_to_race_time,
)
from utils.workout_segmentation import (
    _extract_normalized_splits,
    fmt_duration_hms,
    fmt_pace_sec,
    parse_pace_range_to_sec,
    parse_pace_str_to_sec,
    parse_time_str_to_seconds,
)

logger = logging.getLogger("pacer_evaluator")


# ─────────────────────────────────────────────────────────────────────────────
# 1. OFFICIAL PACER GROUP PRESETS & EVENT TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────

PACER_GROUP_PRESETS: Dict[str, List[Dict[str, Any]]] = {
    "fm": [
        {"code": "300", "label": "300 官兔", "target_time": "3:00:00", "target_sec": 10800, "tier": "elite"},
        {"code": "315", "label": "315 官兔", "target_time": "3:15:00", "target_sec": 11700, "tier": "elite"},
        {"code": "330", "label": "330 官兔", "target_time": "3:30:00", "target_sec": 12600, "tier": "advanced"},
        {"code": "345", "label": "345 官兔", "target_time": "3:45:00", "target_sec": 13500, "tier": "advanced"},
        {"code": "400", "label": "400 官兔", "target_time": "4:00:00", "target_sec": 14400, "tier": "mass"},
        {"code": "415", "label": "415 官兔", "target_time": "4:15:00", "target_sec": 15300, "tier": "mass"},
        {"code": "430", "label": "430 官兔", "target_time": "4:30:00", "target_sec": 16200, "tier": "mass"},
        {"code": "500", "label": "500 官兔", "target_time": "5:00:00", "target_sec": 18000, "tier": "finisher"},
        {"code": "530", "label": "530 官兔", "target_time": "5:30:00", "target_sec": 19800, "tier": "finisher"},
        {"code": "600", "label": "600 关门兔", "target_time": "6:00:00", "target_sec": 21600, "tier": "finisher"},
        {"code": "615", "label": "615 关门兔", "target_time": "6:15:00", "target_sec": 22500, "tier": "finisher"},
    ],
    "hm": [
        {"code": "130", "label": "130 官兔", "target_time": "1:30:00", "target_sec": 5400, "tier": "elite"},
        {"code": "145", "label": "145 官兔", "target_time": "1:45:00", "target_sec": 6300, "tier": "advanced"},
        {"code": "200", "label": "200 官兔", "target_time": "2:00:00", "target_sec": 7200, "tier": "mass"},
        {"code": "215", "label": "215 官兔", "target_time": "2:15:00", "target_sec": 8100, "tier": "mass"},
        {"code": "230", "label": "230 官兔", "target_time": "2:30:00", "target_sec": 9000, "tier": "finisher"},
        {"code": "245", "label": "245 官兔", "target_time": "2:45:00", "target_sec": 9900, "tier": "finisher"},
        {"code": "300", "label": "300 关门兔", "target_time": "3:00:00", "target_sec": 10800, "tier": "finisher"},
        {"code": "310", "label": "310 关门兔", "target_time": "3:10:00", "target_sec": 11400, "tier": "finisher"},
    ],
    "10k": [
        {"code": "40", "label": "40分 官兔", "target_time": "40:00", "target_sec": 2400, "tier": "elite"},
        {"code": "45", "label": "45分 官兔", "target_time": "45:00", "target_sec": 2700, "tier": "advanced"},
        {"code": "50", "label": "50分 官兔", "target_time": "50:00", "target_sec": 3000, "tier": "mass"},
        {"code": "55", "label": "55分 官兔", "target_time": "55:00", "target_sec": 3300, "tier": "mass"},
        {"code": "60", "label": "60分 官兔", "target_time": "1:00:00", "target_sec": 3600, "tier": "mass"},
        {"code": "70", "label": "70分 完赛兔", "target_time": "1:10:00", "target_sec": 4200, "tier": "finisher"},
        {"code": "80", "label": "80分 关门兔", "target_time": "1:20:00", "target_sec": 4800, "tier": "finisher"},
    ],
}

NOMINAL_DISTANCES_KM: Dict[str, float] = {
    "fm": 42.195,
    "hm": 21.0975,
    "10k": 10.0,
}

FIRST_AID_LABELS: Dict[str, str] = {
    "medical_pro": "🏥 执业医护人员",
    "aha": "❤️ AHA 急救认证",
    "red_cross": "➕ 红十字救护员证",
    "": "未登记急救资质",
}


def get_pacer_preset_events() -> List[Dict[str, Any]]:
    """Returns curated road marathon events and generic templates for quick UI selection."""
    presets: List[Dict[str, Any]] = []
    for entry in OFFICIAL_ROAD_CATALOG:
        def_type = entry.get("default_type", "fm")
        presets.append({
            "event_name": entry["event_name"],
            "race_level": entry.get("race_level", "国际金标"),
            "default_distance_type": def_type,
            "course_profile": entry.get("course_profile", "平坦"),
            "elevation_gain_m": entry.get(f"{def_type}_elevation_gain_m") or entry.get("fm_elevation_gain_m", 45),
            "avg_temp_c": entry.get("avg_temp_c", 14),
            "is_template": False,
        })
    presets.extend([
        {
            "event_name": "通用世界白金标马拉松",
            "race_level": "世界白金标",
            "default_distance_type": "fm",
            "course_profile": "极速平坦 (严苛选拔标准)",
            "elevation_gain_m": 45,
            "avg_temp_c": 13,
            "is_template": True,
        },
        {
            "event_name": "通用国际金标马拉松",
            "race_level": "国际金标",
            "default_distance_type": "fm",
            "course_profile": "城市标准赛道",
            "elevation_gain_m": 65,
            "avg_temp_c": 15,
            "is_template": True,
        },
        {
            "event_name": "通用大众认证城马",
            "race_level": "国内 A 类认证",
            "default_distance_type": "hm",
            "course_profile": "大众友好选拔标准",
            "elevation_gain_m": 40,
            "avg_temp_c": 16,
            "is_template": True,
        },
        {
            "event_name": "跑团赛前长距离模拟拉练",
            "race_level": "跑团内部拉练",
            "default_distance_type": "custom",
            "course_profile": "免证书初审 · 侧重控速与带队",
            "elevation_gain_m": 30,
            "avg_temp_c": 15,
            "is_template": True,
        },
    ])
    return presets


# ─────────────────────────────────────────────────────────────────────────────
# 2. EVENT CALIBRATION & STRICTNESS RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_distance_type(
    distance_type: Optional[str],
    event_name: Optional[str] = None,
    custom_distance_km: Optional[float] = None,
) -> str:
    dt = (distance_type or "").strip().lower()
    if dt in ("fm", "full", "marathon", "全马", "全程马拉松"):
        return "fm"
    if dt in ("hm", "half", "半马", "半程马拉松"):
        return "hm"
    if dt in ("10k", "10km", "10公里"):
        return "10k"
    if dt in ("custom", "lsd", "拉练", "自定义"):
        return "custom"
    if custom_distance_km and custom_distance_km > 0:
        if abs(custom_distance_km - 42.195) <= 1.2:
            return "fm"
        if abs(custom_distance_km - 21.0975) <= 1.2:
            return "hm"
        if abs(custom_distance_km - 10.0) <= 0.8:
            return "10k"
        return "custom"
    ev = (event_name or "").lower()
    if "拉练" in ev or "约跑" in ev or "lsd" in ev:
        return "custom"
    if "10公里" in ev or "10k" in ev:
        return "10k"
    if "半程" in ev or "半马" in ev or "上半马" in ev or "half" in ev:
        return "hm"
    return "fm"


def resolve_event_calibration(
    event_name: Optional[str],
    distance_type: str = "fm",
    custom_distance_km: Optional[float] = None,
    race_date: Optional[str] = None,
    allow_web_search: bool = True,
) -> Dict[str, Any]:
    """
    Resolves official race metadata and computes dynamic calibration factors:
    - strictness_tier: 'platinum' | 'gold' | 'mass' | 'club_lsd'
    - target_gun_error_sec: ±30s (platinum), ±45s (gold), ±60s (mass/club_lsd)
    - sigma_ideal_sec: per-km GAP std-dev benchmark for 90+ score
    - extra_margin_fm_sec: additional safety margin (scaled by distance) for Platinum / Altitude / Heat
    """
    clean_name = (event_name or "").strip() or (
        "跑团赛前长距离模拟拉练" if distance_type == "custom" else "上海马拉松"
    )
    dist_km = (
        float(custom_distance_km)
        if (distance_type == "custom" and custom_distance_km and custom_distance_km >= 3.0)
        else NOMINAL_DISTANCES_KM.get(distance_type, 42.195)
    )
    if distance_type == "custom" and (not custom_distance_km or custom_distance_km < 3.0):
        dist_km = 30.0

    dist_scale = dist_km / 42.195

    # Universal templates shortcut (0ms, no external call)
    lower_name = clean_name.lower()
    if "拉练" in lower_name or "约跑" in lower_name or distance_type == "custom" and "马拉松" not in lower_name:
        race_info = {
            "race_distance_km": dist_km,
            "elevation_gain_m": round(dist_km * 1.0),
            "max_altitude_m": 25,
            "race_level": "跑团内部拉练",
            "course_profile": "常规训练路线",
            "avg_temp_c": 15,
            "humidity_pct": 65,
            "cutoff_notes": "按跑团分组配速要求执行",
            "custom_notes": "免组委会官方证书初审，重点考察当期控速稳健度与带队实战经验",
        }
        source = "template"
        official_name = clean_name
    elif clean_name.startswith("通用"):
        if "白金" in clean_name:
            lvl, gain, prof = "世界白金标", 45, "极速平坦 (严苛选拔标准)"
        elif "金标" in clean_name:
            lvl, gain, prof = "国际金标", 65, "城市标准赛道"
        else:
            lvl, gain, prof = "国内 A 类认证", 55, "大众城市赛道"
        race_info = {
            "race_distance_km": dist_km,
            "elevation_gain_m": round(gain * dist_scale),
            "max_altitude_m": 30,
            "race_level": lvl,
            "course_profile": prof,
            "avg_temp_c": 14,
            "humidity_pct": 65,
            "cutoff_notes": "全马6小时15分 / 半马3小时10分",
            "custom_notes": f"{lvl}通用评估基准",
        }
        source = "template"
        official_name = clean_name
    else:
        rtype_hint = {
            "fm": "全程马拉松",
            "hm": "半程马拉松",
            "10k": "10公里",
            "custom": f"{round(dist_km, 1)}公里路跑",
        }.get(distance_type, "全程马拉松")
        intel = fetch_race_intelligence(
            race_name=clean_name,
            race_type=rtype_hint,
            race_date=race_date,
            use_cache=True,
            allow_web_search=allow_web_search,
        )
        race_info = dict(intel.get("race_info") or {})
        official_name = intel.get("official_event_name") or clean_name
        source = intel.get("source") or "official_catalog"
        # Align nominal distance with user's chosen distance_type (e.g. evaluating HM pacer on a marathon event)
        if distance_type in ("fm", "hm", "10k"):
            orig_dist = float(race_info.get("race_distance_km") or dist_km)
            if abs(orig_dist - dist_km) > 3.0 and orig_dist > 0:
                orig_gain = float(race_info.get("elevation_gain_m") or 50.0)
                race_info["elevation_gain_m"] = max(10, round(orig_gain * (dist_km / orig_dist)))
            race_info["race_distance_km"] = dist_km
        elif distance_type == "custom":
            race_info["race_distance_km"] = dist_km

    race_level = str(race_info.get("race_level") or "国内 A 类认证")
    elev_gain_m = float(race_info.get("elevation_gain_m") or 45.0)
    max_alt_m = float(race_info.get("max_altitude_m") or 30.0)
    avg_temp_c = float(race_info.get("avg_temp_c") or 15.0)
    humidity_pct = float(race_info.get("humidity_pct") or 65.0)
    course_profile = str(race_info.get("course_profile") or "平坦")

    if distance_type == "custom" or "拉练" in race_level:
        strictness_tier = "club_lsd"
        strictness_label = "跑团模拟拉练标准"
        target_gun_error_sec = 60
        sigma_ideal_sec = 6.5
        tier_margin_fm_adj = -360  # -6 min vs Gold
        min_cert_count_2y = 0
    elif "白金" in race_level or "大满贯" in race_level or "platinum" in race_level.lower():
        strictness_tier = "platinum"
        strictness_label = "世界白金标严苛标准"
        target_gun_error_sec = 30
        sigma_ideal_sec = 4.0
        tier_margin_fm_adj = 300  # +5 min extra PB margin vs Gold
        min_cert_count_2y = 2
    elif "金标" in race_level or "银标" in race_level or "gold" in race_level.lower():
        strictness_tier = "gold"
        strictness_label = "国际金标选拔标准"
        target_gun_error_sec = 45
        sigma_ideal_sec = 5.0
        tier_margin_fm_adj = 0
        min_cert_count_2y = 1
    else:
        strictness_tier = "mass"
        strictness_label = "大众认证赛事标准"
        target_gun_error_sec = 60
        sigma_ideal_sec = 6.0
        tier_margin_fm_adj = -180  # -3 min relief vs Gold
        min_cert_count_2y = 1

    grade_m_per_km = elev_gain_m / max(5.0, dist_km)
    hilly_course = bool(
        grade_m_per_km >= 2.8
        or (dist_km >= 35.0 and elev_gain_m >= 120.0)
        or any(k in course_profile for k in ("中等坡度", "丘陵", "多爬升"))
    )
    sub_plateau = bool(max_alt_m >= 1000.0)
    heat_stress = bool((avg_temp_c >= 18.0 and humidity_pct >= 68.0) or avg_temp_c >= 20.0)

    env_margin_fm_adj = 0
    if sub_plateau:
        env_margin_fm_adj += 420  # +7 min on FM for sub-plateau (e.g. Lanzhou 1530m)
    if heat_stress:
        env_margin_fm_adj += 300  # +5 min on FM for warm/humid conditions
    if hilly_course:
        env_margin_fm_adj += 180  # +3 min on FM for bridge/hill courses (e.g. Wuhan/Hangzhou/Boston)

    tags: List[str] = []
    if strictness_tier == "platinum":
        tags.append(f"🏆 {race_level} · 冲线误差要求 ±{target_gun_error_sec}s")
    elif strictness_tier == "gold":
        tags.append(f"🥇 {race_level} · 冲线误差要求 ±{target_gun_error_sec}s")
    elif strictness_tier == "club_lsd":
        tags.append("🐰 跑团拉练模式 · 免官方完赛证书初审")
    else:
        tags.append(f"🏅 {race_level} · 冲线误差 ±{target_gun_error_sec}s")

    if hilly_course:
        tags.append(f"🌉 起伏坡道 (D+ {int(round(elev_gain_m))}m) · 爬升肌耐力加权")
    else:
        tags.append(f"🛣️ 平坦赛道 (D+ {int(round(elev_gain_m))}m) · 纯匀速节拍考核")

    if sub_plateau:
        tags.append(f"🏔️ 亚高原海拔 ({int(round(max_alt_m))}m) · 实力冗余上浮")
    if heat_stress:
        tags.append(f"☀️ 温湿热应激 ({int(round(avg_temp_c))}℃/{int(round(humidity_pct))}%) · 防漂移加严")

    return {
        "event_name": official_name,
        "input_event_name": clean_name,
        "distance_type": distance_type,
        "distance_km": round(dist_km, 3),
        "distance_scale": round(dist_scale, 3),
        "source": source,
        "race_level": race_level,
        "strictness_tier": strictness_tier,
        "strictness_label": strictness_label,
        "target_gun_error_sec": target_gun_error_sec,
        "sigma_ideal_sec": sigma_ideal_sec,
        "tier_margin_fm_adj": tier_margin_fm_adj,
        "env_margin_fm_adj": env_margin_fm_adj,
        "total_margin_adj_sec": int(round((tier_margin_fm_adj + env_margin_fm_adj) * dist_scale)),
        "min_cert_count_2y": min_cert_count_2y,
        "hilly_course": hilly_course,
        "sub_plateau": sub_plateau,
        "heat_stress": heat_stress,
        "elevation_gain_m": int(round(elev_gain_m)),
        "max_altitude_m": int(round(max_alt_m)),
        "avg_temp_c": round(avg_temp_c, 1),
        "humidity_pct": int(round(humidity_pct)),
        "course_profile": course_profile,
        "weather_notes": race_info.get("weather_notes") or "",
        "custom_notes": race_info.get("custom_notes") or "",
        "calibration_tags": tags,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. RUNNER BASE EVIDENCE EXTRACTION (SHARED ACROSS ALL GROUPS)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_any_seconds(val: Any) -> int:
    if val is None or val == "":
        return 0
    if isinstance(val, (int, float)):
        return max(0, int(round(float(val))))
    parsed = parse_time_str_to_seconds(str(val))
    if parsed:
        return parsed
    try:
        return max(0, int(round(float(str(val).strip()))))
    except Exception:
        return 0


def _mad_trim_paces(paces: List[int], max_trim: int = 2) -> List[int]:
    """
    Trims at most 1-2 extreme single-km traffic-light / water-station pauses using MAD
    so genuine steady road runs aren't ruined by a single intersection stop.
    """
    if len(paces) < 6 or max_trim <= 0:
        return paces
    med = statistics.median(paces)
    abs_devs = [abs(x - med) for x in paces]
    mad = statistics.median(abs_devs)
    threshold = max(18.0, 3.2 * (mad if mad > 1.0 else 4.5))

    indexed = list(enumerate(paces))
    outliers = [i for i, p in indexed if (p - med) > threshold]  # primarily slow stoppages
    if not outliers:
        return paces
    # Trim at most max_trim worst stoppages
    worst = set(sorted(outliers, key=lambda idx: abs(paces[idx] - med), reverse=True)[:max_trim])
    trimmed = [p for i, p in indexed if i not in worst]
    return trimmed if len(trimmed) >= 5 else paces


def _extract_cruise_portfolio(
    activities: List[Dict[str, Any]],
    min_dist_km: float = 12.0,
    lookback_days: int = 90,
) -> Dict[str, Any]:
    """
    Implements '代表作择优制' (Top 3-5 Steady Cruise Portfolio):
    - Filters out interval workouts, trail runs, and short runs
    - Strips warmup (first 1-2 slower km) and cooldown (last 1 slower km)
    - Applies MAD single-km traffic-light outlier protection
    - Ranks candidate runs by GAP std-dev and selects Top 3-5 best cruise sessions
    - Extracts the single best 'showcase_run' with 1km split series for UI & Poster
    """
    cutoff_90d = (date.today() - timedelta(days=lookback_days)).isoformat()
    cutoff_75d = (date.today() - timedelta(days=75)).isoformat()

    candidates: List[Dict[str, Any]] = []
    steady_pace_runs_75d: List[Dict[str, Any]] = []

    for act in (activities or []):
        if act.get("exclude_mode") == "excluded" or act.get("is_excluded"):
            continue
        sp_low = str(act.get("sport_type") or "").lower()
        nm_low = str(act.get("name") or "").lower()
        if "trail" in sp_low or "越野" in nm_low or not LocalStore.is_running_activity(act.get("sport_type")):
            continue

        dist_m = float(act.get("distance_meters") or 0.0)
        dist_km = dist_m / 1000.0
        time_s = float(act.get("moving_time_seconds") or 0.0)
        if dist_km < 5.5 or time_s <= 300:
            continue

        st_date = str(act.get("start_time") or "")[:10]
        avg_pace_sec = time_s / max(0.5, dist_km)
        avg_hr = float(act.get("average_heartrate") or 0.0)

        if st_date >= cutoff_75d and 170.0 <= avg_pace_sec <= 620.0:
            steady_pace_runs_75d.append({
                "date": st_date,
                "distance_km": round(dist_km, 2),
                "pace_sec": round(avg_pace_sec, 1),
                "avg_hr": avg_hr if avg_hr > 60 else None,
                "exclude_mode": act.get("exclude_mode") or "normal",
            })

        if st_date < cutoff_90d or dist_km < min(6.0, min_dist_km):
            continue

        # Skip obvious interval workouts via segment_analysis_json or title keywords
        seg_raw = act.get("segment_analysis_json")
        if seg_raw:
            try:
                seg_obj = json.loads(seg_raw) if isinstance(seg_raw, str) else seg_raw
                if isinstance(seg_obj, dict):
                    has_nested_intervals = any(
                        isinstance(ph, dict) and (ph.get("interval_detail") or ph.get("phase_type") == "intervals")
                        for ph in (seg_obj.get("phases") or [])
                    )
                    if seg_obj.get("interval_detail") or has_nested_intervals:
                        continue
            except Exception:
                pass
        if any(kw in nm_low for kw in ("间歇", "interval", "400m", "800m", "1000m", "法特莱克", "fartlek")):
            continue

        track_obj = None
        if not act.get("splits_data") and not act.get("laps_data") and act.get("gps_track_data"):
            try:
                track_obj = json.loads(act["gps_track_data"]) if isinstance(act["gps_track_data"], str) else act["gps_track_data"]
            except Exception:
                track_obj = None

        primary_laps, km_splits, _ = _extract_normalized_splits(act, track_obj)
        splits = km_splits if len(km_splits) >= 5 else primary_laps
        if len(splits) < 5:
            continue

        # Reject structured interval workouts with RECOVERY/INTERVAL tags
        itypes = {str(s.get("intensity_type") or "AUTO").upper() for s in splits}
        if "INTERVAL" in itypes or ("RECOVERY" in itypes and len([s for s in splits if s.get("intensity_type") == "RECOVERY"]) >= 2):
            continue

        # Keep full-ish km splits (>= 650m)
        valid_splits = [
            s for s in splits
            if float(s.get("distance_m") or 0.0) >= 650.0
            and (s.get("gap_sec") or s.get("pace_sec"))
            and 155 <= int(s.get("gap_sec") or s["pace_sec"]) <= 660
        ]
        if len(valid_splits) < 5:
            continue

        # Strip warmup (first 1-2 splits if >= 14s slower than median) and last cooldown split
        raw_gaps = [int(s.get("gap_sec") or s["pace_sec"]) for s in valid_splits]
        med_gap = statistics.median(raw_gaps)
        start_i = 0
        while start_i < min(2, len(valid_splits) - 5) and (raw_gaps[start_i] - med_gap) >= 14:
            start_i += 1
        end_i = len(valid_splits)
        if end_i - start_i > 5 and (raw_gaps[end_i - 1] - med_gap) >= 16:
            end_i -= 1

        core_splits = valid_splits[start_i:end_i]
        if len(core_splits) < 5:
            continue

        core_gaps = [int(s.get("gap_sec") or s["pace_sec"]) for s in core_splits]
        core_paces = [int(s.get("pace_sec") or s["gap_sec"]) for s in core_splits]

        # Bimodal interval guard (alternating >35s jumps >= 3 times)
        alt_jumps = sum(1 for a, b in zip(core_gaps, core_gaps[1:]) if abs(b - a) >= 35)
        if alt_jumps >= max(3, len(core_gaps) // 2):
            continue

        clean_gaps = _mad_trim_paces(core_gaps, max_trim=2 if len(core_gaps) >= 12 else 1)
        clean_paces = _mad_trim_paces(core_paces, max_trim=2 if len(core_paces) >= 12 else 1)
        sigma_gap = round(statistics.pstdev(clean_gaps), 2) if len(clean_gaps) >= 2 else 0.0
        sigma_raw = round(statistics.pstdev(clean_paces), 2) if len(clean_paces) >= 2 else 0.0

        # 5km block max deviation (in seconds per 5km block relative to mean 5km time)
        block_5k_max_dev_s: Optional[float] = None
        if len(core_paces) >= 10:
            blocks = [sum(core_paces[i : i + 5]) for i in range(0, (len(core_paces) // 5) * 5, 5)]
            if len(blocks) >= 2:
                mean_blk = sum(blocks) / len(blocks)
                block_5k_max_dev_s = round(max(abs(b - mean_blk) for b in blocks), 1)

        # First-half vs second-half split ratio
        mid = len(clean_gaps) // 2
        h1_avg = sum(clean_gaps[:mid]) / max(1, mid)
        h2_avg = sum(clean_gaps[mid:]) / max(1, len(clean_gaps) - mid)
        split_ratio = round(h2_avg / h1_avg, 3) if h1_avg > 0 else 1.0

        splits_series = []
        for idx_s, sp in enumerate(core_splits[:42], start=1):
            p_s = int(sp.get("pace_sec") or sp.get("gap_sec") or 300)
            g_s = int(sp.get("gap_sec") or p_s)
            splits_series.append({
                "km": idx_s,
                "pace_sec": p_s,
                "pace_str": fmt_pace_sec(p_s, with_unit=False),
                "gap_sec": g_s,
                "hr": sp.get("avg_hr"),
            })

        candidates.append({
            "activity_id": act.get("id"),
            "name": act.get("name") or "长距离稳态跑",
            "date": st_date,
            "distance_km": round(dist_km, 2),
            "core_km_count": len(core_splits),
            "avg_pace_sec": int(round(sum(clean_paces) / len(clean_paces))),
            "avg_pace_str": fmt_pace_sec(sum(clean_paces) / len(clean_paces)),
            "avg_hr": int(round(avg_hr)) if avg_hr > 60 else None,
            "sigma_gap_sec": sigma_gap,
            "sigma_raw_sec": sigma_raw,
            "block_5k_max_dev_sec": block_5k_max_dev_s,
            "split_ratio": split_ratio,
            "meets_primary_dist": dist_km >= min_dist_km,
            "splits_series": splits_series,
        })

    # Prefer runs that meet min_dist_km; fall back to shorter steady runs (>=6km) if scarce
    primary_cands = [c for c in candidates if c["meets_primary_dist"]]
    usable_pool = primary_cands if len(primary_cands) >= 2 else candidates

    # Sort by steady quality: lowest sigma_gap_sec, with slight bonus for longer distance
    usable_pool.sort(key=lambda c: (c["sigma_gap_sec"] - min(2.0, c["distance_km"] * 0.06)))
    top_portfolio = usable_pool[:5]

    showcase_run: Optional[Dict[str, Any]] = None
    if top_portfolio:
        # Pick longest run among ultra-steady top_portfolio (within +2.5s of best sigma)
        best_sig = top_portfolio[0]["sigma_gap_sec"]
        steady_elites = [c for c in top_portfolio if c["sigma_gap_sec"] <= best_sig + 2.8]
        showcase_run = max(steady_elites, key=lambda c: c["distance_km"])

    return {
        "portfolio_runs": top_portfolio,
        "portfolio_count": len(top_portfolio),
        "primary_dist_count": len(primary_cands),
        "showcase_run": showcase_run,
        "steady_pace_runs_75d": steady_pace_runs_75d,
    }


def _compute_monthly_mileage_6m(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Computes last 6 calendar months of running mileage for the Pacer Resume Card."""
    today = date.today()
    months: List[Tuple[int, int]] = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()

    buckets: Dict[str, Dict[str, Any]] = {}
    for yy, mm in months:
        key = f"{yy:04d}-{mm:02d}"
        buckets[key] = {
            "month": key,
            "short_label": f"{mm}月",
            "km": 0.0,
            "run_count": 0,
        }

    for act in (activities or []):
        if act.get("exclude_mode") == "excluded" or act.get("is_excluded"):
            continue
        if not LocalStore.is_running_activity(act.get("sport_type")):
            continue
        ym = str(act.get("start_time") or "")[:7]
        if ym in buckets:
            dist_km = float(act.get("distance_meters") or 0.0) / 1000.0
            if dist_km >= 0.5:
                buckets[ym]["km"] += dist_km
                buckets[ym]["run_count"] += 1

    out = []
    for k in sorted(buckets.keys()):
        b = buckets[k]
        b["km"] = round(b["km"], 1)
        out.append(b)
    return out


def _collect_verified_races_and_pacer_history(
    race_plans: List[Dict[str, Any]],
    activities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Merges completed race_plans and watch-detected 42K / 21K / 10K races (deduplicated by date ±1 day).
    Extracts:
    - 24-month completed counts by distance tier
    - Past official pacer history & gun/finish time error precision
    - Upcoming races (for 14-day back-to-back conflict detection & quick UI selection)
    """
    today = date.today()
    cutoff_24m = (today - timedelta(days=730)).isoformat()

    completed_list: List[Dict[str, Any]] = []
    upcoming_list: List[Dict[str, Any]] = []
    covered_dates: List[date] = []

    for rp in (race_plans or []):
        r_date_str = str(rp.get("race_date") or "")[:10]
        r_info = rp.get("race_info") if isinstance(rp.get("race_info"), dict) else {}
        r_type = str(rp.get("race_type") or "")
        r_name = str(rp.get("name") or "路跑赛事")
        comb = f"{r_name} {r_type}".lower()

        is_trail = any(w in comb for w in ("越野", "trail", "utmb", "168", "柴古", "宁海", "武功山", "灵鹫"))
        dist_km = float(r_info.get("race_distance_km") or 0.0)
        if dist_km <= 0:
            if "全马" in comb or "全程" in comb or "marathon" in comb and "半" not in comb and "half" not in comb:
                dist_km = 42.195
            elif "半马" in comb or "半程" in comb or "half" in comb:
                dist_km = 21.0975
            elif "10" in comb:
                dist_km = 10.0
            else:
                dist_km = 42.195 if "马拉松" in comb else 21.0975

        if rp.get("is_completed") or rp.get("status") == "completed" or rp.get("finish_time"):
            fin_sec = _parse_any_seconds(rp.get("finish_time"))
            tgt_sec = _parse_any_seconds(rp.get("target_time"))
            pacer_tgt_sec = _parse_any_seconds(rp.get("pacer_target_time")) or tgt_sec
            was_pacer = bool(rp.get("was_official_pacer"))
            pacer_err_sec = (fin_sec - pacer_tgt_sec) if (was_pacer and fin_sec > 0 and pacer_tgt_sec > 0) else None

            # Infer race_level via catalog if missing in race_info
            r_level = str(r_info.get("race_level") or "")
            if not r_level and not is_trail:
                for cat_entry in OFFICIAL_ROAD_CATALOG:
                    if any(kw.lower() in r_name.lower() for kw in cat_entry["keywords"]):
                        r_level = cat_entry.get("race_level", "")
                        break

            try:
                covered_dates.append(datetime.strptime(r_date_str, "%Y-%m-%d").date())
            except Exception:
                pass

            completed_list.append({
                "id": rp.get("id"),
                "name": r_name,
                "date": r_date_str,
                "distance_km": round(dist_km, 2),
                "is_trail": is_trail,
                "race_level": r_level or ("越野赛" if is_trail else "认证赛事"),
                "finish_sec": fin_sec,
                "finish_time": rp.get("finish_time") or (format_duration(fin_sec) if fin_sec > 0 else ""),
                "target_sec": tgt_sec,
                "diff_sec": (fin_sec - tgt_sec) if (fin_sec > 0 and tgt_sec > 0) else None,
                "was_official_pacer": was_pacer,
                "pacer_target_time": rp.get("pacer_target_time") or "",
                "pacer_error_sec": pacer_err_sec,
                "source": "race_plan",
            })
        else:
            upcoming_list.append({
                "id": rp.get("id"),
                "name": r_name,
                "date": r_date_str,
                "race_type": r_type,
                "distance_km": round(dist_km, 2),
                "target_time": rp.get("target_time") or "",
                "is_trail": is_trail,
            })

    # Auto-supplement unlogged full/half marathon watch activities so newly synced runners aren't penalized
    for act in (activities or []):
        if act.get("exclude_mode") == "excluded" or act.get("is_excluded"):
            continue
        sp_low = str(act.get("sport_type") or "").lower()
        nm_low = str(act.get("name") or "").lower()
        if "trail" in sp_low or not LocalStore.is_running_activity(act.get("sport_type")):
            continue
        dist_km = float(act.get("distance_meters") or 0.0) / 1000.0
        time_s = int(round(float(act.get("moving_time_seconds") or 0.0)))
        elp_s = int(round(float(act.get("elapsed_time_seconds") or time_s)))
        eff_s = elp_s if (elp_s > time_s and (elp_s - time_s) <= 1800) else time_s
        if dist_km < 20.8 or eff_s <= 3000:
            continue

        st_str = str(act.get("start_time") or "")[:10]
        try:
            act_d = datetime.strptime(st_str, "%Y-%m-%d").date()
        except Exception:
            continue
        if any(abs((act_d - cd).days) <= 1 for cd in covered_dates):
            continue

        # Classify watch-detected FM (41.6-44.5km) or HM (20.85-22.2km with race-like effort or race keyword)
        is_watch_fm = 41.6 <= dist_km <= 44.5 and 7500 <= eff_s <= 24000
        is_watch_hm = (
            20.85 <= dist_km <= 22.2
            and 3300 <= eff_s <= 11500
            and (
                any(k in nm_low for k in ("马拉松", "半马", "比赛", "marathon", "race", "半程"))
                or float(act.get("average_heartrate") or 0) >= 148
            )
        )
        if is_watch_fm or is_watch_hm:
            covered_dates.append(act_d)
            nom_d = 42.195 if is_watch_fm else 21.0975
            # Project watch time onto exact 42.195 / 21.0975 if slightly over-distance (GPS 42.5km)
            norm_s = int(round(eff_s * (nom_d / dist_km))) if dist_km > nom_d else eff_s
            completed_list.append({
                "id": act.get("id"),
                "name": act.get("name") or ("全程马拉松实测" if is_watch_fm else "半程马拉松实测"),
                "date": st_str,
                "distance_km": nom_d,
                "is_trail": False,
                "race_level": "手表轨迹核验",
                "finish_sec": norm_s,
                "finish_time": format_duration(norm_s),
                "target_sec": 0,
                "diff_sec": None,
                "was_official_pacer": ("官兔" in nm_low or "配速员" in nm_low or "pacer" in nm_low),
                "pacer_target_time": "",
                "pacer_error_sec": None,
                "source": "watch_activity",
            })

    completed_list.sort(key=lambda r: r.get("date") or "", reverse=True)

    road_24m = [r for r in completed_list if not r["is_trail"] and (r.get("date") or "") >= cutoff_24m]
    fm_24m = [r for r in road_24m if r["distance_km"] >= 40.0]
    hm_24m = [r for r in road_24m if 19.5 <= r["distance_km"] < 40.0]
    official_pacer_races = [r for r in completed_list if r.get("was_official_pacer")]

    return {
        "completed_races": completed_list,
        "upcoming_races": upcoming_list,
        "road_24m_count": len(road_24m),
        "fm_24m_count": len(fm_24m),
        "hm_24m_count": len(hm_24m),
        "best_fm_24m_sec": min([r["finish_sec"] for r in fm_24m if r["finish_sec"] > 0], default=0),
        "best_hm_24m_sec": min([r["finish_sec"] for r in hm_24m if r["finish_sec"] > 0], default=0),
        "official_pacer_races": official_pacer_races,
    }


def _evaluate_group_run_leadership(pacer_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluates accuracy and count of club offline group-run '🐰 领跑兔' check-ins."""
    total_count = len(pacer_records or [])
    verified_count = 0
    on_target_count = 0

    for rec in (pacer_records or []):
        pace_str = rec.get("act_avg_pace_str") or rec.get("manual_pace_str")
        actual_pace_sec = parse_pace_str_to_sec(pace_str)
        if not actual_pace_sec and rec.get("act_distance_meters") and rec.get("act_moving_time_seconds"):
            dk = float(rec["act_distance_meters"]) / 1000.0
            if dk >= 2.0:
                actual_pace_sec = int(round(float(rec["act_moving_time_seconds"]) / dk))

        if rec.get("activity_id") and actual_pace_sec:
            verified_count += 1
            pg_txt = f"{rec.get('pace_group') or ''} {rec.get('pace_requirement') or ''}"
            rng = parse_pace_range_to_sec(pg_txt)
            if rng:
                lo, hi = rng
                if "内" in pg_txt and lo == hi:
                    if actual_pace_sec <= hi + 10:
                        on_target_count += 1
                elif "+" in pg_txt and lo == hi:
                    if actual_pace_sec >= lo - 10:
                        on_target_count += 1
                elif (lo - 12) <= actual_pace_sec <= (hi + 12):
                    on_target_count += 1
            else:
                on_target_count += 1

    return {
        "club_pacer_total_count": total_count,
        "club_pacer_verified_count": verified_count,
        "club_pacer_on_target_count": on_target_count,
    }


def build_runner_pacer_context(
    uid: str,
    viewer_uid: Optional[str] = None,
    club_id: Optional[str] = None,
    preloaded_activities: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Loads and pre-computes all distance-independent runner metrics once,
    enabling sub-millisecond evaluation across all 11 pacer groups.
    """
    canonical_uid = LocalStore.resolve_user_id(uid)
    profile = LocalStore.get_profile(canonical_uid) or {}
    can_view_confidential = True
    if viewer_uid:
        canonical_viewer = LocalStore.resolve_user_id(viewer_uid)
        if canonical_viewer != canonical_uid:
            can_view_confidential = LocalStore.can_view_confidential_runner_data(
                canonical_viewer, canonical_uid, club_id=club_id
            )

    activities = (
        preloaded_activities
        if preloaded_activities is not None
        else LocalStore.get_recent_activities(canonical_uid, limit=240)
    )
    health_trend = LocalStore.get_health_trend_30d(canonical_uid)
    v_meta = LocalStore.resolve_verified_runner_profile_and_pbs(
        canonical_uid, profile=profile, recent_acts=activities, query_activities=False
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

    # Compute 90d CTL / ATL / TSB
    daily_trimp_map: Dict[str, float] = {}
    for i in range(90, -1, -1):
        d_str = (date.today() - timedelta(days=i)).isoformat()
        daily_trimp_map[d_str] = 0.0
    for act in (activities or []):
        if (act.get("exclude_mode") or "normal") == "excluded":
            continue
        st = str(act.get("start_time") or "")[:10]
        if st in daily_trimp_map:
            daily_trimp_map[st] += float(act.get("trimp") or 0.0)
    ctl_series = compute_ctl_atl_tsb(sorted(daily_trimp_map.items(), key=lambda x: x[0]))
    latest_load = ctl_series[-1] if ctl_series else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}

    canova_matrix = compute_canova_athlete_matrix(
        profile=clean_profile,
        activities=activities,
        current_ctl=float(latest_load["ctl"]),
        current_tsb=float(latest_load["tsb"]),
        health_trend=health_trend,
    )
    race_preds = predict_realistic_race_times(canova_matrix)

    race_plans = LocalStore.get_race_plans(canonical_uid)
    race_history = _collect_verified_races_and_pacer_history(race_plans, activities)
    club_pacer_records = LocalStore.get_user_group_run_pacer_records(canonical_uid)
    club_leadership = _evaluate_group_run_leadership(club_pacer_records)
    monthly_6m = _compute_monthly_mileage_6m(activities)

    # Longest single activity duration in last 56 days (critical for 500-615 slow finisher pacers)
    cutoff_56d = (date.today() - timedelta(days=56)).isoformat()
    longest_duration_56d_sec = 0
    active_weeks_8w = set()
    cutoff_56d_dt = date.today() - timedelta(days=56)
    for act in (activities or []):
        if (act.get("exclude_mode") or "normal") == "excluded":
            continue
        if not LocalStore.is_running_activity(act.get("sport_type")):
            continue
        st = str(act.get("start_time") or "")[:10]
        if st >= cutoff_56d:
            dur = int(round(float(act.get("moving_time_seconds") or 0.0)))
            if dur > longest_duration_56d_sec:
                longest_duration_56d_sec = dur
            try:
                dt_obj = datetime.strptime(st, "%Y-%m-%d").date()
                if dt_obj >= cutoff_56d_dt:
                    iso_y, iso_w, _ = dt_obj.isocalendar()
                    active_weeks_8w.add((iso_y, iso_w))
            except Exception:
                pass

    return {
        "uid": canonical_uid,
        "profile": clean_profile,
        "raw_profile": profile,
        "can_view_confidential": can_view_confidential,
        "hide_biometrics": bool(profile.get("hide_biometrics")),
        "age": get_age_from_dob(profile.get("date_of_birth")),
        "activities": activities,
        "ctl": float(latest_load["ctl"]),
        "atl": float(latest_load["atl"]),
        "tsb": float(latest_load["tsb"]),
        "canova_matrix": canova_matrix,
        "race_predictions": race_preds,
        "race_history": race_history,
        "club_leadership": club_leadership,
        "monthly_mileage_6m": monthly_6m,
        "longest_duration_56d_sec": longest_duration_56d_sec,
        "active_weeks_8w": len(active_weeks_8w),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. SINGLE-GROUP QUANTITATIVE SCORING & DUAL-GATEKEEPER ARBITRATION
# ─────────────────────────────────────────────────────────────────────────────

def _predict_time_for_distance(ctx: Dict[str, Any], dist_km: float) -> int:
    """
    Predicts current realistic race time (seconds) for any distance_km.
    Accounts for polarized aerobic training (high weekly volume + low-%HRR steady runs
    without recent all-out races) while preserving strict detraining penalties when volume is low.
    """
    preds = ctx["race_predictions"]
    matrix = ctx["canova_matrix"]
    prof = ctx["profile"]
    eff_v = float(matrix.get("effective_vdot") or 0.0)
    if eff_v <= 0:
        return 0

    wk_km = float(matrix.get("weekly_km_avg") or 0.0)
    longest_km = float(matrix.get("longest_km_42d") or 0.0)
    lr25 = int(matrix.get("long_runs_25k_42d") or 0)
    peak_end_v = float(matrix.get("peak_endurance_vdot") or prof.get("peak_endurance_vdot") or 0.0)

    # Polarized base-training HR efficiency calibration (only unlocked when current volume & long runs are solid!)
    aerobic_eff_v = eff_v
    if wk_km >= 32.0 and longest_km >= 18.0:
        rest_hr = float(prof.get("resting_heart_rate") or 56.0)
        max_hr = float(prof.get("max_heart_rate") or 190.0)
        hrr = max(30.0, max_hr - rest_hr)
        cutoff_42d = (date.today() - timedelta(days=42)).isoformat()
        hr_vdots: List[float] = []
        for act in (ctx.get("activities") or []):
            if (act.get("exclude_mode") or "normal") == "excluded":
                continue
            if not LocalStore.is_running_activity(act.get("sport_type")):
                continue
            st = str(act.get("start_time") or "")[:10]
            if st < cutoff_42d:
                continue
            d_m = float(act.get("distance_meters") or 0.0)
            t_s = float(act.get("moving_time_seconds") or 0.0)
            ahr = float(act.get("average_heartrate") or 0.0)
            if d_m < 10000.0 or t_s <= 600.0 or ahr < 110.0:
                continue
            pct_hrr = (ahr - rest_hr) / hrr
            if 0.60 <= pct_hrr <= 0.85:
                v_m_min = (d_m / t_s) * 60.0
                vo2_sub = -4.60 + 0.182258 * v_m_min + 0.000104 * (v_m_min ** 2)
                if vo2_sub > 15.0:
                    est_v = vo2_sub / (0.08 + 0.92 * pct_hrr)
                    hr_vdots.append(est_v)
        if len(hr_vdots) >= 2:
            top_hr_v = sorted(hr_vdots, reverse=True)[:4]
            avg_hr_v = sum(top_hr_v) / len(top_hr_v)
            cap_v = max(peak_end_v, eff_v + 5.5) if peak_end_v > 0 else (eff_v + 4.5)
            aerobic_eff_v = max(eff_v, min(cap_v, 0.30 * eff_v + 0.70 * avg_hr_v))

    # Endurance conversion decay based on volume & 25km+ long runs
    fm_decay = float(preds.get("marathon_decay_vdot") or 2.2)
    if wk_km >= 65.0 and longest_km >= 29.0 and lr25 >= 3:
        fm_decay = min(fm_decay, 1.3)
    elif wk_km >= 50.0 and longest_km >= 26.0 and lr25 >= 2:
        fm_decay = min(fm_decay, 1.8)

    if abs(dist_km - 42.195) <= 1.2:
        base_fm_s = int(preds.get("marathon_seconds") or vdot_to_race_time(max(16.0, eff_v - 2.2), 42195.0))
        hr_fm_s = vdot_to_race_time(max(16.0, aerobic_eff_v - fm_decay), 42195.0)
        return min(base_fm_s, hr_fm_s)
    if abs(dist_km - 21.0975) <= 1.2:
        base_hm_s = _parse_any_seconds(preds.get("half_marathon")) or vdot_to_race_time(max(16.0, eff_v - 1.0), 21097.5)
        hr_hm_s = vdot_to_race_time(max(16.0, aerobic_eff_v - fm_decay * 0.45), 21097.5)
        return min(base_hm_s, hr_hm_s)
    if abs(dist_km - 10.0) <= 0.8:
        base_10k_s = _parse_any_seconds(preds.get("ten_k")) or vdot_to_race_time(max(16.0, eff_v - 0.3), 10000.0)
        hr_10k_s = vdot_to_race_time(max(16.0, aerobic_eff_v - 0.3), 10000.0)
        return min(base_10k_s, hr_10k_s)

    # Interpolate realistic endurance decay for custom LSD distances (e.g., 25km / 30km)
    fm_v = max(float(preds.get("marathon_effective_vdot") or 0.0), aerobic_eff_v - fm_decay)
    ratio = max(0.0, min(1.0, (dist_km - 10.0) / (42.195 - 10.0)))
    interp_v = aerobic_eff_v - (aerobic_eff_v - fm_v) * ratio
    return vdot_to_race_time(max(16.0, interp_v), dist_km * 1000.0)


def _best_certified_time_for_distance(ctx: Dict[str, Any], distance_type: str, dist_km: float) -> Tuple[int, str]:
    """
    Resolves runner's best verified certificate/PB time for the target distance category.
    For FM official pacers, requires actual FM PB / 24m FM finish (cannot extrapolate 5K PB to FM cert!).
    For HM / 10K, accepts same-distance PB or longer-distance official PB pace equivalent.
    """
    prof = ctx["profile"]
    rh = ctx["race_history"]
    mp = int(prof.get("marathon_pb") or 0)
    hp = int(prof.get("half_pb") or 0)
    tk = int(prof.get("ten_k_pb") or 0)

    best_fm_24m = int(rh.get("best_fm_24m_sec") or 0)
    best_hm_24m = int(rh.get("best_hm_24m_sec") or 0)

    if distance_type == "fm":
        cands = [(s, src) for s, src in [(best_fm_24m, "近2年全马完赛"), (mp, "档案全马PB")] if s > 0]
        if not cands:
            return 0, "暂无全马完赛证书"
        return min(cands, key=lambda x: x[0])

    if distance_type == "hm":
        cands = [(s, src) for s, src in [(best_hm_24m, "近2年半马完赛"), (hp, "档案半马PB")] if s > 0]
        if mp > 0:
            # Official marathon certificate also qualifies for half marathon pacer (~0.478x FM time)
            cands.append((int(round(mp * 0.478)), "全马PB折算资格"))
        if not cands:
            return 0, "暂无半马/全马完赛证书"
        return min(cands, key=lambda x: x[0])

    if distance_type == "10k":
        cands = []
        if tk > 0:
            cands.append((tk, "档案10K PB"))
        if hp > 0:
            cands.append((int(round(hp * 0.455)), "半马PB折算资格"))
        if mp > 0:
            cands.append((int(round(mp * 0.218)), "全马PB折算资格"))
        if not cands:
            return 0, "暂无10K及以上证书"
        return min(cands, key=lambda x: x[0])

    # Custom distance: project from best endurance VDOT
    best_v = float(prof.get("peak_endurance_vdot") or prof.get("peak_vdot") or 0.0)
    if best_v > 0:
        return vdot_to_race_time(best_v, dist_km * 1000.0), "历史跑力折算"
    return 0, "未设置PB"


def _score_single_group(
    ctx: Dict[str, Any],
    calib: Dict[str, Any],
    portfolio: Dict[str, Any],
    group_spec: Dict[str, Any],
    target_race_date: Optional[str] = None,
) -> Dict[str, Any]:
    dist_km = float(calib["distance_km"])
    dist_scale = float(calib["distance_scale"])
    distance_type = calib["distance_type"]
    strictness = calib["strictness_tier"]
    target_sec = int(group_spec["target_sec"])
    target_pace_sec = target_sec / max(1.0, dist_km)
    group_tier = group_spec.get("tier", "mass")

    # ── Required Margins (scaled from FM baseline + event calibration) ──
    if group_tier == "elite":
        base_cert_fm_sec = 900   # 15m Gold baseline (+5m = 20m Platinum)
        ideal_margin_fm_sec = 1680  # 28m for 95+ score
    elif group_tier == "advanced":
        base_cert_fm_sec = 1140  # 19m Gold (+5m = 24m Platinum)
        ideal_margin_fm_sec = 2100  # 35m
    elif group_tier == "mass":
        base_cert_fm_sec = 1200  # 20m Gold (+5m = 25m Platinum)
        ideal_margin_fm_sec = 2520  # 42m
    else:
        base_cert_fm_sec = 1500  # 25m Gold (+5m = 30m Platinum)
        ideal_margin_fm_sec = 3000  # 50m

    req_cert_margin_sec = max(
        int(round(300 * dist_scale)),
        int(round(base_cert_fm_sec * dist_scale)) + int(calib["total_margin_adj_sec"]),
    )
    ideal_margin_sec = max(
        req_cert_margin_sec + int(round(360 * dist_scale)),
        int(round(ideal_margin_fm_sec * dist_scale)) + int(calib["total_margin_adj_sec"]),
    )
    min_fitness_margin_sec = max(
        int(round(240 * dist_scale)),
        int(round(req_cert_margin_sec * 0.68)),
    )

    pred_sec = _predict_time_for_distance(ctx, dist_km)
    cert_sec, cert_source = _best_certified_time_for_distance(ctx, distance_type, dist_km)

    pred_margin_sec = (target_sec - pred_sec) if pred_sec > 0 else -99999
    cert_margin_sec = (target_sec - cert_sec) if cert_sec > 0 else -99999

    # ── Dimension 1: Speed & VDOT Margin (25%) ──
    def _margin_to_pts(margin_s: int, min_req_s: int, ideal_s: int) -> float:
        if margin_s <= -90000:
            return 15.0
        if margin_s < 0:
            return max(12.0, 35.0 + (margin_s / max(60.0, float(min_req_s))) * 20.0)
        if margin_s < min_req_s:
            return 38.0 + (margin_s / max(60.0, float(min_req_s))) * 24.0  # 38 -> 62
        if margin_s <= ideal_s:
            span = max(60.0, float(ideal_s - min_req_s))
            return 62.0 + ((margin_s - min_req_s) / span) * 32.0          # 62 -> 94
        return min(98.0, 94.0 + (margin_s - ideal_s) / max(180.0, ideal_s * 0.5) * 4.0)

    pred_pts = _margin_to_pts(pred_margin_sec, min_fitness_margin_sec, ideal_margin_sec)
    cert_pts = (
        pred_pts
        if strictness == "club_lsd"
        else _margin_to_pts(cert_margin_sec, req_cert_margin_sec, ideal_margin_sec)
    )

    # HR reserve comfort at target pace
    prof = ctx["profile"]
    rest_hr = float(prof.get("resting_heart_rate") or 58.0)
    max_hr = float(prof.get("max_heart_rate") or 190.0)
    hrr = max(25.0, max_hr - rest_hr)
    near_pace_hrs = [
        float(r["avg_hr"])
        for r in portfolio["steady_pace_runs_75d"]
        if r.get("avg_hr") and abs(float(r["pace_sec"]) - target_pace_sec) <= 14.0 and float(r["distance_km"]) >= 8.0
    ]
    if near_pace_hrs:
        avg_target_hr = sum(near_pace_hrs) / len(near_pace_hrs)
        pct_hrr = (avg_target_hr - rest_hr) / hrr
        if pct_hrr <= 0.74:
            hr_comfort_pts = 95.0
        elif pct_hrr <= 0.80:
            hr_comfort_pts = 82.0
        elif pct_hrr <= 0.86:
            hr_comfort_pts = 62.0
        else:
            hr_comfort_pts = 42.0
        hr_note = f"目标配速心率 {int(round(avg_target_hr))}bpm ({int(round(pct_hrr * 100))}%HRR)"
    else:
        hr_comfort_pts = 0.75 * pred_pts + 0.25 * 75.0
        hr_note = f"目标配速 {fmt_pace_sec(target_pace_sec)}"

    s1_speed_margin = int(round(min(98.0, max(15.0, 0.60 * pred_pts + 0.25 * cert_pts + 0.15 * hr_comfort_pts))))
    pred_margin_min = round(pred_margin_sec / 60.0, 1) if pred_sec > 0 else None
    cert_margin_min = round(cert_margin_sec / 60.0, 1) if cert_sec > 0 else None

    s1_disp = (
        f"当期实力 {format_duration(pred_sec)} (余量 {pred_margin_min:+.0f}分)"
        if pred_sec > 0 and pred_margin_min is not None
        else "暂无近期有效跑力预测"
    )

    # ── Dimension 2: Pacing Stability / Metronome Index (25%) ──
    top_runs = portfolio["portfolio_runs"]
    sigma_ideal = float(calib["sigma_ideal_sec"])
    has_pace_memory = any(
        abs(float(r["pace_sec"]) - target_pace_sec) <= 12.0 and float(r["distance_km"]) >= (6.0 if dist_km <= 12.0 else 10.0)
        for r in portfolio["steady_pace_runs_75d"]
    )
    is_fast_runner_slow_group = bool(
        group_tier == "finisher"
        and pred_sec > 0
        and (target_sec - pred_sec) >= int(round(5400 * dist_scale))  # >90 min faster on FM
    )

    if not top_runs:
        s2_pacing = 35
        sigma_avg = None
        s2_disp = "近90天缺长距离稳态分段数据"
        s2_desc = "缺少 6km+ 稳态路跑分段数据，建议同步佳明/高驰手表完成 2-3 次 15km+ 定速巡航跑以解锁精准节拍评分。"
    else:
        top3 = top_runs[:3]
        # On flat courses emphasize raw pace consistency; on hilly courses use GAP consistency
        sigmas = [float(r["sigma_gap_sec"] if calib["hilly_course"] else (0.5 * r["sigma_raw_sec"] + 0.5 * r["sigma_gap_sec"])) for r in top3]
        sigma_avg = round(sum(sigmas) / len(sigmas), 1)

        if sigma_avg <= sigma_ideal:
            base_s2 = 90.0 + min(8.0, (sigma_ideal - sigma_avg) * 3.0)
        elif sigma_avg <= sigma_ideal + 4.0:
            base_s2 = 76.0 + ((sigma_ideal + 4.0 - sigma_avg) / 4.0) * 14.0
        elif sigma_avg <= sigma_ideal + 10.0:
            base_s2 = 55.0 + ((sigma_ideal + 10.0 - sigma_avg) / 6.0) * 21.0
        else:
            base_s2 = max(28.0, 55.0 - (sigma_avg - sigma_ideal - 10.0) * 2.2)

        # Sample depth adjustment (if only short <12km runs available for FM)
        if dist_km >= 20.0 and portfolio["primary_dist_count"] == 0:
            base_s2 -= 10.0
        elif len(top_runs) == 1:
            base_s2 -= 5.0

        # Split symmetry adjustment (penalize positive split fade > 1.035)
        avg_split_ratio = sum(float(r["split_ratio"]) for r in top3) / len(top3)
        if 0.985 <= avg_split_ratio <= 1.012:
            base_s2 += 3.0
        elif avg_split_ratio > 1.04:
            base_s2 -= min(10.0, (avg_split_ratio - 1.03) * 140.0)

        # Target-pace muscle memory & fast-runner-slow-pacer gait check
        if has_pace_memory:
            base_s2 += 3.0
        elif is_fast_runner_slow_group:
            base_s2 -= 9.0  # Fast runner with zero slow-pace practice risks knee/gait discomfort at 7:30-8:30/km

        # Bonus if past official pacer had tight finish accuracy (<= 30s)
        past_pacer_errs = [
            abs(int(r["pacer_error_sec"]))
            for r in ctx["race_history"]["official_pacer_races"]
            if r.get("pacer_error_sec") is not None
        ]
        if past_pacer_errs and min(past_pacer_errs) <= 30:
            base_s2 += 4.0

        s2_pacing = int(round(min(98.0, max(25.0, base_s2))))
        mem_tag = " · 含目标配速巡航" if has_pace_memory else (" · 缺慢速步态适应" if is_fast_runner_slow_group else "")
        s2_disp = f"代表作波动 ±{sigma_avg}s/km ({len(top3)}场){mem_tag}"
        s2_desc = (
            f"剥离间歇课、热身冷身与红绿灯单点停顿后，近90天最稳巡航代表作每公里波动 ±{sigma_avg}s/km"
            f"（{calib['strictness_label']}满分基准 ≤{sigma_ideal}s/km）。"
        )

    # ── Dimension 3: Training Readiness & Endurance Base (20%) ──
    matrix = ctx["canova_matrix"]
    wk_km = float(matrix.get("weekly_km_avg") or 0.0)
    longest_km = float(matrix.get("longest_km_42d") or 0.0)
    lr16 = int(matrix.get("long_runs_16k_42d") or 0)
    lr25 = int(matrix.get("long_runs_25k_42d") or 0)
    drift_pct = matrix.get("avg_long_run_drift_pct")
    active_wks = int(ctx["active_weeks_8w"])
    longest_dur_s = int(ctx["longest_duration_56d_sec"])

    # Target weekly volume benchmark depends on distance & group tier
    if distance_type == "fm":
        req_wk_km = 70.0 if group_tier == "elite" else (52.0 if group_tier == "advanced" else (42.0 if group_tier == "mass" else 34.0))
        req_long_km = 30.0 if group_tier in ("elite", "advanced") else 25.0
    elif distance_type == "hm":
        req_wk_km = 48.0 if group_tier == "elite" else (36.0 if group_tier in ("advanced", "mass") else 26.0)
        req_long_km = 20.0 if group_tier in ("elite", "advanced") else 16.0
    elif distance_type == "10k":
        req_wk_km = 38.0 if group_tier == "elite" else 25.0
        req_long_km = 14.0 if group_tier == "elite" else 10.0
    else:
        req_wk_km = max(25.0, dist_km * 1.35)
        req_long_km = max(12.0, dist_km * 0.80)

    vol_ratio = min(1.20, wk_km / max(10.0, req_wk_km))
    vol_score = 30.0 + vol_ratio * 58.0  # 100% req -> 88

    long_ratio = min(1.15, longest_km / max(8.0, req_long_km))
    long_score = 25.0 + long_ratio * 60.0 + min(10.0, lr25 * 4.0 if dist_km >= 25.0 else lr16 * 3.0)

    # Time-on-feet coverage for slow finisher pacers (500 / 530 / 600)
    dur_ratio = longest_dur_s / max(1800.0, float(target_sec))
    if group_tier == "finisher" and dist_km >= 21.0:
        dur_score = min(96.0, 30.0 + min(1.0, dur_ratio / 0.68) * 62.0)
        endurance_sub = 0.55 * long_score + 0.45 * dur_score
    else:
        endurance_sub = long_score

    consistency_pts = min(8.0, (active_wks / 7.0) * 8.0)
    drift_penalty = 0.0
    if drift_pct is not None:
        d_val = float(drift_pct)
        if d_val <= 3.8:
            drift_penalty = -4.0  # bonus
        elif d_val > 6.5:
            mult = 1.25 if calib["heat_stress"] else 1.0
            drift_penalty = min(14.0, (d_val - 6.5) * 2.0 * mult)

    # Hilly course blends in climbing_strength dimension from Canova matrix
    dim_map = {d["key"]: int(d["score"]) for d in (matrix.get("dimensions") or [])}
    climb_dim_score = float(dim_map.get("climbing_strength", 55))
    if calib["hilly_course"]:
        raw_s3 = 0.35 * vol_score + 0.35 * endurance_sub + 0.22 * climb_dim_score + consistency_pts - drift_penalty
    else:
        raw_s3 = 0.45 * vol_score + 0.47 * endurance_sub + consistency_pts - drift_penalty

    s3_training = int(round(min(98.0, max(18.0, raw_s3))))
    s3_disp = f"周均 {wk_km:.1f}km · 最长 {longest_km:.1f}km" + (f" · 漂移 {drift_pct:+.1f}%" if drift_pct is not None else "")

    # ── Dimension 4: Race Experience & Execution Track Record (15%) ──
    rh = ctx["race_history"]
    completed_road = [r for r in rh["completed_races"] if not r["is_trail"]]
    if distance_type == "fm":
        rel_24m = rh["fm_24m_count"]
        sub_24m = rh["hm_24m_count"]
    elif distance_type == "hm":
        rel_24m = rh["hm_24m_count"] + rh["fm_24m_count"]
        sub_24m = 0
    else:
        rel_24m = rh["road_24m_count"]
        sub_24m = 0

    if rel_24m == 0 and sub_24m == 0 and not completed_road:
        if strictness == "club_lsd":
            base_s4 = min(84.0, 52.0 + lr25 * 5.5 + lr16 * 2.5)
        else:
            base_s4 = 26.0
    else:
        cnt_pts = min(46.0, rel_24m * 14.5 + sub_24m * 5.0 + min(10.0, len(completed_road) * 2.5))
        # Prestige tier bonus
        has_platinum = any("白金" in str(r.get("race_level") or "") for r in completed_road)
        has_gold = any("金标" in str(r.get("race_level") or "") for r in completed_road)
        lvl_pts = 14.0 if has_platinum else (9.0 if has_gold else 4.0)

        # Same-event course familiarity bonus (+8 pts if runner previously finished this exact event!)
        ev_core = calib["event_name"].replace("马拉松", "").replace("国际", "").strip()
        same_event_done = bool(
            ev_core
            and len(ev_core) >= 2
            and any(ev_core in str(r.get("name") or "") for r in completed_road)
        )
        same_pts = 8.0 if same_event_done else 0.0

        # Historical target execution accuracy
        diffs = [abs(int(r["diff_sec"])) for r in completed_road if r.get("diff_sec") is not None]
        if diffs:
            avg_diff = sum(diffs) / len(diffs)
            exec_pts = 10.0 if avg_diff <= 180 else (6.0 if avg_diff <= 480 else 2.0)
        else:
            exec_pts = 5.0

        base_s4 = 24.0 + cnt_pts + lvl_pts + same_pts + exec_pts

    s4_experience = int(round(min(98.0, max(20.0, base_s4))))
    s4_disp = (
        f"近2年全马 {rh['fm_24m_count']}场 / 半马 {rh['hm_24m_count']}场"
        if distance_type in ("fm", "hm")
        else f"近2年路跑完赛 {rh['road_24m_count']}场"
    )

    # ── Dimension 5: Pacing & Leadership Credentials (10%) ──
    cl = ctx["club_leadership"]
    past_pacer_cnt = len(rh["official_pacer_races"])
    club_pacer_ver = int(cl["club_pacer_verified_count"])
    club_pacer_tot = int(cl["club_pacer_total_count"])
    club_on_tgt = int(cl["club_pacer_on_target_count"])
    fa_type = str(ctx["raw_profile"].get("first_aid_cert_type") or "").strip()

    # Baseline 45 so strong runners without formal badges aren't crushed, scaling to 98 with real credentials
    pacer_hist_pts = min(30.0, past_pacer_cnt * 16.0)
    club_lead_pts = min(22.0, club_pacer_on_target_pts := (club_on_tgt * 7.5 + max(0, club_pacer_tot - club_on_tgt) * 3.5))
    companion_runs = sum(1 for a in (ctx["activities"] or []) if a.get("exclude_mode") == "ignore_vdot")
    comp_pts = min(6.0, companion_runs * 2.0)
    fa_pts = 16.0 if fa_type in ("medical_pro", "aha") else (13.0 if fa_type == "red_cross" else 0.0)

    s5_leadership = int(round(min(98.0, 42.0 + pacer_hist_pts + club_lead_pts + comp_pts + fa_pts)))
    s5_tags = []
    if past_pacer_cnt > 0:
        s5_tags.append(f"往届官兔 {past_pacer_cnt}次")
    if club_pacer_tot > 0:
        s5_tags.append(f"约跑领跑 {club_pacer_tot}次")
    if fa_type in FIRST_AID_LABELS and fa_type:
        s5_tags.append(FIRST_AID_LABELS[fa_type].split(" ")[-1])
    s5_disp = " · ".join(s5_tags) if s5_tags else (f"陪跑慢摇 {companion_runs}次" if companion_runs > 0 else "待积累领跑/急救履历")

    # ── Dimension 6: Autonomic Recovery & Reliability (5%, Privacy-Safe) ──
    rec_dim = next((d for d in (matrix.get("dimensions") or []) if d["key"] == "autonomic_recovery"), None)
    s6_recovery = int(rec_dim["score"]) if rec_dim else 60
    if ctx["hide_biometrics"] and not ctx["can_view_confidential"]:
        s6_disp = f"隐私保护已脱敏 · 负荷状态 TSB {ctx['tsb']:+.1f}"
        s6_desc = "该队员已开启生理数据保密，仅展示训练负荷平衡度，不暴露原始 HRV 与静息心率。"
    else:
        s6_disp = rec_dim["display_value"] if rec_dim else f"TSB {ctx['tsb']:+.1f}"
        s6_desc = rec_dim["desc"] if rec_dim else "基于近 30 天生理指标与 TSB 评估的赛前出战稳定性。"

    # ── Gatekeepers & Barrel Penalty ──
    raw_weighted = (
        0.25 * s1_speed_margin
        + 0.25 * s2_pacing
        + 0.20 * s3_training
        + 0.15 * s4_experience
        + 0.10 * s5_leadership
        + 0.05 * s6_recovery
    )
    weak_penalty = sum(0.40 * max(0.0, 55.0 - float(sc)) for sc in (s1_speed_margin, s2_pacing, s3_training))
    penalized_score = max(15.0, raw_weighted - weak_penalty)

    gate_cap = 100
    gates: Dict[str, Dict[str, Any]] = {}

    # Gate 1: Current Fitness Safety Gate (防吃老本硬顶崩盘)
    # Only treat as low-load休整期 when BOTH Canova matrix flags recovery AND actual training volume/long run is below 65% of target pacer need
    is_rec_phase = bool(
        matrix.get("is_recovery_phase")
        and (wk_km < req_wk_km * 0.65 or longest_km < req_long_km * 0.65)
    )
    if pred_sec <= 0 or pred_margin_sec < min_fitness_margin_sec:
        gate_cap = min(gate_cap, 58)
        need_str = format_duration(target_sec - min_fitness_margin_sec)
        gates["fitness_gate"] = {
            "status": "fail",
            "badge": "❌ 当期体能余量不足",
            "detail": (
                f"当期预测完赛 {format_duration(pred_sec) if pred_sec > 0 else '未知'}，距离 {group_spec['label']} 安全底线（需快于 {need_str}）余量不足，硬顶存在后程掉速/抽筋风险。"
            ),
        }
    elif is_rec_phase:
        gate_cap = min(gate_cap, 68)
        gates["fitness_gate"] = {
            "status": "warn",
            "badge": "🩹 处于恢复/休整期",
            "detail": "近期训练量处于低负荷休整阶段，虽保留历史高水平底座，建议先恢复 4-6 周规律长距离后再出战官兔。",
        }
    elif ctx["tsb"] < -35.0:
        gate_cap = min(gate_cap, 74)
        gates["fitness_gate"] = {
            "status": "warn",
            "badge": f"⚠️ 短期疲劳偏深 (TSB {ctx['tsb']:+.1f})",
            "detail": "当前训练疲劳累积较深，赛前务必执行 7-10 天减量调整以释放超量恢复。",
        }
    else:
        gates["fitness_gate"] = {
            "status": "pass",
            "badge": f"✅ 当期体能达标 (余量 +{int(round(pred_margin_sec / 60.0))}分)",
            "detail": f"当期耐力修正预测 {format_duration(pred_sec)}，相对目标组别具备充沛有氧安全余量。",
        }

    # Gate 2: Official Certificate Gate (区分官兔初审 vs 私兔/拉练兔)
    req_cert_time_str = format_duration(target_sec - req_cert_margin_sec)
    is_dark_horse_qual = bool(
        gates["fitness_gate"]["status"] == "pass"
        and (
            cert_sec == 0
            or pred_margin_sec >= req_cert_margin_sec
            or (cert_sec > 0 and cert_margin_sec >= req_cert_margin_sec and rel_24m < calib["min_cert_count_2y"])
        )
    )
    if strictness == "club_lsd":
        gates["cert_gate"] = {
            "status": "exempt",
            "badge": "🆓 跑团拉练免证书初审",
            "detail": "内部拉练领跑不卡官方田协证书门槛，以当期真实跑力与控速稳健度为准。",
        }
    elif cert_sec > 0 and cert_margin_sec >= req_cert_margin_sec and rel_24m >= calib["min_cert_count_2y"]:
        gates["cert_gate"] = {
            "status": "pass",
            "badge": f"✅ 组委会证书达标 ({cert_source} {format_duration(cert_sec)})",
            "detail": f"满足{calib['strictness_label']}完赛证书余量要求（门槛 ≤ {req_cert_time_str}，近2年达标场次 {rel_24m} 场）。",
        }
    elif is_dark_horse_qual:
        # 黑马缺证型: strong current fitness, missing qualifying certificate or 2yr race count!
        gate_cap = min(gate_cap, 75)
        reason_detail = (
            f"近2年同项目完赛仅 {rel_24m} 场（白金标要求 ≥{calib['min_cert_count_2y']} 场）"
            if (cert_sec > 0 and cert_margin_sec >= req_cert_margin_sec and rel_24m < calib["min_cert_count_2y"])
            else f"当前最佳证书 {format_duration(cert_sec) if cert_sec > 0 else '暂无'}，未达组委会初审线（通常要求 ≤ {req_cert_time_str}）"
        )
        gates["cert_gate"] = {
            "status": "missing_cert",
            "badge": "⚠️ 胜任私兔/拉练兔 · 官兔初审缺证",
            "detail": f"当期硬实力已胜任该配速领跑，但{reason_detail}；建议先担任跑团私兔/拉练兔，或刷一场达标认证PB。",
        }
    else:
        gate_cap = min(gate_cap, 58)
        gates["cert_gate"] = {
            "status": "fail",
            "badge": f"❌ 证书未达初审线 (需 ≤ {req_cert_time_str})",
            "detail": f"组委会选拔 {group_spec['label']} 通常要求官方完赛证书快于 {req_cert_time_str}。",
        }

    # Gate 3: 14-day Back-to-Back Race Conflict Check
    conflict_race = None
    if target_race_date:
        try:
            tgt_d = datetime.strptime(target_race_date[:10], "%Y-%m-%d").date()
            for up in rh["upcoming_races"]:
                if not up.get("date") or up["distance_km"] < 20.0:
                    continue
                if calib["event_name"] in str(up.get("name") or ""):
                    continue
                up_d = datetime.strptime(up["date"][:10], "%Y-%m-%d").date()
                gap_d = (tgt_d - up_d).days
                if -7 <= gap_d <= 14:
                    conflict_race = up
                    break
        except Exception:
            pass

    if conflict_race:
        gate_cap = min(gate_cap, 69)
        gates["schedule_gate"] = {
            "status": "conflict",
            "badge": f"⚠️ 背靠背赛程冲突 ({conflict_race['name']})",
            "detail": f"检测到赛前/后邻近日期已报【{conflict_race['name']} ({conflict_race['date']})】，违反官方配速员“严禁背靠背参赛”纪律。",
        }
    else:
        gates["schedule_gate"] = {
            "status": "pass",
            "badge": "✅ 无背靠背赛程冲突",
            "detail": "前后 14 天内未检测到高负荷全马/越野赛事冲突。",
        }

    # Gate 4: Official Age Window (20 - 60)
    age = ctx.get("age")
    if age is not None and strictness != "club_lsd" and not (20 <= age <= 60):
        gate_cap = min(gate_cap, 50)
        gates["age_gate"] = {
            "status": "fail",
            "badge": f"❌ 年龄超出官方规程 ({age}周岁)",
            "detail": "国内标牌马拉松官方配速员招募通常要求年龄在 20 至 60 周岁之间。",
        }
    else:
        gates["age_gate"] = {
            "status": "pass",
            "badge": f"✅ 年龄合规 ({age}周岁)" if age is not None else "ℹ️ 年龄未填 (默认合规)",
            "detail": "符合马拉松官方配速员 20–60 周岁招募规程。",
        }

    final_score = int(min(gate_cap, max(15, round(penalized_score))))
    priv_s1 = int(round(min(98.0, max(15.0, 0.82 * pred_pts + 0.18 * hr_comfort_pts))))
    priv_s4 = max(s4_experience, int(round(min(84.0, 52.0 + lr25 * 5.5 + lr16 * 2.5))))
    priv_raw = (
        0.25 * priv_s1
        + 0.25 * s2_pacing
        + 0.20 * s3_training
        + 0.15 * priv_s4
        + 0.10 * s5_leadership
        + 0.05 * s6_recovery
    )
    priv_pen = sum(0.40 * max(0.0, 55.0 - float(sc)) for sc in (priv_s1, s2_pacing, s3_training))
    private_pacer_score = int(min(98 if gates["fitness_gate"]["status"] == "pass" else 58, max(15, round(priv_raw - priv_pen))))

    # Tier & Verdict Badge
    is_missing_cert_dark_horse = (
        gates["fitness_gate"]["status"] == "pass" and gates["cert_gate"]["status"] == "missing_cert"
    )
    if is_missing_cert_dark_horse:
        grade = "B+"
        verdict_label = "🏃 胜任私兔/拉练兔 · 官兔初审缺证"
        verdict_color = "#f59e0b"
    elif final_score >= 90:
        grade = "S"
        verdict_label = "👑 S级 · 首席官兔/组长苗子"
        verdict_color = "#10b981"
    elif final_score >= 80:
        grade = "A"
        verdict_label = "🎯 A级 · 高胜任度 · 强烈推荐申请"
        verdict_color = "#22c55e"
    elif final_score >= 70:
        grade = "B"
        verdict_label = "⚡ B级 · 具备潜力 · 建议专项强化"
        verdict_color = "#0ea5e9"
    elif final_score >= 60:
        grade = "C"
        verdict_label = "🔄 C级 · 余量偏紧 · 建议降一档申请"
        verdict_color = "#f59e0b"
    else:
        grade = "D"
        verdict_label = "⛔ D级 · 暂不适配当前兔组"
        verdict_color = "#ef4444"

    dimensions = [
        {
            "key": "speed_margin",
            "label": "硬实力与配速冗余",
            "weight_pct": 25,
            "score": s1_speed_margin,
            "display_value": s1_disp,
            "desc": f"综合当期预测完赛时间（60%）、官方认证PB（25%）与{hr_note}（15%）评估的控场安全余量。",
        },
        {
            "key": "pacing_stability",
            "label": "巡航控速精准度",
            "weight_pct": 25,
            "score": s2_pacing,
            "display_value": s2_disp,
            "desc": s2_desc,
        },
        {
            "key": "training_endurance",
            "label": "训练水平与耐力储备",
            "weight_pct": 20,
            "score": s3_training,
            "display_value": s3_disp,
            "desc": "结合近 6 周跑量、连续出勤周数、长距离深度/在途时长及后半程心率抗衰减度评估的零抽筋底气。",
        },
        {
            "key": "race_experience",
            "label": "赛事履历与完赛经验",
            "weight_pct": 15,
            "score": s4_experience,
            "display_value": s4_disp,
            "desc": "考察近 24 个月标牌赛事完赛场次、同赛道熟悉度与过往目标执行兑现率。",
        },
        {
            "key": "leadership_credentials",
            "label": "领跑实战与官方资质",
            "weight_pct": 10,
            "score": s5_leadership,
            "display_value": s5_disp,
            "desc": "统计跑团线下约跑「🐰 领跑兔」打卡配速准度、往届官兔压线经历及红十字/AHA/医护急救资质加分。",
        },
        {
            "key": "recovery_reliability",
            "label": "生理恢复与出战可靠",
            "weight_pct": 5,
            "score": s6_recovery,
            "display_value": s6_disp,
            "desc": s6_desc,
        },
    ]

    # Actionable deterministic diagnosis bullets
    action_tips: List[str] = []
    if gates["fitness_gate"]["status"] == "fail":
        action_tips.append(gates["fitness_gate"]["detail"])
    if is_missing_cert_dark_horse:
        action_tips.append(gates["cert_gate"]["detail"])
    if conflict_race:
        action_tips.append(gates["schedule_gate"]["detail"])
    if s2_pacing < 75:
        action_tips.append(
            f"控速精度待打磨：建议每周安排 1 次 14~20km @ {fmt_pace_sec(target_pace_sec)} 关闭手表自动配速播报的「盲跑定速巡航」，将每公里波动压进 ±{sigma_ideal:.0f}s。"
        )
    if is_fast_runner_slow_group and not has_pace_memory:
        action_tips.append(
            f"慢速步态适应提醒：您的自然配速远快于 {group_spec['label']}（{fmt_pace_sec(target_pace_sec)}），赛前需专门以高频小步慢跑拉练 2 次，防止刻意压速引发膝关节不适。"
        )
    if s3_training < 72:
        action_tips.append(
            f"耐力底座建议：未来 4~6 周建议将周均跑量稳步提升至 {int(round(req_wk_km))}km+，并完成至少 2 次 {int(round(req_long_km))}km 稳态长距离。"
        )
    if not fa_type and strictness in ("platinum", "gold"):
        action_tips.append("组委会优先项提示：考取红十字救护员证或 AHA 急救证，可在上马等头部赛事官兔选拔同等条件下获得优先录取权重。")
    if not action_tips:
        action_tips.append(
            f"各项指标高度契合【{calib['event_name']} · {group_spec['label']}】选拔标准，赛前保持每周 1 次目标配速巡航维持肌肉记忆即可稳妥压线！"
        )

    return {
        "group_code": group_spec["code"],
        "group_label": group_spec["label"],
        "target_time": group_spec["target_time"],
        "target_sec": target_sec,
        "target_pace_sec": round(target_pace_sec, 1),
        "target_pace_str": fmt_pace_sec(target_pace_sec),
        "tier": group_tier,
        "overall_score": final_score,
        "private_pacer_score": private_pacer_score,
        "raw_weighted_score": round(raw_weighted, 1),
        "barrel_penalty": round(weak_penalty, 1),
        "grade": grade,
        "verdict_label": verdict_label,
        "verdict_color": verdict_color,
        "pred_finish_sec": pred_sec,
        "pred_finish_str": format_duration(pred_sec) if pred_sec > 0 else "—",
        "pred_margin_sec": pred_margin_sec if pred_sec > 0 else None,
        "cert_finish_sec": cert_sec,
        "cert_finish_str": format_duration(cert_sec) if cert_sec > 0 else "—",
        "cert_source": cert_source,
        "cert_margin_sec": cert_margin_sec if cert_sec > 0 else None,
        "req_cert_margin_sec": req_cert_margin_sec,
        "min_fitness_margin_sec": min_fitness_margin_sec,
        "sigma_avg_sec": sigma_avg,
        "has_target_pace_memory": has_pace_memory,
        "gates": gates,
        "dimensions": dimensions,
        "action_tips": action_tips[:4],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. PUBLIC API FUNCTIONS: SINGLE EVALUATION, CLUB RADAR & AI PRESCRIPTION
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_runner_pacer_fitness(
    uid: str,
    event_name: Optional[str] = None,
    distance_type: Optional[str] = None,
    target_group: Optional[str] = None,
    custom_distance_km: Optional[float] = None,
    custom_target_time: Optional[str] = None,
    custom_target_pace: Optional[str] = None,
    race_date: Optional[str] = None,
    viewer_uid: Optional[str] = None,
    club_id: Optional[str] = None,
    allow_web_search: bool = True,
    precomputed_ctx: Optional[Dict[str, Any]] = None,
    precomputed_calib: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main entrypoint for single-runner Official Pacer suitability evaluation.
    """
    ctx = precomputed_ctx or build_runner_pacer_context(uid, viewer_uid=viewer_uid, club_id=club_id)

    # Auto-infer upcoming race from runner's race_plans if event_name not explicitly passed
    eff_event_name = (event_name or "").strip()
    eff_race_date = race_date
    if not eff_event_name:
        upcoming_road = [r for r in ctx["race_history"]["upcoming_races"] if not r["is_trail"]]
        if upcoming_road:
            eff_event_name = upcoming_road[0]["name"]
            eff_race_date = eff_race_date or upcoming_road[0].get("date")
            if not distance_type:
                dk = upcoming_road[0]["distance_km"]
                distance_type = "fm" if dk >= 35 else ("hm" if dk >= 18 else "10k")
        else:
            eff_event_name = "上海马拉松"

    # Match race_date if runner registered this event in race_plans
    if not eff_race_date and eff_event_name:
        for up in ctx["race_history"]["upcoming_races"]:
            if eff_event_name[:3] in str(up.get("name") or ""):
                eff_race_date = up.get("date")
                break

    norm_dt = _normalize_distance_type(distance_type, eff_event_name, custom_distance_km)
    calib = precomputed_calib or resolve_event_calibration(
        event_name=eff_event_name,
        distance_type=norm_dt,
        custom_distance_km=custom_distance_km,
        race_date=eff_race_date,
        allow_web_search=allow_web_search,
    )

    min_cruise_km = 12.0 if calib["distance_km"] >= 18.0 else 7.5
    portfolio = _extract_cruise_portfolio(ctx["activities"], min_dist_km=min_cruise_km)

    # Build group specs to evaluate
    if norm_dt == "custom":
        dist_km = calib["distance_km"]
        t_sec = _parse_any_seconds(custom_target_time)
        if not t_sec and custom_target_pace:
            p_s = parse_pace_str_to_sec(custom_target_pace)
            if p_s:
                t_sec = int(round(p_s * dist_km))
        if not t_sec:
            t_sec = int(round(300 * dist_km))  # default 5:00/km
        p_s_eff = t_sec / max(1.0, dist_km)
        tier_c = "elite" if p_s_eff <= 265 else ("advanced" if p_s_eff <= 315 else ("mass" if p_s_eff <= 390 else "finisher"))
        group_list = [{
            "code": "custom",
            "label": f"{round(dist_km, 1)}km @ {fmt_pace_sec(p_s_eff)}",
            "target_time": fmt_duration_hms(t_sec),
            "target_sec": t_sec,
            "tier": tier_c,
        }]
    else:
        group_list = PACER_GROUP_PRESETS[norm_dt]

    evaluated_groups = [
        _score_single_group(ctx, calib, portfolio, g_spec, target_race_date=eff_race_date)
        for g_spec in group_list
    ]

    # Identify recommended official group (fastest/highest-scoring eligible group) & private pacer group
    eligible_official = [
        g for g in evaluated_groups
        if g["gates"]["fitness_gate"]["status"] == "pass"
        and g["gates"]["cert_gate"]["status"] in ("pass", "exempt")
        and g["overall_score"] >= 72
    ]
    if eligible_official:
        # Pick highest-scoring group (tie-break toward faster standard group within 3 pts of peak score)
        max_sc = max(g["overall_score"] for g in eligible_official)
        near_top = [g for g in eligible_official if g["overall_score"] >= max_sc - 3]
        recommended_group = near_top[0]
    else:
        recommended_group = max(evaluated_groups, key=lambda g: (g["overall_score"], g["private_pacer_score"]))

    # Select active group requested by user (or auto-select recommended_group when target_group is empty/'auto')
    req_code = (target_group or "").strip().lower()
    selected = None
    if req_code and req_code not in ("auto", "recommend", "智能推荐"):
        for g in evaluated_groups:
            if g["group_code"].lower() == req_code or g["label" if "label" in g else "group_label"].lower() == req_code:
                selected = g
                break
    if selected is None:
        selected = recommended_group

    # Compact matrix strip for top horizontal selector bar
    all_groups_matrix = [
        {
            "group_code": g["group_code"],
            "group_label": g["group_label"],
            "target_time": g["target_time"],
            "target_pace_str": g["target_pace_str"],
            "overall_score": g["overall_score"],
            "private_pacer_score": g["private_pacer_score"],
            "grade": g["grade"],
            "verdict_color": g["verdict_color"],
            "fitness_ok": g["gates"]["fitness_gate"]["status"] == "pass",
            "cert_status": g["gates"]["cert_gate"]["status"],
            "is_recommended": g["group_code"] == recommended_group["group_code"],
        }
        for g in evaluated_groups
    ]

    raw_prof = ctx["raw_profile"]
    fa_code = str(raw_prof.get("first_aid_cert_type") or "").strip()
    real_name_safe = (
        (raw_prof.get("real_name") or "")
        if ctx["can_view_confidential"]
        else ""
    )

    return {
        "runner": {
            "uid": ctx["uid"],
            "display_name": raw_prof.get("display_name") or "跑者",
            "real_name": real_name_safe,
            "avatar_url": raw_prof.get("avatar_url") or "",
            "gender": raw_prof.get("gender") or "male",
            "age": ctx["age"],
            "garmin_connected": bool(raw_prof.get("garmin_connected")),
            "coros_connected": bool(raw_prof.get("coros_connected")),
            "watch_verified_label": (
                "Garmin 佳明官方同步认证"
                if raw_prof.get("garmin_connected")
                else ("COROS 高驰官方同步认证" if raw_prof.get("coros_connected") else "RGM 运动数据档案")
            ),
            "first_aid_cert_type": fa_code,
            "first_aid_cert_label": FIRST_AID_LABELS.get(fa_code, "未登记急救资质"),
            "effective_vdot": ctx["canova_matrix"].get("effective_vdot"),
            "weekly_km_avg": ctx["canova_matrix"].get("weekly_km_avg"),
        },
        "event_calibration": calib,
        "selected_evaluation": selected,
        "recommended_group": {
            "group_code": recommended_group["group_code"],
            "group_label": recommended_group["group_label"],
            "target_time": recommended_group["target_time"],
            "target_pace_str": recommended_group["target_pace_str"],
            "overall_score": recommended_group["overall_score"],
            "grade": recommended_group["grade"],
            "verdict_label": recommended_group["verdict_label"],
        },
        "all_groups_matrix": all_groups_matrix,
        "showcase_run": portfolio["showcase_run"],
        "monthly_mileage_6m": ctx["monthly_mileage_6m"],
        "verified_races": ctx["race_history"]["completed_races"][:8],
        "upcoming_races": ctx["race_history"]["upcoming_races"][:5],
        "pacer_credentials_summary": {
            "official_pacer_count": len(ctx["race_history"]["official_pacer_races"]),
            "club_pacer_total_count": ctx["club_leadership"]["club_pacer_total_count"],
            "club_pacer_on_target_count": ctx["club_leadership"]["club_pacer_on_target_count"],
            "first_aid_cert_type": fa_code,
            "first_aid_cert_label": FIRST_AID_LABELS.get(fa_code, "未登记急救资质"),
        },
    }


def evaluate_club_pacer_candidates(
    club_id: str,
    viewer_uid: str,
    event_name: Optional[str] = None,
    distance_type: str = "fm",
    target_groups: Optional[List[str]] = None,
    custom_distance_km: Optional[float] = None,
    custom_target_pace: Optional[str] = None,
    allow_web_search: bool = True,
) -> Dict[str, Any]:
    """
    Batch-evaluates all active members in a club for Official Pacer / Group-Run LSD Pacer selection.
    Resolves race calibration once and bulk-loads lightweight activities for sub-50ms club-wide ranking.
    """
    norm_dt = _normalize_distance_type(distance_type, event_name, custom_distance_km)
    calib = resolve_event_calibration(
        event_name=event_name,
        distance_type=norm_dt,
        custom_distance_km=custom_distance_km,
        allow_web_search=allow_web_search,
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, role, training_group
            FROM club_memberships
            WHERE club_id = ? AND status = 'active'
            """,
            (club_id,),
        )
        member_rows = [dict(r) for r in cursor.fetchall()]

        cursor.execute(
            """
            SELECT id, title, meet_time, start_date, target_km, pace_requirement, status
            FROM club_events
            WHERE club_id = ? AND COALESCE(status, 'upcoming') != 'cancelled'
            ORDER BY COALESCE(meet_time, start_date, created_at) DESC
            LIMIT 12
            """,
            (club_id,),
        )
        club_events = [dict(r) for r in cursor.fetchall()]

        member_uids = list({LocalStore.resolve_user_id(m["user_id"]) for m in member_rows if m.get("user_id")})
        acts_by_uid: Dict[str, List[Dict[str, Any]]] = {u: [] for u in member_uids}
        if member_uids:
            cutoff_190d = (date.today() - timedelta(days=190)).isoformat()
            placeholders = ",".join(["?"] * len(member_uids))
            cursor.execute(
                f"""
                SELECT id, user_id, name, sport_type, start_time, distance_meters,
                       moving_time_seconds, elapsed_time_seconds, elevation_gain_meters,
                       average_heartrate, max_heartrate, average_cadence, avg_pace_str,
                       trimp, exclude_mode, laps_data, splits_data, segment_analysis_json
                FROM activities
                WHERE user_id IN ({placeholders}) AND start_time >= ?
                ORDER BY start_time DESC
                """,
                [*member_uids, cutoff_190d],
            )
            for row in cursor.fetchall():
                ad = dict(row)
                u_key = LocalStore.resolve_user_id(ad.get("user_id") or "")
                if u_key in acts_by_uid and len(acts_by_uid[u_key]) < 160:
                    acts_by_uid[u_key].append(ad)

    # Determine target groups to rank
    if norm_dt == "custom":
        desired_codes = ["custom"]
    elif target_groups:
        desired_codes = [g.strip() for g in target_groups if g.strip()]
    elif norm_dt == "fm":
        desired_codes = ["300", "315", "330", "345", "400", "430", "500"]
    elif norm_dt == "hm":
        desired_codes = ["130", "145", "200", "215", "230"]
    else:
        desired_codes = ["40", "45", "50", "55", "60"]

    member_evals: List[Dict[str, Any]] = []
    group_buckets: Dict[str, List[Dict[str, Any]]] = {code: [] for code in desired_codes}

    for uid in member_uids:
        ctx = build_runner_pacer_context(
            uid=uid,
            viewer_uid=viewer_uid,
            club_id=club_id,
            preloaded_activities=acts_by_uid.get(uid, []),
        )
        res = evaluate_runner_pacer_fitness(
            uid=uid,
            event_name=calib["event_name"],
            distance_type=norm_dt,
            custom_distance_km=custom_distance_km,
            custom_target_pace=custom_target_pace,
            viewer_uid=viewer_uid,
            club_id=club_id,
            allow_web_search=False,
            precomputed_ctx=ctx,
            precomputed_calib=calib,
        )
        runner_meta = res["runner"]
        rec = res["recommended_group"]
        cred = res["pacer_credentials_summary"]

        # Map each group evaluation for this runner
        min_cruise_km = 12.0 if calib["distance_km"] >= 18.0 else 7.5
        portfolio = _extract_cruise_portfolio(ctx["activities"], min_dist_km=min_cruise_km)

        if norm_dt == "custom":
            g_specs = [{
                "code": "custom",
                "label": res["selected_evaluation"]["group_label"],
                "target_time": res["selected_evaluation"]["target_time"],
                "target_sec": res["selected_evaluation"]["target_sec"],
                "tier": res["selected_evaluation"]["tier"],
            }]
        else:
            preset_map = {g["code"]: g for g in PACER_GROUP_PRESETS[norm_dt]}
            g_specs = [preset_map[c] for c in desired_codes if c in preset_map]

        for gs in g_specs:
            g_ev = _score_single_group(ctx, calib, portfolio, gs)
            group_buckets.setdefault(gs["code"], []).append({
                "uid": uid,
                "display_name": runner_meta["display_name"],
                "avatar_url": runner_meta["avatar_url"],
                "effective_vdot": runner_meta["effective_vdot"],
                "weekly_km_avg": runner_meta["weekly_km_avg"],
                "overall_score": g_ev["overall_score"],
                "private_pacer_score": g_ev["private_pacer_score"],
                "grade": g_ev["grade"],
                "verdict_label": g_ev["verdict_label"],
                "verdict_color": g_ev["verdict_color"],
                "pred_finish_str": g_ev["pred_finish_str"],
                "cert_finish_str": g_ev["cert_finish_str"],
                "sigma_avg_sec": g_ev["sigma_avg_sec"],
                "fitness_gate_status": g_ev["gates"]["fitness_gate"]["status"],
                "cert_gate_status": g_ev["gates"]["cert_gate"]["status"],
                "club_pacer_count": cred["club_pacer_total_count"],
                "official_pacer_count": cred["official_pacer_count"],
                "first_aid_cert_label": cred["first_aid_cert_label"] if cred["first_aid_cert_type"] else "",
                "dimensions": g_ev["dimensions"],
            })

        member_evals.append({
            "uid": uid,
            "display_name": runner_meta["display_name"],
            "avatar_url": runner_meta["avatar_url"],
            "effective_vdot": runner_meta["effective_vdot"],
            "weekly_km_avg": runner_meta["weekly_km_avg"],
            "recommended_group": rec,
            "pacer_credentials": cred,
        })

    # Sort each group bucket by overall_score DESC, then private_pacer_score DESC, then VDOT DESC
    groups_ranking = []
    for code in desired_codes:
        cands = group_buckets.get(code, [])
        cands.sort(
            key=lambda x: (
                x["overall_score"],
                x["private_pacer_score"],
                float(x["effective_vdot"] or 0.0),
            ),
            reverse=True,
        )
        qualified_cnt = sum(1 for c in cands if c["overall_score"] >= 70 or (norm_dt == "custom" and c["private_pacer_score"] >= 70))
        label_str = code if norm_dt == "custom" else next(
            (g["label"] for g in PACER_GROUP_PRESETS.get(norm_dt, []) if g["code"] == code),
            f"{code} 组",
        )
        pace_str = next(
            (fmt_pace_sec(g["target_sec"] / calib["distance_km"]) for g in PACER_GROUP_PRESETS.get(norm_dt, []) if g["code"] == code),
            res["selected_evaluation"]["target_pace_str"] if member_evals else "",
        )
        groups_ranking.append({
            "group_code": code,
            "group_label": label_str,
            "target_pace_str": pace_str,
            "qualified_count": qualified_cnt,
            "candidates": cands[:15],
        })

    member_evals.sort(key=lambda m: m["recommended_group"]["overall_score"], reverse=True)

    return {
        "club_id": club_id,
        "total_members_evaluated": len(member_uids),
        "event_calibration": calib,
        "groups_ranking": groups_ranking,
        "members_best_fit": member_evals,
        "assignable_events": club_events,
    }


def generate_pacer_ai_prescription(
    eval_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generates an on-demand 4-week blind-pacing training prescription AND an ~180-word
    Official Pacer Recruitment Application Statement via DashScope/DeepSeek,
    with an instant structured deterministic fallback if LLM is unreachable.
    """
    runner = eval_result["runner"]
    calib = eval_result["event_calibration"]
    sel = eval_result["selected_evaluation"]
    cred = eval_result["pacer_credentials_summary"]
    m6 = eval_result.get("monthly_mileage_6m") or []
    total_6m_km = round(sum(float(x.get("km") or 0.0) for x in m6), 1)

    fallback_plan = (
        f"【第1周 · 目标配速体感标定】周中完成 12km @ {sel['target_pace_str']} 定速跑（关闭每公里语音，每3km核对一次误差）；周末 20km 稳态有氧。\n"
        f"【第2周 · 盲跑节拍器强化】周中 14km @ {sel['target_pace_str']} 纯盲跑（目标每公里波动 ≤ {calib['sigma_ideal_sec']}s）；周末 24~28km 含后半程 10km 目标配速巡航。\n"
        f"【第3周 · 实战补给与带队模拟】模拟{calib['event_name']}每 5km 进站减速取水后 400m 平滑回补配速（严禁猛冲），单次拉练 25~30km。\n"
        f"【第4周 · 赛前减量与配速手环核对】跑量减半释放 TSB 超量恢复，周三完成 6km @ {sel['target_pace_str']} 唤醒肌肉记忆，核对分枪计时毯节点。"
    )
    fa_clause = f"，持有{cred['first_aid_cert_label'].split(' ')[-1]}" if cred.get("first_aid_cert_type") else ""
    pacer_clause = (
        f"，具备 {cred['official_pacer_count']} 场官方配速员及 {cred['club_pacer_total_count']} 次跑团定速领跑经验"
        if (cred.get("official_pacer_count") or cred.get("club_pacer_total_count"))
        else ""
    )
    sigma_clause = f"，长距离巡航每公里配速波动稳定在 ±{sel['sigma_avg_sec']}s 以内" if sel.get("sigma_avg_sec") else ""
    fallback_bio = (
        f"您好！我申请竞选【{calib['event_name']} · {sel['group_label']}（目标配速 {sel['target_pace_str']}）】。"
        f"本人认证最佳成绩 {sel['cert_finish_str']}，当期有效跑力预测 {sel['pred_finish_str']}，相对目标组别具备充沛体能冗余；"
        f"近半年累计跑量 {total_6m_km}km（周均 {runner.get('weekly_km_avg') or 0}km）{sigma_clause}{pacer_clause}{fa_clause}。"
        f"严格遵守组委会赛前不背靠背参赛与官方装备纪律，有信心以 ±{calib['target_gun_error_sec']} 秒内精准压线带领跑友安全圆梦！"
    )

    system_prompt = (
        "你是世界级马拉松教练兼白金标赛事官方配速员总管。"
        "请基于跑者的真实手表数据与目标赛事特征，输出严格 JSON（不含代码块标记）："
        '{"four_week_plan": "分4周的官兔盲跑控速与专项耐力课表（约220字，使用换行分段）", '
        '"application_statement": "第一人称撰写的官方配速员竞选自荐陈述（约160~200字，数据真实硬核、语气专业诚恳，可直接粘贴进组委会报名表）"}'
    )
    user_prompt = (
        f"申请赛事：{calib['event_name']}（{calib['race_level']}，爬升 {calib['elevation_gain_m']}m，误差要求 ±{calib['target_gun_error_sec']}s）\n"
        f"目标组别：{sel['group_label']}（目标时间 {sel['target_time']}，配速 {sel['target_pace_str']}）\n"
        f"综合评分：{sel['overall_score']}分（{sel['verdict_label']}）\n"
        f"证书PB：{sel['cert_finish_str']} | 当期预测：{sel['pred_finish_str']} | 近6月跑量：{total_6m_km}km（周均 {runner.get('weekly_km_avg')}km）\n"
        f"代表作配速标准差：{sel.get('sigma_avg_sec') or '待采集'}s/km | 往届官兔：{cred['official_pacer_count']}次 | 跑团领跑：{cred['club_pacer_total_count']}次 | 急救资质：{cred['first_aid_cert_label']}\n"
        f"当前短板提示：{'; '.join(sel.get('action_tips') or [])}"
    )

    try:
        from utils.llm import llm_client
        raw = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
            max_tokens=700,
        )
        clean = str(raw or "").strip()
        if "{" in clean and "}" in clean:
            clean = clean[clean.find("{") : clean.rfind("}") + 1]
            parsed = json.loads(clean)
            if parsed.get("four_week_plan") and parsed.get("application_statement"):
                return {
                    "success": True,
                    "source": "ai",
                    "four_week_plan": str(parsed["four_week_plan"]).strip(),
                    "application_statement": str(parsed["application_statement"]).strip(),
                }
    except Exception as e:
        logger.warning(f"[pacer_ai] Falling back to deterministic template: {e}")

    return {
        "success": True,
        "source": "template",
        "four_week_plan": fallback_plan,
        "application_statement": fallback_bio,
    }
