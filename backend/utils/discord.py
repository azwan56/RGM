"""
Discord Notification Utility
Sends a rich embed card to a Discord channel whenever a new run is detected.

Usage:
    from utils.discord import send_activity_discord_notification
    send_activity_discord_notification(act_doc, user_data)

Webhook URL stored in user Firestore profile: user_data["discord_webhook_url"]
"""

import os
import requests
from datetime import datetime, date


# ── Helpers: pull extra context from Firestore ────────────────────────────────

def _get_monthly_km(uid: str, current_date_str: str) -> float:
    """Sum distance for the current calendar month."""
    try:
        from firebase_config import db
        month_prefix = current_date_str[:7]  # "YYYY-MM"
        docs = (
            db.collection("users").document(uid)
            .collection("activities")
            .order_by("start_date_local", direction="DESCENDING")
            .limit(200)
            .stream()
        )
        total = 0.0
        for d in docs:
            act = d.to_dict()
            if act.get("start_date_local", "")[:7] == month_prefix:
                total += act.get("distance_km", 0)
            elif act.get("start_date_local", "")[:7] < month_prefix:
                break  # sorted descending, safe to stop
        return round(total, 1)
    except Exception:
        return 0.0


def _get_fitness_state(uid: str, user_data: dict) -> dict:
    """Get today's CTL/ATL/TSB from sports science module."""
    try:
        from firebase_config import db
        from utils.sports_science import compute_fitness_fatigue_timeseries

        max_hr  = user_data.get("max_heart_rate", 190)
        rest_hr = user_data.get("resting_heart_rate", 60)

        docs = (
            db.collection("users").document(uid)
            .collection("activities")
            .order_by("start_date_local", direction="DESCENDING")
            .limit(90)
            .stream()
        )
        activities = [d.to_dict() for d in docs]
        activities.reverse()

        series = compute_fitness_fatigue_timeseries(activities, max_hr, rest_hr, days=3)
        if series:
            latest = series[-1]
            return {
                "ctl": round(latest.get("ctl", 0), 1),
                "atl": round(latest.get("atl", 0), 1),
                "tsb": round(latest.get("tsb", 0), 1),
            }
    except Exception:
        pass
    return {}


# ── Gemini coach tip ──────────────────────────────────────────────────────────

