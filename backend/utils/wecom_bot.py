"""
WeCom AI Bot (Interactive, Long-Connection)
Uses wecom-aibot-sdk-python to maintain a WebSocket connection and handle incoming messages.

Capabilities:
  - Personal data queries (individual running stats, recent activities)
  - Team/group leaderboard queries (monthly & weekly rankings)
  - AI coaching responses via Gemini (reuses coach.py)
  - User identity binding (WeCom UserId → RGM uid)
"""

import os
import asyncio
import logging
from wecom_aibot_sdk import WSClient, generate_req_id
from firebase_config import db
from routers.coach import _gemini_generate, _fetch_recent_activities, _build_runs_str, _fetch_leaderboard

logger = logging.getLogger("wecom_bot")

_client = None
_bot_task = None


# ── User identity mapping ────────────────────────────────────────────────────

def _resolve_user_by_wecom_id(wecom_user_id: str):
    """
    Find the RGM user by their wecom_user_id.
    Returns (uid, user_data) or (None, None).
    """
    if not wecom_user_id:
        return None, None

    docs = (db.collection("users")
              .where("wecom_user_id", "==", wecom_user_id)
              .limit(1)
              .stream())
    for doc in docs:
        return doc.id, doc.to_dict()
    return None, None


def _bind_user(wecom_user_id: str, bind_code: str):
    """
    Bind a WeCom user to an RGM account.
    Tries matching in order: email → display_name → strava_name.
    Returns the display_name on success, None on failure.
    """
    bind_code = bind_code.strip()
    if not bind_code:
        return None

    # Try email first
    for field in ("email", "display_name", "strava_name"):
        docs = (db.collection("users")
                  .where(field, "==", bind_code)
                  .limit(1)
                  .stream())
        for doc in docs:
            uid = doc.id
            db.collection("users").document(uid).set({"wecom_user_id": wecom_user_id}, merge=True)
            d = doc.to_dict()
            return d.get("display_name") or d.get("strava_name") or uid

    # Case-insensitive fallback: scan all users (small user base)
    all_users = db.collection("users").stream()
    code_lower = bind_code.lower()
    for doc in all_users:
        d = doc.to_dict()
        if (code_lower == (d.get("email") or "").lower()
                or code_lower == (d.get("display_name") or "").lower()
                or code_lower == (d.get("strava_name") or "").lower()):
            uid = doc.id
            db.collection("users").document(uid).set({"wecom_user_id": wecom_user_id}, merge=True)
            return d.get("display_name") or d.get("strava_name") or uid

    return None


# ── Data query helpers ────────────────────────────────────────────────────────

def _fetch_monthly_leaderboard(limit_n: int = 20) -> list:
    """Fetch the monthly leaderboard (all users, sorted by distance)."""
    docs = (db.collection("leaderboard")
              .order_by("total_distance_km", direction="DESCENDING")
              .limit(limit_n)
              .stream())
    return [d.to_dict() for d in docs]


def _fetch_weekly_leaderboard(limit_n: int = 20) -> list:
    """Fetch the weekly leaderboard (all users, sorted by distance)."""
    docs = (db.collection("leaderboard_weekly")
              .order_by("total_distance_km", direction="DESCENDING")
              .limit(limit_n)
              .stream())
    return [d.to_dict() for d in docs]


def _format_leaderboard_markdown(entries: list, title: str) -> str:
    """Format leaderboard entries as a compact markdown string for WeCom."""
    if not entries:
        return f"{title}\n暂无数据"

    medal = ["🥇", "🥈", "🥉"]
    lines = [f"**{title}**\n"]
    for i, e in enumerate(entries):
        name = e.get("display_name", "—")
        km = round(e.get("total_distance_km", 0), 1)
        pace = e.get("avg_pace", "—")
        runs = e.get("run_count", 0)
        icon = medal[i] if i < 3 else f"{i+1}."
        lines.append(f"{icon} **{name}**  {km}km · {runs}次 · {pace}/km")

    return "\n".join(lines)


def _fetch_user_weekly_stats(uid: str) -> dict:
    """Fetch a user's weekly leaderboard stats."""
    doc = db.collection("leaderboard_weekly").document(uid).get()
    return doc.to_dict() if doc.exists else {}


