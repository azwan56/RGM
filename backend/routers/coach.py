from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import json
import sqlite3
from datetime import datetime, date, timedelta
from db import supabase_admin
from utils.llm import llm_client
from utils.local_store import LocalStore
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
    target_race: Optional[str] = "武功山 50K"
    target_time: Optional[str] = "8:00:00"
    race_type: Optional[str] = None  # "trail", "marathon", "half", "10k", "5k"
    elevation_gain: Optional[float] = None

CANOVA_SYSTEM_PROMPT = """你是一位严格遵循世界耐力运动殿堂级教练 Renato Canova (雷纳托·卡诺瓦) 训练哲学的顶级 AI 耐力教练。
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


@router.get("/latest/{uid}")
def get_latest_coach_report(uid: str):
    """
    Returns latest cached Canova AI coach report for fast UI rendering.
    """
    eff_uid = uid
    report = LocalStore.get_coach_report(eff_uid)
    load_metrics = LocalStore.get_training_load(eff_uid, days=60)
    user_profile = LocalStore.get_profile(eff_uid) or {}

    age = get_age_from_dob(user_profile.get("date_of_birth"))
    runner_name = user_profile.get("display_name") or user_profile.get("email", "").split("@")[0] or "跑者"

    if report:
        if "tsb_metrics" not in report:
            report["tsb_metrics"] = {
                "ctl": load_metrics.get("ctl", 0.0),
                "atl": load_metrics.get("atl", 0.0),
                "tsb": load_metrics.get("tsb", 0.0),
                "status": load_metrics.get("status", "平衡稳健"),
                "status_code": load_metrics.get("status_code", "neutral"),
                "risk_warning": load_metrics.get("risk_warning")
            }
        if "athlete_snapshot" not in report:
            report["athlete_snapshot"] = {
                "name": runner_name,
                "age": age,
                "gender": user_profile.get("gender") or "male",
                "years_running": user_profile.get("years_running") or 2
            }
        if "multi_race_analysis" not in report or "multi_race_strategy" not in report:
            user_races = LocalStore.get_race_plans(eff_uid)
            multi_analysis = analyze_multi_race_calendar(user_races)
            report["multi_race_analysis"] = multi_analysis
            report["multi_race_strategy"] = generate_fallback_multi_race_strategy(
                multi_analysis,
                report.get("athlete_snapshot", {}).get("target_race", "目标赛事"),
                report.get("athlete_snapshot", {}).get("race_category", "marathon")
            )

        if isinstance(report.get("recovery_advice"), dict):
            rec_d = report["recovery_advice"]
            report["recovery_advice"] = "\n".join(f"【{k}】{v}" for k, v in rec_d.items())
        if isinstance(report.get("focus_workout_of_the_week"), dict):
            foc_d = report["focus_workout_of_the_week"]
            report["focus_workout_of_the_week"] = "\n".join(f"【{k}】{v}" for k, v in foc_d.items())

        return report

    garmin_connected = bool(user_profile.get("garmin_connected", False))
    coros_connected = bool(user_profile.get("coros_connected", False))

    user_races = LocalStore.get_race_plans(eff_uid)
    multi_analysis = analyze_multi_race_calendar(user_races)
    multi_strategy = generate_fallback_multi_race_strategy(multi_analysis, "首选目标赛", "marathon")

    if not garmin_connected and not coros_connected:
        return {
            "summary": "欢迎来到 Renato Canova AI 耐力教练专区！请在【我的】页面绑定 Garmin 或高驰 (COROS) 账号同步您的历史运动。",
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

    # Age calculation
    dob_str = user_profile.get("date_of_birth")
    age = get_age_from_dob(dob_str)
    if age is None:
        age_desc = "未登记出生年份（系统默认按 30 岁常规体能与 48 小时恢复周期评估）"
    elif age < 35:
        age_desc = f"{age} 岁 (青年期 - 组织再生快，主课间歇恢复窗口 48 小时，可耐受较高专项密度)"
    elif age < 50:
        age_desc = f"{age} 岁 (中壮年组 - 需兼顾软组织与肌腱微损伤修复，主课间歇恢复窗口 48~72 小时，增加筋膜维护)"
    else:
        age_desc = f"{age} 岁 (大师组 Masters - 肌肉蛋白合成减缓与胶原刚性下降，主课恢复窗口需 72~96 小时，严格保证超量恢复，重点强化抗阻肌力以防肌肉流失)"

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
    load_metrics = LocalStore.get_training_load(eff_uid, days=60)
    ctl = load_metrics.get("ctl", 0.0)
    atl = load_metrics.get("atl", 0.0)
    tsb = load_metrics.get("tsb", 0.0)
    acwr = load_metrics.get("acwr", 0.0)
    tsb_status = load_metrics.get("status", "稳健")
    risk_warning = load_metrics.get("risk_warning")

    # 3. Race Type Resolution & Specificity Zones
    target_race = request.target_race or "目标赛事"
    target_time_str = request.target_time or "—"
    target_time_sec = parse_time_str(target_time_str)
    race_category, race_category_name = resolve_race_category(target_race, request.race_type, target_time_sec)

    max_hr = int(user_profile.get("max_heart_rate") or 190)
    health = LocalStore.get_latest_health(eff_uid) or {}
    rest_hr = int(health.get("resting_heart_rate") or user_profile.get("resting_heart_rate") or 56)

    zones = get_race_specific_zones(
        race_type=race_category,
        target_time_seconds=target_time_sec,
        pb_seconds=marathon_pb if race_category == "marathon" else (half_pb or marathon_pb),
        max_hr=max_hr,
        rest_hr=rest_hr
    )

    # 4. Fetch recent 15 activities & multi-race calendar
    local_acts = LocalStore.get_recent_activities(eff_uid, limit=15)
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
    
    # Check if target_race matches an existing race in eval_races (exact or substring/clean match)
    matched_race = None
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
        # Align with existing database record to prevent duplicate Wugongshan / split names
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

    # Build prompt context
    user_context = f"""
