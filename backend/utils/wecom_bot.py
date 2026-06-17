"""
WeCom Bot — Passive Message Listener & Active Replier

Receives group messages via the WeCom callback API (see routers/wecom_callback.py),
decides whether Bonnie should reply, and sends replies via the WeCom Application
Message API (or webhook fallback).

Capabilities:
  - Personal data queries (individual running stats, recent activities)
  - Team/group leaderboard queries (monthly & weekly rankings)
  - AI coaching responses via Gemini (reuses coach.py)
  - User identity binding (WeCom UserId → RGM uid)
  - Passive keyword/intent-based "chime-in" for group chats
"""

import os
import asyncio
import logging
import time
import random
import threading
from datetime import datetime
import requests
from firebase_config import db
from routers.coach import _gemini_generate, _fetch_recent_activities, _build_runs_str, _fetch_leaderboard

try:
    from wecom_aibot_sdk import WSClient, generate_req_id
except ImportError:
    WSClient = None
    generate_req_id = None

logger = logging.getLogger("wecom_bot")

_client = None
_bot_task = None

# Pending image context: when a user @Bonnie asking about an image but hasn't
# sent it yet (common on mobile), we store the context here so the Callback API
# can associate a standalone image with the pending request.
# Structure: {sender_id: {"text": str, "timestamp": float, "reply_func": fn|None, "frame": frame|None}}
_pending_image_context = {}
_PENDING_IMAGE_TIMEOUT = 120  # seconds

_IMAGE_INTENT_KEYWORDS = [
    "看图", "看看图", "图片", "截图", "看看这个", "看看这张", "看这个", "看这张",
    "帮我看", "帮我分析", "分析一下", "发给你", "发你", "给你看", "发图",
    "识别", "ocr", "看看我的", "看看他的", "看下", "看一下",
]

def _set_pending_image_context(sender_id: str, text: str, reply_func=None, frame=None):
    """Store pending image context for a user."""
    _pending_image_context[sender_id] = {
        "text": text,
        "timestamp": time.time(),
        "reply_func": reply_func,
        "frame": frame,
    }
    logger.info(f"[wecom_bot] Stored pending image context for {sender_id!r}: {text[:50]!r}")

def _consume_pending_image_context(sender_id: str):
    """Consume and return pending image context if not expired."""
    ctx = _pending_image_context.pop(sender_id, None)
    if ctx and (time.time() - ctx["timestamp"]) < _PENDING_IMAGE_TIMEOUT:
        logger.info(f"[wecom_bot] Consumed pending image context for {sender_id!r}")
        return ctx
    return None

def _has_image_intent(content: str) -> bool:
    """Check if the user's text implies they want to send/discuss an image."""
    c = content.lower()
    return any(kw in c for kw in _IMAGE_INTENT_KEYWORDS)

# ── User identity mapping ────────────────────────────────────────────────────

def _resolve_user_by_wecom_id(wecom_user_id: str):
    """
    Find the RGM user by their wecom_user_id.
    Returns (uid, user_data) or (None, None).
    
    Auto-rebind fallback: if lookup fails, tries to match by WeCom
    contact name → RGM display_name/strava_name for users with
    stale empty wecom_user_id (left by the previous sender bug).
    """
    if not wecom_user_id:
        return None, None

    docs = (db.collection("users")
              .where("wecom_user_id", "==", wecom_user_id)
              .limit(1)
              .stream())
    for doc in docs:
        return doc.id, doc.to_dict()

    # ── Auto-rebind fallback ──────────────────────────────────────────
    # Try to resolve WeCom user's real name via WeCom Contact API,
    # then match it against RGM users with empty/missing wecom_user_id.
    try:
        wecom_names = _get_wecom_user_names(wecom_user_id)
        if wecom_names:
            wecom_names_lower = [n.lower() for n in wecom_names]
            # Scan users with empty or missing wecom_user_id
            all_users = db.collection("users").stream()
            for doc in all_users:
                d = doc.to_dict()
                existing_wid = d.get("wecom_user_id", "")
                if existing_wid and existing_wid != "":
                    continue  # Already bound to someone else
                # Collect all RGM name variants for this user
                rgm_names = set()
                for field in ("display_name", "strava_name", "email"):
                    val = d.get(field, "") or ""
                    if val:
                        rgm_names.add(val.lower())
                        # Also add first-name token (e.g. "Vivian" from "Vivian CHEN")
                        first = val.split()[0].lower()
                        if len(first) > 1:
                            rgm_names.add(first)
                        # Add email prefix (e.g. "vivian" from "vivian@example.com")
                        if "@" in val:
                            rgm_names.add(val.split("@")[0].lower())
                if not rgm_names:
                    continue
                # Bidirectional matching: WeCom name ↔ RGM name
                matched = False
                for wn in wecom_names_lower:
                    for rn in rgm_names:
                        if wn == rn or wn in rn or rn in wn:
                            matched = True
                            break
                    if matched:
                        break
                if matched:
                    db.collection("users").document(doc.id).set(
                        {"wecom_user_id": wecom_user_id}, merge=True
                    )
                    matched_wn = next(n for n in wecom_names if n.lower() in str(rgm_names))
                    print(f"[wecom_bot] Auto-rebound '{matched_wn}' → uid={doc.id} (wecom_id={wecom_user_id})")
                    return doc.id, d
    except Exception as e:
        print(f"[wecom_bot] Auto-rebind fallback failed: {e}")

    return None, None


