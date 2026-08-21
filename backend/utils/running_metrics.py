"""
Running Science & Performance Metrics Calculations:
- TRIMP (Training Impulse - Banister model)
- CTL / ATL / TSB (Fitness, Fatigue, Form)
- VDOT & Race Predictions (Jack Daniels Formula)
- Renato Canova Training Pace Zones
"""

import math
from typing import Dict, List, Optional, Tuple, Any

def calculate_trimp(
    duration_minutes: float,
    avg_hr: float,
    rest_hr: float = 60,
    max_hr: float = 190,
    gender: str = "male"
) -> float:
    """Calculates Banister's TRIMP (Training Impulse)."""
    if duration_minutes <= 0 or avg_hr <= rest_hr or max_hr <= rest_hr:
        return 0.0

    hr_reserve = (avg_hr - rest_hr) / (max_hr - rest_hr)
    hr_reserve = max(0.0, min(1.0, hr_reserve))

    # Factor b: 1.92 for males, 1.67 for females
    b = 1.67 if str(gender).lower() == "female" else 1.92
    trimp = duration_minutes * hr_reserve * 0.64 * math.exp(b * hr_reserve)
    return round(trimp, 1)

def calculate_vdot(distance_meters: float, time_seconds: float) -> float:
    """Calculates Jack Daniels VDOT score from a race or workout effort."""
    if distance_meters <= 0 or time_seconds <= 0:
        return 0.0

    t_min = time_seconds / 60.0
    v = distance_meters / t_min  # meters per minute

    # Oxygen cost formula
    vo2 = -4.60 + 0.182258 * v + 0.000104 * (v ** 2)
    # Fraction of VO2max at race duration
    p = 0.8 + 0.1894393 * math.exp(-0.012778 * t_min) + 0.2989558 * math.exp(-0.1932605 * t_min)

    vdot = vo2 / p
    return round(vdot, 1)

def vdot_to_race_time(vdot: float, distance_meters: float) -> int:
    """Estimates race time in seconds for a given distance and VDOT."""
    if vdot <= 0 or distance_meters <= 0:
        return 0

    # Binary search for time in seconds that yields target VDOT
    low_s = 60
    high_s = 24 * 3600

    for _ in range(50):
        mid_s = (low_s + high_s) / 2.0
        calc = calculate_vdot(distance_meters, mid_s)
        if calc < vdot:
            high_s = mid_s
        else:
            low_s = mid_s

    return int(round((low_s + high_s) / 2.0))

def compute_ctl_atl_tsb(
    daily_trimp_series: List[Tuple[str, float]],
    ctl_decay_days: int = 42,
    atl_decay_days: int = 7
) -> List[Dict[str, Any]]:
    """
    Computes CTL (Fitness), ATL (Fatigue), and TSB (Form = CTL - ATL).
    daily_trimp_series: sorted list of (date_str, trimp_value)
    """
    if not daily_trimp_series:
        return []

    ctl_k = 2.0 / (ctl_decay_days + 1)
    atl_k = 2.0 / (atl_decay_days + 1)

    ctl = 0.0
    atl = 0.0
    results = []

    for date_str, trimp in daily_trimp_series:
        ctl = ctl + ctl_k * (trimp - ctl)
        atl = atl + atl_k * (trimp - atl)
        tsb = ctl - atl

        results.append({
            "date": date_str,
            "trimp": round(trimp, 1),
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(tsb, 1),
        })

    return results

def get_canova_zones(marathon_pb_seconds: int) -> Dict[str, Dict[str, Any]]:
    """
    Calculates Renato Canova Training Pace Zones based on Marathon Pace (MP).
    Zones:
    - Fundamental (90-95% MP)
    - Special (95-100% MP)
    - Specific (100-105% MP)
    - Max Specific (105-110% MP)
    - Recovery (>110% MP)
    """
    if not marathon_pb_seconds or marathon_pb_seconds <= 0:
        marathon_pb_seconds = 10800 # 3:00:00 default

    mp_sec_per_km = marathon_pb_seconds / 42.195

    def fmt_pace(sec_km: float) -> str:
        m = int(sec_km // 60)
        s = int(round(sec_km % 60))
        return f"{m}:{s:02d}"

    return {
        "recovery": {
            "name": "恢复跑 / 基础慢跑 (Recovery/Easy)",
            "range": f"{fmt_pace(mp_sec_per_km / 0.80)} - {fmt_pace(mp_sec_per_km / 0.88)} /km",
            "desc": "毛细血管增生与有氧基础构建"
        },
        "fundamental": {
            "name": "基础有氧耐力 (Fundamental Endurance)",
            "range": f"{fmt_pace(mp_sec_per_km / 0.90)} - {fmt_pace(mp_sec_per_km / 0.95)} /km",
            "desc": "马拉松配速的 90%~95%，持续有氧长跑 (LSD/Progression)"
        },
        "special": {
            "name": "专项准备能力 (Special Endurance)",
            "range": f"{fmt_pace(mp_sec_per_km / 0.95)} - {fmt_pace(mp_sec_per_km / 1.00)} /km",
            "desc": "马拉松配速的 95%~100%，乳酸阈值与专项耐力结合"
        },
        "specific": {
            "name": "马拉松专项速度 (Marathon Specific)",
            "range": f"{fmt_pace(mp_sec_per_km / 1.00)} - {fmt_pace(mp_sec_per_km / 1.05)} /km",
            "desc": "目标全马配速 100%~105%，比赛核心专项刺激"
        },
        "max_specific": {
            "name": "最大专项速度 (Maximum Specific)",
            "range": f"{fmt_pace(mp_sec_per_km / 1.05)} - {fmt_pace(mp_sec_per_km / 1.12)} /km",
            "desc": "半马/10K 配速间歇，提升 VO2max 与速度储备"
        }
    }