跑者真实生理画像：
- 称呼/姓名: {runner_name}
- 性别: {gender_zh}
- 生理年龄状态: {age_desc}
- 跑步球龄/年限: {years_running} 年
- 最大心率: {max_hr} bpm | 晨起静息心率: {rest_hr} bpm (心率储备 HRR: {max_hr - rest_hr} bpm)
- 个人历史最佳成绩 (PB):
{pb_summary}

当前身体疲劳与负荷量化监测 (Banister EWMA 模型):
- 长期体能 (CTL / 42天负荷积累): {ctl}
- 短期疲劳 (ATL / 7天急性负荷): {atl}
- 状态平衡指数 (TSB / Form = CTL - ATL): {tsb} ({tsb_status})
- 急慢性负荷比 (ACWR): {acwr}
- 负荷安全诊断: {risk_warning or '负荷增长稳健，无突发伤病风险'}

最新生理恢复指标:
- 身体电量: {health.get('body_battery_max') or '—'}%
- 夜间平均 HRV: {health.get('hrv_last_night_avg') or '—'} ms
- 睡眠质量分: {health.get('sleep_score') or '—'} 分 (睡眠时长: {health.get('sleep_duration_hours') or '—'} 小时)

当前主要备赛目标:
- 目标比赛: {target_race}
- 赛事类型: {race_category_name}
- 目标成绩: {target_time_str}

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
        # Intelligent fallback matching race_category & TSB
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
            rec_text = f"【大师组恢复特别提示】跑者周岁满 {age} 岁，大课后需保留 72 小时超量恢复窗口，夜间保证深睡并配合蛋白质补充。"

        analysis_data = {
            "summary": f"体能稳步构建中，当前处于面向 {target_race} 的专项准备期。",
            "fitness_status": f"近期训练负荷处于稳态 (CTL: {ctl}, TSB: {tsb})，静息心率维持在 {rest_hr} bpm 基线，具备进阶专项负荷的生理基础。",
            "periodization_phase": "专项准备期 (Special Period)",
            "key_suggestions": suggs,
            "focus_workout_of_the_week": workout_desc,
            "recovery_advice": rec_text
        }

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

    # Save to local store
    if analysis_data:
        LocalStore.save_coach_report(eff_uid, analysis_data)

    return analysis_data