def _generate_coach_tip(act_doc: dict, user_data: dict, context: dict, is_wecom: bool = False) -> str:
    """
    Generates a detailed 4-5 sentence AI coach analysis.
    Context includes VDOT, CTL/ATL/TSB, monthly km, user goals.
    """
    try:
        from routers.coach import _gemini_generate

        name     = (user_data.get("display_name") or user_data.get("strava_name") or "跑者").split()[0]
        dist     = act_doc.get("distance_km", 0)
        pace     = act_doc.get("avg_pace", "—")
        hr       = act_doc.get("avg_heart_rate", 0)
        elev     = act_doc.get("total_elevation_gain", 0)
        duration = act_doc.get("duration_str", "—")
        cadence  = act_doc.get("avg_cadence", 0)
        vdot     = act_doc.get("vdot")
        goal     = user_data.get("training_goal", "")
        fm_pb    = user_data.get("marathon_pb_sec", 0)

        monthly_km = context.get("monthly_km", 0)
        ctl = context.get("ctl", 0)
        atl = context.get("atl", 0)
        tsb = context.get("tsb", 0)

        # Format marathon PB
        pb_str = ""
        if fm_pb:
            h, r = divmod(int(fm_pb), 3600)
            pb_str = f"全马PB {h}:{r//60:02d}"

        # Build rich context lines
        context_lines = [
            f"跑者：{name}，训练目标：{goal or '未设定'}，{pb_str or '无PB记录'}",
            f"本次跑步：{dist}km，配速 {pace}/km，时长 {duration}",
        ]
        if hr:
            context_lines.append(f"心率：{hr}bpm，步频：{cadence}spm，爬升：{elev}m")
        if vdot and float(vdot) > 20:
            context_lines.append(f"当前VDOT值：{round(float(vdot),1)}（跑力评估指数，越高越强）")
        if monthly_km:
            context_lines.append(f"本月累计跑量：{monthly_km}km")
        if ctl or atl:
            state = "良好" if tsb > 5 else ("疲劳蓄积" if tsb < -10 else "平衡")
            context_lines.append(f"体能状态：CTL体能={ctl}，ATL疲劳={atl}，TSB状态值={tsb}（{state}）")

        reqs = (
            "要求（重要）：\n"
            "1. 用4-5句话深度分析，分别评估：配速质量、心率效率、本次训练价值\n"
            "2. 结合VDOT和体能状态数据（如有）给出针对性点评\n"
            "3. 给出1-2个具体的后续训练建议\n"
            "4. 语言专业但热情，有温度，不要机械罗列数据\n"
            "5. 不要用markdown格式，不要用JSON，只输出纯文本\n"
            "6. 不要超过120字"
        )

        if is_wecom:
            reqs = (
                "要求（重要）：\n"
                "1. 用4-5句话深度分析，分别评估：配速质量、心率效率、本次训练价值\n"
                "2. 结合提供的VDOT和体能状态数据进行定性评估，不要在回复中直接引用具体的VDOT、CTL、ATL等数字\n"
                "3. 给出1-2个具体的后续训练建议\n"
                "4. 语言专业但热情，有温度，绝不罗列冷冰冰的数据\n"
                "5. 不要用markdown格式，不要用JSON，只输出纯文本\n"
                "6. 不要超过120字"
            )

        prompt = (
            "你是一位专业的中文马拉松教练，请根据以下跑步数据给出深度教练分析。\n\n"
            + "\n".join(context_lines)
            + f"\n\n{reqs}"
        )

        result = _gemini_generate(prompt, temperature=0.7, response_json=False)
        return result.get("text", "").strip()

    except Exception as e:
        print(f"[discord] Coach tip generation failed: {e}")
        return ""


# ── Embed builder ─────────────────────────────────────────────────────────────

