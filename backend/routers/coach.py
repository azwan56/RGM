from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import json
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

def resolve_race_category(race_name: str, race_type: Optional[str] = None) -> tuple[str, str]:
    """Returns (race_key, race_display_name)."""
    combined = f"{race_name} {race_type or ''}".lower()
    if any(k in combined for k in ["越野", "trail", "ultra", "50k", "100k", "武功山", "崇礼", "柴古", "utmb"]):
        return "trail", "越野超马 / 山地耐力赛 (Trail & Ultra)"
    elif any(k in combined for k in ["半马", "半程", "half"]):
        return "half", "半程马拉松 (Half Marathon)"
    elif any(k in combined for k in ["10k", "10公里"]):
        return "10k", "10公里场地/路跑 (10K Road/Track)"
    elif any(k in combined for k in ["5k", "5公里"]):
        return "5k", "5公里场地/路跑 (5K Road/Track)"
    else:
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
    race_category, race_category_name = resolve_race_category(target_race, request.race_type)
    target_time_sec = parse_time_str(target_time_str)

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
            race_category, race_category_name = resolve_race_category(target_race, matched_race.get("race_type"))
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

    # Save to local store
    if analysis_data:
        LocalStore.save_coach_report(eff_uid, analysis_data)

    return analysis_data

