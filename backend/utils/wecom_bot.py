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
import base64
import time
from datetime import datetime
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


# ── Chat History ─────────────────────────────────────────────────────────────

def _fetch_chat_history(wecom_user_id: str, uid: str, limit: int = 10) -> list:
    """Fetch recent chat history for the user from Firestore."""
    try:
        if uid:
            ref = db.collection("users").document(uid).collection("wecom_chat_history")
        else:
            ref = db.collection("wecom_guests").document(wecom_user_id).collection("chat_history")
        
        docs = ref.order_by("timestamp", direction="DESCENDING").limit(limit).stream()
        history = [d.to_dict() for d in docs]
        return list(reversed(history))
    except Exception as e:
        print(f"[wecom_bot] Failed to fetch chat history: {e}")
        return []


def _save_chat_message(wecom_user_id: str, uid: str, role: str, content: str, media_type: str = None):
    """Save a single chat message to history."""
    if not content and not media_type:
        return
        
    if uid:
        ref = db.collection("users").document(uid).collection("wecom_chat_history")
    else:
        ref = db.collection("wecom_guests").document(wecom_user_id).collection("chat_history")
        
    msg_id = str(int(time.time() * 1000))
    ref.document(msg_id).set({
        "role": role,
        "content": content,
        "media_type": media_type,
        "timestamp": datetime.now().isoformat()
    })


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


def _extract_quoted_text(frame_body: dict) -> str:
    """
    Extract text content from a WeCom quoted message.
    WeCom sends quoted messages in frame.body.quote with various formats:
      - Simple text: {"msgtype": "text", "text": {"content": "..."}}
      - Mixed:       {"msgtype": "mixed", "mixed": {"msg_item": [...]}}
    Returns the extracted text or empty string.
    """
    quote = frame_body.get("quote")
    if not quote:
        return ""

    msgtype = quote.get("msgtype", "")

    if msgtype == "text":
        return (quote.get("text", {}).get("content", "") or "").strip()

    if msgtype == "mixed":
        items = quote.get("mixed", {}).get("msg_item", [])
        texts = []
        for item in items:
            if item.get("msgtype") == "text":
                t = (item.get("text", {}).get("content", "") or "").strip()
                if t:
                    texts.append(t)
        return " ".join(texts)

    # Fallback: try to find any text content in the quote dict
    if "text" in quote:
        return (quote.get("text", {}).get("content", "") or "").strip()

    return ""


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
    """Fetch yearly leaderboard. Tries leaderboard_yearly first, falls back to computing from activities."""
    # Try the pre-computed collection first
    docs = (db.collection("leaderboard_yearly")
              .where("year", "==", year)
              .stream())
    results = [d.to_dict() for d in docs]
    if results:
        results.sort(key=lambda x: x.get("total_distance_km", 0), reverse=True)
        return results

    # Fallback: compute from all users' activities for that year
    year_start = f"{year}-01-01"
    year_end = f"{year + 1}-01-01"
    users = db.collection("users").where("strava_connected", "==", True).stream()
    for udoc in users:
        uid = udoc.id
        udata = udoc.to_dict()
        name = udata.get("display_name") or udata.get("strava_name") or uid[:8]
        acts = (db.collection("users").document(uid)
                  .collection("activities")
                  .where("start_date_local", ">=", year_start)
                  .where("start_date_local", "<", year_end)
                  .stream())
        total_km = 0.0
        run_count = 0
        for a in acts:
            ad = a.to_dict()
            if ad.get("activity_type", "run") != "run":
                continue
            total_km += ad.get("distance_km", 0)
            run_count += 1
        if total_km > 0:
            results.append({
                "display_name": name,
                "total_distance_km": round(total_km, 2),
                "run_count": run_count,
                "uid": uid,
                "year": year,
            })
    results.sort(key=lambda x: x["total_distance_km"], reverse=True)
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