def _build_embed(act_doc: dict, user_data: dict, coach_tip: str, context: dict) -> dict:
    """Builds a refined Discord embed with key stats + fitness state."""
    runner_name = (
        user_data.get("display_name") or
        user_data.get("strava_name") or
        user_data.get("email", "").split("@")[0] or
        "跑者"
    )

    dist     = act_doc.get("distance_km", 0)
    pace     = act_doc.get("avg_pace", "—")
    hr       = act_doc.get("avg_heart_rate", 0)
    elev     = act_doc.get("total_elevation_gain", 0)
    duration = act_doc.get("duration_str", "—")
    run_name = act_doc.get("name", "跑步")
    date_str = act_doc.get("start_date_local", "")[:10]
    act_type = act_doc.get("activity_type", "run")
    strava_type = act_doc.get("strava_type", "Run")

    is_ct = (act_type == "cross_training")

    monthly_km = context.get("monthly_km", 0)
    ctl = context.get("ctl")
    atl = context.get("atl")
    tsb = context.get("tsb")

    # Colour and icon based on type / distance
    if is_ct:
        colour = 0x06B6D4  # Cyan — cross training
        title_icon = "🏋️" if strava_type in ("WeightTraining", "Workout", "Crossfit", "HighIntensityIntervalTraining") else "🧘" if strava_type == "Yoga" else "🏊" if strava_type == "Swim" else "💪"
        title_text = "完成了一次交叉训练！"
    else:
        title_icon = "🏃"
        title_text = "完成了一次跑步！"
        if dist >= 21:
            colour = 0xFC4C02   # Strava orange — long run
        elif dist >= 10:
            colour = 0x3B82F6   # Blue — medium run
        else:
            colour = 0x22C55E   # Green — short run

    # ── Activity link ─────────────────────────────────────────────────────────
    activity_id = act_doc.get("activity_id")
    strava_link = f"https://www.strava.com/activities/{activity_id}" if activity_id else ""

    # ── Description: all basic stats as compact flowing text ──────────────────
    desc_lines = [f"**{run_name}**  ·  📅 {date_str}"]
    if strava_link:
        desc_lines.append(f"[查看 Strava 详情]({strava_link})")
    desc_lines.append("")  # blank separator

    # Row 1: distance · pace · duration (or just duration for CT)
    if is_ct:
        desc_lines.append(f"⏱ **{duration}**")
    else:
        desc_lines.append(f"🏁 **{dist} km**  ·  ⚡ **{pace}/km**  ·  ⏱ **{duration}**")

    # Row 2: HR and/or elevation (optional)
    row2_parts = []
    if hr:
        row2_parts.append(f"❤️ **{hr} bpm**")
    if not is_ct and elev and elev > 5:
        row2_parts.append(f"⛰ **{elev} m**")
    if row2_parts:
        desc_lines.append("  ·  ".join(row2_parts))

    # Row 3: monthly mileage
    if monthly_km and not is_ct:
        month_label = date_str[:7] if date_str else datetime.now().strftime("%Y-%m")
        desc_lines.append(f"📅 {month_label} 月累计跑量：**{monthly_km} km**")

    description = "\n".join(desc_lines)

    # ── Fields: only fitness state + AI coach tip (both full-width) ───────────
    fields = []

    if ctl is not None and atl is not None and tsb is not None:
        if tsb > 5:
            form_icon, form_label = "🟢", f"状态良好 (+{tsb})"
        elif tsb < -15:
            form_icon, form_label = "🔴", f"疲劳蓄积 ({tsb})"
        elif tsb < -5:
            form_icon, form_label = "🟡", f"略感疲劳 ({tsb})"
        else:
            form_icon, form_label = "🔵", f"状态平衡 ({tsb})"

        fields.append({
            "name":  "💪 体能 / 状态",
            "value": f"体能CTL **{ctl}** · 疲劳ATL **{atl}** · {form_icon} {form_label}",
            "inline": False
        })

    if coach_tip:
        fields.append({
            "name":   "🤖 AI 教练点评",
            "value":  coach_tip,
            "inline": False
        })


    embed = {
        "title":       f"{title_icon} {runner_name} {title_text}",
        "description": description,
        "color":       colour,
        "fields":      fields,
        "footer":      {"text": "RGM 跑团管理平台 · 由 Strava 同步"},
        "timestamp":   datetime.utcnow().isoformat() + "Z",
    }

    avatar = user_data.get("strava_profile_url") or user_data.get("photoURL")
    if avatar:
        embed["thumbnail"] = {"url": avatar}

    return embed


# ── Public entry point ────────────────────────────────────────────────────────

def send_activity_discord_notification(act_doc: dict, user_data: dict, uid: str = "", coach_tip: str = "") -> bool:
    """
    Sends a Discord embed notification for a completed run.
    Reads webhook URL from user_data["discord_webhook_url"] (set in profile).
    If uid is provided, fetches rich runner context (VDOT, fitness state, monthly volume).
    If coach_tip is provided, uses it directly instead of generating a new one.
    Returns True on success, False on failure (never raises).
    """
    webhook_url = (user_data.get("discord_webhook_url") or "").strip()
    if not webhook_url:
        print("[discord] No discord_webhook_url in user profile — skipping")
        return False

    try:
        # Determine uid safely
        if not uid:
            uid = user_data.get("uid") or user_data.get("id") or act_doc.get("uid") or ""

        date_str = act_doc.get("start_date_local", "")

        # Gather extra context
        monthly_km = _get_monthly_km(uid, date_str) if uid else 0.0
        fitness    = _get_fitness_state(uid, user_data) if uid else {}

        context = {
            "monthly_km": monthly_km,
            **fitness,
        }

        # Reuse provided coach_tip (from journal), or generate a new one
        if not coach_tip:
            coach_tip = _generate_coach_tip(act_doc, user_data, context)
        embed     = _build_embed(act_doc, user_data, coach_tip, context)

        payload = {
            "embeds":   [embed],
            "username": "RGM 跑团助手",
        }

        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            print(f"[discord] Notification sent for activity {act_doc.get('activity_id')}")
            return True
        else:
            print(f"[discord] Failed to send: {resp.status_code} {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[discord] Notification error: {e}")
        return False


