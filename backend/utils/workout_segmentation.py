"""
Multi-Signal Workout & Preset-Race Segmentation Engine for RGM.

Capabilities:
1. Segments a running activity into physiological/tactical phases (Warm-up, Main Cruise / Progression /
   Intervals, Cool-down) using watch Laps, 1km Splits, high-frequency Telemetry (speed/GAP/HR/cadence/elevation),
   and GPS route geometry (track loop detection, grade-adjusted pace, cardiac-lag compensation).
2. Strict 3-mode routing:
   - 'race': Triggered strictly when the activity matches a user's preset race (race_plans or training_plans race day).
             Produces stage-by-stage race breakdown, 1st/2nd half split (Negative/Positive Split), fade inflection km,
             physiological root-cause attribution (cardiac drift vs glycogen/muscular bonk vs terrain hill), and prescriptions.
   - 'planned_workout': Triggered when the runner has an active training plan workout on that date.
             Aligns detected phases (especially Main Set / Intervals) against prescribed targets.
   - 'free_workout': Triggered when no preset race or scheduled workout exists on that date.
             Auto-classifies session structure and critiques each phase quantitatively.
"""

import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple


def fmt_pace_sec(sec_val: Optional[float], with_unit: bool = True) -> str:
    if sec_val is None or sec_val <= 0:
        return "—"
    s_i = max(90, int(round(float(sec_val))))
    base = f"{s_i // 60}:{s_i % 60:02d}"
    return f"{base}/km" if with_unit else base


def fmt_duration_hms(seconds_val: Optional[float]) -> str:
    if seconds_val is None or seconds_val <= 0:
        return "—"
    total = int(round(float(seconds_val)))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def parse_pace_str_to_sec(pace_text: Optional[str]) -> Optional[int]:
    if not pace_text:
        return None
    m = re.search(r"(\d{1,2})\s*[:'’分]\s*(\d{2})", str(pace_text))
    if not m:
        return None
    val = int(m.group(1)) * 60 + int(m.group(2))
    return val if 90 <= val <= 1200 else None


def parse_pace_range_to_sec(text: Optional[str]) -> Optional[Tuple[int, int]]:
    if not text:
        return None
    matches = re.findall(r"(\d{1,2})\s*[:'’分]\s*(\d{2})", str(text))
    secs = []
    for m_s, s_s in matches:
        v = int(m_s) * 60 + int(s_s)
        if 120 <= v <= 900:
            secs.append(v)
    if not secs:
        return None
    return (min(secs), max(secs))


def _extract_planned_interval_spec(text: Optional[str]) -> Tuple[int, float]:
    """
    Parses (rep_count, rep_distance_km) from a workout title/description if present.
    Ignores post-run short strides (e.g. '结束后做 4 组 100m 跨步冲刺', '跑后 6 组 × 80m').
    """
    if not text:
        return 0, 0.0
    core_text = re.split(r"(?:结束后|跑后)", str(text))[0]
    # Pattern 1: 6组 × 1000m, 6x1000m, 6 x 1km, 10组400米
    for m in re.finditer(
        r"(\d{1,2})\s*(?:组\s*[*xX×]?|[*xX×])\s*(\d+(?:\.\d+)?)\s*(km|k|公里|m|米)",
        core_text,
        re.I,
    ):
        reps = int(m.group(1))
        val = float(m.group(2))
        unit = m.group(3).lower()
        rep_km = val / 1000.0 if unit in ("m", "米") else val
        if reps >= 2 and rep_km >= 0.18:
            return reps, round(rep_km, 2)
    # Pattern 2: 1000m*6, 1600m+400m*6, 400米×10组, 200米*8
    for m in re.finditer(
        r"(\d+(?:\.\d+)?)\s*(km|k|公里|m|米)\s*(?:\+\s*\d+\s*(?:m|米)\s*)?[*xX×]\s*(\d{1,2})\s*组?",
        core_text,
        re.I,
    ):
        val = float(m.group(1))
        unit = m.group(2).lower()
        reps = int(m.group(3))
        rep_km = val / 1000.0 if unit in ("m", "米") else val
        if reps >= 2 and rep_km >= 0.18:
            return reps, round(rep_km, 2)
    return 0, 0.0


def has_large_plan_discrepancy(
    planned_day: Optional[Dict[str, Any]],
    activity: Dict[str, Any],
    eval_total_km: Optional[float] = None,
    eval_main_km: Optional[float] = None,
    planned_main_km: Optional[float] = None,
    eval_pace_sec: Optional[int] = None,
    phases: Optional[List[Dict[str, Any]]] = None,
    interval_meta: Optional[Dict[str, Any]] = None,
    same_day_runs: Optional[List[Dict[str, Any]]] = None,
    aerobic_ceiling: float = 152.0,
    threshold_ceiling: float = 168.0,
) -> bool:
    """
    Returns True if the actual workout has a large discrepancy from the scheduled workout (`planned_day`)
    across any of:
    1. Distance (距离): rest day vs run, activity is a short fragment, or total / main-set distance deviates by >25%.
    2. Pace (配速): main-set pace deviates from prescribed target pace window by >20s/km (or outside progression bounds).
    3. Combination / Structure (组合): interval vs continuous mismatch, interval rep count/distance mismatch,
       mountain/climb vs flat road mismatch, missing 3-stage warmup/cooldown on structured quality sessions,
       or late fade on a prescribed progression run.
    When True, Canova Coach directly critiques the workout's actual training effect instead of comparing with the schedule.
    """
    if not planned_day:
        return True

    w_type = str(planned_day.get("workout_type") or "easy_run").strip().lower()
    plan_title_raw = str(planned_day.get("title") or "").strip()
    plan_dist = float(planned_day.get("distance_km") or 0.0)
    plan_pace_text = str(planned_day.get("target_pace") or "").strip()
    plan_desc = str(planned_day.get("description") or "").strip()

    if (
        w_type in ("rest", "travel", "cross_training", "strength")
        or plan_dist <= 0
        or any(k in plan_title_raw for k in ("完全休息", "跑休", "休整日"))
    ):
        return True

    # ── 1. Distance Discrepancy Check (距离差异) ──
    raw_dist_m = float(activity.get("distance_meters") or 0.0)
    act_dist_km = round(raw_dist_m / 1000.0, 2) if raw_dist_m > 0 else round(float(activity.get("distance_km") or 0.0), 2)
    if eval_total_km is None:
        eval_total_km = act_dist_km
    if planned_main_km is None:
        planned_main_km = plan_dist
    if eval_main_km is None:
        eval_main_km = eval_total_km
    if eval_pace_sec is None:
        eval_pace_sec = parse_pace_str_to_sec(activity.get("avg_pace_str"))
        if eval_pace_sec is None:
            mov_s = float(activity.get("moving_time_seconds") or activity.get("elapsed_time_seconds") or 0.0)
            if act_dist_km > 0.1 and mov_s > 0:
                p_cand = int(round(mov_s / act_dist_km))
                if 90 <= p_cand <= 1200:
                    eval_pace_sec = p_cand

    eff_planned_main = planned_main_km if planned_main_km > 0 else plan_dist

    # Standalone short warm-up/cool-down recording or single interval rep fragment
    if act_dist_km < plan_dist * 0.60 and act_dist_km < eff_planned_main * 0.70:
        return True

    total_ratio = eval_total_km / max(0.5, plan_dist)
    if total_ratio < 0.75 or total_ratio > 1.25:
        return True

    if eff_planned_main > 0 and eval_main_km > 0:
        main_ratio = eval_main_km / max(0.5, eff_planned_main)
        if main_ratio < 0.75 or main_ratio > 1.25:
            return True

    # ── 2. Combination / Structure Discrepancy Check (组合差异) ──
    core_plan_desc = re.split(r"(?:结束后|跑后)", plan_desc)[0]
    main_clause = ""
    if "+" in core_plan_desc:
        parts = [p.strip() for p in core_plan_desc.split("+") if p.strip()]
        non_wucd = [p for p in parts if not p.startswith("热身") and "冷身" not in p[:6]]
        if non_wucd:
            main_clause = non_wucd[0].split("。")[0].strip()

    plan_core_text = f"{plan_title_raw} {main_clause or core_plan_desc}"
    planned_reps, planned_rep_km = _extract_planned_interval_spec(plan_core_text)
    is_planned_interval = bool(
        w_type in ("interval", "intervals", "fartlek", "speed", "track", "reps")
        or any(k in plan_core_text for k in ("间歇", "变速", "法特莱克", "重复跑", "多组"))
        or (planned_reps >= 2 and planned_rep_km >= 0.18)
    )

    act_name = str(activity.get("name") or "")
    act_reps, act_rep_km_from_name = _extract_planned_interval_spec(act_name)
    name_has_interval = bool(
        (act_reps >= 2 and act_rep_km_from_name >= 0.15)
        or re.search(
            r"(\d+\s*(?:m|米|km|k)\s*\+\s*\d+\s*(?:m|米|km|k)|\b(?:1st|2nd|3rd|\d+th)\b|间歇|变速|法特莱克|速耐\s*\d)",
            act_name,
            re.I,
        )
    )
    multi_split_bouts = bool(same_day_runs and len(same_day_runs) >= 4)
    seg_has_interval = bool(interval_meta and int(interval_meta.get("rep_count") or 0) >= 2)
    is_actual_interval = bool(seg_has_interval or name_has_interval or multi_split_bouts)

    # 2A. Interval vs Continuous combination mismatch
    if is_planned_interval != is_actual_interval:
        return True

    # 2B. Interval rep count / rep distance combination mismatch
    if is_planned_interval and is_actual_interval:
        eff_act_rep_km = (
            float(interval_meta["avg_rep_km"])
            if (interval_meta and interval_meta.get("avg_rep_km"))
            else act_rep_km_from_name
        )
        eff_act_reps = (
            int(interval_meta["rep_count"])
            if (interval_meta and interval_meta.get("rep_count"))
            else act_reps
        )
        if planned_rep_km >= 0.18 and eff_act_rep_km > 0:
            if eff_act_rep_km < planned_rep_km * 0.65 or eff_act_rep_km > planned_rep_km * 1.40:
                return True
        if planned_reps >= 2 and eff_act_reps >= 2:
            if eff_act_reps < planned_reps * 0.65 or eff_act_reps > planned_reps * 1.40:
                return True

    # 2C. Mountain / Hill Climb / Trail vs Flat Road combination mismatch
    is_planned_climb = bool(
        w_type in ("trail", "trail_climb", "hill", "mountain")
        or any(k in plan_title_raw for k in ("山地", "爬坡", "越野", "阶梯", "D+"))
        or "累计爬升" in core_plan_desc
    )
    elev_m_match = re.search(r"爬升\s*\+?\s*(\d+)\s*(?:m|米)", f"{plan_title_raw} {core_plan_desc}", re.I)
    planned_elev_m = float(elev_m_match.group(1)) if elev_m_match else (150.0 if is_planned_climb else 0.0)
    actual_elev_m = float(
        activity.get("elevation_gain_meters")
        or activity.get("total_elevation_gain")
        or activity.get("elevationGain")
        or 0.0
    )
    min_climb_req = max(80.0, planned_elev_m * 0.35) if planned_elev_m > 0 else 120.0
    is_actual_climb = bool(
        actual_elev_m >= min_climb_req
        or any(k in act_name.lower() for k in ("山", "坡", "越野", "阶梯", "楼梯", "trail", "hill"))
    )
    if is_planned_climb and not is_actual_climb:
        return True
    if not is_planned_climb and (actual_elev_m >= 220.0 or "越野" in act_name or "trail" in act_name.lower()):
        return True

    # 2D. Granular phase combination checks (Progression vs Fade; 3-stage Warmup+Main+Cooldown quality structure)
    total_laps_count = sum(int(p.get("lap_count") or 1) for p in (phases or []))
    is_planned_progression = bool(
        "渐进" in f"{plan_title_raw} {plan_pace_text} {core_plan_desc}"
        or "渐速" in f"{plan_title_raw} {plan_pace_text} {core_plan_desc}"
        or w_type in ("progression", "progressive")
    )
    if phases and total_laps_count >= 4:
        if is_planned_progression and any(p.get("phase_type") == "fade" for p in phases):
            return True

        combined_wucd_text = f"{plan_title_raw} {core_plan_desc}"
        wu_m = re.search(r"热身\s*(\d+(?:\.\d+)?)\s*(?:km|k|公里)", combined_wucd_text, re.I)
        cd_m = re.search(
            r"(?:(\d+(?:\.\d+)?)\s*(?:km|k|公里)\s*冷身|冷身\s*(\d+(?:\.\d+)?)\s*(?:km|k|公里))",
            combined_wucd_text,
            re.I,
        )
        req_wu_km = float(wu_m.group(1)) if wu_m else 0.0
        req_cd_km = float(cd_m.group(1) or cd_m.group(2)) if cd_m else 0.0
        is_quality_wucd = bool(
            req_wu_km >= 1.0
            and req_cd_km >= 1.0
            and (
                w_type in ("tempo", "threshold", "marathon_pace", "interval", "intervals")
                or any(k in plan_title_raw for k in ("门槛", "节奏", "间歇", "乳酸", "马配", "巡航"))
            )
        )
        if is_quality_wucd and (not same_day_runs or len(same_day_runs) == 1):
            has_wu_phase = any(p.get("phase_type") == "warmup" for p in phases)
            has_cd_phase = any(p.get("phase_type") == "cooldown" for p in phases)
            if not has_wu_phase and not has_cd_phase:
                return True

    # ── 3. Pace Discrepancy Check (配速差异) ──
    target_p_range = (
        parse_pace_range_to_sec(main_clause)
        or parse_pace_range_to_sec(plan_pace_text)
        or parse_pace_range_to_sec(core_plan_desc)
    )
    if target_p_range and eval_pace_sec:
        lo_p, hi_p = target_p_range
        if is_planned_progression and (hi_p - lo_p >= 20):
            # Progression from hi_p (easy start) down to lo_p (fast finish):
            # Overall/main avg pace should be faster than starting easy pace and not way faster than finish pace
            if eval_pace_sec < lo_p - 10 or eval_pace_sec > hi_p - 5:
                return True
        else:
            # Standard target pace or range: > 20s/km deviation is a different training zone
            if eval_pace_sec < lo_p - 20 or eval_pace_sec > hi_p + 20:
                return True
    else:
        avg_hr = activity.get("average_heartrate")
        if avg_hr:
            hr_f = float(avg_hr)
            if w_type in ("easy_run", "recovery") and hr_f >= threshold_ceiling:
                return True
            if w_type in ("tempo", "threshold", "interval", "intervals") and hr_f < aerobic_ceiling - 12:
                return True

    return False