# ── CANOVA & DANIELS PERIODIZED TRAINING PLAN SYSTEM ──

class GenerateTrainingPlanRequest(BaseModel):
    athlete_uid: str
    goal_type: Optional[str] = "race_prep"  # "race_prep" or "fitness_maintenance"
    target_race_id: Optional[str] = None
    target_race_name: Optional[str] = None
    target_time: Optional[str] = None
    race_type: Optional[str] = None  # "marathon", "half", "trail", "10k", "5k"
    maintenance_focus: Optional[str] = None  # "aerobic_base", "lactate_threshold", "vo2max_speed", "trail_climbing", "general_maintenance"
    target_date: Optional[str] = None  # YYYY-MM-DD
    weeks_count: Optional[int] = 8
    days_per_week: Optional[int] = 4
    preferred_long_run_day: Optional[str] = "Sunday"  # "Sunday" or "Saturday"
    club_id: Optional[str] = None
    operator_uid: Optional[str] = None
    align_with_user_goal: Optional[bool] = True
    user_weekly_target: Optional[float] = None


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
    target_pace: Optional[str] = None
    target_hr_zone: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    coach_notes: Optional[str] = None
    operator_uid: str


class UpdatePlanRequest(BaseModel):
    title: Optional[str] = None
    overview_summary: Optional[str] = None
    status: Optional[str] = None  # 'active', 'archived', 'completed'
    operator_uid: str


