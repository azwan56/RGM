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


def _find_mentioned_users(content: str) -> list:
    """
    Scan the message content for names of other users.
    Returns a list of (uid, user_data) tuples.
    """
    mentioned = []
    # Fetch all users with connected strava
    docs = db.collection("users").where("strava_connected", "==", True).stream()
    content_lower = content.lower()
    
    for doc in docs:
        d = doc.to_dict()
        names_to_check = []
        if d.get("display_name"):
            names_to_check.append(d["display_name"].lower())
            # Also check first name / shorthand (e.g. "Vivian" from "Vivian CHEN")
            names_to_check.append(d["display_name"].split()[0].lower())
        if d.get("strava_name"):
            names_to_check.append(d["strava_name"].lower())
            names_to_check.append(d["strava_name"].split()[0].lower())
            
        # Remove duplicates and short fragments (like single letters)
        names_to_check = list(set(n for n in names_to_check if len(n) > 1))
        
        if any(name in content_lower for name in names_to_check):
            mentioned.append((doc.id, d))
            
    return mentioned


def _detect_month_query(content: str):
    """
    Check if the user is asking about a specific month.
    Returns (year, month) tuple or None.
    """
    import re
    from datetime import datetime
    now = datetime.now()
    
    # Match patterns like "5月", "五月", "上个月", "上月"
    m = re.search(r'(\d{1,2})\s*月', content)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            # If asking about a future month this year, assume last year
            year = now.year if month <= now.month else now.year - 1
            return (year, month)
    
    if any(kw in content for kw in ["上个月", "上月"]):
        prev = now.month - 1
        year = now.year if prev >= 1 else now.year - 1
        prev = prev if prev >= 1 else 12
        return (year, prev)
    
    return None


def _detect_year_query(content: str):
    """
    Check if the user is asking about yearly stats.
    Returns year (int) or None.
    """
    import re
    from datetime import datetime
    now = datetime.now()

    if any(kw in content for kw in ["今年", "年跑量", "年度", "全年"]):
        return now.year

    m = re.search(r'(\d{4})\s*年', content)
    if m:
        return int(m.group(1))

    if "去年" in content:
        return now.year - 1

    return None


def _fetch_yearly_leaderboard(year: int) -> list:
    """Fetch yearly leaderboard from leaderboard_yearly collection."""
    docs = (db.collection("leaderboard_yearly")
              .order_by("total_distance_km", direction="DESCENDING")
              .stream())
    results = []
    for d in docs:
        data = d.to_dict()
        if data.get("year") == year:
            results.append(data)
    results.sort(key=lambda x: x.get("total_distance_km", 0), reverse=True)
    return results