def parse_hr_range(text: Optional[str], max_hr: float = 185.0) -> Optional[Tuple[int, int]]:
    if not text:
        return None
    s = str(text)
    m_bpm = re.search(r"(\d{2,3})\s*[-~至–]\s*(\d{2,3})\s*(?:bpm)?", s, re.IGNORECASE)
    if m_bpm:
        a, b = int(m_bpm.group(1)), int(m_bpm.group(2))
        if 90 <= min(a, b) <= 220 and 90 <= max(a, b) <= 230:
            return (min(a, b), max(a, b))
    m_cap = re.search(r"[<≤低于不超过]\s*(\d{2,3})", s)
    if m_cap:
        cap = int(m_cap.group(1))
        if 100 <= cap <= 210:
            return (int(round(max_hr * 0.60)), cap)
    if "Z4" in s.upper() or "门槛" in s or "乳酸" in s:
        return (int(round(max_hr * 0.84)), int(round(max_hr * 0.90)))
    if "Z3" in s.upper() or "马拉松" in s or "混氧" in s:
        return (int(round(max_hr * 0.78)), int(round(max_hr * 0.85)))
    if "Z2" in s.upper() or "有氧" in s:
        return (int(round(max_hr * 0.68)), int(round(max_hr * 0.79)))
    if "Z1" in s.upper() or "恢复" in s:
        return (int(round(max_hr * 0.58)), int(round(max_hr * 0.70)))
    return None


def parse_time_str_to_seconds(t_str: Optional[str]) -> Optional[int]:
    if not t_str:
        return None
    s = str(t_str).strip()
    m_hms = re.match(r"^(\d{1,2}):(\d{1,2}):(\d{1,2})$", s)
    if m_hms:
        return int(m_hms.group(1)) * 3600 + int(m_hms.group(2)) * 60 + int(m_hms.group(3))
    m_cn = re.search(r"(?:(\d{1,2})\s*(?:小时|h|时))?\s*(\d{1,2})\s*(?:分|min|m)\s*(?:(\d{1,2})\s*秒?)?", s, re.I)
    if m_cn and (m_cn.group(1) or m_cn.group(2)):
        hh = int(m_cn.group(1) or 0)
        mm = int(m_cn.group(2) or 0)
        ss = int(m_cn.group(3) or 0)
        tot = hh * 3600 + mm * 60 + ss
        if tot >= 300:
            return tot
    m_ms = re.match(r"^(\d{2,3}):(\d{2})$", s)
    if m_ms:
        return int(m_ms.group(1)) * 60 + int(m_ms.group(2))
    return None


def compute_gap_sec(pace_sec: Optional[float], dist_m: float, elev_gain_m: float, elev_loss_m: float) -> Optional[int]:
    """Estimates Grade-Adjusted Pace (sec/km) from net elevation grade when native watch GAP is absent."""
    if not pace_sec or pace_sec <= 0 or dist_m < 80.0:
        return int(round(pace_sec)) if pace_sec else None
    net_grade = (float(elev_gain_m or 0.0) - float(elev_loss_m or 0.0)) / float(dist_m)
    net_grade = max(-0.20, min(0.25, net_grade))
    if abs(net_grade) < 0.004:
        return int(round(pace_sec))
    if net_grade > 0:
        # Uphill: ~3.2% energy/speed cost per +1% grade
        factor = 1.0 + net_grade * 3.2
    else:
        # Moderate downhill aids speed (~1.7% per -1% grade up to -8%)
        eff_down = max(-0.08, net_grade)
        factor = max(0.85, 1.0 + eff_down * 1.7)
    return int(round(float(pace_sec) / factor))


def _detect_track_loop(track_data: Optional[Dict[str, Any]], total_dist_km: float) -> bool:
    """Detects standard 400m stadium track workouts via GPS bounding box vs total distance."""
    if not isinstance(track_data, dict) or total_dist_km < 2.0:
        return False
    bounds = track_data.get("bounds") or {}
    sw = bounds.get("southwest") or {}
    ne = bounds.get("northeast") or {}
    lat1, lng1 = sw.get("latitude"), sw.get("longitude")
    lat2, lng2 = ne.get("latitude"), ne.get("longitude")
    if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
        return False
    lat_span_m = abs(float(lat2) - float(lat1)) * 111320.0
    mid_lat_rad = math.radians((float(lat1) + float(lat2)) / 2.0)
    lng_span_m = abs(float(lng2) - float(lng1)) * 111320.0 * max(0.2, math.cos(mid_lat_rad))
    return 50.0 <= max(lat_span_m, lng_span_m) <= 260.0 and 30.0 <= min(lat_span_m, lng_span_m) <= 200.0


def _steady_hr_from_telemetry(
    telemetry: List[Dict[str, Any]],
    start_km: float,
    end_km: float,
    fallback_hr: Optional[int],
    skip_lag_km: float = 0.14,
) -> Optional[int]:
    """
    Computes steady-state HR in [start_km, end_km] after compensating for initial ~35-40s (~0.14km)
    cardiac ramp-up lag at the start of an active segment.
    """
    if not telemetry or end_km - start_km < 0.25:
        return fallback_hr
    eff_start = start_km + skip_lag_km if (end_km - start_km) >= 0.45 else start_km
    hrs = [
        int(pt["hr"])
        for pt in telemetry
        if isinstance(pt, dict)
        and pt.get("dist_km") is not None
        and pt.get("hr") is not None
        and eff_start <= float(pt["dist_km"]) <= end_km + 0.03
        and 45 <= int(pt["hr"]) <= 230
    ]
    if len(hrs) >= 2:
        return int(round(sum(hrs) / len(hrs)))
    return fallback_hr