def _fetch_user_goal(uid: str) -> dict:
    """Fetch a user's current goal settings."""
    doc = db.collection("users").document(uid).collection("goals").document("current").get()
    return doc.to_dict() if doc.exists else {}


def _detect_intent(content: str) -> str:
    """
    Simple keyword-based intent detection.
    Returns one of: 'leaderboard_monthly', 'leaderboard_weekly', 'my_stats',
                     'my_activity', 'team_info', 'general'
    """
    c = content.lower()

    # Leaderboard queries
    if any(kw in c for kw in ["排行", "排名", "榜", "谁跑得最多", "谁跑的最多", "龙虎榜"]):
        if any(kw in c for kw in ["周", "本周", "这周", "weekly"]):
            return "leaderboard_weekly"
        return "leaderboard_monthly"

    # Personal stats
    if any(kw in c for kw in ["我跑了", "我的数据", "我的统计", "我这周", "我这个月", "我本月", "我本周", "我的跑量",
                               "计划", "目标", "plan", "goal", "完成度", "进度"]):
        return "my_stats"

    # Recent activity analysis
    if any(kw in c for kw in ["分析", "昨天", "上次跑步", "最近", "上一次"]):
        return "my_activity"

    # Team info
    if any(kw in c for kw in ["团队", "跑团", "成员", "队伍"]):
        return "team_info"

    return "general"


# ── Message processing ────────────────────────────────────────────────────────