# ── WeCom (企业微信) Notification ─────────────────────────────────────────────

def send_activity_wecom_notification(act_doc: dict, user_data: dict, uid: str = "", coach_tip: str = "", journal_entry: dict = None) -> bool:
    """
    Sends a WeCom (企业微信) group robot notification for a completed run.
    Reads the webhook URL from user_data["wecom_webhook_url"] (set in profile).

    Privacy policy for WeCom (group channel):
    - Always regenerates a WeCom-specific AI tip — never reuses journal tip
      which may contain CTL/ATL/TSB/HR/PB numbers.
    - Only shows basic run stats: distance, pace, duration, elevation,
      weekly/monthly mileage. No biometric or fitness-score data.
    - journal_entry is accepted for API compatibility but only weekly_progress
      (non-biometric) is read from it.
    Returns True on success, False on failure.
    """
    webhook_url = (user_data.get("wecom_webhook_url") or "").strip()
    if not webhook_url:
        print("[wecom] No wecom_webhook_url in user profile — skipping")
        return False

    try:
        if not uid:
            uid = user_data.get("uid") or user_data.get("id") or act_doc.get("uid") or ""

        date_str = act_doc.get("start_date_local", "")

        monthly_km = _get_monthly_km(uid, date_str) if uid else 0.0
        # Fetch fitness for Gemini context only — not shown in message
        fitness = _get_fitness_state(uid, user_data) if uid else {}
        context = {"monthly_km": monthly_km, **fitness}

        # ALWAYS regenerate a WeCom-safe tip — never reuse the journal
        # coach_tip which can contain CTL/ATL/TSB/HR/PB numbers.
        wecom_tip = _generate_coach_tip(act_doc, user_data, context, is_wecom=True)

        if journal_entry is None:
            journal_entry = {}

        # ── Build Markdown ────────────────────────────────────────────────────
        runner_name = (
            user_data.get("display_name") or
            user_data.get("strava_name") or
            user_data.get("email", "").split("@")[0] or
            "跑者"
        )
        run_name   = act_doc.get("name", "跑步")
        date_short = date_str[:10]
        dist       = act_doc.get("distance_km", 0)
        pace       = act_doc.get("avg_pace", "—")
        duration   = act_doc.get("duration_str", "—")
        elev       = act_doc.get("total_elevation_gain", 0)
        act_type   = act_doc.get("activity_type", "run")
        strava_type = act_doc.get("strava_type", "Run")
        is_ct      = (act_type == "cross_training")

        if is_ct:
            title_icon = "🏋️" if strava_type in ("WeightTraining", "Workout", "Crossfit", "HighIntensityIntervalTraining") else "🧘" if strava_type == "Yoga" else "🏊" if strava_type == "Swim" else "💪"
            title_text = "完成了一次交叉训练！"
            md  = f"{title_icon} **{runner_name} {title_text}**\n"
            md += f"> **{run_name}** · {date_short}\n\n"
            md += f"⏱ 时长：**{duration}**\n"
        else:
            md  = f"🏃 **{runner_name} 完成了一次跑步！**\n"
            md += f"> **{run_name}** · {date_short}\n\n"
            md += f"🏁 距离：**{dist} km**\n"
            md += f"⚡ 配速：**{pace}/km**  |  ⏱ 时长：{duration}\n"
            if elev and elev > 5:
                md += f"🏔 爬升：{elev} m\n"

        # Weekly/monthly mileage (non-biometric, only for runs)
        if not is_ct:
            wp = journal_entry.get("weekly_progress", {})
            if wp and wp.get("target_km"):
                md += f"📊 本周进度：**{wp['week_km']}km / {wp['target_km']}km** ({wp.get('completion_pct', 0)}%)\n"
            elif monthly_km:
                month_label = date_str[:7] if date_str else datetime.now().strftime("%Y-%m")
                md += f"📅 {month_label} 月累计：**{monthly_km} km**\n"

        # Privacy-safe AI coach comment (no biometric numbers)
        if wecom_tip:
            md += f"\n🤖 **教练点评**：\n{wecom_tip}\n"

        payload = {
            "msgtype": "markdown",
            "markdown": {"content": md},
        }

        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("errcode") == 0:
            print(f"[wecom] Notification sent for activity {act_doc.get('activity_id')}")
            return True
        else:
            print(f"[wecom] Failed to send: {resp.status_code} {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[wecom] Notification error: {e}")
        return False


