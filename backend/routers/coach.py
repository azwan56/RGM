from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import json
from datetime import datetime, date, timedelta
from db import supabase_admin
from utils.llm import llm_client
from utils.local_store import LocalStore, DB_PATH, sqlite3
from utils.running_metrics import (
    get_race_specific_zones,
    get_age_from_dob,
    format_duration,
    calculate_vdot,
    analyze_multi_race_calendar
)

logger = logging.getLogger("router_coach")
router = APIRouter()

class CoachAnalysisRequest(BaseModel):
    uid: str
    target_race: Optional[str] = None
    target_time: Optional[str] = None
    race_type: Optional[str] = None  # "trail", "marathon", "half", "10k", "5k"
    elevation_gain: Optional[float] = None


def resolve_athlete_race_context(eff_uid: str) -> Dict[str, Any]:
    """
    Intelligently resolves athlete's multi-race reality:
    - Filters out completed races and past races
    - Identifies nearest upcoming race (next_race)
    - Identifies season A-goal race (goal_race)
    - Distinguishes past completed achievements (e.g. Wugongshan) from upcoming targets
    - Determines athlete's primary discipline (trail/ultra vs road/marathon)
    """
    raw_races = LocalStore.get_race_plans(eff_uid) or []
    today = LocalStore.get_beijing_today()
    upcoming = []
    completed = []

    for r in raw_races:
        r_dict = dict(r)
        is_comp = (r_dict.get("status") == "completed" or bool(r_dict.get("finish_time")))
        date_str = str(r_dict.get("race_date") or "")[:10]
        try:
            r_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if not is_comp and r_date >= today:
                days_left = (r_date - today).days
                upcoming.append({**r_dict, "date_obj": r_date, "days_left": days_left, "days_until": days_left, "race_date_clean": date_str})
            else:
                completed.append({**r_dict, "date_obj": r_date, "race_date_clean": date_str})
        except Exception:
            if is_comp:
                completed.append(r_dict)

    upcoming.sort(key=lambda x: x["date_obj"])
    completed.sort(key=lambda x: x.get("date_obj") or today, reverse=True)

    next_race = upcoming[0] if upcoming else None
    a_races = [r for r in upcoming if str(r.get("priority") or "").upper() in ("1", "A")]
    goal_race = a_races[0] if a_races else next_race

    # Primary discipline determination
    target_race_obj = goal_race or next_race or (completed[0] if completed else None)
    is_trail = False
    if target_race_obj:
        r_type = str(target_race_obj.get("race_type") or "").lower()
        r_name = str(target_race_obj.get("name") or "").lower()
        is_trail = ("trail" in r_type or "越野" in r_name or "50k" in r_name or "100k" in r_name or "160" in r_name)
    elif upcoming:
        is_trail = any("trail" in str(r.get("race_type", "")).lower() or "越野" in str(r.get("name", "")).lower() for r in upcoming)

    return {
        "upcoming": upcoming,
        "completed": completed,
        "next_race": next_race,
        "goal_race": goal_race,
        "is_trail": is_trail,
        "target_discipline": "越野超马 / 山地耐力赛 (Trail & Ultra)" if is_trail else "公路马拉松 / 路跑 (Road Marathon)"
    }


CANOVA_SYSTEM_PROMPT = """你是由 Renato Canova (雷纳托·卡诺瓦) 耐力哲学驱动的专业教练，名为「Canova教练」。
Canova 哲学的核心准则：
1. 【专项性 (Specificity) 是王道】：
   - 全程马拉松：所有训练最终必须向 100% 马拉松配速 (MP) 和超长距离糖原耐受收敛。
   - 半程马拉松：核心围绕乳酸门槛 (LT2) 巡航速度与 95%~102% HMP 稳态延伸。
   - 5K / 10K：以最大摄氧量 (VO2max)、乳酸耐受力 (Lactic Capacity) 与高配速专项间歇为核心。
   - 越野跑 / 超马 (Trail & Ultra 如武功山 50K)：专项性绝不仅是平路配速，而是【山地心率储备 (%HRR) 控制】、【累计爬升 (D+) 垂直耐力】、【下坡大腿股四头肌离心抗撕裂耐受】、【时间负荷 (Time on Feet)】以及【每小时 60~90g 碳水化合物补给演练】。
2. 【周期化推进 (Periodization)】：基础期 (Fundamental) -> 专项准备期 (Special) -> 专项期 (Specific) -> 赛前调整 (Taper)。
3. 【生理年龄与机能恢复因人而异】：
   - 青年跑者 (<35岁)：大课恢复周期约 48 小时，可耐受高密度专项负荷。
   - 中年跑者 (35~49岁)：恢复周期需 48~72 小时，强调筋膜维护与关节保护。
   - 大师组跑者 (≥50岁)：恢复周期需 72~96 小时，坚决避免过密大课，强调抗阻力量防止肌肉流失 (Sarcopenia)。
4. 【状态平衡指数 (TSB / Form) 动态量化驱动】：
   - 若 TSB < -35 (高度疲劳/伤病高危)，必须强制削减强度，安排主动恢复或休整，严禁盲目执行杀手级课表。
   - 若 TSB 在 -10 ~ -30，处于最佳负荷吸收区，可按部就班推进专项课。
   - 若 TSB > +10，处于减量就绪巅峰期，重点激活神经兴奋性。
5. 【杜绝无效垃圾跑量】：坚决反对既不够慢又不够快的“中间垃圾配速”，轻松跑必须绝对低心率，专项课必须绝对保质量。
6. 【多赛事战略统筹与 A/B/C 梯队分级 (Multi-Race Periodization)】：
   - A 标 (Goal Race / 突破之战)：全赛季最高优先级目标，赛前严格执行 14~21 天专项减量 (Tapering)，追求体能峰值 (Peak CTL & Positive TSB)。
   - B 标 (Tune-up Test / 以赛代练)：距离 A 标 3~6 周的实战测试（如全马前 4 周的半马），以 98%~100% 目标配速巡航验证乳酸门槛与补给，赛前仅需减量 3 天，赛后 4~5 天低心率排酸。
   - C 标 (Training Run / 模拟拉练)：完全作为周末长距离有氧耐力跑 (LSD) 替代课，严禁拼尽全力，赛前无减量，赛后无需特殊休息。
   - 严禁赛程过密：若两场全马或百公里越野间隔 < 21 天，必须强制将后一场降格为 C 标慢跑完赛，坚决防止应力性骨折与中枢神经过度消耗。
   - 跨项转换（路跑与越野）：路跑转越野需在赛前 4~8 周加入手杖爬升 (D+) 与下坡股四头肌离心抗阻；越野转路跑必须在赛前 4 周回归平路维持步频刚性与跑步经济性。
7. 【融合赛事情报深度定制 (Race Intelligence Integration)】：
   - 若提供越野赛事情报（累计爬升 D+、下降 D-、最高海拔、地形路况、气候带、关门时间）：必须结合这些客观数据设计爬升垂直耐力课、高海拔心率控制、抗风保暖与强制装备演练建议；
   - 若提供路跑赛事情报（赛事等级、赛道起伏/特点、历史气温与湿度、参赛规模）：必须在关键建议和配速策略中，针对应对赛道坡度、防拥堵起跑节奏、高温高湿下的心率漂移防范与补水降温策略给出针对性方案。
8. 【针对不同水平队员的差异化施教话术规范 (Differentiated Athlete Coaching & Tone)】：
   - 【新手 / 入门级队员 (Novice / Beginner)】：
     * 话术基调：必须以鼓励为主，饱含热情、耐心肯定与温暖引导，多用正向激励（如“每一步都在重塑更好的自己”、“跑得慢才能跑得长”），坚决杜绝生硬苛责或生僻术语轰炸。
     * 理论结合：必须自然结合经典基础耐力训练理论深入浅出地指导：
       1) 80/20 极化训练原则（80%的时间保持轻松低心率有氧跑，夯实心肺有氧耐力与脂肪供能效率，绝不可天天全力冲刺）；
       2) 组织适应滞后律（心肺耐力几周就能提高，但肌腱骨骼重塑需要数月，告诫切忌盲目急躁堆量防伤病）；
       3) 跑姿与呼吸（建议 170~180 步频小步快频落地、深层腹式呼吸减轻下肢冲击）；
       4) 超量恢复原理（体能是在深度睡眠与休息中增长，疲劳时勇于减量休整）。
   - 【精英级 / 高水平队员 (Advanced / Elite)】：
     * 话术基调：言简意赅，直达重点！杜绝多余废话、冗长寒暄或泛泛而谈的常识性鸡汤。
     * 专业深度：直击 Canova 核心教条与边际增益 (Marginal Gains)：
       1) 100% 马拉松专项配速收敛 (Specific Pace Extension) 与末段抗糖原耗竭能力；
       2) 乳酸门槛 (LT2) 巡航动力学与间歇漂浮跑 (Float Recoveries) 的乳酸再利用清除效率；
       3) 比赛燃料代谢实战演练（60~90g/h 高碳水与电解质水合耐受）；
       4) 减量期 (Taper) 中枢神经兴奋度激发与配速精准切片执行。
   - 【进阶队员 (Intermediate)】：专业严谨，鼓励与技术指导并重，兼顾混氧门槛与周期化推进。
9. 【大师组队员隐私与尊严保护铁律 (Masters Privacy Protection)】：
   - 对于大师组队员（40+/50+ 资深跑者），在生成的分析、建议、课表和总结中，【严禁直接提及跑者的具体周岁、出生年份或任何具体年龄数字】（例如绝不可说“您已52岁”、“跑者53岁”等具体年龄隐私）。
   - 必须统一使用尊称“大师组跑者 / 资深大师跑者 / 经验丰富的资深队员”。
   - 重点从生理恢复规律层面给予科学关怀（保留 72~96 小时超量恢复窗口、增加抗阻力量防肌肉流失、监测晨起 HRV 与静息心率）。

请根据跑者真实的生理特征、近期打卡、健康睡眠、负荷平衡指数 (CTL/ATL/TSB)、目标赛事以及多赛事赛历统筹，直接以中文标准 JSON 格式输出深度个性化训练诊断报告：
{
  "summary": "一句话核心战略评价（结合跑者当前体能阶段与目标赛事）",
  "fitness_status": "体能与近期负荷诊断（深度剖析跑量、配速、心率、TSB状态与身体疲劳程度）",
  "periodization_phase": "专项期 (Specific Period) / 专项准备期 (Special) / 基础期 (Fundamental) / 减量调整期 (Taper)",
  "key_suggestions": [
    "针对性战术/训练建议 1 (结合赛事类型与跑者特点)",
    "针对性战术/训练建议 2 (结合疲劳负荷与年龄恢复)",
    "针对性战术/训练建议 3 (动作经济性/力量/补给)"
  ],
  "focus_workout_of_the_week": "本周最核心的关键专项课设计（必须高度匹配目标赛事类型，写明热身、主课间歇/配速/心率、冷身与执行注意事项）",
  "recovery_advice": "个性化恢复指导（针对当前睡眠评分、HRV、TSB 疲劳与跑者年龄恢复特点）",
  "multi_race_strategy": {
    "macro_cycle_overview": "宏观大周期战略统筹阐述（如何协调赛历中多场赛事的体能高峰与先后次序）",
    "race_timeline_advice": [
      {
        "race_name": "赛事名称",
        "tier": "A / B / C",
        "tactical_role": "核心突破 / 以赛代练 / 模拟拉练",
        "pacing_strategy": "针对该场赛事的配速/心率与战术执行策略",
        "taper_recovery_rule": "赛前减量建议与赛后超量恢复周期"
      }
    ],
    "conflict_resolution": "赛程冲突化解或跨项转换战术规避建议（若无冲突则给予宏观周期肯定）"
  }
}
"""

