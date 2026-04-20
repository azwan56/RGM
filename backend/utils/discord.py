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

def _generate_coach_tip(act_doc: dict, user_data: dict, context: dict) -> str:
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

        prompt = (
            "你是一位专业的中文马拉松教练，请根据以下跑步数据给出深度教练分析。\n\n"
            + "\n".join(context_lines)
            + "\n\n要求（重要）：\n"
            "1. 用4-5句话深度分析，分别评估：配速质量、心率效率、本次训练价值\n"
            "2. 结合VDOT和体能状态数据（如有）给出针对性点评\n"
            "3. 给出1-2个具体的后续训练建议\n"
            "4. 语言专业但热情，有温度，不要机械罗列数据\n"
            "5. 不要用markdown格式，不要用JSON，只输出纯文本\n"
            "6. 不要超过120字"
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
    vdot     = act_doc.get("vdot")

    monthly_km = context.get("monthly_km", 0)
    ctl = context.get("ctl")
    atl = context.get("atl")
    tsb = context.get("tsb")

    # Colour based on distance
    if dist >= 21:
        colour = 0xFC4C02   # Strava orange — long run
    elif dist >= 10:
        colour = 0x3B82F6   # Blue — medium run
    else:
        colour = 0x22C55E   # Green — short run

    # ── Primary stats row (always shown) ─────────────────────────────────────
    fields = [
        {"name": "🏁 距离",  "value": f"**{dist} km**",  "inline": True},
        {"name": "⚡ 配速",  "value": f"**{pace}/km**",  "inline": True},
        {"name": "⏱ 时长",  "value": f"**{duration}**", "inline": True},
    ]

    # ── Secondary stats row ───────────────────────────────────────────────────
    secondary = []
    if hr:
        secondary.append({"name": "❤️ 心率", "value": f"**{hr} bpm**", "inline": True})
    if vdot and float(vdot) > 20:
        secondary.append({"name": "📊 VDOT", "value": f"**{round(float(vdot),1)}**", "inline": True})
    if elev and elev > 5:
        secondary.append({"name": "⛰ 爬升", "value": f"**{elev} m**", "inline": True})
    if secondary:
        fields += secondary

    # ── Monthly mileage ───────────────────────────────────────────────────────
    if monthly_km:
        month_label = date_str[:7] if date_str else datetime.now().strftime("%Y-%m")
        fields.append({
            "name":   f"📅 {month_label} 月累计",
            "value":  f"**{monthly_km} km**",
            "inline": True
        })

    # ── Fitness / form state ──────────────────────────────────────────────────
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

    # ── AI coach tip ──────────────────────────────────────────────────────────
    if coach_tip:
        fields.append({
            "name":   "🤖 AI 教练点评",
            "value":  coach_tip,
            "inline": False
        })

    # Activity link
    activity_id = act_doc.get("activity_id")
    strava_link = f"https://www.strava.com/activities/{activity_id}" if activity_id else ""

    description = f"**{run_name}**  ·  📅 {date_str}"
    if strava_link:
        description += f"\n[查看 Strava 详情]({strava_link})"

    embed = {
        "title":       f"🏃 {runner_name} 完成了一次跑步！",
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

def send_activity_discord_notification(act_doc: dict, user_data: dict, uid: str = "") -> bool:
    """
    Sends a Discord embed notification for a completed run.
    Reads webhook URL from user_data["discord_webhook_url"] (set in profile).
    If uid is provided, fetches rich runner context (VDOT, fitness state, monthly volume).
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


# ── WeCom (企业微信) Notification — reserved for future implementation ─────────

def send_activity_wecom_notification(act_doc: dict, user_data: dict, uid: str = "") -> bool:
    """
    Sends a WeCom (企业微信) group robot notification for a completed run.
    Reads the webhook URL from user_data["wecom_webhook_url"] (set in profile).
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
        fitness    = _get_fitness_state(uid, user_data) if uid else {}
        context = {
            "monthly_km": monthly_km,
            **fitness,
        }

        # Reuse the identical AI coach engine
        coach_tip = _generate_coach_tip(act_doc, user_data, context)

        # ── Build Markdown ──
        runner_name = (
            user_data.get("display_name") or
            user_data.get("strava_name") or
            user_data.get("email", "").split("@")[0] or
            "跑者"
        )
        run_name = act_doc.get("name", "跑步")
        date_short = date_str[:10]
        
        dist     = act_doc.get("distance_km", 0)
        pace     = act_doc.get("avg_pace", "—")
        duration = act_doc.get("duration_str", "—")
        hr       = act_doc.get("avg_heart_rate", 0)
        elev     = act_doc.get("total_elevation_gain", 0)
        vdot     = act_doc.get("vdot")

        ctl = context.get("ctl")
        atl = context.get("atl")
        tsb = context.get("tsb")

        # Color coding in markdown via <font color="warning|info|comment">
        # Distance gets info (green-ish in wecom), title gets warning (red/orange)
        md = f"🏃 **<font color=\\"warning\\">{runner_name}</font> 完成了一次跑步！**\n"
        md += f"> **{run_name}** · <font color=\\"comment\\">{date_short}</font>\n\n"
        
        md += f"🏁 **距离**: <font color=\\"info\\">{dist} km</font>\n"
        md += f"⚡ **配速**: <font color=\\"info\\">{pace}/km</font>  |  ⏱ **时长**: {duration}\n"
        
        if hr:
            md += f"❤️ **心率**: {hr} bpm"
        if elev and elev > 5:
            md += f"  |  ⛰ **爬升**: {elev}m"
        md += "\n"

        if monthly_km:
            month_label = date_str[:7] if date_str else datetime.now().strftime("%Y-%m")
            md += f"📅 **{month_label} 月累计**: <font color=\\"info\\">{monthly_km} km</font>\n"

        if ctl is not None and atl is not None and tsb is not None:
            if tsb > 5:
                form_str = f"<font color=\\"info\\">状态良好 (+{tsb})</font>"
            elif tsb < -15:
                form_str = f"<font color=\\"warning\\">疲劳蓄积 ({tsb})</font>"
            elif tsb < -5:
                form_str = f"<font color=\\"warning\\">略感疲劳 ({tsb})</font>"
            else:
                form_str = f"<font color=\\"comment\\">状态平衡 ({tsb})</font>"

            md += f"💪 **体能/状态**: CTL **{ctl}** · ATL **{atl}** · {form_str}\n"

        if vdot and float(vdot) > 20:
            md += f"📊 **VDOT 指数**: **{round(float(vdot),1)}**\n"

        if coach_tip:
            # WeCom blockquotes look nicely formatted for AI tips
            md += f"\n🤖 **AI 教练点评**:\n<font color=\\"comment\\">{coach_tip}</font>\n"

        activity_id = act_doc.get("activity_id")
        if activity_id:
            md += f"\n[🔗 查看 Strava 详情](https://www.strava.com/activities/{activity_id})"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": md
            }
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