# ── Rest Day Reminder ─────────────────────────────────────────────────────────

def _generate_rest_day_tip(user_data: dict, rest_date: str, monthly_km: float) -> str:
    """
    Uses Gemini to generate a short, warm motivational message for a runner
    who had no recorded activity the previous day.
    Returns plain text (no markdown/JSON), max ~80 chars.
    """
    try:
        from routers.coach import _gemini_generate

        name  = (user_data.get("display_name") or user_data.get("strava_name") or "跑者").split()[0]
        goal  = user_data.get("training_goal", "")

        context = (
            f"跑者：{name}，训练目标：{goal or '未设定'}\n"
            f"昨天（{rest_date}）没有运动记录\n"
            f"本月累计跑量：{monthly_km}km"
        )

        prompt = (
            f"你是一位温柔、充满活力的跑步教练。以下是跑者情况：\n{context}\n\n"
            f"请用中文写一句温馨鼓励的话（不超过60字），提醒{name}昨天没有运动，"
            f"鼓励他今天重新出发。语气亲切自然，不要提具体数字或专业术语。"
            f"只输出这一句话，不要加任何前缀或解释。"
        )

        result = _gemini_generate(prompt, max_tokens=100, temperature=0.8, response_json=False)
        return result.get("text", "").strip()

    except Exception as e:
        print(f"[discord] Rest day tip generation failed: {e}")
        return ""


def send_rest_day_discord_notification(user_data: dict, rest_date: str, uid: str = "") -> bool:
    """
    Sends a Discord rest-day reminder for a runner with no activity yesterday.
    Does NOT create a journal entry — pure motivational ping.
    Returns True on success, False on failure.
    """
    webhook_url = (user_data.get("discord_webhook_url") or "").strip()
    if not webhook_url:
        return False

    try:
        runner_name = (
            user_data.get("display_name") or
            user_data.get("strava_name") or
            user_data.get("email", "").split("@")[0] or
            "跑者"
        )

        monthly_km = _get_monthly_km(uid, rest_date) if uid else 0.0
        rest_tip   = _generate_rest_day_tip(user_data, rest_date, monthly_km)

        fields = []
        if monthly_km:
            month_label = rest_date[:7]
            fields.append({
                "name":   f"📊 {month_label} 月累计",
                "value":  f"**{monthly_km} km**",
                "inline": False,
            })
        if rest_tip:
            fields.append({
                "name":   "🤖 AI 教练寄语",
                "value":  rest_tip,
                "inline": False,
            })

        embed = {
            "title":       f"☀️ 早安，{runner_name}！昨天没有运动记录",
            "description": f"昨天（{rest_date}）暂无活动  ·  今天是重新出发的好时机 💪",
            "color":       0x8B5CF6,  # Purple — rest day
            "fields":      fields,
            "footer":      {"text": "RGM 跑团管理平台 · AI 教练提醒"},
            "timestamp":   datetime.utcnow().isoformat() + "Z",
        }

        avatar = user_data.get("strava_profile_url") or user_data.get("photoURL")
        if avatar:
            embed["thumbnail"] = {"url": avatar}

        payload = {"embeds": [embed], "username": "RGM 跑团助手"}
        resp = requests.post(webhook_url, json=payload, timeout=10)
        ok = resp.status_code in (200, 204)
        if ok:
            print(f"[discord] Rest-day reminder sent for {runner_name}")
        else:
            print(f"[discord] Rest-day reminder failed: {resp.status_code}")
        return ok

    except Exception as e:
        print(f"[discord] Rest-day reminder error: {e}")
        return False