def parse_time_str(t_str: Optional[str]) -> Optional[int]:
    """Parses HH:MM:SS or MM:SS to total seconds."""
    if not t_str:
        return None
    try:
        parts = [int(p) for p in str(t_str).strip().split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
    except Exception:
        return None
    return None

def resolve_race_category(
    race_name: str,
    race_type: Optional[str] = None,
    target_time_seconds: Optional[int] = None
) -> tuple[str, str]:
    """
    Intelligently resolves (race_key, race_display_name).
    Prioritizes explicit naming in race_name, cross-validates with race_type and target_time.
    """
    r_name = (race_name or "").strip().lower()
    r_type = (race_type or "").strip().lower()

    # 1. Trail / Ultra detection (keywords in name take top priority)
    trail_keywords = ["越野", "trail", "ultra", "50k", "100k", "160", "武功山", "崇礼", "柴古", "utmb", "江南百英里", "四姑娘山", "高黎贡"]
    if any(k in r_name for k in trail_keywords):
        return "trail", "越野超马 / 山地耐力赛 (Trail & Ultra)"

    # 2. Half marathon explicit check in race_name
    half_keywords = ["半马", "半程", "half"]
    is_name_half = any(k in r_name for k in half_keywords)

    # 3. Full marathon explicit check in race_name
    # Note: "上海马拉松", "北京马拉松", "全马", "全程马拉松" contain "马拉松" but NOT "半马"/"半程"
    is_name_marathon = (any(k in r_name for k in ["全马", "全程", "马拉松", "marathon"]) and not is_name_half)

    if is_name_half:
        return "half", "半程马拉松 (Half Marathon)"
    if is_name_marathon:
        return "marathon", "全程马拉松 (Full Marathon)"

    # 4. 10K / 5K check in race_name
    if any(k in r_name for k in ["10k", "10公里", "十公里"]):
        return "10k", "10公里场地/路跑 (10K Road/Track)"
    if any(k in r_name for k in ["5k", "5公里", "五公里"]):
        return "5k", "5公里场地/路跑 (5K Road/Track)"

    # 5. If race_name doesn't explicitly declare distance, inspect race_type with target_time cross-validation
    if any(k in r_type for k in ["trail", "越野", "ultra"]):
        return "trail", "越野超马 / 山地耐力赛 (Trail & Ultra)"

    if any(k in r_type for k in ["half", "半"]):
        # Sanity check: If target_time is > 2h30m (9000s) and target_time/21.0975 > 420 (slower than 7:00/km),
        # but target_time/42.195 is between 200 and 450 (3:20 - 7:30/km): it was almost certainly a full marathon!
        if target_time_seconds and target_time_seconds >= 9000:
            half_pace = target_time_seconds / 21.0975
            full_pace = target_time_seconds / 42.195
            if half_pace > 420 and 200 <= full_pace <= 450:
                return "marathon", "全程马拉松 (Full Marathon)"
        return "half", "半程马拉松 (Half Marathon)"

    if any(k in r_type for k in ["10k", "10"]):
        return "10k", "10公里场地/路跑 (10K Road/Track)"
    if any(k in r_type for k in ["5k", "5"]):
        return "5k", "5公里场地/路跑 (5K Road/Track)"

    return "marathon", "全程马拉松 (Full Marathon)"


def resolve_runner_tier(profile: Dict[str, Any], ctl: float = 0.0) -> tuple[str, str]:
    """
    Categorizes runner into 'beginner', 'elite', or 'intermediate' and returns detailed coaching instructions.
    """
    def _parse_pb(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v) if v > 0 else None
        if isinstance(v, str):
            p = v.strip().split(":")
            try:
                if len(p) == 3:
                    return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
                if len(p) == 2:
                    return int(p[0]) * 60 + float(p[1])
                return float(v)
            except Exception:
                return None
        return None

    m_pb = _parse_pb(profile.get("marathon_pb") or profile.get("marathon_pb_seconds"))
    h_pb = _parse_pb(profile.get("half_pb") or profile.get("half_marathon_pb") or profile.get("half_pb_seconds"))
    ten_pb = _parse_pb(profile.get("ten_k_pb") or profile.get("ten_pb_seconds"))
    raw_years = profile.get("years_running") or 1
    try:
        years = float(raw_years)
    except Exception:
        years = 1.0

    # 1. Elite / High Level Athlete
    is_elite = False
    if m_pb and m_pb <= (3 * 3600 + 15 * 60):  # Sub 3:15
        is_elite = True
    elif h_pb and h_pb <= (88 * 60):  # Sub 1:28
        is_elite = True
    elif ten_pb and ten_pb <= (39 * 60):  # Sub 39m
        is_elite = True
    elif ctl >= 65 and years >= 3:
        is_elite = True

    if is_elite:
        return "elite", (
            "【高水平/精英级跑者 (Elite Athlete)】\n"
            "话术要求：言简意赅，直达重点！杜绝多余废话、冗长寒暄或泛泛常识性鸡汤。直接直击 Canova 核心教条与边际增益 (Marginal Gains)："
            "100% 马拉松专项配速收敛 (Specific Pace Extension)、乳酸门槛 (LT2) 动力学、间歇漂浮跑 (Float) 质量、比赛燃料代谢 (60-90g/h 补碳) 及减量期精准神经激活。"
        )

    # 2. Novice / Beginner Runner
    is_beginner = False
    if years <= 1:
        is_beginner = True
    elif not m_pb and not h_pb and ctl < 30:
        is_beginner = True
    elif m_pb and m_pb > (4 * 3600 + 15 * 60):  # > 4h15
        is_beginner = True
    elif h_pb and h_pb > (115 * 60):  # > 1h55
        is_beginner = True
    elif ten_pb and ten_pb > (56 * 60):  # > 56m
        is_beginner = True
    elif ctl < 25:
        is_beginner = True

    if is_beginner:
        return "beginner", (
            "【新人/入门级跑者 (Beginner / Novice)】\n"
            "话术要求：以鼓励为主，饱含热情、耐心肯定与温暖引导，多用正向激励（如“每一步都在重塑更好的自己”、“跑得慢才能跑得长”），严禁生硬苛责。"
            "必须自然结合经典基础耐力训练理论通俗讲解：\n"
            "1) 80/20 极化训练原则（80%时间保持轻松低心率有氧跑，夯实心肺有氧耐力与脂肪供能效率，绝不可天天全力冲刺）；\n"
            "2) 组织适应滞后律（心肺耐力提升较快，但肌腱骨骼重塑需要数月，告诫切忌盲目急躁堆量防伤病）；\n"
            "3) 步频 170~180 与腹式呼吸减轻关节冲击；\n"
            "4) 睡眠与超量恢复原理（体能是在深度睡眠与休息中增长，疲劳时勇于减量休整）。"
        )

    # 3. Intermediate Runner
    return "intermediate", (
        "【进阶跑者 (Intermediate Runner)】\n"
        "话术要求：专业严谨，鼓励与技术指导并重，兼顾混氧门槛巡航 (LT2) 与有氧专项耐力稳步进阶。"
    )


def generate_fallback_multi_race_strategy(multi_analysis: Dict[str, Any], target_race: str, race_category: str) -> Dict[str, Any]:
    """Generates Renato Canova periodization strategy when LLM output lacks multi_race_strategy."""
    races = multi_analysis.get("races") or []
    if not races:
        return {
            "macro_cycle_overview": f"当前赛历以主目标【{target_race}】为单核推进。依照 Renato Canova 大周期推进律，建议在赛前 4~6 周安排一场 B 标测试赛（如半马或 10K），用以实战校验乳酸门槛平台与补给反应。",
            "race_timeline_advice": [
                {
                    "race_name": target_race,
                    "tier": "A",
                    "tactical_role": "A 标核心目标 (Goal Race)",
                    "days_left": 60,
                    "pacing_strategy": "赛前 14~21 天启动专项减量收敛，比赛日严格执行 100% 专项配速，前程克制，后程凭借糖原节约能力平稳巡航。",
                    "taper_recovery_rule": "赛前 3 周削减跑量 20%，赛前 2 周削减 40%，赛前 1 周仅保留 20-30 分钟慢跑与短冲刺激；赛后执行 14~21 天超量修复。"
                }
            ],
            "conflict_resolution": "单赛事备战周期结构清晰，无赛程重叠冲突，全力聚焦核心专项课质量。"
        }

    timeline_advice = []
    for r in races:
        tier = r.get("tier", "B")
        r_name = r.get("name", "未命名赛事")
        days_left = r.get("days_left", 0)

        if tier == "A":
            pacing = "追求巅峰突破。前程严格压制心率在乳酸门槛 (LT2) 以内，后半程利用稳态代谢储备逐步加速收敛。"
            taper = "赛前 14~21 天启动渐进减量（削减 40%~60% 容量但保持配速神经张力）；赛后强制安排 14~21 天深层组织修复。"
            role = "A 标核心突破 (Goal Race)"
        elif tier == "B":
            pacing = "以 98%~100% 专项配速巡航实战，核心检验乳酸门槛平台、测试补给策略与鞋服装备，终点前切忌无谓拼尽全力导致过度疲劳。"
            taper = "赛前仅需减量 3~4 天保持肌肉弹性；赛后 4~5 天低心率慢跑排酸后即可恢复专项课表。"
            role = "B 标以赛代练 (Tune-up Test)"
        else:
            pacing = "严格作为长距离基础有氧 (LSD) 训练课，心率严格压制在最大心率 75% 以下，严禁被赛道人群节奏带偏。"
            taper = "赛前无需减量，当作普通训练周末；赛后无需深度休息，次日慢跑恢复即可。"
            role = "C 标模拟拉练 (Training Run)"

        timeline_advice.append({
            "id": r.get("id") or r_name,
            "race_name": r_name,
            "tier": tier,
            "tactical_role": role,
            "days_left": days_left,
            "pacing_strategy": pacing,
            "taper_recovery_rule": taper
        })

    conflicts = multi_analysis.get("conflicts") or []
    pairings = multi_analysis.get("pairings") or []
    cross = multi_analysis.get("cross_discipline") or []

    conflict_texts = []
    for c in conflicts:
        conflict_texts.append(c["warning"])
    for p in pairings:
        conflict_texts.append(p["strategy"])
    for x in cross:
        conflict_texts.append(x["transition_tip"])

    if not conflict_texts:
        conflict_texts.append("各赛事之间时间间隔分布合理，符合 Canova 周期化推进规律，无严重疲劳冲突。")

    return {
        "macro_cycle_overview": multi_analysis.get("macrocycle_summary", "多赛事宏观统筹，科学划分 A/B/C 梯队与疲劳释放节奏。"),
        "race_timeline_advice": timeline_advice,
        "conflict_resolution": "\n\n".join(conflict_texts)
    }


class CoachRacePriorityRequest(BaseModel):
    uid: str
    race_id: Optional[str] = None
    race_identifier: Optional[str] = None
    priority: Any  # "A", "B", "C" or 1, 2, 3
    target_race: Optional[str] = None


@router.post("/race-priority")
def update_coach_race_priority(req: CoachRacePriorityRequest):
    """
    Updates the priority (A/B/C) of a race for the user,
    re-analyzes the multi-race calendar, and immediately updates the cached coach report.
    """
    eff_uid = req.uid
    race_key = req.race_id or req.race_identifier or ""
    raw_pri = str(req.priority).upper()
    pri_int = 1 if raw_pri in ["A", "1"] else (2 if raw_pri in ["B", "2"] else 3)
    tier_label = "A 标 (核心突破)" if pri_int == 1 else ("B 标 (以赛代练)" if pri_int == 2 else "C 标 (模拟拉练)")

    # 1. Update in local store
    LocalStore.update_race_plan_priority(eff_uid, race_key, pri_int)

    # 2. Get fresh races & re-analyze
    races = LocalStore.get_race_plans(eff_uid)
    multi_race_analysis = analyze_multi_race_calendar(races)

    # 3. Update cached report if present
    report = LocalStore.get_coach_report(eff_uid) or {}
    target_race = req.target_race or report.get("athlete_snapshot", {}).get("target_race", "目标赛事")
    race_category = report.get("athlete_snapshot", {}).get("race_category", "marathon")

    multi_race_strategy = generate_fallback_multi_race_strategy(multi_race_analysis, target_race, race_category)
    report["multi_race_analysis"] = multi_race_analysis
    report["multi_race_strategy"] = multi_race_strategy
    LocalStore.save_coach_report(eff_uid, report)

    return {
        "success": True,
        "message": f"已将赛事优先级调整为 {tier_label}",
        "races": races,
        "multi_race_analysis": multi_race_analysis,
        "multi_race_strategy": multi_race_strategy
    }


class CoachChatRequest(BaseModel):
    message: str
    uid: Optional[str] = None
    user_id: Optional[str] = None
    body_reaction_tag: Optional[str] = None
    rpe: Optional[int] = None
    history: Optional[List[Dict[str, str]]] = None


def _build_athlete_coach_dialog_context(eff_uid: str) -> Dict[str, Any]:
    """
    Aggregates the 3 core pillars for the interactive Coach Dialog:
    1. 训练情况 (Recent activities, 7d/30d mileage, CTL/ATL/TSB, VDOT)
    2. 训练计划 (Active periodized training plan, current week progress, today's scheduled workout)
    3. 身体反应 (Watch HRV/RHR/Sleep/BodyBattery + Plan RPE, runner self-feel notes, injury reports)
    """
    canonical_uid = LocalStore.resolve_user_id(eff_uid)
    user_profile = LocalStore.get_profile(canonical_uid) or {}
    runner_name = user_profile.get("display_name") or "跑者"
    load_metrics = LocalStore.get_training_load(canonical_uid, days=90) or {}
    ctl = round(float(load_metrics.get("ctl") or 0.0), 1)
    atl = round(float(load_metrics.get("atl") or 0.0), 1)
    tsb = round(float(load_metrics.get("tsb") or 0.0), 1)
    tsb_sign = f"+{tsb}" if tsb > 0 else f"{tsb}"
    if tsb > 15:
        tsb_status = "巅峰就绪"
    elif tsb >= -10:
        tsb_status = "平衡稳健"
    elif tsb >= -30:
        tsb_status = "训练中 (良好吸收)"
    elif tsb >= -45:
        tsb_status = "疲劳累积"
    else:
        tsb_status = "过度负荷 / 伤病高危"

    # 1. Recent activities & mileage
    recent_acts = LocalStore.get_recent_activities(canonical_uid, limit=20) or []
    today_dt = LocalStore.get_beijing_today()
    cutoff_7d = (today_dt - timedelta(days=7)).isoformat()
    cutoff_30d = (today_dt - timedelta(days=30)).isoformat()

    runs_7d = []
    km_7d = 0.0
    km_30d = 0.0
    formatted_recent = []
    for a in recent_acts:
        st = str(a.get("start_time") or "")[:10]
        dist_km = round(float(a.get("distance_meters") or 0.0) / 1000.0, 2)
        if st >= cutoff_30d:
            km_30d += dist_km
        if st >= cutoff_7d:
            km_7d += dist_km
            runs_7d.append(a)
        if len(formatted_recent) < 5:
            formatted_recent.append({
                "date": st,
                "name": a.get("name") or "跑步训练",
                "distance_km": dist_km,
                "avg_pace": a.get("avg_pace_str") or "—",
                "avg_hr": a.get("average_heartrate"),
                "elevation_gain_m": round(float(a.get("elevation_gain_meters") or 0.0), 0),
                "trimp": round(float(a.get("trimp") or 0.0), 1),
            })

    km_7d = round(km_7d, 1)
    km_30d = round(km_30d, 1)
    latest_run = formatted_recent[0] if formatted_recent else None

    # 2. Active training plan & today's workout
    plan = LocalStore.get_user_active_training_plan(canonical_uid)
    if not plan:
        plan = LocalStore.get_user_draft_training_plan(canonical_uid, reconcile=True)
    today_workout = LocalStore.get_today_workout(canonical_uid)

    plan_status: Dict[str, Any] = {
        "has_plan": False,
        "plan_id": None,
        "plan_title": None,
        "target_race": None,
        "current_week_index": 1,
        "total_weeks": 0,
        "week_title": None,
        "phase": None,
        "key_focus": None,
        "planned_weekly_km": 0.0,
        "actual_weekly_km": 0.0,
        "completion_pct": 0,
        "strength_count": 0,
        "coach_review_note": None,
        "today_workout": today_workout,
        "week_days": [],
    }

    subjective_rpe_items: List[Dict[str, Any]] = []
    injury_note = ""
    has_injury_alert = False
    athlete_weekly_summary = ""
    travel_or_leave_note = ""
    avg_rpe = None
    max_rpe = None
    avg_rec_pct = None

    if plan and isinstance(plan.get("schedule_data"), dict):
        sched = plan["schedule_data"]
        weeks = sched.get("weeks") or []
        cur_wk_idx = int(plan.get("current_week_index") or 1)
        active_wk = next((w for w in weeks if int(w.get("week_index") or 0) == cur_wk_idx), weeks[0] if weeks else None)
        if active_wk:
            ws = active_wk.get("week_summary") or {}
            days_list = active_wk.get("days") or []
            # If today_workout wasn't matched by exact date, match by today's weekday
            if not today_workout and days_list:
                weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                today_wd = weekday_map[today_dt.weekday()]
                matched_d = next((d for d in days_list if str(d.get("day_of_week") or "") == today_wd), None)
                if matched_d:
                    today_workout = {
                        "plan_id": plan.get("id"),
                        "plan_title": plan.get("title"),
                        "week_index": active_wk.get("week_index"),
                        "week_title": active_wk.get("week_title"),
                        "date": matched_d.get("date") or today_dt.isoformat(),
                        "day_of_week": matched_d.get("day_of_week") or today_wd,
                        "workout_type": matched_d.get("workout_type") or "easy_run",
                        "title": matched_d.get("title") or "训练课目",
                        "distance_km": float(matched_d.get("distance_km") or 0.0),
                        "target_pace": matched_d.get("target_pace"),
                        "target_hr_zone": matched_d.get("target_hr_zone"),
                        "description": matched_d.get("description"),
                        "completed": bool(matched_d.get("completed")),
                        "actual_distance_km": matched_d.get("actual_distance_km"),
                        "actual_pace": matched_d.get("actual_pace"),
                    }

            week_days_brief = []
            for d in days_list:
                rpe_v = d.get("rpe")
                feel_v = str(d.get("runner_feel_notes") or d.get("athlete_notes") or "").strip()
                if rpe_v is not None or feel_v:
                    subjective_rpe_items.append({
                        "day_of_week": d.get("day_of_week"),
                        "date": d.get("date"),
                        "title": d.get("title"),
                        "rpe": rpe_v,
                        "feel_note": feel_v,
                        "recovery_pct": d.get("recovery_pct"),
                    })
                week_days_brief.append({
                    "day_of_week": d.get("day_of_week"),
                    "date": d.get("date"),
                    "workout_type": d.get("workout_type"),
                    "title": d.get("title"),
                    "distance_km": float(d.get("distance_km") or 0.0),
                    "target_pace": d.get("target_pace"),
                    "completed": bool(d.get("completed")),
                    "actual_distance_km": d.get("actual_distance_km"),
                    "rpe": rpe_v,
                    "feel_note": feel_v,
                })

            injury_note = str(ws.get("injury_note") or "").strip()
            has_injury_alert = bool(ws.get("has_injury_alert"))
            athlete_weekly_summary = str(ws.get("athlete_weekly_summary") or "").strip()
            travel_or_leave_note = str(ws.get("travel_or_leave_note") or "").strip()
            avg_rpe = ws.get("avg_rpe")
            max_rpe = ws.get("max_rpe")
            avg_rec_pct = ws.get("avg_recovery_pct")

            plan_status = {
                "has_plan": True,
                "plan_id": plan.get("id"),
                "plan_title": plan.get("title") or "Canova 周期训练计划",
                "target_race": plan.get("target_race_name") or sched.get("target_race"),
                "current_week_index": int(active_wk.get("week_index") or cur_wk_idx),
                "total_weeks": len(weeks),
                "week_title": active_wk.get("week_title") or f"第 {active_wk.get('week_index', cur_wk_idx)} 周",
                "phase": active_wk.get("phase") or "专项训练期",
                "key_focus": active_wk.get("key_focus") or "",
                "planned_weekly_km": float(ws.get("planned_mileage_km") or active_wk.get("weekly_mileage_km") or 0.0),
                "actual_weekly_km": float(ws.get("actual_mileage_km") or active_wk.get("actual_mileage_km") or 0.0),
                "completion_pct": int(ws.get("completion_pct") or active_wk.get("compliance_rate") or 0),
                "strength_count": int(ws.get("strength_count") or 0),
                "coach_review_note": plan.get("coach_review_note") or sched.get("coach_review_note") or "",
                "today_workout": today_workout,
                "week_days": week_days_brief,
            }

    # 3. Body reactions (Watch physiological metrics + Plan subjective RPE/injury)
    health = LocalStore.get_latest_health(canonical_uid) or {}
    recovery_avail = LocalStore.assess_recovery_data_availability(
        canonical_uid, health_row=health, profile=user_profile, recent_acts=recent_acts
    )
    is_rec_ok = bool(recovery_avail.get("recovery_data_available"))
    hrv_val = health.get("hrv_last_night_avg") if is_rec_ok else None
    hrv_base = health.get("hrv_weekly_avg") if is_rec_ok else None
    sleep_sc = health.get("sleep_score") if is_rec_ok else None
    sleep_hr = health.get("sleep_duration_hours") if is_rec_ok else None
    rhr_val = health.get("resting_heart_rate") if is_rec_ok else None
    bb_val = health.get("body_battery_max") if is_rec_ok else None
    vo2_val = health.get("vo2_max") or user_profile.get("vo2max")

    watch_parts = []
    if hrv_val is not None:
        base_str = f"（7日基线 {int(round(float(hrv_base)))} ms）" if hrv_base else ""
        watch_parts.append(f"夜间 HRV {int(round(float(hrv_val)))} ms{base_str}")
    if rhr_val is not None:
        watch_parts.append(f"晨起静息心率 {int(round(float(rhr_val)))} bpm")
    if sleep_sc is not None:
        hr_str = f" ({sleep_hr}h)" if sleep_hr else ""
        watch_parts.append(f"睡眠评分 {int(round(float(sleep_sc)))}{hr_str}")
    if bb_val is not None:
        watch_parts.append(f"身体电量/恢复 {int(round(float(bb_val)))}%")

    watch_summary_line = " · ".join(watch_parts) if watch_parts else "暂未同步昨晚睡眠佩戴 HRV/静息心率数据"

    # Determine overall body reaction level
    reaction_level = "good"
    reaction_reasons = []
    if has_injury_alert:
        reaction_level = "warning"
        reaction_reasons.append(f"存在伤痛上报（{injury_note}）")
    if tsb < -35:
        reaction_level = "warning"
        reaction_reasons.append(f"急性疲劳偏高 (TSB {tsb_sign})")
    elif tsb < -18 and reaction_level == "good":
        reaction_level = "caution"
        reaction_reasons.append(f"处于负荷吸收期 (TSB {tsb_sign})")
    if max_rpe and max_rpe >= 8:
        if reaction_level == "good":
            reaction_level = "caution"
        reaction_reasons.append(f"近期单课最高主观体感 RPE {max_rpe}/10")
    if hrv_val and hrv_base and float(hrv_val) < float(hrv_base) * 0.85:
        if reaction_level == "good":
            reaction_level = "caution"
        reaction_reasons.append("晨起 HRV 低于 7 日基线")

    if reaction_level == "warning":
        reaction_badge = "🔴 伤痛/高疲劳预警 · 建议降阶减量恢复"
    elif reaction_level == "caution":
        reaction_badge = "🟡 存在一定疲劳反应 · 建议严控有氧心率"
    else:
        reaction_badge = "🟢 身体反应良好 · 适宜按计划执行课表"

    # 4. Synthesize proactive 3-dimensional coach feedback (训练情况 + 训练计划 + 身体反应)
    if latest_run:
        hr_seg = f"，平均心率 {latest_run['avg_hr']} bpm" if latest_run.get("avg_hr") else ""
        latest_run_text = f"最近一次打卡为 {latest_run['date']}「{latest_run['name']}」{latest_run['distance_km']} km（配速 {latest_run['avg_pace']}{hr_seg}）"
    else:
        latest_run_text = "近 7 天暂无同步跑步记录"

    if plan_status["has_plan"]:
        tw = plan_status["today_workout"]
        if tw:
            if tw.get("workout_type") == "rest" or float(tw.get("distance_km") or 0) <= 0:
                today_plan_text = f"今日（{tw.get('day_of_week') or '今日'}）课表安排为【{tw.get('title') or '跑休恢复'}】，重点进行主动排酸、筋膜放松与睡眠超量恢复。"
            else:
                done_tag = f"（已完成 {tw.get('actual_distance_km') or tw.get('distance_km')} km）" if tw.get("completed") else "（待执行）"
                pace_tag = f"，目标配速 {tw.get('target_pace')}" if tw.get("target_pace") and tw.get("target_pace") != "—" else ""
                hr_tag = f"，心率控制 {tw.get('target_hr_zone')}" if tw.get("target_hr_zone") else ""
                today_plan_text = f"今日（{tw.get('day_of_week') or '今日'}）课表为【{tw.get('title')}】{tw.get('distance_km')} km{done_tag}{pace_tag}{hr_tag}。"
        else:
            today_plan_text = f"当前处于《{plan_status['plan_title']}》第 {plan_status['current_week_index']} 周（{plan_status['phase']}）。"
        plan_progress_text = (
            f"当前执行《{plan_status['plan_title']}》第 {plan_status['current_week_index']}/{plan_status['total_weeks']} 周，"
            f"本周计划跑量 {plan_status['planned_weekly_km']} km，已执行 {plan_status['actual_weekly_km']} km（完成度 {plan_status['completion_pct']}%）。"
            f"{today_plan_text}"
        )
    else:
        plan_progress_text = "当前暂未激活周期训练课表，可在「训练」或「跑团教练」中一键生成或套用分组配速模版。"

    subj_parts = []
    if avg_rpe is not None:
        subj_parts.append(f"本周已填报平均主观体感 RPE {avg_rpe}/10")
    if subjective_rpe_items:
        last_item = subjective_rpe_items[-1]
        if last_item.get("feel_note"):
            subj_parts.append(f"{last_item.get('day_of_week') or '近期'}自评「{last_item['feel_note']}」")
    if has_injury_alert:
        subj_parts.append(f"⚠️ 伤痛报备：「{injury_note}」")
    elif athlete_weekly_summary:
        subj_parts.append(f"周小结：「{athlete_weekly_summary}」")
    subj_line = "；".join(subj_parts) if subj_parts else "本周暂未上报异常酸痛或高 RPE 疲劳反应"

    if reaction_level == "warning":
        action_advice = (
            "鉴于当前存在伤痛或高疲劳信号，教练建议今日严禁硬顶高强度间歇或节奏跑，"
            "将课表降阶为 Zone 1-2 低心率恢复慢跑（配速下调 20-30 秒/km）或直接改为完全跑休与泡沫轴松解。"
        )
    elif reaction_level == "caution":
        action_advice = (
            "身体正处于训练负荷吸收期，执行今日课表时请以【心率不漂移】为第一准则，"
            "热身延长至 15 分钟，轻松跑段严格压在有氧稳态区（Zone 2），跑后及时补充碳水与蛋白质。"
        )
    else:
        action_advice = (
            "当前心肺储备与身体恢复状态匹配良好，可按今日计划课表的目标配速与心率区间稳步执行；"
            "跑后欢迎在下方选择您的【今日身体反应】或直接向我提问，我会为您实时微调后续课表。"
        )

    proactive_feedback = (
        f"👋 **{runner_name}，我是您的 Canova 科学训练教练。已为您实时读取最新训练、课表与身体反应：**\n\n"
        f"📊 **1. 训练情况评估**：近 7 天累计完成 **{len(runs_7d)} 次 / {km_7d} km**（近 30 天 {km_30d} km），{latest_run_text}。"
        f"当前长期体能储备 **CTL {ctl}**、急性疲劳 **ATL {atl}**、状态平衡指数 **TSB {tsb_sign}（{tsb_status}）**。\n\n"
        f"📋 **2. 训练计划进度**：{plan_progress_text}\n\n"
        f"🫀 **3. 身体反应与专业反馈**：{watch_summary_line}；{subj_line}。\n"
        f"💡 **教练今日执行处方**：{action_advice}"
    )

    return {
        "runner_name": runner_name,
        "training_status": {
            "ctl": ctl,
            "atl": atl,
            "tsb": tsb,
            "tsb_sign": tsb_sign,
            "tsb_status": tsb_status,
            "vo2max": vo2_val,
            "recent_7d_runs": len(runs_7d),
            "recent_7d_km": km_7d,
            "recent_30d_km": km_30d,
            "latest_run": latest_run,
            "recent_activities": formatted_recent,
        },
        "plan_status": plan_status,
        "body_reaction": {
            "level": reaction_level,
            "badge_text": reaction_badge,
            "reasons": reaction_reasons,
            "watch_summary_line": watch_summary_line,
            "hrv": hrv_val,
            "hrv_baseline": hrv_base,
            "rhr": rhr_val,
            "sleep_score": sleep_sc,
            "sleep_hours": sleep_hr,
            "body_battery": bb_val,
            "avg_rpe": avg_rpe,
            "max_rpe": max_rpe,
            "avg_recovery_pct": avg_rec_pct,
            "subjective_rpe_items": subjective_rpe_items,
            "injury_note": injury_note,
            "has_injury_alert": has_injury_alert,
            "athlete_weekly_summary": athlete_weekly_summary,
            "travel_or_leave_note": travel_or_leave_note,
            "subjective_summary_line": subj_line,
        },
        "proactive_feedback": proactive_feedback,
    }


@router.get("/chat-context/{uid}")
def get_coach_chat_context_endpoint(uid: str):
    """
    Returns the athlete's real-time 3-pillar context (训练情况 + 训练计划 + 身体反应)
    and an instant proactive coach diagnosis briefing for the Web Coach Dialog.
    """
    ctx = _build_athlete_coach_dialog_context(uid)
    raw_model_id, model_display = _get_current_llm_model_display()
    return {
        "status": "ok",
        "model": raw_model_id,
        "model_display": model_display,
        **ctx,
    }


CANOVA_CHAT_SYSTEM_PROMPT = """你是一位以意大利传奇耐力训练大师 Renato Canova（雷纳托·卡诺瓦）专项训练哲学为核心方法论的 RGM AI 私人耐力与恢复教练（Canova 教练），正在与跑者一对一对话。

【身份与底层大模型信息】
- 底层大语言模型：当前由 {model_display} 驱动，并融合 RGM 运动生理与 Banister 负荷量化推理引擎。
- 教练简介：
  1. 以 Renato Canova 专项周期化训练哲学为核心（基础期 Fundamental -> 专项准备期 Special -> 专项期 Specific -> 赛前减量期 Taper），强调“专项性收敛 (Specificity)”与“杜绝无效垃圾跑量”；
  2. 融合 Banister 体能负荷动力学模型（长期体能 CTL、急性疲劳 ATL、状态平衡指数 TSB）与 Jack Daniels VDOT 跑力体系；
  3. 结合智能手表同步的 WHOOP 级生理恢复指标（夜间 HRV、静息心率 RHR、睡眠质量与睡眠债、日间 Strain 负荷），为路跑马拉松与山地越野跑者提供个性化每日训练处方、多赛事 A/B/C 梯队统筹与伤病预防指导。
- 当跑者询问“你是谁”、“你是什么模型”、“用什么大模型”或要求自我介绍时，必须明确告知当前使用的 LLM 模型（{model_display}）以及上述教练简介。

【方法论：专项性收敛】
训练负荷应逐步收敛到目标赛事的实际需求。
1. 越野 / 山地超马：不以平路配速为主要依据，改用心率储备区间 (%HRR)、累计爬升与快步走效率、下坡离心耐受、山地时长 (Time on Feet)、每小时 60~90g 碳水补给作为基准。
2. 公路马拉松 / 半马：围绕比赛配速 (MP)、乳酸阈 (LT2) 巡航与漂浮恢复间歇 (Float Recoveries)。
3. 临近比赛（≤14 天）时，训练建议应遵循赛前减量 (Taper) 原则；但只在与问题相关时提及，不要每次都把它放在开头。
4. 已完赛的比赛只是历史负荷参考，不能说成“正在备战”的目标。只使用用户消息中提供的赛事信息，不要自行编造赛事。

【回答方式：先识别问题类型，再决定开头】
- A. 身份与模型问答类（“你是谁 / 什么模型 / 自我介绍”）：明确回答当前使用的 LLM 大模型名称与版本，并清晰介绍教练的方法论体系与核心能力。
- B. 决策类（“合不合适 / 能不能跑 / 要不要 / 行不行”）：第一句直接给出你的判断（可行 / 需调整 / 不建议），并用一句话说明理由。
- C. 分析解读类（“分析我的负荷 / TSB / 状态 / 数据”）：第一句直接概括当前状态是什么（例如体能储备水平、疲劳程度、状态是否新鲜），不要用“合适 / 不合适”这类判决词开头，因为跑者并没有提出一个待批准的方案。
- D. 规划类（“这周末跑多长 / 怎么安排”）：第一句直接给出具体建议（距离 / 时长 / 强度）。
- E. 其他知识问答：直接回答问题本身。
无论哪类，都要紧扣跑者的原话，不要套用固定开场白，不要复述本说明中的措辞。

【内容要求】
1. 结合提供的 CTL（体能储备）、ATL（急性疲劳）、TSB（状态平衡）解释原因，数字必须与提供的数据一致。
2. 若跑者设想的课表不合理，给出可执行的替代方案（心率区间、时长 / 爬升、恢复方式）。
3. 只输出纯文本或 Markdown，不要输出 JSON。语气专业、简洁、有同理心，150~280 字。
"""


def _get_current_llm_model_display() -> tuple[str, str]:
    """Returns (raw_model_id, human_readable_model_display)."""
    raw_model = (getattr(llm_client, "model", None) or "qwen-max").strip()
    low = raw_model.lower()
    if "qwen-max" in low:
        return raw_model, f"阿里云通义千问旗舰大模型 Qwen-Max ({raw_model})"
    elif "qwen" in low:
        return raw_model, f"阿里云通义千问大模型 ({raw_model})"
    elif "deepseek" in low:
        return raw_model, f"DeepSeek 大语言模型 ({raw_model})"
    elif "gpt" in low:
        return raw_model, f"OpenAI 大语言模型 ({raw_model})"
    return raw_model, f"{raw_model}"


def _extract_user_question_and_context(raw_message: str) -> tuple[str, str]:
    """
    Separates optional leading '[跑者实时生理与WHOOP状态：...]' prefix injected by the iOS client
    from the athlete's actual question text so keyword/intent detection only inspects the question.
    """
    msg = (raw_message or "").strip()
    if msg.startswith("[") and "]" in msg:
        idx = msg.find("]")
        prefix = msg[1:idx].strip()
        question = msg[idx + 1:].strip()
        if question:
            return question, prefix
    return msg, ""


@router.post("/chat")
def coach_chat_endpoint(req: CoachChatRequest):
    """
    Answers athlete questions from the Renato Canova endurance philosophy perspective.
    """
    eff_uid = req.uid or req.user_id
    if not eff_uid:
        raise HTTPException(status_code=400, detail="请先登录后再咨询 AI 教练")
    user_profile = LocalStore.get_profile(eff_uid) or {}
    report = LocalStore.get_coach_report(eff_uid) or {}
    load_metrics = LocalStore.get_training_load(eff_uid, days=90)
    ctl = round(float(load_metrics.get("ctl") or 0.0), 1)
    atl = round(float(load_metrics.get("atl") or 0.0), 1)
    tsb = round(float(load_metrics.get("tsb") or 0.0), 1)
    tsb_sign = f"+{tsb}" if tsb > 0 else f"{tsb}"
    if tsb > 15:
        tsb_status = "巅峰就绪"
    elif tsb >= -10:
        tsb_status = "平衡稳健"
    elif tsb >= -30:
        tsb_status = "训练中 (良好吸收)"
    elif tsb >= -45:
        tsb_status = "疲劳累积"
    else:
        tsb_status = "过度负荷 / 伤病高危"

    race_ctx = resolve_athlete_race_context(eff_uid)
    next_r = race_ctx["next_race"]
    goal_r = race_ctx["goal_race"]
    comp_r = race_ctx["completed"]
    discipline = race_ctx["target_discipline"]

    race_desc_parts = []
    if next_r:
        taper_note = "，已进入赛前减量窗口" if next_r["days_left"] <= 14 else ""
        race_desc_parts.append(f"• 下一场待战赛事：{next_r['name']}（{next_r.get('race_type', '未知类型')}，{next_r['race_date_clean']}，距今 {next_r['days_left']} 天{taper_note}）")
    if goal_r and (not next_r or goal_r["name"] != next_r["name"]):
        race_desc_parts.append(f"• 年度主目标 (A 标)：{goal_r['name']}（{goal_r.get('race_type', '未知类型')}，{goal_r['race_date_clean']}，距今 {goal_r['days_left']} 天）")
    if comp_r:
        past_str = "、".join(f"{c['name']}（{c.get('race_date_clean','')}）" for c in comp_r[:2])
        race_desc_parts.append(f"• 已完赛（仅作历史参考，不是备战目标）：{past_str}")

    race_schedule_text = "\n".join(race_desc_parts) if race_desc_parts else "暂无登记的比赛"

    phase = report.get("periodization_phase")
    comp_names = [c["name"] for c in comp_r]
    stale_target = str(report.get("athlete_snapshot", {}).get("target_race", ""))
    if not phase or (stale_target and stale_target in comp_names):
        phase = "赛前减量调整期 (Taper)" if (next_r and next_r["days_left"] <= 14) else "专项期 (Specific Period)"

    clean_question, client_whoop_context = _extract_user_question_and_context(req.message)
    raw_model_id, model_display = _get_current_llm_model_display()
    q_lower = clean_question.lower()

    identity_keywords = [
        "你是谁", "您是谁", "你是哪位", "你叫什么", "什么模型", "哪个模型",
        "什么大模型", "用什么模型", "底层模型", "llm", "自我介绍",
        "介绍一下你自己", "介绍下你自己", "介绍一下你", "你是干什么的",
        "你的简介", "教练简介", "who are you", "what model"
    ]
    is_identity_query = any(k in q_lower for k in identity_keywords) or q_lower.strip("？?！!。., ") in ("你是", "模型", "介绍")

    if is_identity_query:
        reply = (
            f"👋 你好！我是 **RGM AI 耐力与恢复教练（Canova 教练）**。\n\n"
            f"🤖 **当前驱动的 LLM 模型**：\n"
            f"• **核心大模型**：**{model_display}**\n"
            f"• **协同量化引擎**：RGM 运动生理学推理引擎（融合 Banister CTL/ATL/TSB 负荷动力学、Jack Daniels VDOT 跑力模型与 WHOOP 级生理恢复算法）\n\n"
            f"🏃‍♂️ **教练简介与训练哲学**：\n"
            f"我以意大利传奇马拉松与耐力训练大师 **Renato Canova（雷纳托·卡诺瓦）** 的科学训练体系为核心灵魂，专注于为路跑与山地越野跑者提供一对一动态指导：\n"
            f"1. **Canova 专项周期化推进**：围绕您的目标赛事，按「基础期 → 专项准备期 → 专项期 → 赛前减量期 (Taper)」动态演进，强调比赛配速收敛与山地垂直耐力，坚决杜绝无效“垃圾跑量”；\n"
            f"2. **WHOOP 级全天候恢复监测**：实时追踪您手表同步的夜间 **HRV（心率变异性）**、**静息心率 (RHR)**、**睡眠质量/睡眠债** 与日间 **Strain 生理负荷**，在晨间主动为您定制当日恢复与训练处方；\n"
            f"3. **Banister 负荷与多赛事统筹**：量化监控您的体能储备（当前 CTL {ctl}）、急性疲劳（ATL {atl}）与状态平衡指数（TSB {tsb_sign}，{tsb_status}），统筹赛季 A/B/C 级赛事节奏，严防过度训练与运动损伤。"
        )
        return {"reply": reply, "model": raw_model_id, "status": "ok"}

    # Classify question intent so the opener matches what the athlete actually asked
    if any(k in q_lower for k in ["合适", "能不能", "可以吗", "要不要", "行不行", "跑不跑", "可不可以", "该不该"]):
        intent_hint = "决策类：跑者在询问某个方案是否可行，请第一句给出判断。"
    elif any(k in q_lower for k in ["分析", "解读", "负荷", "tsb", "ctl", "atl", "状态", "数据"]):
        intent_hint = "分析解读类：跑者没有提出待批准的方案，请第一句概括当前状态，不要以“合适/不合适”开头。"
    elif any(k in q_lower for k in ["安排", "计划", "多长", "多远", "怎么跑", "跑什么", "课表"]):
        intent_hint = "规划类：请第一句给出具体的距离/时长/强度建议。"
    else:
        intent_hint = "知识问答类：请直接回答问题本身。"

    runner_name = user_profile.get("display_name") or "跑者"
    years_running = user_profile.get("years_running")
    years_text = f"，跑龄 {years_running} 年" if years_running else ""

    health = LocalStore.get_latest_health(eff_uid) or {}
    recovery_avail = LocalStore.assess_recovery_data_availability(eff_uid, health_row=health, profile=user_profile)
    is_rec_ok = bool(recovery_avail.get("recovery_data_available"))
    hrv_val = health.get("hrv_last_night_avg") if is_rec_ok else None
    hrv_base = health.get("hrv_weekly_avg") if is_rec_ok else None
    sleep_sc = health.get("sleep_score") if is_rec_ok else None
    sleep_hr = health.get("sleep_duration_hours") if is_rec_ok else None
    rhr_val = health.get("resting_heart_rate") if is_rec_ok else None
    bb_val = health.get("body_battery_max") if is_rec_ok else None
    vo2_val = health.get("vo2_max") or user_profile.get("vo2max")

    health_parts = []
    if hrv_val is not None:
        base_str = f"（7日基线 {int(round(float(hrv_base)))} ms）" if hrv_base else ""
        health_parts.append(f"夜间平均 HRV {int(round(float(hrv_val)))} ms{base_str}")
    if sleep_sc is not None:
        hr_str = f"（睡眠时长 {sleep_hr} 小时）" if sleep_hr else ""
        health_parts.append(f"睡眠质量 {int(round(float(sleep_sc)))} 分{hr_str}")
    if rhr_val is not None:
        health_parts.append(f"静息心率 {int(round(float(rhr_val)))} bpm")
    if bb_val is not None:
        health_parts.append(f"身体电量 {int(round(float(bb_val)))}%")
    if vo2_val is not None:
        health_parts.append(f"最大摄氧量 VO2Max {vo2_val} ml/kg")
    if client_whoop_context:
        health_parts.append(client_whoop_context)
    if recovery_avail.get("night_wear_missing"):
        health_line = recovery_avail.get("user_warning") or "夜间未佩戴手表，缺失夜间 HRV、静息心率与睡眠恢复数据"
    else:
        health_line = "，".join(health_parts) if health_parts else "暂未同步夜间 HRV 与静息心率恢复数据"

    dialog_ctx = _build_athlete_coach_dialog_context(eff_uid)
    t_stat = dialog_ctx["training_status"]
    p_stat = dialog_ctx["plan_status"]
    b_react = dialog_ctx["body_reaction"]

    recent_runs_lines = []
    for r in (t_stat.get("recent_activities") or [])[:4]:
        hr_s = f"，心率 {r['avg_hr']} bpm" if r.get("avg_hr") else ""
        recent_runs_lines.append(f"  - {r['date']} {r['name']}：{r['distance_km']} km，配速 {r['avg_pace']}{hr_s}")
    recent_runs_block = "\n".join(recent_runs_lines) if recent_runs_lines else "  - 近 7 天暂无同步跑步记录"

    if p_stat.get("has_plan"):
        tw = p_stat.get("today_workout")
        if tw:
            tw_line = (
                f"今日课表（{tw.get('day_of_week') or '今日'}）：【{tw.get('title')}】"
                f" 计划 {tw.get('distance_km')} km，目标配速 {tw.get('target_pace') or '—'}，心率区间 {tw.get('target_hr_zone') or '—'}，"
                f"状态：{'已完成' if tw.get('completed') else '待执行'}。要求：{tw.get('description') or '按计划执行'}"
            )
        else:
            tw_line = "今日无特定课表条目"
        plan_block = (
            f"• 当前执行计划：《{p_stat['plan_title']}》第 {p_stat['current_week_index']}/{p_stat['total_weeks']} 周（{p_stat['phase']}）\n"
            f"• 本周计划跑量：{p_stat['planned_weekly_km']} km，已执行 {p_stat['actual_weekly_km']} km（完成度 {p_stat['completion_pct']}%，力量训练 {p_stat['strength_count']} 次）\n"
            f"• 本周训练重点：{p_stat.get('key_focus') or '稳步推进有氧与专项能力'}\n"
            f"• 教练叮嘱：{p_stat.get('coach_review_note') or '注意控制有氧心率与跑后恢复'}\n"
            f"• {tw_line}"
        )
    else:
        plan_block = "• 暂未生成或激活周期训练计划"

    realtime_reaction_str = ""
    if req.body_reaction_tag or req.rpe is not None:
        parts_rt = []
        if req.body_reaction_tag:
            parts_rt.append(f"跑者刚刚在对话框上报今日实时身体反应：【{req.body_reaction_tag}】")
        if req.rpe is not None:
            parts_rt.append(f"跑者自评今日主观疲劳度 RPE：{req.rpe}/10")
        realtime_reaction_str = "；".join(parts_rt)

    body_reaction_block = (
        f"• 手表客观生理恢复：{health_line}\n"
        f"• 课表主观体感与伤痛反馈：{b_react.get('subjective_summary_line')}\n"
        f"• 综合身体反应状态：{b_react.get('badge_text')}"
    )
    if realtime_reaction_str:
        body_reaction_block += f"\n• 🔴 实时主诉身体反应：{realtime_reaction_str}"

    prompt = f"""跑者提问：{clean_question}
问题类型：{intent_hint}

【一、跑者背景与近期训练情况】
• 跑者：{runner_name}{years_text}，主攻专项：{discipline}
• Banister 负荷：CTL 体能 {ctl}，ATL 疲劳 {atl}，TSB 状态平衡 {tsb_sign}（{tsb_status}）
• 近期跑量：近 7 天完成 {t_stat['recent_7d_runs']} 次共 {t_stat['recent_7d_km']} km（近 30 天共 {t_stat['recent_30d_km']} km）
• 最近跑步记录：
{recent_runs_block}

【二、当前训练计划与今日课表】
{plan_block}

【三、身体反应（生理恢复 + 主观RPE体感 + 伤痛反馈）】
{body_reaction_block}

【四、赛历与周期阶段】
• 当前周期阶段：{phase}
{race_schedule_text}

请作为专业耐力教练，紧密结合该跑者的【1.近期训练情况】、【2.当前训练计划/今日课表】和【3.身体反应】给出具体、有针对性的专业反馈与配速/心率/恢复建议。只引用上面列出的真实数据。"""

    try:
        system_prompt = CANOVA_CHAT_SYSTEM_PROMPT.format(model_display=model_display)
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if req.history:
            for h in req.history[-4:]:
                role = h.get("role")
                content = h.get("content")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": str(content)[:600]})
        messages.append({"role": "user", "content": prompt})
        res = llm_client.chat_completion(messages=messages, temperature=0.6, max_tokens=650)
        if res and len(res.strip()) > 10 and not res.startswith("【Canova教练提示】") and not res.startswith("AI 分析生成失败"):
            cleaned_res = res.strip()
            if cleaned_res.startswith("{") and "summary" in cleaned_res:
                try:
                    parsed = json.loads(cleaned_res)
                    summary = parsed.get("summary") or ""
                    fitness = parsed.get("fitness_status") or ""
                    key_sugg = parsed.get("key_suggestions", [])
                    key_sugg_str = "\n".join(f"• {s}" for s in key_sugg)
                    cleaned_res = f"{summary}\n\n{fitness}"
                    if key_sugg_str:
                        cleaned_res += f"\n\n战术建议：\n{key_sugg_str}"
                except Exception:
                    pass
            return {"reply": cleaned_res, "model": raw_model_id, "status": "ok", "context": dialog_ctx}
    except Exception as e:
        logger.warning(f"Coach chat LLM error: {e}")

    # Fallback to high-quality synthesized response grounded in the 3 pillars (训练情况 + 训练计划 + 身体反应)
    q = q_lower
    target_race_name = (next_r["name"] if next_r else (goal_r["name"] if goal_r else (p_stat.get("target_race") or "目标赛事")))
    tw = p_stat.get("today_workout")
    tw_desc = (
        f"今日课表【{tw.get('title')}】（{tw.get('distance_km')} km，目标配速 {tw.get('target_pace') or '有氧稳态'}）"
        if tw and float(tw.get("distance_km") or 0) > 0
        else "今日休整恢复日"
    )
    reaction_tag = req.body_reaction_tag or ""

    if any(k in (q + reaction_tag) for k in ["酸痛", "紧绷", "疼痛", "膝盖", "跟腱", "足底", "伤", "不适", "沉重", "疲惫", "累", "睡眠欠佳", "没睡好", "心率偏高"]):
        reply = (
            f"🩺 **【教练综合诊断与课表动态调整】**\n\n"
            f"1. **训练负荷复盘**：您近 7 天已跑 **{t_stat['recent_7d_km']} km**（{t_stat['recent_7d_runs']} 次），当前 CTL **{ctl}**、ATL **{atl}**、TSB **{tsb_sign}（{tsb_status}）**。\n"
            f"2. **身体反应评估**：结合您反馈的**「{reaction_tag or clean_question[:18]}」**以及当前生理/体感状态（{b_react.get('watch_summary_line')}；{b_react.get('subjective_summary_line')}），说明神经肌肉或自主神经存在一定微疲劳累积。\n"
            f"3. **今日课表调整处方**：原定{tw_desc}**切勿强行顶配速**！建议将今日训练立即降阶为 **6~8 km Zone 1-2 低心率排酸慢跑（配速放慢 20~30 秒/km，心率压在 140 bpm 以下）**，或直接改为完全跑休 + 20 分钟泡沫轴松解与早睡，待明日晨起静息心率与腿部弹性恢复后再回归正常课表。"
        )
    elif any(k in q for k in ["合适", "能不能", "可以吗", "建议跑", "再跑", "要不要", "行不行", "跑不跑"]):
        if any(dist in q for dist in ["30", "40", "50", "大长", "全马", "越野", "背靠背"]):
            if next_r and next_r["days_left"] <= 14:
                reply = f"【Canova 教练裁决】：坚决反对！{runner_name}，距离您的下一场越野赛事【{next_r['name']}】仅剩 {next_r['days_left']} 天，当前已进入宝贵的赛前减量调整期 (Taper)。此时盲目堆叠 30 公里大长距离越野，不仅无法提升心肺，反而会导致大腿股四头肌离心肌纤维撕裂与深层结缔组织水肿，带着未修复的微损伤走上起点！明日强烈建议进行 45~60 分钟低心率排酸或彻底休息，切忌盲目硬撑！"
            else:
                reply = f"【Canova 教练裁决】：不建议盲目执行！{runner_name}，您当前处于{tsb_status}状态（TSB {tsb_sign}），近 7 天已累计 {t_stat['recent_7d_km']} km，连续大距离极易造成股四头肌离心损伤和无效神经疲劳堆积。建议把距离压在 15~18 公里以内，全程维持在持续有氧心率（134-151 bpm），切忌拼配速！"
        else:
            reply = (
                f"【Canova 教练裁决】：可以进行训练，但需严控强度区间。\n"
                f"• **训练与负荷**：当前 CTL {ctl} / ATL {atl} / TSB {tsb_sign}（{tsb_status}），本周计划已完成 {p_stat.get('actual_weekly_km', 0)}/{p_stat.get('planned_weekly_km', 0)} km。\n"
                f"• **身体反应与执行建议**：{b_react.get('watch_summary_line')}。针对{tw_desc}，请将有氧段心率稳压在 Zone 2（134-148 bpm），严禁跑成既不慢又不够快的‘中间垃圾配速’。"
            )
    elif "负荷" in q or "tsb" in q or "ctl" in q or "完成" in q or "评估" in q:
        reply = (
            f"📊 **【训练负荷与周计划执行评估】**\n\n"
            f"• **体能动力学**：当前长期体能储备 **CTL {ctl}**，急性疲劳 **ATL {atl}**，状态平衡指数 **TSB {tsb_sign}（{tsb_status}）**，近 7 天完成 **{t_stat['recent_7d_runs']} 次 / {t_stat['recent_7d_km']} km**。\n"
            f"• **周计划进度**：当前第 {p_stat.get('current_week_index', 1)} 周计划跑量 **{p_stat.get('planned_weekly_km', 0)} km**，已执行 **{p_stat.get('actual_weekly_km', 0)} km（完成度 {p_stat.get('completion_pct', 0)}%）**，{tw_desc}。\n"
            f"• **身体反应与建议**：{b_react.get('badge_text')}（{b_react.get('watch_summary_line')}）。面向【{target_race_name}】，请继续坚持「重点课保质量、轻松跑压心率」的极化原则。"
        )
    elif any(k in q for k in ["今天", "今日", "怎么跑", "课表"]):
        reply = (
            f"📋 **【今日课表执行与身体反应处方】**\n\n"
            f"• **今日课表**：{tw_desc}（所属《{p_stat.get('plan_title') or '当前周期计划'}》第 {p_stat.get('current_week_index', 1)} 周，本周已执行 {p_stat.get('actual_weekly_km', 0)}/{p_stat.get('planned_weekly_km', 0)} km）。\n"
            f"• **身体状态校准**：当前 TSB **{tsb_sign}（{tsb_status}）**，{b_react.get('watch_summary_line')}；{b_react.get('subjective_summary_line')}。\n"
            f"• **教练执行叮嘱**：{p_stat.get('coach_review_note') or '起跑前先做 10~15 分钟动态热身，前 2 公里循序渐进进入目标配速，跑后及时填报今日 RPE 体感。'}"
        )
    elif any(k in q for k in ["周末", "长距离", "lsd"]) and any(k in q for k in ["安排", "计划", "多长", "多远", "跑什么"]):
        if next_r and next_r["days_left"] <= 14:
            reply = f"【Canova 赛前减量特别提示】：针对即将到来的【{next_r['name']}】（仅剩 {next_r['days_left']} 天），当前处于赛前减量期 (Taper)！周末严禁安排 20 公里以上大长距离，建议安排 10~12 公里山地轻松跑（爬升 < 500m），全程压在持续有氧区 (134-148 bpm)，重点演练下坡步频与强制装备。"
        elif race_ctx["is_trail"]:
            reply = f"【Canova 山地超马长距离规划】：针对目标赛事【{target_race_name}】，周末长距离重点不在平地配速，而在【山地驻留时间 (Time on Feet)】与【爬升垂直耐力】。建议安排 3~4 小时山地训练：上坡严格压制心率（快步走 Power Hiking 控在 145 bpm 以下），下坡演练小步频离心控制，每 45 分钟演练 1 次 30-40g 高能胶补给。"
        else:
            reply = f"【Canova 周末长距离规划】针对目标赛事【{target_race_name}】，结合您当前 CTL {ctl}（TSB {tsb_sign}），建议周末按计划执行专项长距离：前半程稳守 Zone 2 有氧区，后程若心率平稳再渐进切入目标比赛配速，每 5 公里演练一次补水补胶。"
    elif "乳酸" in q or "阈值" in q:
        reply = "【Canova 乳酸门槛动力学】提升 LT2 配速的核心在于间歇漂浮跑 (Float Recoveries)，如 4x3000m 间歇以 1000m 漂浮慢跑恢复，强迫肌肉在动态巡航中清除乳酸。"
    else:
        reply = dialog_ctx["proactive_feedback"]

    return {"reply": reply, "model": raw_model_id, "status": "ok", "context": dialog_ctx}


def _build_health_recovery_sentence(health: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None) -> str:
    """Builds an accurate, factual physiological recovery sentence from latest health metrics."""
    if not health or not health.get("overnight_wear_valid"):
        return ""
    parts = []
    bb = health.get("body_battery_max")
    hrv = health.get("hrv_last_night_avg")
    hrv_base = health.get("hrv_weekly_avg")
    sleep_score = health.get("sleep_score")
    sleep_hours = health.get("sleep_duration_hours")
    rhr = health.get("resting_heart_rate")

    if bb is not None:
        parts.append(f"身体电量为 {int(round(float(bb)))}%")
    if hrv is not None:
        hrv_int = int(round(float(hrv)))
        if hrv_base:
            base_int = int(round(float(hrv_base)))
            status_zh = "平衡稳健" if 0.85 <= (hrv_int / max(1.0, float(base_int))) <= 1.15 else ("偏低需注意恢复" if hrv_int < base_int * 0.85 else "表现活跃")
            parts.append(f"夜间平均 HRV 为 {hrv_int} ms（7日基线 {base_int} ms，自主神经状态{status_zh}）")
        else:
            parts.append(f"夜间平均 HRV 为 {hrv_int} ms")
    if sleep_score is not None:
        sc_int = int(round(float(sleep_score)))
        if sleep_hours:
            parts.append(f"睡眠质量得分 {sc_int} 分（睡眠时长 {sleep_hours} 小时）")
        else:
            parts.append(f"睡眠质量得分 {sc_int} 分")
    if rhr is not None:
        parts.append(f"晨起静息心率 {int(round(float(rhr)))} bpm")

    if not parts:
        return ""
    return "最新生理恢复监测显示：" + "，".join(parts) + "。"


@router.get("/latest/{uid}")
def get_latest_coach_report(uid: str):
    """
    Returns latest cached Canova AI coach report for fast UI rendering,
    synchronizing live CTL/ATL/TSB and latest physiological health (HRV, sleep, RHR)
    so stale cached text never contradicts real watch data.
    """
    eff_uid = uid
    report = LocalStore.get_coach_report(eff_uid)
    load_metrics = LocalStore.get_training_load(eff_uid, days=90)
    user_profile = LocalStore.get_profile(eff_uid) or {}
    health = LocalStore.get_latest_health(eff_uid) or {}
    recovery_avail = LocalStore.assess_recovery_data_availability(eff_uid, health_row=health, profile=user_profile)

    age = get_age_from_dob(user_profile.get("date_of_birth"))
    runner_name = user_profile.get("display_name") or user_profile.get("email", "").split("@")[0] or "跑者"
    race_ctx = resolve_athlete_race_context(eff_uid)
    next_r = race_ctx["next_race"]
    goal_r = race_ctx["goal_race"]
    primary_target = goal_r or next_r

    if report:
        ctl_live = round(float(load_metrics.get("ctl") or 0.0), 1)
        atl_live = round(float(load_metrics.get("atl") or 0.0), 1)
        tsb_live = round(float(load_metrics.get("tsb") or 0.0), 1)
        status_live = load_metrics.get("status", "平衡稳健")
        risk_live = load_metrics.get("risk_warning")

        old_tsb_metrics = report.get("tsb_metrics") or {}
        old_ctl = float(old_tsb_metrics.get("ctl") or 0.0)
        old_tsb = float(old_tsb_metrics.get("tsb") or 0.0)

        # Always synchronize with real-time training load
        report["tsb_metrics"] = {
            "ctl": ctl_live,
            "atl": atl_live,
            "tsb": tsb_live,
            "status": status_live,
            "status_code": load_metrics.get("status_code", "neutral"),
            "risk_warning": risk_live
        }

        dirty = False
        has_real_hrv_or_sleep = bool(recovery_avail.get("recovery_data_available"))
        fs_text = str(report.get("fitness_status") or "")
        claims_missing_health = any(k in fs_text for k in ["缺失", "暂无数据", "未检测", "无夜间", "未佩戴"])
        metrics_drifted = (abs(ctl_live - old_ctl) >= 2.0 or abs(tsb_live - old_tsb) >= 3.0)

        if (has_real_hrv_or_sleep and claims_missing_health) or (not has_real_hrv_or_sleep and not claims_missing_health) or metrics_drifted:
            health_sentence = (
                _build_health_recovery_sentence(health, user_profile)
                if has_real_hrv_or_sleep
                else (recovery_avail.get("user_warning") or "近期夜间未佩戴手表，缺失夜间 HRV 与静息心率恢复数据。")
            )
            status_clean = status_live.split(" (")[0]
            risk_sentence = f"{risk_live}" if risk_live else "近期训练负荷吸收良好，体能储备与急性疲劳处于动态平衡区间。"
            report["fitness_status"] = (
                f"{runner_name}目前的长期体能 (CTL) 为 {ctl_live}，短期疲劳 (ATL) 为 {atl_live}，"
                f"状态平衡指数 (TSB) 为 {tsb_live}，处于{status_clean}状态。{risk_sentence}"
                + (f"{health_sentence}" if health_sentence else "")
            )
            sum_text = str(report.get("summary") or "")
            if tsb_live >= -15 and ("高度疲劳" in sum_text or "过度疲劳" in sum_text):
                t_name = primary_target["name"] if primary_target else report.get("athlete_snapshot", {}).get("target_race", "目标赛事")
                report["summary"] = f"当前体能储备扎实（CTL {ctl_live}，TSB {tsb_live}），生理恢复状态良好，稳步推进【{t_name}】专项能力与乳酸阈值耐力。"
            dirty = True

        # Sanitize target race if stale or pointing to completed past race
        comp_names = [c["name"] for c in race_ctx["completed"]]
        snap = report.get("athlete_snapshot") or {}
        curr_target = snap.get("target_race")
        if not curr_target or curr_target in comp_names:
            if primary_target:
                snap["target_race"] = primary_target["name"]
                snap["race_category"] = "trail" if race_ctx["is_trail"] else "marathon"
                snap["race_category_name"] = race_ctx["target_discipline"]
                report["athlete_snapshot"] = snap
                if any(cn in str(report.get("summary", "")) for cn in comp_names):
                    next_n = next_r["name"] if next_r else primary_target["name"]
                    days_l = next_r["days_left"] if next_r else 12
                    report["summary"] = f"{runner_name} 目前处于体能吸收与调整状态。距下一场【{next_n}】仅剩 {days_l} 天，应强化赛前减量与机能激活；同时扎实推进主目标【{primary_target['name']}】的越野专项储备。"
                dirty = True

        if "athlete_snapshot" not in report:
            report["athlete_snapshot"] = {
                "name": runner_name,
                "age": age,
                "gender": user_profile.get("gender") or "male",
                "years_running": user_profile.get("years_running") or 2,
                "target_race": primary_target["name"] if primary_target else "目标赛事",
                "race_category": "trail" if race_ctx["is_trail"] else "marathon",
                "race_category_name": race_ctx["target_discipline"]
            }

        # Keep multi-race countdown days_left fresh
        user_races = LocalStore.get_race_plans(eff_uid)
        if user_races:
            multi_analysis = analyze_multi_race_calendar(user_races)
            report["multi_race_analysis"] = multi_analysis
            if "multi_race_strategy" not in report:
                report["multi_race_strategy"] = generate_fallback_multi_race_strategy(
                    multi_analysis,
                    report.get("athlete_snapshot", {}).get("target_race", "目标赛事"),
                    report.get("athlete_snapshot", {}).get("race_category", "trail" if race_ctx["is_trail"] else "marathon")
                )
            else:
                races_map = {r["name"]: r for r in multi_analysis.get("races", [])}
                for adv in (report["multi_race_strategy"].get("race_timeline_advice") or []):
                    r_obj = races_map.get(adv.get("race_name", ""))
                    if r_obj and adv.get("days_left") != r_obj.get("days_left"):
                        adv["days_left"] = r_obj["days_left"]
                        dirty = True
        elif "multi_race_analysis" not in report or "multi_race_strategy" not in report:
            multi_analysis = analyze_multi_race_calendar([])
            report["multi_race_analysis"] = multi_analysis
            report["multi_race_strategy"] = generate_fallback_multi_race_strategy(
                multi_analysis,
                report.get("athlete_snapshot", {}).get("target_race", "目标赛事"),
                report.get("athlete_snapshot", {}).get("race_category", "trail" if race_ctx["is_trail"] else "marathon")
            )

        if isinstance(report.get("recovery_advice"), dict):
            rec_d = report["recovery_advice"]
            report["recovery_advice"] = "\n".join(f"【{k}】{v}" for k, v in rec_d.items())
        if isinstance(report.get("focus_workout_of_the_week"), dict):
            foc_d = report["focus_workout_of_the_week"]
            report["focus_workout_of_the_week"] = "\n".join(f"【{k}】{v}" for k, v in foc_d.items())

        if dirty:
            LocalStore.save_coach_report(eff_uid, report)

        report["recovery_data_availability"] = recovery_avail
        report["recovery_data_warning"] = recovery_avail.get("user_warning") if not recovery_avail.get("recovery_data_available") else None
        if recovery_avail.get("night_wear_missing"):
            warn_msg = recovery_avail.get("user_warning") or ""
            cur_rec_adv = str(report.get("recovery_advice") or "")
            if warn_msg and "夜间" not in cur_rec_adv:
                report["recovery_advice"] = f"{warn_msg}\n\n{cur_rec_adv}".strip()
        return report

    garmin_connected = bool(user_profile.get("garmin_connected", False))
    coros_connected = bool(user_profile.get("coros_connected", False))

    user_races = LocalStore.get_race_plans(eff_uid)
    multi_analysis = analyze_multi_race_calendar(user_races)
    multi_strategy = generate_fallback_multi_race_strategy(multi_analysis, "首选目标赛", "marathon")

    if not garmin_connected and not coros_connected:
        return {
            "summary": "欢迎来到 Canova教练 专区！请在【我的】页面绑定 Garmin 或高驰 (COROS) 账号同步您的历史运动。",
            "fitness_status": "暂未检测到手表现用运动数据。系统将在您完成首次数据同步后，自动评估您的乳酸阈值、Banister TSB 疲劳曲线与专项耐力储备。",
            "periodization_phase": "准备启动期 (Preparation)",
            "key_suggestions": [
                "连接佳明或高驰设备并开启全天候心率监测，建立个人的静息心率与夜间 HRV 基线。",
                "初级阶段建议以基础有氧轻松跑 (Zone 2) 为主，建立慢肌纤维毛细血管网与心肺储备。",
                "保持科学作息，每次长跑后及时进行针对性拉伸放松与水分电解质补充。"
            ],
            "focus_workout_of_the_week": "基础有氧建立：轻松跑 30~45 分钟，心率控制在心率储备的 65%~75% 之间。",
            "recovery_advice": "夜间保证 7~8 小时高质量睡眠，观察晨起静息心率变化，建立稳定生理基准。",
            "tsb_metrics": {
                "ctl": 0.0,
                "atl": 0.0,
                "tsb": 0.0,
                "status": "初始基线建立中",
                "status_code": "initial",
                "risk_warning": None
            },
            "athlete_snapshot": {
                "name": runner_name,
                "age": age,
                "gender": user_profile.get("gender") or "male",
                "years_running": user_profile.get("years_running") or 2
            },
            "multi_race_analysis": multi_analysis,
            "multi_race_strategy": multi_strategy
        }

    return {
        "summary": "有氧基础扎实，当前处于专项准备期，需注重专项速度与机能负荷平衡。",
        "fitness_status": f"近期训练负荷处于稳态吸收区间 (CTL: {load_metrics.get('ctl', 0)}, TSB: {load_metrics.get('tsb', 0)})，具备进阶高强度专项负荷的生理基础。",
        "periodization_phase": "专项准备期 (Special Period)",
        "key_suggestions": [
            "每周安排一次渐速长距离跑 (Progression Run)，末段提升至比赛目标特定配速。",
            "保持轻松跑日的绝对低心率控制，坚决剔除非专项的疲劳垃圾跑量。",
            "结合核心肌群与下肢力量训练，提高奔跑经济性与抗伤病能力。"
        ],
        "focus_workout_of_the_week": "热身 2km + 3 × 3000m @ 专项目标配速 (间歇 3 分钟慢跑) + 2km 冷身",
        "recovery_advice": "大课后 30 分钟内补充高碳水与适量蛋白质，夜间保证 8 小时深度睡眠，监控晨起 HRV 恢复基准。",
        "tsb_metrics": {
            "ctl": load_metrics.get("ctl", 0.0),
            "atl": load_metrics.get("atl", 0.0),
            "tsb": load_metrics.get("tsb", 0.0),
            "status": load_metrics.get("status", "平衡稳健"),
            "status_code": load_metrics.get("status_code", "neutral"),
            "risk_warning": load_metrics.get("risk_warning")
        },
        "athlete_snapshot": {
            "name": runner_name,
            "age": age,
            "gender": user_profile.get("gender") or "male",
            "years_running": user_profile.get("years_running") or 2
        },
        "multi_race_analysis": multi_analysis,
        "multi_race_strategy": multi_strategy
    }

@router.post("/analysis")
def generate_coach_analysis(request: CoachAnalysisRequest):
    """Generates Renato Canova AI Coach individualized, race-specific analysis using LLM."""
    eff_uid = request.uid
    
    # 1. Fetch real runner profile
    user_profile = LocalStore.get_profile(eff_uid) or {}
    runner_name = user_profile.get("display_name") or user_profile.get("email", "").split("@")[0] or "跑者"
    gender = str(user_profile.get("gender") or "male")
    gender_zh = "女" if gender.lower() == "female" else "男"
    years_running = user_profile.get("years_running") or 2

    # Age calculation & Masters Privacy Protection
    dob_str = user_profile.get("date_of_birth")
    age = get_age_from_dob(dob_str)
    if age is None:
        age_desc = "常规生理机能（按 48 小时常规恢复窗口评估）"
    elif age < 35:
        age_desc = f"{age} 岁 (青年期 - 组织再生快，主课间歇恢复窗口 48 小时，可耐受较高专项密度)"
    elif age < 50:
        age_desc = f"{age} 岁 (中壮年组 - 需兼顾软组织与肌腱微损伤修复，主课间歇恢复窗口 48~72 小时，增加筋膜维护)"
    else:
        # Strict privacy protection for Masters: NEVER output exact age number!
        age_desc = "大师组 (Masters - 需遵循超量恢复规律，大负荷后恢复窗口需 72~96 小时，强化抗阻肌力以防肌肉流失。特别提醒：严格保护队员隐私，分析中严禁提及具体周岁数字)"

    # Real personal bests
    marathon_pb = user_profile.get("marathon_pb")
    half_pb = user_profile.get("half_pb")
    ten_k_pb = user_profile.get("ten_k_pb")
    five_k_pb = user_profile.get("five_k_pb")

    pb_summary = f"""- 全马 PB: {format_duration(marathon_pb)}
- 半马 PB: {format_duration(half_pb)}
- 10公里 PB: {format_duration(ten_k_pb)}
- 5公里 PB: {format_duration(five_k_pb)}"""

    # 2. Fetch real training load metrics (CTL/ATL/TSB)
    load_metrics = LocalStore.get_training_load(eff_uid, days=90)
    ctl = load_metrics.get("ctl", 0.0)
    atl = load_metrics.get("atl", 0.0)
    tsb = load_metrics.get("tsb", 0.0)
    acwr = load_metrics.get("acwr", 0.0)
    tsb_status = load_metrics.get("status", "稳健")
    risk_warning = load_metrics.get("risk_warning")

    # Runner tier & coaching tone resolution
    tier_key, tier_instruction = resolve_runner_tier(user_profile, ctl)

    # 3. Race Type Resolution & Specificity Zones
    race_ctx = resolve_athlete_race_context(eff_uid)
    default_target_race = race_ctx["goal_race"] or race_ctx["next_race"]
    target_race = request.target_race or (default_target_race["name"] if default_target_race else "目标赛事")
    target_time_str = request.target_time or (default_target_race.get("target_time") if default_target_race else None) or "—"
    target_time_sec = parse_time_str(target_time_str)
    race_category, race_category_name = resolve_race_category(target_race, request.race_type, target_time_sec)

    max_hr = int(user_profile.get("max_heart_rate") or 190)
    health = LocalStore.get_latest_health(eff_uid) or {}
    local_acts = LocalStore.get_recent_activities(eff_uid, limit=15)
    recovery_avail = LocalStore.assess_recovery_data_availability(
        eff_uid, health_row=health, profile=user_profile, recent_acts=local_acts
    )
    rest_hr = int(health.get("resting_heart_rate") or 56) if recovery_avail.get("recovery_data_available") else 56

    zones = get_race_specific_zones(
        race_type=race_category,
        target_time_seconds=target_time_sec,
        pb_seconds=marathon_pb if race_category == "marathon" else (half_pb or marathon_pb),
        max_hr=max_hr,
        rest_hr=rest_hr
    )

    # 4. Format recent 15 activities & multi-race calendar
    activities_summary = []
    for a in local_acts:
        activities_summary.append({
            "name": a.get("name"),
            "start_time": a.get("start_time"),
            "distance_km": round(float(a.get("distance_meters") or 0) / 1000.0, 2),
            "elevation_gain_m": round(float(a.get("elevation_gain_meters") or 0), 1),
            "avg_pace": a.get("avg_pace_str"),
            "avg_hr": a.get("average_heartrate"),
            "trimp": a.get("trimp")
        })

    races = LocalStore.get_race_plans(eff_uid)
    eval_races = list(races) if races else []
    
    # Check if target_race matches an existing race in eval_races (prefer upcoming over completed)
    matched_race = None
    if not request.target_race and default_target_race:
        matched_race = default_target_race
    else:
        clean_target = (target_race or "").strip().lower().replace(" ", "")
        for r in eval_races:
            r_name = str(r.get("name") or "").strip().lower().replace(" ", "")
            if r_name == clean_target:
                matched_race = r
                break
            if len(clean_target) >= 2 and len(r_name) >= 2:
                if clean_target in r_name or r_name in clean_target:
                    matched_race = r
                    break

    if matched_race:
        # Align with existing database record
        target_race = matched_race["name"]
        if not request.target_time or request.target_time == "—":
            target_time_str = matched_race.get("target_time") or target_time_str
        if not request.race_type:
            race_category, race_category_name = resolve_race_category(target_race, matched_race.get("race_type"), target_time_sec)
            zones = get_race_specific_zones(
                race_type=race_category,
                target_time_seconds=target_time_sec,
                pb_seconds=marathon_pb if race_category == "marathon" else (half_pb or marathon_pb),
                max_hr=max_hr,
                rest_hr=rest_hr
            )
    elif not eval_races and target_race:
        # ONLY add synthetic race when user has ZERO registered races in DB!
        eval_races.append({
            "id": "target_active",
            "name": target_race,
            "race_type": request.race_type or race_category,
            "race_date": (date.today() + timedelta(days=60)).isoformat(),
            "target_time": target_time_str,
            "priority": "A"
        })

    multi_race_analysis = analyze_multi_race_calendar(eval_races)

    # ── Extract race intelligence (race_info) from matched race ──
    race_info = (matched_race or {}).get("race_info") or {}
    race_info_block = ""
    if race_info:
        lines = []
        # Common fields
        if race_info.get("race_level"):
            lines.append(f"- 赛事等级: {race_info['race_level']}")
        if race_info.get("course_profile"):
            lines.append(f"- 赛道特点: {race_info['course_profile']}")
        if race_info.get("net_elevation_gain_m") is not None:
            lines.append(f"- 赛道累计爬升: {race_info['net_elevation_gain_m']} m")
        if race_info.get("course_surface"):
            lines.append(f"- 路面材质: {race_info['course_surface']}")
        if race_info.get("avg_temp_c") is not None:
            lines.append(f"- 历史参赛平均气温: {race_info['avg_temp_c']} ℃")
        if race_info.get("humidity_pct") is not None:
            lines.append(f"- 历史平均湿度: {race_info['humidity_pct']}%")
        if race_info.get("weather_notes"):
            lines.append(f"- 天气情况备注: {race_info['weather_notes']}")
        if race_info.get("typical_participants"):
            lines.append(f"- 大致参赛规模: {race_info['typical_participants']} 人")
        # Trail-specific fields
        if race_info.get("race_distance_km") is not None:
            lines.append(f"- 报名赛程: {race_info['race_distance_km']} km")
        if race_info.get("elevation_gain_m") is not None:
            lines.append(f"- 累计爬升 (D+): {race_info['elevation_gain_m']} m")
        if race_info.get("elevation_loss_m") is not None:
            lines.append(f"- 累计下降 (D-): {race_info['elevation_loss_m']} m")
        if race_info.get("max_altitude_m") is not None:
            lines.append(f"- 最高点海拔: {race_info['max_altitude_m']} m")
        if race_info.get("difficulty_level"):
            lines.append(f"- 难度等级: {race_info['difficulty_level']}")
        if race_info.get("terrain_type"):
            lines.append(f"- 地形类型: {race_info['terrain_type']}")
        if race_info.get("climate_zone"):
            lines.append(f"- 气候带: {race_info['climate_zone']}")
        if race_info.get("mandatory_gear"):
            lines.append(f"- 强制装备要求: {race_info['mandatory_gear']}")
        if race_info.get("cutoff_notes"):
            lines.append(f"- 关门时间说明: {race_info['cutoff_notes']}")
        if race_info.get("custom_notes"):
            lines.append(f"- 其他备注: {race_info['custom_notes']}")
        if lines:
            race_info_block = "\n目标赛事客观情报 (Race Intelligence):\n" + "\n".join(lines)

    if recovery_avail.get("recovery_data_available"):
        recovery_context_block = f"""最新生理恢复指标:
- 晨起静息心率: {health.get('resting_heart_rate') or '—'} bpm
- 身体电量: {health.get('body_battery_max') or '—'}%
- 夜间平均 HRV: {f"{health.get('hrv_last_night_avg')} ms (7日基线 {health.get('hrv_weekly_avg')} ms)" if health.get('hrv_last_night_avg') is not None and health.get('hrv_weekly_avg') is not None else (f"{health.get('hrv_last_night_avg')} ms" if health.get('hrv_last_night_avg') is not None else '—')}
- 睡眠质量分: {health.get('sleep_score') or '—'} 分 (睡眠时长: {health.get('sleep_duration_hours') or '—'} 小时)
- 最大摄氧量 (VO2Max): {health.get('vo2_max') or user_profile.get('vo2max') or '—'} ml/kg/min"""
    else:
        recovery_context_block = f"""最新生理恢复指标:
- ⚠️ 恢复数据缺失：{recovery_avail.get('user_warning')}
- 重要执教约束：该跑者近期未在夜间佩戴手表，缺失夜间 HRV、晨起静息心率与睡眠恢复数据！切勿编造或引用任何虚假的静息心率、HRV 或睡眠数值；必须在报告中明确提示跑者与教练因缺失夜间恢复数据而无法给出准确的强度与恢复建议，要求跑者保持 24 小时佩戴手表。"""

    # Build prompt context
    user_context = f"""
跑者真实生理画像：
- 称呼/姓名: {runner_name}
- 性别: {gender_zh}
- 生理年龄与组别: {age_desc}
- 跑步球龄/年限: {years_running} 年
- 队员能力层级与教练执教要求:
{tier_instruction}
- 最大心率: {max_hr} bpm | 晨起静息心率: {f"{health.get('resting_heart_rate')} bpm" if recovery_avail.get('has_recent_rhr') else "夜间未佩戴手表(缺失)"}
- 个人历史最佳成绩 (PB):
{pb_summary}

当前身体疲劳与负荷量化监测 (Banister EWMA 模型):
- 长期体能 (CTL / 42天负荷积累): {ctl}
- 短期疲劳 (ATL / 7天急性负荷): {atl}
- 状态平衡指数 (TSB / Form = CTL - ATL): {tsb} ({tsb_status})
- 急慢性负荷比 (ACWR): {acwr}
- 负荷安全诊断: {risk_warning or '负荷增长稳健，无突发伤病风险'}

{recovery_context_block}

当前主要备赛目标:
- 目标比赛: {target_race}
- 赛事类型: {race_category_name}
- 目标成绩: {target_time_str}{race_info_block}

多赛事赛历统筹评估 (Canova A/B/C Macrocycle):
- 宏观赛历概括: {multi_race_analysis.get('macrocycle_summary')}
- 待跑赛事梯队: {json.dumps(multi_race_analysis.get('races', []), ensure_ascii=False, indent=2)}
- 密集赛程冲突预警: {json.dumps(multi_race_analysis.get('conflicts', []), ensure_ascii=False, indent=2)}
- 黄金以赛代练配对: {json.dumps(multi_race_analysis.get('pairings', []), ensure_ascii=False, indent=2)}
- 跨项转换专项考量: {json.dumps(multi_race_analysis.get('cross_discipline', []), ensure_ascii=False, indent=2)}

Canova 针对该赛事类型的专项训练区间:
{json.dumps(zones, ensure_ascii=False, indent=2)}

最近 15 次真实训练记录概览:
{json.dumps(activities_summary, ensure_ascii=False, indent=2)}
"""


    messages = [
        {"role": "system", "content": CANOVA_SYSTEM_PROMPT},
        {"role": "user", "content": f"请为跑者 {runner_name} 量身生成最新一期 Canova 训练诊断报告：\n{user_context}"}
    ]

    analysis_data = None
    try:
        raw_output = llm_client.chat_completion(messages=messages, temperature=0.7)
        clean_json = raw_output.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
        analysis_data = json.loads(clean_json)
    except Exception as e:
        logger.warning(f"[coach] LLM parse fallback: {e}")
        # Intelligent fallback matching runner tier, race_category & TSB
        if tier_key == "beginner":
            summary_text = f"每一步都在重塑更好的自己！当前处于面向【{target_race}】的有氧基础构建期，保持耐心，稳步积累。"
            fitness_text = f"近期训练正处于良好的有氧适应阶段 (CTL: {ctl}, TSB: {tsb})，静息心率维持在 {rest_hr} bpm 基线。基础有氧大厦正在一层层筑牢，持之以恒就是最大的胜利！"
            workout_desc = "基础有氧稳态跑：热身 10 分钟动态关节拉伸 + 35~45 分钟轻松对话跑 (心率严格锁定在 Z2 轻松区间，若心率漂移可果断走跑结合) + 10 分钟静态拉伸放松"
            suggs = [
                "【80/20 极化训练原则】将 80% 的跑量严格控制在能轻松交谈的慢跑心率区间。日常慢跑不盲目拼速度，才能扎实打好心肺有氧耐力基础，留出体力应对重点训练。",
                "【组织适应滞后律】心肺系统提升只需几周，但肌腱、软骨与骨骼微重塑需要 3~6 个月。请切忌盲目急躁加量，每周增量控制在 10% 以内以防伤病。",
                "【步频与落地技巧】日常慢跑中练习 170~180 步频的小步快频轻柔落地，配合深层腹式呼吸，用膝盖微屈化解地面冲击，有效保护膝关节与踝关节。"
            ]
            rec_text = "训练只是提供成长信号，真正的体能增长发生在睡眠与充分休整中。跑完当天保证 8 小时优质睡眠，如有肌肉酸痛隔天果断安排休整。"
        elif tier_key == "elite":
            summary_text = f"直击核心专项收敛瓶颈，当前处于面向【{target_race}】的高阶专项冲刺准备期。"
            fitness_text = f"体能负荷基线深厚 (CTL: {ctl}, TSB: {tsb})，静息心率 {rest_hr} bpm，神经肌肉募集与专项氧化酶储备充沛。"
            if race_category == "trail":
                workout_desc = "山地专项强化大课：热身 2km + 18km 连续技术起伏跑 (爬升 +1000m，陡坡手杖快步走压在 HRR 75%，技术下坡专注轻捷落脚) + 2km 冷身"
                suggs = [
                    f"针对 {target_race} 赛道爬升，严控上坡心率漂移，将快步走 (Power Hiking) 垂直推进效率推向极致。",
                    "利用下坡反复演练股四头肌离心抗疲劳耐受，减少技术路段着地触地时间与制动能耗。",
                    "全程严格执行每小时 60~90g 高碳水与电解质水合摄入，杜绝胃肠不耐受风险。"
                ]
            else:
                workout_desc = "马拉松专项大课：热身 3km + 4 × 4000m @ 100% 目标比赛配速 (间歇 1000m 漂浮跑 @ 门槛-15s) + 2km 冷身"
                suggs = [
                    f"针对 {target_race} 目标，核心推进 100% 比赛配速下的糖原节约效率，延长专项巡航耐力极限。",
                    "间歇组间以高质量漂浮跑 (Float) 替代慢跑散步，极致拉高血乳酸清除再利用能力。",
                    "长距离大课严格演练 60~90g/h 液体碳水补充，防范后程能量悬崖。"
                ]
            rec_text = "严控 TSB 在 -15 ~ -25 之间最佳负荷吸收区。赛前 18 天准时切入指数级减量，激发神经兴奋峰值。"
        else:
            # Intermediate
            summary_text = f"体能稳步构建中，当前处于面向【{target_race}】的专项准备期。"
            fitness_text = f"近期训练负荷处于稳态 (CTL: {ctl}, TSB: {tsb})，静息心率维持在 {rest_hr} bpm 基线，具备进阶专项负荷的生理基础。"
            if race_category == "trail":
                workout_desc = "模拟赛道起伏课：热身 2km + 15km 山地专项推进 (累计爬升 +800m，上坡手杖快步走保持 Z2 心率，下坡练习平稳着地) + 2km 冷身"
                suggs = [
                    f"针对 {target_race} 赛事，强化爬升专项垂直耐力与山地快步走 (Power Hiking) 效率。",
                    "重点练习连续技术下坡的敏捷落脚，让股四头肌建立对离心冲击的耐受保护。",
                    "长距离实战中严格演练补给策略，确保每 45 分钟补充 1 支能量胶并配合电解质水。"
                ]
            elif race_category == "half":
                workout_desc = "半马门槛巡航：热身 3km + 3 × 3000m @ 半马专项配速 (间歇 2 分钟慢跑) + 2km 冷身"
                suggs = [
                    f"针对 {target_race}，核心推进乳酸门槛 (LT2) 速度平台，提升混氧续航时间。",
                    "每周安排一次 14~16km 稳态节奏跑，严格锁定在目标半马配速区间。",
                    "保持轻松跑日的绝对低心率，防止门槛课疲劳向平时渗透。"
                ]
            elif race_category in ["10k", "5k"]:
                workout_desc = "最大摄氧量间歇：热身 2km + 5 × 1000m @ 比赛配速 (间歇 90 秒慢跑) + 2km 冷身"
                suggs = [
                    f"针对 {target_race} 场地/路跑，重点提升 VO2max 峰值与乳酸耐受能力。",
                    "增强下肢踝关节刚性与后蹬步频节奏，减少触地时间。",
                    "短距离高强度课前后做好深层筋膜放松与充分动态拉伸。"
                ]
            else:
                workout_desc = "马拉松专项长推进：热身 3km + 3 × 4000m @ 全马专项配速 (间歇 1000m 漂浮跑) + 2km 冷身"
                suggs = [
                    f"针对 {target_race}，重点强化 100% 马拉松配速 (MP) 下的肌糖原节约效率。",
                    "每周安排一次 20~24km 的渐速长距离跑 (Progression Run)，末段 5km 提至比赛配速段。",
                    "保持轻松跑日的绝对低心率控制，杜绝无效疲劳垃圾跑量。"
                ]
            rec_text = "课后 30 分钟内补充优质碳水与乳清蛋白，夜间保证 8 小时深度睡眠，监控晨起 HRV 与静息心率恢复。"

        if risk_warning:
            rec_text = f"【负荷预警】{risk_warning} 请降低训练密度，优先保证充分休息。"
        elif age and age >= 50:
            rec_text = "【大师组恢复特别提示】作为经验丰富的大师组队员，大负荷课后需保留充裕的超量恢复窗口（72~96小时），夜间保证高质量深睡并配合充足蛋白质摄入与核心抗阻维护。"

        analysis_data = {
            "summary": summary_text,
            "fitness_status": fitness_text,
            "periodization_phase": "专项准备期 (Special Period)",
            "key_suggestions": suggs,
            "focus_workout_of_the_week": workout_desc,
            "recovery_advice": rec_text
        }

    if analysis_data and isinstance(analysis_data, dict):
        has_real_hrv_or_sleep = (
            health.get("hrv_last_night_avg") is not None
            or health.get("sleep_score") is not None
            or health.get("sleep_duration_hours") is not None
        )
        fit_str = str(analysis_data.get("fitness_status") or "")
        if has_real_hrv_or_sleep and ("数据缺失" in fit_str or "HRV缺失" in fit_str or "缺乏睡眠" in fit_str):
            health_sentence = _build_health_recovery_sentence(health)
            fit_str = re.sub(
                r"身体电量为[^。]*数据缺失[^。]*。",
                health_sentence,
                fit_str,
            )
            analysis_data["fitness_status"] = fit_str

    # Ensure robust multi-race strategy is present
    raw_strategy = analysis_data.get("multi_race_strategy") if analysis_data else None
    if not raw_strategy or not isinstance(raw_strategy, dict) or not raw_strategy.get("race_timeline_advice"):
        fallback_strat = generate_fallback_multi_race_strategy(multi_race_analysis, target_race, race_category)
        if raw_strategy and isinstance(raw_strategy, dict):
            fallback_strat.update({k: v for k, v in raw_strategy.items() if v})
        analysis_data["multi_race_strategy"] = fallback_strat
    else:
        # Attach id and days_left from multi_race_analysis if missing
        advice_list = raw_strategy.get("race_timeline_advice") or []
        races_map = {r["name"]: r for r in multi_race_analysis.get("races", [])}
        for adv in advice_list:
            adv_name = adv.get("race_name", "")
            matched_r = races_map.get(adv_name)
            if not matched_r:
                for rn, r_obj in races_map.items():
                    if adv_name in rn or rn in adv_name:
                        matched_r = r_obj
                        break
            if matched_r:
                adv["id"] = matched_r.get("id") or matched_r["name"]
                if "days_left" not in adv:
                    adv["days_left"] = matched_r.get("days_left", 0)
            else:
                adv["id"] = adv_name

        analysis_data["multi_race_strategy"] = raw_strategy

    analysis_data["multi_race_analysis"] = multi_race_analysis

    # Inject metadata into response
    analysis_data["tsb_metrics"] = {
        "ctl": ctl,
        "atl": atl,
        "tsb": tsb,
        "acwr": acwr,
        "status": tsb_status,
        "risk_warning": risk_warning
    }
    analysis_data["athlete_snapshot"] = {
        "name": runner_name,
        "age": age,
        "gender": gender,
        "years_running": years_running,
        "target_race": target_race,
        "target_time": target_time_str,
        "race_category": race_category,
        "race_category_name": race_category_name
    }
    analysis_data["race_zones"] = zones

    # Normalize recovery_advice and focus_workout_of_the_week if dict
    if isinstance(analysis_data.get("recovery_advice"), dict):
        rec_d = analysis_data["recovery_advice"]
        analysis_data["recovery_advice"] = "\n".join(f"【{k}】{v}" for k, v in rec_d.items())
    if isinstance(analysis_data.get("focus_workout_of_the_week"), dict):
        foc_d = analysis_data["focus_workout_of_the_week"]
        analysis_data["focus_workout_of_the_week"] = "\n".join(f"【{k}】{v}" for k, v in foc_d.items())

    analysis_data["recovery_data_availability"] = recovery_avail
    analysis_data["recovery_data_warning"] = (
        recovery_avail.get("user_warning") if not recovery_avail.get("recovery_data_available") else None
    )
    if recovery_avail.get("night_wear_missing"):
        warn_msg = recovery_avail.get("user_warning") or ""
        cur_rec_adv = str(analysis_data.get("recovery_advice") or "")
        if warn_msg and "夜间" not in cur_rec_adv:
            analysis_data["recovery_advice"] = f"{warn_msg}\n\n{cur_rec_adv}".strip()

    # Save to local store
    if analysis_data:
        LocalStore.save_coach_report(eff_uid, analysis_data)

    return analysis_data


# ── CANOVA & DANIELS PERIODIZED TRAINING PLAN SYSTEM ──

class GenerateTrainingPlanRequest(BaseModel):
    athlete_uid: Optional[str] = None
    uid: Optional[str] = None
    user_id: Optional[str] = None
    goal_type: Optional[str] = "race_prep"  # "race_prep" or "fitness_maintenance"
    target_race_id: Optional[str] = None
    target_race_name: Optional[str] = None
    target_time: Optional[str] = None
    race_type: Optional[str] = None  # "marathon", "half", "trail", "10k", "5k"
    maintenance_focus: Optional[str] = None  # "aerobic_base", "lactate_threshold", "vo2max_speed", "trail_climbing", "general_maintenance"
    target_date: Optional[str] = None  # YYYY-MM-DD
    weeks_count: Optional[int] = None
    weeks: Optional[int] = None
    days_per_week: Optional[int] = 4
    preferred_long_run_day: Optional[str] = "Sunday"  # "Sunday" or "Saturday"
    club_id: Optional[str] = None
    operator_uid: Optional[str] = None
    align_with_user_goal: Optional[bool] = True
    user_weekly_target: Optional[float] = None
    as_draft: Optional[bool] = False
    coach_notes_prompt: Optional[str] = None
    use_fast_engine: Optional[bool] = False
    preview_only: Optional[bool] = False


class ConfirmPlanRequest(BaseModel):
    plan_payload: Dict[str, Any]
    user_id: Optional[str] = None
    operator_uid: Optional[str] = None
    publish_as_coach: Optional[bool] = False
    sync_to_goals: Optional[bool] = False


class SyncPlanToGoalsRequest(BaseModel):
    user_id: Optional[str] = None
    sync_mode: Optional[str] = "average"  # "average" (mean weekly mileage) or "current_week"


class UpdateWorkoutRequest(BaseModel):
    week_index: int
    day_index: int
    date: Optional[str] = None
    workout_type: Optional[str] = None
    title: Optional[str] = None
    distance_km: Optional[float] = None
    duration_minutes: Optional[int] = None
    target_pace: Optional[str] = None
    target_hr_zone: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    coach_notes: Optional[str] = None
    # W19 Biometrics & Execution & RPE & Runner Self-Feel Notes
    hrv: Optional[int] = None
    resting_hr: Optional[int] = None
    respiratory_rate: Optional[float] = None
    strain_score: Optional[float] = None
    recovery_pct: Optional[int] = None
    actual_execution_text: Optional[str] = None
    rpe: Optional[int] = None
    feeling_tag: Optional[str] = None
    feeling: Optional[str] = None
    feedback: Optional[str] = None
    athlete_notes: Optional[str] = None
    notes: Optional[str] = None
    workout_photos: Optional[List[str]] = None
    photo_url: Optional[str] = None
    photo_base64: Optional[str] = None
    new_photos_base64: Optional[List[str]] = None
    strength_completed: Optional[bool] = None
    is_swapped: Optional[bool] = None
    swap_with_day_index: Optional[int] = None
    undo_swap: Optional[bool] = False
    is_coach_edit: Optional[bool] = False
    preview_only: Optional[bool] = False
    schedule_data: Optional[Dict[str, Any]] = None
    plan_payload: Optional[Dict[str, Any]] = None
    operator_uid: str


class UpdateWeekSummaryRequest(BaseModel):
    week_index: int
    injury_note: Optional[str] = None
    athlete_weekly_summary: Optional[str] = None
    travel_or_leave_note: Optional[str] = None
    coach_weekly_diagnosis: Optional[str] = None
    strength_count_override: Optional[int] = None
    custom_summary_line: Optional[str] = None
    week_summary_override: Optional[str] = None
    macro_roadmap: Optional[str] = None
    operator_uid: str


class RollNextWeekRequest(BaseModel):
    source_week_index: Optional[int] = None
    base_week_index: Optional[int] = None
    coach_diagnosis: Optional[str] = None
    coach_focus_note: Optional[str] = None
    mileage_delta_pct: Optional[float] = None
    volume_scale: Optional[float] = None
    focus_override: Optional[str] = None
    next_week_theme: Optional[str] = None
    weekday_group_workout: Optional[str] = None
    weekend_long_run_km: Optional[float] = None
    preview_only: Optional[bool] = False
    schedule_data: Optional[Dict[str, Any]] = None
    plan_payload: Optional[Dict[str, Any]] = None
    operator_uid: str


class ClubBroadcastWorkoutRequest(BaseModel):
    club_id: str
    operator_uid: str
    day_index: int  # Supports 0=周一..6=周日 (day_index_base=0) or 1=周一..7=周日 (day_index_base=1)
    day_index_base: Optional[int] = None
    target_week_mode: Optional[str] = "current"  # "current" or "next"
    user_ids: Optional[List[str]] = None
    workout_type: Optional[str] = "interval"
    title: str
    distance_km: Optional[float] = 12.0
    duration_minutes: Optional[int] = None
    target_pace: Optional[str] = "按分组配速"
    target_hr_zone: Optional[str] = "Z3-Z4"
    description: Optional[str] = ""
    coach_notes: Optional[str] = ""


class AssignTemplateRequest(BaseModel):
    template_id: str
    user_ids: Optional[List[str]] = None
    target_user_ids: Optional[List[str]] = None
    operator_uid: str
    club_id: Optional[str] = None
    apply_mode: Optional[str] = None  # "full_plan" or "single_week"
    apply_scope: Optional[str] = None  # "full_plan", "current_week", "next_week", "single_week"
    target_week_index: Optional[int] = None
    weeks_count: Optional[int] = 4
    volume_scale: Optional[float] = None
    scale_factor: Optional[float] = None
    as_draft: Optional[bool] = True
    custom_days: Optional[List[Dict[str, Any]]] = None
    custom_weeks: Optional[List[Dict[str, Any]]] = None
    custom_title: Optional[str] = None
    coach_review_note: Optional[str] = None
    macro_roadmap: Optional[str] = None
    preview_only: Optional[bool] = False
    base_plan: Optional[Dict[str, Any]] = None
    canova_progression: Optional[bool] = True


class SaveCustomTemplateRequest(BaseModel):
    operator_uid: str
    club_id: Optional[str] = None
    template_id: Optional[str] = None
    group_code: str = "自定义组"
    category: Optional[str] = "custom"
    name: Optional[str] = None
    short_name: Optional[str] = None
    badge_color: Optional[str] = "amber"
    target_level: Optional[str] = "教练定制专项组"
    intensity_tag: Optional[str] = "教练定制配速与强度"
    weekly_km: Optional[float] = None
    days_per_week: Optional[int] = None
    pace_zones: Optional[Dict[str, Any]] = None
    macro_roadmap: Optional[str] = ""
    coach_review_note: Optional[str] = ""
    days_template: Optional[List[Dict[str, Any]]] = None
    from_plan_id: Optional[str] = None
    from_week_index: Optional[int] = None


class UpdatePlanRequest(BaseModel):
    title: Optional[str] = None
    overview_summary: Optional[str] = None
    status: Optional[str] = None  # 'draft', 'active', 'archived', 'completed'
    coach_review_note: Optional[str] = None
    operator_uid: str


class PublishPlanRequest(BaseModel):
    operator_uid: str
    title: Optional[str] = None
    overview_summary: Optional[str] = None
    coach_review_note: Optional[str] = None
    sync_to_goals: Optional[bool] = True
    schedule_data: Optional[Dict[str, Any]] = None
    plan_payload: Optional[Dict[str, Any]] = None


class AdjustPlanWeekRequest(BaseModel):
    week_index: int
    action: str  # "scale_volume", "downgrade_intensity", "update_meta"
    scale_factor: Optional[float] = None
    week_title: Optional[str] = None
    phase: Optional[str] = None
    key_focus: Optional[str] = None
    preview_only: Optional[bool] = False
    schedule_data: Optional[Dict[str, Any]] = None
    plan_payload: Optional[Dict[str, Any]] = None
    operator_uid: str


class ClubBatchGeneratePlansRequest(BaseModel):
    club_id: str
    operator_uid: str
    student_uids: Optional[List[str]] = None
    weeks_count: Optional[int] = None
    weeks: Optional[int] = None
    days_per_week: Optional[int] = 4
    only_without_plan: Optional[bool] = True
    as_draft: Optional[bool] = True
    use_fast_engine: Optional[bool] = True



CANOVA_PLAN_SYSTEM_PROMPT = """你是一位享誉国际的耐力运动首席训练专家，精通雷纳托·卡诺瓦 (Renato Canova) 的“专项性推进哲学”与杰克·丹尼尔斯 (Jack Daniels) 的“VDOT 能量代谢配速模型”。
你的任务是根据跑者的真实生理画像、即时负荷 (CTL/ATL/TSB)、历史 PB、以及近 12~18 个月的真实比赛和长距离实战表现，制定科学、严密、可落地的周度/日度周期训练计划 (Training Plan)。

【核心训练准则】：
1. 目标导向性与 Canova 漏斗周期递进 (Canova Funnel Periodization - 严禁每周课表雷同)：
   - 比赛备战目标 (race_prep)：倒排至比赛日。合理规划：基础构建期 (Fundamental) -> 专项准备期 (Special) -> 比赛专项期 (Specific) -> 渐进减量期 (Tapering，赛前 2-3 周递减 20%-40%-60% 容量但维持配速神经张力) -> 比赛周 (Race Week)。
   - 【核心铁律：拒绝复制粘贴】：严禁在 6 周或 8 周课表中每周重复完全相同的周二、周三、周四或周日课表！必须遵循 Renato Canova 漏斗收敛理论 (Funnel Periodization)：
     * 周二（速度端/有氧支撑）：从短坡冲刺/400m神经激活 -> 800m/1000m VO2Max 经典间歇 -> 1600m/2000m 混氧耐力间歇 -> 减量周法特莱克 -> 赛前锐化短间歇，每周递进演化；
     * 周四（门槛与专项端）：从有氧渐速跑 (Progressive Run) -> LT2 巡航短间歇 (4×1600m/3×2000m) -> LT2 稳态延伸 (3×2500m) -> 减量周马配节奏感知 -> Canova 专项交替跑 (Alternations: 1km@103%MP + 1km@95%MP 乳酸穿梭) -> 长距离专项巡航 (3×3000m @ MP/LT2) -> 赛前专项配速唤醒；
     * 周日（长距离端）：从纯有氧稳态 LSD (85% MP) -> 后程渐进长距离 (后30% @ 95% MP) -> 分段马配长距离 (含 2×4-5km @ 100% MP) -> 减量吸收有氧长跑 -> Canova 专项模拟大课 (Fast-Finish 后40% @ 100% MP) -> 赛前减量中长跑 -> 目标正赛；
     * 恢复跑与力量训练：每周轮换力量侧重点（臀中肌骨盆稳定 -> 单腿离心抗阻 -> 跟腱踝关节刚性 -> 深度筋膜松解），里程呈 3:1 波浪式起伏。
   - 非赛季体能进阶目标 (fitness_maintenance)：
     * 基础有氧扩容 (aerobic_base)：低心率 Zone 2 扩容，最大化慢肌纤维毛细血管网与脂肪氧化率；
     * 乳酸阈值提升 (lactate_threshold)：LT1/LT2 巡航间歇与稳态节奏跑，提升高配速巡航续航时间；
     * VO2Max 速度储备 (vo2max_speed)：800m~1500m 场地间歇与神经肌肉步频刚性；
     * 山地越野爬坡抗阻 (trail_climbing)：手杖垂直爬升 (D+)、山地阶梯与下坡股四头肌离心抗撕裂；
     * 全面体能维持 (general_maintenance)：平衡跑量、力量与柔韧，维持良好 CTL。
2. 年龄与恢复窗口自适应 (Masters Recovery)：
   - 青年跑者 (<35岁)：大课恢复窗口约 48 小时；
   - 中壮年跑者 (35~49岁)：大课恢复窗口约 48~72 小时；
   - 大师组跑者 (≥50岁)：大课恢复窗口需 72~96 小时！坚决执行 Hard-Easy 规律，大课后必须留足 2~3 天轻松慢跑或休整，严禁连续两天堆积高强度或大跑量。
3. 负荷与防伤控制：
   - 起始周跑量须与跑者近 4 周平均周跑量自然衔接，周增幅严格 ≤ 10%；
   - 每 3~4 周必须安排一次减量恢复周 (Down-week)，削减 25%~35% 容量以促进超量恢复。
4. 12~18 个月比赛历史尊重：
   - 严禁空想超出跑者实际经验的极端单次跑量，长跑课须基于其过去 18 个月的最长拉练纪录稳步拓展。
5. 已安排既定比赛深度融合与实战周历重排 (Seamless Integration of Scheduled Races):
   - 若跑者在计划周期内已登记既定比赛（如 9/12 武功山 50K C 标模拟拉练赛、B 标以赛代练等），必须在比赛所在周的准确具体日期将 workout_type 设为 "race"；
   - 课目标题必须明确写为“【比赛日】赛事名称 (A/B/C 标)”，里程填写真实比赛公里数（如 50km），并根据 A/B/C 标定位给出针对性实战控心率与补给说明；
   - 比赛次日严禁安排长距离大课，强制彻底休息或排酸极慢步 (workout_type: "rest", 0km)；
   - 比赛当周以该比赛完全替代周末长距离大课，严禁在同一周末既跑 50K 比赛次日又跑 21K 长距离！
6. 跑者自定跑量目标基准对齐 (Weekly & Monthly Target Alignment):
   - 计划的基准容量必须锚定跑者的自定周跑量目标 (Weekly Target km) 与月度目标；
   - 第 1 周起始跑量应收敛在跑者自定周目标的 ±5%~10% 范围内，符合其日常生活作息习惯，切勿盲目大幅偏离；
   - 渐进周按波浪式（递增 ≤ 10%），减量周自然下浮至 70%~75%，使整套周期的平均跑量与跑者的心智预期高度契合！

请直接以严格的 JSON 格式输出，不得带有除 JSON 外的任何解释文字：
{
  "macro_cycle_name": "周期计划名称",
  "goal_summary": "总体周期战略与科学设计要点综述（结合跑者年龄、VO2Max、TSB、18个月比赛表现）",
  "weeks": [
    {
      "week_index": 1,
      "week_title": "第 1 周 · 阶段与重点",
      "phase": "基础构建期 / 专项准备期 / 专项突破期 / 赛前减量期 / 实战比赛周 / 比赛恢复周",
      "weekly_mileage_km": 45.0,
      "key_focus": "本周核心训练目标说明",
      "days": [
        {
          "day_of_week": "周一",
          "date": "2026-09-08",
          "workout_type": "rest", // 枚举: "rest", "easy_run", "tempo", "interval", "long_run", "trail_climb", "cross_training", "race"
          "title": "完全休息 / 筋膜泡沫轴放松",
          "distance_km": 0.0,
          "target_pace": "—",
          "target_hr_zone": "—",
          "description": "详细课表安排，包含热身、主课间歇/配速/心率要求、冷身慢跑与注意事项",
          "completed": false,
          "coach_notes": ""
        }
      ]
    }
  ]
}
"""


def integrate_scheduled_races_into_schedule(
    schedule_data: Dict[str, Any],
    scheduled_races: List[Dict[str, Any]],
    age: Optional[int] = None,
    vdot: Optional[float] = None
) -> Dict[str, Any]:
    """
    Deterministically integrates upcoming scheduled races into the periodized training plan:
    1. Replaces the matching date's workout with an official 'race' workout (with accurate distance and A/B/C strategy).
    2. Adjusts the day before the race (pre-race shakeout/rest).
    3. Adjusts the day after the race (STRICTLY cancels any conflicting Sunday long run or quality session, replacing with rest).
    4. For masters (age >= 50), ensures a 72-96h recovery window after major races (e.g. 50K ultra or marathon).
    5. Updates week title, key focus, and re-aggregates weekly mileage.
    """
    if not schedule_data or not schedule_data.get("weeks") or not scheduled_races:
        return schedule_data

    weeks = schedule_data.get("weeks", [])
    is_masters = age and age >= 50

    for race in scheduled_races:
        race_date_raw = str(race.get("race_date") or "").strip()
        if not race_date_raw:
            continue
        race_date_str = race_date_raw[:10]
        race_name = race.get("name") or "目标赛事"
        race_type = str(race.get("race_type") or "").lower()
        target_time = race.get("target_time") or ""

        # Priority resolution
        raw_pri = str(race.get("priority", 1)).upper()
        if raw_pri in ["A", "1"]:
            pri = 1
            pri_label = "A 标 (巅峰核心目标)"
        elif raw_pri in ["B", "2"]:
            pri = 2
            pri_label = "B 标 (以赛代练)"
        else:
            pri = 3
            pri_label = "C 标 (模拟拉练赛)"

        # Distance resolution
        name_type = f"{race_name} {race_type}".lower()
        if "160" in name_type or "百英里" in name_type:
            race_dist = 160.0
        elif "100k" in name_type or "百公里" in name_type or "100公里" in name_type:
            race_dist = 100.0
        elif "60k" in name_type or "60公里" in name_type or "60" in name_type:
            race_dist = 60.0
        elif "50k" in name_type or "50公里" in name_type or "50" in name_type or "武功山" in name_type or "灵鹫山" in name_type:
            race_dist = 50.0
        elif "30k" in name_type or "30公里" in name_type:
            race_dist = 30.0
        elif "全马" in name_type or "全程" in name_type or "marathon" in name_type:
            race_dist = 42.2
        elif "半马" in name_type or "半程" in name_type or "half" in name_type:
            race_dist = 21.1
        elif "10k" in name_type or "10公里" in name_type:
            race_dist = 10.0
        elif "5k" in name_type or "5公里" in name_type:
            race_dist = 5.0
        else:
            race_dist = 50.0 if any(k in name_type for k in ["越野", "trail", "山"]) else 42.2

        # Pacing & guidance based on priority
        if pri == 1:
            pace_advice = f"执行 100% 专项目标配速/心率 (目标时间: {target_time or '突破 PB'})"
            hr_advice = "比赛专项心率控速"
            desc = (
                f"正式比赛日：本场为赛季 A 标巅峰突破战！前程沉稳克制控心率，半程后发挥体能储备果断收敛。"
                f"演练实战进补（每 40~45 分钟补胶与电解质水），直击 {target_time or '突破个人最好成绩'} 目标！"
            )
        elif pri == 2:
            pace_advice = "执行 95%~98% 门槛巡航配速，稳态控心率"
            hr_advice = "心率控制在 LT1-LT2 门槛区间"
            desc = (
                f"正式比赛日：本场作为 B 标以赛代练，主要实战校验乳酸门槛平台、跑鞋装备与补给消化吸收。"
                f"严控心率在门槛稳态内，切勿拼到力竭，保留 5% 储备安全完赛。"
            )
        else:
            pace_advice = "心率严格压在 Zone 2 / Zone 3 稳态，严禁盲目冲刺"
            hr_advice = "心率上限严格控制在 < 155 bpm"
            desc = (
                f"正式比赛日：本场作为 C 标模拟拉练赛，以实战完全代替当周周末长距离拉练。"
                f"严禁盲目冲刺抢速，重点演练实战补给节奏、手杖使用技术与下坡股四头肌离心抗阻缓冲，安全无伤完赛。"
            )

        # Search weeks for matching date
        for w_idx, week in enumerate(weeks):
            days = week.get("days", [])
            for d_idx, day in enumerate(days):
                if day.get("date") == race_date_str:
                    # Found race day!
                    day["workout_type"] = "race"
                    day["title"] = f"🏁【比赛日】{race_name} ({pri_label})"
                    day["distance_km"] = float(race_dist)
                    day["target_pace"] = pace_advice
                    day["target_hr_zone"] = hr_advice
                    day["description"] = desc

                    # 1. Adjust day before race
                    if d_idx > 0:
                        prev_day = days[d_idx - 1]
                        if pri == 1:
                            prev_day["workout_type"] = "rest"
                            prev_day["title"] = f"赛前静养蓄能 ({race_name} 赛前)"
                            prev_day["distance_km"] = 0.0
                            prev_day["target_pace"] = "—"
                            prev_day["target_hr_zone"] = "—"
                            prev_day["description"] = f"为明日【{race_name}】巅峰之战储备糖原与精力，静养休息，检查强制装备与号码布。"
                        else:
                            prev_day["workout_type"] = "rest"
                            prev_day["title"] = f"赛前休整蓄能 ({race_name} 赛前)"
                            prev_day["distance_km"] = 0.0
                            prev_day["target_pace"] = "—"
                            prev_day["target_hr_zone"] = "—"
                            prev_day["description"] = f"为明日【{race_name}】实战拉练储备糖原，静养，检查装备、越野杖与补给胶。"

                    # 2. Adjust 2 days before race (e.g. Thursday if race is Saturday): ensure no heavy quality workout
                    if d_idx >= 2:
                        two_days_before = days[d_idx - 2]
                        if two_days_before.get("workout_type") in ["tempo", "interval", "trail_climb"] or (two_days_before.get("distance_km") or 0) > 10:
                            two_days_before["workout_type"] = "easy_run"
                            two_days_before["title"] = "赛前低心率唤醒轻松跑 (Shakeout)"
                            two_days_before["distance_km"] = 6.0
                            two_days_before["target_pace"] = "轻松跑配速"
                            two_days_before["target_hr_zone"] = "心率 < 135 bpm"
                            two_days_before["description"] = "赛前 48 小时轻松短距离慢跑，活动关节与激活神经，严禁累积疲劳。"

                    # 3. Adjust day after race (CRITICAL: Cancel any long run or quality workout!)
                    if d_idx < len(days) - 1:
                        next_day = days[d_idx + 1]
                        next_day["workout_type"] = "rest"
                        next_day["title"] = f"赛后超量恢复 / 排酸休整 ({race_name} 赛后)"
                        next_day["distance_km"] = 0.0
                        next_day["target_pace"] = "—"
                        next_day["target_hr_zone"] = "—"
                        next_day["description"] = (
                            f"【{race_name}】完赛后机能处于深度吸收与微损伤修复期，坚决严禁任何长跑或强度课！"
                            f"彻底休息，温水足浴、轻柔拉伸，充分补充高碳水化合物、优质蛋白与电解质水。"
                        )

                    # 4. If race is on Sunday (d_idx == 6), adjust following week Monday/Tuesday
                    if d_idx == 6 and w_idx + 1 < len(weeks):
                        following_week = weeks[w_idx + 1]
                        fol_days = following_week.get("days", [])
                        if len(fol_days) > 0:
                            fol_days[0]["workout_type"] = "rest"
                            fol_days[0]["title"] = f"赛后超量恢复日 ({race_name} 赛后)"
                            fol_days[0]["distance_km"] = 0.0
                            fol_days[0]["description"] = "赛后次日深度休整，保证充足睡眠，让下肢微肌纤维恢复。"
                        if is_masters and len(fol_days) > 1:
                            fol_days[1]["workout_type"] = "easy_run"
                            fol_days[1]["title"] = "极低心率排酸漫步"
                            fol_days[1]["distance_km"] = 5.0
                            fol_days[1]["description"] = "50+ 大师组 72 小时恢复窗口，仅做轻微排酸活动，心率不超过 125 bpm。"

                    # 5. If race is on Saturday (d_idx == 5), also ensure following week Monday is rest
                    if d_idx == 5 and w_idx + 1 < len(weeks):
                        following_week = weeks[w_idx + 1]
                        fol_days = following_week.get("days", [])
                        if len(fol_days) > 0:
                            fol_days[0]["workout_type"] = "rest"
                            fol_days[0]["title"] = f"赛后超量恢复日 ({race_name} 赛后)"
                            fol_days[0]["distance_km"] = 0.0
                            fol_days[0]["description"] = "赛后第 2 天深度休整，温水泡脚，促进乳酸代谢吸收。"

                    # Update week overview & titles
                    week["week_title"] = f"第 {week.get('week_index', w_idx + 1)} 周 · 【实战拉练】{race_name} ({pri_label})"
                    week["phase"] = f"实战比赛周 ({pri_label})"
                    week["key_focus"] = f"本周核心：出战【{race_name}】({pri_label})。实战演练补给与配速，周末严禁额外叠加长距离，赛后严格执行超量恢复。"
                    week["weekly_mileage_km"] = round(sum(float(d.get("distance_km") or 0) for d in days), 1)

    return schedule_data


def _shift_pace_mmss(pace_str: str, delta_sec: int) -> str:
    """Shifts a 'M:SS' pace string by delta_sec seconds and returns 'M:SS'."""
    try:
        parts = str(pace_str).strip().split(":")
        total = int(parts[0]) * 60 + int(parts[1]) + int(delta_sec)
        total = max(150, min(600, total))
        return f"{total // 60}:{total % 60:02d}"
    except Exception:
        return pace_str


def generate_fallback_training_plan(
    athlete_name: str,
    goal_type: str,
    target_race_name: str,
    target_time_str: str,
    race_category: str,
    maintenance_focus: Optional[str],
    weeks_count: int,
    days_per_week: int,
    start_monday: date,
    vdot: float,
    pb_marathon_sec: Optional[int],
    max_long_run_18m_km: float,
    age: Optional[int],
    scheduled_races: Optional[List[Dict[str, Any]]] = None,
    user_weekly_target: Optional[float] = 50.0
) -> Dict[str, Any]:
    """
    Intelligently generates a complete, scientifically rigorous Renato Canova Funnel Periodization
    & Jack Daniels VDOT training plan tailored to runner's age, VDOT paces, 18-month historical
    performances, and self-defined weekly target. Every week evolves in volume, stimulus, and workout structure.
    """
    # Calculate key paces
    easy_pace_low = "5:35"
    easy_pace_high = "6:00"
    marathon_pace = "4:30"
    tempo_pace = "4:15"
    interval_pace = "3:55"

    if vdot and vdot > 0:
        if vdot >= 58:
            easy_pace_low, easy_pace_high, marathon_pace, tempo_pace, interval_pace = "4:50", "5:15", "4:00", "3:48", "3:30"
        elif vdot >= 52:
            easy_pace_low, easy_pace_high, marathon_pace, tempo_pace, interval_pace = "5:20", "5:45", "4:30", "4:15", "3:55"
        elif vdot >= 46:
            easy_pace_low, easy_pace_high, marathon_pace, tempo_pace, interval_pace = "5:45", "6:15", "4:58", "4:42", "4:20"
        elif vdot >= 40:
            easy_pace_low, easy_pace_high, marathon_pace, tempo_pace, interval_pace = "6:15", "6:50", "5:35", "5:15", "4:50"
        else:
            easy_pace_low, easy_pace_high, marathon_pace, tempo_pace, interval_pace = "6:45", "7:25", "6:20", "5:55", "5:25"

    # Derived Canova funnel paces (relative to Marathon Pace & LT2)
    aerobic_support_pace = _shift_pace_mmss(marathon_pace, 18)   # ~92-94% MP (Canova Moderate Aerobic / Float)
    sub_mp_pace = _shift_pace_mmss(marathon_pace, 10)            # ~96% MP (Special Endurance)
    fast_mp_pace = _shift_pace_mmss(marathon_pace, -6)           # ~102-103% MP (Canova Alternation Fast segment)
    rep_pace = _shift_pace_mmss(interval_pace, -8)               # ~108-110% MP (Short Neuromuscular / 400m)

    is_trail = race_category == "trail" or "越野" in (target_race_name or "") or maintenance_focus == "trail_climbing"
    is_masters = bool(age and age >= 50)

    weeks = []
    days_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    # Target base weekly mileage anchoring
    base_weekly_tgt = float(user_weekly_target or 50.0)
    base_weekly_tgt = max(20.0, min(120.0, base_weekly_tgt))
    scale_f = max(0.65, min(1.65, base_weekly_tgt / 42.0))

    # Base starting long run
    start_lr_dist = min(max_long_run_18m_km * 0.75 if max_long_run_18m_km else 18.0, 22.0)
    if is_trail:
        start_lr_dist = min(start_lr_dist, 20.0)
    start_lr_dist = round(max(start_lr_dist, base_weekly_tgt * 0.36), 1)

    focus_name_map = {
        "aerobic_base": "基础有氧扩容",
        "lactate_threshold": "乳酸阈值耐力提升",
        "vo2max_speed": "VO2Max 速度储备",
        "trail_climbing": "山地越野爬坡抗阻",
        "general_maintenance": "综合体能维持"
    }
    focus_name = focus_name_map.get(maintenance_focus or "aerobic_base", "基础有氧扩容")
    stage_round_counter: Dict[int, int] = {}

    for w_idx in range(1, weeks_count + 1):
        w_start = start_monday + timedelta(weeks=w_idx - 1)

        # Map w_idx to Canova Funnel Stage (0..7) so every week in 4/6/8/12w plans has a distinct stimulus
        if goal_type == "race_prep":
            if w_idx == weeks_count:
                stage_idx = 7  # Race Week
            elif w_idx == weeks_count - 1:
                stage_idx = 6  # Taper Week
            elif weeks_count == 4:
                stage_idx = 0 if w_idx == 1 else 4
            elif weeks_count == 6:
                stage_idx = [0, 1, 3, 4][min(w_idx - 1, 3)]
            elif weeks_count == 8:
                stage_idx = min(w_idx - 1, 5)  # 0, 1, 2, 3(Down), 4(Alternations), 5(Peak Specific)
            else:
                if w_idx % 4 == 0:
                    stage_idx = 3  # Down-week every 4th week
                else:
                    prog_ratio = w_idx / float(max(weeks_count - 2, 1))
                    if prog_ratio <= 0.34:
                        stage_idx = 0 if (w_idx % 2 == 1) else 1
                    elif prog_ratio <= 0.67:
                        stage_idx = 2 if (w_idx % 2 == 1) else 4
                    else:
                        stage_idx = 4 if (w_idx % 2 == 1) else 5
        else:
            # Non-race fitness maintenance still follows Canova 3+1 wave & progressive stimulus diversification
            if w_idx % 4 == 0:
                stage_idx = 3
            else:
                stage_idx = [0, 1, 2, 3, 4, 5, 1, 4][(w_idx - 1) % 8]

        # Canova Stage Metadata & Wave Load Multipliers
        stage_meta = {
            0: (
                "基础构建期 (Fundamental Phase)",
                f"第 {w_idx} 周 · Canova 基础有氧扩容与神经短冲激活",
                "建立宽厚低心率有氧底座 (80-85% MP) 与纯神经肌肉短坡/跨步招募，为后续专项负荷打底",
                0.94, 0.95, 0.94, 0.95
            ),
            1: (
                "基础转化期 (Introductive Special)",
                f"第 {w_idx} 周 · 有氧耐力延伸与 LT2 巡航初探",
                "Canova 漏斗两端初步向中间靠拢：周中引入短段落门槛巡航，周末长跑加入后程渐加速",
                1.00, 1.00, 1.00, 1.02
            ),
            2: (
                "专项准备期 (Special Period)",
                f"第 {w_idx} 周 · 乳酸门槛稳态延伸与混氧耐力",
                "拉长单组 LT2 阈值停留时长 (3×2500m)，周末长距离嵌入目标马配段落，提升糖原氧化效率",
                1.06, 1.05, 1.06, 1.08
            ),
            3: (
                "减量吸收周 (Modulation Down-week)",
                f"第 {w_idx} 周 · Canova 波浪减量与超量恢复周",
                "遵循 Canova 3:1 波浪负荷律，下调 20%~25% 跑量，以马配节奏感知跑替代高强间歇，促进肌糖原与结缔组织超量恢复",
                0.80, 0.82, 0.82, 0.78
            ),
            4: (
                "专项突破期 (Specific Alternations)",
                f"第 {w_idx} 周 · Canova 专项乳酸穿梭交替跑与模拟长距离",
                "核心引入 Canova 招牌「快慢配速连续交替跑 (Alternations)」，强化在 100% 比赛配速下清除并复用乳酸的能力",
                1.04, 1.08, 1.05, 1.12
            ),
            5: (
                "专项高峰期 (Peak Specific Block)",
                f"第 {w_idx} 周 · 100% 专项配速大容量巡航与巅峰拉练",
                "周期最高专项负荷周：周中 3×3000m 专项巡航 + 周末 Fast-Finish 专项大课，全面锤炼后半程抗掉速能力",
                1.10, 1.12, 1.08, 1.16
            ),
            6: (
                "赛前减量期 (Tapering)",
                f"第 {w_idx} 周 · 赛前渐进减量与神经张力保持",
                "削减 30%~35% 总跑量消除深层疲劳，保留少量 100% 目标配速短间歇维持肌肉弹性与步频经济性",
                0.76, 0.78, 0.75, 0.68
            ),
            7: (
                "比赛周 (Race Week)" if goal_type == "race_prep" else "周期转化测试周 (Peak Conversion)",
                f"第 {w_idx} 周 · {target_race_name} 巅峰之战" if goal_type == "race_prep" else f"第 {w_idx} 周 · 【{focus_name}】周期转化与达标检验",
                "充分蓄能超量恢复，赛前仅做短距离配速唤醒，周末全力兑现周期训练成果",
                0.65, 0.65, 0.65, 0.65
            ),
        }

        phase, w_title, w_focus, easy_mult, qual_mult, shake_mult, lr_mult = stage_meta[stage_idx]
        if goal_type != "race_prep" and stage_idx not in (3, 7):
            w_title = f"第 {w_idx} 周 · 【{focus_name}】{w_title.split('·')[-1].strip()}"

        # Long (12/16-week) plans revisit stages: progress volume per round and mark the week as advanced
        stage_round = stage_round_counter.get(stage_idx, 0)
        stage_round_counter[stage_idx] = stage_round + 1
        if stage_round > 0 and stage_idx not in (3, 6, 7):
            bump = 1.0 + 0.04 * stage_round
            qual_mult, lr_mult, easy_mult = qual_mult * bump, lr_mult * bump, easy_mult * (1.0 + 0.02 * stage_round)
            w_title = f"{w_title}（第{stage_round + 1}轮进阶）"

        easy_km = round(max(5.0, 8.5 * scale_f * easy_mult * 2.0) / 2.0, 1)
        quality_km = round(max(6.0, 11.0 * scale_f * qual_mult * 2.0) / 2.0, 1)
        shakeout_km = round(max(4.0, 6.5 * scale_f * shake_mult * 2.0) / 2.0, 1)
        lr_cap = 34.0 if not is_trail else 28.0
        lr_km = round(min(max(10.0, start_lr_dist * lr_mult * 2.0) / 2.0, lr_cap), 1)

        # Weekly rotating Tuesday workouts (Aerobic + Neuromuscular / Canova Speed Support)
        tue_variants = [
            (
                "easy_run",
                "基础有氧稳态跑 + 短坡神经冲刺 (Hill Sprints)",
                f"{easy_pace_low} - {easy_pace_high} /km",
                "心率 130-142 bpm (Zone 2)",
                f"低心率有氧慢跑 {max(3.0, round(easy_km - 1.0, 1))}km 扩充毛细血管网 + 跑后 6 组 × 80m 坡道全力短冲（慢走下坡恢复），按 Canova 理论纯激活快肌纤维而不堆积乳酸。"
            ),
            (
                "easy_run",
                "有氧扩展跑 + 跨步冲刺刚性激活 (Strides)",
                f"{easy_pace_low} - {easy_pace_high} /km",
                "心率 132-144 bpm (Zone 2)",
                f"热身 1km + {max(2.0, round(easy_km - 2.0, 1))}km Zone 2 稳态巡航 + 8 组 × 100m 轻快跨步跑 (@ {rep_pace}/km，间休 60 秒慢跑)，提升步频经济性。"
            ),
            (
                "interval" if days_per_week >= 6 else "easy_run",
                "Canova 速度耐力法特莱克 (Fartlek 变速激活)",
                f"{easy_pace_low} 穿插 {interval_pace} /km",
                "心率 138-162 bpm (Z2-Z4)",
                f"热身 2km + {max(2.0, round(easy_km - 3.5, 1))}km 有氧跑中穿插 6 组 × (90秒 @ {interval_pace}/km 快配 + 90秒慢跑恢复) + 冷身 1.5km，打通有氧与无氧过渡带。"
            ),
            (
                "easy_run",
                "减量周低心率恢复跑 + 髋踝灵活性体操",
                f"{easy_pace_high} /km",
                "心率 < 138 bpm (Zone 1-2)",
                f"减量吸收周轻松慢跑 {easy_km}km，全程压住心率深呼吸，结束后完成 15 分钟行进间高抬腿、后踢腿与髋关节绕环。"
            ),
            (
                "easy_run",
                "Canova 有氧支撑稳态跑 (Aerobic Support)",
                f"{aerobic_support_pace} - {easy_pace_low} /km",
                "心率 138-148 bpm (Zone 2 上沿)",
                f"热身 1.5km + {max(2.0, round(easy_km - 3.0, 1))}km 按 Canova 基础支撑配速 ({aerobic_support_pace}/km) 稳态推进 + 5 组 × 120m 渐速冲刺 + 冷身。"
            ),
            (
                "easy_run",
                "有氧巡航跑 + 末段马配神经切入",
                f"{easy_pace_low} 渐进至 {marathon_pace} /km",
                "心率 135-152 bpm (Z2-Z3)",
                f"前 {max(2.0, round(easy_km - 3.0, 1))}km 轻松有氧巡航，最后 3km 自然提速切入目标比赛配速 ({marathon_pace}/km)，强化疲劳前夕的配速体感。"
            ),
            (
                "easy_run",
                "赛前减量轻快跑 + 4×200m 步频锐化",
                f"{easy_pace_low} /km",
                "心率 130-140 bpm",
                f"轻松慢跑 {max(2.0, round(easy_km - 1.5, 1))}km + 4 组 × 200m 轻快节奏跑 (@ {interval_pace}/km，间休 90 秒)，保持下肢跟腱弹性且不消耗糖原。"
            ),
            (
                "easy_run",
                "赛前神经唤醒慢跑 + 4×100m 轻快加速",
                f"{easy_pace_low} - {easy_pace_high} /km",
                "心率 < 138 bpm",
                f"赛前周轻松唤醒跑 {easy_km}km，末段完成 4 组 × 100m 轻快加速跑，保持心肺与肌肉最佳兴奋度。"
            ),
        ]

        # Weekly rotating Wednesday workouts (Recovery + Phase-Specific Strength / Mobility)
        wed_variants = [
            ("排酸慢跑 + 骨盆与臀中肌稳定力量", f"极慢速恢复跑 {shakeout_km}km，跑后完成 15 分钟蚌式开合、侧桥与臀中肌抗阻训练，稳固落地骨盆姿态。"),
            ("主动恢复慢跑 + 单腿离心抗阻力量", f"低心率排酸跑 {shakeout_km}km，跑后完成单腿罗马尼亚硬拉、慢速离心提踵与核心平板 3 组，强化跟腱抗拉伤能力。"),
            ("轻松排酸跑 + 步频弹力带与足弓强化", f"放松慢跑 {shakeout_km}km（严禁拼配速），结束后完成足底抓毛巾、踝关节四向弹力带与核心抗旋练习。"),
            ("减量周极慢排酸跑 + 深度泡沫轴松解", f"吸收周超慢速恢复跑 {shakeout_km}km，跑后进行 25 分钟股四头肌、髂胫束与比目鱼肌深度筋膜松解。"),
            ("专项期恢复慢跑 + 保加利亚分腿蹲下肢抗疲劳", f"轻松排酸慢跑 {shakeout_km}km 促进毛细血管排酸，跑后完成自重保加利亚分腿蹲与臀桥 3 组。"),
            ("高峰周恢复慢跑 + 核心与躯干抗塌腰训练", f"大课前主动恢复慢跑 {shakeout_km}km，跑后针对性强化腹横肌死虫式与背肌支撑，防止全马后程核心散架。"),
            ("减量期唤醒慢跑 + 动态关节灵活性拉伸", f"赛前减量期轻松跑 {shakeout_km}km，暂停大重量力量训练，仅做 15 分钟全身动态拉伸与泡沫轴放松。"),
            ("赛前轻柔排酸慢跑 · 蓄能休整", f"轻松慢跑 {shakeout_km}km 活动下肢微循环，跑后温水泡脚并早睡储备糖原。"),
        ]

        # Weekly rotating Thursday workouts (The Core Canova Midweek Funnel Progression)
        mp_block_km = max(4.0, round(quality_km - 4.0, 1))
        alt_sets = max(3, min(6, int(round((quality_km - 3.5) / 2.0))))
        if is_trail:
            thu_variants = [
                ("trail_climb", "山地短坡抗阻冲刺 + 台阶步频专项", "坡度RPE 7-8", "心率 148-162 bpm",
                 f"热身 2km + 8~10 组 × 90秒陡坡强力推坡（慢跑下坡恢复，强化臀大肌与小腿推进）+ {max(1.0, round(quality_km - 5.0, 1))}km 台阶快步频 + 冷身。总量 {quality_km}km。"),
                ("trail_climb", "连续长坡爬升巡航 (LT1-LT2 垂直爬升)", "等强配速控制", "心率 148-160 bpm (LT1-LT2)",
                 f"热身 2km + 连续起伏长坡/台阶往返 {mp_block_km}km (目标累计爬升 +350~450m，上坡小步高频不爆心率，下坡练股四头肌离心缓冲) + 2km 冷身。"),
                ("trail_climb", "山野上下坡转换节奏跑 + 双杖推进专项", "山野混氧节奏", "心率 152-165 bpm (LT2)",
                 f"热身 2km + 3 组 × 2000m 起伏坡道混氧巡航（练习坡顶不降速直接切入平路/下坡巡航，熟练登山杖点地节奏）+ 2km 冷身，总量 {quality_km}km。"),
                ("easy_run", "减量周起伏地形有氧感知跑", f"{easy_pace_low} /km", "心率 135-148 bpm",
                 f"减量吸收周：选择微起伏路线舒适跑 {quality_km}km，专注下坡落脚点预判与呼吸节奏，不堆积深层肌肉微损伤。"),
                ("trail_climb", "Canova 山地变速交替跑 (爬坡+平路乳酸穿梭)", "上坡强推+平路快巡", "心率 155-168 bpm",
                 f"热身 2km + {alt_sets} 组 × (400m 坡道强攻 + 800m 平路按 {marathon_pace}/km 快速衔接不间休) + 冷身，专克越野赛刚上完坡双腿灌铅难题，总量 {quality_km}km。"),
                ("trail_climb", "高强度垂直爬升 D+ 专项 + 技术下坡抗震", "专项强负荷", "心率 155-166 bpm",
                 f"热身 2km + {mp_block_km}km 高密度爬升与技术下坡拉练（目标爬升 +500m+，重点检验疲惫态下踝膝稳定与高频小步下坡）+ 2km 冷身。"),
                ("trail_climb", "赛前减量山野节奏唤醒跑", "轻快等强配速", "心率 142-155 bpm",
                 f"热身 2km + 3 组 × 1200m 缓坡轻快巡航 + 平路放松跑，总量 {quality_km}km，保持山野肌肉记忆与关节灵活。"),
                ("easy_run", "赛前平路/微坡轻快唤醒跑", f"{easy_pace_low} /km", "心率 < 142 bpm",
                 f"赛前唤醒慢跑 {quality_km}km，穿戴正式比赛越野鞋与背包贴合测试，跑后充分拉伸休息。"),
            ]
        elif maintenance_focus == "vo2max_speed":
            thu_variants = [
                ("interval", f"场地短间歇速度激活 (10 × 400m · {quality_km}km)", f"{rep_pace} /km", "心率 165-176 bpm",
                 f"热身 2km + 行进间身训 + 10 × 400m @ {rep_pace}/km (间休 75 秒慢跑) + 冷身，提升神经招募与最大摄氧量跑姿经济性，总量 {quality_km}km。"),
                ("interval", f"VO2Max 亚索800经典间歇 (6 × 800m · {quality_km}km)", f"{interval_pace} /km", "心率 166-176 bpm (Zone 4/5)",
                 f"热身 2km + 6 × 800m @ {interval_pace}/km (间休 2 分钟慢跑) + 冷身放松，拉升心肺每搏输出量，总量 {quality_km}km。"),
                ("interval", f"VO2Max 千米摄氧量冲击 (5~6 × 1000m · {quality_km}km)", f"{interval_pace} /km", "心率 168-178 bpm (Zone 5)",
                 f"热身 2km + 6 × 1000m @ {interval_pace}/km (间休 2 分钟慢走/慢跑) + 冷身，强化最大摄氧量平台停留时长，总量 {quality_km}km。"),
                ("tempo", f"减量周法特莱克节奏感知跑 ({quality_km}km)", f"{tempo_pace} - {marathon_pace} /km", "心率 150-162 bpm",
                 f"热身 2km + 6 组 × (2分钟 @ {tempo_pace}/km + 2分钟有氧慢跑) + 冷身，在减量周维持速度感同时消除中枢神经疲劳。"),
                ("interval", f"Canova 混氧金字塔间歇 (400-800-1200-1600-800-400m)", f"{interval_pace} - {tempo_pace} /km", "心率 164-176 bpm",
                 f"热身 2km + 金字塔变速间歇 (400m/800m @ {interval_pace} + 1200m/1600m @ {tempo_pace} + 800m/400m 冲刺) + 冷身，总量 {quality_km}km。"),
                ("interval", f"Canova 长段落混氧强间歇 (4 × 1600m · {quality_km}km)", f"{interval_pace} - {tempo_pace} /km", "心率 165-175 bpm",
                 f"热身 2km + 4 × 1600m @ {interval_pace}~{tempo_pace}/km (间休 2分30秒慢跑) + 冷身，把高速度储备转化为长距离抗乳酸耐力，总量 {quality_km}km。"),
                ("interval", f"减量期速度锐化间歇 (5 × 600m · {quality_km}km)", f"{interval_pace} /km", "心率 162-172 bpm",
                 f"热身 2km + 5 × 600m @ {interval_pace}/km (间休 2 分钟充分恢复) + 冷身，削减容量但维持巅峰步频张力，总量 {quality_km}km。"),
                ("easy_run", f"转化周轻快配速唤醒 ({quality_km}km)", f"{marathon_pace} /km", "心率 145-155 bpm",
                 f"热身 2km + 3 × 800m @ {marathon_pace}/km (间休 90 秒) + 冷身，保持轻盈跑感迎接测试或比赛。"),
            ]
        else:
            # Standard Canova Road Marathon / Half / Threshold Funnel Progression
            thu_variants = [
                ("tempo", f"Canova 有氧耐力渐速跑 (Progressive Run · {quality_km}km)", f"{easy_pace_low} 渐进至 {marathon_pace} /km", "心率 142-160 bpm (Z2→Z3)",
                 f"热身 2km + {mp_block_km}km 连续渐速跑（从 {easy_pace_low}/km 起步，每 2km 提速约 8 秒，末段达到 {marathon_pace}/km）+ 2km 冷身，温和唤醒有氧代谢酶。"),
                ("tempo", f"乳酸门槛巡航短间歇 (4 × 1600m @ LT2 · {quality_km}km)", f"{tempo_pace} /km", "心率 154-164 bpm (LT2)",
                 f"热身 2km + 4 × 1600m @ {tempo_pace}/km (组间 90 秒慢跑恢复) + 冷身。通过短间休分段积累 LT2 阈值停留时间，总量 {quality_km}km。"),
                ("tempo", f"乳酸门槛稳态延伸 (3 × 2500m @ LT2 · {quality_km}km)", f"{tempo_pace} /km", "心率 156-166 bpm (LT2)",
                 f"热身 2km + 3 × 2500m @ {tempo_pace}/km (间歇 2分30秒慢跑) + 冷身。拉长单组抗乳酸巡航距离，强化乳酸清除耐受力，总量 {quality_km}km。"),
                ("tempo", f"减量周马配稳态节奏感知跑 ({quality_km}km)", f"{marathon_pace} /km", "心率 148-158 bpm (Zone 3)",
                 f"热身 2km + {max(3.0, round(quality_km - 4.0, 1))}km 按目标比赛配速 ({marathon_pace}/km) 轻松稳态巡航 + 2km 冷身。减量周不追极限强度，专注呼吸与跑姿经济性。"),
                ("interval", f"Canova 专项乳酸穿梭交替跑 (Alternations · {quality_km}km)", f"{fast_mp_pace} 与 {sub_mp_pace} 交替", "心率 155-168 bpm (LT1-LT2交替)",
                 f"热身 2km + 连续 {alt_sets} 组 × (1km @ {fast_mp_pace}/km 稍快于马配 + 1km @ {sub_mp_pace}/km 浮游巡航不降速恢复) + 冷身。Canova 核心课目：训练肌肉在高配速下直接将乳酸作为燃料复用！"),
                ("tempo", f"Canova 专项长段落巡航 (3 × 3000m @ LT2/MP · {quality_km}km)", f"{tempo_pace} - {marathon_pace} /km", "心率 156-166 bpm (LT2)",
                 f"热身 2km + 3 × 3000m @ {tempo_pace}~{marathon_pace}/km (组间 800m 按 {aerobic_support_pace}/km 浮游慢跑衔接) + 冷身。直击比赛 30km 后抗掉速专项耐力，总量 {quality_km}km。"),
                ("tempo", f"赛前减量专项锐化跑 (3 × 1600m @ MP · {quality_km}km)", f"{marathon_pace} /km", "心率 150-160 bpm (Zone 3)",
                 f"热身 2km + 3 × 1600m @ {marathon_pace}/km (间休 2 分钟慢跑) + 冷身。削减总负荷但精准锁死比赛目标配速肌肉记忆，总量 {quality_km}km。"),
                ("easy_run", f"赛前专项配速唤醒跑 (MP Dress Rehearsal · {quality_km}km)", f"{marathon_pace} /km", "心率 142-154 bpm",
                 f"热身 2km + 2km 按目标比赛配速 ({marathon_pace}/km) 轻快巡航体验 + 冷身慢跑，检验参赛鞋袜与心率响应，保持最佳满糖原状态。"),
            ]

        # Weekly rotating Saturday workouts (Pre-Long-Run Shakeout / Drills)
        sat_variants = [
            ("周末前唤醒轻松跑 + 关节活动度", f"轻松舒适慢跑 {shakeout_km}km，活动髋膝踝关节与心肺神经，不堆积任何疲劳。"),
            ("长距离前热身慢跑 + 行进间技术体操", f"低心率慢跑 {shakeout_km}km + 跑后完成高抬腿、小步跑、后踢腿技术体操各 2×30m，优化次日长跑触地效率。"),
            ("Canova 预疲劳有氧慢跑 (Pre-Fatigue Shakeout)", f"稳态有氧慢跑 {shakeout_km}km（末段含 4×80m 跨步跑），适度预耗浅层糖原以强化次日长距离脂肪动员能力。"),
            ("减量周轻柔恢复慢跑", f"减量周极轻松慢跑 {shakeout_km}km，全程体感舒适，跑后早睡补碳水。"),
            ("专项大课前唤醒跑 + 4×100m 跨步激活", f"轻松慢跑 {max(3.0, round(shakeout_km - 0.5, 1))}km + 4 组 100m 轻快跨步冲刺，唤醒神经募集迎接次日专项长距离。"),
            ("高峰长距离前蓄能慢跑", f"控制心率在 135 bpm 以下完成 {shakeout_km}km 唤醒跑，准备好次日大课能量胶与电解质盐丸。"),
            ("赛前减量短程唤醒跑", f"轻快慢跑 {shakeout_km}km，活动筋骨，保持良好跑感。"),
            ("赛前一日神经唤醒跑 (Pre-Race Shakeout)", f"超短距离唤醒慢跑 {min(4.0, shakeout_km)}km + 2×80m 轻快加速，检查参赛号码布、芯片与补给胶。"),
        ]

        # Weekly rotating Sunday Long Run workouts (The Canova Specific Long Run Funnel)
        lr_first_65 = round(lr_km * 0.65, 1)
        lr_last_35 = round(lr_km - lr_first_65, 1)
        lr_first_60 = round(lr_km * 0.60, 1)
        lr_last_40 = round(lr_km - lr_first_60, 1)
        mp_seg_km = max(3.0, min(6.0, round(lr_km * 0.20, 0)))

        sun_variants = [
            (
                f"Canova 基础有氧稳态长距离 (General LSD - {lr_km}km)",
                f"{easy_pace_low} - {easy_pace_high} /km",
                "心率 132-145 bpm (Zone 2)",
                f"全程 {lr_km}km 保持在 {easy_pace_low}~{easy_pace_high}/km 低心率稳态巡航，严禁前半程起跑过快，专注慢肌纤维毛细血管扩容与脂肪供能效率。"
            ),
            (
                f"Canova 渐进加速长距离 (Progressive Long Run - {lr_km}km)",
                f"{easy_pace_low} 渐进至 {sub_mp_pace} /km",
                "心率 135-154 bpm (Z2→Z3)",
                f"前 {lr_first_65}km 稳守 {easy_pace_low}/km 低心率有氧，后 {lr_last_35}km 渐进提速至 {sub_mp_pace}/km（约 95% 目标配速），演练每 45 分钟补胶与饮水。"
            ),
            (
                f"Canova 分段专项长距离 (2×{int(mp_seg_km)}km MP 嵌入 - {lr_km}km)",
                f"{easy_pace_low} 穿插 {marathon_pace} /km",
                "心率 138-158 bpm (Z2-Z3)",
                f"总长 {lr_km}km：前段有氧热身巡航，中后段嵌入 2 组 × {int(mp_seg_km)}km @ {marathon_pace}/km 目标比赛配速（组间 2km 按 {easy_pace_low}/km 慢跑过渡），建立长距离下的专项配速定力。"
            ),
            (
                f"减量吸收周有氧恢复长跑 (Recovery LSD - {lr_km}km)",
                f"{easy_pace_low} - {easy_pace_high} /km",
                "心率 130-142 bpm (Zone 2)",
                f"周期减量吸收周：轻松完成 {lr_km}km 纯有氧耐力跑，不设配速硬指标，让前 3 周累积的肌纤维微损伤与肝糖原实现超量恢复。"
            ),
            (
                f"Canova 专项后程切入长距离 (Fast-Finish Long Run - {lr_km}km)",
                f"{aerobic_support_pace} 切入 {marathon_pace} /km",
                "心率 140-162 bpm (Z2→Z3上沿)",
                f"前 {lr_first_60}km 按 {aerobic_support_pace}/km 有氧支撑配速稳态推进，后 {lr_last_40}km 果断连续切入 100% 目标比赛配速 ({marathon_pace}/km)，模拟比赛 25km 后体能临界点实战！"
            ),
            (
                f"Canova 巅峰专项模拟大课 (Specific Block Long Run - {lr_km}km)",
                f"{aerobic_support_pace} 渐进至 {marathon_pace} /km",
                "心率 142-164 bpm (专项心率区间)",
                f"周期巅峰大课 {lr_km}km：前 {round(lr_km * 0.5, 1)}km 稳态有氧，后 {round(lr_km * 0.5, 1)}km 执行 Canova 专项推进（每 4km @ {marathon_pace}/km + 1km @ {sub_mp_pace}/km 连续巡航），全真演练赛时装备与每 40 分钟补给。"
            ),
            (
                f"赛前减量期中长距离跑 (Taper Medium-Long Run - {lr_km}km)",
                f"{easy_pace_low} 末段 {marathon_pace} /km",
                "心率 135-150 bpm",
                f"赛前减量期 {lr_km}km：前 {max(6.0, round(lr_km - 3.0, 1))}km 轻松有氧慢跑，最后 3km 轻快提至 {marathon_pace}/km 点到为止，保持心肺张力且零疲劳累积。"
            ),
            (
                f"🏁 目标赛事正赛：{target_race_name} 突破之战！" if goal_type == "race_prep" else f"🏁 周期结业专项达标拉练 ({lr_km}km)",
                f"{marathon_pace} /km",
                "按比赛战术心率执行",
                f"前程克制压住心率，半程后依靠扎实糖原储备稳步加速收敛，直击 {target_time_str} 目标！" if goal_type == "race_prep" else f"检验 {weeks_count} 周 Canova 周期训练成果，按目标配速稳健完成 {lr_km}km 周期综合拉练！"
            ),
        ]

        days_list = []
        for d_idx in range(7):
            cur_date = (w_start + timedelta(days=d_idx)).isoformat()
            d_name = days_labels[d_idx]

            if d_idx == 0:  # Monday: Rest (or Active Recovery if 6 days/week)
                if days_per_week >= 6 and stage_idx not in (3, 6, 7):
                    mon_km = max(4.0, round(shakeout_km * 0.85, 1))
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "easy_run",
                        "title": "大课后主动排酸慢跑 + 泡沫轴松解",
                        "distance_km": mon_km,
                        "target_pace": f"{easy_pace_high} /km",
                        "target_hr_zone": "心率 < 135 bpm (Zone 1)",
                        "description": f"周末长距离后主动恢复慢跑 {mon_km}km，全程极慢速放松步频，跑后 20 分钟泡沫轴放松股四头肌与小腿。",
                        "completed": False,
                        "coach_notes": ""
                    }
                else:
                    mon_notes = [
                        "彻底休息，配合泡沫轴滚动股四头肌外侧与小腿三头肌，促进微肌纤维超量恢复。",
                        "完全跑休，进行 15 分钟髋关节与腘绳肌温和静态拉伸，保证 8 小时深度睡眠。",
                        "大课后跑休，重点用筋膜球滚压足底筋膜与跟腱周围，补充优质蛋白。",
                        "减量吸收周首日完全跑休，监测晨起静息心率与 HRV 回升情况。",
                    ]
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "rest",
                        "title": "完全休息 / 筋膜泡沫轴放松",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "—",
                        "description": mon_notes[(w_idx - 1) % len(mon_notes)],
                        "completed": False,
                        "coach_notes": ""
                    }
            elif d_idx == 1:  # Tuesday: Aerobic + Neuromuscular / Speed Support
                t_type, t_title, t_pace, t_hr, t_desc = tue_variants[stage_idx]
                w_item = {
                    "day_of_week": d_name,
                    "date": cur_date,
                    "workout_type": t_type,
                    "title": t_title,
                    "distance_km": easy_km,
                    "target_pace": t_pace,
                    "target_hr_zone": t_hr,
                    "description": t_desc,
                    "completed": False,
                    "coach_notes": ""
                }
            elif d_idx == 2:  # Wednesday: Active Recovery + Rotating Strength (if >=5 days) or Rest
                if days_per_week >= 5:
                    wed_title, wed_desc = wed_variants[stage_idx]
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "easy_run",
                        "title": wed_title,
                        "distance_km": shakeout_km,
                        "target_pace": f"{easy_pace_high} /km",
                        "target_hr_zone": "心率 < 135 bpm",
                        "description": wed_desc,
                        "completed": False,
                        "coach_notes": ""
                    }
                else:
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "rest",
                        "title": "大师组周期休整日 (Active Recovery)" if is_masters else "周中休整与核心激活日",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "—",
                        "description": "遵循 72 小时大课恢复窗口，不安排路跑；居家完成 15 分钟核心平板支撑与臀中肌激活，为周四重点课蓄能。",
                        "completed": False,
                        "coach_notes": ""
                    }
            elif d_idx == 3:  # Thursday: Key Canova Midweek Funnel Workout
                q_type, q_title, q_pace, q_hr, q_desc = thu_variants[stage_idx]
                w_item = {
                    "day_of_week": d_name,
                    "date": cur_date,
                    "workout_type": q_type,
                    "title": q_title,
                    "distance_km": quality_km,
                    "target_pace": q_pace,
                    "target_hr_zone": q_hr,
                    "description": q_desc,
                    "completed": False,
                    "coach_notes": ""
                }
            elif d_idx == 4:  # Friday: Rest & Glycogen Loading
                fri_notes = [
                    "周四重点课后完全跑休，消除乳酸与神经疲劳，晚餐增加复合碳水化合物储备。",
                    "完全休息，为周末 Canova 长距离大课储备肌糖原，早睡并补充电解质水。",
                    "跑休蓄能日，可进行 10 分钟轻柔泡沫轴放松小腿比目鱼肌，切勿熬夜。",
                ]
                w_item = {
                    "day_of_week": d_name,
                    "date": cur_date,
                    "workout_type": "rest",
                    "title": "完全休息 / 周末大课前糖原蓄能",
                    "distance_km": 0.0,
                    "target_pace": "—",
                    "target_hr_zone": "—",
                    "description": fri_notes[(w_idx - 1) % len(fri_notes)],
                    "completed": False,
                    "coach_notes": ""
                }
            elif d_idx == 5:  # Saturday: Shakeout + Drills (if >=4 days) or Rest (if 3 days)
                if days_per_week >= 4:
                    sat_title, sat_desc = sat_variants[stage_idx]
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "easy_run",
                        "title": sat_title,
                        "distance_km": shakeout_km,
                        "target_pace": f"{easy_pace_low} - {easy_pace_high} /km",
                        "target_hr_zone": "心率 128-138 bpm",
                        "description": sat_desc,
                        "completed": False,
                        "coach_notes": ""
                    }
                else:
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "rest",
                        "title": "大课前休整日",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "—",
                        "description": "彻底休息，准备次日关键长距离。",
                        "completed": False,
                        "coach_notes": ""
                    }
            else:  # Sunday: The Canova Specific Long Run Progression
                if stage_idx == 7 and goal_type == "race_prep":
                    race_km = 42.2 if ("全马" in target_race_name or "马拉松" in target_race_name) else (21.1 if "半马" in target_race_name else (50.0 if is_trail else lr_km))
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "long_run",
                        "title": f"🏁 目标赛事正赛：{target_race_name} 突破之战！",
                        "distance_km": race_km,
                        "target_pace": f"{marathon_pace} /km",
                        "target_hr_zone": "按比赛战术心率执行",
                        "description": f"前程克制压住心率，半程后依靠扎实糖原储备稳步加速收敛，直击 {target_time_str} 目标！",
                        "completed": False,
                        "coach_notes": ""
                    }
                elif is_trail:
                    trail_elev = int(round(lr_km * (45 + (stage_idx % 4) * 10), -1))
                    trail_sun_titles = [
                        f"山野有氧耐力拉练 ({lr_km}km · 爬升+{trail_elev}m)",
                        f"山野长坡推进与技术下坡拉练 ({lr_km}km · 爬升+{trail_elev}m)",
                        f"山野全装备补给模拟拉练 ({lr_km}km · 爬升+{trail_elev}m)",
                        f"减量周山野轻快有氧跑 ({lr_km}km · 爬升+{int(trail_elev*0.7)}m)",
                        f"Canova 山野分段变速长距离 ({lr_km}km · 爬升+{trail_elev}m)",
                        f"百公里/越野巅峰模拟拉练 ({lr_km}km · 爬升+{trail_elev}m)",
                        f"赛前减量山野唤醒跑 ({lr_km}km)",
                        f"山野周期综合达标拉练 ({lr_km}km)",
                    ]
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "long_run",
                        "title": trail_sun_titles[stage_idx],
                        "distance_km": lr_km,
                        "target_pace": "按地形等强心率控制",
                        "target_hr_zone": "心率 135-155 bpm (Z2-Z3)",
                        "description": f"进山完成 {lr_km}km 越野专项长距离（累计爬升约 +{trail_elev}m）：上坡高效使用登山杖节省股四头肌，下坡高频小步轻柔落地，严格执行每 45 分钟摄入能量胶/盐丸演练肠胃耐受。",
                        "completed": False,
                        "coach_notes": ""
                    }
                else:
                    s_title, s_pace, s_hr, s_desc = sun_variants[stage_idx]
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "long_run",
                        "title": s_title,
                        "distance_km": lr_km,
                        "target_pace": s_pace,
                        "target_hr_zone": s_hr,
                        "description": s_desc,
                        "completed": False,
                        "coach_notes": ""
                    }

            days_list.append(w_item)

        if stage_round > 0:
            adv_label = f"第{stage_round + 1}次吸收" if stage_idx in (3, 6) else f"第{stage_round + 1}轮进阶"
            for adv_d in days_list:
                if adv_d.get("workout_type") in ("interval", "tempo", "long_run", "trail_climb", "easy_run") and adv_d.get("day_of_week") in ("周二", "周四", "周日"):
                    adv_d["title"] = f"{adv_d['title']} · {adv_label}"

        total_week_km = round(sum(d["distance_km"] for d in days_list), 1)
        weeks.append({
            "week_index": w_idx,
            "week_title": w_title,
            "phase": phase,
            "weekly_mileage_km": total_week_km,
            "key_focus": w_focus,
            "days": days_list
        })

    focus_cn = focus_name_map.get(maintenance_focus or "aerobic_base", "非赛期专项强化")

    target_display = target_race_name if goal_type == "race_prep" else focus_cn
    title = f"{athlete_name} · {target_display} {weeks_count}周 Canova 周期训练计划"
    if age and age >= 50:
        age_str = "大师组超量恢复律"
    elif age:
        age_str = f"{age}岁恢复律"
    else:
        age_str = "常规生理恢复律"
    summary = f"严格结合跑者真实生理画像（{age_str}、VO2Max {vdot or 50.0}），参考过去18个月历史长拉练能力（单次最长 {max_long_run_18m_km}km），遵循 Renato Canova 漏斗周期理论（基础有氧→门槛延伸→乳酸穿梭交替→专项模拟→减量巅峰）逐周演进。"
    res_plan = {
        "macro_cycle_name": title,
        "goal_summary": summary,
        "weeks": weeks
    }
    if scheduled_races:
        res_plan = integrate_scheduled_races_into_schedule(
            schedule_data=res_plan,
            scheduled_races=scheduled_races,
            age=age,
            vdot=vdot
        )

    return res_plan


