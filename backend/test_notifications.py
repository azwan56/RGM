"""
Notification Test Script
========================
Tests all 4 notification types with prominent TEST banners:
  1. Activity completed  → Discord  (yesterday's run)
  2. Activity completed  → WeCom    (yesterday's run)
  3. Rest-day reminder   → Discord  (no activity yesterday)
  4. Rest-day reminder   → WeCom    (no activity yesterday)

Run from backend/:
    venv/bin/python test_notifications.py [uid]

If uid is omitted the script auto-detects the first user that has
at least one webhook configured.
"""

import sys
import os
import requests
from datetime import datetime, date, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

import firebase_config  # noqa: F401  — bootstraps Firestore
from firebase_config import db

# ── ANSI colours for terminal output ─────────────────────────────────────────
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def ok(msg):  print(f"  {GREEN}✅ {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}⚠️  {msg}{RESET}")
def err(msg):  print(f"  {RED}❌ {msg}{RESET}")
def info(msg): print(f"  {CYAN}ℹ️  {msg}{RESET}")
def section(title):
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}")

TEST_LABEL   = "🧪【测试消息 · TEST · 请忽略】"
TEST_COLOUR  = 0xFF5722   # Deep Orange — unmistakable test colour

# ── Resolve target user ───────────────────────────────────────────────────────

section("Step 1 · Locate user")

uid = sys.argv[1] if len(sys.argv) > 1 else None

if not uid:
    print("  No uid provided — scanning Firestore for users with webhooks…")
    users = db.collection("users").stream()
    found = []
    for u in users:
        d = u.to_dict()
        if d.get("discord_webhook_url") or d.get("wecom_webhook_url"):
            found.append((u.id, d))
    if not found:
        err("No users with discord_webhook_url or wecom_webhook_url found.")
        err("Please save a webhook URL in your RGM profile first.")
        sys.exit(1)
    uid, user_data = found[0]
else:
    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        err(f"User {uid} not found in Firestore.")
        sys.exit(1)
    user_data = doc.to_dict()

runner_name = (
    user_data.get("display_name") or
    user_data.get("strava_name") or
    user_data.get("email", "").split("@")[0] or
    "跑者"
)

discord_url = (user_data.get("discord_webhook_url") or "").strip()
wecom_url   = (user_data.get("wecom_webhook_url")   or "").strip()

ok(f"User: {uid}")
ok(f"Name: {runner_name}")
info(f"Discord webhook: {'configured ✓' if discord_url else 'NOT configured'}")
info(f"WeCom webhook:   {'configured ✓' if wecom_url else 'NOT configured'}")

# ── Fetch yesterday's activity ────────────────────────────────────────────────

section("Step 2 · Fetch yesterday's activity")

# Use CST (UTC+8) for "yesterday"
cst_now   = datetime.now(timezone.utc) + timedelta(hours=8)
yesterday = (cst_now - timedelta(days=1)).date().isoformat()   # "YYYY-MM-DD"

print(f"  Looking for an activity on {yesterday} (CST) …")

acts = (
    db.collection("users").document(uid)
    .collection("activities")
    .order_by("start_date_local", direction="DESCENDING")
    .limit(10)
    .stream()
)
activities = [(a.id, a.to_dict()) for a in acts]

target_act = None
for aid, a in activities:
    if a.get("start_date_local", "")[:10] == yesterday:
        target_act = a
        ok(f"Found yesterday's run: {a.get('name')}  "
           f"{a.get('distance_km')}km @ {a.get('avg_pace')}/km")
        break

if not target_act and activities:
    # Fall back to most recent run
    target_act = activities[0][1]
    warn(f"No activity found for {yesterday}. "
         f"Using most recent run instead: "
         f"{target_act.get('name')} ({target_act.get('start_date_local','')[:10]})")

if not target_act:
    err("No activities in Firestore. Please sync Strava first.")
    sys.exit(1)

# ── Build shared context ──────────────────────────────────────────────────────