CANOVA_PLAN_SYSTEM_PROMPT = """你是一位享誉国际的耐力运动首席训练专家，精通雷纳托·卡诺瓦 (Renato Canova) 的“专项性推进哲学”与杰克·丹尼尔斯 (Jack Daniels) 的“VDOT 能量代谢配速模型”。
你的任务是根据跑者的真实生理画像、即时负荷 (CTL/ATL/TSB)、历史 PB、以及近 12~18 个月的真实比赛和长距离实战表现，制定科学、严密、可落地的周度/日度周期训练计划 (Training Plan)。

【核心训练准则】：
1. 目标导向性：
   - 比赛备战目标 (race_prep)：倒排至比赛日。合理规划：基础构建期 (Fundamental) -> 专项准备期 (Special) -> 比赛专项期 (Specific) -> 渐进减量期 (Tapering，赛前 2-3 周递减 20%-40%-60% 容量但维持配速神经张力) -> 比赛周 (Race Week)。
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
    Intelligently generates a complete, scientifically rigorous Canova/Daniels training plan
    tailored to runner's age, VDOT paces, 18-month historical performances, and self-defined weekly target.
    """
    # Calculate key paces
    easy_pace_low = "5:35"
    easy_pace_high = "6:00"
    marathon_pace = "4:30"
    tempo_pace = "4:15"
    interval_pace = "3:55"

    if vdot and vdot > 0:
        # Approximate paces from VDOT
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

    is_trail = race_category == "trail" or "越野" in (target_race_name or "") or maintenance_focus == "trail_climbing"
    is_masters = age and age >= 50

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

    for w_idx in range(1, weeks_count + 1):
        w_start = start_monday + timedelta(weeks=w_idx - 1)
        
        # Determine phase
        if goal_type == "race_prep":
            if w_idx == weeks_count:
                phase = "比赛周 (Race Week)"
                w_title = f"第 {w_idx} 周 · {target_race_name} 巅峰之战"
                w_focus = "充分蓄能超量恢复，赛前仅做神经短冲激活，比赛日执行 100% 专项配速"
            elif w_idx >= weeks_count - 2:
                phase = "赛前减量期 (Tapering)"
                w_title = f"第 {w_idx} 周 · 渐进减量与神经保持"
                w_focus = "削减 30%~50% 总跑量，消除深层中枢疲劳，维持短冲刺激保持肌肉弹性"
            elif w_idx >= int(weeks_count * 0.6):
                phase = "专项突破期 (Specific Period)"
                w_title = f"第 {w_idx} 周 · 100% 比赛专项配速与糖原耐受"
                w_focus = "大课向目标比赛专项配速收敛，强化高配速下的肌糖原利用效率"
            elif w_idx >= int(weeks_count * 0.3):
                phase = "专项准备期 (Special Period)"
                w_title = f"第 {w_idx} 周 · 乳酸门槛与有氧扩展"
                w_focus = "提升乳酸门槛 (LT2) 平台，穿插 3x3000m 稳态巡航间歇"
            else:
                phase = "基础构建期 (Fundamental Phase)"
                w_title = f"第 {w_idx} 周 · 基础有氧扩容与线粒体激活"
                w_focus = "以低心率 Zone 2 扩充有氧耐力底座，周末稳步推进长距离"
        else:
            # Fitness maintenance
            focus_name = {
                "aerobic_base": "基础有氧扩容",
                "lactate_threshold": "乳酸阈值耐力提升",
                "vo2max_speed": "VO2Max 速度储备",
                "trail_climbing": "山地越野爬坡抗阻",
                "general_maintenance": "综合体能维持"
            }.get(maintenance_focus or "aerobic_base", "基础有氧扩容")

            if w_idx % 4 == 0:
                phase = "减量吸收周 (Down-week)"
                w_title = f"第 {w_idx} 周 · 周期性减量与超量吸收"
                w_focus = "削减 25% 跑量让机能充分恢复，防止慢性疲劳累积"
            else:
                phase = "能力强化期 (Capacity Building)"
                w_title = f"第 {w_idx} 周 · {focus_name} 专项推进"
                w_focus = f"核心围绕【{focus_name}】设计关键课，结合每周渐速长跑稳固体能"

        # Calculate weekly long run & session distances with user weekly target anchoring
        if phase in ["比赛周 (Race Week)", "赛前减量期 (Tapering)", "减量吸收周 (Down-week)"]:
            w_mult = 0.72
            lr_km = round(start_lr_dist * 0.72, 1)
        else:
            prog = min((w_idx - 1) * 0.04, 0.20)
            w_mult = 1.0 + prog
            lr_km = round(min(start_lr_dist * w_mult, 34.0 if not is_trail else 28.0), 1)

        easy_km = round(max(8.0 * scale_f * (0.8 if w_mult < 1.0 else 1.0), 5.0), 1)
        quality_km = round(max(10.0 * scale_f * (0.85 if w_mult < 1.0 else 1.0), 6.0), 1)
        shakeout_km = round(max(6.0 * scale_f * (0.8 if w_mult < 1.0 else 1.0), 4.0), 1)

        days_list = []
        # Days structure based on days_per_week
        # E.g. 4 days: Mon Rest, Tue Easy, Wed Rest, Thu Quality/Tempo, Fri Rest, Sat Easy, Sun Long Run
        for d_idx in range(7):
            cur_date = (w_start + timedelta(days=d_idx)).isoformat()
            d_name = days_labels[d_idx]

            if d_idx == 0:  # Monday: Rest
                w_item = {
                    "day_of_week": d_name,
                    "date": cur_date,
                    "workout_type": "rest",
                    "title": "完全休息 / 筋膜泡沫轴放松",
                    "distance_km": 0.0,
                    "target_pace": "—",
                    "target_hr_zone": "—",
                    "description": "彻底休息，充分让下肢肌纤维超量恢复，建议配合泡沫轴或筋膜枪进行股四头肌与小腿放松。",
                    "completed": False,
                    "coach_notes": ""
                }
            elif d_idx == 1:  # Tuesday: Easy Run
                w_item = {
                    "day_of_week": d_name,
                    "date": cur_date,
                    "workout_type": "easy_run",
                    "title": "低心率基础有氧轻松跑 (Zone 2)",
                    "distance_km": easy_km,
                    "target_pace": f"{easy_pace_low} - {easy_pace_high} /km",
                    "target_hr_zone": "心率 130-142 bpm (Zone 2)",
                    "description": f"热身 1km + {max(1.0, round(easy_km - 2.0, 1))}km 低心率稳态巡航跑 + 1km 冷身。结束后做 4 组 100m 跨步冲刺 (Strides) 激活神经刚性。",
                    "completed": False,
                    "coach_notes": ""
                }
            elif d_idx == 2:  # Wednesday: Rest or Active Recovery
                if days_per_week >= 5:
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "easy_run",
                        "title": "排酸轻松慢跑 / 力量训练",
                        "distance_km": shakeout_km,
                        "target_pace": f"{easy_pace_high} /km",
                        "target_hr_zone": "心率 < 135 bpm",
                        "description": f"极慢速排酸跑 {shakeout_km}km，结束后完成 15 分钟核心深蹲与臀中肌抗阻力量。",
                        "completed": False,
                        "coach_notes": ""
                    }
                else:
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "rest",
                        "title": "大师组周期休整日 (Active Recovery)",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "—",
                        "description": "遵循 50+ 大师组 72 小时大课恢复窗口，休整并保持充分水分与睡眠。",
                        "completed": False,
                        "coach_notes": ""
                    }
            elif d_idx == 3:  # Thursday: Quality Workout (Tempo or Intervals or Trail)
                if is_trail:
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "trail_climb",
                        "title": "山地爬坡与阶梯抗阻专项 (D+ 爬升强化)",
                        "distance_km": quality_km,
                        "target_pace": "心率控制为主",
                        "target_hr_zone": "心率 145-160 bpm (LT1-LT2)",
                        "description": f"热身 2km + 连续起伏坡道/台阶往返 {max(1.0, round(quality_km - 4.0, 1))}km (累计爬升 +400m，上坡手杖快走，下坡轻快练习股四头肌离心缓冲) + 2km 冷身。",
                        "completed": False,
                        "coach_notes": ""
                    }
                elif maintenance_focus == "vo2max_speed":
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "interval",
                        "title": f"VO2Max 速度间歇 ({quality_km}km 综合)",
                        "distance_km": quality_km,
                        "target_pace": f"{interval_pace} /km",
                        "target_hr_zone": "心率 165-175 bpm (Zone 4/5)",
                        "description": f"热身 2km + 6 × 1000m @ {interval_pace} (间歇 2 分钟原地慢走) + 冷身放松。总量 {quality_km}km。",
                        "completed": False,
                        "coach_notes": ""
                    }
                else:
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "tempo",
                        "title": "乳酸门槛巡航跑 (LT2 稳态延伸)",
                        "distance_km": quality_km,
                        "target_pace": f"{tempo_pace} /km",
                        "target_hr_zone": "心率 155-165 bpm (LT2)",
                        "description": f"热身 2km + 3 × 2500m @ {tempo_pace} (间歇 3 分钟慢跑) + 冷身。强化乳酸清除非专项耐受力，总量 {quality_km}km。",
                        "completed": False,
                        "coach_notes": ""
                    }
            elif d_idx == 4:  # Friday: Rest
                w_item = {
                    "day_of_week": d_name,
                    "date": cur_date,
                    "workout_type": "rest",
                    "title": "完全休息 / 赛前或大课前蓄能",
                    "distance_km": 0.0,
                    "target_pace": "—",
                    "target_hr_zone": "—",
                    "description": "为周末长距离大课储备糖原，早睡并保证高碳水化合物营养补充。",
                    "completed": False,
                    "coach_notes": ""
                }
            elif d_idx == 5:  # Saturday: Easy Shakeout or Rest
                if days_per_week >= 5:
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "easy_run",
                        "title": "周末前唤醒轻松跑 (Shakeout)",
                        "distance_km": shakeout_km,
                        "target_pace": f"{easy_pace_low} - {easy_pace_high} /km",
                        "target_hr_zone": "心率 128-138 bpm",
                        "description": f"轻松舒适慢跑 {shakeout_km}km，活动关节与心肺神经，不堆积疲劳。",
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
            else:  # Sunday: Long Run (The Canova Specific Long Progression)
                if phase == "比赛周 (Race Week)":
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "long_run",
                        "title": f"🏁 目标赛事正赛：{target_race_name} 突破之战！",
                        "distance_km": 42.2 if "全马" in target_race_name or "马拉松" in target_race_name else (21.1 if "半马" in target_race_name else 50.0),
                        "target_pace": f"{marathon_pace} /km",
                        "target_hr_zone": "按比赛战术心率执行",
                        "description": f"前程克制压住心率，半程后依靠扎实糖原储备稳步加速收敛，直击 {target_time_str} 目标！",
                        "completed": False,
                        "coach_notes": ""
                    }
                else:
                    w_item = {
                        "day_of_week": d_name,
                        "date": cur_date,
                        "workout_type": "long_run",
                        "title": f"周末长距离专项推进 (Long Specific Run - {lr_km}km)",
                        "distance_km": lr_km,
                        "target_pace": f"{easy_pace_low} 渐进至 {marathon_pace} /km",
                        "target_hr_zone": "心率 135-155 bpm (Z2-Z3)",
                        "description": f"前 {round(lr_km * 0.6, 1)}km 保持在 {easy_pace_low} 低心率稳态，后 {round(lr_km * 0.4, 1)}km 渐进提升至目标专项配速 ({marathon_pace})，演练每 45 分钟补胶与电解质水。",
                        "completed": False,
                        "coach_notes": ""
                    }

            days_list.append(w_item)

        total_week_km = round(sum(d["distance_km"] for d in days_list), 1)
        weeks.append({
            "week_index": w_idx,
            "week_title": w_title,
            "phase": phase,
            "weekly_mileage_km": total_week_km,
            "key_focus": w_focus,
            "days": days_list
        })

    focus_cn = {
        "aerobic_base": "基础有氧耐力扩容",
        "lactate_threshold": "乳酸阈值耐力提升",
        "vo2max_speed": "VO2Max 速度储备",
        "trail_climbing": "山地越野爬坡抗阻",
        "general_maintenance": "综合体能维持"
    }.get(maintenance_focus or "aerobic_base", "非赛期专项强化")

    target_display = target_race_name if goal_type == "race_prep" else focus_cn
    title = f"{athlete_name} · {target_display} {weeks_count}周科学训练计划"
    summary = f"严格结合跑者真实生理画像（{age or 35}岁大师组恢复律、VO2Max {vdot or 50.0}），参考过去18个月历史长拉练能力（单次最长 {max_long_run_18m_km}km），按照 Canova 专项收敛律推进。"
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
    eff_uid = req.athlete_uid
    canonical_uid = LocalStore.resolve_user_id(eff_uid)
    user_profile = LocalStore.get_profile(canonical_uid) or {}
    runner_name = user_profile.get("display_name") or user_profile.get("email", "").split("@")[0] or "跑者"
    gender = str(user_profile.get("gender") or "male")
    gender_zh = "女" if gender.lower() == "female" else "男"
    dob_str = user_profile.get("date_of_birth")
    age = get_age_from_dob(dob_str)
    
    # Biometrics & VO2Max
    vo2max = user_profile.get("vo2max")
    health = LocalStore.get_latest_health(canonical_uid) or {}
    if not vo2max and health.get("vo2_max"):
        vo2max = health.get("vo2_max")

    marathon_pb = user_profile.get("marathon_pb")
    half_pb = user_profile.get("half_pb")
    ten_k_pb = user_profile.get("ten_k_pb")
    five_k_pb = user_profile.get("five_k_pb")

    if not vo2max:
        # Calculate from marathon or half PB
        if marathon_pb:
            v_calc = calculate_vdot(42195.0, float(marathon_pb))
            vo2max = round(v_calc, 1) if v_calc else 50.0
        elif half_pb:
            v_calc = calculate_vdot(21097.5, float(half_pb))
            vo2max = round(v_calc, 1) if v_calc else 50.0
        else:
            vo2max = 48.0

    # Training Load CTL/ATL/TSB
    load_metrics = LocalStore.get_training_load(canonical_uid, days=60)
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

    # Resolve target and race details
    goal_type = req.goal_type or "race_prep"
    target_race_name = req.target_race_name or "目标赛事"
    target_time_str = req.target_time or "3:15:00"
    target_time_sec = parse_time_str(target_time_str)

    race_category, race_category_name = resolve_race_category(target_race_name, req.race_type, target_time_sec)

    # Date and weeks calculation
    today = date.today()
    # Find next Monday (or today if today is Monday)
    start_monday = today - timedelta(days=today.weekday())  # Current week Monday

    weeks_count = req.weeks_count or 8
    if req.target_date and goal_type == "race_prep":
        try:
            t_date = datetime.strptime(req.target_date[:10], "%Y-%m-%d").date()
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
        if r.get("race_date") and start_date <= str(r["race_date"])[:10] <= end_date
    ]

    # Age category prompt description
    if age is None:
        age_desc = "未登记年龄（按 32 岁中青年 48 小时恢复窗口规划）"
    elif age < 35:
        age_desc = f"{age} 岁 (青年组 - 恢复快，大课恢复窗口 48 小时，耐受专项密度高)"
    elif age < 50:
        age_desc = f"{age} 岁 (中壮年组 - 大课恢复窗口需 48~72 小时，增加筋膜维护)"
    else:
        age_desc = f"{age} 岁 (大师组 Masters - 肌肉胶原与糖原合成较缓，大课后需保留 72~96 小时超量恢复窗口，坚决执行 Hard-Easy 规律，防肌肉流失与关节损伤)"

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

    # Build prompt context
    user_context = f"""
跑者真实画像：
- 姓名/昵称: {runner_name}
- 性别: {gender_zh} | 生理年龄: {age_desc}
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
请根据以上跑者的真实生理承受力、历史表现、自定目标与既定赛历，为跑者生成包含第 1 周到第 {weeks_count} 周的完整周度/日度训练课表。直接输出标准 JSON。
"""

    messages = [
        {"role": "system", "content": CANOVA_PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user_context}
    ]

    schedule_data = None
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

    operator = req.operator_uid or eff_uid

    # Upsert plan into DB
    saved_plan = LocalStore.upsert_training_plan({
        "user_id": canonical_uid,
        "club_id": req.club_id,
        "title": plan_title,
        "goal_type": goal_type,
        "maintenance_focus": maintenance_focus,
        "target_race_id": req.target_race_id,
        "target_race_name": target_race_name,
        "target_date": req.target_date or end_date,
        "start_date": start_date,
        "end_date": end_date,
        "weeks_count": weeks_count,
        "days_per_week": days_per_week,
        "preferred_long_run_day": req.preferred_long_run_day or "Sunday",
        "status": "active",
        "overview_summary": plan_overview,
        "schedule_data": schedule_data,
        "creator_id": operator,
        "last_modified_by": operator
    })

    return {
        "success": True,
        "message": f"成功为 {runner_name} 生成 {weeks_count} 周科学训练计划！",
        "plan": saved_plan
    }


