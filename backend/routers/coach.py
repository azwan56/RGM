from fastapi import APIRouter
from pydantic import BaseModel
from firebase_config import db
import os
import json
import asyncio

router = APIRouter()

_api_key = os.getenv("GEMINI_API_KEY")
_gemini_base_url = os.getenv("GEMINI_BASE_URL")  # Optional CDN proxy, e.g. https://your-proxy.example.com
_coach_client = None  # Lazy init

def _get_client():
    """Lazily creates the Gemini client on first call.
    If GEMINI_BASE_URL is set, routes requests through that proxy endpoint.
    """
    global _coach_client
    if _coach_client is None and _api_key:
        from google import genai
        from google.genai import types
        if _gemini_base_url:
            _coach_client = genai.Client(
                api_key=_api_key,
                http_options=types.HttpOptions(base_url=_gemini_base_url)
            )
        else:
            _coach_client = genai.Client(api_key=_api_key)
    return _coach_client

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

    runs_str = _build_runs_str(activities)
    completion_pct = stats.get('goal_completion_percentage', 0)

    prompt = (
        "你是一位热情、专业、善于鼓励的中文跑步教练。"
        "请根据以下跑者信息，给出温暖、正面、具有激励性的个性化训练建议。"
        "回复必须是纯 JSON，不含 markdown 标记。\n\n"
        f"【跑者档案】\n"
        f"- 称呼：{runner_name}\n"
        f"- 年龄：{age or '未知'}\n"
        f"- 跑龄：{years_running} 年\n"
        f"- 训练目标：{goal_cn}\n"
        f"- 当前目标：{goal_str}\n\n"
        f"{race_section}"
        f"{race_coaching_instructions}"
        f"【本期训练数据（{stats.get('period', 'monthly')}）】\n"
        f"- 总里程：{stats.get('total_distance_km', 0)} 公里\n"
        f"- 平均配速：{stats.get('avg_pace', '?')}/km\n"
        f"- 平均心率：{stats.get('avg_heart_rate', 0)} bpm\n"
        f"- 跑步次数：{stats.get('run_count', 0)} 次\n"
        f"- 目标完成度：{completion_pct}%\n\n"
        f"【近期跑步记录】\n{runs_str}\n\n"
        "【输出要求】\n"
        "全部使用中文。语气要温暖、正面、充满鼓励。\n"
        "根据跑者的实际数据给出有针对性的分析，不要泛泛而谈。\n"
        "先肯定跑者的付出和进步，再给出改进建议。\n"
    )

    # Add race-specific output instructions if there's an upcoming race
    if nearest_race and nearest_days <= 120:
        prompt += (
            "⚠️ 重点：跑者有临近比赛，你的建议必须围绕备赛展开：\n"
            "  - summary 中要提到比赛备赛状态和当前训练阶段\n"
            "  - actionable_tips 中至少2条要针对比赛备赛\n"
            "  - 如果距比赛≤14天，重点提醒减量和赛前准备\n"
            "  - 如果有目标成绩，分析当前状态与目标的差距\n\n"
        )

    prompt += (
        "返回 JSON 格式如下：\n"
        '{\n'
        '  "status": "<状态标签，如：备赛冲刺 🔥|稳步提升 📈|状态出色 💪|注意恢复 😴|继续加油 🏃>",\n'
        '  "summary": "<2-3 句话的训练总结，如有比赛则重点评估备赛状态>",\n'
        '  "encouragement": "<一句短小有力的鼓励金句>",\n'
        '  "actionable_tips": ["建议1", "建议2", "建议3", "建议4"]\n'
        '}\n\n'
        "建议要具体、可操作，结合跑者的配速/心率/跑量数据给出。如有比赛需包含本周训练重点。"
    )

    if not _api_key:
        return {"feedback": {
            "status": "离线模式 🔌",
            "summary": "AI 教练暂时离线，但你的努力不会被辜负！",
            "encouragement": "坚持训练，胜利属于每一个不放弃的人！",
            "actionable_tips": ["轻松跑保持能聊天的配速", "坚持比速度更重要", "休息也是训练的一部分"]
        }}

    try:
        from google.genai import types
        client = _get_client()
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.6,
            max_output_tokens=800,
        )
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config,
            )
        )
        text = response.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return {"feedback": json.loads(text)}

    except json.JSONDecodeError as e:
        print(f"Coach JSON parse error: {e}")
        return {"feedback": _FALLBACK}
    except Exception as e:
        print(f"Coach generation failed: {e}")
        return {"feedback": {
            **_FALLBACK,
            "summary": f"{runner_name}，你已经跑了 {stats.get('total_distance_km', 0)} 公里，非常棒！继续保持！"
        }}


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