@router.post("/plan/generate")
def generate_scientific_training_plan(req: GenerateTrainingPlanRequest):
    """
    Generates an individualized, periodized Canova & Daniels training plan for the runner,
    incorporating athlete biometrics, CTL/ATL/TSB, PBs, and 12-18 months of real race & long run history.
    """
    eff_uid = req.athlete_uid or req.uid or req.user_id or ""
    canonical_uid = LocalStore.resolve_user_id(eff_uid)
    user_profile = LocalStore.get_profile(canonical_uid) or {}
    runner_name = user_profile.get("display_name") or user_profile.get("email", "").split("@")[0] or "跑者"
    gender = str(user_profile.get("gender") or "male")
    gender_zh = "女" if gender.lower() == "female" else "男"
    dob_str = user_profile.get("date_of_birth")
    age = get_age_from_dob(dob_str)
    
    # Biometrics & VO2Max (strictly prioritize watch VO2Max without recalculating)
    health = LocalStore.get_latest_health(canonical_uid) or {}
    vo2max = health.get("vo2_max") or user_profile.get("vo2max")
    has_watch_vo2 = bool(
        health.get("vo2_max")
        or (
            user_profile.get("vo2max")
            and any(user_profile.get(k) for k in ("garmin_connected", "coros_connected", "apple_health_connected", "huawei_health_connected"))
        )
    )
    vo2max_source = "watch" if has_watch_vo2 else ("profile" if vo2max else "estimated")

    marathon_pb = user_profile.get("marathon_pb")
    half_pb = user_profile.get("half_pb")
    ten_k_pb = user_profile.get("ten_k_pb")
    five_k_pb = user_profile.get("five_k_pb")

    if vo2max:
        vo2max = round(float(vo2max), 1)
    else:
        # Only fall back to PB calculation when no watch/profile VO2Max is available
        if marathon_pb:
            mp_sec = parse_time_str(str(marathon_pb))
            v_calc = calculate_vdot(42195.0, float(mp_sec)) if mp_sec and mp_sec > 0 else None
            vo2max = round(v_calc, 1) if v_calc else 50.0
        elif half_pb:
            hp_sec = parse_time_str(str(half_pb))
            v_calc = calculate_vdot(21097.5, float(hp_sec)) if hp_sec and hp_sec > 0 else None
            vo2max = round(v_calc, 1) if v_calc else 50.0
        else:
            vo2max = 48.0

    # Training Load CTL/ATL/TSB
    load_metrics = LocalStore.get_training_load(canonical_uid, days=90)
    ctl = load_metrics.get("ctl", 0.0)
    atl = load_metrics.get("atl", 0.0)
    tsb = load_metrics.get("tsb", 0.0)
    acwr = load_metrics.get("acwr", 0.0)
    tsb_status = load_metrics.get("status", "稳健")

    # 12-18 months (540 days) real race and long run history
    history_18m = LocalStore.extract_runner_race_history(canonical_uid, days=540)

    # Fetch runner's self-defined goals (weekly target & monthly targets)
    user_goal = LocalStore.get_goal(canonical_uid) or {}
    user_weekly_target = float(req.user_weekly_target or user_goal.get("weekly_target") or 50.0)
    user_monthly_target = float(user_goal.get("target_distance") or (user_weekly_target * 4.0))

    # Resolve target and race details (auto-resolve from runner's registered races if not explicitly specified)
    race_ctx = resolve_athlete_race_context(canonical_uid)
    auto_goal_race = race_ctx.get("goal_race") or race_ctx.get("next_race")

    goal_type = req.goal_type or ("race_prep" if auto_goal_race else "race_prep")
    target_race_name = req.target_race_name
    target_time_str = req.target_time
    eff_target_date = req.target_date
    eff_race_type = req.race_type

    if (not target_race_name or target_race_name == "目标赛事") and auto_goal_race:
        target_race_name = auto_goal_race.get("name") or "目标赛事"
        if not target_time_str and auto_goal_race.get("target_time"):
            target_time_str = auto_goal_race.get("target_time")
        if not eff_target_date and auto_goal_race.get("race_date"):
            eff_target_date = str(auto_goal_race.get("race_date"))[:10]
        if not eff_race_type and auto_goal_race.get("race_type"):
            eff_race_type = auto_goal_race.get("race_type")

    target_race_name = target_race_name or "目标赛事"
    target_time_str = target_time_str or "3:15:00"
    target_time_sec = parse_time_str(target_time_str)

    race_category, race_category_name = resolve_race_category(target_race_name, eff_race_type, target_time_sec)

    # Date and weeks calculation
    today = date.today()
    # Find next Monday (or today if today is Monday)
    start_monday = today - timedelta(days=today.weekday())  # Current week Monday

    weeks_count = req.weeks_count or req.weeks or 8
    if eff_target_date and goal_type == "race_prep" and not req.weeks and not req.weeks_count:
        try:
            t_date = datetime.strptime(eff_target_date[:10], "%Y-%m-%d").date()
            diff_days = (t_date - start_monday).days
            calc_weeks = max(4, min(16, (diff_days + 6) // 7))
            weeks_count = calc_weeks
        except Exception:
            pass

    end_date = (start_monday + timedelta(weeks=weeks_count) - timedelta(days=1)).isoformat()
    start_date = start_monday.isoformat()

    days_per_week = req.days_per_week or 4
    maintenance_focus = req.maintenance_focus or "aerobic_base"

    # Fetch runner's already scheduled upcoming races within the period
    all_scheduled_races = LocalStore.get_race_plans(canonical_uid)
    active_scheduled_races = [
        r for r in all_scheduled_races 
        if r.get("race_date") and start_date <= str(r["race_date"])[:10] <= end_date and not r.get("is_completed") and r.get("status") != "completed"
    ]

    # Age category prompt description & Masters Privacy Protection
    if age is None:
        age_desc = "常规生理机能（按 48 小时常规恢复窗口规划）"
    elif age < 35:
        age_desc = f"{age} 岁 (青年组 - 恢复快，大课恢复窗口 48 小时，耐受专项密度高)"
    elif age < 50:
        age_desc = f"{age} 岁 (中壮年组 - 大课恢复窗口需 48~72 小时，增加筋膜维护)"
    else:
        # Strict privacy protection for Masters
        age_desc = "大师组 (Masters - 肌肉胶原与糖原合成较缓，大课后需保留 72~96 小时超量恢复窗口，坚决执行 Hard-Easy 规律，防肌肉流失与关节损伤。严禁在计划中直接输出具体周岁数字)"

    plan_tier_key, plan_tier_instruction = resolve_runner_tier(user_profile, ctl)

    scheduled_races_prompt = []
    for r in active_scheduled_races:
        raw_p = str(r.get("priority", 1)).upper()
        p_label = "A 标 (巅峰核心目标)" if raw_p in ["1", "A"] else ("B 标 (以赛代练)" if raw_p in ["2", "B"] else "C 标 (模拟拉练赛)")
        scheduled_races_prompt.append(
            f"- 赛事名称: {r.get('name')} | 比赛日期: {str(r.get('race_date'))[:10]} | 组别: {r.get('race_type', '赛事')} | 目标时间: {r.get('target_time') or '稳态完赛'} | 定位: {p_label}"
        )

    scheduled_races_section = ""
    if scheduled_races_prompt:
        scheduled_races_section = f"""
【！！！极重要硬性要求：必须将以下跑者已排定的真实比赛精准融合进训练计划中！！！】
该跑者在计划周期内已经报名/安排了以下 {len(active_scheduled_races)} 场比赛：
{chr(10).join(scheduled_races_prompt)}

执行规则：
1. 比赛当天精准落位：必须在比赛当天的具体日期（例如 2026-09-12 周六）将当天的课目设为该比赛（workout_type: "race"），标题写为“【比赛日】赛事名称 (A/B/C 标)”，里程填写真实比赛公里数（如 50km），并针对性给出配速/心率说明；
2. 赛后超量恢复绝对阻断：比赛次日（例如 9/12 比赛，9/13 周日）坚决严禁再安排任何长距离大课！必须设为 workout_type: "rest" (0km)；
3. 替代当周长跑负荷：比赛本身即充当当周的关键大课，当周切勿重复堆积周末长跑；
4. 赛前减量与休整：赛前一天设为赛前休整或 3km 神经激活跑 (Shakeout)；
5. 周标题与重点对齐：包含比赛的周度，其 week_title 和 key_focus 必须显式体现该场实战拉练比赛。
"""

    coach_custom_section = ""
    if req.coach_notes_prompt and str(req.coach_notes_prompt).strip():
        coach_custom_section = f"""
【！！！跑团主教练针对该队员的专项指导指令（最高优先级遵循）！！！】
主教练要求：{str(req.coach_notes_prompt).strip()}
请在周重点 (key_focus)、总评 (goal_summary) 及每日具体课表安排中严格贯彻主教练的上述要求！
"""

    # Build prompt context
    user_context = f"""
跑者真实画像：
- 姓名/昵称: {runner_name}
- 性别: {gender_zh} | 生理组别: {age_desc}
- 队员能力分层与执教话术指引:
{plan_tier_instruction}
- VO2Max (最大摄氧量): {vo2max}
- 个人最好成绩 (PB):
  * 全马 PB: {format_duration(marathon_pb)}
  * 半马 PB: {format_duration(half_pb)}
  * 10K PB: {format_duration(ten_k_pb)}
  * 5K PB: {format_duration(five_k_pb)}

即时疲劳负荷监测 (Banister EWMA 模型):
- 长期体能 CTL: {ctl}
- 短期疲劳 ATL: {atl}
- 状态平衡指数 TSB: {tsb} ({tsb_status})
- 急慢性负荷比 ACWR: {acwr}

过去 12~18 个月 (540天) 比赛与长跑历史实战表现 (真实打卡记录):
- 过去 1.5 年总跑步活动数: {history_18m.get('total_activities_count')} 次 (总里程: {history_18m.get('total_distance_km')} km)
- 过去 1.5 年长距离 (≥15km) 次数: {history_18m.get('long_runs_count')} 次
- 过去 1.5 年单次最长实跑距离: {history_18m.get('max_single_distance_km')} km
- 过去 1.5 年参加的真实比赛/高强度测验 (前5次):
{json.dumps(history_18m.get('recent_races', [])[:5], ensure_ascii=False, indent=2)}
- 过去 1.5 年长跑拉练记录 (前5次):
{json.dumps(history_18m.get('recent_long_runs', [])[:5], ensure_ascii=False, indent=2)}
- 山地越野/爬坡活动: {len(history_18m.get('trail_climbing_runs', []))} 次

训练目标设定与自定跑量基准：
- 跑者自定周跑量目标 (Weekly Target): {user_weekly_target} km/周
- 跑者自定月跑量目标 (Monthly Target): {user_monthly_target} km/月
- 目标对齐核心要求：课表的基准总跑量必须与跑者的自定周目标 ({user_weekly_target} km) 科学收敛对齐！第 1 周起始跑量收敛在 ±5%~10%（约 {round(user_weekly_target * 0.95, 1)} ~ {round(user_weekly_target * 1.05, 1)} km），减量周下浮至 70%~75%（约 {round(user_weekly_target * 0.72, 1)} km），其余常规训练周以波浪式渐进递增（周增幅 ≤ 10%）。
- 目标类型: {'赛事备赛 (race_prep)' if goal_type == 'race_prep' else '非赛季体能进阶 (fitness_maintenance)'}
- 目标赛事: {target_race_name} (类别: {race_category_name}, 目标成绩: {target_time_str})
- 非赛期专项焦点: {maintenance_focus}
- 训练周期: {weeks_count} 周 (起始日期: {start_date}, 结束/比赛日期: {end_date})
- 每周训练跑步天数: {days_per_week} 天 (其余天数为完全休息或交叉放松)
- 长跑日偏好: {req.preferred_long_run_day or 'Sunday'}
{scheduled_races_section}
{coach_custom_section}
请根据以上跑者的真实生理承受力、历史表现、自定目标与既定赛历，为跑者生成包含第 1 周到第 {weeks_count} 周的完整周度/日度训练课表。直接输出标准 JSON。
"""

    messages = [
        {"role": "system", "content": CANOVA_PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user_context}
    ]

    schedule_data = None
    if not req.use_fast_engine:
        try:
            raw_output = llm_client.chat_completion(messages=messages, temperature=0.7)
            clean_json = raw_output.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
            schedule_data = json.loads(clean_json)
            
            # Verify structure integrity
            if not schedule_data.get("weeks") or len(schedule_data.get("weeks")) == 0:
                schedule_data = None
        except Exception as e:
            logger.warning(f"[coach_plan] LLM generation error/fallback: {e}")
            schedule_data = None

    if not schedule_data:
        # Generate robust, realistic Canova schedule dynamically
        schedule_data = generate_fallback_training_plan(
            athlete_name=runner_name,
            goal_type=goal_type,
            target_race_name=target_race_name,
            target_time_str=target_time_str,
            race_category=race_category,
            maintenance_focus=maintenance_focus,
            weeks_count=weeks_count,
            days_per_week=days_per_week,
            start_monday=start_monday,
            vdot=vo2max,
            pb_marathon_sec=marathon_pb,
            max_long_run_18m_km=history_18m.get("max_single_distance_km") or 25.0,
            age=age,
            scheduled_races=active_scheduled_races,
            user_weekly_target=user_weekly_target
        )

    # Deterministic safety-net integration for any active scheduled races
    if active_scheduled_races and schedule_data and schedule_data.get("weeks"):
        schedule_data = integrate_scheduled_races_into_schedule(
            schedule_data=schedule_data,
            scheduled_races=active_scheduled_races,
            age=age,
            vdot=vo2max
        )

    # If athlete is currently in deep fatigue (TSB < -30), automatically annotate Week 1 with fatigue-aware adjustment
    if tsb < -30 and schedule_data and schedule_data.get("weeks"):
        w1 = schedule_data["weeks"][0]
        w1["key_focus"] = f"【疲劳保护适应】当前 TSB 为 {tsb}，首周适度控制负荷以消化前期疲劳 · " + (w1.get("key_focus") or "")

    # Attach fitness snapshot and user goal alignment to schedule
    schedule_data["user_goal_alignment"] = {
        "weekly_target": user_weekly_target,
        "monthly_target": user_monthly_target,
        "aligned": True
    }
    schedule_data["current_fitness_snapshot"] = {
        "ctl": ctl,
        "atl": atl,
        "tsb": tsb,
        "vo2max": vo2max,
        "vo2max_source": vo2max_source,
        "age": age,
        "max_long_run_18m_km": history_18m.get("max_single_distance_km"),
        "total_activities_18m": history_18m.get("total_activities_count"),
        "recent_races_count": len(history_18m.get("recent_races", [])),
        "scheduled_races_count": len(active_scheduled_races)
    }

    focus_cn = {
        "aerobic_base": "基础有氧耐力扩容",
        "lactate_threshold": "乳酸阈值耐力提升",
        "vo2max_speed": "VO2Max 速度储备",
        "trail_climbing": "山地越野爬坡抗阻",
        "general_maintenance": "综合体能维持"
    }.get(maintenance_focus or "aerobic_base", "非赛期专项强化")
    target_display = target_race_name if goal_type == "race_prep" else focus_cn
    plan_title = schedule_data.get("macro_cycle_name") or f"{runner_name} · {target_display} {weeks_count}周训练计划"
    plan_overview = schedule_data.get("goal_summary") or ""
    if plan_overview and "VO2Max" in plan_overview:
        import re as _re
        plan_overview = _re.sub(r"VO2Max\s+\d+(?:\.\d+)?", f"VO2Max {vo2max}", plan_overview)
        schedule_data["goal_summary"] = plan_overview
    if req.coach_notes_prompt and str(req.coach_notes_prompt).strip():
        plan_overview = f"【教练定制指引：{str(req.coach_notes_prompt).strip()}】" + plan_overview

    operator = req.operator_uid or eff_uid
    plan_status = "draft" if req.as_draft else "active"
    review_status = "draft" if req.as_draft else ("published" if operator != eff_uid else "self_created")

    plan_payload = {
        "user_id": canonical_uid,
        "club_id": req.club_id,
        "title": plan_title,
        "goal_type": goal_type,
        "maintenance_focus": maintenance_focus,
        "target_race_id": req.target_race_id,
        "target_race_name": target_race_name,
        "target_date": eff_target_date or end_date,
        "start_date": start_date,
        "end_date": end_date,
        "weeks_count": weeks_count,
        "days_per_week": days_per_week,
        "preferred_long_run_day": req.preferred_long_run_day or "Sunday",
        "status": plan_status,
        "review_status": review_status,
        "coach_review_note": str(req.coach_notes_prompt).strip() if req.coach_notes_prompt else None,
        "overview_summary": plan_overview,
        "schedule_data": schedule_data,
        "creator_id": operator,
        "last_modified_by": operator
    }

    if req.preview_only:
        import copy as _copy
        preview_plan = _copy.deepcopy(plan_payload)
        preview_plan["id"] = f"preview_{int(datetime.utcnow().timestamp()*1000)}"
        preview_plan["is_preview"] = True
        preview_plan = LocalStore.reconcile_training_plan_activities(preview_plan, canonical_uid)
        preview_plan = LocalStore._enrich_plan_with_current_week(preview_plan)
        return {
            "success": True,
            "preview_only": True,
            "message": "已生成训练计划预览！请确认更新或确认派发后才会写入生效（放弃将不会覆盖现有计划）。",
            "plan": preview_plan
        }

    # Upsert plan into DB
    saved_plan = LocalStore.upsert_training_plan(plan_payload)

    msg_suffix = "草案已生成，请审核修改后发布给队员！" if req.as_draft else f"成功为 {runner_name} 生成 {weeks_count} 周科学训练计划！"
    return {
        "success": True,
        "message": msg_suffix,
        "plan": saved_plan
    }


@router.post("/plan/confirm")
def confirm_training_plan_endpoint(req: ConfirmPlanRequest):
    """
    Persists a previewed training plan only after the athlete or coach explicitly confirms.
    Avoids accidental overwrites when previewing generated or modified plans.
    """
    import copy as _copy
    payload = _copy.deepcopy(req.plan_payload or {})
    if not payload or not payload.get("schedule_data"):
        raise HTTPException(status_code=400, detail="待确认的训练计划数据不完整")

    raw_id = str(payload.get("id") or "")
    if raw_id.startswith("preview_"):
        payload.pop("id", None)
    payload.pop("is_preview", None)

    if req.user_id and not payload.get("user_id"):
        payload["user_id"] = LocalStore.resolve_user_id(req.user_id)
    operator = req.operator_uid or payload.get("last_modified_by") or payload.get("creator_id") or payload.get("user_id")
    payload["last_modified_by"] = operator
    if not payload.get("creator_id"):
        payload["creator_id"] = operator

    saved_plan = LocalStore.upsert_training_plan(payload)
    if not saved_plan:
        raise HTTPException(status_code=400, detail="确认写入训练计划失败")

    if req.publish_as_coach and saved_plan.get("id"):
        saved_plan = LocalStore.publish_training_plan(
            plan_id=saved_plan["id"],
            operator_uid=operator,
            coach_review_note=payload.get("coach_review_note"),
            title=payload.get("title"),
            overview_summary=payload.get("overview_summary"),
            schedule_data=payload.get("schedule_data")
        )

    if req.sync_to_goals and saved_plan and saved_plan.get("id"):
        try:
            sync_training_plan_to_user_goals(saved_plan["id"], SyncPlanToGoalsRequest(user_id=saved_plan.get("user_id")))
        except Exception as e:
            logger.warning(f"Auto sync to goals on confirm failed: {e}")

    return {
        "success": True,
        "message": "训练计划已确认并正式更新生效！",
        "plan": saved_plan
    }


@router.get("/plan/user/{uid}")
def get_user_training_plan(uid: str):
    """
    Returns the active training plan for the specified user,
    plus any pending coach draft plan, history of archived plans, version backups, and user's current goal targets.
    """
    canonical_uid = LocalStore.resolve_user_id(uid)
    plan = LocalStore.get_user_active_training_plan(canonical_uid)
    draft_plan = LocalStore.get_user_draft_training_plan(canonical_uid, reconcile=True)
    past_plans = LocalStore.get_user_training_plans(canonical_uid, limit=8)
    backups = LocalStore.get_user_plan_backups(canonical_uid, limit=10)
    user_goal = LocalStore.get_goal(canonical_uid)
    race_ctx = resolve_athlete_race_context(canonical_uid)
    recovery_avail = LocalStore.assess_recovery_data_availability(canonical_uid)
    return {
        "active_plan": plan,
        "draft_plan": draft_plan,
        "past_plans": past_plans,
        "backups": backups,
        "user_goal": user_goal,
        "upcoming_races": race_ctx.get("upcoming", []),
        "recovery_data_availability": recovery_avail,
    }


@router.get("/plan/user/{uid}/today")
def get_user_today_workout(uid: str):
    """
    Returns today's specific workout from the athlete's active training plan.
    """
    canonical_uid = LocalStore.resolve_user_id(uid)
    today_workout = LocalStore.get_today_workout(canonical_uid)
    return {"today_workout": today_workout}


@router.get("/plan/templates")
def get_coach_training_templates_endpoint(
    club_id: Optional[str] = None,
    operator_uid: Optional[str] = None,
    coach_uid: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """
    Returns the coach training plan template library grouped by pace, target finish time, and scenario:
    - 8 Built-in System Templates (240组/A/B/C/D/E组 + 戈壁挑战赛A组 + 百公里长距离越野组): available to all coaches.
    - Coach Custom Templates: strictly private to the requesting coach (`operator_uid` / `coach_uid`) and portable across all running clubs they manage.
    """
    eff_uid = operator_uid or coach_uid or user_id
    templates = LocalStore.get_coach_training_templates(club_id=club_id, operator_uid=eff_uid)
    return {
        "success": True,
        "templates": templates
    }


@router.post("/plan/templates")
def save_coach_custom_template_endpoint(req: SaveCustomTemplateRequest):
    """
    Creates or updates a coach's private custom training plan template (or saves an athlete's current week schedule as a reusable template).
    The saved template is strictly visible only to `req.operator_uid` and can be applied across any running club this coach manages.
    """
    days_tpl = req.days_template
    eff_roadmap = req.macro_roadmap or ""
    eff_note = req.coach_review_note or ""
    eff_pz = req.pace_zones

    if (not days_tpl or len(days_tpl) == 0) and req.from_plan_id:
        src_plan = LocalStore.get_training_plan(req.from_plan_id, reconcile=False)
        if src_plan and src_plan.get("schedule_data"):
            sched = src_plan["schedule_data"]
            weeks = sched.get("weeks") or []
            w_idx = int(req.from_week_index or src_plan.get("current_week_index") or 1)
            target_w = next((w for w in weeks if int(w.get("week_index") or 1) == w_idx), weeks[0] if weeks else None)
            if target_w and target_w.get("days"):
                days_tpl = target_w["days"]
            if not eff_roadmap:
                eff_roadmap = sched.get("macro_roadmap") or ""
            if not eff_note:
                eff_note = src_plan.get("coach_review_note") or target_w.get("key_focus") or ""
            if not eff_pz and sched.get("pace_zones"):
                eff_pz = sched.get("pace_zones")

    saved_tpl = LocalStore.save_coach_custom_template(
        operator_uid=req.operator_uid,
        club_id=req.club_id,
        template_id=req.template_id,
        group_code=req.group_code,
        category=req.category or "custom",
        name=req.name,
        short_name=req.short_name,
        badge_color=req.badge_color or "amber",
        target_level=req.target_level or "教练定制专项组",
        intensity_tag=req.intensity_tag or "教练定制配速与强度",
        weekly_km=req.weekly_km,
        days_per_week=req.days_per_week,
        pace_zones=eff_pz,
        macro_roadmap=eff_roadmap,
        coach_review_note=eff_note,
        days_template=days_tpl,
    )
    templates = LocalStore.get_coach_training_templates(club_id=req.club_id, operator_uid=req.operator_uid)
    return {
        "success": True,
        "template": saved_tpl,
        "templates": templates,
        "message": f"已保存为您的教练个人专属模版【{saved_tpl['short_name']}】（仅您本人可见，可在您执教的所有跑团直接套用）！"
    }


@router.delete("/plan/templates/{template_id}")
def delete_coach_custom_template_endpoint(template_id: str, operator_uid: Optional[str] = None, club_id: Optional[str] = None):
    """
    Deletes a coach's own custom training template. Built-in templates or other coaches' templates cannot be deleted.
    """
    deleted = LocalStore.delete_coach_custom_template(template_id=template_id, operator_uid=operator_uid)
    if not deleted:
        raise HTTPException(status_code=400, detail="系统预置标准模版不可删除（或无权删除其他教练的专属模版），您可以基于它修改并「另存为新模版」")
    templates = LocalStore.get_coach_training_templates(club_id=club_id, operator_uid=operator_uid)
    return {
        "success": True,
        "templates": templates,
        "message": "已删除您的教练个人自定义训练模版"
    }


@router.post("/plan/assign-template")
def assign_template_to_athletes_endpoint(req: AssignTemplateRequest):
    """
    Assigns a pace & intensity group template (built-in or custom) to one or multiple athletes.
    Supports both full 4-week plan assignment (draft or published) and single-week replacement,
    allowing coaches to batch-assign by pace group and then fine-tune individual athletes.
    """
    eff_uids = req.user_ids or req.target_user_ids or []
    if not eff_uids:
        if req.preview_only:
            eff_uids = ["__template_preview__"]
        else:
            raise HTTPException(status_code=400, detail="请至少选择一位需要分配模版的队员")

    raw_scope = req.apply_mode or req.apply_scope or "full_plan"
    eff_mode = "single_week" if raw_scope in ("single_week", "current_week", "next_week") else "full_plan"
    eff_week_idx = req.target_week_index
    if raw_scope == "next_week" and eff_week_idx is None:
        eff_week_idx = 2
    eff_scale = req.volume_scale if req.volume_scale is not None else (req.scale_factor if req.scale_factor is not None else 1.0)

    res = LocalStore.assign_template_to_athletes(
        template_id=req.template_id,
        user_ids=eff_uids,
        operator_uid=req.operator_uid,
        club_id=req.club_id,
        apply_mode=eff_mode,
        target_week_index=eff_week_idx,
        weeks_count=req.weeks_count or 4,
        volume_scale=eff_scale,
        as_draft=True if req.as_draft is None else bool(req.as_draft),
        custom_days=req.custom_days,
        custom_weeks=req.custom_weeks,
        custom_title=req.custom_title,
        coach_review_note=req.coach_review_note,
        macro_roadmap=req.macro_roadmap,
        preview_only=bool(req.preview_only),
        base_plan=req.base_plan,
        canova_progression=True if req.canova_progression is None else bool(req.canova_progression),
    )
    cnt = res.get("assigned_count", 0)
    t_name = res.get("template_name") or req.template_id
    if req.preview_only:
        msg = f"已加载【{t_name}】模版预览（尚未写入），请点击底部「确认派发/更新」后才会正式生效！"
    elif eff_mode == "single_week":
        msg = f"已将【{t_name}】周课表模版套用至 {cnt} 位队员，可继续针对个人情况微调单日课表！"
    elif res.get("as_draft"):
        msg = f"已按【{t_name}】为 {cnt} 位队员批量生成待审草案！您可在流水线中快速微调个别队员后一键发布。"
    else:
        msg = f"已按【{t_name}】为 {cnt} 位队员批量分配并正式发布训练计划！"

    return {
        "success": True,
        **res,
        "message": msg
    }


class ImportWeeklyScheduleRequest(BaseModel):
    image_base64: Optional[str] = None
    raw_text: Optional[str] = None
    preset_id: Optional[str] = None
    club_id: Optional[str] = None
    operator_uid: Optional[str] = None


class BatchAssignImportedWeekRequest(BaseModel):
    club_id: Optional[str] = None
    operator_uid: str
    plan_title: str
    source_week_index: Optional[int] = 1
    target_monday: Optional[str] = None
    coach_review_note: Optional[str] = None
    as_draft: Optional[bool] = False
    save_as_templates: Optional[bool] = False
    group_assignments: List[Dict[str, Any]]


@router.get("/plan/import-presets")
def get_weekly_schedule_import_presets():
    """
    Returns built-in real weekly training schedule presets (Fudan EMBA Gobi 22 Pre-A & Shangma race-in-race)
    for quick assistant coach testing and reference.
    """
    from utils.schedule_importer import PRESET_SCHEDULES
    presets = [
        {
            "id": p["id"],
            "label": p["label"],
            "category": p["category"],
            "raw_text": p["raw_text"],
        }
        for p in PRESET_SCHEDULES.values()
    ]
    return {"success": True, "presets": presets}


@router.post("/plan/import-weekly-schedule")
def parse_and_import_weekly_schedule_endpoint(req: ImportWeeklyScheduleRequest):
    """
    Smart weekly training schedule importer for assistant coaches:
    - Accepts a schedule screenshot (`image_base64`), pasted text (`raw_text`), or `preset_id`.
    - Automatically splits the schedule into sub-groups (`A组~E组` or `男组/女组`),
      merges strength training footnotes (`体能训练 a/b/c`) into daily descriptions,
      and matches club members to their respective groups.
    """
    from utils.schedule_importer import (
        PRESET_SCHEDULES,
        extract_text_from_schedule_image,
        parse_weekly_schedule_text,
    )

    eff_text = (req.raw_text or "").strip()
    source_type = "text"

    if not eff_text and req.preset_id and req.preset_id in PRESET_SCHEDULES:
        eff_text = PRESET_SCHEDULES[req.preset_id]["raw_text"]
        source_type = "preset"
    elif not eff_text and req.image_base64:
        try:
            eff_text = extract_text_from_schedule_image(req.image_base64)
            source_type = "image_ocr"
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not eff_text:
        raise HTTPException(status_code=400, detail="请上传周课表图片、粘贴课表文字或选择示例课表")

    try:
        parsed = parse_weekly_schedule_text(eff_text)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to parse weekly schedule text: {e}")
        raise HTTPException(status_code=400, detail=f"解析周课表失败：{str(e)}")

    # Auto-match club members to the parsed groups if club_id is provided
    group_codes = [g["group_code"] for g in parsed.get("groups", [])]
    grouping_mode = parsed.get("grouping_mode", "single")
    member_group_map: Dict[str, str] = {}

    if req.club_id and group_codes:
        try:
            students = LocalStore.get_coach_students_metrics(req.club_id, req.operator_uid or "")
            for s in students:
                uid = s["user_id"]
                saved_grp = (s.get("training_group") or "").strip()
                tpl_grp = ((s.get("plan_info") or {}).get("template_group_code") or "").strip()
                rec_grp = ((s.get("recommended_group") or {}).get("group_code") or "").strip()
                gender_str = str(s.get("gender") or s.get("gender_label") or "").strip()

                matched_code = None
                if grouping_mode == "gender":
                    if saved_grp in group_codes:
                        matched_code = saved_grp
                    elif "女" in gender_str or gender_str.lower() in ("f", "female"):
                        matched_code = "女组" if "女组" in group_codes else group_codes[-1]
                    else:
                        matched_code = "男组" if "男组" in group_codes else group_codes[0]
                elif grouping_mode == "pace_groups":
                    for cand in (saved_grp, tpl_grp, rec_grp):
                        if not cand:
                            continue
                        if cand in group_codes:
                            matched_code = cand
                            break
                        if cand == "240组" and "A组" in group_codes:
                            matched_code = "A组"
                            break
                    if not matched_code:
                        matched_code = "C组" if "C组" in group_codes else group_codes[len(group_codes) // 2]
                else:
                    matched_code = group_codes[0]

                member_group_map[uid] = matched_code
        except Exception as me:
            logger.warning(f"Auto-matching club members for schedule import failed: {me}")

    return {
        "success": True,
        "source_type": source_type,
        "parsed_schedule": parsed,
        "recommended_member_mapping": member_group_map,
        "message": f"成功识别《{parsed['plan_title']}》，共拆解出 {len(group_codes)} 个训练组别（{', '.join(group_codes)}）！",
    }


@router.post("/plan/batch-assign-imported-week")
def batch_assign_imported_week_endpoint(req: BatchAssignImportedWeekRequest):
    """
    Batch-assigns the parsed multi-group weekly schedule to the matched athletes in each group.
    Preserves the coach's exact daily workouts (canova_progression=False) and remembers each athlete's group.
    """
    total_uids = sum(len(g.get("user_ids") or []) for g in (req.group_assignments or []))
    if total_uids == 0:
        raise HTTPException(status_code=400, detail="请至少为一个训练组勾选需要派发课表的队员")

    res = LocalStore.batch_assign_imported_weekly_schedule(
        club_id=req.club_id,
        operator_uid=req.operator_uid,
        plan_title=req.plan_title,
        source_week_index=req.source_week_index or 1,
        target_monday=req.target_monday,
        coach_review_note=req.coach_review_note,
        as_draft=bool(req.as_draft),
        save_as_templates=bool(req.save_as_templates),
        group_assignments=req.group_assignments,
    )

    grp_parts = [
        f"{g['group_code']} {g['assigned_count']}人"
        for g in res.get("group_summary", [])
        if g.get("assigned_count", 0) > 0
    ]
    grp_detail_str = "、".join(grp_parts) if grp_parts else f"共 {res['total_assigned_count']} 人"
    mode_str = "生成待审草案" if req.as_draft else "正式发布下周课表"

    return {
        "success": True,
        **res,
        "message": f"✅ 已按组完成《{res['plan_title']}》({res['target_monday']} ~ {res['target_sunday']}) 课表派发：{grp_detail_str}（已{mode_str}）！",
    }


class RollbackUserPlanRequest(BaseModel):
    operator_uid: Optional[str] = None
    backup_id: Optional[str] = None
    target_plan_id: Optional[str] = None
    discard_draft_only: Optional[bool] = False


class RollbackBatchRequest(BaseModel):
    operator_uid: Optional[str] = None


@router.post("/plan/user/{uid}/rollback")
def rollback_user_training_plan_endpoint(uid: str, req: RollbackUserPlanRequest):
    """
    Rolls back or switches an athlete's training plan:
    - `discard_draft_only=True`: removes/archives the pending draft without touching the athlete's active plan.
    - `target_plan_id`: activates any historical/archived plan (e.g. switching back from Coach schedule to AI Canova plan).
    - `backup_id` (or latest backup): restores the exact previous active plan snapshot.
    """
    try:
        res = LocalStore.rollback_user_training_plan(
            user_id=uid,
            operator_uid=req.operator_uid,
            backup_id=req.backup_id,
            target_plan_id=req.target_plan_id,
            discard_draft_only=bool(req.discard_draft_only),
        )
        canonical_uid = LocalStore.resolve_user_id(uid)
        res["past_plans"] = LocalStore.get_user_training_plans(canonical_uid, limit=8)
        res["backups"] = LocalStore.get_user_plan_backups(canonical_uid, limit=10)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Rollback user plan error for {uid}: {e}")
        raise HTTPException(status_code=500, detail=f"回退训练计划失败：{str(e)}")


@router.get("/plan/club-batches")
def get_club_plan_batches_endpoint(club_id: Optional[str] = None, limit: int = 15):
    """
    Returns recent batch plan dispatches (imported weekly schedules & template batch assignments)
    so coaches can inspect history and roll back an entire batch in 1 click.
    """
    batches = LocalStore.get_club_plan_batches(club_id=club_id, limit=limit)
    return {"success": True, "batches": batches}


@router.post("/plan/club-batches/{batch_id}/rollback")
def rollback_club_plan_batch_endpoint(batch_id: str, req: Optional[RollbackBatchRequest] = None):
    """
    Rolls back an entire batch dispatch (either removing drafts or restoring all affected athletes' previous active plans).
    """
    op_uid = req.operator_uid if req else None
    res = LocalStore.rollback_plan_batch(batch_id=batch_id, operator_uid=op_uid)
    return res


@router.get("/plan/{plan_id}")
def get_training_plan_detail(plan_id: str):
    """
    Returns specific training plan details by plan_id, along with user's goal targets for alignment.
    """
    plan = LocalStore.get_training_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="训练计划不存在")
    user_goal = LocalStore.get_goal(plan.get("user_id"))
    return {"plan": plan, "user_goal": user_goal}


@router.post("/plan/{plan_id}/sync-to-goals")
def sync_training_plan_to_user_goals(plan_id: str, req: Optional[SyncPlanToGoalsRequest] = None):
    """
    Synchronizes the periodized training plan's weekly and monthly mileage back to the runner's goals table.
    Updates weekly_target, target_distance (monthly), and monthly_targets for affected calendar months.
    """
    plan = LocalStore.get_training_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="训练计划不存在")
    
    uid = (req.user_id if req and req.user_id else None) or plan.get("user_id")
    canonical_uid = LocalStore.resolve_user_id(uid)

    schedule_data = plan.get("schedule_data") or {}
    weeks = schedule_data.get("weeks") or []
    if not weeks:
        raise HTTPException(status_code=400, detail="该训练计划无有效周课表数据")

    # 1. Weekly mileage calculation
    # Exclude extreme race weeks (where mileage is massive like 50k ultra) when computing standard weekly target
    regular_weeks_km = [
        float(w.get("weekly_mileage_km", 0.0))
        for w in weeks
        if "比赛周" not in str(w.get("phase", "")) and "巅峰之战" not in str(w.get("week_title", ""))
    ]
    if not regular_weeks_km:
        regular_weeks_km = [float(w.get("weekly_mileage_km", 0.0)) for w in weeks]
    
    avg_weekly_km = round(sum(regular_weeks_km) / max(len(regular_weeks_km), 1), 1)

    # Current week mileage if sync_mode is current_week
    sync_mode = req.sync_mode if req else "average"
    new_weekly_target = avg_weekly_km

    if sync_mode == "current_week":
        today_iso = date.today().isoformat()
        for w in weeks:
            for d in w.get("days", []):
                if d.get("date") == today_iso:
                    new_weekly_target = float(w.get("weekly_mileage_km", avg_weekly_km))
                    break

    # 2. Monthly mileage calculation
    month_km_map: Dict[int, float] = {}
    for w in weeks:
        for d in w.get("days", []):
            d_date = str(d.get("date") or "")
            d_km = float(d.get("distance_km") or 0.0)
            if len(d_date) >= 7 and d_km > 0:
                try:
                    m_idx = int(d_date[5:7])  # 1..12
                    month_km_map[m_idx] = month_km_map.get(m_idx, 0.0) + d_km
                except Exception:
                    pass

    existing_goal = LocalStore.get_goal(canonical_uid)
    monthly_targets = list(existing_goal.get("monthly_targets") or [round(new_weekly_target * 4.0, 1)] * 12)
    while len(monthly_targets) < 12:
        monthly_targets.append(round(new_weekly_target * 4.0, 1))

    # Update affected months in monthly_targets (only unstarted future months > current month)
    cur_month = LocalStore.get_beijing_today().month
    for m_idx, planned_km in month_km_map.items():
        if cur_month < m_idx <= 12 and planned_km > 0:
            monthly_targets[m_idx - 1] = round(max(planned_km, new_weekly_target * 3.5), 1)

    new_monthly_target = round(new_weekly_target * 4.0, 1)

    updated_goal_data = {
        "user_id": canonical_uid,
        "target_distance": new_monthly_target,
        "weekly_target": new_weekly_target,
        "next_weekly_target": new_weekly_target,
        "period_type": "monthly",
        "monthly_targets": monthly_targets
    }
    LocalStore.upsert_goal(canonical_uid, updated_goal_data, enforce_started_lock=True)
    saved_goal = LocalStore.get_goal(canonical_uid)

    return {
        "success": True,
        "message": f"成功将训练计划同步至未开始的周/月计划目标！下周起周目标已设为 {new_weekly_target} km/周（本周及已开始月份锁定不变）。",
        "weekly_target": new_weekly_target,
        "current_week_target": saved_goal.get("current_week_target"),
        "next_weekly_target": saved_goal.get("next_weekly_target"),
        "monthly_target": new_monthly_target,
        "monthly_targets": saved_goal.get("monthly_targets") or monthly_targets
    }


@router.put("/plan/{plan_id}")
def update_training_plan_overview(plan_id: str, req: UpdatePlanRequest):
    """
    Updates the plan title, overview summary, coach_review_note, or status.
    """
    plan = LocalStore.get_training_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="训练计划不存在")

    update_fields = {}
    if req.title is not None:
        update_fields["title"] = req.title
    if req.overview_summary is not None:
        update_fields["overview_summary"] = req.overview_summary
    if req.status is not None:
        update_fields["status"] = req.status
    if req.coach_review_note is not None:
        update_fields["coach_review_note"] = req.coach_review_note
    update_fields["last_modified_by"] = req.operator_uid

    # Update in DB using canonical DB_PATH and strict column whitelist
    allowed_plan_cols = {"title", "overview_summary", "status", "coach_review_note", "last_modified_by"}
    safe_update = {k: v for k, v in update_fields.items() if k in allowed_plan_cols}
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        now_iso = datetime.utcnow().isoformat() + "Z"
        set_clauses = [f"{k} = ?" for k in safe_update.keys()]
        set_clauses.append("updated_at = ?")
        vals = list(safe_update.values()) + [now_iso, plan_id]
        cursor.execute(f"UPDATE training_plans SET {', '.join(set_clauses)} WHERE id = ?", vals)
        conn.commit()

    updated = LocalStore.get_training_plan(plan_id)
    return {"success": True, "message": "计划信息已更新", "plan": updated}


@router.post("/plan/{plan_id}/publish")
def publish_training_plan_endpoint(plan_id: str, req: PublishPlanRequest):
    """
    Coach approves and publishes a training plan (draft, preview, or active) to the athlete.
    Marks status='active', review_status='published', records coach review note,
    optionally syncs mileage to athlete's goals, and notifies the athlete.
    """
    plan = None
    if plan_id and not str(plan_id).startswith("preview_"):
        plan = LocalStore.get_training_plan(plan_id, reconcile=False)
    if not plan and not req.plan_payload:
        raise HTTPException(status_code=404, detail="训练计划不存在")

    published_plan = LocalStore.publish_training_plan(
        plan_id=plan_id,
        operator_uid=req.operator_uid,
        coach_review_note=req.coach_review_note,
        title=req.title,
        overview_summary=req.overview_summary,
        schedule_data=req.schedule_data,
        plan_payload=req.plan_payload,
    )
    if not published_plan:
        raise HTTPException(status_code=400, detail="发布训练计划失败")

    if req.sync_to_goals:
        try:
            sync_training_plan_to_user_goals(published_plan["id"], SyncPlanToGoalsRequest(user_id=published_plan.get("user_id")))
        except Exception as e:
            logger.warning(f"Auto sync to goals on publish failed: {e}")

    return {
        "success": True,
        "message": "训练计划已确认并正式派发/更新给队员！",
        "plan": published_plan
    }


@router.post("/plan/{plan_id}/week-adjust")
def adjust_training_plan_week_endpoint(plan_id: str, req: AdjustPlanWeekRequest):
    """
    Coach batch-adjusts a specific week in the training plan:
    - scale_volume: scales all running workouts in the week by scale_factor (e.g. 0.85 or 1.10)
    - downgrade_intensity: converts interval/tempo/trail_climb workouts in the week to easy_run
    - update_meta: updates week_title, phase, key_focus
    """
    updated_plan = LocalStore.batch_adjust_plan_week(
        plan_id=plan_id,
        week_index=req.week_index,
        action=req.action,
        operator_uid=req.operator_uid,
        scale_factor=req.scale_factor,
        week_title=req.week_title,
        phase=req.phase,
        key_focus=req.key_focus,
        preview_only=bool(req.preview_only),
        schedule_data=req.schedule_data,
        plan_payload=req.plan_payload,
    )
    if not updated_plan:
        raise HTTPException(status_code=400, detail="调整周课表失败，请检查周序号")

    return {
        "success": True,
        "preview_only": bool(req.preview_only),
        "message": f"第 {req.week_index} 周课表已调整预览（点击底部确认派发/更新后写入生效）" if req.preview_only else f"第 {req.week_index} 周课表已批量调整更新",
        "plan": updated_plan
    }


@router.post("/plan/club-batch-generate")
def club_batch_generate_plans_endpoint(req: ClubBatchGeneratePlansRequest):
    """
    Generates personalized draft training plans for multiple club members based on each member's
    target race, weekly mileage goal, and current CTL/ATL/TSB physiological state.
    """
    members = LocalStore.get_club_members(req.club_id)
    if not members:
        raise HTTPException(status_code=404, detail="未找到跑团成员")

    target_uids = set(req.student_uids) if req.student_uids else None
    only_without = True if req.only_without_plan is None else bool(req.only_without_plan)
    generated_plans = []

    for m in members:
        uid = m["user_id"]
        if target_uids is not None and uid not in target_uids:
            continue
        if target_uids is None and only_without:
            # Only generate for members without an active or draft plan
            existing_active = LocalStore.get_user_active_training_plan(uid, reconcile=False)
            existing_draft = LocalStore.get_user_draft_training_plan(uid, reconcile=False)
            if existing_active or existing_draft:
                continue

        try:
            gen_res = generate_scientific_training_plan(GenerateTrainingPlanRequest(
                athlete_uid=uid,
                club_id=req.club_id,
                weeks_count=req.weeks or req.weeks_count or 8,
                days_per_week=req.days_per_week or 4,
                operator_uid=req.operator_uid,
                as_draft=True if req.as_draft is None else req.as_draft,
                use_fast_engine=True if req.use_fast_engine is None else req.use_fast_engine
            ))
            if gen_res.get("plan"):
                generated_plans.append({
                    "user_id": uid,
                    "display_name": m.get("display_name"),
                    "plan_id": gen_res["plan"].get("id"),
                    "title": gen_res["plan"].get("title")
                })
        except Exception as e:
            logger.warning(f"Batch generate plan failed for {uid}: {e}")

    return {
        "success": True,
        "generated_count": len(generated_plans),
        "generated_plans": generated_plans,
        "message": f"已为 {len(generated_plans)} 名队员智能生成个性化训练计划草案，请逐一审核后发布！"
    }


@router.patch("/plan/{plan_id}/workout")
@router.put("/plan/{plan_id}/workout")
def update_plan_workout_item(plan_id: str, req: UpdateWorkoutRequest):
    """
    Fine-grained collaborative editing of a single workout in the plan.
    Allows athlete or coach to modify distance, pace, workout type, completion status, coach notes,
    or log W19 daily biometrics (HRV, RHR, respiratory, strain, recovery%), actual execution, RPE, self-feel notes, and day swap.
    """
    plan = None
    if plan_id and not str(plan_id).startswith("preview_"):
        plan = LocalStore.get_training_plan(plan_id)
    if not plan and not req.plan_payload:
        raise HTTPException(status_code=404, detail="训练计划不存在")

    workout_update = {}
    for k in [
        "workout_type", "title", "distance_km", "duration_minutes", "target_pace",
        "target_hr_zone", "description", "completed", "coach_notes", "date",
        "hrv", "resting_hr", "respiratory_rate", "strain_score", "recovery_pct",
        "actual_execution_text", "rpe", "feeling_tag", "athlete_notes",
        "workout_photos", "photo_url", "strength_completed",
        "is_swapped", "swap_with_day_index", "undo_swap", "is_coach_edit"
    ]:
        v = getattr(req, k, None)
        if v is not None:
            workout_update[k] = v

    if "athlete_notes" not in workout_update and req.notes is not None:
        workout_update["athlete_notes"] = req.notes
    if "feeling_tag" not in workout_update:
        if req.feeling is not None:
            workout_update["feeling_tag"] = req.feeling
        elif req.feedback is not None:
            workout_update["feeling_tag"] = req.feedback

    # Handle base64 workout check-in photo uploads (single or multiple)
    b64_inputs: List[str] = []
    if req.photo_base64 and str(req.photo_base64).strip():
        b64_inputs.append(str(req.photo_base64).strip())
    if req.new_photos_base64:
        for item in req.new_photos_base64:
            if item and str(item).strip():
                b64_inputs.append(str(item).strip())

    if b64_inputs or req.workout_photos is not None or req.photo_url is not None:
        import os
        import base64
        import time

        existing_photos: List[str] = []
        if req.workout_photos is not None:
            existing_photos = [str(p).strip() for p in req.workout_photos if p and str(p).strip()]
        elif plan:
            sched_obj = plan.get("schedule_data") or {}
            for w_obj in (sched_obj.get("weeks") or []):
                if int(w_obj.get("week_index") or 0) == int(req.week_index):
                    d_list = w_obj.get("days") or []
                    if 0 <= req.day_index < len(d_list):
                        cur_d = d_list[req.day_index]
                        raw_p = cur_d.get("workout_photos") or []
                        if isinstance(raw_p, list):
                            existing_photos = [str(x).strip() for x in raw_p if x]
                        elif cur_d.get("photo_url"):
                            existing_photos = [str(cur_d["photo_url"]).strip()]
                    break

        if b64_inputs:
            photo_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "race_photos")
            os.makedirs(photo_dir, exist_ok=True)
            safe_uid = "".join(c for c in str(req.operator_uid or "runner") if c.isalnum() or c in ("_", "-"))[:24]
            ts_ms = int(time.time() * 1000)
            for idx, raw_b64 in enumerate(b64_inputs):
                if raw_b64.startswith("http://") or raw_b64.startswith("https://") or raw_b64.startswith("/api/"):
                    if raw_b64 not in existing_photos:
                        existing_photos.append(raw_b64)
                    continue
                b64_str = raw_b64.split(",", 1)[1] if "," in raw_b64 else raw_b64
                try:
                    img_bytes = base64.b64decode(b64_str)
                    if len(img_bytes) > 100:
                        fname = f"workout_{safe_uid}_w{req.week_index}_d{req.day_index}_{ts_ms}_{idx}.jpg"
                        fpath = os.path.join(photo_dir, fname)
                        with open(fpath, "wb") as f:
                            f.write(img_bytes)
                        pub_url = f"https://rgm.vanpower.net/api/race-photos/{fname}"
                        if pub_url not in existing_photos:
                            existing_photos.append(pub_url)
                except Exception as pe:
                    logger.warning(f"Failed to decode workout photo base64: {pe}")

        existing_photos = existing_photos[:6]
        workout_update["workout_photos"] = existing_photos
        workout_update["photo_url"] = existing_photos[0] if existing_photos else ""

    updated_plan = LocalStore.update_training_plan_workout(
        plan_id=plan_id,
        week_index=req.week_index,
        day_index=req.day_index,
        workout_update=workout_update,
        operator_uid=req.operator_uid,
        preview_only=bool(req.preview_only),
        schedule_data=req.schedule_data,
        plan_payload=req.plan_payload,
    )

    if not updated_plan:
        raise HTTPException(status_code=400, detail="未找到对应周或日的课表")

    return {
        "success": True,
        "preview_only": bool(req.preview_only),
        "message": "单日课表修改已生成预览（点击底部确认派发/更新后写入生效）" if req.preview_only else "训练课表与执行体感已更新",
        "plan": updated_plan
    }