section("Step 3 · Build rich context")
print("  Fetching monthly km & fitness state …")

from utils.discord import (
    _get_monthly_km, _get_fitness_state, _generate_coach_tip,
    _build_embed, _generate_rest_day_tip,
)

date_str   = target_act.get("start_date_local", "")
monthly_km = _get_monthly_km(uid, date_str)
fitness    = _get_fitness_state(uid, user_data)
context    = {"monthly_km": monthly_km, **fitness}

ok(f"Monthly km: {monthly_km} km")
ok(f"Fitness: CTL={fitness.get('ctl','—')}  ATL={fitness.get('atl','—')}  TSB={fitness.get('tsb','—')}")

# ── Generate AI tips ──────────────────────────────────────────────────────────

section("Step 4 · Generate AI coach tips (Gemini)")

print("  Generating activity coach tip …")
try:
    act_tip = _generate_coach_tip(target_act, user_data, context)
    ok(f"Activity tip: {act_tip[:80]}{'…' if len(act_tip)>80 else ''}")
except Exception as e:
    act_tip = "（AI生成失败，使用默认文案）"
    warn(f"Activity tip generation failed: {e}")

print("  Generating rest-day tip …")
try:
    rest_tip = _generate_rest_day_tip(user_data, yesterday, monthly_km)
    ok(f"Rest-day tip: {rest_tip[:80]}{'…' if len(rest_tip)>80 else ''}")