@router.post("/training-plan")
async def generate_training_plan(req: TrainingPlanRequest):
    """
    Generates a personalized 7-day training plan using Gemini AI.
    Uses VDOT, profile, goals, recent activities, and fitness state.
    Saves to Firestore for history.
    """
    loop = asyncio.get_event_loop()

    profile, goal_data, activities, stats = await asyncio.gather(
        loop.run_in_executor(None, _fetch_profile, req.uid),
        loop.run_in_executor(None, _fetch_goal, req.uid),
        loop.run_in_executor(None, _fetch_recent_14d, req.uid),
        loop.run_in_executor(None, _fetch_leaderboard, req.uid),
    )

    if not profile:
        return {"error": "User profile not found. Please fill in your profile first."}

    # Build context
    vdot = profile.get("vdot") or None
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

    prompt = (
        "You are a professional running coach creating a 7-day training plan. "
        "Reply with ONLY a valid JSON object, no markdown fences.\n\n"
        f"ATHLETE PROFILE:\n"
        f"- Age: {age}, Gender: {gender}, Running years: {years_running}\n"
        f"- VDOT: {vdot or 'Unknown'}\n"
        f"- Marathon PB: {_fmt_pb(fm_pb_sec)}, Half PB: {_fmt_pb(half_pb_sec)}\n"
        f"- Training goal: {training_goal}\n"
        f"- Max HR: {max_hr}, Rest HR: {rest_hr}\n"
        f"- Goal: {goal_str}\n\n"
        f"RECENT 14 DAYS: {run_count_14d} runs, {total_km_14d:.1f}km total\n"
        f"Last runs: {' | '.join(recent_summary) or 'No recent data'}\n\n"
        f"Current monthly stats: {stats.get('total_distance_km',0)}km, "
        f"pace {stats.get('avg_pace','?')}/km, "
        f"HR {stats.get('avg_heart_rate',0)}bpm\n\n"
        "Generate a 7-day plan starting from tomorrow. "
        "Use CHINESE for all text fields. "
        "Return JSON with exactly this structure:\n"
        '{\n'
        '  "plan_summary": "<1-2 sentence overview in Chinese>",\n'
        '  "weekly_km": <total km number>,\n'
        '  "days": [\n'
        '    {\n'
        '      "day": 1,\n'
        '      "type": "<Easy|Tempo|Interval|Long Run|Recovery|Rest|Cross Training>",\n'
        '      "title": "<Chinese title, e.g. 轻松跑>",\n'
        '      "distance_km": <number or 0 for rest>,\n'
        '      "pace_target": "<e.g. 5:30-6:00 or null for rest>",\n'
        '      "hr_zone": "<e.g. Zone 2 or null>",\n'
        '      "duration_min": <estimated minutes>,\n'
        '      "description": "<Chinese description of workout>",\n'
        '      "intensity": <1-5 scale>\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "RULES:\n"
        "- Include 1-2 rest days\n"
        "- Follow 80/20 rule (80% easy, 20% hard)\n"
        "- Long run should be on weekend\n"
        "- Match intensity to athlete's current fitness level\n"
        "- If VDOT is unknown, estimate from recent pace data"
    )

    if not _api_key:
        return {"error": "AI Coach offline — Gemini API key not configured."}

    try:
        from google.genai import types
        client = _get_client()
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.5,
            max_output_tokens=2048,
        )
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config,
            )
        )
        text = response.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
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
        return {"error": "AI returned invalid format. Please try again."}
    except Exception as e:
        print(f"Training plan generation failed: {e}")
        return {"error": f"Generation failed: {str(e)}"}

