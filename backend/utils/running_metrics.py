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

def estimate_vo2max(
    pb_5k_seconds: Optional[int] = None,
    pb_10k_seconds: Optional[int] = None,
    pb_half_seconds: Optional[int] = None,
    pb_marathon_seconds: Optional[int] = None,
    max_hr: Optional[int] = None,
    rest_hr: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Estimates VO2Max using Jack Daniels VDOT formula (from best race performances)
    and Heart Rate Ratio method (Uth-Sørensen formula).
    Returns recommended VO2Max and the estimation breakdown.
    """
    candidates = []

    # 1. 5K VDOT
    if pb_5k_seconds and 600 <= pb_5k_seconds <= 3600:
        v = calculate_vdot(5000.0, float(pb_5k_seconds))
        if v > 0:
            candidates.append({"source": "5公里 PB", "method": "Jack Daniels VDOT", "value": v})

    # 2. 10K VDOT
    if pb_10k_seconds and 1200 <= pb_10k_seconds <= 7200:
        v = calculate_vdot(10000.0, float(pb_10k_seconds))
        if v > 0:
            candidates.append({"source": "10公里 PB", "method": "Jack Daniels VDOT", "value": v})

    # 3. Half Marathon VDOT
    if pb_half_seconds and 3000 <= pb_half_seconds <= 15000:
        v = calculate_vdot(21097.5, float(pb_half_seconds))
        if v > 0:
            candidates.append({"source": "半程马拉松 PB", "method": "Jack Daniels VDOT", "value": v})

    # 4. Marathon VDOT
    if pb_marathon_seconds and 7200 <= pb_marathon_seconds <= 30000:
        v = calculate_vdot(42195.0, float(pb_marathon_seconds))
        if v > 0:
            candidates.append({"source": "全程马拉松 PB", "method": "Jack Daniels VDOT", "value": v})

    # 5. Heart Rate Ratio: VO2Max ≈ 15.3 * (HRmax / HRrest)
    if max_hr and rest_hr and max_hr > rest_hr and rest_hr >= 35 and max_hr >= 140:
        hr_vo2 = round(15.3 * (float(max_hr) / float(rest_hr)), 1)
        if 25.0 <= hr_vo2 <= 85.0:
            candidates.append({"source": f"心率比值 ({max_hr}/{rest_hr} bpm)", "method": "Uth-Sørensen 心率公式", "value": hr_vo2})

    if not candidates:
        return {
            "estimated_vo2max": None,
            "primary_source": None,
            "candidates": [],
            "message": "缺少有效的 PB 成绩或心率数据，无法推算"
        }

    # Best estimate: prioritize VDOT from race performances
    vdot_candidates = [c for c in candidates if "VDOT" in c["method"]]
    if vdot_candidates:
        best = max(vdot_candidates, key=lambda x: x["value"])
        primary = best
    else:
        primary = candidates[0]

    return {
        "estimated_vo2max": primary["value"],
        "primary_source": primary["source"],
        "method": primary["method"],
        "candidates": candidates,
        "message": f"基于【{primary['source']}】通过 {primary['method']} 成功推算出 VO2Max 为 {primary['value']}"
    }

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

def format_duration(seconds: Optional[Any]) -> str:
    """Formats seconds into HH:MM:SS or MM:SS."""
    if not seconds:
        return "—"
    if isinstance(seconds, str):
        s_clean = seconds.strip()
        if ":" in s_clean:
            return s_clean
        try:
            seconds = int(float(s_clean))
        except Exception:
            return s_clean or "—"
    try:
        seconds = int(seconds)
    except Exception:
        return "—"
    if seconds <= 0:
        return "—"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def get_age_from_dob(dob_str: Optional[str]) -> Optional[int]:
    """Calculates age in years from YYYY-MM-DD string."""
    if not dob_str:
        return None
    try:
        from datetime import date, datetime
        dob = datetime.strptime(str(dob_str)[:10], "%Y-%m-%d").date()
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return max(0, age)
    except Exception:
        return None

def get_canova_zones(marathon_pb_seconds: int) -> Dict[str, Dict[str, Any]]:
    """
    Calculates Renato Canova Training Pace Zones based on Marathon Pace (MP).
    """
    return get_race_specific_zones(
        race_type="marathon",
        target_time_seconds=marathon_pb_seconds,
        pb_seconds=marathon_pb_seconds
    )

def get_race_specific_zones(
    race_type: str,
    target_time_seconds: Optional[int] = None,
    pb_seconds: Optional[int] = None,
    max_hr: int = 190,
    rest_hr: int = 56
) -> Dict[str, Dict[str, Any]]:
    """
    Calculates Renato Canova Specificity Training Zones adapted for:
    - marathon: Full Marathon (100% MP specificity)
    - half: Half Marathon (LT2 threshold specificity)
    - 10k: 10K Road/Track (VO2max & Specific Speed Endurance)
    - 5k: 5K Road/Track (Maximal Aerobic Power & Lactate Capacity)
    - trail: Trail Running / Ultra (Elevation D+, Eccentric Loading, %HRR zones)
    """
    r_type = (race_type or "marathon").lower()
    if "trail" in r_type or "越野" in r_type or "ultra" in r_type or "50k" in r_type or "100k" in r_type:
        hrr = max(20, max_hr - rest_hr)
        def calc_hr(pct: float) -> int:
            return int(round(rest_hr + hrr * pct))

        return {
            "recovery": {
                "name": "极低强度主动恢复 (Active Recovery / Flat Easy)",
                "range": f"心率 < {calc_hr(0.60)} bpm (或 < 68% Max HR)",
                "desc": "平路极低强度慢跑或快走，促进下肢微循环，排除下肢组织水肿与酸痛"
            },
            "fundamental": {
                "name": "山地持续有氧爬升 (Mountain Aerobic / Power Hiking)",
                "range": f"心率 {calc_hr(0.60)} - {calc_hr(0.72)} bpm",
                "desc": "下肢慢肌纤维耐力构建，结合手杖与前脚掌发力的山地快步走 (Power Hiking)"
            },
            "special": {
                "name": "混氧门槛爬升推进 (Threshold Climbing / Continuous D+)",
                "range": f"心率 {calc_hr(0.72)} - {calc_hr(0.82)} bpm",
                "desc": "长上坡连续输出能力，逼近乳酸门槛，训练肌糖原节约与乳酸清除速率"
            },
            "specific": {
                "name": "越野比赛专项节奏与技术下坡 (Trail Specific Pace & Tech Downhill)",
                "range": f"心率 {calc_hr(0.75)} - {calc_hr(0.85)} bpm",
                "desc": "模拟实战节奏，强化大腿股四头肌离心收缩耐受力与技术下坡敏捷性"
            },
            "max_specific": {
                "name": "陡坡短间歇刺激 (Hill Repeats / VO2max Surge)",
                "range": f"心率 > {calc_hr(0.88)} bpm",
                "desc": "15%~25% 陡坡 1~2 分钟全力重复冲刺，提升下肢神经肌肉募集与最大摄氧量"
            }
        }

    # Distance-based pacing calculation
    dist_km = 42.195
    if "half" in r_type or "半" in r_type:
        dist_km = 21.0975
    elif "10" in r_type:
        dist_km = 10.0
    elif "5" in r_type:
        dist_km = 5.0

    base_seconds = target_time_seconds or pb_seconds
    if not base_seconds or base_seconds <= 0:
        if dist_km == 42.195:
            base_seconds = 11370 # 3:09:30
        elif dist_km == 21.0975:
            base_seconds = 5457  # 1:30:57
        elif dist_km == 10.0:
            base_seconds = 2426  # 40:26
        else:
            base_seconds = 1164  # 19:24

    # Sanity protection against mismatched distance vs target time:
    # 1. If user passed a Full Marathon time (>= 2h30m / 9000s) with Half Marathon distance:
    #    e.g. 3:09:30 (11370s) for half marathon yields 8:59/km (walking speed), but 4:29/km for full marathon!
    if dist_km == 21.0975 and base_seconds and base_seconds >= 9000:
        half_pace = base_seconds / 21.0975
        full_pace = base_seconds / 42.195
        if half_pace > 420 and 200 <= full_pace <= 450:
            dist_km = 42.195
            r_type = "marathon"

    # 2. If user passed a Half Marathon time (<= 2h10m / 7800s) with Full Marathon distance:
    #    e.g. 1:30:00 (5400s) for full marathon yields 2:07/km (impossible), but 4:16/km for half marathon!
    elif dist_km == 42.195 and base_seconds and base_seconds <= 7800:
        full_pace = base_seconds / 42.195
        half_pace = base_seconds / 21.0975
        if full_pace < 185 and 200 <= half_pace <= 450:
            dist_km = 21.0975
            r_type = "half"

    rp_sec_per_km = base_seconds / dist_km

    def fmt_pace(sec_km: float) -> str:
        m = int(sec_km // 60)
        s = int(round(sec_km % 60))
        return f"{m}:{s:02d}"

    if "half" in r_type or "半" in r_type:
        return {
            "recovery": {
                "name": "恢复跑 / 低心率慢跑 (Recovery)",
                "range": f"{fmt_pace(rp_sec_per_km / 0.78)} - {fmt_pace(rp_sec_per_km / 0.85)} /km",
                "desc": "毛细血管微循环激活与代谢废物排酸"
            },
            "fundamental": {
                "name": "基础有氧耐力 (Fundamental Endurance)",
                "range": f"{fmt_pace(rp_sec_per_km / 0.85)} - {fmt_pace(rp_sec_per_km / 0.92)} /km",
                "desc": "半马配速 85%~92%，大容量有氧长跑 (LSD/基础积累)"
            },
            "special": {
                "name": "专项准备推进 (Special Aerobic Endurance)",
                "range": f"{fmt_pace(rp_sec_per_km / 0.92)} - {fmt_pace(rp_sec_per_km / 0.98)} /km",
                "desc": "接近全马比赛配速，乳酸稳态积累与能量节约"
            },
            "specific": {
                "name": "半马比赛专项乳酸门槛 (Half Marathon Specific LT2)",
                "range": f"{fmt_pace(rp_sec_per_km / 0.98)} - {fmt_pace(rp_sec_per_km / 1.02)} /km",
                "desc": "目标半马配速 98%~102%，核心专项耐力与门槛巡航"
            },
            "max_specific": {
                "name": "专项速度储备 (Specific Speed Reserve)",
                "range": f"{fmt_pace(rp_sec_per_km / 1.04)} - {fmt_pace(rp_sec_per_km / 1.10)} /km",
                "desc": "10K/5K 配速间歇，推高 VO2max 与神经肌肉效率"
            }
        }
    elif "10" in r_type or "5" in r_type:
        dist_name = "10K" if "10" in r_type else "5K"
        return {
            "recovery": {
                "name": "恢复跑 / 基础慢跑 (Recovery)",
                "range": f"{fmt_pace(rp_sec_per_km / 0.72)} - {fmt_pace(rp_sec_per_km / 0.80)} /km",
                "desc": "极低强度轻松慢跑，恢复中枢神经系统"
            },
            "fundamental": {
                "name": "基础有氧基线 (General Aerobic Base)",
                "range": f"{fmt_pace(rp_sec_per_km / 0.80)} - {fmt_pace(rp_sec_per_km / 0.88)} /km",
                "desc": "有氧支撑与基础里程构建"
            },
            "special": {
                "name": "乳酸阈值门槛跑 (Lactate Threshold Tempo)",
                "range": f"{fmt_pace(rp_sec_per_km / 0.88)} - {fmt_pace(rp_sec_per_km / 0.95)} /km",
                "desc": "半马配速稳态跑，拉高无氧阈值平台"
            },
            "specific": {
                "name": f"{dist_name} 比赛专项配速 (Race Specific Pace)",
                "range": f"{fmt_pace(rp_sec_per_km / 0.98)} - {fmt_pace(rp_sec_per_km / 1.02)} /km",
                "desc": f"100% {dist_name} 目标比赛配速间歇 (如 5×2000m 或 6×1000m)"
            },
            "max_specific": {
                "name": "速度与乳酸耐受突破 (Lactic Power / Speed Surge)",
                "range": f"{fmt_pace(rp_sec_per_km / 1.05)} - {fmt_pace(rp_sec_per_km / 1.15)} /km",
                "desc": "短间歇冲刺 (400m/800m)，强化快肌纤维募集与冲刺能力"
            }
        }

    # Default: Full Marathon
    return {
        "recovery": {
            "name": "恢复跑 / 基础慢跑 (Recovery/Easy)",
            "range": f"{fmt_pace(rp_sec_per_km / 0.80)} - {fmt_pace(rp_sec_per_km / 0.88)} /km",
            "desc": "毛细血管增生与有氧基础构建"
        },
        "fundamental": {
            "name": "基础有氧耐力 (Fundamental Endurance)",
            "range": f"{fmt_pace(rp_sec_per_km / 0.90)} - {fmt_pace(rp_sec_per_km / 0.95)} /km",
            "desc": "马拉松配速的 90%~95%，持续有氧长跑 (LSD/Progression)"
        },
        "special": {
            "name": "专项准备能力 (Special Endurance)",
            "range": f"{fmt_pace(rp_sec_per_km / 0.95)} - {fmt_pace(rp_sec_per_km / 1.00)} /km",
            "desc": "马拉松配速的 95%~100%，乳酸阈值与专项耐力结合"
        },
        "specific": {
            "name": "马拉松专项速度 (Marathon Specific)",
            "range": f"{fmt_pace(rp_sec_per_km / 1.00)} - {fmt_pace(rp_sec_per_km / 1.05)} /km",
            "desc": "目标全马配速 100%~105%，比赛核心专项刺激"
        },
        "max_specific": {
            "name": "最大专项速度 (Maximum Specific)",
            "range": f"{fmt_pace(rp_sec_per_km / 1.05)} - {fmt_pace(rp_sec_per_km / 1.12)} /km",
            "desc": "半马/10K 配速间歇，提升 VO2max 与速度储备"
        }
    }

def analyze_multi_race_calendar(races: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyzes athlete's multiple race calendar according to Renato Canova's periodization principles:
    - Filters and sorts upcoming races
    - Classifies/validates A/B/C race tiers:
        * A 标 (Goal Race): Primary breakthrough target, peaked taper.
        * B 标 (Tune-up / Test Race): 3-6 weeks before A race, lactate threshold validation without full taper.
        * C 标 (Training Run): Long aerobic run (LSD) replacement, controlled effort.
    - Calculates inter-race day gaps
    - Detects schedule conflicts (< 21 days between marathons/ultras) and issues warnings
    - Identifies golden preparation pairings (e.g. Half Marathon 4-6 weeks before Full Marathon)
    - Detects cross-discipline challenges (e.g. Road Marathon vs Mountain Trail)
    """
    from datetime import date, datetime
    today = date.today()
    upcoming = []
    completed = []

    for r in (races or []):
        r_dict = dict(r)
        is_completed = (r_dict.get("status") == "completed" or bool(r_dict.get("finish_time")))
        if is_completed:
            completed.append(r_dict)
            continue

        date_str = str(r_dict.get("race_date") or "")[:10]
        try:
            r_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            days_left = (r_date - today).days
            if days_left >= 0:
                r_dict["parsed_date"] = r_date
                r_dict["days_left"] = days_left
                r_dict["days_until"] = days_left
                r_dict["race_date_clean"] = date_str
                upcoming.append(r_dict)
            else:
                # Past uncompleted race
                r_dict["days_left"] = 0
                r_dict["race_date_clean"] = date_str
                completed.append(r_dict)
        except Exception:
            continue

    upcoming.sort(key=lambda x: x["parsed_date"])

    if not upcoming:
        return {
            "total_upcoming": 0,
            "total_completed": len(completed),
            "races": [],
            "completed_races": completed,
            "conflicts": [],
            "pairings": [],
            "cross_discipline": [],
            "macrocycle_summary": "当前暂无未来待备战的比赛计划，建议以稳态基础有氧、神经肌肉激活与日常体能储备为主。"
        }

    # Resolve A/B/C tiers
    has_explicit_a = any(str(r.get("priority") or "").upper() in ["A", "1"] for r in upcoming)
    for idx, r in enumerate(upcoming):
        raw_pri = str(r.get("priority") or "").upper()
        if raw_pri in ["A", "1"]:
            tier = "A"
            role = "A 标核心目标 (Goal Race)"
        elif raw_pri in ["B", "2"]:
            tier = "B"
            role = "B 标以赛代练 (Tune-up Test)"
        elif raw_pri in ["C", "3"]:
            tier = "C"
            role = "C 标训练拉练 (Training Run)"
        else:
            if not has_explicit_a and idx == len(upcoming) - 1:
                tier = "A"
                role = "A 标核心目标 (Goal Race)"
            elif idx == 0 and len(upcoming) > 1:
                tier = "B"
                role = "B 标以赛代练 (Tune-up Test)"
            else:
                tier = "B" if "半" in str(r.get("race_type") or "") else "A"
                role = "B 标以赛代练" if tier == "B" else "A 标核心目标"
        r["tier"] = tier
        r["role"] = role

    conflicts = []
    pairings = []
    cross_discipline = []

    for i in range(len(upcoming) - 1):
        r1 = upcoming[i]
        r2 = upcoming[i + 1]
        gap = (r2["parsed_date"] - r1["parsed_date"]).days
        r1["gap_to_next"] = gap

        r1_type = str(r1.get("race_type") or "").lower()
        r2_type = str(r2.get("race_type") or "").lower()
        r1_is_major = any(k in r1_type or k in r1["name"].lower() for k in ["全马", "marathon", "50k", "100k", "越野", "trail"])
        r2_is_major = any(k in r2_type or k in r2["name"].lower() for k in ["全马", "marathon", "50k", "100k", "越野", "trail"])

        # Conflict: 2 major races < 21 days
        if gap < 21 and r1_is_major and r2_is_major:
            conflicts.append({
                "race1": r1["name"],
                "race2": r2["name"],
                "gap_days": gap,
                "warning": f"【赛程冲突警报】{r1['name']} 与 {r2['name']} 间隔仅 {gap} 天！大负荷全马/越野后深层肌纤维与结缔组织微损伤至少需要 21~28 天超量修复。Canova 建议：必须将后一场设为 C 标（以赛代练/慢跑陪跑），严禁背靠背连续拼全力突破，否则极易诱发应力性骨折与中枢疲劳崩溃。"
            })

        # Optimal B -> A tune-up pairing: 20-45 days before a major race
        r1_is_tuneup = any(k in r1_type or k in r1["name"].lower() for k in ["半马", "half", "10k", "10公里"])
        r2_is_marathon = any(k in r2_type or k in r2["name"].lower() for k in ["全马", "marathon"])
        if 20 <= gap <= 45 and r1_is_tuneup and r2_is_marathon:
            pairings.append({
                "tuneup_race": r1["name"],
                "goal_race": r2["name"],
                "gap_days": gap,
                "strategy": f"【黄金以赛代练配对】{r1['name']} 位于 {r2['name']} 赛前 {gap} 天（4~6 周窗口）。属于标准的 Canova B 标专项准备实战：在 {r1['name']} 中以目标半马配速巡航检验乳酸门槛，赛前无需深度减量（减 3 天即可），赛后 4~5 天低心率排酸后无缝衔接全马最后专项收敛。"
            })

        # Cross-discipline transition
        r1_is_trail = "越野" in r1["name"] or "trail" in r1_type or "50k" in r1["name"].lower()
        r2_is_trail = "越野" in r2["name"] or "trail" in r2_type or "50k" in r2["name"].lower()
        if r1_is_trail != r2_is_trail:
            cross_discipline.append({
                "from_race": r1["name"],
                "to_race": r2["name"],
                "transition_tip": f"【跨赛道专项切换】从 {r1['name']} ({'越野' if r1_is_trail else '路跑'}) 转向 {r2['name']} ({'越野' if r2_is_trail else '路跑'})：需经历专项转换。若从路跑转越野，赛后第 2 周起需逐步加入山地手杖爬升 (D+) 与下坡离心抗阻；若从越野转公路，赛前 4 周必须停止大爬升以唤醒平地步频刚性与跑步经济性。"
            })

    # Summary description
    a_races = [r["name"] for r in upcoming if r["tier"] == "A"]
    b_races = [r["name"] for r in upcoming if r["tier"] == "B"]
    summary_parts = []
    if a_races:
        summary_parts.append(f"核心突破 A 标：【{' / '.join(a_races)}】")
    if b_races:
        summary_parts.append(f"以赛代练 B 标：【{' / '.join(b_races)}】")
    if conflicts:
        summary_parts.append(f"⚠️ 存在 {len(conflicts)} 处赛程过密冲突需战术规避")

    # Clean serializable objects (remove parsed_date)
    serializable_races = []
    for r in upcoming:
        rc = dict(r)
        rc.pop("parsed_date", None)
        serializable_races.append(rc)

    return {
        "total_upcoming": len(serializable_races),
        "total_completed": len(completed),
        "races": serializable_races,
        "completed_races": completed,
        "conflicts": conflicts,
        "pairings": pairings,
        "cross_discipline": cross_discipline,
        "macrocycle_summary": " · ".join(summary_parts) if summary_parts else "按赛历时间节点逐步推进专项周期化训练"
    }


def calculate_workout_effective_vdot(
    distance_meters: float,
    time_seconds: float,
    avg_hr: Optional[float] = None,
    rest_hr: float = 58.0,
    max_hr: float = 190.0,
    elevation_gain_m: float = 0.0,
) -> Optional[float]:
    """
    Calculates single-workout Effective VDOT (单次等效 VDOT / 心率配速效率)
    by combining a conservative Grade-Adjusted Distance (GAD) with a damped
    Karvonen Heart Rate Reserve (%HRR) efficiency adjustment.
    Anchored to Jack Daniels VDOT so submaximal runs receive modest positive
    feedback without inflating VDOT beyond realistic race capabilities.
    """
    if not distance_meters or distance_meters < 2000 or not time_seconds or time_seconds < 360:
        return None

    dist_f = float(distance_meters)
    time_f = float(time_seconds)
    pace_s_km = time_f / (dist_f / 1000.0)

    # Filter out GPS glitches (< 2:45/km) and walking/trekking hikes (> 8:30/km)
    if pace_s_km < 165.0 or pace_s_km > 510.0:
        return None

    raw_vdot = calculate_vdot(dist_f, time_f)
    if raw_vdot <= 0:
        return None

    # Slow jog / trail hike-run (7:30/km - 8:30/km): return raw VDOT without HR/elevation extrapolation
    if pace_s_km > 450.0:
        return round(max(18.0, min(82.0, raw_vdot)), 1)

    # Conservative Grade-Adjusted Distance (ignore <4m/km flat barometer jitter; cap +3.5% road, +1.5% steep trail)
    elev = max(0.0, float(elevation_gain_m or 0.0))
    grade = elev / dist_f
    if grade > 0.004:
        max_gad_pct = 0.035 if grade <= 0.03 else 0.015
        eff_dist = dist_f + min((elev - dist_f * 0.004) * 2.5, dist_f * max_gad_pct)
    else:
        eff_dist = dist_f
    gad_vdot = calculate_vdot(eff_dist, time_f)

    if not avg_hr or avg_hr <= 0:
        return round(max(20.0, min(82.0, gad_vdot)), 1)

    r_hr = float(rest_hr or 58.0)
    m_hr = float(max_hr or 190.0)
    if m_hr <= r_hr + 25:
        m_hr = max(185.0, r_hr + 120.0)

    if avg_hr <= r_hr + 15:
        return round(max(20.0, min(82.0, gad_vdot)), 1)

    hrr = (float(avg_hr) - r_hr) / (m_hr - r_hr)
    hrr = max(0.45, min(0.98, hrr))
    if hrr < 0.56:
        # Very low Zone 1 jog: avoid noisy stroke-volume extrapolation
        return round(max(20.0, min(82.0, gad_vdot + 0.4)), 1)

    # Expected race-effort %HRR for duration t_min (~88% for 5K/10K, ~84% for HM, ~80% for FM)
    t_min = time_f / 60.0
    expected_hrr = min(0.91, max(0.79, 0.77 + 0.14 * math.exp(-t_min / 90.0)))
    reserve_gap = max(0.0, expected_hrr - hrr)

    # Conservative aerobic efficiency bonus (capped at +1.8 VDOT points on controlled aerobic runs)
    hr_bonus = min(1.8, gad_vdot * 0.14 * reserve_gap)
    eff_vdot = gad_vdot + hr_bonus
    return round(max(20.0, min(82.0, eff_vdot)), 1)


def simulate_taper_7d(current_ctl: float, current_atl: float) -> Dict[str, Any]:
    """
    Projects 7-day CTL / ATL / TSB trajectories under 3 taper scenarios:
    - taper_50: 50% of current CTL daily load (standard pre-race taper)
    - taper_20: 80% of current CTL daily load (light sharpening taper)
    - rest: 0% load (complete rest)
    """
    from datetime import date, timedelta

    ctl_k = 2.0 / (42 + 1)
    atl_k = 2.0 / (7 + 1)
    base_ctl = float(current_ctl or 0.0)
    base_atl = float(current_atl or 0.0)
    today = date.today()

    scenario_defs = [
        {"key": "taper_50", "label": "标准减量 50% (推荐备赛)", "subtitle": "跑量减半 · 保留短促赛速刺激", "factor": 0.50},
        {"key": "taper_20", "label": "轻量减量 20% (保持锐度)", "subtitle": "维持 80% 负荷 · 适合 C 标拉练", "factor": 0.80},
        {"key": "rest", "label": "完全休整 (0负荷)", "subtitle": "连续跑休排酸 · 适合深度疲劳期", "factor": 0.0},
    ]

    scenarios_list = []
    scenarios_map = {}

    for sdef in scenario_defs:
        c = base_ctl
        a = base_atl
        daily_load = round(base_ctl * sdef["factor"], 1)
        days_to_pos = 0 if (c - a) >= 0 else None
        days_arr = []
        for d_idx in range(1, 8):
            d_obj = today + timedelta(days=d_idx)
            c = c + ctl_k * (daily_load - c)
            a = a + atl_k * (daily_load - a)
            t = round(c - a, 1)
            if days_to_pos is None and t >= 0:
                days_to_pos = d_idx
            days_arr.append({
                "day_offset": d_idx,
                "date": d_obj.isoformat(),
                "short_date": d_obj.strftime("%m-%d"),
                "date_label": f"D+{d_idx} ({d_obj.strftime('%m/%d')})",
                "ctl": round(c, 1),
                "atl": round(a, 1),
                "tsb": t,
            })

        day7_tsb = days_arr[-1]["tsb"] if days_arr else round(base_ctl - base_atl, 1)
        if day7_tsb >= 5:
            readiness_label = "巅峰竞技区"
        elif day7_tsb >= -5:
            readiness_label = "良好参赛区"
        else:
            readiness_label = "恢复调整中"

        item = {
            "key": sdef["key"],
            "label": sdef["label"],
            "subtitle": sdef["subtitle"],
            "factor": sdef["factor"],
            "daily_trimp": daily_load,
            "days_to_positive_tsb": days_to_pos,
            "projected_day7_tsb": day7_tsb,
            "readiness_label": readiness_label,
            "days": days_arr,
        }
        scenarios_list.append(item)
        scenarios_map[sdef["key"]] = item

    cur_tsb = round(base_ctl - base_atl, 1)
    d50 = scenarios_map["taper_50"]["projected_day7_tsb"]
    days_pos_50 = scenarios_map["taper_50"]["days_to_positive_tsb"]

    if cur_tsb > 5:
        rec_key = "taper_20"
        rec_label = "轻量减量 20%"
        advice = f"当前状态指数 TSB 为 +{cur_tsb}（已处巅峰充沛区），无需过度减量，建议采用「轻量减量 20%」维持神经肌肉张力。"
    elif days_pos_50 is not None or cur_tsb >= -25:
        rec_key = "taper_50"
        rec_label = "标准减量 50%"
        pos_str = f"预计 {days_pos_50} 天后状态回正，" if days_pos_50 else ""
        advice = f"当前 TSB 为 {cur_tsb}；若本周执行「标准减量 50%」，{pos_str}7 天后可达 {d50:+.1f} 黄金参赛区。"
    else:
        rec_key = "rest"
        rec_label = "完全休整 / 深度减量"
        d_rest = scenarios_map["rest"]["days_to_positive_tsb"]
        advice = (
            f"近期累积疲劳较深（TSB {cur_tsb}），标准减量 50% 在 7 天后预计回升至 {d50:+.1f}；"
            + (f"若需快速回正需连续休整约 {d_rest} 天。" if d_rest else "建议优先安排 2~3 天完全跑休与充足睡眠。")
        )

    return {
        "current_ctl": round(base_ctl, 1),
        "current_atl": round(base_atl, 1),
        "current_tsb": cur_tsb,
        "recommended_strategy": rec_key,
        "recommended_strategy_label": rec_label,
        "recommendation_summary": advice,
        "coach_taper_advice": advice,
        "scenarios": scenarios_list,
    }


def _assess_long_run_anti_fade(act: Dict[str, Any]) -> Optional[float]:
    """
    Evaluates late-run cardiac drift / pace decoupling (%) for a >=15km run.
    Positive value = decoupling / fade (e.g. +8.5% means noticeable drift/slowdown in 2nd half);
    <= +3.5% indicates strong Canova steady/negative-split control.
    """
    import json

    seg_raw = act.get("segment_analysis") or act.get("segment_analysis_json")
    if seg_raw:
        try:
            seg_obj = json.loads(seg_raw) if isinstance(seg_raw, str) else seg_raw
            if isinstance(seg_obj, dict):
                segs = seg_obj.get("segments") or seg_obj.get("phases") or []
                drifts = [
                    float(
                        s["cardiac_drift_pct"]
                        if s.get("cardiac_drift_pct") is not None
                        else s["decoupling_pct"]
                    )
                    for s in segs
                    if isinstance(s, dict)
                    and (s.get("cardiac_drift_pct") is not None or s.get("decoupling_pct") is not None)
                    and float(s.get("distance_km") or 0) >= 6.0
                ]
                if drifts:
                    return round(sum(drifts) / len(drifts), 1)
        except Exception:
            pass

    splits_raw = act.get("splits_data") or act.get("splits") or act.get("laps_data") or act.get("laps")
    if splits_raw:
        try:
            splits = json.loads(splits_raw) if isinstance(splits_raw, str) else splits_raw
            if isinstance(splits, list) and len(splits) >= 6:
                valid_sp = []
                for sp in splits:
                    if not isinstance(sp, dict):
                        continue
                    w_type = str(sp.get("wktStepType") or sp.get("lapType") or sp.get("intensityType") or "").upper()
                    if w_type.startswith("RWD_"):
                        continue
                    d_m = float(sp.get("distance") or sp.get("distance_m") or 0.0)
                    t_s = float(sp.get("movingDuration") or sp.get("duration") or sp.get("time_s") or sp.get("totalTime") or 0.0)
                    hr_v = float(sp.get("averageHR") or sp.get("avgHr") or sp.get("avgHeartRate") or sp.get("hr") or 0.0)
                    if d_m >= 500 and t_s >= 90:
                        valid_sp.append((d_m, t_s, hr_v))
                if len(valid_sp) >= 6:
                    # Skip first warmup split and compare first steady half vs final steady half
                    core = valid_sp[1:] if len(valid_sp) >= 7 else valid_sp
                    mid = len(core) // 2
                    first_h, second_h = core[:mid], core[mid:]
                    d1, t1 = sum(x[0] for x in first_h), sum(x[1] for x in first_h)
                    d2, t2 = sum(x[0] for x in second_h), sum(x[1] for x in second_h)
                    if d1 > 0 and t1 > 0 and d2 > 0 and t2 > 0:
                        spd1, spd2 = d1 / t1, d2 / t2
                        hr1_list = [x[2] for x in first_h if x[2] > 80]
                        hr2_list = [x[2] for x in second_h if x[2] > 80]
                        if len(hr1_list) >= 2 and len(hr2_list) >= 2:
                            eff1 = spd1 / (sum(hr1_list) / len(hr1_list))
                            eff2 = spd2 / (sum(hr2_list) / len(hr2_list))
                            if eff1 > 0:
                                return round(((eff1 - eff2) / eff1) * 100.0, 1)
                        elif spd1 > 0:
                            return round(((spd1 - spd2) / spd1) * 100.0, 1)
        except Exception:
            pass

    return None


def compute_canova_athlete_matrix(
    profile: Dict[str, Any],
    activities: List[Dict[str, Any]],
    current_ctl: float = 0.0,
    current_tsb: float = 0.0,
    health_trend: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Computes RGM's calibrated 5-dimension Canova Specificity & Autonomic Recovery Matrix:
    - Decouples physiological watch VO2Max from realized running performance VDOT
    - Incorporates 6-week volume, CTL, 16k+/25k+ long-run depth & anti-fade drift,
      barometer-filtered elevation + cadence leg conditioning, and 7d vs 30d HRV/RHR/Sleep recovery
    """
    from datetime import date, timedelta

    rest_hr = float(profile.get("resting_heart_rate") or 58.0)
    max_hr = float(profile.get("max_heart_rate") or 190.0)
    today = date.today()
    cutoff_42d = (today - timedelta(days=42)).isoformat()
    cutoff_56d = (today - timedelta(days=56)).isoformat()
    cutoff_7d = (today - timedelta(days=7)).isoformat()

    recent_raw_vdots: List[float] = []
    recent_eff_vdots: List[float] = []
    older_raw_vdots: List[float] = []
    older_eff_vdots: List[float] = []
    short_run_vdots: List[float] = []
    long_run_vdots: List[float] = []
    latest_workout_vdot: Optional[float] = None

    km_42d = 0.0
    elev_42d = 0.0
    eff_elev_42d = 0.0
    long_runs_16k = 0
    long_runs_25k = 0
    longest_km = 0.0
    active_days_42d = set()
    long_run_drifts: List[float] = []
    cadence_samples: List[float] = []

    _RUN_SPORTS = {
        "run",
        "running",
        "trailrun",
        "trail run",
        "trail_running",
        "treadmill_running",
        "track_running",
        "street_running",
        "obstacle_run",
        "indoor_running",
        "virtual_run",
    }

    for act in (activities or []):
        if act.get("exclude_mode") == "excluded" or act.get("is_excluded"):
            continue
        raw_sport = str(act.get("sport_type") or "").strip().lower()
        if raw_sport and raw_sport not in _RUN_SPORTS and "run" not in raw_sport and "跑" not in raw_sport:
            continue
        dist_m = float(act.get("distance_meters") or 0.0)
        time_s = float(act.get("moving_time_seconds") or 0.0)
        st = str(act.get("start_time") or "")[:10]
        elev_m = max(0.0, float(act.get("elevation_gain_meters") or act.get("total_elevation_gain") or 0.0))
        avg_hr = float(act.get("average_heartrate") or 0.0)
        avg_cad = float(act.get("average_cadence") or 0.0)

        if st >= cutoff_42d and dist_m >= 1000:
            km = dist_m / 1000.0
            km_42d += km
            elev_42d += elev_m
            grade_m_per_km = elev_m / max(1.0, km)
            # Discount flat-road barometer jitter (<5m/km) while counting real slopes/hills fully
            if grade_m_per_km < 5.0:
                eff_elev_42d += elev_m * 0.35
            elif grade_m_per_km < 12.0:
                eff_elev_42d += elev_m * 0.80
            else:
                eff_elev_42d += elev_m

            active_days_42d.add(st)
            if km >= 15.5:
                long_runs_16k += 1
                drift_val = _assess_long_run_anti_fade(act)
                if drift_val is not None:
                    long_run_drifts.append(drift_val)
            if km >= 24.5:
                long_runs_25k += 1
            if km > longest_km:
                longest_km = km
            if 130.0 <= avg_cad <= 230.0 and km >= 3.0:
                cadence_samples.append(avg_cad)

        # VDOT speed/efficiency indexing (exclude ultra-marathons >45km and hikes >8:00/km)
        if act.get("exclude_mode") != "ignore_vdot" and 3000 <= dist_m <= 45000 and time_s >= 600:
            elp_s = float(act.get("elapsed_time_seconds") or 0.0)
            # Guard against GPS auto-pause glitches or heavily paused interval sessions
            vdot_time_s = elp_s if (elp_s > time_s * 1.18 and (elp_s - time_s) > 240.0) else time_s
            pace_s_km = vdot_time_s / (dist_m / 1000.0)
            sp_low = str(act.get("sport_type") or "").lower()
            nm_low = str(act.get("name") or "").lower()
            is_treadmill = ("treadmill" in sp_low or "indoor" in sp_low or "跑步机" in nm_low or "室内" in nm_low)
            is_cad_glitch = (avg_cad > 0 and avg_cad < 138.0 and pace_s_km < 330.0)
            is_hr_glitch = (pace_s_km < 270.0 and 0 < avg_hr < 122.0)

            if 165.0 <= pace_s_km <= 480.0 and not is_cad_glitch and not is_hr_glitch and not (is_treadmill and pace_s_km < 240.0):
                rv = calculate_vdot(dist_m, vdot_time_s)
                # Anaerobic speed discount on short <4.8km efforts for endurance VDOT baseline
                adj_rv = round(rv * 0.97, 1) if dist_m < 4800 else rv
                ev = calculate_workout_effective_vdot(dist_m, vdot_time_s, avg_hr, rest_hr, max_hr, elev_m)
                if ev and dist_m < 4800:
                    ev = round(ev * 0.97, 1)

                if ev and latest_workout_vdot is None:
                    latest_workout_vdot = ev

                if st >= cutoff_56d:
                    if adj_rv > 0:
                        recent_raw_vdots.append(adj_rv)
                        if dist_m < 14000:
                            short_run_vdots.append(rv)
                        elif dist_m >= 15500:
                            long_run_vdots.append(rv)
                    if ev:
                        recent_eff_vdots.append(ev)
                else:
                    is_continuous = not (elp_s > time_s * 1.09 and (elp_s - time_s) > 180.0)
                    if adj_rv > 0 and is_continuous and not is_treadmill:
                        older_raw_vdots.append(adj_rv)
                    if ev:
                        older_eff_vdots.append(ev)

    # 1. Physiological Watch VO2Max vs Practical Realized VDOT (separated, no longer 1:1 equated)
    watch_vo2: Optional[float] = None
    if health_trend:
        for h_row in reversed(health_trend):
            v_h = h_row.get("vo2_max") or h_row.get("vo2max")
            if v_h is not None and float(v_h or 0) > 0:
                watch_vo2 = round(float(v_h), 1)
                break
    if watch_vo2 is None and profile.get("vo2max") is not None and float(profile.get("vo2max") or 0) > 0:
        watch_vo2 = round(float(profile["vo2max"]), 1)

    def _pb_to_sec(val: Any) -> int:
        if val is None or val == "":
            return 0
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip()
        if not s:
            return 0
        if ":" in s:
            parts = s.split(":")
            try:
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(float(parts[1]))
            except Exception:
                return 0
        try:
            return int(float(s))
        except Exception:
            return 0

    raw_mp = _pb_to_sec(profile.get("marathon_pb"))
    raw_hp = _pb_to_sec(profile.get("half_pb"))
    raw_tk = _pb_to_sec(profile.get("ten_k_pb"))
    raw_fk = _pb_to_sec(profile.get("five_k_pb"))
    is_default_pb_tuple = (
        (raw_mp == 10800 and raw_hp == 5100 and raw_tk == 2400 and raw_fk == 1140)
        or (raw_mp == 11370 and raw_hp == 5457 and raw_tk == 2426 and raw_fk == 1164)
    )

    pb_vdot = 0.0
    pb_anchor_vdot = 0.0
    if not is_default_pb_tuple:
        v_mp = calculate_vdot(42195.0, float(raw_mp)) if (7200 <= raw_mp <= 30000 and raw_mp not in (10800, 11370)) else 0.0
        v_hp = calculate_vdot(21097.5, float(raw_hp)) if (3000 <= raw_hp <= 15000 and raw_hp not in (5100, 5457)) else 0.0
        v_tk = calculate_vdot(10000.0, float(raw_tk)) if (1200 <= raw_tk <= 7200) else 0.0
        v_fk = calculate_vdot(5000.0, float(raw_fk)) if (600 <= raw_fk <= 3600) else 0.0
        valid_pbs = [v for v in (v_mp, v_hp, v_tk, v_fk) if v > 0]
        if valid_pbs:
            pb_vdot = max(valid_pbs)
        # Prefer Half/Full endurance PBs over single short-distance PBs when anchoring aerobic VDOT
        endurance_pbs = [v for v in (v_mp, v_hp * 0.975 if v_hp > 0 else 0.0) if v > 0]
        if endurance_pbs:
            pb_anchor_vdot = max(endurance_pbs)
        elif v_tk > 0 or v_fk > 0:
            pb_anchor_vdot = max(v_tk * 0.95, v_fk * 0.925)

    older_peak_vdot = max(older_raw_vdots) if older_raw_vdots else 0.0
    peak_vdot = max(pb_vdot, float(profile.get("peak_vdot") or 0.0), older_peak_vdot)
    peak_anchor_vdot = max(
        pb_anchor_vdot,
        float(profile.get("peak_endurance_vdot") or 0.0),
        older_peak_vdot * 0.96 if older_peak_vdot > 0 else 0.0,
    )

    recent_workout_vdot = 0.0
    workout_vdot = 0.0
    if recent_raw_vdots:
        top_r = sorted(recent_raw_vdots, reverse=True)[:3]
        raw_anchor = (0.60 * top_r[0] + 0.40 * top_r[1]) if len(top_r) >= 2 else top_r[0]
        if recent_eff_vdots:
            top_e = sorted(recent_eff_vdots, reverse=True)[:3]
            eff_avg = sum(top_e) / len(top_e)
            workout_vdot = min(raw_anchor + 1.5, 0.45 * raw_anchor + 0.55 * eff_avg)
        else:
            workout_vdot = raw_anchor
        recent_workout_vdot = workout_vdot
    elif older_raw_vdots:
        top_or = sorted(older_raw_vdots, reverse=True)[:2]
        raw_anchor = sum(top_or) / len(top_or)
        workout_vdot = max(20.0, raw_anchor * 0.88)

    wk_km = km_42d / 6.0
    calibrated_watch_vdot: Optional[float] = None
    if watch_vo2 is not None and watch_vo2 > 0:
        # Running economy & fractional utilization realization factor (0.835 at 0km/wk -> up to 0.93 at 80km+/wk & 32km+ LSD)
        re_factor = min(
            0.93,
            0.835
            + min(0.065, wk_km / 1200.0)
            + min(0.030, max(0.0, min(35.0, longest_km) - 12.0) / 750.0),
        )
        calibrated_watch_vdot = round(watch_vo2 * re_factor, 1)

    # Dual-track VDOT: keep current effective_vdot safe for current injury/rehab training paces,
    # while granting a bounded structural base cushion (+0 to +4.2 VDOT) for proven high-level runners.
    perf_vdot = 0.0
    if recent_workout_vdot > 0:
        if peak_anchor_vdot > recent_workout_vdot:
            base_cushion = min(5.8, (peak_anchor_vdot - recent_workout_vdot) * 0.28)
            perf_vdot = recent_workout_vdot + base_cushion
        else:
            perf_vdot = recent_workout_vdot
    elif peak_anchor_vdot > 0:
        perf_vdot = max(20.0, peak_anchor_vdot * (0.89 if wk_km >= 20.0 else 0.85))
    elif workout_vdot > 0:
        perf_vdot = workout_vdot

    effective_vdot: Optional[float] = None
    if perf_vdot > 0 and calibrated_watch_vdot is not None:
        blended_v = 0.80 * perf_vdot + 0.20 * calibrated_watch_vdot
        # Cap watch VO2Max upward pull at +1.8 above actual demonstrated running output
        effective_vdot = round(max(perf_vdot - 1.2, min(perf_vdot + 1.8, blended_v)), 1)
    elif perf_vdot > 0:
        effective_vdot = round(perf_vdot, 1)
    elif calibrated_watch_vdot is not None:
        effective_vdot = calibrated_watch_vdot

    if effective_vdot and effective_vdot > peak_vdot:
        peak_vdot = effective_vdot
    peak_vdot_rounded = round(peak_vdot, 1) if peak_vdot > 0 else None
    peak_endurance_rounded = (
        round(peak_anchor_vdot, 1)
        if peak_anchor_vdot > 0
        else (round(peak_vdot * 0.95, 1) if peak_vdot > 0 else None)
    )

    ref_current_v = recent_workout_vdot if recent_workout_vdot > 0 else (effective_vdot or 0.0)
    is_recovery_phase = bool(
        peak_vdot_rounded
        and peak_vdot_rounded >= 42.0
        and effective_vdot
        and (
            (recent_workout_vdot > 0 and (peak_vdot_rounded - ref_current_v) >= 4.5 and (peak_vdot_rounded - effective_vdot) >= 2.2)
            or (recent_workout_vdot == 0 and (peak_vdot_rounded - effective_vdot) >= 3.0)
        )
    )

    def _fmt_hms(secs: int) -> str:
        if not secs or secs <= 0:
            return "—"
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"

    peak_marathon_potential: Optional[str] = None
    recovery_phase_label: Optional[str] = None
    if peak_endurance_rounded and peak_endurance_rounded > 0:
        peak_marathon_potential = _fmt_hms(vdot_to_race_time(peak_endurance_rounded, 42195.0))
    if is_recovery_phase and peak_vdot_rounded:
        pot_clause = f"（满血实力 ~{peak_marathon_potential}）" if peak_marathon_potential and peak_marathon_potential != "—" else ""
        recovery_phase_label = f"🩹 恢复/休整期 · 历史巅峰 VDOT {peak_vdot_rounded}{pot_clause}"

    vo2max_utilization_pct: Optional[float] = None
    if effective_vdot and watch_vo2 and watch_vo2 > 0:
        vo2max_utilization_pct = round(min(100.0, (effective_vdot / watch_vo2) * 100.0), 1)

    # 2. Endurance Retention & Anti-Fade Diagnosis
    v_short = max(short_run_vdots) if short_run_vdots else 0.0
    v_long = max(long_run_vdots) if long_run_vdots else 0.0
    if not is_default_pb_tuple:
        if raw_fk > 0:
            v_short = max(v_short, calculate_vdot(5000.0, float(raw_fk)))
        if raw_tk > 0:
            v_short = max(v_short, calculate_vdot(10000.0, float(raw_tk)))
        if raw_mp not in (0, 10800, 11370):
            v_long = max(v_long, calculate_vdot(42195.0, float(raw_mp)))
        elif raw_hp not in (0, 5100, 5457):
            v_long = max(v_long, calculate_vdot(21097.5, float(raw_hp)))

    retention_ratio = round((v_long / v_short) * 100.0, 1) if (v_short > 0 and v_long > 0) else None
    avg_drift_pct = round(sum(long_run_drifts) / len(long_run_drifts), 1) if long_run_drifts else None

    if (
        (retention_ratio and retention_ratio >= 95.5)
        or (long_runs_25k >= 2 and long_runs_16k >= 5 and (avg_drift_pct is None or avg_drift_pct <= 5.5))
    ):
        runner_type_code = "endurance_strong"
        runner_type_label = "🏔️ 耐力抗衰减型"
        focus_tip = "长距离有氧保持率扎实，建议每周穿插 1 次乳酸门槛 (T) 或间歇 (I) 课以推高专项速度上限。"
    elif (retention_ratio and retention_ratio < 91.0) or (avg_drift_pct is not None and avg_drift_pct > 8.0) or (effective_vdot and effective_vdot >= 46.0 and longest_km < 20.0):
        runner_type_code = "speed_dominant"
        runner_type_label = "⚡ 速度偏强·耐力待补"
        focus_tip = "中短距离速度潜力优于当前长距离兑现力，建议周末逐步延伸 22~30km 稳态有氧长距离以压低后程心率漂移。"
    elif km_42d >= 150:
        runner_type_code = "balanced"
        runner_type_label = "⚖️ 有氧专项均衡型"
        focus_tip = "有氧跑量与配速效率较均衡，可结合目标赛事逐步增加比赛配速巡航段落。"
    else:
        runner_type_code = "base_building"
        runner_type_label = "🌱 有氧底座筑基期"
        focus_tip = "建议优先保持每周 3~4 次低心率有氧慢跑，稳步提升周跑量与单次耐力时长。"

    # 3. Calibrated Five Dimensions (0 - 100, strict Canova coaching scale)
    # (1) Aerobic Base: 6-week volume + CTL + weekly consistency (requires ~80km/wk & CTL 70+ for 90+)
    if km_42d <= 0 and current_ctl <= 1.0:
        aerobic_score = 18
    else:
        if wk_km <= 30.0:
            vol_pts = wk_km * 0.70
        elif wk_km <= 60.0:
            vol_pts = 21.0 + (wk_km - 30.0) * 0.46
        else:
            vol_pts = 34.8 + min(11.2, (wk_km - 60.0) * 0.28)
        ctl_pts = min(32.0, current_ctl * 0.40)
        cons_pts = min(8.0, (len(active_days_42d) / 24.0) * 8.0)
        aerobic_score = int(min(96, max(20, round(12.0 + vol_pts + ctl_pts + cons_pts))))

    # (2) Pace-HR Efficiency: anchored to calibrated effective_vdot (not raw watch VO2Max)
    if effective_vdot is None or effective_vdot <= 0:
        efficiency_score = 25
        eff_disp = f"手表 VO2Max {watch_vo2}" if watch_vo2 else "待采集跑步记录"
    else:
        if effective_vdot >= 32.0:
            efficiency_score = int(min(96, max(22, round(42.0 + (effective_vdot - 32.0) * 1.85))))
        else:
            efficiency_score = int(max(20, round(22.0 + max(0.0, effective_vdot - 20.0) * 1.65)))
        if is_recovery_phase and peak_vdot_rounded:
            eff_disp = f"当期 VDOT {effective_vdot} · 巅峰 {peak_vdot_rounded}"
        elif watch_vo2:
            eff_disp = f"有效 VDOT {effective_vdot} (VO2Max {watch_vo2})"
        else:
            eff_disp = f"有效 VDOT {effective_vdot}"

    # (3) Long-Run Anti-Fade Endurance: longest run + 16k+ count + 25k+ specificity + real drift/retention check
    drift_adj = 0.0
    if avg_drift_pct is not None:
        if avg_drift_pct <= 3.5:
            drift_adj = 5.0
        elif avg_drift_pct <= 6.5:
            drift_adj = 1.0
        elif avg_drift_pct <= 10.0:
            drift_adj = -4.0
        else:
            drift_adj = -9.0
    elif retention_ratio is not None:
        if retention_ratio >= 95.0:
            drift_adj = 3.0
        elif retention_ratio < 90.0:
            drift_adj = -5.0

    if longest_km < 5.0:
        endurance_score = 20
    else:
        longest_pts = min(30.0, max(0.0, min(35.0, longest_km) - 5.0) * 1.0)
        lr16_pts = min(24.0, long_runs_16k * 4.2)
        lr25_pts = min(18.0, long_runs_25k * 6.0)
        endurance_score = int(min(96, max(20, round(18.0 + longest_pts + lr16_pts + lr25_pts + drift_adj))))

    drift_tag = f" · 漂移 {avg_drift_pct:+.1f}%" if avg_drift_pct is not None else (f" · 25k+ {long_runs_25k}次" if long_runs_25k > 0 else "")
    endurance_disp = f"16k+ {long_runs_16k}次 · 最长 {round(longest_km, 1)}km{drift_tag}"

    # (4) Climbing & Muscular Endurance: barometer-filtered D+ + mileage/cadence leg conditioning
    avg_cadence = round(sum(cadence_samples) / len(cadence_samples)) if cadence_samples else None
    if km_42d <= 0 and elev_42d <= 0:
        climbing_score = 18
    else:
        leg_vol_pts = min(14.0, km_42d / 28.0)
        cad_pts = 0.0
        if avg_cadence:
            if avg_cadence >= 180:
                cad_pts = 7.0
            elif avg_cadence >= 174:
                cad_pts = 5.0
            elif avg_cadence >= 168:
                cad_pts = 2.5
        if eff_elev_42d <= 1500.0:
            elev_pts = (eff_elev_42d / 1500.0) * 26.0
        elif eff_elev_42d <= 4500.0:
            elev_pts = 26.0 + ((eff_elev_42d - 1500.0) / 3000.0) * 22.0
        else:
            elev_pts = 48.0 + min(11.0, ((eff_elev_42d - 4500.0) / 3500.0) * 11.0)
        climbing_score = int(min(96, max(20, round(16.0 + leg_vol_pts + cad_pts + elev_pts))))

    cad_tag = f" · 步频 {avg_cadence}" if avg_cadence else ""
    climbing_disp = f"近6周 +{int(round(elev_42d))}m{cad_tag}"

    # (5) Autonomic Recovery: 7d vs 30d Sleep + HRV + Resting HR + TSB (honest fallback when watch not worn at night)
    hrv_30d = [
        float(h.get("hrv") or h.get("hrv_last_night_avg"))
        for h in (health_trend or [])
        if (h.get("hrv") or h.get("hrv_last_night_avg") or 0) > 0
    ]
    rhr_30d = [
        float(h["resting_heart_rate"])
        for h in (health_trend or [])
        if (h.get("resting_heart_rate") or 0) > 0
    ]
    recent_7d = [
        h for h in (health_trend or [])
        if (not h.get("date") or str(h.get("date"))[:10] >= cutoff_7d)
        and (
            (h.get("sleep_score") or 0) > 0
            or (h.get("hrv") or h.get("hrv_last_night_avg") or 0) > 0
            or (h.get("body_battery") or h.get("body_battery_max") or 0) > 0
            or (h.get("resting_heart_rate") or 0) > 0
        )
    ]

    slp_7d = [float(h["sleep_score"]) for h in recent_7d if (h.get("sleep_score") or 0) > 0]
    bb_7d = [float(h.get("body_battery") or h.get("body_battery_max")) for h in recent_7d if (h.get("body_battery") or h.get("body_battery_max") or 0) > 0]
    hrv_7d = [float(h.get("hrv") or h.get("hrv_last_night_avg")) for h in recent_7d if (h.get("hrv") or h.get("hrv_last_night_avg") or 0) > 0]
    rhr_7d = [float(h["resting_heart_rate"]) for h in recent_7d if (h.get("resting_heart_rate") or 0) > 0]

    has_nocturnal_wear = bool(slp_7d or hrv_7d or bb_7d)
    if not has_nocturnal_wear:
        # Conservative load-based readiness without inflating to 72-74 when nocturnal watch wear is missing
        tsb_only_adj = max(-18.0, min(6.0, current_tsb * 0.45))
        recovery_score = int(min(64, max(32, round(54.0 + tsb_only_adj))))
        recovery_disp = f"近7天缺夜间数据 · TSB {current_tsb:+.1f}"
        recovery_desc = "近 7 天缺少夜间睡眠与 HRV 佩戴数据，当前仅按训练疲劳度 (TSB) 保守评估；建议夜间佩戴手表以获取完整恢复评分。"
        recovery_data_status = "missing_nocturnal"
    else:
        if slp_7d:
            base_rec = (sum(slp_7d) / len(slp_7d)) * 0.80
        elif bb_7d:
            base_rec = (sum(bb_7d) / len(bb_7d)) * 0.72
        else:
            base_rec = 60.0

        hrv_adj = 0.0
        if hrv_7d:
            hrv_avg_7d = sum(hrv_7d) / len(hrv_7d)
            wk_hrv_candidates = [float(h["hrv_weekly_avg"]) for h in recent_7d if (h.get("hrv_weekly_avg") or 0) > 0]
            hrv_base = (
                (sum(hrv_30d) / len(hrv_30d))
                if len(hrv_30d) >= 4
                else (wk_hrv_candidates[-1] if wk_hrv_candidates else hrv_avg_7d)
            )
            if hrv_base > 0:
                hrv_adj = max(-12.0, min(10.0, ((hrv_avg_7d - hrv_base) / hrv_base) * 80.0))

        rhr_adj = 0.0
        eff_rhr_disp = int(round(rest_hr))
        if rhr_7d:
            rhr_avg_7d = sum(rhr_7d) / len(rhr_7d)
            eff_rhr_disp = int(round(rhr_avg_7d))
            if len(rhr_30d) >= 4:
                sorted_rhr = sorted(rhr_30d)
                rhr_base = sum(sorted_rhr[: max(2, len(sorted_rhr) // 2)]) / max(2, len(sorted_rhr) // 2)
            else:
                rhr_base = rest_hr
            diff_bpm = rhr_avg_7d - rhr_base
            if diff_bpm <= 0.5:
                rhr_adj = min(5.0, 2.0 + max(0.0, -diff_bpm) * 1.0)
            else:
                rhr_adj = -min(10.0, (diff_bpm - 0.5) * 2.2)

        if current_tsb >= -5.0:
            tsb_adj = min(8.0, 2.0 + current_tsb * 0.35)
        else:
            tsb_adj = max(-12.0, (current_tsb + 5.0) * 0.35)

        recovery_score = int(min(95, max(25, round(base_rec + hrv_adj + rhr_adj + tsb_adj))))
        rec_parts = []
        if hrv_7d:
            rec_parts.append(f"HRV {int(round(sum(hrv_7d) / len(hrv_7d)))}ms")
        elif slp_7d:
            rec_parts.append(f"睡眠 {int(round(sum(slp_7d) / len(slp_7d)))}分")
        rec_parts.append(f"RHR {eff_rhr_disp}bpm")
        rec_parts.append(f"TSB {current_tsb:+.1f}")
        recovery_disp = " · ".join(rec_parts)
        recovery_desc = "综合近 7 天夜间睡眠、HRV 相对个人基线偏离度、静息心率波动及负荷平衡 (TSB) 评估的超量恢复水平。"
        recovery_data_status = "complete"

    eff_desc = (
        f"检测到近期处于恢复或低负荷休整期：主指标按当期安全状态评估配速，同时保留历史巅峰 VDOT {peak_vdot_rounded}（满血全马潜力 ~{peak_marathon_potential}）底座托底。"
        if (is_recovery_phase and peak_vdot_rounded)
        else "基于真实跑步表现与储备心率 (%HRR) 推算的实战跑力 VDOT（已剥离手表生理 VO2Max 虚高偏差）。"
    )
    dimensions = [
        {"key": "aerobic_base", "label": "有氧底座", "score": aerobic_score, "detail": f"近6周 {round(km_42d, 1)}km (周均 {round(wk_km, 1)}k) · CTL {round(current_ctl, 1)}", "display_value": f"近6周 {round(km_42d, 1)}km · CTL {round(current_ctl, 1)}", "desc": "基于近 42 天有氧跑量、出勤频次与慢性负荷 CTL 评估的线粒体与毛细血管底座（周均 75km+ 进入高水平区）。"},
        {"key": "pace_hr_efficiency", "label": "心率配速效率", "score": efficiency_score, "detail": eff_disp, "display_value": eff_disp, "desc": eff_desc},
        {"key": "long_run_endurance", "label": "长距离抗衰减", "score": endurance_score, "detail": endurance_disp, "display_value": endurance_disp, "desc": "综合 16km+/25km+ 长距离次数、单次最长距离及后半程心率配速抗衰减度评估的马拉松耐力。"},
        {"key": "climbing_strength", "label": "爬升与肌耐力", "score": climbing_score, "detail": climbing_disp, "display_value": climbing_disp, "desc": "过滤平路气压噪声后的真实坡度爬升 (D+) 与平路步频下肢抗冲击肌耐力评估。"},
        {"key": "autonomic_recovery", "label": "自主神经恢复", "score": recovery_score, "detail": recovery_disp, "display_value": recovery_disp, "desc": recovery_desc},
    ]

    overall_score = int(round(sum(d["score"] for d in dimensions) / len(dimensions)))
    vdot_label_str = f"{effective_vdot}" if effective_vdot else "待评估"
    vo2_clause = f"（手表 VO2Max {watch_vo2}）" if (watch_vo2 and effective_vdot and abs(watch_vo2 - effective_vdot) >= 0.5) else ""
    if is_recovery_phase and peak_vdot_rounded:
        pot_txt = f" · 满血潜力 ~{peak_marathon_potential}" if peak_marathon_potential and peak_marathon_potential != "—" else ""
        one_line = (
            f"检测到处于恢复/休整期（历史巅峰 VDOT {peak_vdot_rounded}{pot_txt}）· "
            f"当前有效 VDOT {vdot_label_str}{vo2_clause} 按近期安全状态匹配训练配速，建议稳步重建无痛周跑量与长距离，切勿急于按巅峰配速硬顶强度。"
        )
    else:
        one_line = f"当前有效 VDOT {vdot_label_str}{vo2_clause} · {runner_type_label} · {focus_tip}"

    return {
        "effective_vdot": effective_vdot,
        "watch_vo2max": watch_vo2,
        "vo2max_utilization_pct": vo2max_utilization_pct,
        "peak_vdot": peak_vdot_rounded,
        "peak_endurance_vdot": peak_endurance_rounded,
        "peak_marathon_potential": peak_marathon_potential,
        "is_recovery_phase": is_recovery_phase,
        "recovery_phase_label": recovery_phase_label,
        "baseline_vdot": peak_vdot_rounded if peak_vdot_rounded else effective_vdot,
        "latest_workout_vdot": latest_workout_vdot,
        "km_42d": round(km_42d, 1),
        "weekly_km_avg": round(wk_km, 1),
        "longest_km_42d": round(longest_km, 1),
        "long_runs_16k_42d": long_runs_16k,
        "long_runs_25k_42d": long_runs_25k,
        "elev_42d_m": round(elev_42d, 1),
        "avg_long_run_drift_pct": avg_drift_pct,
        "recovery_data_status": recovery_data_status,
        "endurance_retention_pct": retention_ratio,
        "endurance_retention_ratio": f"{retention_ratio}%" if retention_ratio else "均衡",
        "overall_score": overall_score,
        "runner_type_code": runner_type_code,
        "runner_type_label": runner_type_label,
        "canova_one_line_summary": one_line,
        "dimensions": dimensions,
    }


def predict_realistic_race_times(canova_matrix: Dict[str, Any]) -> Dict[str, Any]:
    """
    Predicts realistic 5K, 10K, Half Marathon, and Full Marathon times from effective_vdot
    by applying distance-specific endurance decay based on 6-week mileage, longest run,
    25km+ marathon specificity, late-run cardiac drift, and elite historical base relief.
    """
    def _fmt(secs: int) -> str:
        if not secs or secs <= 0:
            return "—"
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"

    eff_v = float(canova_matrix.get("effective_vdot") or 0.0)
    if eff_v <= 0:
        return {
            "five_k": "—",
            "ten_k": "—",
            "half_marathon": "—",
            "marathon": "—",
            "marathon_effective_vdot": None,
            "endurance_note": "暂无近期有效跑步数据，待完成 3km+ 跑步后生成预测。",
        }

    wk_km = float(canova_matrix.get("weekly_km_avg") or (float(canova_matrix.get("km_42d") or 0.0) / 6.0))
    longest_km = float(canova_matrix.get("longest_km_42d") or 0.0)
    lr25 = int(canova_matrix.get("long_runs_25k_42d") or 0)
    avg_drift = canova_matrix.get("avg_long_run_drift_pct")
    ret_pct = canova_matrix.get("endurance_retention_pct")
    is_rec_phase = bool(canova_matrix.get("is_recovery_phase"))
    peak_v = canova_matrix.get("peak_vdot")
    peak_end_v = float(canova_matrix.get("peak_endurance_vdot") or peak_v or 0.0)
    peak_fm_str = canova_matrix.get("peak_marathon_potential")

    has_fade_risk = bool((avg_drift is not None and float(avg_drift) > 7.5) or (ret_pct is not None and float(ret_pct) < 91.0))

    # Structural endurance relief for proven high-level runners in injury rehab / off-season:
    # avoids double-penalizing detraining when effective_vdot already reflects reduced current pace/HR.
    detraining_gap = max(0.0, peak_end_v - eff_v) if peak_end_v > eff_v else 0.0
    decay_relief = min(0.55, detraining_gap * 0.035) if detraining_gap >= 2.5 else 0.0

    # 5K: aerobic power index (minimal volume penalty unless <12km/wk)
    v_5k = max(18.0, eff_v - (0.4 if wk_km < 12.0 else 0.0))

    # 10K: light aerobic volume conversion
    dec_10k = 0.25 + ((min(1.1, (30.0 - wk_km) * 0.04) * (1.0 - decay_relief)) if wk_km < 30.0 else 0.0)
    v_10k = max(18.0, eff_v - dec_10k)

    # Half Marathon: requires ~50km/wk & 20km+ long run for full conversion
    hm_base_gap = 0.0 if (wk_km >= 65.0 and longest_km >= 22.0) else 0.55
    hm_vol_gap = min(2.2, (50.0 - wk_km) * 0.045) if wk_km < 50.0 else 0.0
    hm_lr_gap = min(2.2, (20.0 - longest_km) * 0.15) if longest_km < 20.0 else 0.0
    hm_fade_gap = 0.55 if has_fade_risk else 0.0
    hm_total_decay = hm_base_gap + (hm_vol_gap + hm_lr_gap) * (1.0 - decay_relief) + hm_fade_gap
    v_hm = max(17.0, eff_v - hm_total_decay)

    # Full Marathon: requires ~75km+/wk, 30km+ long run, and 25k+ specificity depth
    fm_base_gap = 0.0 if (wk_km >= 85.0 and longest_km >= 32.0 and lr25 >= 2) else 0.95
    fm_vol_gap = min(3.6, (75.0 - wk_km) * 0.052) if wk_km < 75.0 else 0.0
    fm_lr_gap = min(3.4, (30.0 - longest_km) * 0.17) if longest_km < 30.0 else 0.0
    fm_spec_gap = 0.55 if lr25 == 0 else (0.25 if lr25 == 1 else 0.0)
    fm_fade_gap = 0.85 if has_fade_risk else 0.0
    fm_total_decay = round(
        fm_base_gap + (fm_vol_gap + fm_lr_gap + fm_spec_gap) * (1.0 - decay_relief) + fm_fade_gap,
        1,
    )
    v_fm = max(16.0, round(eff_v - fm_total_decay, 1))

    fm_sec = vdot_to_race_time(v_fm, 42195.0)
    if is_rec_phase and peak_v:
        pot_clause = f"（满血全马实力 ~{peak_fm_str}）" if peak_fm_str and peak_fm_str != "—" else ""
        note = (
            f"🩹 恢复/休整期保护：主预测按当期安全状态 + 高水平底座托底推算（全马折算 -{fm_total_decay} VDOT）；"
            f"历史巅峰 VDOT {peak_v}{pot_clause}，待无痛跑量与长距离恢复后可逐步重返巅峰。"
        )
    elif fm_total_decay <= 1.2:
        note = f"当前周均 {round(wk_km, 1)}km、最长 {round(longest_km, 1)}km，耐力储备充足，半/全马转化折损较小（全马折算 -{fm_total_decay} VDOT）。"
    else:
        note = f"已结合近6周周均 {round(wk_km, 1)}km、最长 {round(longest_km, 1)}km 做耐力衰减修正（全马折算 -{fm_total_decay} VDOT）；提升周跑量与 30km 拉练可进一步兑现潜力。"

    return {
        "five_k": _fmt(vdot_to_race_time(v_5k, 5000.0)),
        "ten_k": _fmt(vdot_to_race_time(v_10k, 10000.0)),
        "half_marathon": _fmt(vdot_to_race_time(v_hm, 21097.5)),
        "marathon": _fmt(fm_sec),
        "marathon_seconds": fm_sec,
        "marathon_effective_vdot": v_fm,
        "marathon_decay_vdot": fm_total_decay,
        "is_recovery_phase": is_rec_phase,
        "peak_vdot": peak_v,
        "peak_marathon": peak_fm_str,
        "endurance_note": note,
    }