@router.post("/plan/{plan_id}/week-summary")
@router.put("/plan/{plan_id}/week-summary")
def update_plan_week_summary_endpoint(plan_id: str, req: UpdateWeekSummaryRequest):
    """
    Updates the W19 weekly summary footer (伤痛记录, 队员周小结, 出行/请假报备, 教练本周复盘与下周导向, 宏观周期大纲).
    """
    summary_update = {}
    for k in [
        "injury_note",
        "athlete_weekly_summary",
        "travel_or_leave_note",
        "coach_weekly_diagnosis",
        "strength_count_override",
        "custom_summary_line",
        "macro_roadmap"
    ]:
        v = getattr(req, k, None)
        if v is not None:
            summary_update[k] = v
    if req.week_summary_override is not None and "custom_summary_line" not in summary_update:
        summary_update["custom_summary_line"] = req.week_summary_override

    updated_plan = LocalStore.update_training_plan_week_summary(
        plan_id=plan_id,
        week_index=req.week_index,
        summary_update=summary_update,
        operator_uid=req.operator_uid
    )
    if not updated_plan:
        raise HTTPException(status_code=400, detail="更新周小结失败，请检查计划或周序号")

    return {
        "success": True,
        "message": f"第 {req.week_index} 周小结与复盘已保存",
        "plan": updated_plan
    }