def send_rest_day_wecom_notification(user_data: dict, rest_date: str, uid: str = "") -> bool:
    """
    Sends a WeCom rest-day reminder for a runner with no activity yesterday.
    Does NOT create a journal entry — pure motivational ping.
    Returns True on success, False on failure.
    """
    webhook_url = (user_data.get("wecom_webhook_url") or "").strip()
    if not webhook_url:
        return False

    try:
        runner_name = (
            user_data.get("display_name") or
            user_data.get("strava_name") or
            user_data.get("email", "").split("@")[0] or
            "跑者"
        )

        monthly_km = _get_monthly_km(uid, rest_date) if uid else 0.0
        rest_tip   = _generate_rest_day_tip(user_data, rest_date, monthly_km)

        md  = f"☀️ **早安，{runner_name}！**\n"
        md += f"> 昨天（{rest_date}）暂无运动记录\n\n"
        if monthly_km:
            month_label = rest_date[:7]
            md += f"📊 {month_label} 月累计：**{monthly_km} km**\n"
        if rest_tip:
            md += f"\n🤖 **教练寄语**：{rest_tip}\n"
        md += "\n💪 今天是重新出发的好时机，加油！"

        payload = {
            "msgtype": "markdown",
            "markdown": {"content": md},
        }

        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("errcode") == 0:
            print(f"[wecom] Rest-day reminder sent for {runner_name}")
            return True
        else:
            print(f"[wecom] Rest-day reminder failed: {resp.status_code} {resp.text[:100]}")
            return False

    except Exception as e:
        print(f"[wecom] Rest-day reminder error: {e}")
        return False


# ── Weekly Report Notification ──────────────────────────────────────────────────