async def _process_chat_message(frame, client: WSClient):
    """Core logic to process incoming text and generate a response."""
    try:
        content = frame.body.get("text", {}).get("content", "").strip()
        wecom_user_id = frame.body.get("from", {}).get("userid", "")

        print(f"[wecom_bot] sender={wecom_user_id}, raw_content='{content}'")

        # Strip bot @mention prefix.
        # WeCom sends content like "@Bonnie 你好" or "aBonnie 你好" (@ sometimes stripped).
        # Remove any leading mention of the bot name.
        import re
        bot_name = "Bonnie"  # Must match the bot's display name in WeCom
        content = re.sub(rf'^[@a]?{re.escape(bot_name)}\s*', '', content, flags=re.IGNORECASE).strip()

        if not content:
            return

        # ── Bind command ──────────────────────────────────────────────────
        if content.startswith("绑定 ") or content.startswith("绑定"):
            bind_code = content.replace("绑定", "").strip()
            if not bind_code:
                sid = generate_req_id("stream")
                await client.reply_stream(frame, sid, "请输入你的 RGM 注册邮箱或昵称来绑定，格式：\n**绑定 你的名字**", finish=True)
                return
            name = _bind_user(wecom_user_id, bind_code)
            if name:
                sid = generate_req_id("stream")
                await client.reply_stream(frame, sid, f"✅ 绑定成功！你好，{name}。现在我可以查询你的跑步数据了 🎉", finish=True)
            else:
                sid = generate_req_id("stream")
                await client.reply_stream(frame, sid, "❌ 绑定失败，没找到这个人。试试用 RGM 里的昵称、Strava 名或注册邮箱？", finish=True)
            return

        # ── Identify user ─────────────────────────────────────────────────
        uid, user_data = _resolve_user_by_wecom_id(wecom_user_id)
        intent = _detect_intent(content)

        # ── Quick-reply: Leaderboard (no AI needed) ───────────────────────
        if intent == "leaderboard_monthly":
            entries = await asyncio.to_thread(_fetch_monthly_leaderboard, 10)
            md = _format_leaderboard_markdown(entries, "📊 本月跑量排行榜")
            sid = generate_req_id("stream")
            await client.reply_stream(frame, sid, md, finish=True)
            return

        if intent == "leaderboard_weekly":
            entries = await asyncio.to_thread(_fetch_weekly_leaderboard, 10)
            md = _format_leaderboard_markdown(entries, "📊 本周跑量排行榜")
            sid = generate_req_id("stream")
            await client.reply_stream(frame, sid, md, finish=True)
            return

        # ── Stream reply start (loading state) ────────────────────────────
        stream_id = generate_req_id("stream")
        await client.reply_stream(frame, stream_id, "💨 容我先喝口水…", finish=False)

        # ── Build AI context ──────────────────────────────────────────────
        runner_name = user_data.get("display_name", "跑者") if user_data else "跑者"
        context_str = (
            "你是 RGM 跑团的群聊吉祥物，外号「团宠」。\n"
            "你的性格特点：\n"
            "- 热爱跑步，但更热爱在群里搞气氛\n"
            "- 说话风格：接地气、诙谐幽默、偶尔毒舌但不伤人，像跑团里那个最会活跃气氛的老油条\n"
            "- 喜欢用夸张的比喻和跑圈黑话来调侃和鼓励队友\n"
            "- 会适时制造竞争氛围（善意的激将法），比如'再不跑，排名要被xxx踩到脚底了哦'\n"
            "- 虽然嘴上不饶人，但内心温暖，真正需要鼓励的时候会认真说\n"
            "- 绝对不是那种端着架子的正经教练，而是跑团里最会来事的那个人\n"
            "\n"
            "重要：你和自动推送通知里的'AI教练'是不同的角色。\n"
            "AI教练负责专业分析和训练建议（严肃、有数据），你负责群里互动和气氛（轻松、好玩）。\n"
            "\n"
            f"正在和你聊天的人是：{runner_name}。\n"
        )

        if uid:
            # Personal monthly stats
            lb = await asyncio.to_thread(_fetch_leaderboard, uid)
            if lb:
                context_str += (
                    f"- 本月累计: {lb.get('total_distance_km', 0)}km, "
                    f"跑步{lb.get('run_count', 0)}次, "
                    f"平均配速: {lb.get('avg_pace', '—')}/km\n"
                )

            # Personal weekly stats
            wk = await asyncio.to_thread(_fetch_user_weekly_stats, uid)
            if wk:
                context_str += (
                    f"- 本周累计: {wk.get('total_distance_km', 0)}km, "
                    f"跑步{wk.get('run_count', 0)}次\n"
                )

            # Goals / targets
            goal = await asyncio.to_thread(_fetch_user_goal, uid)
            if goal:
                from datetime import datetime
                current_month = datetime.now().month - 1  # 0-based index
                period = goal.get("period", "monthly")
                target_dist = goal.get("target_distance", 0)
                monthly_targets = goal.get("monthly_targets", [])
                this_month_target = monthly_targets[current_month] if len(monthly_targets) > current_month else target_dist

                if period == "weekly":
                    context_str += f"- 周跑量目标: {target_dist}km\n"
                    # Calculate weekly progress
                    wk_actual = wk.get('total_distance_km', 0) if wk else 0
                    pct = round(wk_actual / target_dist * 100) if target_dist else 0
                    context_str += f"- 周目标完成度: {pct}% ({wk_actual}/{target_dist}km)\n"
                else:
                    context_str += f"- 本月跑量目标: {this_month_target}km\n"
                    # Calculate monthly progress
                    lb_actual = lb.get('total_distance_km', 0) if lb else 0
                    pct = round(lb_actual / this_month_target * 100) if this_month_target else 0
                    context_str += f"- 月目标完成度: {pct}% ({lb_actual}/{this_month_target}km)\n"

            # Recent activities
            acts = await asyncio.to_thread(_fetch_recent_activities, uid, 5)
            if acts:
                context_str += f"- 最近活动: {_build_runs_str(acts)}\n"

            # PB
            if user_data.get("marathon_pb_sec"):
                pb = user_data["marathon_pb_sec"]
                h, r = divmod(pb, 3600); m = r // 60
                context_str += f"- 全马PB: {h}:{m:02d}\n"

            # Team leaderboard context (so AI can reference rankings)
            if intent in ("my_stats", "my_activity", "general"):
                monthly_lb = await asyncio.to_thread(_fetch_monthly_leaderboard, 10)
                if monthly_lb:
                    # Find user's rank
                    user_rank = next(
                        (i + 1 for i, e in enumerate(monthly_lb)
                         if e.get("uid") == uid),
                        None
                    )
                    top3 = ", ".join(
                        f"{e.get('display_name', '—')}({e.get('total_distance_km', 0)}km)"
                        for e in monthly_lb[:3]
                    )
                    context_str += f"- 本月排行前三: {top3}\n"
                    if user_rank:
                        context_str += f"- {runner_name}当前排名第{user_rank}名\n"
        else:
            context_str += (
                "（注：该用户尚未绑定 RGM 账号，无法查询其具体的跑步数据。"
                "请友好地提示他可以通过回复『绑定 邮箱』来绑定。）\n"
            )

        prompt = (
            f"{context_str}\n\n"
            f"用户说：{content}\n\n"
            f"请用你的'团宠'人设回复。要求：\n"
            f"- 简短有力（群聊场景，不超过120字）\n"
            f"- 语言风格：诙谐、接地气、像朋友聊天，可以适度调侃但不恶意\n"
            f"- 如果问到数据/排名，先给出数据，再加一句有梗的点评\n"
            f"- 善用跑圈黑话（配速、撞墙、LSD、间歇、乳酸阈值等），但要让小白也能看懂\n"
            f"- 多用 emoji 增加群聊感\n"
            f"- 不要用markdown标题格式，不要用JSON，纯文本+emoji即可\n"
            f"- 如果用户明显心情低落或受伤，收起嬉皮，认真关心"
        )

        # ── Call Gemini ───────────────────────────────────────────────────
        result = await asyncio.to_thread(
            _gemini_generate, prompt,
            temperature=0.7, max_tokens=1024, response_json=False
        )
        reply_text = result.get("text", "我刚跑了个间歇，喘不上气，等我缓缓再说 🫠").strip()

        # ── Stream reply finish ───────────────────────────────────────────
        await client.reply_stream(frame, stream_id, reply_text, finish=True)

    except Exception as e:
        logger.error(f"[wecom_bot] Error processing message: {e}")
        try:
            sid = generate_req_id("stream")
            await client.reply_stream(frame, sid, "💀 不好意思，我刚撞墙了…脑子暂时转不动，等我补个胶再来！", finish=True)
        except Exception:
            pass