@router.post("/plan/{plan_id}/roll-next-week")
def roll_next_week_schedule_endpoint(plan_id: str, req: RollNextWeekRequest):
    """
    Generates or updates Week (source_week_index + 1) based on Week (source_week_index)'s
    execution completion, HRV/recovery, RPE, injury notes, and the coach's weekly diagnosis.
    """
    eff_src_week = int(req.source_week_index or req.base_week_index or 1)
    eff_diag = req.coach_diagnosis if req.coach_diagnosis is not None else req.coach_focus_note
    eff_focus = req.focus_override if req.focus_override is not None else req.next_week_theme
    eff_delta_pct = req.mileage_delta_pct
    if eff_delta_pct is None and req.volume_scale is not None:
        eff_delta_pct = round((float(req.volume_scale) - 1.0) * 100.0, 1)

    updated_plan = LocalStore.roll_next_week_schedule(
        plan_id=plan_id,
        source_week_index=eff_src_week,
        operator_uid=req.operator_uid,
        coach_diagnosis=eff_diag,
        mileage_delta_pct=eff_delta_pct,
        focus_override=eff_focus,
        weekday_group_workout=req.weekday_group_workout,
        weekend_long_run_km=req.weekend_long_run_km,
        preview_only=bool(req.preview_only),
        schedule_data=req.schedule_data,
        plan_payload=req.plan_payload,
    )
    if not updated_plan:
        raise HTTPException(status_code=400, detail="滚动生成下周课表失败")

    next_w_idx = eff_src_week + 1
    rolled_week = None
    for w in (updated_plan.get("schedule_data") or {}).get("weeks") or []:
        if int(w.get("week_index") or 0) == next_w_idx:
            rolled_week = w
            break

    return {
        "success": True,
        "preview_only": bool(req.preview_only),
        "next_week_index": next_w_idx,
        "rolled_week": rolled_week,
        "message": f"已根据 W{eff_src_week} 生成 W{next_w_idx} 课表预览（请点击底部确认派发/更新后写入生效）！" if req.preview_only else f"已根据 W{eff_src_week} 执行情况与教练复盘，智能滚动更新 W{next_w_idx} 课表！",
        "plan": updated_plan
    }