async def _process_chat_message(frame, client: WSClient, msgtype: str = "text"):
    """Core logic to process incoming text and generate a response."""
    global _last_chatid
    try:
        content = ""
        inline_data = None
        wecom_user_id = frame.body.get("from", {}).get("userid", "")
        media_type = None

        # Auto-capture group chatid for send_bonnie_message()
        msg_chatid = frame.body.get("chatid", "")
        if msg_chatid:
            _last_chatid = msg_chatid

        if msgtype == "text":
            content = frame.body.get("text", {}).get("content", "").strip()
        elif msgtype == "image":
            img_obj = frame.body.get("image", {})
            url = img_obj.get("url")
            aes_key = img_obj.get("aeskey")
            if url:
                try:
                    file_bytes, ext = await client.download_file(url, aes_key)
                    b64 = base64.b64encode(file_bytes).decode("utf-8")
                    inline_data = {
                        "mimeType": "image/jpeg",
                        "data": b64
                    }
                    media_type = "image"
                    content = "[用户发送了一张图片]"
                except Exception as e:
                    logger.error(f"[wecom_bot] Image download failed: {e}")
                    content = "[接收到图片，但无法下载]"
        elif msgtype == "mixed":
            # For mixed messages with image and text
            items = frame.body.get("mixed", {}).get("msg_item", [])
            for item in items:
                if item.get("msgtype") == "text":
                    content += (item.get("text", {}).get("content", "") or "").strip() + " "
                elif item.get("msgtype") == "image":
                    url = item.get("image", {}).get("url")
                    aes_key = item.get("image", {}).get("aeskey")
                    if url and not inline_data: # only take first image for now
                        try:
                            file_bytes, ext = await client.download_file(url, aes_key)
                            b64 = base64.b64encode(file_bytes).decode("utf-8")
                            inline_data = {
                                "mimeType": "image/jpeg",
                                "data": b64
                            }
                            media_type = "image"
                        except Exception as e:
                            logger.error(f"[wecom_bot] Mixed image download failed: {e}")
            content = content.strip()
        
        # ── Extract quoted message context ────────────────────────────────
        quoted_text = _extract_quoted_text(frame.body)
        if quoted_text:
            print(f"[wecom_bot] sender={wecom_user_id}, raw_content='{content}', quoted='{quoted_text[:100]}'")
        else:
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

        # Save user message to history
        asyncio.create_task(asyncio.to_thread(
            _save_chat_message, wecom_user_id, uid, "user", content, media_type
        ))

        # Combine current message + quoted text for intent/keyword detection
        combined_text = f"{quoted_text} {content}" if quoted_text else content
        intent = _detect_intent(combined_text)

        # ── Quick-reply: Leaderboard (no AI needed) ───────────────────────
        if msgtype == "text" and not inline_data:
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
                # Use combined_text (current + quoted) so quoted context
                # keywords like "今年" are also detected
                year_query = _detect_year_query(combined_text)
                # Check if user is asking about a specific month
                month_query = _detect_month_query(combined_text)
                
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
        # Use combined_text so names mentioned in quoted messages are also found
        mentioned_users = await asyncio.to_thread(_find_mentioned_users, combined_text)
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
                    context_str += f"  - 本月已跑: {m_lb.get('total_distance_km', 0)}km, 跑步{m_lb.get('run_count', 0)}次, 平均配速: {m_lb.get('avg_pace', '—')}/km\n"

                m_wk = await asyncio.to_thread(_fetch_user_weekly_stats, m_uid)
                if m_wk:
                    context_str += f"  - 本周已跑: {m_wk.get('total_distance_km', 0)}km, 跑步{m_wk.get('run_count', 0)}次\n"

                m_goal = await asyncio.to_thread(_fetch_user_goal, m_uid)
                if m_goal:
                    from datetime import datetime
                    current_month = datetime.now().month - 1
                    m_goal_period = m_goal.get("period", "monthly")
                    m_target_dist = m_goal.get("target_distance", 0)
                    m_monthly_targets = m_goal.get("monthly_targets", [])
                    m_this_month = m_monthly_targets[current_month] if len(m_monthly_targets) > current_month else 0
                    
                    if m_goal_period == "weekly":
                        m_wk_actual = m_wk.get('total_distance_km', 0) if m_wk else 0
                        m_w_pct = round(m_wk_actual / m_target_dist * 100) if m_target_dist else 0
                        context_str += f"  - 计划: 周目标 {m_target_dist}km, 本周完成 {m_w_pct}%\n"
                    else:
                        context_str += f"  - 计划: 月目标 {m_this_month}km\n"

        # Build conversation context for AI prompt
        quoted_context = ""
        if quoted_text:
            quoted_context = f"【用户引用了之前的消息】：\n\"{quoted_text}\"\n\n"

        prompt = (
            f"{context_str}\n\n"
            f"{quoted_context}"
            f"用户当前的输入是：{content}\n\n"
            f"请用你的'团宠'人设回复。要求：\n"
            f"- 控制在80-150个中文字以内（包括标点和emoji），简洁但把话说完整\n"
            f"- 语言风格：诙谐、接地气、毒舌但好玩，像跑团里最会搞气氛的老油条\n"
            f"- 如果用户发送了图片，请结合图片内容进行调侃或鼓励\n"
            f"- 如果用户问跑量/数据：先回答数据再调侃，数据要完整别说一半\n"
            f"- 如果用户只是闲聊（比如求鸡汤、打招呼）：直接按人设发挥，不用强行报数据\n"
            f"- 用1-2个emoji\n"
            f"- 纯文本，不要用markdown格式如**加粗**\n"
            f"- 如果用户心情低落或受伤，收起嬉皮，认真关心\n"
            f"- 严禁编造数据！如果上面没有提供相关数据，就说'这个数据我还没收到，让我查查去'\n"
            f"- 如果用户问赛事、天气、新闻等实时信息，你必须基于搜索结果回答，给出具体的日期、地点和报名链接。如果搜索不到可靠信息，就诚实说'我搜了一圈没找到靠谱的，建议你去官方渠道确认一下'"
        )

        # ── Build Gemini Contents with History ────────────────────────────
        history = await asyncio.to_thread(_fetch_chat_history, wecom_user_id, uid, 10)
        
        gemini_contents = []
        last_role = None
        for msg in history:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            if not text:
                continue
            # Gemini requires alternating user/model roles
            # Skip consecutive same-role messages (keep the latest)
            if role == last_role:
                gemini_contents[-1] = {
                    "role": role,
                    "parts": [{"text": text}]
                }
            else:
                gemini_contents.append({
                    "role": role,
                    "parts": [{"text": text}]
                })
                last_role = role
            
        # Add current message - ensure no consecutive user roles
        if gemini_contents and gemini_contents[-1]["role"] == "user":
            gemini_contents.pop()  # Remove last user msg to avoid duplicate role
        
        # Gemini requires first message to be 'user' role
        while gemini_contents and gemini_contents[0]["role"] != "user":
            gemini_contents.pop(0)
            
        current_parts = []
        if inline_data:
            current_parts.append({"inlineData": inline_data})
        current_parts.append({"text": prompt})
        
        gemini_contents.append({
            "role": "user",
            "parts": current_parts
        })

        # ── Call Gemini ───────────────────────────────────────────────────
        # For Gemini 2.5 Flash (thinking model), maxOutputTokens includes
        # BOTH thinking tokens AND response tokens. We need:
        #   - Low thinking budget (casual chat, not complex reasoning)
        #   - Enough total tokens for thinking + full reply
        result = await asyncio.to_thread(
            _gemini_generate, 
            prompt=None, # use contents_obj instead
            temperature=0.7, 
            max_tokens=1024, 
            response_json=False,
            thinking_budget=128,
            contents_obj=gemini_contents,
            system_instruction=context_str,
            tools=[{"google_search": {}}]
        )
        reply_text = result.get("text", "我刚跑了个间歇，喘不上气，等我缓缓再说 🫠").strip()
        # Strip any markdown bold markers
        reply_text = reply_text.replace("**", "")

        # Save bot reply to history
        asyncio.create_task(asyncio.to_thread(
            _save_chat_message, wecom_user_id, uid, "model", reply_text
        ))

        # ── Safety truncation (WeCom text limit is 2048 bytes) ─────────────
        MAX_BYTES = 2000  # Leave margin below 2048
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
_bot_loop_ref = None  # Reference to the asyncio event loop the bot runs on
_last_chatid = None   # Auto-captured from last incoming message