def _get_wecom_user_names(wecom_user_id: str) -> list:
    """Fetch all name variants for a WeCom user (name + alias) via Contact API.
    
    WeCom users have:
    - name: admin-set or real-name-verified name (e.g. 陈晓韵)
    - alias: user-set display alias (e.g. Vivian CHEN)
    Both are useful for matching against RGM accounts.
    """
    names = []
    try:
        token = _get_wecom_access_token()
        if not token:
            return names
        resp = requests.get(
            "https://qyapi.weixin.qq.com/cgi-bin/user/get",
            params={"access_token": token, "userid": wecom_user_id},
            timeout=5,
        )
        if resp.ok:
            data = resp.json()
            if data.get("errcode", 0) == 0:
                name = data.get("name", "")
                alias = data.get("alias", "")
                if name:
                    names.append(name)
                if alias and alias != name:
                    names.append(alias)
    except Exception as e:
        from utils.discord import clean_err
        print(f"[wecom_bot] WeCom contact API error: {clean_err(e)}")
    return names


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
    if not wecom_user_id:
        print("[wecom_bot] _bind_user called with empty wecom_user_id, rejecting")
        return None
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


def _download_wecom_media(media_id: str) -> dict:
    """Download media from WeCom and return Gemini-compatible inlineData dict."""
    token = _get_wecom_access_token()
    if not token:
        logger.error("[wecom_bot] Cannot download media: no access token")
        return None
    url = f"https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token={token}&media_id={media_id}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.ok:
            content_type = resp.headers.get("Content-Type", "")
            if content_type.startswith("image/"):
                import base64
                mime = content_type
                b64 = base64.b64encode(resp.content).decode("utf-8")
                return {"mimeType": mime, "data": b64}
            else:
                logger.warning(f"[wecom_bot] Downloaded media content-type {content_type} is not an image")
        else:
            logger.error(f"[wecom_bot] Failed to download media: HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"[wecom_bot] Exception downloading media: {e}")
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


def _fetch_user_fitness_state(uid: str, max_hr: float = 190, rest_hr: float = 60) -> dict:
    """Fetch recent activities and compute CTL/ATL/TSB."""
    try:
        from utils.sports_science import compute_fitness_fatigue_timeseries
        user_ref = db.collection("users").document(uid)
        fitness_docs = (
            user_ref.collection("activities")
            .order_by("start_date_local", direction="DESCENDING")
            .limit(90)
            .stream()
        )
        fitness_activities = [d.to_dict() for d in fitness_docs]
        fitness_activities.reverse()  # Chronological order for timeseries
        ts = compute_fitness_fatigue_timeseries(fitness_activities, max_hr, rest_hr, days=3)
        if ts:
            latest = ts[-1]
            return {
                "ctl": round(latest.get("ctl", 0), 1),
                "atl": round(latest.get("atl", 0), 1),
                "tsb": round(latest.get("tsb", 0), 1)
            }
    except Exception as e:
        print(f"[wecom_bot] Failed to compute fitness state for {uid}: {e}")
    return {}



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

async def _generate_reply(content: str, wecom_user_id: str, chatid: str, reply_func=None, inline_data=None):
    """Core logic to process incoming text and generate a response."""
    quoted_text = ''
    media_type = 'text' if not inline_data else 'image'
    
    async def _send_msg(msg: str):
        if reply_func:
            await reply_func(msg)
        else:
            await asyncio.to_thread(send_bonnie_message, chatid, msg)



    try:
        # Strip @BotName mentions from the beginning (WeCom includes @mention in text)
        import re
        content = re.sub(r'^@\S+\s*', '', content).strip()

        # ── Bind command ──────────────────────────────────────────────────
        if content.startswith("绑定 ") or content.startswith("绑定"):
            bind_code = content.replace("绑定", "").strip()
            if not bind_code:
                await _send_msg("请输入你的 RGM 注册邮箱或昵称来绑定，格式：\n**绑定 你的名字**")
                return
            print(f"[wecom_bot] Bind attempt: wecom_user_id={wecom_user_id!r}, bind_code={bind_code!r}")
            name = _bind_user(wecom_user_id, bind_code)
            if name:
                await _send_msg(f"✅ 绑定成功！你好，{name}。现在我可以查询你的跑步数据了 🎉")
            elif not wecom_user_id:
                await _send_msg("❌ 绑定失败：系统无法识别你的企微身份（user_id 为空）。请联系管理员检查 Bot 配置。")
            else:
                await _send_msg(f"❌ 绑定失败，没找到 \"{bind_code}\"。试试用 RGM 里的昵称、Strava 名或注册邮箱？")
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
        if not inline_data:
            if intent == "leaderboard_monthly":
                entries = await asyncio.to_thread(_fetch_monthly_leaderboard, 10)
                md = _format_leaderboard_markdown(entries, "📊 本月跑量排行榜")
                await _send_msg(md)
                return

            if intent == "leaderboard_weekly":
                entries = await asyncio.to_thread(_fetch_weekly_leaderboard, 10)
                md = _format_leaderboard_markdown(entries, "📊 本周跑量排行榜")
                await _send_msg(md)
                return

        # ── Build AI context ──────────────────────────────────────────────
        runner_name = user_data.get("display_name", "跑者") if user_data else "跑者"
        gender_val = user_data.get("gender", "") if user_data else ""
        gender_str = "女" if gender_val == "female" else ("男" if gender_val == "未知" else "未知")
        if gender_val == "male":
            gender_str = "男"
        
        context_str = (
            "你是 RGM 跑团的群聊吉祥物，外号「团宠」。\n"
            "你的性格特点：\n"
            "- 热爱跑步，但更热爱在群里搞气氛\n"
            "- 说话风格：接地气、诙谐幽默、偶尔毒舌但不伤人，像跑团里那个最会活跃气氛的老油条\n"
            "- 喜欢用夸张的比喻和跑圈黑话来调侃和鼓励队友\n"
            "- 会适时制造竞争氛围（善意的激将法），比如'再不跑，排名要被xxx踩到脚底了哦'\n"
            "- 虽然嘴上不饶人，但内心温暖，真正需要鼓励的时候会认真说\n"
            "- 绝对不是那种端着架子的正经教练，而是跑团里最会来事的那个人\n"
            "- 如果用户问起自己的体能状态、累不累，或者你看到他们疲劳度 ATL 很高，或者 TSB 很低（为负数），可以用幽默诙谐或调侃关心的语气去说（例如：'瞧你这 TSB 都负成啥样了，今天就别卷了，赶紧洗洗睡吧'；'CTL 涨得挺猛啊，体能见长！'）\n"
            "\n"
            "重要：你和自动推送通知里的'AI教练'是不同的角色。\n"
            "AI教练负责专业分析和训练建议（严肃、有数据），你负责群里互动和气氛（轻松、好玩）。\n"
            "\n"
            f"正在和你聊天的人是：{runner_name} (性别: {gender_str})。\n"
        )

        if uid:
            # Personal fitness stats (CTL, ATL, TSB)
            max_hr = user_data.get("max_heart_rate", 190)
            rest_hr = user_data.get("resting_heart_rate", 60)
            fit = await asyncio.to_thread(_fetch_user_fitness_state, uid, max_hr, rest_hr)
            if fit:
                context_str += (
                    f"- 当前体能指标：CTL(体能/训练负荷)={fit.get('ctl', 0)}, "
                    f"ATL(疲劳度)={fit.get('atl', 0)}, "
                    f"TSB(状态值/就绪度)={fit.get('tsb', 0)}\n"
                    f"  (TSB说明: >5代表恢复状态好，适合拉强或拉量；在-10到5代表适应期/正常负荷；小于-10代表处于疲劳状态需要注意恢复休息)\n"
                )

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
                    
                # Include next month's target if available
                next_month = (current_month + 1) % 12
                next_month_display = datetime.now().month % 12 + 1
                if len(monthly_targets) > next_month and monthly_targets[next_month] > 0:
                    context_str += f"- 下个月({next_month_display}月)计划: 目标 {monthly_targets[next_month]}km\n"
            else:
                context_str += "- 该用户还没有设跑量目标\n"

            # Recent activities
            acts = await asyncio.to_thread(_fetch_recent_activities, uid, 5)
            if acts:
                context_str += f"- 最近活动: {_build_runs_str(acts)}\n"

            # Additional Profile Data
            profile_stats = []
            if user_data.get("height_cm"):
                profile_stats.append(f"身高: {user_data['height_cm']}cm")
            if user_data.get("weight_kg"):
                profile_stats.append(f"体重: {user_data['weight_kg']}kg")
            if user_data.get("years_running"):
                profile_stats.append(f"跑龄: {user_data['years_running']}年")
            if profile_stats:
                context_str += f"- 身体数据: {', '.join(profile_stats)}\n"

            # PBs
            pbs = []
            if user_data.get("marathon_pb_sec"):
                pb = user_data["marathon_pb_sec"]
                h, r = divmod(pb, 3600); m = r // 60
                pbs.append(f"全马 {h}:{m:02d}")
            if user_data.get("half_pb_sec"):
                pb = user_data["half_pb_sec"]
                h, r = divmod(pb, 3600); m, s = divmod(r, 60)
                pbs.append(f"半马 {h}:{m:02d}:{s:02d}")
            if user_data.get("ten_k_pb_sec"):
                pb = user_data["ten_k_pb_sec"]
                m, s = divmod(pb, 60)
                pbs.append(f"10K {m:02d}:{s:02d}")
            if user_data.get("five_k_pb_sec"):
                pb = user_data["five_k_pb_sec"]
                m, s = divmod(pb, 60)
                pbs.append(f"5K {m:02d}:{s:02d}")
            if pbs:
                context_str += f"- 个人PB: {', '.join(pbs)}\n"

            # Team leaderboard context (so AI can reference rankings)
            if intent in ("my_stats", "my_activity", "general"):
                from datetime import datetime
                now = datetime.now()
                
                # Check if user is asking about yearly stats
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
        history = await asyncio.to_thread(_fetch_chat_history, wecom_user_id, uid, 10)
        mentioned_users = await asyncio.to_thread(_find_mentioned_users, combined_text)
        mentioned_users = [(m_uid, m_data) for m_uid, m_data in mentioned_users if m_uid != uid]
        
        # If no user mentioned in current message, resolve context user from history
        if not mentioned_users:
            for msg in reversed(history):
                h_content = msg.get("content", "")
                if h_content:
                    h_mentions = _find_mentioned_users(h_content)
                    h_mentions = [(m_uid, m_data) for m_uid, m_data in h_mentions if m_uid != uid]
                    if h_mentions:
                        mentioned_users = h_mentions
                        print(f"[wecom_bot] Resolved context user from history: {[m[1].get('display_name') for m in mentioned_users]}")
                        break
        
        if mentioned_users:
            context_str += "\n【聊天中提到其他成员的数据，可供参考】：\n"
            for m_uid, m_data in mentioned_users:
                m_name = m_data.get("display_name", m_data.get("strava_name", "某队员"))
                m_gender_val = m_data.get("gender", "")
                m_gender_str = "女" if m_gender_val == "female" else ("男" if m_gender_val == "male" else "未知")
                context_str += f"队员 [{m_name}] (性别: {m_gender_str}):\n"

                # Mentioned User Profile Data
                m_profile_stats = []
                if m_data.get("height_cm"):
                    m_profile_stats.append(f"身高 {m_data['height_cm']}cm")
                if m_data.get("weight_kg"):
                    m_profile_stats.append(f"体重 {m_data['weight_kg']}kg")
                if m_data.get("years_running"):
                    m_profile_stats.append(f"跑龄 {m_data['years_running']}年")
                if m_profile_stats:
                    context_str += f"  - 身体数据: {', '.join(m_profile_stats)}\n"
                
                # Mentioned User PBs
                m_pbs = []
                if m_data.get("marathon_pb_sec"):
                    pb = m_data["marathon_pb_sec"]
                    h, r = divmod(pb, 3600); m = r // 60
                    m_pbs.append(f"全马 {h}:{m:02d}")
                if m_data.get("half_pb_sec"):
                    pb = m_data["half_pb_sec"]
                    h, r = divmod(pb, 3600); m, s = divmod(r, 60)
                    m_pbs.append(f"半马 {h}:{m:02d}:{s:02d}")
                if m_data.get("ten_k_pb_sec"):
                    pb = m_data["ten_k_pb_sec"]
                    m, s = divmod(pb, 60)
                    m_pbs.append(f"10K {m:02d}:{s:02d}")
                if m_data.get("five_k_pb_sec"):
                    pb = m_data["five_k_pb_sec"]
                    m, s = divmod(pb, 60)
                    m_pbs.append(f"5K {m:02d}:{s:02d}")
                if m_pbs:
                    context_str += f"  - PB成绩: {', '.join(m_pbs)}\n"
                
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

                # Recent activities for this member
                m_acts = await asyncio.to_thread(_fetch_recent_activities, m_uid, 5)
                if m_acts:
                    context_str += f"  - 最近活动: {_build_runs_str(m_acts)}\n"

        # Build conversation context for AI prompt
        quoted_context = ""
        if quoted_text:
            quoted_context = f"【用户引用了之前的消息】：\n\"{quoted_text}\"\n\n"

        prompt_reqs = [
            "- 字数控制：如果是闲聊或调侃，控制在80-150个中文字以内；如果是回答跑步知识、赛事信息或长篇科普，请详尽完整地回答，字数不限，务必把话说清楚",
            "- 语言风格：诙谐、接地气、毒舌但好玩，像跑团里最会搞气氛的老油条",
            "- 如果用户发送了图片，请结合图片内容进行调侃或鼓励",
            "- 如果用户问跑量/数据：先回答数据再调侃，数据要完整别说一半",
            "- 如果用户只是闲聊（比如求鸡汤、打招呼）：直接按人设发挥，不用强行报数据",
            "- 用1-2个emoji",
            "- 纯文本，不要用markdown格式如**加粗**",
            "- 如果用户心情低落或受伤，收起嬉皮，认真关心",
            "- 严禁编造数据！如果上面没有提供相关数据，就说'这个数据我还没收到，让我查查去'",
            "- 如果用户问赛事、天气、新闻等实时信息，你必须基于搜索结果回答，给出具体的日期、地点和报名链接等详尽信息。如果搜索不到可靠信息，就诚实说'我搜了一圈没找到靠谱的，建议你去官方渠道确认一下'"
        ]
        if inline_data:
            prompt_reqs.append("- 用户提供了一张图片/文件。你需要对该图片/文件进行OCR与识别。如果是训练计划、课表、跑步记录截图等，请识别其中的距离、配速、时间、训练日期和动作等关键数据，为用户进行细致的解读和点评（必要时进行毒舌调侃）。")

        reqs_str = "\n".join(prompt_reqs)
        prompt = (
            f"{context_str}\n\n"
            f"{quoted_context}"
            f"用户当前的输入是：{content}\n\n"
            f"请用你的'团宠'人设回复。要求：\n"
            f"{reqs_str}"
        )

        # ── Build Gemini Contents with History ────────────────────────────
        # history is already fetched early
        
        
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
        result = await asyncio.to_thread(
            _gemini_generate, 
            prompt=None, # use contents_obj instead
            temperature=0.7, 
            max_tokens=2048, 
            response_json=False,
            thinking_budget=256,
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

        # ── Safety truncation (WeCom WS stream limit is 20480 bytes) ────────
        MAX_BYTES = 20000  # Leave margin below 20480
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

        # ── Send reply ───────────────────────────────────────────        # 3) Dispatch to WeCom API
        await _send_msg(reply_text)
        
    except Exception as e:
        print(f"[wecom_bot] Error generating reply: {e}")
        import traceback
        traceback.print_exc()
        try:
            await _send_msg("💀 不好意思，我刚撞墙了…脑子暂时转不动，等我补个胶再来！")
        except Exception:
            pass

# ── Bot lifecycle ─────────────────────────────────────────────────────────────

_token_cache = {"access_token": None, "expires_at": 0}
_token_lock = threading.Lock()

def _get_wecom_access_token():
    corpid = os.getenv("WECOM_CORP_ID")
    corpsecret = os.getenv("WECOM_CALLBACK_SECRET")
    if not corpid or not corpsecret:
        return None
        
    with _token_lock:
        if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
            return _token_cache["access_token"]
            
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corpid}&corpsecret={corpsecret}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.ok:
                data = resp.json()
                if data.get("errcode") == 0:
                    _token_cache["access_token"] = data["access_token"]
                    _token_cache["expires_at"] = time.time() + data["expires_in"] - 60
                    return _token_cache["access_token"]
        except Exception:
            pass
    return None

def send_bonnie_message(chatid: str, content: str) -> bool:
    """Send a message via WeCom Application Message API.
    Used as fallback when the WS SDK reply_func is not available (Callback API path).
    Requires WECOM_CORP_ID + WECOM_CALLBACK_SECRET for access token.
    """
    token = _get_wecom_access_token()
    if not token:
        print("[wecom_bot] Cannot send message: no access token (WECOM_CORP_ID/WECOM_CALLBACK_SECRET not set)")
        return False
        
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    payload = {
        "touser": chatid,
        "msgtype": "markdown",
        "agentid": int(os.getenv("WECOM_AGENT_ID", "1000002")),
        "markdown": {
            "content": content
        }
    }
    resp = requests.post(url, json=payload)
    return resp.ok and resp.json().get("errcode") == 0

def handle_wecom_message(msg_data: dict):
    """Entry point for incoming messages from WeCom Callback API."""
    print(f"[wecom_bot] ▶ handle_wecom_message called with keys: {list(msg_data.keys())}")
    msg_type = msg_data.get("MsgType", "")
    print(f"[wecom_bot]   MsgType={msg_type}")
    if msg_type not in ["text", "image", "file"]:
        print(f"[wecom_bot]   ✗ Skipping non-text/image/file message (MsgType={msg_type})")
        return
        
    content = ""
    inline_data = None
    
    if msg_type == "text":
        content = msg_data.get("Content", "").strip()
    elif msg_type == "image":
        media_id = msg_data.get("MediaId", "")
        print(f"[wecom_bot]   Downloading Callback image MediaId={media_id}")
        inline_data = _download_wecom_media(media_id) if media_id else None
        content = "请帮我看看这张图片"
    elif msg_type == "file":
        filename = msg_data.get("Title", "") or msg_data.get("FileName", "") or ""
        media_id = msg_data.get("MediaId", "")
        suffix = filename.split(".")[-1].lower() if "." in filename else ""
        if suffix in ["jpg", "jpeg", "png", "webp", "gif"]:
            print(f"[wecom_bot]   Downloading Callback image file {filename} MediaId={media_id}")
            inline_data = _download_wecom_media(media_id) if media_id else None
            content = f"请帮我看看这个文件：{filename}"
        else:
            from_user = msg_data.get("FromUserName", "")
            if from_user:
                asyncio.run(asyncio.to_thread(
                    send_bonnie_message, 
                    from_user, 
                    "不好意思，我目前只能识别图片或者图片格式的文件（如 .jpg, .png）。如果是其他类型文件，我暂时还看不懂哦~"
                ))
            return

    from_user = msg_data.get("FromUserName", "")
    chatid = from_user # Default reply to user
    print(f"[wecom_bot]   Content={content[:80]!r}, FromUser={from_user}, has_inline_data={inline_data is not None}")
    
    # For standalone image/file messages, check pending image context first
    if msg_type in ["image", "file"] and inline_data:
        pending_ctx = _consume_pending_image_context(from_user)
        if pending_ctx:
            # Merge: use the original question text from the @Bonnie message
            content = pending_ctx["text"]
            print(f"[wecom_bot]   ★ Merged with pending context: {content[:60]!r}")
        should_reply = True
    elif msg_type in ["image", "file"]:
        should_reply = True
    else:
        # Check if we should reply (sliding window logic)
        keywords = ["受伤", "PB", "偷懒", "装备", "鞋", "跑", "bonnie", "团宠", "配速", "课表", "绑定", "我是谁"]
        content_lower = content.lower()
        matched_keywords = [k for k in keywords if k in content_lower]
        should_reply = bool(matched_keywords) or random.random() < 0.1 # 10% chance
        print(f"[wecom_bot]   matched_keywords={matched_keywords}, should_reply={should_reply}")
    
    if should_reply:
        # Use asyncio to run the async generate_reply in background
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        
        print(f"[wecom_bot]   loop={'running' if loop and loop.is_running() else 'none'}")
        try:
            if loop and loop.is_running():
                loop.create_task(_generate_reply(content, from_user, chatid, inline_data=inline_data))
            else:
                asyncio.run(_generate_reply(content, from_user, chatid, inline_data=inline_data))
            print(f"[wecom_bot]   ✓ _generate_reply dispatched")
        except Exception as e:
            print(f"[wecom_bot]   ✗ Failed to dispatch _generate_reply: {e}")
    else:
        print(f"[wecom_bot]   ✗ Not replying (no keyword match, random miss)")


# ── WS SDK Bot lifecycle ──────────────────────────────────────────────────────

async def _bot_main_loop():
    global _client
    bot_id = os.getenv("WECOM_BOT_ID", "").strip()
    secret = os.getenv("WECOM_BOT_SECRET", "").strip()

    if not bot_id or not secret:
        logger.info("[wecom_bot] WECOM_BOT_ID or WECOM_BOT_SECRET not set. WS Bot is disabled.")
        return

    if not WSClient:
        logger.error("[wecom_bot] wecom_aibot_sdk not installed. WS Bot cannot start.")
        return

    logger.info(f"[wecom_bot] Initializing WS bot {bot_id}...")
    _client = WSClient({
        "bot_id": bot_id,
        "secret": secret,
    })

    async def on_text(frame):
        try:
            content = frame.body.get("text", {}).get("content", "").strip()
            sender = frame.body.get("from", {}).get("userid", "")
            chattype = frame.body.get("chattype", "single")
            logger.info(f"[wecom_bot] WS Received text from sender={sender!r}, chattype={chattype}, content={content[:60]!r}")
            
            import re
            clean_content = re.sub(r'@\S+\s*', '', content).strip()
            
            if chattype == "group":
                should_reply = True
            else:
                keywords = ["受伤", "PB", "偷懒", "装备", "鞋", "跑", "bonnie", "团宠", "配速", "课表", "绑定", "我是谁"]
                content_lower = clean_content.lower()
                matched_keywords = [k for k in keywords if k in content_lower]
                should_reply = bool(matched_keywords) or random.random() < 0.1
            
            if should_reply:
                async def ws_reply(text):
                    stream_id = generate_req_id("stream")
                    await _client.reply_stream(frame, stream_id, text, finish=True)
                
                if chattype == "group" and _has_image_intent(clean_content) and not frame.body.get("image"):
                    await ws_reply(
                        "📸 想让我看图片？请在电脑端操作：\n"
                        "先粘贴/拖入图片到输入框，再输入 @Bonnie + 你的问题，一起发送就行啦～\n\n"
                        "⚠️ 手机端暂时无法把图片和文字放在同一条消息里，所以需要切换到电脑端发送哦"
                    )
                    logger.info(f"[wecom_bot] Image intent detected, sent guidance for {sender!r}")
                    return
                
                logger.info("[wecom_bot] Dispatching _generate_reply via WS")
                asyncio.create_task(_generate_reply(content, sender, sender, reply_func=ws_reply))
            else:
                logger.info("[wecom_bot] WS Not replying (no keyword match)")
        except Exception as e:
            logger.error(f"[wecom_bot] on_text handler error: {e}", exc_info=True)

    async def on_image(frame):
        sender = frame.body.get("from", {}).get("userid", "")
        image_info = frame.body.get("image", {})
        img_url = image_info.get("url", "")
        aes_key = image_info.get("aeskey", "") or image_info.get("aes_key", "")
        
        logger.info(f"[wecom_bot] WS Received image from sender={sender!r}, url={img_url!r}")
        if not img_url:
            return
            
        try:
            buf, filename = await _client.download_file(img_url, aes_key)
            import base64
            b64 = base64.b64encode(buf).decode("utf-8")
            inline_data = {"mimeType": "image/jpeg", "data": b64}
            
            content = "请帮我看看这张图片"
            async def ws_reply(text):
                stream_id = generate_req_id("stream")
                await _client.reply_stream(frame, stream_id, text, finish=True)
                
            asyncio.create_task(_generate_reply(content, sender, sender, reply_func=ws_reply, inline_data=inline_data))
        except Exception as e:
            logger.error(f"[wecom_bot] Failed to download/decrypt WS image: {e}")

    async def on_file(frame):
        sender = frame.body.get("from", {}).get("userid", "")
        file_info = frame.body.get("file", {})
        file_url = file_info.get("url", "")
        aes_key = file_info.get("aeskey", "") or file_info.get("aes_key", "")
        filename = file_info.get("name", "") or file_info.get("filename", "") or ""
        
        logger.info(f"[wecom_bot] WS Received file from sender={sender!r}, name={filename!r}, url={file_url!r}")
        if not file_url:
            return
            
        suffix = filename.split(".")[-1].lower() if "." in filename else ""
        if suffix not in ["jpg", "jpeg", "png", "webp", "gif"]:
            async def ws_reply(text):
                stream_id = generate_req_id("stream")
                await _client.reply_stream(frame, stream_id, text, finish=True)
            await ws_reply("不好意思，我目前只能识别图片或者图片格式的文件（如 .jpg, .png）。其他类型文件我暂时看不懂哦~")
            return
            
        try:
            buf, filename = await _client.download_file(file_url, aes_key)
            import base64
            mime_map = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "webp": "image/webp",
                "gif": "image/gif"
            }
            mime = mime_map.get(suffix, "image/jpeg")
            b64 = base64.b64encode(buf).decode("utf-8")
            inline_data = {"mimeType": mime, "data": b64}
            
            content = f"请帮我看看这个文件：{filename}"
            async def ws_reply(text):
                stream_id = generate_req_id("stream")
                await _client.reply_stream(frame, stream_id, text, finish=True)
                
            asyncio.create_task(_generate_reply(content, sender, sender, reply_func=ws_reply, inline_data=inline_data))
        except Exception as e:
            logger.error(f"[wecom_bot] Failed to download/decrypt WS file: {e}")

    async def on_mixed(frame):
        """Handle mixed messages (text + image combined, e.g. @Bot + image + text)."""
        try:
            sender = frame.body.get("from", {}).get("userid", "")
            mixed_info = frame.body.get("mixed", {})
            # WeCom uses "msg_item" (not "items") for mixed message items
            items = mixed_info.get("msg_item", []) or mixed_info.get("items", [])
            
            logger.info(f"[wecom_bot] WS Received mixed message from sender={sender!r}, {len(items)} items, keys={list(frame.body.keys())}")
            
            # Extract text and image from items
            text_parts = []
            inline_data = None
            for item in items:
                # WeCom uses "msgtype" (not "type") for each item's content type
                item_type = item.get("msgtype", "") or item.get("type", "")
                if item_type == "text":
                    t = item.get("text", {}).get("content", "").strip()
                    if t:
                        # Strip @BotName mentions
                        import re
                        t = re.sub(r'@\S+\s*', '', t).strip()
                        if t:
                            text_parts.append(t)
                elif item_type == "image":
                    image_data = item.get("image", {})
                    img_url = image_data.get("url", "")
                    aes_key = image_data.get("aeskey", "") or image_data.get("aes_key", "")
                    if img_url and not inline_data:
                        try:
                            buf, fname = await _client.download_file(img_url, aes_key or None)
                            import base64
                            b64 = base64.b64encode(buf).decode("utf-8")
                            inline_data = {"mimeType": "image/jpeg", "data": b64}
                            logger.info(f"[wecom_bot] WS Mixed: downloaded image {fname}, {len(buf)} bytes")
                        except Exception as e:
                            logger.error(f"[wecom_bot] Failed to download mixed image: {e}")
            
            content = " ".join(text_parts) if text_parts else "请帮我看看这张图片"
            
            if not inline_data and not text_parts:
                logger.info("[wecom_bot] WS Mixed: no actionable content, skipping")
                return
            
            async def ws_reply(text):
                stream_id = generate_req_id("stream")
                await _client.reply_stream(frame, stream_id, text, finish=True)
            
            logger.info(f"[wecom_bot] WS Mixed: dispatching reply with content={content[:60]!r}, has_image={inline_data is not None}")
            asyncio.create_task(_generate_reply(content, sender, sender, reply_func=ws_reply, inline_data=inline_data))
        except Exception as e:
            logger.error(f"[wecom_bot] on_mixed handler error: {e}", exc_info=True)

    async def on_any_message(frame):
        """Catch-all logger. Only processes unknown message types as fallback."""
        body = frame.body if hasattr(frame, 'body') else {}
        if not isinstance(body, dict):
            return
        msgtype = body.get("msgtype", "unknown")
        sender = body.get("from", {}).get("userid", "") if isinstance(body.get("from"), dict) else ""
        body_keys = list(body.keys())
        logger.info(f"[wecom_bot] WS ★ ANY message: msgtype={msgtype!r}, sender={sender!r}, body_keys={body_keys}")

        # Known types have dedicated handlers — don't double-process
        known_types = {"text", "image", "file", "mixed"}
        if msgtype in known_types:
            return

        # Unknown message type — try to extract image as fallback
        if sender:
            import base64, json
            inline_data = None
            text_parts = []

            # Scan all dict values for image-like data with "url" field
            for key, val in body.items():
                if isinstance(val, dict) and val.get("url") and not inline_data:
                    try:
                        buf, fname = await _client.download_file(val["url"], val.get("aeskey") or val.get("aes_key") or None)
                        inline_data = {"mimeType": "image/jpeg", "data": base64.b64encode(buf).decode("utf-8")}
                        logger.info(f"[wecom_bot] WS fallback: downloaded from key={key!r}, {len(buf)} bytes")
                    except Exception as e:
                        logger.error(f"[wecom_bot] WS fallback: failed download from key={key!r}: {e}")

            content = "请帮我看看这张图片"
            if inline_data:
                async def ws_reply(text):
                    stream_id = generate_req_id("stream")
                    await _client.reply_stream(frame, stream_id, text, finish=True)
                asyncio.create_task(_generate_reply(content, sender, sender, reply_func=ws_reply, inline_data=inline_data))
            else:
                logger.warning(f"[wecom_bot] WS fallback: unknown msgtype={msgtype!r}, no image found. body_keys={body_keys}")

    _client.on("message", on_any_message)
    _client.on("message.text", on_text)
    _client.on("message.image", on_image)
    _client.on("message.file", on_file)
    _client.on("message.mixed", on_mixed)

    # Connect and keep alive with auto-reconnect
    while True:
        try:
            logger.info("[wecom_bot] Connecting to WeCom WebSocket...")
            await _client.connect_async()

            while _client.is_connected:
                await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info("[wecom_bot] Bot task cancelled.")
            break
        except Exception as e:
            logger.error(f"[wecom_bot] Connection error: {e}")
            await asyncio.sleep(5)


def start_wecom_bot():
    """Start the WeCom bot background task if not already running."""
    global _bot_task
    if _bot_task is None or _bot_task.done():
        bot_id = os.getenv("WECOM_BOT_ID", "").strip()
        secret = os.getenv("WECOM_BOT_SECRET", "").strip()
        if bot_id and secret:
            try:
                loop = asyncio.get_running_loop()
                _bot_task = loop.create_task(_bot_main_loop())
                logger.info("[wecom_bot] WS Background task scheduled.")
            except Exception as e:
                logger.error(f"[wecom_bot] Could not schedule WS task: {e}")
        else:
            logger.info("[wecom_bot] Skipped starting WS bot: WECOM_BOT_ID/SECRET missing.")