@router.post("/plan/club-broadcast-workout")
def club_broadcast_workout_endpoint(req: ClubBroadcastWorkoutRequest):
    """
    Broadcasts a shared club workout (e.g., 周二交大合练 or 周六长距离合练) to all active member plans in the club.
    """
    # Deterministically normalize day_index to 0..6 (0=周一..6=周日)
    eff_day_idx = req.day_index
    if req.day_index_base == 1:
        eff_day_idx = max(0, min(6, eff_day_idx - 1))
    elif req.day_index_base == 0:
        eff_day_idx = max(0, min(6, eff_day_idx))
    elif eff_day_idx == 7:
        eff_day_idx = 6
    elif 1 <= eff_day_idx <= 6 and req.duration_minutes is not None:
        eff_day_idx = eff_day_idx - 1

    workout_template = {
        "workout_type": req.workout_type or "interval",
        "title": req.title,
        "distance_km": req.distance_km if req.distance_km is not None else 12.0,
        "target_pace": req.target_pace or "按分组配速",
        "target_hr_zone": req.target_hr_zone or "Z3-Z4",
        "description": req.description or "",
        "coach_notes": req.coach_notes or ""
    }
    res = LocalStore.broadcast_club_workout_to_members(
        club_id=req.club_id,
        operator_uid=req.operator_uid,
        day_index=eff_day_idx,
        workout_template=workout_template,
        user_ids=req.user_ids,
        target_week_mode=req.target_week_mode or "current"
    )
    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    d_label = day_names[eff_day_idx] if 0 <= eff_day_idx < 7 else f"Day {eff_day_idx}"
    w_label = "下周" if req.target_week_mode == "next" else "本周"
    return {
        "success": True,
        **res,
        "message": f"已将【{w_label}{d_label} · {req.title}】一键同步派发至 {res.get('updated_count', 0)} 位队员的课表！"
    }


@router.delete("/plan/{plan_id}")
def delete_training_plan_endpoint(plan_id: str, operator_uid: Optional[str] = None):
    """
    Deletes a training plan.
    """
    ok = LocalStore.delete_training_plan(plan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="训练计划不存在或已删除")
    return {"message": "训练计划已成功删除"}