def send_bonnie_message(chatid: str, content: str) -> bool:
    """Thread-safe function to send a message as Bonnie via the AI Bot SDK.
    
    Can be called from any thread (including daemon threads).
    Returns True on success, False on failure.
    """
    global _bot_client, _bot_loop_ref
    if not _bot_client or not _bot_loop_ref or not chatid:
        return False
    try:
        if not _bot_client.is_connected:
            print("[wecom_bot] send_bonnie_message: bot not connected")
            return False
        
        from wecom_aibot_sdk.types.message import SendMarkdownMsgBody
        body = SendMarkdownMsgBody(markdown={"content": content})
        future = asyncio.run_coroutine_threadsafe(
            _bot_client.send_message(chatid, body), _bot_loop_ref
        )
        future.result(timeout=15)
        return True
    except Exception as e:
        print(f"[wecom_bot] send_bonnie_message failed: {e}")
        return False


async def _bot_loop():
    """Main bot loop — runs as a background asyncio task in FastAPI's event loop."""
    global _bot_client, _bot_loop_ref
    _bot_loop_ref = asyncio.get_running_loop()
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
        print(f"[wecom_bot] >>> Text Message from={frame.body.get('from')}")
        try:
            await _process_chat_message(frame, client, msgtype="text")
        except Exception as e:
            print(f"[wecom_bot] Error in text handler: {e}")
            import traceback
            traceback.print_exc()
            
    async def on_image(frame):
        print(f"[wecom_bot] >>> Image Message from={frame.body.get('from')}")
        try:
            await _process_chat_message(frame, client, msgtype="image")
        except Exception as e:
            print(f"[wecom_bot] Error in image handler: {e}")
            
    async def on_mixed(frame):
        print(f"[wecom_bot] >>> Mixed Message from={frame.body.get('from')}")
        try:
            await _process_chat_message(frame, client, msgtype="mixed")
        except Exception as e:
            print(f"[wecom_bot] Error in mixed handler: {e}")

    client.on("message.text", on_text)
    client.on("message.image", on_image)
    client.on("message.mixed", on_mixed)
    print("[wecom_bot] Handlers registered.")

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

