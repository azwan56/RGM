from fastapi import APIRouter
from pydantic import BaseModel
from firebase_config import db
import os
import json
import asyncio

router = APIRouter()

_api_key = os.getenv("GEMINI_API_KEY")

# Model preference order — try these in sequence
_MODEL_CANDIDATES = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-2.0-flash-lite",
    "gemini-pro",
]
_resolved_model = None  # Will be set on first successful call

import requests as http_requests

def _gemini_generate(prompt: str, temperature: float = 0.6, max_tokens: int = 6000, response_json: bool = True) -> dict:
    """Call Gemini REST API directly, bypassing SDK version issues."""
    global _resolved_model

    models_to_try = [_resolved_model] if _resolved_model else _MODEL_CANDIDATES

    last_error = None
    for model_name in models_to_try:
        for api_ver in ["v1beta", "v1"]:
            url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model_name}:generateContent?key={_api_key}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            if response_json:
                body["generationConfig"]["responseMimeType"] = "application/json"

            try:
                resp = http_requests.post(url, json=body, timeout=60)
                if resp.status_code == 200:
                    _resolved_model = model_name  # Cache working model
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return {"text": text, "model": model_name, "api_version": api_ver}
                else:
                    last_error = f"{model_name}@{api_ver}: {resp.status_code} {resp.text[:200]}"
                    print(f"[gemini] {last_error}")
            except Exception as e:
                last_error = f"{model_name}@{api_ver}: {e}"
                print(f"[gemini] {last_error}")

    raise Exception(f"All Gemini models failed. Last error: {last_error}")


