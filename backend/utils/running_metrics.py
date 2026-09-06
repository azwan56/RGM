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

def format_duration(seconds: Optional[int]) -> str:
    """Formats seconds into HH:MM:SS or MM:SS."""
    if not seconds or seconds <= 0:
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

    for r in (races or []):
        r_dict = dict(r)
        date_str = str(r_dict.get("race_date") or "")[:10]
        try:
            r_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            days_left = (r_date - today).days
            if days_left >= 0:
                r_dict["parsed_date"] = r_date
                r_dict["days_left"] = days_left
                r_dict["race_date_clean"] = date_str
                upcoming.append(r_dict)
        except Exception:
            continue

    upcoming.sort(key=lambda x: x["parsed_date"])

    if not upcoming:
        return {
            "total_upcoming": 0,
            "races": [],
            "conflicts": [],
            "pairings": [],
            "cross_discipline": [],
            "macrocycle_summary": "当前暂未录入未来比赛计划，训练以建立稳态基础有氧与力量基线为主。"
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
        "races": serializable_races,
        "conflicts": conflicts,
        "pairings": pairings,
        "cross_discipline": cross_discipline,
        "macrocycle_summary": " · ".join(summary_parts) if summary_parts else "按赛历时间节点逐步推进专项周期化训练"
    }