except Exception as e:
    rest_tip = "昨天休息了一天，今天重新出发吧！"
    warn(f"Rest-day tip generation failed: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 1 — Activity notification → Discord
# ════════════════════════════════════════════════════════════════════════════════

section("TEST 1 · Activity notification → Discord")

if not discord_url:
    warn("Skipped — no Discord webhook configured for this user.")
else:
    # Build standard embed then inject test markers
    embed = _build_embed(target_act, user_data, act_tip, context)
    embed["title"]  = f"{TEST_LABEL}\n{embed['title']}"
    embed["color"]  = TEST_COLOUR
    embed["footer"] = {"text": f"⚠️ 测试消息 · TEST · {embed['footer']['text']}"}

    payload = {"embeds": [embed], "username": "RGM 跑团助手 [TEST]"}
    resp = requests.post(discord_url, json=payload, timeout=10)
    if resp.status_code in (200, 204):
        ok("Discord activity notification sent! ✉️  Check your Discord channel.")
    else:
        err(f"Failed — HTTP {resp.status_code}: {resp.text[:120]}")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 2 — Activity notification → WeCom
# ════════════════════════════════════════════════════════════════════════════════

section("TEST 2 · Activity notification → WeCom")

if not wecom_url:
    warn("Skipped — no WeCom webhook configured for this user.")
else:
    dist     = target_act.get("distance_km", 0)
    pace     = target_act.get("avg_pace", "—")
    duration = target_act.get("duration_str", "—")
    elev     = target_act.get("total_elevation_gain", 0)
    run_name = target_act.get("name", "跑步")
    date_short = (target_act.get("start_date_local") or yesterday)[:10]

    # Weekly progress
    wp = {}
    wp_str = ""
    if monthly_km:
        month_label = date_str[:7] if date_str else datetime.now().strftime("%Y-%m")
        wp_str = f"📅 {month_label} 月累计：**{monthly_km} km**\n"

    md  = f"> {TEST_LABEL}\n\n"
    md += f"🏃 **{runner_name} 完成了一次跑步！**\n"
    md += f"> **{run_name}** · {date_short}\n\n"
    md += f"🏁 距离：**{dist} km**\n"
    md += f"⚡ 配速：**{pace}/km**  |  ⏱ 时长：{duration}\n"
    if elev and elev > 5:
        md += f"🏔 爬升：{elev}m\n"
    md += wp_str
    if act_tip:
        md += f"\n🤖 **Canova教练点评**：\n{act_tip}\n"
    md += f"\n---\n⚠️ *此为测试消息，请忽略 · TEST MESSAGE*"

    payload = {"msgtype": "markdown", "markdown": {"content": md}}
    resp = requests.post(wecom_url, json=payload, timeout=10)
    if resp.status_code == 200 and resp.json().get("errcode") == 0:
        ok("WeCom activity notification sent! ✉️  Check your WeCom group.")
    else:
        err(f"Failed — HTTP {resp.status_code}: {resp.text[:120]}")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 3 — Rest-day reminder → Discord
# ════════════════════════════════════════════════════════════════════════════════

section("TEST 3 · Rest-day reminder → Discord")

if not discord_url:
    warn("Skipped — no Discord webhook configured for this user.")
else:
    fields = [
        {
            "name":  "📅 昨天",
            "value": f"**{yesterday}**  — 无运动记录",
            "inline": True,
        },
    ]
    if monthly_km:
        month_label = yesterday[:7]
        fields.append({
            "name":  f"📊 {month_label} 月累计",
            "value": f"**{monthly_km} km**",
            "inline": True,
        })
    if rest_tip:
        fields.append({
            "name":   "🤖 AI 教练寄语",
            "value":  rest_tip,
            "inline": False,
        })

    embed = {
        "title":       f"{TEST_LABEL}\n☀️ 早安，{runner_name}！昨天没有运动记录",
        "description": "今天是重新出发的好时机 💪",
        "color":       TEST_COLOUR,
        "fields":      fields,
        "footer":      {"text": "⚠️ 测试消息 · TEST · RGM 跑团管理平台 · AI 教练提醒"},
        "timestamp":   datetime.utcnow().isoformat() + "Z",
    }
    avatar = user_data.get("strava_profile_url") or user_data.get("photoURL")
    if avatar:
        embed["thumbnail"] = {"url": avatar}

    payload = {"embeds": [embed], "username": "RGM 跑团助手 [TEST]"}
    resp = requests.post(discord_url, json=payload, timeout=10)
    if resp.status_code in (200, 204):
        ok("Discord rest-day reminder sent! ✉️  Check your Discord channel.")
    else:
        err(f"Failed — HTTP {resp.status_code}: {resp.text[:120]}")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 4 — Rest-day reminder → WeCom
# ════════════════════════════════════════════════════════════════════════════════

section("TEST 4 · Rest-day reminder → WeCom")

if not wecom_url:
    warn("Skipped — no WeCom webhook configured for this user.")
else:
    md  = f"> {TEST_LABEL}\n\n"
    md += f"☀️ **早安，{runner_name}！**\n"
    md += f"> 昨天（{yesterday}）暂无运动记录\n\n"
    if monthly_km:
        month_label = yesterday[:7]
        md += f"📊 {month_label} 月累计：**{monthly_km} km**\n\n"
    if rest_tip:
        md += f"🤖 **教练寄语**：{rest_tip}\n"
    md += "\n💪 今天是重新出发的好时机，加油！"
    md += "\n\n---\n⚠️ *此为测试消息，请忽略 · TEST MESSAGE*"

    payload = {"msgtype": "markdown", "markdown": {"content": md}}
    resp = requests.post(wecom_url, json=payload, timeout=10)
    if resp.status_code == 200 and resp.json().get("errcode") == 0:
        ok("WeCom rest-day reminder sent! ✉️  Check your WeCom group.")
    else:
        err(f"Failed — HTTP {resp.status_code}: {resp.text[:120]}")


# ── Summary ───────────────────────────────────────────────────────────────────

section("Done")
print(f"""
  All tests completed.
  • Tests 1 & 2 — activity notification (with AI coach tip)
  • Tests 3 & 4 — rest-day reminder    (with AI encouragement)

  Every message carries a prominent  {TEST_LABEL}
  banner so recipients know it's a test run.

  If any test was skipped, save the missing webhook URL in
  your RGM profile page and re-run this script.
""")