@router.get("/debug-models")
async def debug_models():
    """List available Gemini models for diagnostics."""
    results = {}
    for api_ver in ["v1beta", "v1"]:
        url = f"https://generativelanguage.googleapis.com/{api_ver}/models?key={_api_key}"
        try:
            resp = http_requests.get(url, timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                results[api_ver] = [m.get("name", "") for m in models if "generateContent" in str(m.get("supportedGenerationMethods", []))]
            else:
                results[api_ver] = f"Error {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            results[api_ver] = str(e)
    return results

class CoachRequest(BaseModel):
    uid: str

# ── Firestore helpers (run in thread pool) ────────────────────────────────────

def _fetch_leaderboard(uid: str):
    doc = db.collection("leaderboard").document(uid).get()
    return doc.to_dict() if doc.exists else None

def _fetch_goal(uid: str):
    doc = db.collection("users").document(uid).collection("goals").document("current").get()
    return doc.to_dict() if doc.exists else None

def _fetch_recent_activities(uid: str, n: int = 5):
    docs = (
        db.collection("users").document(uid)
        .collection("activities")
        .order_by("start_date_local", direction="DESCENDING")
        .limit(n)
        .stream()
    )
    return [d.to_dict() for d in docs]

def _build_runs_str(acts: list) -> str:
    if not acts:
        return "No recent activities."
    lines = [
        f"{a.get('start_date_local','')[:10]} "
        f"{a.get('distance_km',0)}km "
        f"@{a.get('avg_pace','?')}/km "
        f"HR:{a.get('avg_heart_rate',0)}bpm "
        f"Elev:{a.get('total_elevation_gain',0)}m"
        for a in acts
    ]
    return " | ".join(lines)

_FALLBACK = {
    "status": "继续加油 💪",
    "summary": "你的训练保持了很好的一致性！继续专注跑姿，循序渐进地提升吧。",
    "encouragement": "每一步都是进步，坚持就是胜利！",
    "actionable_tips": [
        "80% 的跑步保持轻松配速，能聊天的节奏最好",
        "注意补水和睡眠，恢复和训练同样重要",
        "每周跑量增幅不超过 10%，循序渐进",
        "每周安排 1 次速度训练（间歇跑或节奏跑）提升心肺能力",
    ]
}

# ── Endpoint ──────────────────────────────────────────────────────────────────

def _build_race_fallback(nearest_race, nearest_days, runner_name, stats):
    """Generate race-specific fallback advice when Gemini API is unavailable."""
    if not nearest_race or nearest_days > 120:
        return {
            **_FALLBACK,
            "summary": f"{runner_name}，你已完成 {stats.get('total_distance_km', 0)} 公里，保持节奏！"
                       if stats else _FALLBACK["summary"],
        }

    rtype = nearest_race.get("type", "")
    rname = nearest_race.get("name", "比赛")
    rtarget = nearest_race.get("target_time", "")

    race_label = {
        "10k": "10K", "half_marathon": "半马", "full_marathon": "全马",
        "gobi": "戈壁挑战赛", "trail_50k": "越野50K",
        "trail_100k": "越野100K", "trail_100m": "越野100英里",
    }.get(rtype, rtype)

    # Phase-specific tips
    if nearest_days <= 7:
        status = "赛前倒计时 ⏳"
        summary = (
            f"{runner_name}，距{rname}（{race_label}）仅剩 {nearest_days} 天！"
            f"现在是赛前减量期，保持轻松跑维持状态即可，千万不要追求强度。"
        )
        encouragement = "信任你的训练，你已经准备好了！"
        tips = [
            f"跑量降至平时的 30-40%，每次跑步不超过 30-40 分钟",
            "赛前 2 天完全休息或仅做 15 分钟慢跑 + 动态拉伸",
            "调整作息，确保赛前连续 3 晚睡够 7-8 小时",
            "准备比赛装备清单：号码布、能量胶、凡士林、备用袜子",
        ]
        if rtype in ("gobi", "trail_100k", "trail_100m", "trail_50k"):
            tips.append("检查越野装备：头灯电池、水袋、应急毯、急救包")
        if rtarget:
            tips.append(f"回顾目标配速 {rtarget}，比赛前半段保守，后半段发力")

    elif nearest_days <= 14:
        status = "赛前调整期 📋"
        summary = (
            f"{runner_name}，距{rname}还有 {nearest_days} 天，"
            f"进入赛前调整期。减量但不停跑，1-2 次短距离配速跑验证状态。"
        )
        encouragement = "减量期的不安是正常的，相信过程！"
        tips = [
            "本周跑量减至高峰期的 50-60%，以轻松跑为主",
            f"安排 1 次 5-8km 的{race_label}目标配速跑，验证体感",
            "增加碳水摄入比例，赛前 3 天进行糖原补充",
            "提前研究赛道路线、补给站位置和海拔变化",
        ]
        if rtype in ("gobi", "trail_100k", "trail_100m"):
            tips.append("最后一次装备全套测试跑，确保无磨脚、背包晃动等问题")

    elif nearest_days <= 30:
        status = "备赛冲刺 🔥"
        summary = (
            f"{runner_name}，距{rname}还有 {nearest_days} 天，"
            f"这是最后的高质量训练窗口！保持强度但注意恢复，避免受伤。"
        )
        encouragement = "冲刺阶段，每一次训练都在为赛道蓄力！"
        tips = [
            f"每周安排 1 次{race_label}比赛配速的中长距离跑（15-25km）",
            "每周 1 次间歇跑或节奏跑，维持速度感",
            "注意身体信号，任何不适立即减量，保护性训练",
            "模拟比赛日流程：起床时间、赛前餐、热身节奏",
        ]
        if rtype == "full_marathon":
            tips.insert(0, "完成最后一次 30-32km 长距离拉练，之后开始逐步减量")
        elif rtype in ("gobi", "trail_100k", "trail_100m"):
            tips.insert(0, "完成最后一次 40-50km 的超长距离训练或连续 2 天背靠背长距离")

    elif nearest_days <= 60:
        status = "专项训练期 📈"
        summary = (
            f"{runner_name}，距{rname}还有 {nearest_days} 天，"
            f"正是提升比赛专项能力的关键阶段，跑量接近峰值。"
        )
        encouragement = "此刻的汗水，都会成为赛道上的底气！"
        tips = [
            f"周跑量稳定在备赛峰值，长距离拉练每周递增 2-3km",
            "每周 1-2 次比赛配速训练，找到比赛节奏",
            "加入一些高于比赛配速的间歇训练，提升乳酸阈值",
            "关注营养恢复，训练后 30 分钟内补充蛋白质和碳水",
        ]
    else:
        status = "基础储备期 💪"
        summary = (
            f"{runner_name}，距{rname}还有 {nearest_days} 天，"
            f"目前以打基础为主，稳步提升周跑量和有氧耐力。"
        )
        encouragement = "基础打得越扎实，赛道上越从容！"
        tips = [
            "80% 的跑步保持轻松配速（MAF 心率或能聊天的节奏）",
            "每周跑量增幅不超过 10%，循序渐进积累",
            "每周 1 次长距离慢跑，逐步延长到赛事距离的 60-70%",
            "加入核心力量训练和柔韧性训练，预防跑步伤病",
        ]

    return {
        "status": status,
        "summary": summary,
        "encouragement": encouragement,
        "actionable_tips": tips[:5],
    }

@router.post("/analyze")
async def generate_coach_feedback(req: CoachRequest):
    """
    Returns structured AI coaching feedback in Chinese.
    Parallel Firestore reads + personalized, encouraging tone.
    """
    loop = asyncio.get_event_loop()
    stats, goal_data, activities, profile = await asyncio.gather(
        loop.run_in_executor(None, _fetch_leaderboard, req.uid),
        loop.run_in_executor(None, _fetch_goal, req.uid),
        loop.run_in_executor(None, _fetch_recent_activities, req.uid),
        loop.run_in_executor(None, _fetch_profile, req.uid),
    )

    if not stats:
        return {"feedback": {
            "status": "等待数据 📊",
            "summary": "同步你的 Strava 数据，即可获得 AI 教练的专属建议！",
            "encouragement": "跑步之旅从第一步开始 🏃",
            "actionable_tips": []
        }}

    # Build rich context for personalized coaching
    goal_str = "暂未设定具体目标"
    if goal_data:
        period_cn = {"weekly": "每周", "monthly": "每月"}.get(goal_data.get("period", "monthly"), "每月")
        goal_str = (
            f"目标 {goal_data.get('target_distance', 0)} 公里/{period_cn}，"
            f"配速目标：{goal_data.get('target_pace', '未设')}"
        )

    # Profile context
    runner_name = (
        profile.get("display_name") or profile.get("strava_name")
        or profile.get("email", "").split("@")[0] or "跑者"
    ) if profile else "跑者"
    training_goal = profile.get("training_goal", "fitness") if profile else "fitness"
    years_running = profile.get("years_running", 0) if profile else 0
    # Compute age from date_of_birth, fallback to legacy 'age' field
    _dob = profile.get("date_of_birth", "") if profile else ""
    if _dob:
        try:
            from datetime import date as _d
            _born = _d.fromisoformat(_dob)
            _today = _d.today()
            age = _today.year - _born.year - ((_today.month, _today.day) < (_born.month, _born.day))
        except (ValueError, TypeError):
            age = profile.get("age", "") if profile else ""
    else:
        age = profile.get("age", "") if profile else ""

    goal_cn = {
        "fitness": "健康健身", "5k": "5K 突破", "10k": "10K 提升",
        "half": "半马训练", "full": "全马备赛", "ultra": "超马挑战",
    }.get(training_goal, training_goal)

    # Race context — multiple upcoming races
    race_type_cn = {
        "10k": "10K 路跑赛",
        "half_marathon": "半程马拉松",
        "full_marathon": "全程马拉松",
        "gobi": "戈壁挑战赛（连续3天共120K竞技赛事）",
        "trail_50k": "越野跑 50K",
        "trail_100k": "越野跑 100K",
        "trail_100m": "越野跑 100英里",
    }
    upcoming_races = profile.get("upcoming_races", []) if profile else []
    race_lines = []
    has_gobi = False
    if upcoming_races:
        from datetime import date
        for r in upcoming_races:
            rtype = race_type_cn.get(r.get("type", ""), r.get("type", ""))
            rname = r.get("name", rtype)
            rdate = r.get("date", "")
            rtarget = r.get("target_time", "")
            countdown = ""
            if rdate:
                try:
                    days = (date.fromisoformat(rdate) - date.today()).days
                    if days > 0:
                        countdown = f"（还有{days}天）"
                    elif days == 0:
                        countdown = "（今天！）"
                    else:
                        continue  # skip past races
                except ValueError:
                    pass
            line = f"  · {rname}（{rtype}）{rdate}{countdown}"
            if rtarget:
                line += f" 目标成绩：{rtarget}"
            race_lines.append(line)
            if r.get("type") == "gobi":
                has_gobi = True

    race_section = ""
    nearest_race = None
    nearest_days = 999
    if race_lines:
        race_section = "【备赛计划】\n" + "\n".join(race_lines) + "\n"
        if has_gobi:
            race_section += "⚠️ 戈壁挑战赛为连续3天共120K的高强度竞技赛事，训练要求激进，需要大量耐力储备和越野适应训练\n"
        race_section += "\n"

    # Find the nearest upcoming race for focused coaching
    if upcoming_races:
        from datetime import date
        for r in upcoming_races:
            rdate = r.get("date", "")
            if rdate:
                try:
                    days = (date.fromisoformat(rdate) - date.today()).days
                    if 0 <= days < nearest_days:
                        nearest_days = days
                        nearest_race = r
                except ValueError:
                    pass

    # Build race-specific coaching instructions
    race_coaching_instructions = ""
    if nearest_race:
        rtype = nearest_race.get("type", "")
        rname = nearest_race.get("name", "")
        rtarget = nearest_race.get("target_time", "")
        race_label = race_type_cn.get(rtype, rtype)

        # Determine training phase
        if nearest_days <= 7:
            phase = "赛前减量期"
            phase_detail = "距比赛仅剩1周以内，应大幅减量，保持状态但不追求强度。重点是休息、营养、心理准备。"
        elif nearest_days <= 14:
            phase = "赛前调整期"
            phase_detail = "距比赛2周，开始逐步减量（减至高峰期的50-60%），可安排1-2次短距离配速跑验证状态，但不追求新的训练刺激。"
        elif nearest_days <= 30:
            phase = "冲刺期"
            phase_detail = "距比赛1个月，这是最后的高质量训练窗口。保持强度但注意恢复，避免受伤。每周安排1次比赛配速跑。"
        elif nearest_days <= 60:
            phase = "专项期"
            phase_detail = "距比赛2个月，重点提升比赛专项能力。增加比赛配速训练和长距离拉练，跑量接近峰值。"
        elif nearest_days <= 120:
            phase = "基础期"
            phase_detail = "距比赛3-4个月，重点打基础。稳步提升周跑量，80%有氧 + 20%速度，建立耐力储备。"
        else:
            phase = "准备期"
            phase_detail = "距比赛尚远，可以轻松积累跑量，逐步建立训练习惯和基础体能。"

        # Race difficulty context
        race_difficulty = ""
        if rtype in ("gobi", "trail_100k", "trail_100m"):
            race_difficulty = (
                "这是一场极高难度的超长距离赛事，需要特别关注：\n"
                "  - 超长距离耐力储备（周跑量建议60-100km+）\n"
                "  - 越野地形适应训练（爬升、下坡技术）\n"
                "  - 补给策略（能量胶、电解质、固体食物搭配）\n"
                "  - 装备测试（越野鞋、背包、头灯、急救包）\n"
                "  - 心理韧性训练（长时间独处运动的心理准备）\n"
            )
            if rtype == "gobi":
                race_difficulty += (
                    "  - 戈壁特殊要素：防晒防沙、极端气候适应、连续3天恢复策略\n"
                    "  - 需要提前进行连续2-3天背靠背长距离训练\n"
                )
        elif rtype == "full_marathon":
            race_difficulty = "全程马拉松需要扎实的有氧基础，建议赛前至少完成2-3次30km+的长距离拉练。\n"
        elif rtype == "trail_50k":
            race_difficulty = "50K越野需要良好的爬升能力和下坡技术，建议增加山地训练和负重跑。\n"

        # PB target analysis
        pb_analysis = ""
        if rtarget:
            pb_analysis = f"目标成绩 {rtarget}，请根据跑者当前配速和心率数据，分析目标是否合理，给出达成目标的具体训练配速建议。\n"

        race_coaching_instructions = (
            f"\n【⚡ 重点备赛指导 — {rname or race_label}】\n"
            f"最近的比赛：{rname}（{race_label}），距今 {nearest_days} 天\n"
            f"当前阶段：{phase}\n"
            f"{phase_detail}\n"
            f"{race_difficulty}"
            f"{pb_analysis}"
            f"请围绕这场比赛的备赛需求给出有针对性的训练建议，"
            f"包括本周具体训练重点和需要注意的事项。\n\n"
        )

    # ── Build context variables used in prompt ───────────────────────────────
    runs_str = _build_runs_str(activities)
    completion_pct = stats.get("goal_completion_percentage", 0)

    # ── Training phase for plan (reuse nearest_race computed above) ──────────
    from datetime import date as _dclz
    plan_phase_block = ""
    if nearest_race:
        _rtype  = nearest_race.get("type", "")
        _rname  = nearest_race.get("name", _rtype)
        _rtarget= nearest_race.get("target_time", "")
        _rcn    = {"10k":"10K","half_marathon":"半程马拉松","full_marathon":"全程马拉松",
                   "gobi":"戈壁挑战赛（连续3天120K）","trail_50k":"越野50K",
                   "trail_100k":"越野100K","trail_100m":"越野100英里"}.get(_rtype, _rtype)
        if nearest_days <= 7:
            _phase = "赛前减量期"
            _prules = "跑量减至40%，至少3个休息日，最多1次短配速验证跑（≤5km），禁高强度。"
        elif nearest_days <= 21:
            _phase = "赛前调整期"
            _prules = f"赛前{nearest_days}天，跑量减至峰值60%，1次配速验证跑（≤8km），须有2个休息日。"
        elif nearest_days <= 42:
            _phase = "赛前冲刺期"
            _prules = f"距赛{nearest_days}天，1次目标配速中长距离（15-25km），1次间歇/节奏跑，1-2个休息日。"
        elif nearest_days <= 84:
            _phase = "专项训练期"
            _prules = "长距离+节奏跑+间歇三合一，配速向目标靠近，跑量接近峰值。"
        else:
            _phase = "基础储备期"
            _prules = "稳步堆跑量，80%轻松有氧，每周1次长距离慢跑。"
        plan_phase_block = (
            f"比赛：{_rname}（{_rcn}），还有{nearest_days}天，阶段：【{_phase}】\n"
            f"本周计划约束：{_prules}\n"
        )

    profile_vdot = profile.get("vdot") if profile else None
    profile_max_hr = profile.get("max_heart_rate", 190) if profile else 190
    profile_rest_hr = profile.get("resting_heart_rate", 60) if profile else 60
    profile_years = years_running
    profile_gender = profile.get("gender", "other") if profile else "other"
    profile_age = age

    prompt = (
        "你是一位热情、专业、善于鼓励的中文跑步教练。\n"
        "请根据以下跑者信息，**同时**输出：① 今日训练分析建议 ② 从明天开始的7天训练计划。\n"
        "两者必须高度一致：7天计划是分析建议的具体日程落地。\n"
        "回复必须是纯 JSON，不含 markdown 标记。\n\n"
        f"【跑者档案】\n"
        f"- 称呼：{runner_name}，年龄：{profile_age or '未知'}，性别：{profile_gender}，跑龄：{profile_years}年\n"
        f"- 训练目标：{goal_cn}，VDOT：{profile_vdot or '未知'}\n"
        f"- 最大心率：{profile_max_hr}，静息心率：{profile_rest_hr}\n"
        f"- 当前里程目标：{goal_str}\n\n"
        f"{race_section}"
        f"{race_coaching_instructions}"
        f"【本期训练数据（{stats.get('period', 'monthly')}）】\n"
        f"- 总里程：{stats.get('total_distance_km', 0)} 公里\n"
        f"- 平均配速：{stats.get('avg_pace', '?')}/km\n"
        f"- 平均心率：{stats.get('avg_heart_rate', 0)} bpm\n"
        f"- 跑步次数：{stats.get('run_count', 0)} 次，目标完成度：{completion_pct}%\n\n"
        f"【近期跑步记录】\n{runs_str}\n\n"
        f"【7天计划约束】\n{plan_phase_block if plan_phase_block else '无临近比赛，按训练目标制定。'}\n\n"
        "【输出格式 — 严格按以下 JSON 结构返回，不含任何 markdown】\n"
        "{\n"
        '  "feedback": {\n'
        '    "status": "<状态标签，如：备赛冲刺 🔥|稳步提升 📈|状态出色 💪|注意恢复 😴|继续加油 🏃>",\n'
        '    "summary": "<2-3句训练总结，结合比赛阶段和数据>",\n'
        '    "encouragement": "<一句简短有力的鼓励金句>",\n'
        '    "actionable_tips": ["具体建议1", "具体建议2", "具体建议3", "具体建议4"]\n'
        "  },\n"
        '  "plan": {\n'
        '    "plan_summary": "<1-2句说明本周计划主旨及与教练建议的关联>",\n'
        '    "weekly_km": <总公里数>,\n'
        '    "days": [\n'
        '      {\n'
        '        "day": 1,\n'
        '        "type": "<Easy|Tempo|Interval|Long Run|Recovery|Rest|Cross Training>",\n'
        '        "title": "<中文训练标题，体现训练目的>",\n'
        '        "distance_km": <公里数，休息日为0>,\n'
        '        "pace_target": "<如5:30-6:00，休息日为null>",\n'
        '        "hr_zone": "<如Zone 2，休息日为null>",\n'
        '        "duration_min": <预估分钟数>,\n'
        '        "description": "<详细描述：热身+主课(含配速/心率)+冷身+说明此训练如何落地教练的某条建议>",\n'
        '        "intensity": <1-5强度>\n'
        "      }\n"
        "    ]\n"
        "  }\n"
        "}\n\n"
        "规则：\n"
        "1. 若有备赛阶段约束，plan 必须严格遵守，不可违背\n"
        "2. 7天计划必须能直接执行 feedback 中的 actionable_tips\n"
        "3. 语气温暖鼓励，建议具体可操作\n"
        "4. 安排1-2个休息日，长距离跑在周末\n"
        "5. description 必须有热身/主课/冷身详细步骤\n"
    )

    if not _api_key:
        fb = _build_race_fallback(nearest_race, nearest_days, runner_name, stats)
        return {"feedback": fb, "plan": None}


    try:
        print(f"Coach prompt length: {len(prompt)} chars")
        response = await loop.run_in_executor(
            None,
            lambda: _gemini_generate(prompt, temperature=0.6, max_tokens=6000)
        )
        print(f"[coach] Used model: {response['model']}@{response['api_version']}")
        text = response["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        result = json.loads(text)

        # Handle combined {feedback, plan} format
        if "feedback" in result:
            feedback = result["feedback"]
            plan = result.get("plan")
        else:
            feedback = result  # legacy flat format fallback
            plan = None

        if "encouragement" not in feedback:
            feedback["encouragement"] = "每一步都是进步，坚持就是胜利！"

        # ─ Save both to Firestore ─
        try:
            db.collection("users").document(req.uid).collection("coach").document("latest_analysis").set({
                **feedback,
                "saved_at": __import__("datetime").datetime.now().isoformat(),
                "nearest_race_days": nearest_days if nearest_days < 9999 else None,
                "nearest_race_name": nearest_race.get("name", "") if nearest_race else "",
            }, merge=False)
            if plan:
                from datetime import date as _d
                db.collection("users").document(req.uid).collection("training_plans").document(
                    _d.today().isoformat()).set({**plan, "generated_at": _d.today().isoformat()}, merge=True)
        except Exception as _save_err:
            print(f"[coach] Failed to save: {_save_err}")

        return {"feedback": feedback, "plan": plan}

    except json.JSONDecodeError as e:
        print(f"Coach JSON parse error: {e}")
        fb = _build_race_fallback(nearest_race, nearest_days, runner_name, stats)
        try:
            db.collection("users").document(req.uid).collection("coach").document("latest_analysis").set(
                {**fb, "saved_at": __import__("datetime").datetime.now().isoformat()}, merge=False)
        except Exception:
            pass
        return {"feedback": fb, "plan": None}
    except Exception as e:
        print(f"Coach generation failed: {e}")
        fb = _build_race_fallback(nearest_race, nearest_days, runner_name, stats)
        fb["_error"] = str(e)
        try:
            db.collection("users").document(req.uid).collection("coach").document("latest_analysis").set(
                {**{k: v for k, v in fb.items() if not k.startswith("_")},
                 "saved_at": __import__("datetime").datetime.now().isoformat()}, merge=False)
        except Exception:
            pass
        return {"feedback": fb, "plan": None}


# ── Training Plan Generator ──────────────────────────────────────────────────

class TrainingPlanRequest(BaseModel):
    uid: str


def _fetch_profile(uid: str):
    doc = db.collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else {}


def _fetch_recent_14d(uid: str):
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    docs = (db.collection("users").document(uid)
              .collection("activities")
              .where("start_date_local", ">=", cutoff)
              .order_by("start_date_local", direction="DESCENDING")
              .limit(30)
              .stream())
    return [d.to_dict() for d in docs]


def _build_training_plan_fallback(total_km_14d: float, training_goal: str, upcoming_races: list) -> dict:
    """Returns a sensible template 7-day training plan when AI is unavailable."""
    from datetime import date, timedelta
    # Estimate weekly volume from last 14 days (half of 14d total)
    weekly_base = max(20, round(total_km_14d / 2))
    long_run = round(weekly_base * 0.35)
    tempo = round(weekly_base * 0.20)
    easy1 = round(weekly_base * 0.18)
    easy2 = round(weekly_base * 0.17)
    total = long_run + tempo + easy1 + easy2

    days = [
        {"day": 1, "type": "Easy", "title": "轻松恢复跑", "distance_km": easy1,
         "pace_target": "6:00-6:30", "hr_zone": "Zone 2", "duration_min": easy1 * 6,
         "description": f"热身跑2km，以轻松舒适的配速跑{easy1}km，心率保持在最大心率65-75%，冷身慢跑1km+静态拉伸10分钟。",
         "intensity": 2},
        {"day": 2, "type": "Tempo", "title": "节奏跑", "distance_km": tempo,
         "pace_target": "5:00-5:30", "hr_zone": "Zone 3-4", "duration_min": tempo * 5,
         "description": f"热身跑2km+动态拉伸，主课：{max(tempo-4, 4)}km节奏跑（比马拉松配速快30-45秒），冷身慢跑2km+拉伸。",
         "intensity": 4},
        {"day": 3, "type": "Rest", "title": "完全休息", "distance_km": 0,
         "pace_target": None, "hr_zone": None, "duration_min": 0,
         "description": "完全休息日。可做10-15分钟轻柔瑜伽或泡沫轴放松，保证睡眠质量。",
         "intensity": 0},
        {"day": 4, "type": "Easy", "title": "有氧慢跑", "distance_km": easy2,
         "pace_target": "6:00-6:30", "hr_zone": "Zone 2", "duration_min": easy2 * 6,
         "description": f"热身跑2km，以能聊天的轻松配速跑{easy2}km，专注跑姿和呼吸节奏，冷身拉伸。",
         "intensity": 2},
        {"day": 5, "type": "Interval", "title": "间歇速度训练", "distance_km": round(easy1 * 0.8),
         "pace_target": "4:30-5:00", "hr_zone": "Zone 4-5", "duration_min": round(easy1 * 0.8) * 6,
         "description": "热身跑2km，主课：6×800m间歇跑，每组间歇400m慢跑恢复，目标心率85-90%最大心率，冷身跑2km+拉伸。",
         "intensity": 5},
        {"day": 6, "type": "Long Run", "title": "长距离跑", "distance_km": long_run,
         "pace_target": "6:00-7:00", "hr_zone": "Zone 2", "duration_min": long_run * 6,
         "description": f"热身跑2km，全程保持轻松配速跑完{long_run}km，每5km补水一次，后段若体力允许可稍微提速，冷身拉伸15分钟。",
         "intensity": 3},
        {"day": 7, "type": "Recovery", "title": "恢复慢跑", "distance_km": round(easy1 * 0.7),
         "pace_target": "6:30-7:00", "hr_zone": "Zone 1-2", "duration_min": round(easy1 * 0.7) * 7,
         "description": "极轻松配速的恢复跑，心率不超过最大值的70%，以放松为主。完成后做全身拉伸和泡沫轴放松。",
         "intensity": 1},
    ]
    return {
        "plan_summary": f"基于你过去两周的训练量（{total_km_14d:.0f}km）制定的7天均衡训练计划，遵循80/20原则。",
        "weekly_km": total,
        "days": days,
    }


@router.post("/training-plan")
async def generate_training_plan(req: TrainingPlanRequest):
    """
    Generates a personalized 7-day training plan using Gemini AI.
    Uses VDOT, profile, goals, recent activities, and fitness state.
    Saves to Firestore for history.
    """
    loop = asyncio.get_event_loop()

    # ─ Fetch latest coach analysis to align plan with existing recommendations ─
    def _fetch_latest_coach_analysis(uid: str):
        doc = db.collection("users").document(uid).collection("coach").document("latest_analysis").get()
        return doc.to_dict() if doc.exists else None

    profile, goal_data, activities, stats, coach_analysis = await asyncio.gather(
        loop.run_in_executor(None, _fetch_profile, req.uid),
        loop.run_in_executor(None, _fetch_goal, req.uid),
        loop.run_in_executor(None, _fetch_recent_14d, req.uid),
        loop.run_in_executor(None, _fetch_leaderboard, req.uid),
        loop.run_in_executor(None, _fetch_latest_coach_analysis, req.uid),
    )

    if not profile:
        return {"error": "User profile not found. Please fill in your profile first."}

    # Build context
    vdot = profile.get("vdot") or None
    # Compute age from date_of_birth, fallback to legacy 'age' field
    _dob2 = profile.get("date_of_birth", "")
    if _dob2:
        try:
            from datetime import date as _d2
            _born2 = _d2.fromisoformat(_dob2)
            _today2 = _d2.today()
            age = _today2.year - _born2.year - ((_today2.month, _today2.day) < (_born2.month, _born2.day))
        except (ValueError, TypeError):
            age = profile.get("age", 30)
    else:
        age = profile.get("age", 30)
    gender = profile.get("gender", "other")
    years_running = profile.get("years_running", 0) or 0
    training_goal = profile.get("training_goal", "fitness")
    fm_pb_sec = profile.get("marathon_pb_sec", 0) or 0
    half_pb_sec = profile.get("half_pb_sec", 0) or 0
    max_hr = profile.get("max_heart_rate", 190)
    rest_hr = profile.get("resting_heart_rate", 60)

    # Activity summary
    total_km_14d = sum(a.get("distance_km", 0) for a in activities)
    run_count_14d = len(activities)
    recent_summary = []
    for a in activities[:7]:
        recent_summary.append(
            f"{a.get('start_date_local','')[:10]} "
            f"{a.get('distance_km',0):.1f}km "
            f"@{a.get('avg_pace','?')}/km "
            f"HR:{a.get('avg_heart_rate',0)}"
        )

    goal_str = "No specific target."
    if goal_data:
        goal_str = (
            f"Target {goal_data.get('target_distance',0)} km/"
            f"{goal_data.get('period','monthly')}, "
            f"pace goal: {goal_data.get('target_pace','N/A')}."
        )

    def _fmt_pb(sec):
        if not sec: return "N/A"
        h, r = divmod(sec, 3600)
        m = r // 60
        return f"{h}:{m:02d}"

    # ── Race & goal analysis — PRIMARY plan drivers ───────────────────────────
    from datetime import date as _date_cls
    upcoming_races = profile.get("upcoming_races", [])

    # Find nearest upcoming race
    nearest_race = None
    nearest_days = 9999
    for r in upcoming_races:
        rdate = r.get("date", "")
        if rdate:
            try:
                days = (_date_cls.fromisoformat(rdate) - _date_cls.today()).days
                if 0 < days < nearest_days:
                    nearest_days = days
                    nearest_race = r
            except ValueError:
                pass

    # Determine training phase from nearest race
    race_phase_block = ""
    if nearest_race:
        rtype = nearest_race.get("type", "")
        rname = nearest_race.get("name", rtype)
        rtarget = nearest_race.get("target_time", "")

        race_cn = {
            "10k": "10K", "half_marathon": "半程马拉松", "full_marathon": "全程马拉松",
            "gobi": "戈壁挑战赛（连续3天120K）", "trail_50k": "越野50K",
            "trail_100k": "越野100K", "trail_100m": "越野100英里",
        }.get(rtype, rtype)

        if nearest_days <= 7:
            phase = "赛前减量期"
            phase_rules = (
                "⚠️ 赛前最后1周！跑量减至平时40%，完全避免高强度训练。"
                "重点：轻松跑维持感觉、充分休息、赛前2天完全休息或超短慢跑。"
                "7天内【必须】安排至少3个休息日，最多1次配速验证跑（≤5km）。"
            )
        elif nearest_days <= 21:
            phase = "赛前调整期"
            phase_rules = (
                f"赛前{nearest_days}天，进入减量调整期。跑量减至峰值60%。"
                "保留1次短距离目标配速验证跑（≤8km），其余以轻松跑和休息为主。"
                "7天内【必须】安排2个休息日，禁止大量间歇或长距离拉练。"
            )
        elif nearest_days <= 42:
            phase = "赛前冲刺期"
            phase_rules = (
                f"距{rname}还有{nearest_days}天，最后高质量训练窗口！"
                "需要1次比赛配速的中长距离（15-25km），1次间歇/节奏跑。"
                f"如目标成绩{rtarget}，配速训练需贴近目标配速。"
                "7天内安排1-2个休息日，确保高质量恢复。"
            )
        elif nearest_days <= 84:
            phase = "专项训练期"
            phase_rules = (
                f"距{rname}还有{nearest_days}天，专项能力提升阶段。"
                "每周需要：1次长距离（按比赛距离60-80%），1次节奏跑，1次间歇。"
                f"若全马/超马，长距离跑优先，配速逐步向目标{rtarget or '成绩'}靠近。"
            )
        else:
            phase = "基础储备期"
            phase_rules = (
                f"距{rname}还有{nearest_days}天，以打基础为主。"
                "稳步提升周跑量，80%轻松有氧打底，每周1次长距离慢跑。"
                "不需要高强度专项训练，重点是积累有氧能力。"
            )

        race_phase_block = (
            f"\n\n{'='*50}\n"
            f"⚡ 核心训练依据 — 比赛备赛\n"
            f"{'='*50}\n"
            f"最近比赛：{rname}（{race_cn}）\n"
            f"比赛日期：{nearest_race.get('date', '')}（还有 {nearest_days} 天）\n"
            f"目标成绩：{rtarget or '未设定'}\n"
            f"当前阶段：【{phase}】\n"
            f"本周训练要求：{phase_rules}\n"
            f"{'='*50}\n"
            f"⚠️ 此计划必须完全围绕上述比赛阶段来制定，这是最高优先级！\n"
        )

    # Training goal context
    goal_cn_map = {
        "fitness": "健康健身（有氧为主，养成习惯）",
        "5k": "5K突破（速度训练为核心，800m/1km间歇）",
        "10k": "10K提速（节奏跑+间歇，提升乳酸阈）",
        "half": "半马训练（长距离拉练+配速跑）",
        "full": "全马备赛（高周跑量+多次30km+长距离）",
        "ultra": "超马挑战（极高跑量+背靠背长距离+越野适应）",
    }
    goal_cn = goal_cn_map.get(training_goal, training_goal)

    # All upcoming races list
    all_races_str = ""
    for r in upcoming_races:
        rdate = r.get("date", "")
        if rdate:
            try:
                days = (_date_cls.fromisoformat(rdate) - _date_cls.today()).days
                if days > 0:
                    all_races_str += (
                        f"\n  · {r.get('name', r.get('type',''))}（{rdate}，还有{days}天）"
                        f" 目标：{r.get('target_time','未设')}"
                    )
            except ValueError:
                pass

    # Build coach analysis context to align the plan
    coach_context = ""
    if coach_analysis:
        tips = coach_analysis.get("actionable_tips", [])
        tips_str = "\n".join(f"  · {t}" for t in tips) if tips else "  （暂无）"
        coach_context = (
            f"\n【⚠️ 必须对齐：AI教练最新分析建议（第三优先级，计划必须与此一致）】\n"
            f"  教练总结：{coach_analysis.get('summary', '')}\n"
            f"  当前状态：{coach_analysis.get('status', '')}\n"
            f"  行动建议（必须在7天计划中体现这些）：\n{tips_str}\n"
            f"  ⚠️ 7天计划的每天训练安排必须与上述建议保持一致，不能矛盾！\n"
        )

    prompt = (
        "你是一位专业的中文跑步教练，请为跑者制定一份个性化的7天训练计划。\n"
        "⚠️ 训练计划的制定优先级：① 比赛备赛阶段要求 > ② 训练目标 > ③ AI教练分析建议\n"
        "回复必须是纯 JSON，不含 markdown 标记。\n"
        f"{race_phase_block}\n"
        f"【训练目标（第二优先级）】\n"
        f"  {goal_cn}\n"
        f"  里程目标：{goal_str}\n\n"
        f"【全部赛事计划】{all_races_str or ' 无'}\n"
        f"{coach_context}\n"
        f"【跑者档案（用于校准强度）】\n"
        f"- 年龄：{age}，性别：{gender}，跑龄：{years_running}年\n"
        f"- VDOT：{vdot or '未知'}，最大心率：{max_hr}，静息心率：{rest_hr}\n"
        f"- 全马PB：{_fmt_pb(fm_pb_sec)}，半马PB：{_fmt_pb(half_pb_sec)}\n\n"
        f"【近14天体能数据（用于确认当前状态）】\n"
        f"{run_count_14d} 次跑步，共 {total_km_14d:.1f}km\n"
        f"近期跑步：{' | '.join(recent_summary) or '无近期数据'}\n"
        f"本月：{stats.get('total_distance_km',0)}km，"
        f"配速 {stats.get('avg_pace','?')}/km，"
        f"均心率 {stats.get('avg_heart_rate',0)}bpm\n\n"
        "请从明天开始生成7天训练计划，所有文本使用中文。\n"
        "返回 JSON 格式如下：\n"
        '{\n'
        '  "plan_summary": "<1-2句话，先说明当前备赛阶段/训练目标，再说本周训练重点>",\n'
        '  "weekly_km": <总公里数>,\n'
        '  "days": [\n'
        '    {\n'
        '      "day": 1,\n'
        '      "type": "<Easy|Tempo|Interval|Long Run|Recovery|Rest|Cross Training>",\n'
        '      "title": "<中文训练标题，要体现训练目的，如：赛前配速验证跑>",\n'
        '      "distance_km": <公里数，休息日为0>,\n'
        '      "pace_target": "<如 5:30-6:00，休息日为null>",\n'
        '      "hr_zone": "<如 Zone 2，休息日为null>",\n'
        '      "duration_min": <预估分钟数>,\n'
        '      "description": "<详细中文描述，必须包含：热身方式+主课内容（含具体配速/心率）+冷身方式，以及为什么安排这个训练（联系比赛或目标）>",\n'
        '      "intensity": <1-5强度>\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "核心规则（按优先级）：\n"
        "1. 【最高优先级】若有备赛阶段要求，该阶段的训练规则必须严格执行，不可违背\n"
        "2. 每天描述中必须说明此训练如何服务于比赛目标或训练目标\n"
        "3. 安排 1-2 个休息日，遵循 80/20 原则\n"
        "4. 长距离跑安排在周末\n"
        "5. description 字段必须有详细执行步骤，不能简短！\n"
        "6. VDOT 未知时，根据近期配速数据推算心率区间和配速目标\n"
    )

    if not _api_key:
        plan = _build_training_plan_fallback(total_km_14d, training_goal, upcoming_races)
        return {"plan": plan, "generated_at": __import__("datetime").date.today().isoformat(), "source": "fallback"}

    try:
        response = await loop.run_in_executor(
            None,
            lambda: _gemini_generate(prompt, temperature=0.5, max_tokens=4000)
        )
        print(f"[training-plan] Used model: {response['model']}@{response['api_version']}")
        text = response["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        plan = json.loads(text)

        # Save to Firestore
        from datetime import date
        today = date.today().isoformat()
        try:
            plan_ref = (db.collection("users").document(req.uid)
                          .collection("training_plans").document(today))
            plan_ref.set({
                **plan,
                "generated_at": today,
                "vdot_used": vdot,
                "training_goal": training_goal,
            }, merge=True)
        except Exception as e:
            print(f"[training-plan] Failed to save: {e}")

        return {"plan": plan, "generated_at": today}

    except json.JSONDecodeError as e:
        print(f"Training plan JSON parse error: {e}")
        plan = _build_training_plan_fallback(total_km_14d, training_goal, upcoming_races)
        return {"plan": plan, "generated_at": __import__("datetime").date.today().isoformat(), "source": "fallback"}
    except Exception as e:
        print(f"Training plan generation failed: {e}")
        plan = _build_training_plan_fallback(total_km_14d, training_goal, upcoming_races)
        return {"plan": plan, "generated_at": __import__("datetime").date.today().isoformat(), "source": "fallback", "_error": str(e)}