@router.get("/plan/user/{uid}")
def get_user_training_plan(uid: str):
    """
    Returns the active training plan for the specified user,
    plus history of archived plans, along with user's current goal targets for alignment.
    """
    canonical_uid = LocalStore.resolve_user_id(uid)
    plan = LocalStore.get_user_active_training_plan(canonical_uid)
    past_plans = LocalStore.get_user_training_plans(canonical_uid, limit=5)
    user_goal = LocalStore.get_goal(canonical_uid)
    return {
        "active_plan": plan,
        "past_plans": past_plans,
        "user_goal": user_goal
    }


@router.get("/plan/user/{uid}/today")
def get_user_today_workout(uid: str):
    """
    Returns today's specific workout from the athlete's active training plan.
    """
    canonical_uid = LocalStore.resolve_user_id(uid)
    today_workout = LocalStore.get_today_workout(canonical_uid)
    return {"today_workout": today_workout}


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

    # Update affected months in monthly_targets
    for m_idx, planned_km in month_km_map.items():
        if 1 <= m_idx <= 12 and planned_km > 0:
            monthly_targets[m_idx - 1] = round(max(planned_km, new_weekly_target * 3.5), 1)

    new_monthly_target = round(new_weekly_target * 4.0, 1)

    updated_goal_data = {
        "user_id": canonical_uid,
        "target_distance": new_monthly_target,
        "weekly_target": new_weekly_target,
        "period_type": "monthly",
        "monthly_targets": monthly_targets
    }
    LocalStore.upsert_goal(canonical_uid, updated_goal_data)

    return {
        "success": True,
        "message": f"成功将训练计划同步为个人跑量目标！自定周目标已更新为 {new_weekly_target} km/周，月度基准设为 {new_monthly_target} km/月。",
        "weekly_target": new_weekly_target,
        "monthly_target": new_monthly_target,
        "monthly_targets": monthly_targets
    }


