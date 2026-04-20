"""
Discord Notification Utility
Sends a rich embed card to a Discord channel whenever a new run is detected.

Usage:
    from utils.discord import send_activity_discord_notification
    send_activity_discord_notification(act_doc, user_data)

Requires env var:
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
"""

import os
import requests
from datetime import datetime


# ── Gemini quick tip ──────────────────────────────────────────────────────────

def _generate_quick_coach_tip(act_doc: dict, user_data: dict) -> str:
    """
    Generates a short 2-sentence AI coach comment on a single run.
    Falls back gracefully if Gemini is unavailable.
    """
    try:
        api_key  = os.getenv("GEMINI_API_KEY", "")
        base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
        if not api_key:
            return ""

        name     = (user_data.get("display_name") or user_data.get("strava_name") or "跑者").split()[0]
        dist     = act_doc.get("distance_km", 0)
        pace     = act_doc.get("avg_pace", "—")
        hr       = act_doc.get("avg_heart_rate", 0)
        elev     = act_doc.get("total_elevation_gain", 0)
        duration = act_doc.get("duration_str", "—")

        prompt = (
            f"你是一位热情的中文跑步教练。请对以下一次跑步用2-3句话给出简短、有针对性、有激励性的点评。\n"
            f"跑者：{name}\n"
            f"距离：{dist}km，配速：{pace}/km，平均心率：{hr}bpm，爬升：{elev}m，时长：{duration}\n"
            f"要求：语言简洁有力，包含一个具体的训练建议，不要用markdown，不要emoji过多，最多1个emoji。"
        )

        for model in [
            "gemini-2.5-flash-preview-04-17",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-8b",
            "gemini-1.0-pro",
        ]:
            for api_ver in ["v1beta", "v1"]:
                url  = f"{base_url}/{api_ver}/models/{model}:generateContent?key={api_key}"
                body = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200},
                }
                try:
                    resp = requests.post(url, json=body, timeout=20)
                    if resp.status_code == 200:
                        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                        return text.strip()
                except Exception:
                    continue
    except Exception as e:
        print(f"[discord] Coach tip generation failed: {e}")

    return ""


# ── Embed builder ─────────────────────────────────────────────────────────────

def _build_embed(act_doc: dict, user_data: dict, coach_tip: str) -> dict:
    """Builds the Discord embed payload."""
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
    kudos    = act_doc.get("kudos_count", 0)
    cadence  = act_doc.get("avg_cadence", 0)

    # Colour based on distance
    if dist >= 21:
        colour = 0xFC4C02   # Strava orange — long run
    elif dist >= 10:
        colour = 0x3B82F6   # Blue — medium run
    else:
        colour = 0x22C55E   # Green — short run

    # Build field rows
    fields = [
        {"name": "🏁 距离",  "value": f"**{dist} km**",  "inline": True},
        {"name": "⚡ 配速",  "value": f"**{pace}/km**",  "inline": True},
        {"name": "⏱ 时长",  "value": f"**{duration}**", "inline": True},
    ]

    if hr:
        fields.append({"name": "❤️ 平均心率", "value": f"**{hr} bpm**", "inline": True})
    if elev:
        fields.append({"name": "⛰ 爬升",    "value": f"**{elev} m**", "inline": True})
    if cadence:
        fields.append({"name": "🦵 步频",    "value": f"**{cadence} spm**", "inline": True})
    if kudos:
        fields.append({"name": "👍 Kudos",   "value": f"**{kudos}**",  "inline": True})

    # Coach tip field
    if coach_tip:
        fields.append({
            "name":   "🤖 AI 教练点评",
            "value":  coach_tip,
            "inline": False
        })

    # Activity link (best-effort — uses athlete ID if available)
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

    # Use Strava profile avatar if available
    avatar = user_data.get("strava_profile_url") or user_data.get("photoURL")
    if avatar:
        embed["thumbnail"] = {"url": avatar}

    return embed


# ── Public entry point ────────────────────────────────────────────────────────

def send_activity_discord_notification(act_doc: dict, user_data: dict) -> bool:
    """
    Sends a Discord embed notification for a completed run.
    Reads the webhook URL from user_data["discord_webhook_url"] (set in profile).
    Returns True on success, False on failure (never raises).

    Args:
        act_doc   – Firestore activity document dict (as saved by _build_act_doc)
        user_data – Firestore user document dict
    """
    webhook_url = (user_data.get("discord_webhook_url") or "").strip()
    if not webhook_url:
        print("[discord] No discord_webhook_url in user profile — skipping")
        return False

    try:
        coach_tip = _generate_quick_coach_tip(act_doc, user_data)
        embed     = _build_embed(act_doc, user_data, coach_tip)

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

def send_activity_wecom_notification(act_doc: dict, user_data: dict) -> bool:
    """
    Placeholder: Sends a WeCom (企业微信) group robot notification for a completed run.
    Reads the webhook URL from user_data["wecom_webhook_url"] (set in profile).

    TODO: Implement after Discord flow is validated.
    WeCom robot API: POST to webhook URL with JSON body:
      { "msgtype": "markdown", "markdown": { "content": "..." } }

    Args:
        act_doc   – Firestore activity document dict
        user_data – Firestore user document dict
    """
    webhook_url = (user_data.get("wecom_webhook_url") or "").strip()
    if not webhook_url:
        return False

    # TODO: build WeCom markdown message and POST
    print(f"[wecom] WeCom notification not yet implemented for activity {act_doc.get('activity_id')}")
    return False