def _extract_normalized_splits(
    activity: Dict[str, Any],
    track_data: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (primary_laps, km_splits, telemetry_series).
    Normalizes any raw Garmin/COROS/DB laps or synthesizes 1km splits from telemetry if needed.
    """
    telemetry: List[Dict[str, Any]] = []
    laps_from_track: List[Dict[str, Any]] = []
    km_splits_from_track: List[Dict[str, Any]] = []
    structured_from_track: List[Dict[str, Any]] = []

    if isinstance(track_data, dict):
        telemetry = track_data.get("telemetry_series") or track_data.get("elevation_profile") or []
        laps_from_track = track_data.get("laps") or []
        km_splits_from_track = track_data.get("km_splits") or []
        structured_from_track = track_data.get("structured_splits") or []

    def _parse_json_field(val: Any) -> List[Dict[str, Any]]:
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, str) and val.strip():
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return [x for x in parsed if isinstance(x, dict)]
            except Exception:
                pass
        return []

    db_laps = _parse_json_field(activity.get("laps_data") or activity.get("laps"))
    db_splits = _parse_json_field(activity.get("splits_data") or activity.get("splits"))

    def _ensure_norm_list(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        cum_km = 0.0
        for idx, item in enumerate(raw_list, start=1):
            raw_kind = str(
                item.get("type")
                or item.get("splitType")
                or item.get("intensity_type")
                or item.get("intensityType")
                or ""
            ).upper()
            if raw_kind.startswith("RWD_"):
                continue
            dist_m = float(item.get("distance_m") or item.get("distance") or 0.0)
            dur_s = float(item.get("duration_s") or item.get("movingDuration") or item.get("duration") or 0.0)
            if dist_m <= 5.0 and dur_s <= 2.0:
                continue
            p_sec = item.get("pace_sec")
            if p_sec is None:
                avg_spd = float(item.get("averageMovingSpeed") or item.get("averageSpeed") or 0.0)
                if avg_spd > 0.35:
                    p_sec = int(round(1000.0 / avg_spd))
                elif dist_m >= 25.0 and dur_s > 0:
                    p_sec = int(round(dur_s / (dist_m / 1000.0)))
            if p_sec is not None and not (90 <= int(p_sec) <= 1200):
                p_sec = None

            eg = float(item.get("elev_gain_m") or item.get("elevationGain") or 0.0)
            el = float(item.get("elev_loss_m") or item.get("elevationLoss") or 0.0)
            gap_sec = item.get("gap_sec")
            if gap_sec is None and p_sec is not None:
                gap_sec = compute_gap_sec(p_sec, dist_m, eg, el)

            avg_hr = item.get("avg_hr") or item.get("averageHR") or item.get("avgHr")
            max_hr = item.get("max_hr") or item.get("maxHR") or item.get("maxHr")
            cad = item.get("avg_cadence") or item.get("averageRunCadence") or item.get("avgCadence")
            itype = str(item.get("intensity_type") or item.get("intensityType") or "AUTO").upper()
            if "WARMUP" in itype:
                itype = "WARMUP"
            elif "COOLDOWN" in itype:
                itype = "COOLDOWN"
            elif "RECOVERY" in itype or "REST" in itype:
                itype = "RECOVERY"
            elif "ACTIVE" in itype and itype != "INTERVAL":
                itype = "ACTIVE"
            else:
                itype = "AUTO"

            start_km = round(cum_km, 2)
            cum_km += dist_m / 1000.0
            end_km = round(cum_km, 2)

            out.append({
                "lap_index": int(item.get("lap_index") or item.get("lapIndex") or idx),
                "start_km": start_km,
                "end_km": end_km,
                "distance_m": round(dist_m, 1),
                "distance_km": round(dist_m / 1000.0, 2),
                "duration_s": round(dur_s, 1),
                "pace_sec": int(p_sec) if p_sec is not None else None,
                "pace_str": fmt_pace_sec(p_sec),
                "gap_sec": int(gap_sec) if gap_sec is not None else None,
                "gap_str": fmt_pace_sec(gap_sec) if gap_sec is not None else None,
                "avg_hr": int(round(float(avg_hr))) if avg_hr else None,
                "max_hr": int(round(float(max_hr))) if max_hr else None,
                "avg_cadence": int(round(float(cad))) if cad else None,
                "elev_gain_m": round(eg, 1),
                "elev_loss_m": round(el, 1),
                "intensity_type": itype,
            })
        return out

    act_dist_m = float(activity.get("distance_meters") or 0.0)

    def _filter_sequential_list(cand: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not cand:
            return []
        if act_dist_m > 1000.0:
            cand_sum_m = sum(float(x.get("distance_m") or 0.0) for x in cand)
            # Reject overlapping summary buckets (e.g. Garmin INTERVAL_ACTIVE + RWD_RUN summing to ~2x distance)
            if cand_sum_m > act_dist_m * 1.30:
                return []
        return cand

    norm_structured = _filter_sequential_list(_ensure_norm_list(structured_from_track))
    norm_laps = _filter_sequential_list(_ensure_norm_list(laps_from_track or db_laps))
    norm_km = _filter_sequential_list(_ensure_norm_list(km_splits_from_track or db_splits))

    # Synthesize 1km splits from telemetry_series when watch laps/splits are missing (e.g. GPX/TCX/FIT imports)
    if not norm_laps and not norm_km and len(telemetry) >= 6:
        synth: List[Dict[str, Any]] = []
        bucket_idx = 1
        bucket_pts: List[Dict[str, Any]] = []
        prev_km = 0.0
        for pt in telemetry:
            dk = pt.get("dist_km")
            if dk is None:
                continue
            dk_f = float(dk)
            bucket_pts.append(pt)
            if dk_f >= bucket_idx * 1.0:
                seg_dist_m = max(100.0, (dk_f - prev_km) * 1000.0)
                paces = [int(p["pace_sec"]) for p in bucket_pts if p.get("pace_sec")]
                hrs = [int(p["hr"]) for p in bucket_pts if p.get("hr")]
                cads = [int(p["cadence"]) for p in bucket_pts if p.get("cadence")]
                elevs = [float(p["elevation_m"]) for p in bucket_pts if p.get("elevation_m") is not None]
                t_vals = [float(p["elapsed_s"]) for p in bucket_pts if p.get("elapsed_s") is not None]
                if len(t_vals) >= 2 and t_vals[-1] > t_vals[0]:
                    dur_s = t_vals[-1] - t_vals[0]
                    p_sec = int(round(dur_s / (seg_dist_m / 1000.0)))
                elif paces:
                    p_sec = int(round(sum(paces) / len(paces)))
                    dur_s = p_sec * (seg_dist_m / 1000.0)
                else:
                    p_sec = parse_pace_str_to_sec(activity.get("avg_pace_str"))
                    dur_s = (p_sec or 330) * (seg_dist_m / 1000.0)
                eg = sum(max(0.0, b - a) for a, b in zip(elevs, elevs[1:])) if len(elevs) >= 2 else 0.0
                el = sum(max(0.0, a - b) for a, b in zip(elevs, elevs[1:])) if len(elevs) >= 2 else 0.0
                gap_s = compute_gap_sec(p_sec, seg_dist_m, eg, el)
                synth.append({
                    "lap_index": bucket_idx,
                    "start_km": round(prev_km, 2),
                    "end_km": round(dk_f, 2),
                    "distance_m": round(seg_dist_m, 1),
                    "distance_km": round(seg_dist_m / 1000.0, 2),
                    "duration_s": round(dur_s, 1),
                    "pace_sec": p_sec,
                    "pace_str": fmt_pace_sec(p_sec),
                    "gap_sec": gap_s,
                    "gap_str": fmt_pace_sec(gap_s),
                    "avg_hr": int(round(sum(hrs) / len(hrs))) if hrs else None,
                    "max_hr": max(hrs) if hrs else None,
                    "avg_cadence": int(round(sum(cads) / len(cads))) if cads else None,
                    "elev_gain_m": round(eg, 1),
                    "elev_loss_m": round(el, 1),
                    "intensity_type": "AUTO",
                })
                prev_km = dk_f
                bucket_idx += 1
                bucket_pts = []
        # Remainder tail >= 200m
        if bucket_pts and telemetry[-1].get("dist_km") is not None:
            last_dk = float(telemetry[-1]["dist_km"])
            rem_m = (last_dk - prev_km) * 1000.0
            if rem_m >= 200.0:
                paces = [int(p["pace_sec"]) for p in bucket_pts if p.get("pace_sec")]
                hrs = [int(p["hr"]) for p in bucket_pts if p.get("hr")]
                p_sec = int(round(sum(paces) / len(paces))) if paces else parse_pace_str_to_sec(activity.get("avg_pace_str"))
                dur_s = (p_sec or 330) * (rem_m / 1000.0)
                synth.append({
                    "lap_index": bucket_idx,
                    "start_km": round(prev_km, 2),
                    "end_km": round(last_dk, 2),
                    "distance_m": round(rem_m, 1),
                    "distance_km": round(rem_m / 1000.0, 2),
                    "duration_s": round(dur_s, 1),
                    "pace_sec": p_sec,
                    "pace_str": fmt_pace_sec(p_sec),
                    "gap_sec": p_sec,
                    "gap_str": fmt_pace_sec(p_sec),
                    "avg_hr": int(round(sum(hrs) / len(hrs))) if hrs else None,
                    "max_hr": max(hrs) if hrs else None,
                    "avg_cadence": None,
                    "elev_gain_m": 0.0,
                    "elev_loss_m": 0.0,
                    "intensity_type": "AUTO",
                })
        norm_laps = synth
        norm_km = synth

    has_watch_stages = any(
        x.get("intensity_type") in ("WARMUP", "COOLDOWN", "RECOVERY")
        for x in norm_structured
    )
    primary = norm_structured if (has_watch_stages and len(norm_structured) >= 2) else (norm_laps or norm_km)
    if km_splits_from_track and norm_km:
        km_list = norm_km
    elif norm_laps and len(norm_laps) >= len(norm_km):
        km_list = norm_laps
    else:
        km_list = norm_km if norm_km else norm_laps
    return primary, km_list, telemetry


def _aggregate_laps(
    laps: List[Dict[str, Any]],
    phase_key: str,
    label: str,
    telemetry: List[Dict[str, Any]],
) -> Dict[str, Any]:
    dist_m = sum(float(l.get("distance_m") or 0.0) for l in laps)
    dur_s = sum(float(l.get("duration_s") or 0.0) for l in laps)
    eg = sum(float(l.get("elev_gain_m") or 0.0) for l in laps)
    el = sum(float(l.get("elev_loss_m") or 0.0) for l in laps)
    start_km = float(laps[0].get("start_km") or 0.0) if laps else 0.0
    end_km = float(laps[-1].get("end_km") or round(start_km + dist_m / 1000.0, 2)) if laps else 0.0

    p_sec = int(round(dur_s / (dist_m / 1000.0))) if dist_m >= 30.0 and dur_s > 0 else (laps[0].get("pace_sec") if laps else None)
    gap_sec = compute_gap_sec(p_sec, dist_m, eg, el)

    hr_weighted_num = sum(float(l["avg_hr"]) * float(l.get("duration_s") or 1.0) for l in laps if l.get("avg_hr"))
    hr_weighted_den = sum(float(l.get("duration_s") or 1.0) for l in laps if l.get("avg_hr"))
    raw_avg_hr = int(round(hr_weighted_num / hr_weighted_den)) if hr_weighted_den > 0 else None
    steady_hr = _steady_hr_from_telemetry(
        telemetry,
        start_km,
        end_km,
        raw_avg_hr,
        skip_lag_km=0.15 if phase_key in ("cruise", "progression", "intervals") else 0.0,
    )
    max_hrs = [int(l["max_hr"]) for l in laps if l.get("max_hr")]
    cads = [int(l["avg_cadence"]) for l in laps if l.get("avg_cadence")]

    # Compute Aerobic Decoupling (Pa:Hr %) when segment has >= 4 laps
    decoupling_pct: Optional[float] = None
    valid_hr_laps = [l for l in laps if l.get("avg_hr") and (l.get("gap_sec") or l.get("pace_sec")) and float(l.get("distance_m") or 0) >= 400]
    if len(valid_hr_laps) >= 4:
        mid = len(valid_hr_laps) // 2
        h1 = valid_hr_laps[:mid]
        h2 = valid_hr_laps[mid:]
        spd1 = sum(1000.0 / float(x.get("gap_sec") or x["pace_sec"]) for x in h1) / len(h1)
        hr1 = sum(float(x["avg_hr"]) for x in h1) / len(h1)
        spd2 = sum(1000.0 / float(x.get("gap_sec") or x["pace_sec"]) for x in h2) / len(h2)
        hr2 = sum(float(x["avg_hr"]) for x in h2) / len(h2)
        if hr1 > 60 and hr2 > 60 and spd1 > 0.5:
            ef1 = spd1 / hr1
            ef2 = spd2 / hr2
            decoupling_pct = round(((ef1 - ef2) / ef1) * 100.0, 1)

    return {
        "phase_type": phase_key,
        "label": label,
        "start_km": round(start_km, 2),
        "end_km": round(end_km, 2),
        "range_str": f"{round(start_km, 1)}~{round(end_km, 1)}km",
        "distance_km": round(dist_m / 1000.0, 2),
        "duration_s": int(round(dur_s)),
        "duration_str": fmt_duration_hms(dur_s),
        "pace_sec": p_sec,
        "pace_str": fmt_pace_sec(p_sec),
        "gap_sec": gap_sec,
        "gap_str": fmt_pace_sec(gap_sec),
        "avg_hr": raw_avg_hr,
        "steady_hr": steady_hr,
        "max_hr": max(max_hrs) if max_hrs else raw_avg_hr,
        "avg_cadence": int(round(sum(cads) / len(cads))) if cads else None,
        "elev_gain_m": round(eg, 1),
        "elev_loss_m": round(el, 1),
        "decoupling_pct": decoupling_pct,
        "lap_count": len(laps),
    }


def _is_trail_or_mountain_activity(
    activity: Optional[Dict[str, Any]],
    primary_laps: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    Returns True when an activity is a trail, mountain, or significant hill-climb run.
    In trail/mountain running, slow segments (power-hiking on climbs) are terrain adaptations
    and must NEVER be interpreted as interval recovery bouts or road pace fade.
    """
    if not activity:
        return False
    sport_type = str(activity.get("sport_type") or activity.get("activity_type") or "").lower()
    act_name = str(activity.get("name") or "")
    act_name_lower = act_name.lower()
    if any(k in sport_type for k in ("trail", "mountain", "越野", "登山")):
        return True
    if any(k in act_name for k in ("越野", "山地", "爬山", "登山", "山野", "爬坡")) or "trail" in act_name_lower:
        return True
    elev_gain = float(
        activity.get("elevation_gain_meters")
        or activity.get("total_elevation_gain")
        or activity.get("elevationGain")
        or 0.0
    )
    if elev_gain <= 0 and primary_laps:
        elev_gain = sum(float(l.get("elev_gain_m") or 0.0) for l in primary_laps)
    dist_km = float(activity.get("distance_meters") or 0.0) / 1000.0
    if dist_km <= 0 and primary_laps:
        dist_km = sum(float(l.get("distance_m") or 0.0) for l in primary_laps) / 1000.0
    if elev_gain >= 180.0:
        return True
    if dist_km >= 3.0 and (elev_gain / dist_km) >= 22.0:
        return True
    return False


def _has_explicit_interval_intent(
    activity: Optional[Dict[str, Any]],
    planned_day: Optional[Dict[str, Any]] = None,
) -> bool:
    """Returns True if the activity name or matched plan explicitly indicates an interval/fartlek session."""
    act_name = str((activity or {}).get("name") or "")
    reps_a, rep_km_a = _extract_planned_interval_spec(act_name)
    if (reps_a >= 2 and rep_km_a >= 0.15) or re.search(
        r"(\d+\s*(?:m|米|km|k)\s*\+\s*\d+\s*(?:m|米|km|k)|\b(?:1st|2nd|3rd|\d+th)\b|间歇|变速|法特莱克)",
        act_name,
        re.I,
    ):
        return True
    if planned_day:
        w_type = str(planned_day.get("workout_type") or "").lower()
        p_text = f"{planned_day.get('title') or ''} {planned_day.get('description') or ''}"
        reps_p, rep_km_p = _extract_planned_interval_spec(p_text)
        if (
            w_type in ("interval", "intervals", "fartlek", "speed", "track", "reps")
            or any(k in p_text for k in ("间歇", "变速", "法特莱克", "重复跑"))
            or (reps_p >= 2 and rep_km_p >= 0.18)
        ):
            return True
    return False


def segment_workout_phases(
    primary_laps: List[Dict[str, Any]],
    telemetry: List[Dict[str, Any]],
    planned_wu_km: float = 0.0,
    planned_cd_km: float = 0.0,
    is_trail: bool = False,
    is_explicit_interval: bool = False,
    aerobic_ceiling: float = 152.0,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Segments a training session into ordered phases (Warm-up, Main Cruise / Progression / Intervals, Cool-down).
    Returns (phases_list, interval_summary_or_None).
    Strictly guards against misclassifying:
    1) Trail / mountain runs (where uphill power-hiking causes slow splits) as intervals.
    2) Road or track runs with pauses / stops / water breaks as intervals.
    """
    if not primary_laps:
        return [], None

    # ── Priority 0: Trail / Mountain Running (never segment uphill hiking as interval rest or road fade) ──
    if is_trail:
        trail_phase = _aggregate_laps(primary_laps, "cruise", "🏔️ 山地越野巡航", telemetry)
        return [trail_phase], None

    # ── Priority 1: Watch explicitly tagged WARMUP / ACTIVE / RECOVERY / COOLDOWN ──
    explicit_tags = [l.get("intensity_type") for l in primary_laps]
    if any(t in ("WARMUP", "COOLDOWN", "RECOVERY") for t in explicit_tags):
        leading_wu: List[Dict[str, Any]] = []
        trailing_cd: List[Dict[str, Any]] = []
        idx_start = 0
        idx_end = len(primary_laps)
        while idx_start < idx_end and primary_laps[idx_start].get("intensity_type") == "WARMUP":
            leading_wu.append(primary_laps[idx_start])
            idx_start += 1
        while idx_end > idx_start and primary_laps[idx_end - 1].get("intensity_type") == "COOLDOWN":
            trailing_cd.insert(0, primary_laps[idx_end - 1])
            idx_end -= 1
        core_laps = primary_laps[idx_start:idx_end]
        phases: List[Dict[str, Any]] = []
        if leading_wu:
            phases.append(_aggregate_laps(leading_wu, "warmup", "🔥 热身激活", telemetry))

        work_reps = [l for l in core_laps if l.get("intensity_type") in ("ACTIVE", "AUTO")]
        # Exclude stationary/near-zero-distance pause records (< 40m or > 13:00/km) from valid interval recovery joggers
        valid_rest_reps = [
            l for l in core_laps
            if l.get("intensity_type") == "RECOVERY"
            and float(l.get("distance_m") or 0.0) >= 40.0
            and (l.get("pace_sec") is None or int(l["pace_sec"]) <= 780)
        ]
        has_paired_recoveries = (
            len(work_reps) >= 2
            and len(valid_rest_reps) >= max(1, len(work_reps) - 1)
        )
        interval_meta: Optional[Dict[str, Any]] = None
        if has_paired_recoveries:
            work_agg = _aggregate_laps(work_reps, "intervals", f"⚡ 间歇主课 ({len(work_reps)}组)", telemetry)
            rest_agg = _aggregate_laps(valid_rest_reps, "recovery", "🫧 间歇慢跑/休息", telemetry)
            w_p = work_agg.get("pace_sec") or 999
            r_p = rest_agg.get("pace_sec") or 0
            # Ensure work reps are genuinely faster than recovery reps and not slow walking/hiking
            max_allowed_work_pace = 400 if is_explicit_interval else 360
            if w_p <= max_allowed_work_pace and (r_p == 0 or r_p - w_p >= 15):
                rep_paces = [l["pace_str"].replace("/km", "") for l in work_reps if l.get("pace_sec")]
                rep_secs = [int(l["pace_sec"]) for l in work_reps if l.get("pace_sec")]
                fade_s = (rep_secs[-1] - rep_secs[0]) if len(rep_secs) >= 2 else 0
                hr_drop = (
                    (work_agg["steady_hr"] - rest_agg["avg_hr"])
                    if (work_agg.get("steady_hr") and rest_agg.get("avg_hr"))
                    else None
                )
                interval_meta = {
                    "rep_count": len(work_reps),
                    "avg_rep_km": round(sum(float(x["distance_m"]) for x in work_reps) / len(work_reps) / 1000.0, 2),
                    "work_pace_sec": work_agg["pace_sec"],
                    "work_pace_str": work_agg["pace_str"],
                    "work_steady_hr": work_agg["steady_hr"],
                    "rest_pace_str": rest_agg["pace_str"],
                    "rest_avg_hr": rest_agg["avg_hr"],
                    "hr_recovery_drop": hr_drop,
                    "rep_paces": rep_paces[:12],
                    "fade_sec": fade_s,
                }
                work_agg["start_km"] = round(float(core_laps[0]["start_km"]), 2)
                work_agg["end_km"] = round(float(core_laps[-1]["end_km"]), 2)
                work_agg["range_str"] = f"{round(work_agg['start_km'], 1)}~{round(work_agg['end_km'], 1)}km"
                work_agg["interval_detail"] = interval_meta
                phases.append(work_agg)

        if interval_meta is None and core_laps:
            # Continuous run (e.g. had 1-2 isolated pause/REST laps on road or track): keep moving laps together
            moving_core = [l for l in core_laps if float(l.get("distance_m") or 0.0) >= 30.0] or core_laps
            phases.append(_aggregate_laps(moving_core, "cruise", "🎯 主课巡航", telemetry))

        if trailing_cd:
            phases.append(_aggregate_laps(trailing_cd, "cooldown", "🧊 冷身排酸", telemetry))
        return phases, interval_meta

    # ── Priority 2: Pace / GAP + HR Change-Point Detection (handles 1km auto-laps & manual interval laps) ──
    usable = [l for l in primary_laps if (l.get("gap_sec") or l.get("pace_sec"))]
    if len(usable) <= 1:
        single = _aggregate_laps(primary_laps, "cruise", "🎯 全程稳态跑", telemetry)
        return [single], None

    paces_eff = [int(l.get("gap_sec") or l["pace_sec"]) for l in usable]
    sorted_paces = sorted(paces_eff)
    # Typical fast/main reference pace (35th percentile so warm-up/pause laps don't skew it)
    ref_idx = max(0, int((len(sorted_paces) - 1) * 0.35))
    fast_ref_sec = sorted_paces[ref_idx]

    # 2A. Detect Warm-up at start (1 to 3 laps slower than main body by >= 16s/km, or aligned with planned_wu_km)
    # Do not misclassify a severe pause/stop on lap 1 (> 90s/km slower or >= 7:30/km) as warmup when unplanned.
    wu_end_idx = 0
    max_wu_laps = min(len(primary_laps) - 1, max(3, int(round(planned_wu_km)) + 1 if planned_wu_km > 0 else 3))
    cum_wu_km = 0.0
    wu_threshold_delta = 12 if planned_wu_km > 0 else 16
    for i in range(max_wu_laps):
        lap = primary_laps[i]
        lp = lap.get("gap_sec") or lap.get("pace_sec")
        lap_km = float(lap.get("distance_m") or 0.0) / 1000.0
        if lp is None:
            break
        if planned_wu_km > 0 and cum_wu_km + lap_km <= planned_wu_km + 0.35 and (lp - fast_ref_sec >= 8):
            wu_end_idx = i + 1
            cum_wu_km += lap_km
        elif (
            wu_threshold_delta <= (lp - fast_ref_sec) <= 90
            and lp < 450
            and cum_wu_km + lap_km <= 3.3
        ):
            wu_end_idx = i + 1
            cum_wu_km += lap_km
        else:
            break

    # 2B. Detect Cool-down at end (1 to 3 laps slower than main body by >= 18s/km, or aligned with planned_cd_km)
    cd_start_idx = len(primary_laps)
    cum_cd_km = 0.0
    cd_threshold_delta = 12 if planned_cd_km > 0 else 18
    for j in range(len(primary_laps) - 1, wu_end_idx, -1):
        lap = primary_laps[j]
        lp = lap.get("gap_sec") or lap.get("pace_sec")
        lap_km = float(lap.get("distance_m") or 0.0) / 1000.0
        if lp is None or j <= wu_end_idx:
            break
        if planned_cd_km > 0 and cum_cd_km + lap_km <= planned_cd_km + 0.4 and (lp - fast_ref_sec >= 8):
            cd_start_idx = j
            cum_cd_km += lap_km
        elif (
            cd_threshold_delta <= (lp - fast_ref_sec) <= 95
            and lp < 450
            and cum_cd_km + lap_km <= 3.2
            and (lap_km >= 0.30 or cum_cd_km > 0)
        ):
            cd_start_idx = j
            cum_cd_km += lap_km
        else:
            break

    wu_laps = primary_laps[:wu_end_idx]
    core_laps = primary_laps[wu_end_idx:cd_start_idx]
    cd_laps = primary_laps[cd_start_idx:]

    if not core_laps:
        core_laps = primary_laps
        wu_laps = []
        cd_laps = []

    # 2C. Check if Core Laps exhibit genuine Alternating Fast/Slow Intervals
    # Strictly reject pauses / stops / traffic lights / walking segments during road or track runs!
    fallback_ref_sec = int(fast_ref_sec or 330)
    core_paces = [int(l.get("gap_sec") or l.get("pace_sec") or fallback_ref_sec) for l in core_laps]
    interval_meta = None
    phases = []

    if wu_laps:
        phases.append(_aggregate_laps(wu_laps, "warmup", "🔥 热身激活", telemetry))

    if len(core_laps) >= 4:
        p_min, p_max = min(core_paces), max(core_paces)
        if p_max - p_min >= 35:
            split_cut = p_min + int((p_max - p_min) * 0.45)
            flags = ["F" if p <= split_cut else "S" for p in core_paces]
            transitions = sum(1 for a, b in zip(flags, flags[1:]) if a != b)
            fast_laps = [l for l, fl in zip(core_laps, flags) if fl == "F"]
            slow_laps = [l for l, fl in zip(core_laps, flags) if fl == "S"]

            # Compute contiguous run lengths of 'F' and 'S' to verify 1-to-1 alternation
            # (In a continuous run with 1-3 pauses, there are multiple consecutive 'F' laps like F,F,F,S,F,F,S)
            max_consec_f = 0
            cur_f = 0
            for fl in flags:
                if fl == "F":
                    cur_f += 1
                    if cur_f > max_consec_f:
                        max_consec_f = cur_f
                else:
                    cur_f = 0

            fast_paces_raw = [int(l.get("gap_sec") or l.get("pace_sec") or fallback_ref_sec) for l in fast_laps]
            slow_paces_raw = [int(l.get("gap_sec") or l.get("pace_sec") or fallback_ref_sec) for l in slow_laps]
            fast_spread = (max(fast_paces_raw) - min(fast_paces_raw)) if len(fast_paces_raw) >= 2 else 0
            avg_core_lap_m = sum(float(l.get("distance_m") or 0.0) for l in core_laps) / len(core_laps)
            is_auto_km_laps = avg_core_lap_m >= 750.0

            # Check whether slow_laps are actually paused/stopped/walked laps rather than interval recovery floats
            max_slow_p = max(slow_paces_raw) if slow_paces_raw else 999
            min_fast_p = sum(fast_paces_raw) / len(fast_paces_raw) if fast_paces_raw else 999
            has_pause_contaminated_lap = bool(
                not is_explicit_interval
                and (
                    max_slow_p >= 420  # >= 7:00/km on an unlabeled lap indicates a pause/stop/walk
                    or (is_auto_km_laps and (max_slow_p - min_fast_p >= 75 or max_slow_p >= 400))
                )
            )

            is_strictly_alternating = (
                transitions >= 4
                and len(fast_laps) >= 3
                and len(slow_laps) >= len(fast_laps) - 1
                and len(fast_laps) <= len(slow_laps) + 1
                and max_consec_f <= (2 if is_explicit_interval else 1)
            )
            max_work_pace_sec = 360 if is_explicit_interval else 330
            max_work_spread_sec = 35 if is_explicit_interval else 25

            if (
                is_strictly_alternating
                and not has_pause_contaminated_lap
                and min_fast_p <= max_work_pace_sec
                and fast_spread <= max_work_spread_sec
            ):
                work_agg = _aggregate_laps(fast_laps, "intervals", f"⚡ 变速/间歇主课 ({len(fast_laps)}组)", telemetry)
                rest_agg = _aggregate_laps(slow_laps, "recovery", "🫧 间休慢跑", telemetry)
                w_hr = work_agg.get("steady_hr") or work_agg.get("avg_hr")
                # Unlabeled laps must not be low-HR Zone 1/2 easy jogging masquerading as intervals
                hr_ok = bool(is_explicit_interval or w_hr is None or w_hr >= aerobic_ceiling - 10)
                if hr_ok:
                    rep_paces = [l["pace_str"].replace("/km", "") for l in fast_laps if l.get("pace_sec")]
                    rep_secs = [int(l["pace_sec"]) for l in fast_laps if l.get("pace_sec")]
                    fade_s = (rep_secs[-1] - rep_secs[0]) if len(rep_secs) >= 2 else 0
                    hr_drop = (
                        (work_agg["steady_hr"] - rest_agg["avg_hr"])
                        if (work_agg.get("steady_hr") and rest_agg.get("avg_hr"))
                        else None
                    )
                    interval_meta = {
                        "rep_count": len(fast_laps),
                        "avg_rep_km": round(sum(float(x["distance_m"]) for x in fast_laps) / len(fast_laps) / 1000.0, 2),
                        "work_pace_sec": work_agg["pace_sec"],
                        "work_pace_str": work_agg["pace_str"],
                        "work_steady_hr": work_agg["steady_hr"],
                        "rest_pace_str": rest_agg["pace_str"],
                        "rest_avg_hr": rest_agg["avg_hr"],
                        "hr_recovery_drop": hr_drop,
                        "rep_paces": rep_paces[:12],
                        "fade_sec": fade_s,
                    }
                    work_agg["start_km"] = round(float(core_laps[0]["start_km"]), 2)
                    work_agg["end_km"] = round(float(core_laps[-1]["end_km"]), 2)
                    work_agg["range_str"] = f"{round(work_agg['start_km'], 1)}~{round(work_agg['end_km'], 1)}km"
                    work_agg["interval_detail"] = interval_meta
                    phases.append(work_agg)

    # 2D. Non-interval Core: Check Progression vs Steady Cruise vs Late Fade
    # Filter out single-lap pause outliers (e.g. traffic light / water stop > fast_ref_sec + 75s) when comparing thirds
    if interval_meta is None:
        if len(core_laps) >= 4:
            third = max(1, len(core_laps) // 3)
            first_part = core_laps[:third]
            last_part = core_laps[-third:]
            pause_cut = fallback_ref_sec + 75
            p_first_vals = [
                int(x.get("gap_sec") or x.get("pace_sec") or fallback_ref_sec)
                for x in first_part
                if int(x.get("gap_sec") or x.get("pace_sec") or fallback_ref_sec) <= pause_cut
            ] or [int(x.get("gap_sec") or x.get("pace_sec") or fallback_ref_sec) for x in first_part]
            p_last_vals = [
                int(x.get("gap_sec") or x.get("pace_sec") or fallback_ref_sec)
                for x in last_part
                if int(x.get("gap_sec") or x.get("pace_sec") or fallback_ref_sec) <= pause_cut
            ]
            p_first = sum(p_first_vals) / len(p_first_vals)
            # Only evaluate progression/fade if last_part isn't purely a paused outlier lap
            if p_last_vals:
                p_last = sum(p_last_vals) / len(p_last_vals)
                delta = p_last - p_first  # negative = sped up, positive = slowed down
            else:
                delta = 0.0

            if delta <= -12 and len(p_last_vals) >= max(1, len(last_part) - 1):
                # Split core into Base Cruise + Progression Finish
                split_pt = len(core_laps) - third
                phases.append(_aggregate_laps(core_laps[:split_pt], "cruise", "🎯 前中段稳态巡航", telemetry))
                phases.append(_aggregate_laps(core_laps[split_pt:], "progression", "🚀 后程渐进提速", telemetry))
            elif delta >= 16 and not cd_laps and len(p_last_vals) == len(last_part):
                split_pt = len(core_laps) - third
                phases.append(_aggregate_laps(core_laps[:split_pt], "cruise", "🎯 前中段巡航", telemetry))
                phases.append(_aggregate_laps(core_laps[split_pt:], "fade", "⚠️ 后程心率漂移/掉速", telemetry))
            else:
                phases.append(_aggregate_laps(core_laps, "cruise", "🎯 主课稳态巡航", telemetry))
        else:
            phases.append(_aggregate_laps(core_laps, "cruise", "🎯 主课稳态巡航", telemetry))

    if cd_laps:
        phases.append(_aggregate_laps(cd_laps, "cooldown", "🧊 冷身排酸", telemetry))

    return phases, interval_meta


def _build_race_diagnosis(
    activity: Dict[str, Any],
    preset_race: Dict[str, Any],
    km_splits: List[Dict[str, Any]],
    telemetry: List[Dict[str, Any]],
    max_hr: float,
) -> Dict[str, Any]:
    dist_km = round(float(activity.get("distance_meters") or 0.0) / 1000.0, 2)
    mov_s = int(activity.get("moving_time_seconds") or activity.get("elapsed_time_seconds") or 0)
    overall_pace_sec = int(round(mov_s / dist_km)) if dist_km > 0.2 and mov_s > 0 else parse_pace_str_to_sec(activity.get("avg_pace_str"))
    avg_hr = activity.get("average_heartrate")

    race_name = str(preset_race.get("name") or "预设目标比赛").strip()
    race_type = str(preset_race.get("race_type") or "").strip()
    target_time_str = str(preset_race.get("target_time") or "").strip()
    target_sec = parse_time_str_to_seconds(target_time_str)

    # Determine canonical stage boundaries based on race distance
    if dist_km >= 36.0 or "全马" in race_type or "full" in race_type.lower():
        stage_defs = [
            ("start_control", "🚦 起跑控制期 (0~5km)", 0.0, 5.0),
            ("early_cruise", "🎯 前半巡航期 (5~20km)", 5.0, 20.0),
            ("mid_lock", "⚙️ 中后段定速期 (20~30km)", 20.0, 30.0),
            ("wall_zone", "🔥 撞墙临界区 (30~38km)", 30.0, 38.0),
            ("final_kick", "🏁 终段冲刺期 (38km~终点)", 38.0, max(42.5, dist_km + 0.5)),
        ]
        half_mark_km = 21.0975
    elif dist_km >= 18.0 or "半马" in race_type or "half" in race_type.lower():
        stage_defs = [
            ("start_control", "🚦 起跑定速期 (0~3km)", 0.0, 3.0),
            ("early_cruise", "🎯 阈值巡航期 (3~15km)", 3.0, 15.0),
            ("wall_zone", "🔥 抗衰减关键区 (15~19km)", 15.0, 19.0),
            ("final_kick", "🏁 终段冲刺期 (19km~终点)", 19.0, max(21.5, dist_km + 0.5)),
        ]
        half_mark_km = 10.55
    else:
        q1 = round(dist_km * 0.2, 1)
        q2 = round(dist_km * 0.7, 1)
        stage_defs = [
            ("start_control", f"🚦 起跑出发段 (0~{q1}km)", 0.0, q1),
            ("early_cruise", f"🎯 核心维持段 ({q1}~{q2}km)", q1, q2),
            ("final_kick", f"🏁 后程顶住与冲刺 ({q2}km~终点)", q2, dist_km + 0.5),
        ]
        half_mark_km = round(dist_km / 2.0, 2)

    stages: List[Dict[str, Any]] = []
    if km_splits:
        for skey, slabel, s_lo, s_hi in stage_defs:
            matched = [
                l for l in km_splits
                if float(l.get("end_km") or 0) > s_lo + 0.05 and float(l.get("start_km") or 0) < s_hi - 0.05
            ]
            if matched:
                agg = _aggregate_laps(matched, skey, slabel, telemetry)
                stages.append(agg)

    # First Half vs Second Half Split Calculation
    half_split_info: Optional[Dict[str, Any]] = None
    if len(km_splits) >= 4:
        h1_laps = [l for l in km_splits if float(l.get("end_km") or 0) <= half_mark_km + 0.45]
        h2_laps = [l for l in km_splits if float(l.get("end_km") or 0) > half_mark_km + 0.45]
        if h1_laps and h2_laps:
            p1_dist = sum(float(x["distance_m"]) for x in h1_laps) / 1000.0
            p1_dur = sum(float(x["duration_s"]) for x in h1_laps)
            p2_dist = sum(float(x["distance_m"]) for x in h2_laps) / 1000.0
            p2_dur = sum(float(x["duration_s"]) for x in h2_laps)
            if p1_dist > 1.0 and p2_dist > 1.0:
                pace1 = p1_dur / p1_dist
                pace2 = p2_dur / p2_dist
                pace_diff_sec = int(round(pace2 - pace1))
                # Normalize both halves to equal half_mark_km duration for apples-to-apples split delta
                norm_h1_s = int(round(pace1 * half_mark_km))
                norm_h2_s = int(round(pace2 * half_mark_km))
                half_time_diff_s = norm_h2_s - norm_h1_s
                if half_time_diff_s <= -25:
                    split_label = f"🔥 完美负劈（后半程快 {fmt_duration_hms(abs(half_time_diff_s))}）"
                    split_code = "negative"
                elif half_time_diff_s <= 60:
                    split_label = f"✅ 教科书匀速（前后半程差仅 {abs(half_time_diff_s)} 秒）"
                    split_code = "even"
                else:
                    split_label = f"⚠️ 正劈掉速（后半程慢 {fmt_duration_hms(half_time_diff_s)}）"
                    split_code = "positive"
                half_split_info = {
                    "split_code": split_code,
                    "split_label": split_label,
                    "first_half_pace": fmt_pace_sec(pace1),
                    "second_half_pace": fmt_pace_sec(pace2),
                    "pace_diff_sec_per_km": pace_diff_sec,
                    "half_time_diff_seconds": half_time_diff_s,
                }

    # Detect Fade Inflection Km & Physiological Root Cause
    cruise_laps = [
        l for l in km_splits
        if 2.0 <= float(l.get("end_km") or 0) <= max(5.0, dist_km * 0.55)
        and l.get("pace_sec")
    ]
    baseline_pace = (
        sum(float(x["pace_sec"]) for x in cruise_laps) / len(cruise_laps)
        if cruise_laps
        else float(overall_pace_sec or 300)
    )
    baseline_gap = (
        sum(float(x.get("gap_sec") or x["pace_sec"]) for x in cruise_laps) / len(cruise_laps)
        if cruise_laps
        else baseline_pace
    )
    baseline_hrs = [float(x["avg_hr"]) for x in cruise_laps if x.get("avg_hr")]
    baseline_hr = sum(baseline_hrs) / len(baseline_hrs) if baseline_hrs else (float(avg_hr) if avg_hr else None)
    baseline_cads = [float(x["avg_cadence"]) for x in cruise_laps if x.get("avg_cadence")]
    baseline_cad = sum(baseline_cads) / len(baseline_cads) if baseline_cads else None

    fade_km: Optional[int] = None
    fade_laps: List[Dict[str, Any]] = []
    for l in km_splits:
        end_k = float(l.get("end_km") or 0)
        if end_k <= dist_km * 0.52 or not l.get("pace_sec"):
            continue
        if float(l["pace_sec"]) - baseline_pace >= 16:
            if fade_km is None:
                fade_km = int(round(end_k))
            fade_laps.append(l)

    prescriptions: List[str] = []
    if fade_laps and len(fade_laps) >= 2:
        avg_fade_raw = sum(float(x["pace_sec"]) for x in fade_laps) / len(fade_laps) - baseline_pace
        avg_fade_gap = sum(float(x.get("gap_sec") or x["pace_sec"]) for x in fade_laps) / len(fade_laps) - baseline_gap
        fade_hrs = [float(x["avg_hr"]) for x in fade_laps if x.get("avg_hr")]
        avg_fade_hr = sum(fade_hrs) / len(fade_hrs) if fade_hrs else None
        fade_cads = [float(x["avg_cadence"]) for x in fade_laps if x.get("avg_cadence")]
        avg_fade_cad = sum(fade_cads) / len(fade_cads) if fade_cads else None

        if avg_fade_gap < 8.0 and avg_fade_raw >= 15.0:
            cause_code = "terrain_hill"
            cause_title = f"⛰️ 赛道地形影响（第 {fade_km}km 起原始配速降 {int(round(avg_fade_raw))}秒/km，但等强配速 GAP 稳定）"
            prescriptions.append("后程配速波动主要来自赛道爬坡，生理输出并未崩盘，无需过度担忧耐力短板。")
            prescriptions.append("下阶段可在长距离跑末段加入 3~4 组缓坡巡航，提升坡道步频切换效率。")
        elif avg_fade_hr is not None and baseline_hr is not None and (avg_fade_hr >= max_hr * 0.88 or avg_fade_hr >= baseline_hr + 4):
            cause_code = "cardiac_drift"
            cause_title = f"🌡️ 心率漂移/过热脱水型掉速（第 {fade_km}km 起配速降 {int(round(avg_fade_raw))}秒/km，心率仍顶在 {int(round(avg_fade_hr))}bpm）"
            prescriptions.append("前中段配速略激进或途中补水电解质偏少，导致血容量下降、核心体温升高引发心率漂移。")
            prescriptions.append("下周期建议加强马拉松配速（MP）稳态长距离，比赛前 5km 严守目标配速下限，每 5km 规律补水降温。")
        else:
            cause_code = "glycogen_bonk"
            cad_note = f"，步频跌至 {int(round(avg_fade_cad))}spm" if (avg_fade_cad and baseline_cad and baseline_cad - avg_fade_cad >= 4) else ""
            hr_note = f"，心率同步回落至 {int(round(avg_fade_hr))}bpm" if avg_fade_hr else ""
            cause_title = f"🔋 糖原临界/肌耐力衰减型掉速（第 {fade_km}km 起掉速 {int(round(avg_fade_raw))}秒/km{hr_note}{cad_note}）"
            prescriptions.append("典型后程肌糖原不足或下肢离心抗疲劳见底（心率推不上去但双腿沉重）。")
            prescriptions.append("下周期需夯实周跑量与 28~32km 渐进长距离，并在赛中提前至第 7~8km 起每 35~40 分钟补充能量胶。")
    else:
        cause_code = "strong_finish"
        cause_title = "🏆 全程定速稳健 · 抗衰减能力出色（后程无明显掉速拐点）"
        prescriptions.append("本场配速纪律与能量分配非常成熟，有氧底座扎实支撑了全程输出。")
        prescriptions.append("赛后 5~7 天以完全休整与低心率排酸慢跑为主，待 HRV 与静息心率回升后再开启新周期。")

    # Check start discipline (first stage vs cruise)
    if stages and len(stages) >= 2 and stages[0].get("pace_sec") and stages[1].get("pace_sec"):
        start_diff = stages[1]["pace_sec"] - stages[0]["pace_sec"]  # positive means stage 0 was faster!
        if start_diff >= 10:
            stages[0]["status_tag"] = f"⚠️ 起跑偏快 {start_diff}秒/km"
            stages[0]["comment"] = "出发受赛事氛围带动偏快，提前消耗了部分无氧糖酵解储备。"
        elif start_diff <= -6:
            stages[0]["status_tag"] = "✅ 压速冷静"
            stages[0]["comment"] = "起跑克制稳健，为后程巡航留足糖原储备。"
        else:
            stages[0]["status_tag"] = "✅ 定速精准"
            stages[0]["comment"] = "起跑即精准切入巡航节奏。"

    for st in stages[1:]:
        if st.get("pace_sec") and baseline_pace:
            diff = int(round(st["pace_sec"] - baseline_pace))
            if diff <= -5:
                st["status_tag"] = f"🔥 提速 {-diff}秒/km"
                st["comment"] = f"配速 {st['pace_str']}，后程发力果断。"
            elif diff <= 10:
                st["status_tag"] = "✅ 稳态锁定"
                st["comment"] = f"配速稳守 {st['pace_str']}" + (f"，稳态心率 {st['steady_hr']}bpm。" if st.get("steady_hr") else "。")
            else:
                st["status_tag"] = f"⚠️ 掉速 +{diff}秒/km"
                st["comment"] = f"进入疲劳考验区，配速回落至 {st['pace_str']}。"

    goal_verdict = ""
    if target_sec and mov_s > 0:
        delta_goal = mov_s - target_sec
        if delta_goal <= 0:
            goal_verdict = f"🎯 达成预设目标（实跑 {fmt_duration_hms(mov_s)} vs 目标 {target_time_str}，快 {fmt_duration_hms(abs(delta_goal))}）"
        else:
            goal_verdict = f"⏱️ 完赛用时 {fmt_duration_hms(mov_s)}（预设目标 {target_time_str}，差 {fmt_duration_hms(delta_goal)}）"
    else:
        goal_verdict = f"⏱️ 完赛净用时 {fmt_duration_hms(mov_s)}（均速 {fmt_pace_sec(overall_pace_sec)}）"

    split_short = half_split_info["split_label"] if half_split_info else ""
    concise_critique = (
        f"🏆【赛事复盘 · 《{race_name}》】{goal_verdict}。"
        f"{split_short + '，' if split_short else ''}"
        f"{cause_title}。💡 {prescriptions[0]}"
    )

    return {
        "race_name": race_name,
        "race_type": race_type,
        "target_time": target_time_str or None,
        "actual_time": fmt_duration_hms(mov_s),
        "goal_verdict": goal_verdict,
        "half_split": half_split_info,
        "fade_inflection_km": fade_km,
        "cause_code": cause_code,
        "cause_title": cause_title,
        "prescriptions": prescriptions,
        "stages": stages,
        "concise_critique": concise_critique,
    }


def analyze_activity_segments(
    activity: Dict[str, Any],
    track_data: Optional[Dict[str, Any]] = None,
    planned_day: Optional[Dict[str, Any]] = None,
    preset_race: Optional[Dict[str, Any]] = None,
    max_hr: float = 185.0,
    aerobic_ceiling: float = 152.0,
    threshold_ceiling: float = 168.0,
) -> Dict[str, Any]:
    """
    Master entry point for segmenting an opened/synced running activity and generating:
    - 'race' diagnosis (strictly when preset_race is present)
    - 'planned_workout' phase-by-phase comparison (when planned_day is present)
    - 'free_workout' structured segment critique (otherwise)
    """
    dist_km = round(float(activity.get("distance_meters") or 0.0) / 1000.0, 2)
    mov_s = int(activity.get("moving_time_seconds") or activity.get("elapsed_time_seconds") or 0)
    overall_pace_sec = (
        int(round(mov_s / dist_km))
        if (dist_km > 0.1 and mov_s > 0)
        else (parse_pace_str_to_sec(activity.get("avg_pace_str")) or 330)
    )
    overall_pace_str = fmt_pace_sec(overall_pace_sec)
    is_track = _detect_track_loop(track_data, dist_km)

    primary_laps, km_splits, telemetry = _extract_normalized_splits(activity, track_data)

    # ── MODE 1: Preset Race Diagnosis (strictly for user's preset races) ──
    if preset_race:
        race_diag = _build_race_diagnosis(activity, preset_race, km_splits or primary_laps, telemetry, max_hr)
        return {
            "mode": "race",
            "mode_label": "🏆 预设比赛分阶段复盘",
            "is_track_run": is_track,
            "has_granular_splits": len(km_splits or primary_laps) >= 2,
            "summary_title": f"《{race_diag['race_name']}》赛程诊断",
            "summary_verdict": race_diag["goal_verdict"],
            "coach_advice": " ".join(race_diag["prescriptions"]),
            "phases": race_diag["stages"],
            "race_diagnosis": race_diag,
            "plan_comparison": None,
            "km_splits": (km_splits or primary_laps)[:50],
            "concise_critique": race_diag["concise_critique"],
        }

    # Parse planned workout warm-up / main / cool-down hints if scheduled workout exists
    has_active_plan = bool(
        planned_day
        and str(planned_day.get("workout_type") or "easy_run") not in ("rest", "travel")
        and float(planned_day.get("distance_km") or 0.0) > 0
    )

    wu_hint_km = 0.0
    cd_hint_km = 0.0
    plan_title = ""
    plan_desc = ""
    plan_dist = 0.0
    plan_pace_text = ""
    plan_hr_text = ""
    planned_main_km = 0.0

    if has_active_plan and planned_day:
        plan_title_raw = str(planned_day.get("title") or "今日课表").strip()
        plan_title = re.sub(r"\s*[\(（].*?[\)）]", "", plan_title_raw).strip() or plan_title_raw
        plan_desc = str(planned_day.get("description") or "").strip()
        plan_dist = float(planned_day.get("distance_km") or 0.0)
        plan_pace_text = str(planned_day.get("target_pace") or "").strip()
        plan_hr_text = str(planned_day.get("target_hr_zone") or "").strip()

        combined = f"{plan_title} {plan_desc}"
        wu_m = re.search(r"热身\s*(\d+(?:\.\d+)?)\s*(?:km|k|公里)", combined, re.I)
        cd_m = re.search(r"(?:(\d+(?:\.\d+)?)\s*(?:km|k|公里)\s*冷身|冷身\s*(\d+(?:\.\d+)?)\s*(?:km|k|公里))", combined, re.I)
        wu_hint_km = float(wu_m.group(1)) if wu_m else (2.0 if "热身" in combined else 0.0)
        cd_hint_km = float(cd_m.group(1) or cd_m.group(2)) if cd_m else (1.5 if "冷身" in combined else 0.0)
        if (wu_hint_km + cd_hint_km) > 0 and plan_dist > (wu_hint_km + cd_hint_km + 1.0):
            planned_main_km = round(plan_dist - wu_hint_km - cd_hint_km, 1)
        else:
            planned_main_km = plan_dist

    is_trail = _is_trail_or_mountain_activity(activity, primary_laps)
    is_explicit_interval = _has_explicit_interval_intent(activity, planned_day)

    phases, interval_meta = segment_workout_phases(
        primary_laps,
        telemetry,
        planned_wu_km=wu_hint_km,
        planned_cd_km=cd_hint_km,
        is_trail=is_trail,
        is_explicit_interval=is_explicit_interval,
        aerobic_ceiling=aerobic_ceiling,
    )

    # Fallback single-phase when activity only has summary metrics (e.g. screenshot import without splits)
    if not phases:
        avg_hr_val = int(round(float(activity["average_heartrate"]))) if activity.get("average_heartrate") else None
        phases = [{
            "phase_type": "cruise",
            "label": "🏔️ 山地越野巡航" if is_trail else "🎯 全程汇总段",
            "start_km": 0.0,
            "end_km": dist_km,
            "range_str": f"0~{dist_km}km",
            "distance_km": dist_km,
            "duration_s": mov_s,
            "duration_str": fmt_duration_hms(mov_s),
            "pace_sec": overall_pace_sec,
            "pace_str": overall_pace_str,
            "gap_sec": overall_pace_sec,
            "gap_str": overall_pace_str,
            "avg_hr": avg_hr_val,
            "steady_hr": avg_hr_val,
            "max_hr": activity.get("max_heartrate") or avg_hr_val,
            "avg_cadence": activity.get("average_cadence"),
            "elev_gain_m": round(float(activity.get("elevation_gain_meters") or 0.0), 1),
            "elev_loss_m": 0.0,
            "decoupling_pct": None,
            "lap_count": 1,
        }]

    # Identify Main Set phases (excluding warmup & cooldown)
    main_phases = [p for p in phases if p["phase_type"] not in ("warmup", "cooldown")]
    if not main_phases:
        main_phases = phases
    wu_phase = next((p for p in phases if p["phase_type"] == "warmup"), None)
    cd_phase = next((p for p in phases if p["phase_type"] == "cooldown"), None)

    main_dist_km = round(sum(float(p.get("distance_km") or 0.0) for p in main_phases), 2)
    main_dur_s = sum(int(p.get("duration_s") or 0) for p in main_phases)
    main_pace_sec = (
        interval_meta["work_pace_sec"]
        if (interval_meta and interval_meta.get("work_pace_sec"))
        else (int(round(main_dur_s / main_dist_km)) if main_dist_km > 0.1 and main_dur_s > 0 else overall_pace_sec)
    )
    main_pace_str = fmt_pace_sec(main_pace_sec)
    main_hrs = [int(p["steady_hr"] or p["avg_hr"]) for p in main_phases if (p.get("steady_hr") or p.get("avg_hr"))]
    main_steady_hr = (
        interval_meta["work_steady_hr"]
        if (interval_meta and interval_meta.get("work_steady_hr"))
        else (int(round(sum(main_hrs) / len(main_hrs))) if main_hrs else None)
    )
    main_decoupling = next((p["decoupling_pct"] for p in main_phases if p.get("decoupling_pct") is not None), None)

    # ── MODE 2: Planned Workout Alignment & Phase Comparison ──
    # If actual pace / distance / structure (combination) has a large discrepancy from the scheduled workout,
    # skip schedule comparison and fall through to MODE 3 to directly critique the actual training effect.
    if has_active_plan and planned_day:
        has_wucd_structure_pre = bool(wu_hint_km > 0 or cd_hint_km > 0 or wu_phase or cd_phase)
        ref_target_km_pre = planned_main_km if has_wucd_structure_pre else plan_dist
        measured_km_pre = main_dist_km if has_wucd_structure_pre else dist_km

        if has_large_plan_discrepancy(
            planned_day=planned_day,
            activity=activity,
            eval_total_km=dist_km,
            eval_main_km=measured_km_pre,
            planned_main_km=ref_target_km_pre,
            eval_pace_sec=main_pace_sec,
            phases=phases,
            interval_meta=interval_meta,
            aerobic_ceiling=aerobic_ceiling,
            threshold_ceiling=threshold_ceiling,
        ):
            has_active_plan = False
            if (wu_hint_km > 0 or cd_hint_km > 0) and primary_laps:
                phases, interval_meta = segment_workout_phases(
                    primary_laps,
                    telemetry,
                    planned_wu_km=0.0,
                    planned_cd_km=0.0,
                    is_trail=is_trail,
                    is_explicit_interval=_has_explicit_interval_intent(activity, None),
                    aerobic_ceiling=aerobic_ceiling,
                )
                main_phases = [p for p in phases if p["phase_type"] not in ("warmup", "cooldown")]
                if not main_phases:
                    main_phases = phases
                wu_phase = next((p for p in phases if p["phase_type"] == "warmup"), None)
                cd_phase = next((p for p in phases if p["phase_type"] == "cooldown"), None)
                main_dist_km = round(sum(float(p.get("distance_km") or 0.0) for p in main_phases), 2)
                main_dur_s = sum(int(p.get("duration_s") or 0) for p in main_phases)
                main_pace_sec = (
                    interval_meta["work_pace_sec"]
                    if (interval_meta and interval_meta.get("work_pace_sec"))
                    else (int(round(main_dur_s / main_dist_km)) if main_dist_km > 0.1 and main_dur_s > 0 else overall_pace_sec)
                )
                main_pace_str = fmt_pace_sec(main_pace_sec)
                main_hrs = [int(p["steady_hr"] or p["avg_hr"]) for p in main_phases if (p.get("steady_hr") or p.get("avg_hr"))]
                main_steady_hr = (
                    interval_meta["work_steady_hr"]
                    if (interval_meta and interval_meta.get("work_steady_hr"))
                    else (int(round(sum(main_hrs) / len(main_hrs))) if main_hrs else None)
                )
                main_decoupling = next((p["decoupling_pct"] for p in main_phases if p.get("decoupling_pct") is not None), None)

    if has_active_plan and planned_day:
        # Extract target pace from main clause first if '+' description exists
        main_clause = ""
        if "+" in plan_desc:
            parts = [x.strip() for x in plan_desc.split("+") if x.strip()]
            non_wucd = [x for x in parts if not x.startswith("热身") and "冷身" not in x[:6]]
            if non_wucd:
                main_clause = non_wucd[0].split("。")[0].strip()
        target_p_range = parse_pace_range_to_sec(main_clause) or parse_pace_range_to_sec(plan_pace_text) or parse_pace_range_to_sec(plan_desc)
        target_hr_rng = parse_hr_range(plan_hr_text, max_hr=max_hr)

        # Annotate each phase against plan
        if wu_phase:
            if target_p_range and wu_phase.get("pace_sec") and wu_phase["pace_sec"] < target_p_range[1] + 10:
                wu_phase["status_tag"] = "⚠️ 热身略快"
                wu_phase["comment"] = f"热身 {wu_phase['distance_km']}km 配速 {wu_phase['pace_str']} 偏快，建议前 2km 更从容激活。"
            else:
                wu_phase["status_tag"] = "✅ 循序激活"
                wu_phase["comment"] = f"热身 {wu_phase['distance_km']}km（{wu_phase['pace_str']}），心率平稳爬升。"

        if cd_phase:
            cd_phase["status_tag"] = "✅ 排酸到位"
            cd_phase["comment"] = f"冷身 {cd_phase['distance_km']}km（{cd_phase['pace_str']}），促进乳酸代谢回落。"

        # Main set compliance evaluation
        has_wucd_structure = bool(wu_hint_km > 0 or cd_hint_km > 0 or wu_phase or cd_phase)
        ref_target_km = planned_main_km if has_wucd_structure else plan_dist
        measured_km = main_dist_km if has_wucd_structure else dist_km
        dist_pct = int(round((measured_km / max(0.5, ref_target_km)) * 100))

        pace_status = "✅ 配速达标"
        if target_p_range and main_pace_sec:
            lo_p, hi_p = target_p_range
            tol = 8
            if lo_p - tol <= main_pace_sec <= hi_p + tol:
                pace_status = "✅ 主课配速精准"
            elif main_pace_sec < lo_p - tol:
                pace_status = f"⚠️ 主课偏快 {lo_p - main_pace_sec}秒/km"
            else:
                pace_status = f"⚠️ 主课偏慢 {main_pace_sec - hi_p}秒/km"

        hr_status = ""
        if main_steady_hr and target_hr_rng:
            lo_h, hi_h = target_hr_rng
            if lo_h - 3 <= main_steady_hr <= hi_h + 4:
                hr_status = f"稳态心率 {main_steady_hr}bpm 命中目标区"
            elif main_steady_hr > hi_h + 4:
                hr_status = f"稳态心率 {main_steady_hr}bpm 超上限 {main_steady_hr - hi_h}bpm"
            else:
                hr_status = f"稳态心率 {main_steady_hr}bpm 低于目标下限（游刃有余）"
        elif main_steady_hr:
            hr_status = f"主课稳态心率 {main_steady_hr}bpm"

        for mp in main_phases:
            mp["status_tag"] = pace_status
            if interval_meta and mp["phase_type"] == "intervals":
                reps_txt = " / ".join(interval_meta["rep_paces"][:6])
                mp["comment"] = (
                    f"快跑组均速 {interval_meta['work_pace_str']}（各组：{reps_txt}）"
                    + (f"，组间心率回落 {interval_meta['hr_recovery_drop']}bpm。" if interval_meta.get("hr_recovery_drop") else "。")
                )
            else:
                dec_txt = f"，心率解耦率 {mp['decoupling_pct']}%" if mp.get("decoupling_pct") is not None else ""
                mp["comment"] = f"实跑 {mp['distance_km']}km @ {mp['pace_str']}" + (f"（{hr_status}{dec_txt}）。" if hr_status else "。")

        target_pace_disp = (
            f"{fmt_pace_sec(target_p_range[0], False)}~{fmt_pace_sec(target_p_range[1])}"
            if (target_p_range and target_p_range[0] != target_p_range[1])
            else (fmt_pace_sec(target_p_range[0]) if target_p_range else (plan_pace_text or "按体感"))
        )

        plan_comp = {
            "plan_title": plan_title,
            "has_wucd_structure": has_wucd_structure,
            "planned_total_km": plan_dist,
            "actual_total_km": dist_km,
            "planned_main_km": ref_target_km,
            "actual_main_km": measured_km,
            "compliance_pct": dist_pct,
            "target_pace_str": target_pace_disp,
            "actual_main_pace_str": main_pace_str,
            "pace_verdict": pace_status,
            "target_hr_str": plan_hr_text or None,
            "actual_main_steady_hr": main_steady_hr,
            "hr_verdict": hr_status or None,
            "aerobic_decoupling_pct": main_decoupling,
            "warmup_missing": bool(wu_hint_km >= 1.0 and not wu_phase and len(primary_laps) >= 3),
            "cooldown_missing": bool(cd_hint_km >= 1.0 and not cd_phase and len(primary_laps) >= 3),
        }

        advice_parts = []
        if plan_comp["warmup_missing"]:
            advice_parts.append("本堂课起跑直接切入高配速，下次强度课建议保留 1.5~2km 慢跑热身防拉伤。")
        if main_decoupling is not None and main_decoupling > 5.5:
            advice_parts.append(f"主课后半段心率解耦率 {main_decoupling}%（>5%），注意途中补水与耐力底座巩固。")
        elif interval_meta and interval_meta.get("fade_sec", 0) >= 10:
            advice_parts.append(f"末组较首组掉速 {interval_meta['fade_sec']}秒/km，前两组可再压 2~3 秒留出后程余量。")
        else:
            advice_parts.append("主课分段配速与生理负荷控制理想，课后做好拉伸与碳水补充。")

        verdict_line = (
            f"主课达成率 {dist_pct}%（实跑 {measured_km}km / 目标 {ref_target_km}km），"
            f"主课配速 {main_pace_str}（目标 {target_pace_disp} · {pace_status.replace('✅ ', '').replace('⚠️ ', '')}）"
            + (f"，{hr_status}" if hr_status else "")
        )
        venue_tag = "🏟️ 田径场 · " if is_track else ""
        concise_critique = f"📋【{venue_tag}课表分段比对 · 《{plan_title}》】{verdict_line}。💡 {advice_parts[0]}"

        return {
            "mode": "planned_workout",
            "schema_version": 3,
            "mode_label": "📋 课表分段达成比对",
            "is_track_run": is_track,
            "has_granular_splits": len(primary_laps) >= 2,
            "summary_title": f"对比课表《{plan_title}》",
            "summary_verdict": verdict_line,
            "coach_advice": " ".join(advice_parts),
            "phases": phases,
            "plan_comparison": plan_comp,
            "race_diagnosis": None,
            "km_splits": (km_splits or primary_laps)[:50],
            "concise_critique": concise_critique,
        }

    # ── MODE 3: Free / Unplanned Workout Multi-Segment Critique ──
    act_name_str = str(activity.get("name") or "")
    elev_gain_act = float(activity.get("elevation_gain_meters") or activity.get("total_elevation_gain") or 0.0)
    act_reps_n, act_rep_km_n = _extract_planned_interval_spec(act_name_str)
    is_name_interval = bool(
        not is_trail
        and (
            (act_reps_n >= 2 and act_rep_km_n >= 0.15)
            or re.search(
                r"(\d+\s*(?:m|米|km|k)\s*\+\s*\d+\s*(?:m|米|km|k)|\b(?:1st|2nd|3rd|\d+th)\b|间歇|变速|法特莱克)",
                act_name_str,
                re.I,
            )
        )
    )
    if is_trail:
        archetype = "山地专项耐力跑" if (elev_gain_act >= 500 or dist_km >= 20) else "山地有氧爬坡跑"
    elif interval_meta:
        archetype = f"变速/间歇训练（{interval_meta['rep_count']}组快跑）"
    elif is_name_interval:
        archetype = "变速/间歇专项训练"
    elif any(p["phase_type"] == "progression" for p in phases):
        archetype = "渐进加速跑"
    elif any(p["phase_type"] == "fade" for p in phases):
        archetype = "前快后慢有氧跑"
    elif wu_phase and cd_phase:
        archetype = "三段式结构化巡航跑"
    elif dist_km >= 18.0:
        archetype = "长距离有氧耐力跑（LSD）"
    elif (main_steady_hr and main_steady_hr >= threshold_ceiling) or any(
        k in act_name_str for k in ("节奏", "门槛", "乳酸", "速耐")
    ):
        archetype = "混氧/乳酸门槛节奏跑"
    elif dist_km < 5.0 and "热身" in act_name_str:
        archetype = "热身激活跑"
    elif dist_km < 5.0 and "冷身" in act_name_str:
        archetype = "冷身排酸跑"
    else:
        archetype = "稳态有氧基础跑"

    for p in phases:
        ptype = p["phase_type"]
        if is_trail:
            eff_elev = int(round(elev_gain_act or p.get("elev_gain_m") or 0))
            elev_note = f"（累计爬升 +{eff_elev}m）" if eff_elev > 0 else ""
            hr_note = f"，心率 {p['steady_hr']}bpm" if p.get("steady_hr") else ""
            p["status_tag"] = "🏔️ 爬升徒步与越野巡航"
            p["comment"] = f"全程 {p['distance_km']}km{elev_note}，均速 {p['pace_str']}{hr_note}，爬升段结合徒步稳控心率，平缓及下坡段稳健跑动。"
        elif ptype == "warmup":
            p["status_tag"] = "✅ 渐进激活"
            p["comment"] = f"前段 {p['distance_km']}km 按 {p['pace_str']} 柔和起步，心率热身充分。"
        elif ptype == "cooldown":
            p["status_tag"] = "✅ 主动排酸"
            p["comment"] = f"尾段 {p['distance_km']}km 降速至 {p['pace_str']} 放松收尾，加速恢复。"
        elif ptype == "intervals" and interval_meta:
            p["status_tag"] = f"⚡ {interval_meta['rep_count']}组高质量刺激"
            reps_txt = " / ".join(interval_meta["rep_paces"][:6])
            p["comment"] = f"快跑均速 {interval_meta['work_pace_str']}（{reps_txt}），有效刺激最大摄氧量与步频神经募集。"
        elif ptype == "progression":
            p["status_tag"] = "🚀 后程提速"
            p["comment"] = f"后段提速至 {p['pace_str']}" + (f"（稳态心率 {p['steady_hr']}bpm），抗疲劳收尾极佳。" if p.get("steady_hr") else "，余力充沛。")
        elif ptype == "fade":
            p["status_tag"] = "⚠️ 后程掉速"
            p["comment"] = f"后段配速回落至 {p['pace_str']}，提示前段配速偏急或途中需注意补水。"
        else:
            if p.get("steady_hr") and p["steady_hr"] <= aerobic_ceiling + 2:
                p["status_tag"] = "✅ 有氧稳态"
                p["comment"] = f"核心段 {p['distance_km']}km 稳定在 {p['pace_str']}（心率 {p['steady_hr']}bpm），有氧经济性扎实。"
            elif p.get("steady_hr") and p["steady_hr"] >= threshold_ceiling:
                p["status_tag"] = "🔥 门槛高强"
                p["comment"] = f"核心段 {p['distance_km']}km @ {p['pace_str']}（心率 {p['steady_hr']}bpm），高质量推高乳酸阈值。"
            else:
                p["status_tag"] = "✅ 节奏稳健"
                p["comment"] = f"核心段 {p['distance_km']}km 巡航配速 {p['pace_str']}，步频与输出平稳。"

    phase_briefs = [f"{p['label'].split(' ', 1)[-1]} {p['distance_km']}k({p['pace_str'].replace('/km', '')})" for p in phases]
    structure_line = " → ".join(phase_briefs)
    if is_trail:
        advice_free = "越野跑中遇爬升路段主动切换徒步（Power Hiking）节能、下坡注意小步高频缓震，课后做好股四头肌与小腿放松。"
    elif main_decoupling is not None:
        if main_decoupling <= 4.5:
            advice_free = f"核心段心率解耦率仅 {main_decoupling}%（<5% 优秀），有氧耐力非常稳固。"
        else:
            advice_free = f"核心段后半程心率解耦率 {main_decoupling}%，长距离后半程可留意补水与控速。"
    elif any(p["phase_type"] == "fade" for p in phases):
        advice_free = "下次起跑前 2km 可主动压慢 15秒/km，把体力留给后半程实现负劈。"
    else:
        advice_free = "分段节奏清晰，跑后做好小腿与臀中肌放松拉伸。"

    venue_tag = "🏟️ 田径场 · " if (is_track and not is_trail) else ""
    concise_critique = f"⚡【{venue_tag}{archetype}】分段表现：{structure_line}。💡 {advice_free}"

    return {
        "mode": "free_workout",
        "schema_version": 3,
        "mode_label": "⚡ 智能训练分段复盘",
        "is_track_run": bool(is_track and not is_trail),
        "has_granular_splits": len(primary_laps) >= 2,
        "summary_title": f"{venue_tag}{archetype}",
        "summary_verdict": structure_line,
        "coach_advice": advice_free,
        "phases": phases,
        "plan_comparison": None,
        "race_diagnosis": None,
        "km_splits": (km_splits or primary_laps)[:50],
        "concise_critique": concise_critique,
    }