def send_weekly_report_discord_notification(user_data: dict, uid: str, report: dict) -> bool:
    """
    Sends a Discord embed notification for an automatically generated weekly report.
    """
    webhook_url = (user_data.get("discord_webhook_url") or "").strip()
    if not webhook_url:
        return False

    try:
        runner_name = (
            user_data.get("display_name") or
            user_data.get("strava_name") or
            user_data.get("email", "").split("@")[0] or
            "跑者"
        )
        
        week_num = report.get("week_number", "?")
        score = report.get("weekly_score", 7)
        stats = report.get("week_stats", {})
        
        # Color based on score
        if score >= 8:
            color = 0x22C55E # Green
        elif score >= 6:
            color = 0x3B82F6 # Blue
        else:
            color = 0xEAB308 # Yellow
            
        desc = report.get("summary", "")
        
        fields = []
        
        # Stats row
        km = stats.get("total_km", 0)
        runs = stats.get("total_runs", 0)
        elev = stats.get("total_elevation", 0)
        fields.append({
            "name": "📊 本周数据",
            "value": f"**{km}km** · {runs}次 · 爬升{elev}m",
            "inline": False
        })
        
        # Achievements & Concerns
        achievements = report.get("achievements", [])
        if achievements:
            fields.append({
                "name": "✅ 本周亮点",
                "value": "\n".join([f"- {a}" for a in achievements]),
                "inline": False
            })
            
        concerns = report.get("concerns", [])
        if concerns:
            fields.append({
                "name": "⚠️ 需要注意",
                "value": "\n".join([f"- {c}" for c in concerns]),
                "inline": False
            })
            
        # Suggestions (if new format)
        suggestions = report.get("constructive_suggestions", [])
        if suggestions:
            sugg_text = "\n".join([f"- **{s.get('area','')}**: {s.get('suggestion','')} ({s.get('rationale','')})" for s in suggestions])
            if len(sugg_text) > 1024:
                sugg_text = sugg_text[:1020] + "..."
            fields.append({
                "name": "💡 建设性建议",
                "value": sugg_text,
                "inline": False
            })
            
        # Next week plan
        plan = report.get("next_week_plan", {})
        if plan:
            focus = plan.get("focus", "")
            target_km = plan.get("target_km", "")
            adj = plan.get("adjustments", "")
            plan_str = f"**重点**: {focus}\n**目标跑量**: {target_km}"
            if adj:
                plan_str += f"\n**调整**: {adj}"
            fields.append({
                "name": "📅 下周计划",
                "value": plan_str,
                "inline": False
            })
            
        # Goal Progress (if new format)
        goal_prog = report.get("goal_progress", {})
        if goal_prog and goal_prog.get("race_name") and goal_prog.get("race_name") != "无":
            fields.append({
                "name": "🎯 备赛进度",
                "value": f"**{goal_prog.get('race_name')}** (剩{goal_prog.get('days_remaining')}天) - {goal_prog.get('training_phase')}\n{goal_prog.get('readiness_assessment','')}",
                "inline": False
            })

        embed = {
            "title": f"📈 {runner_name} 的第 {week_num} 周训练总结 (评分: {score}/10)",
            "description": desc,
            "color": color,
            "fields": fields,
            "footer": {"text": "RGM 跑团管理平台 · AI 教练周报"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        avatar = user_data.get("strava_profile_url") or user_data.get("photoURL")
        if avatar:
            embed["thumbnail"] = {"url": avatar}

        payload = {"embeds": [embed], "username": "RGM 跑团助手"}
        resp = requests.post(webhook_url, json=payload, timeout=10)
        ok = resp.status_code in (200, 204)
        if ok:
            print(f"[discord] Weekly report sent for {runner_name}")
        else:
            print(f"[discord] Weekly report failed: {resp.status_code}")
        return ok

    except Exception as e:
        print(f"[discord] Weekly report error: {e}")
        return False


def send_weekly_report_wecom_notification(user_data: dict, uid: str, report: dict) -> bool:
    """
    Sends a WeCom markdown notification for an automatically generated weekly report.
    """
    webhook_url = (user_data.get("wecom_webhook_url") or "").strip()
    if not webhook_url:
        return False

    try:
        runner_name = (
            user_data.get("display_name") or
            user_data.get("strava_name") or
            user_data.get("email", "").split("@")[0] or
            "跑者"
        )
        
        week_num = report.get("week_number", "?")
        score = report.get("weekly_score", 7)
        stats = report.get("week_stats", {})
        
        km = stats.get("total_km", 0)
        runs = stats.get("total_runs", 0)
        elev = stats.get("total_elevation", 0)
        
        md = f"📈 **{runner_name} 的第 {week_num} 周训练总结** (评分: {score}/10)\n\n"
        md += f"📊 **本周数据**: **{km}km** · {runs}次 · 爬升{elev}m\n\n"
        md += f"> {report.get('summary', '')}\n\n"
        
        achievements = report.get("achievements", [])
        if achievements:
            md += "**✅ 亮点**:\n"
            for a in achievements:
                md += f"- {a}\n"
            md += "\n"
            
        suggestions = report.get("constructive_suggestions", [])
        if suggestions:
            md += "**💡 建议**:\n"
            for s in suggestions:
                md += f"- **{s.get('area','')}**: {s.get('suggestion','')}\n"
            md += "\n"
            
        plan = report.get("next_week_plan", {})
        if plan:
            md += f"**📅 下周计划**: {plan.get('focus', '')} (目标: {plan.get('target_km', '')})\n"
            
        goal_prog = report.get("goal_progress", {})
        if goal_prog and goal_prog.get("race_name") and goal_prog.get("race_name") != "无":
            md += f"**🎯 备赛**: {goal_prog.get('race_name')} (剩{goal_prog.get('days_remaining')}天) - {goal_prog.get('training_phase')}\n"

        payload = {
            "msgtype": "markdown",
            "markdown": {"content": md},
        }

        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("errcode") == 0:
            print(f"[wecom] Weekly report sent for {runner_name}")
            return True
        else:
            print(f"[wecom] Weekly report failed: {resp.status_code} {resp.text[:100]}")
            return False

    except Exception as e:
        print(f"[wecom] Weekly report error: {e}")
        return False