@router.put("/plan/{plan_id}")
def update_training_plan_overview(plan_id: str, req: UpdatePlanRequest):
    """
    Updates the plan title, overview summary, or status.
    """
    plan = LocalStore.get_training_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="训练计划不存在")

    update_fields = {}
    if req.title:
        update_fields["title"] = req.title
    if req.overview_summary:
        update_fields["overview_summary"] = req.overview_summary
    if req.status:
        update_fields["status"] = req.status
    update_fields["last_modified_by"] = req.operator_uid

    # Update in DB
    with sqlite3.connect(LocalStore.get_db_path() if hasattr(LocalStore, "get_db_path") else "backend/data/rgm.db") as conn:
        cursor = conn.cursor()
        now_iso = datetime.utcnow().isoformat() + "Z"
        set_clauses = [f"{k} = ?" for k in update_fields.keys()]
        set_clauses.append("updated_at = ?")
        vals = list(update_fields.values()) + [now_iso, plan_id]
        cursor.execute(f"UPDATE training_plans SET {', '.join(set_clauses)} WHERE id = ?", vals)
        conn.commit()

    updated = LocalStore.get_training_plan(plan_id)
    return {"message": "计划信息已更新", "plan": updated}


@router.patch("/plan/{plan_id}/workout")
def update_plan_workout_item(plan_id: str, req: UpdateWorkoutRequest):
    """
    Fine-grained collaborative editing of a single workout in the plan.
    Allows athlete or coach to modify distance, pace, workout type, completion status, or add coach notes.
    """
    plan = LocalStore.get_training_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="训练计划不存在")

    workout_update = {}
    for k in ["workout_type", "title", "distance_km", "target_pace", "target_hr_zone", "description", "completed", "coach_notes", "date"]:
        v = getattr(req, k)
        if v is not None:
            workout_update[k] = v

    updated_plan = LocalStore.update_training_plan_workout(
        plan_id=plan_id,
        week_index=req.week_index,
        day_index=req.day_index,
        workout_update=workout_update,
        operator_uid=req.operator_uid
    )

    if not updated_plan:
        raise HTTPException(status_code=400, detail="未找到对应周或日的课表")

    return {
        "success": True,
        "message": "训练课表已更新",
        "plan": updated_plan
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