# ── Bot lifecycle ─────────────────────────────────────────────────────────────

_bot_client = None
_bot_task = None


async def _bot_loop():
    """Main bot loop — runs as a background asyncio task in FastAPI's event loop."""
    global _bot_client
    bot_id = os.getenv("WECOM_BOT_ID", "").strip()
    secret = os.getenv("WECOM_BOT_SECRET", "").strip()

    print(f"[wecom_bot] Creating WSClient with bot_id={bot_id[:8]}...")
    client = WSClient({
        "bot_id": bot_id,
        "secret": secret,
    })
    _bot_client = client

    # Register message handler
    async def on_text(frame):
        print(f"[wecom_bot] >>> Message from={frame.body.get('from')}")
        try:
            await _process_chat_message(frame, client)
        except Exception as e:
            print(f"[wecom_bot] Error in handler: {e}")
            import traceback
            traceback.print_exc()

    client.on("message.text", on_text)
    print("[wecom_bot] Handler registered.")

    # Initial connect
    print("[wecom_bot] Connecting...")
    await client.connect_async()
    print("[wecom_bot] Connected! Monitoring connection health...")

    # Health check loop
    while True:
        await asyncio.sleep(15)
        if not client.is_connected:
            print("[wecom_bot] Connection lost, waiting 15s before reconnect...")
            await asyncio.sleep(15)
            try:
                await client.connect_async()
                print("[wecom_bot] Reconnected!")
            except Exception as e:
                print(f"[wecom_bot] Reconnect failed: {e}")


async def start_wecom_bot_async():
    """Start the bot as a background task in the current event loop."""
    global _bot_task
    bot_id = os.getenv("WECOM_BOT_ID", "").strip()
    secret = os.getenv("WECOM_BOT_SECRET", "").strip()
    if not bot_id or not secret:
        print("[wecom_bot] Skipped: credentials not set.")
        return

    _bot_task = asyncio.create_task(_bot_loop())
    print("[wecom_bot] Background task created in FastAPI event loop.")