def _fetch_historical_month_leaderboard(year: int, month: int) -> list:
    """
    Compute a leaderboard for a specific historical month by summing activities.
    Returns a list of dicts sorted by total_distance_km descending.
    """
    from datetime import datetime
    month_prefix = f"{year}-{month:02d}"
    
    results = []
    users = db.collection("users").stream()
    for udoc in users:
        uid = udoc.id
        udata = udoc.to_dict()
        name = udata.get("display_name") or udata.get("strava_name") or uid[:8]
        gender = udata.get("gender", "")
        
        acts = (db.collection("users").document(uid)
                  .collection("activities")
                  .order_by("start_date_local", direction="DESCENDING")
                  .limit(100)
                  .stream())
        
        total_km = 0.0
        run_count = 0
        for a in acts:
            ad = a.to_dict()
            date_str = ad.get("start_date_local", "")[:7]  # "YYYY-MM"
            if date_str == month_prefix:
                total_km += ad.get("distance_km", 0)
                run_count += 1
        
        if total_km > 0:
            results.append({
                "display_name": name,
                "total_distance_km": round(total_km, 2),
                "run_count": run_count,
                "uid": uid,
                "gender": gender,
            })
    
    results.sort(key=lambda x: x["total_distance_km"], reverse=True)
    return results


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

        # ── Stream setup ────────────────────────────────────────────────────
        stream_id = generate_req_id("stream")

        # ── Build AI context ──────────────────────────────────────────────
        runner_name = user_data.get("display_name", "跑者") if user_data else "跑者"
        gender_val = user_data.get("gender", "") if user_data else ""
        gender_str = "女" if gender_val == "female" else ("男" if gender_val == "male" else "未知")
        
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
            f"正在和你聊天的人是：{runner_name} (性别: {gender_str})。\n"
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
                goal_period = goal.get("period", "monthly")
                target_dist = goal.get("target_distance", 0)
                monthly_targets = goal.get("monthly_targets", [])
                this_month_target = monthly_targets[current_month] if len(monthly_targets) > current_month else 0

                # Show primary plan
                if goal_period == "weekly":
                    wk_actual = wk.get('total_distance_km', 0) if wk else 0
                    pct = round(wk_actual / target_dist * 100) if target_dist else 0
                    context_str += (
                        f"- 主要计划：【周计划】，周目标 {target_dist}km\n"
                        f"- 本周已跑: {wk_actual}km，完成度: {pct}%\n"
                    )
                else:
                    lb_actual = lb.get('total_distance_km', 0) if lb else 0
                    pct = round(lb_actual / this_month_target * 100) if this_month_target else 0
                    context_str += (
                        f"- 主要计划：【月计划】，本月目标 {this_month_target}km\n"
                        f"- 本月已跑: {lb_actual}km，完成度: {pct}%\n"
                    )

                # Also show the other plan if data exists
                if this_month_target and goal_period == "weekly":
                    lb_actual = lb.get('total_distance_km', 0) if lb else 0
                    m_pct = round(lb_actual / this_month_target * 100) if this_month_target else 0
                    context_str += f"- 月度目标也有设: 本月目标 {this_month_target}km，已跑 {lb_actual}km ({m_pct}%)\n"
                elif target_dist and goal_period == "monthly":
                    wk_actual = wk.get('total_distance_km', 0) if wk else 0
                    w_pct = round(wk_actual / target_dist * 100) if target_dist else 0
                    context_str += f"- 周目标也有设: 每周 {target_dist}km，本周已跑 {wk_actual}km ({w_pct}%)\n"
            else:
                context_str += "- 该用户还没有设跑量目标\n"

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
                from datetime import datetime
                now = datetime.now()
                
                # Check if user is asking about yearly stats
                year_query = _detect_year_query(content)
                # Check if user is asking about a specific month
                month_query = _detect_month_query(content)
                
                if year_query:
                    yearly_lb = await asyncio.to_thread(_fetch_yearly_leaderboard, year_query)
                    if yearly_lb:
                        all_entries = ", ".join(
                            f"{e.get('display_name', '—')}({e.get('total_distance_km', 0)}km/{e.get('run_count', 0)}次)"
                            for e in yearly_lb
                        )
                        context_str += f"- 【{year_query}年度】跑量排名: {all_entries}\n"
                    else:
                        context_str += f"- {year_query}年暂无跑步记录\n"
                elif month_query and (month_query[1] != now.month or month_query[0] != now.year):
                    # Historical month query
                    q_year, q_month = month_query
                    hist_lb = await asyncio.to_thread(_fetch_historical_month_leaderboard, q_year, q_month)
                    if hist_lb:
                        top_all = ", ".join(
                            f"{e['display_name']}({e['total_distance_km']}km)"
                            for e in hist_lb
                        )
                        context_str += f"- 【{q_year}年{q_month}月】跑量排名: {top_all}\n"
                    else:
                        context_str += f"- {q_year}年{q_month}月暂无跑步记录\n"
                else:
                    # Current month
                    monthly_lb = await asyncio.to_thread(_fetch_monthly_leaderboard, 10)
                    if monthly_lb:
                        user_rank = next(
                            (i + 1 for i, e in enumerate(monthly_lb)
                             if e.get("uid") == uid),
                            None
                        )
                        top3 = ", ".join(
                            f"{e.get('display_name', '—')}({e.get('total_distance_km', 0)}km)"
                            for e in monthly_lb[:3]
                        )
                        context_str += f"- 【{now.year}年{now.month}月·本月】排行前三: {top3}\n"
                        if user_rank:
                            context_str += f"- {runner_name}当前排名第{user_rank}名\n"

        else:
            context_str += (
                "（注：该用户尚未绑定 RGM 账号，无法查询其具体的跑步数据。"
                "请友好地提示他可以通过回复『绑定 邮箱』来绑定。）\n"
            )

        # ── Include data for mentioned users ──────────────────────────────
        mentioned_users = await asyncio.to_thread(_find_mentioned_users, content)
        # Filter out the speaker themselves if they were included
        mentioned_users = [(m_uid, m_data) for m_uid, m_data in mentioned_users if m_uid != uid]
        
        if mentioned_users:
            context_str += "\n【聊天中提到其他成员的数据，可供参考】：\n"
            for m_uid, m_data in mentioned_users:
                m_name = m_data.get("display_name", m_data.get("strava_name", "某队员"))
                m_gender_val = m_data.get("gender", "")
                m_gender_str = "女" if m_gender_val == "female" else ("男" if m_gender_val == "male" else "未知")
                context_str += f"队员 [{m_name}] (性别: {m_gender_str}):\n"
                
                m_lb = await asyncio.to_thread(_fetch_leaderboard, m_uid)
                if m_lb:
                    context_str += f"  - 本月已跑: {m_lb.get('total_distance_km', 0)}km\n"
                    
                m_goal = await asyncio.to_thread(_fetch_user_goal, m_uid)
                if m_goal:
                    from datetime import datetime
                    current_month = datetime.now().month - 1
                    m_goal_period = m_goal.get("period", "monthly")
                    m_target_dist = m_goal.get("target_distance", 0)
                    m_monthly_targets = m_goal.get("monthly_targets", [])
                    m_this_month = m_monthly_targets[current_month] if len(m_monthly_targets) > current_month else 0
                    
                    if m_goal_period == "weekly":
                        context_str += f"  - 计划: 周目标 {m_target_dist}km\n"
                    else:
                        context_str += f"  - 计划: 月目标 {m_this_month}km\n"

        prompt = (
            f"{context_str}\n\n"
            f"用户说：{content}\n\n"
            f"请用你的'团宠'人设回复。要求：\n"
            f"- 严格限制在50-70个中文字以内（包括标点和emoji），这是硬性限制！\n"
            f"- 语言风格：诙谐、接地气、毒舌但好玩，像跑团里最会搞气氛的老油条\n"
            f"- 如果用户问跑量/数据：一句数据+一句调侃，精炼不啰嗦\n"
            f"- 如果用户只是闲聊（比如求鸡汤、打招呼）：直接按人设发挥，不用强行报数据\n"
            f"- 用1-2个emoji\n"
            f"- 纯文本，不要用markdown格式如**加粗**\n"
            f"- 如果用户心情低落或受伤，收起嬉皮，认真关心"
        )

        # ── Call Gemini ───────────────────────────────────────────────────
        result = await asyncio.to_thread(
            _gemini_generate, prompt,
            temperature=0.7, max_tokens=300, response_json=False
        )
        reply_text = result.get("text", "我刚跑了个间歇，喘不上气，等我缓缓再说 🫠").strip()
        # Strip any markdown bold markers
        reply_text = reply_text.replace("**", "")

        # ── Safety truncation (WeCom stream limit ~240 bytes) ─────────────
        MAX_BYTES = 220  # Leave margin below 240
        encoded = reply_text.encode("utf-8")
        if len(encoded) > MAX_BYTES:
            # Find the last sentence-ending punctuation within the limit
            truncated = encoded[:MAX_BYTES].decode("utf-8", errors="ignore")
            # Try to cut at last sentence boundary
            for sep in ["！", "！", "。", "？", "~", "…", "!", "?", ".", "\n"]:
                idx = truncated.rfind(sep)
                if idx > 0:
                    truncated = truncated[:idx + len(sep)]
                    break
            reply_text = truncated

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

