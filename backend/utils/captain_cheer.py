"""
Public Club Captain Cheer Generator (团长加油).

Generates warm, motivating, situation-aware encouragement messages on behalf of
a runner's club captain (`跑团团长`) across club check-in feeds, personal activity
lists, track/detail modals, and Moments share posters.

Strict privacy design:
- Open to all viewers even when `canova_critique_visibility='self'`,
  `hide_biometrics=True`, or `hide_gps_route=True`.
- Adapts tone using runner gender, age bucket, mileage, running years, and
  training/fatigue state, while NEVER exposing exact age/birth year, heart rate,
  HRV, sleep metrics, TRIMP/CTL/TSB numbers, real_name, phone, email, or id_card.
- Zero write operations and batched single-connection SQLite reads for feed speed.
"""

from datetime import date, datetime, timedelta
import hashlib
import json
import logging
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from utils.canova_holistic_critique import (
    _is_rest_day_dict,
    _is_trail_record,
    _parse_iso_date,
    _sanitize_daily_health_row,
    _shorten_race_name,
)
from utils.running_metrics import calculate_trimp, compute_ctl_atl_tsb, get_age_from_dob

logger = logging.getLogger("captain_cheer")

_FORBIDDEN_AGE_RE = re.compile(r"\d{1,3}\s*岁")
_FORBIDDEN_YEAR_RE = re.compile(r"(?:19|20)\d{2}\s*年")
_FORBIDDEN_BIO_RE = re.compile(
    r"\b(?:bpm|hrv|ctl|atl|tsb|trimp|vdot|vo2(?:max)?)\b|心率|静息|睡眠",
    re.IGNORECASE,
)


def _fmt_km_cn(km: float) -> str:
    """Formats distance cleanly in Chinese (e.g. '20公里' when near integer, else '15.6公里')."""
    if km <= 0:
        return "0公里"
    rounded = round(km)
    if abs(km - rounded) <= 0.08:
        return f"{int(rounded)}公里"
    return f"{km:.1f}公里"


def _sanitize_display_name(raw_name: Optional[str], fallback: str = "跑友") -> str:
    """Extracts a safe public nickname, never leaking full emails or internal UIDs."""
    if not raw_name:
        return fallback
    s = str(raw_name).strip()
    if not s:
        return fallback
    if "@" in s:
        s = s.split("@", 1)[0].strip()
    if not s or s.startswith(("u_", "wx_", "anon_")) or s in ("跑者", "用户", "微信用户"):
        return fallback
    return s[:16]


def _sanitize_captain_display_name(raw_name: Optional[str]) -> str:
    """Formats captain role name without duplicating '团长'."""
    nick = _sanitize_display_name(raw_name, fallback="")
    if not nick:
        return "团长"
    return nick if nick.endswith("团长") else f"{nick}团长"


def _sanitize_public_cheer(text: str) -> str:
    """Final defense-in-depth scrub preventing accidental age/biometric token leakage."""
    cleaned = _FORBIDDEN_AGE_RE.sub("", text or "")
    cleaned = _FORBIDDEN_YEAR_RE.sub("", cleaned)
    cleaned = _FORBIDDEN_BIO_RE.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _shorten_short_title(raw: Optional[str], max_len: int = 10) -> str:
    s = re.sub(r"\s*[\(（].*?[\)）]", "", str(raw or "")).strip()
    s = re.sub(r"\s+", "", s)
    if not s:
        return ""
    if len(s) > max_len:
        return s[:max_len]
    return s


def _normalize_gender_bucket(raw_gender: Optional[str]) -> str:
    g = str(raw_gender or "").strip().lower()
    if g in ("female", "f", "女", "woman"):
        return "female"
    if g in ("male", "m", "男", "man"):
        return "male"
    return "neutral"


def _normalize_age_bucket(dob_str: Optional[str]) -> str:
    age = get_age_from_dob(dob_str)
    if age is None:
        return "prime"
    if age >= 50:
        return "masters"
    if age < 30:
        return "youth"
    return "prime"


def _normalize_exp_bucket(raw_years: Any) -> str:
    try:
        y = float(raw_years) if raw_years is not None else 1.5
    except Exception:
        y = 1.5
    if y <= 1.0:
        return "newcomer"
    if y >= 5.0:
        return "veteran"
    return "steady"


def _pick_variant(seed: int, offset: int, options: List[str]) -> str:
    if not options:
        return ""
    return options[(seed + offset) % len(options)]


def _parse_scope_club_ids(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    s = str(raw).strip()
    if not s or s.lower() == "all":
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [p.strip() for p in s.split(",") if p.strip()]


def _build_captain_cheer_text(
    *,
    act: Dict[str, Any],
    act_date: Optional[date],
    runner_name: str,
    is_captain_self: bool,
    gender_bucket: str,
    age_bucket: str,
    exp_bucket: str,
    week_km: float,
    week_runs: int,
    month_km: float,
    streak_days: int,
    days_since_prev: Optional[int],
    had_prev_hard_48h: bool,
    tsb_post: float,
    overnight_low_recovery: bool,
    planned_day: Optional[Dict[str, Any]],
    matched_event: Optional[Dict[str, Any]],
    matched_race: Optional[Dict[str, Any]],
    upcoming_race: Optional[Dict[str, Any]],
    target_club_id: str,
    club_name: str,
) -> Tuple[str, str]:
    """Synthesizes deterministic, varied, encouraging public captain commentary."""
    act_id = str(act.get("id") or f"{act.get('start_time', '')}:{act.get('distance_meters', 0)}")
    seed = int(hashlib.md5(f"{act_id}:{target_club_id}".encode("utf-8")).hexdigest()[:8], 16)

    dist_km = round(float(act.get("distance_meters") or 0.0) / 1000.0, 2)
    dist_str = _fmt_km_cn(dist_km)
    elev_gain = float(
        act.get("elevation_gain_meters") or act.get("total_elevation_gain") or act.get("elevationGain") or 0.0
    )
    act_name = str(act.get("name") or "").strip()
    act_name_lower = act_name.lower()

    is_trail = _is_trail_record(act) or elev_gain >= 150.0
    is_group_kw = any(k in act_name_lower for k in ("合练", "团跑", "约跑", "例跑"))
    is_race_kw = (dist_km >= 20.5 and any(k in act_name_lower for k in ("马拉松", "比赛", "半马", "全马", "marathon")))

    # Determine state mode (without ever exposing biometric or load metrics)
    is_high_fatigue = bool(
        tsb_post <= -18.0
        or had_prev_hard_48h
        or streak_days >= 4
        or dist_km >= 18.0
        or overnight_low_recovery
    )
    days_to_race = None
    upcoming_race_short = ""
    if upcoming_race and act_date:
        r_d = _parse_iso_date(upcoming_race.get("race_date"))
        if r_d and 1 <= (r_d - act_date).days <= 14:
            days_to_race = (r_d - act_date).days
            upcoming_race_short = _shorten_race_name(upcoming_race.get("name") or "目标赛")

    state_mode = "high_fatigue" if is_high_fatigue else ("taper_countdown" if days_to_race else "fresh_momentum")

    # ── 1. Determine scenario & lead opener ──
    scenario = "daily"
    opener = ""

    if matched_race or is_race_kw:
        scenario = "race"
        race_title = _shorten_race_name((matched_race or {}).get("name") or act_name or "目标赛事", max_len=10)
        if is_captain_self:
            opener = _pick_variant(seed, 0, [
                f"顺利拿下【{race_title}】{dist_str}，以身作则带队燃爆全场！",
                f"完美完赛【{race_title}】{dist_str}，咱们【{club_name}】的荣誉勋章又添一枚！",
            ])
        else:
            opener = _pick_variant(seed, 0, [
                f"热烈祝贺{runner_name}顺利完赛【{race_title}】{dist_str}！全团都为你骄傲，{runner_name}太强了！",
                f"太燃了！恭喜{runner_name}稳稳拿下【{race_title}】{dist_str}，每一公里都是实打实的底气，加油！",
            ])
    elif matched_event or is_group_kw:
        scenario = "group_run"
        ev_title = _shorten_short_title((matched_event or {}).get("title"), max_len=9)
        ev_label = f"今天【{ev_title}】合练课程" if ev_title else "今天的合练课程"
        if is_captain_self:
            opener = _pick_variant(seed, 1, [
                f"合练涨功力！今天带领大家一起跑完{ev_label}（{dist_str}），感谢每位一起流汗的团友！",
                f"和大家并肩跑完{ev_label}，稳稳进账{dist_str}，团队一起奔跑氛围太棒了！",
            ])
        else:
            opener = _pick_variant(seed, 1, [
                f"合练涨功力！谢谢{runner_name}参加{ev_label}，稳稳进账{dist_str}，{runner_name}太赞了！",
                f"今天{ev_label}（{dist_str}）和大家一起并肩突破，合练涨功力！谢谢{runner_name}积极参与！",
                f"合练氛围拉满！谢谢{runner_name}打卡{ev_label}，顺利完成{dist_str}！",
            ])
    elif planned_day and not _is_rest_day_dict(planned_day) and float(planned_day.get("distance_km") or 0.0) >= 2.0:
        plan_km = float(planned_day.get("distance_km") or 0.0)
        plan_km_str = _fmt_km_cn(plan_km)
        plan_title = _shorten_short_title(planned_day.get("title"), max_len=8)
        ratio = dist_km / max(0.5, plan_km)
        if ratio >= 0.82:
            scenario = "plan_completed"
            if is_captain_self:
                opener = _pick_variant(seed, 2, [
                    f"顺利拿下今天的课表{plan_km_str}，自己先带头打卡表率，大家一起加油！",
                    f"今天的课表{plan_km_str}准时交卷，跟全团伙伴并肩进步！",
                ])
            else:
                opener = _pick_variant(seed, 2, [
                    f"太强了，完成了今天的课表{plan_km_str}，{runner_name}加油！",
                    f"执行力满分！{runner_name}稳稳拿下了今天的课表{plan_km_str}{f'（{plan_title}）' if plan_title else ''}，继续加油！",
                    f"今天{plan_km_str}的课表{runner_name}完美兑现，节奏拿捏得很稳，{runner_name}加油！",
                ])
        else:
            scenario = "plan_adjusted"
            if is_captain_self:
                opener = f"今天稳稳跑完{dist_str}，顺应体感灵活微调课表节奏，健康持久奔跑最重要！"
            else:
                opener = _pick_variant(seed, 2, [
                    f"很棒！{runner_name}今天扎实跑完{dist_str}，能倾听身体体感灵活调整课表，这份自律和清醒太难得了，加油！",
                    f"为你点赞，{runner_name}完成{dist_str}！懂得结合当下状态把控课表节奏才是长跑高手，{runner_name}继续加油！",
                ])
    elif is_trail:
        scenario = "trail"
        elev_int = int(round(elev_gain))
        elev_desc = f"（累计爬升+{elev_int}米）" if elev_int >= 50 else ""
        if is_captain_self:
            opener = f"进山拉练{dist_str}{elev_desc}圆满打卡，爬坡磨意志，回头继续带大家浪山！"
        else:
            opener = _pick_variant(seed, 3, [
                f"野性拉满！{runner_name}在山野中稳稳拿下了{dist_str}{elev_desc}，每一步爬升都在长功力，加油！",
                f"太牛了！{runner_name}完成{dist_str}山地越野{elev_desc}，硬核腿力与毅力双在线，继续加油！",
            ])
    elif dist_km >= 16.0:
        scenario = "long_run"
        if is_captain_self:
            opener = f"周末长距离{dist_str}顺利拿下，稳步积累有氧里程，跟伙伴们一起冲！"
        else:
            opener = _pick_variant(seed, 4, [
                f"耐力大片上线！{runner_name}稳稳拿下{dist_str}长距离拉练，这份韧劲真棒，{runner_name}加油！",
                f"太给力了！{dist_str}长距离顺利交卷，有氧底盘又厚了一大截，{runner_name}真棒！",
            ])
    elif days_since_prev is not None and days_since_prev >= 6:
        scenario = "comeback"
        if is_captain_self:
            opener = f"重启跑鞋稳稳拿下{dist_str}，重新找回风驰电掣的自由节奏！"
        else:
            opener = _pick_variant(seed, 5, [
                f"欢迎{runner_name}元气回归跑道！顺利拿下{dist_str}，跑起来就赢了一半，{runner_name}加油！",
                f"好久不见的赛道身影回来啦！{runner_name}稳稳完成{dist_str}回归跑，循序渐进找回快乐节奏，加油！",
            ])
    elif streak_days >= 3:
        scenario = "streak"
        if is_captain_self:
            opener = f"连续第{streak_days}天稳稳打卡（今日{dist_str}），热爱不停步也要注意劳逸结合！"
        else:
            opener = _pick_variant(seed, 6, [
                f"这股恒心太顶了！{runner_name}连续第{streak_days}天准时打卡（今日{dist_str}），{runner_name}真稳！",
                f"连续{streak_days}天线上打卡集结，今天再收下{dist_str}！自律的{runner_name}太强了，加油！",
            ])
    else:
        scenario = "daily"
        if is_captain_self:
            opener = f"今天日常打卡{dist_str}顺利完成，继续保持好状态陪全团一起稳步奔跑！"
        else:
            opener = _pick_variant(seed, 7, [
                f"漂亮，{runner_name}今天顺利打卡{dist_str}！每次迈出脚步都在积蓄能量，{runner_name}加油！",
                f"太稳了，{runner_name}轻松完成今天{dist_str}奔跑！享受汗水与晚风，继续加油！",
                f"给{runner_name}点个大赞！今日{dist_str}稳健进账，步履不停就是最好的榜样，加油！",
            ])

    # ── 2. Persona & Mileage Clause (Gender / Age Bucket / Running Years / Volume) ──
    persona_bits: List[str] = []

    if gender_bucket == "female":
        g_phrase = _pick_variant(seed, 11, ["飒爽又充满力量", "轻盈又有韧劲", "跑姿稳健太有气质"])
    elif gender_bucket == "male":
        g_phrase = _pick_variant(seed, 12, ["稳扎稳打、执行力拉满", "节奏干脆利落、实力稳健", "踏实硬朗、越来越能打"])
    else:
        g_phrase = _pick_variant(seed, 13, ["状态稳定、执行力很棒", "节奏拿捏得相当扎实"])

    if age_bucket == "masters":
        age_phrase = "节奏沉稳老练，真是咱们跑团自律前辈的榜样"
    elif age_bucket == "youth":
        age_phrase = "朝气蓬勃冲劲足，稳住节奏后劲会越来越强"
    else:
        age_phrase = "忙里抽空坚持训练，这份自律太令人佩服"

    if exp_bucket == "newcomer":
        exp_phrase = "每公里都在刷新自己的成长刻度"
    elif exp_bucket == "veteran":
        exp_phrase = "多年如一日的长期主义热爱令人敬佩"
    else:
        exp_phrase = "日积月累的有氧功底愈发厚实"

    if month_km >= 100.0:
        vol_phrase = f"本月已累计跑出{_fmt_km_cn(month_km)}"
    elif week_km >= 30.0:
        vol_phrase = f"本周已稳稳攒下{_fmt_km_cn(week_km)}"
    elif week_runs >= 3:
        vol_phrase = f"本周第{week_runs}练准时上线"
    else:
        vol_phrase = ""

    # Combine 2 concise persona signals without bloating length
    if vol_phrase:
        persona_bits.append(vol_phrase)
    if age_bucket != "prime":
        persona_bits.append(age_phrase)
    elif exp_bucket != "steady":
        persona_bits.append(exp_phrase)
    else:
        persona_bits.append(g_phrase)

    if len(persona_bits) < 2:
        if age_bucket != "prime":
            persona_bits.append(g_phrase)
        elif gender_bucket != "neutral":
            persona_bits.append(g_phrase if g_phrase not in persona_bits else exp_phrase)
        else:
            persona_bits.append(exp_phrase)

    middle = "，".join(persona_bits) + "。"

    # ── 3. State-Aware Warm Closing (strictly zero biometric numbers) ──
    if scenario == "group_run":
        if state_mode == "high_fatigue":
            closing = _pick_variant(seed, 21, [
                "今天合练和近期跑量消耗都不小，跑后好好拉伸补充营养，今晚早点好好休息！",
                "课后做好腿部放松与补水，好好休息让双腿充满电，下次合练继续约跑！",
            ])
        elif age_bucket == "masters":
            closing = "跑完做好舒缓拉伸与保暖，好好休息留足恢复时间，咱们下次合练继续并肩！"
        else:
            closing = _pick_variant(seed, 22, [
                "跑后记得充分拉伸补水，好好休息养精蓄锐，下次继续一起涨功力！",
                "好好休息恢复精力，期待下次合练再和大家一起痛快开跑！",
            ])
    elif scenario == "race":
        closing = "赛后这几天一定彻底放松双腿、多吃优质蛋白与碳水，好好休息犒劳自己！"
    elif scenario == "trail":
        closing = (
            "山野爬坡对小腿与臀腿考验不小，今晚做好泡沫轴松解与冰敷保暖，早点好好休息恢复！"
            if age_bucket == "masters" or state_mode == "high_fatigue"
            else "下山冲刺后记得重点放松小腿与足底筋膜，及时补水好好休息！"
        )
    elif state_mode == "high_fatigue":
        if streak_days >= 4:
            closing = f"连续跑了{streak_days}天非常辛苦，今天跑完记得多拉伸、补充能量，今晚务必好好休息满血复活！"
        else:
            closing = _pick_variant(seed, 23, [
                "近期跑得挺密、今天输出也很足，跑完记得早点好好休息、多补水补碳水让双腿恢复弹性！",
                "高输出之后恢复同样重要，做好拉伸按摩，今晚好好休息充电，明天状态更稳！",
            ])
    elif state_mode == "taper_countdown" and upcoming_race_short:
        closing = f"眼看【{upcoming_race_short}】越来越近啦，跑完舒舒服服拉伸补水，稳住轻松状态蓄势待发！"
    elif age_bucket == "masters":
        closing = "跑后慢走几分钟缓和再拉伸保暖，留足恢复窗口就能一直健康跑下去，加油！"
    elif exp_bucket == "newcomer":
        closing = "刚起步阶段保护膝踝比追求速度更重要，跑完拉伸放松好，循序渐进越跑越轻盈！"
    else:
        closing = _pick_variant(seed, 24, [
            "跑完别忘了及时补水拉伸，稳稳保持这份好心情，下次赛道见！",
            "继续保持开心奔跑的节奏，平时也要按时吃饭早点休息，咱们全团一起越跑越好！",
        ])

    full_text = _sanitize_public_cheer(f"{opener}{middle}{closing}")
    return full_text, scenario


def _is_event_for_club(ev_row: Dict[str, Any], club_id: str) -> bool:
    if str(ev_row.get("club_id") or "") == club_id:
        return True
    if ev_row.get("is_org_event"):
        scopes = _parse_scope_club_ids(ev_row.get("scope_club_ids"))
        if not scopes or club_id in scopes:
            return True
    return False


def enrich_activities_with_captain_cheer(
    activities: List[Dict[str, Any]],
    club_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Batch-enriches a list of activity dictionaries in-place with public
    `captain_cheer` and `captain_cheer_meta` using 1 SQLite read connection.
    """
    if not activities:
        return activities

    import utils.local_store as ls

    eff_db_path = db_path or ls.DB_PATH

    eligible: List[Tuple[Dict[str, Any], str, Optional[date], str]] = []
    for act in activities:
        if not isinstance(act, dict):
            continue
        sport_type = act.get("sport_type") or act.get("activity_type")
        is_excluded = str(act.get("exclude_mode") or "normal").lower() == "excluded"
        dist_m = float(act.get("distance_meters") or 0.0)
        if sport_type and not ls.LocalStore.is_running_activity(sport_type):
            act["captain_cheer"] = None
            act["captain_cheer_meta"] = None
            continue
        if is_excluded or dist_m <= 50.0 or not act.get("user_id"):
            act["captain_cheer"] = None
            act["captain_cheer_meta"] = None
            continue
        raw_uid = str(act.get("user_id"))
        canon_uid = ls.LocalStore.resolve_user_id(raw_uid)
        act_d = _parse_iso_date(act.get("start_time"))
        eligible.append((act, canon_uid, act_d, raw_uid))

    if not eligible:
        return activities

    # Resolve active clubs per runner (cached per canonical UID)
    clubs_by_uid: Dict[str, List[Dict[str, Any]]] = {}
    selected_club_by_uid: Dict[str, Optional[Dict[str, Any]]] = {}
    uid_aliases: Dict[str, set] = {}

    for _, canon_uid, _, raw_uid in eligible:
        uid_aliases.setdefault(canon_uid, {canon_uid}).add(raw_uid)
        if canon_uid in selected_club_by_uid:
            continue
        try:
            raw_clubs = ls.LocalStore.get_user_clubs(canon_uid) or []
        except Exception:
            raw_clubs = []
        active_clubs = [
            c
            for c in raw_clubs
            if (c.get("status") or "active") == "active" and not c.get("is_access_suspended")
        ]
        clubs_by_uid[canon_uid] = active_clubs
        if not active_clubs:
            selected_club_by_uid[canon_uid] = None
            continue
        chosen = None
        if club_id:
            for c in active_clubs:
                if str(c.get("id")) == str(club_id):
                    chosen = c
                    break
        if chosen is None:
            chosen = active_clubs[0]
        selected_club_by_uid[canon_uid] = chosen

    # Assign None immediately to solo / unaffiliated runners
    affiliated_items: List[Tuple[Dict[str, Any], str, Optional[date], Dict[str, Any]]] = []
    for act, canon_uid, act_d, _ in eligible:
        chosen_club = selected_club_by_uid.get(canon_uid)
        if not chosen_club:
            act["captain_cheer"] = None
            act["captain_cheer_meta"] = None
            continue
        affiliated_items.append((act, canon_uid, act_d, chosen_club))

    if not affiliated_items:
        return activities

    # Gather distinct UIDs, aliases, club IDs, captain UIDs, and date window
    all_runner_aliases: List[str] = sorted(
        {alias for _, cu, _, _ in affiliated_items for alias in uid_aliases.get(cu, {cu})}
    )
    distinct_club_ids = sorted({str(c["id"]) for _, _, _, c in affiliated_items if c.get("id")})
    owner_uid_by_club: Dict[str, str] = {}
    for _, _, _, c in affiliated_items:
        cid = str(c["id"])
        if c.get("owner_id"):
            owner_uid_by_club[cid] = ls.LocalStore.resolve_user_id(str(c["owner_id"]))

    dates = [d for _, _, d, _ in affiliated_items if d is not None]
    min_date = (min(dates) - timedelta(days=45)).isoformat() if dates else "1970-01-01"
    max_date = max(dates).isoformat() if dates else "2999-12-31"
    max_race_date = (max(dates) + timedelta(days=15)).isoformat() if dates else "2999-12-31"
    min_health_date = (min(dates) - timedelta(days=7)).isoformat() if dates else "1970-01-01"

    profiles_map: Dict[str, Dict[str, Any]] = {}
    acts_by_uid: Dict[str, List[Dict[str, Any]]] = {}
    health_by_uid: Dict[str, List[Dict[str, Any]]] = {}
    plans_by_uid: Dict[str, List[Dict[str, Any]]] = {}
    events_by_uid: Dict[str, List[Dict[str, Any]]] = {}
    races_by_uid: Dict[str, List[Dict[str, Any]]] = {}
    captain_meta_by_club: Dict[str, Dict[str, str]] = {}

    alias_to_canon = {
        alias: cu for cu, aliases in uid_aliases.items() for alias in aliases
    }

    conn = None
    try:
        conn = sqlite3.connect(eff_db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Fallback lookup for clubs missing owner_id
        missing_owner_clubs = [cid for cid in distinct_club_ids if cid not in owner_uid_by_club]
        if missing_owner_clubs:
            ph = ",".join(["?"] * len(missing_owner_clubs))
            cur.execute(
                f"""
                SELECT club_id, user_id
                FROM club_memberships
                WHERE club_id IN ({ph}) AND role = 'owner' AND status = 'active'
                ORDER BY joined_at ASC
                """,
                missing_owner_clubs,
            )
            for r in cur.fetchall():
                cid = str(r["club_id"])
                if cid not in owner_uid_by_club and r["user_id"]:
                    owner_uid_by_club[cid] = ls.LocalStore.resolve_user_id(str(r["user_id"]))

        captain_uids = sorted({u for u in owner_uid_by_club.values() if u})
        profile_query_uids = sorted(set(all_runner_aliases) | set(captain_uids))

        # 1. Batch fetch profiles (runner + captains)
        if profile_query_uids:
            ph = ",".join(["?"] * len(profile_query_uids))
            cur.execute(
                f"""
                SELECT id, display_name, gender, date_of_birth, years_running,
                       max_heart_rate, resting_heart_rate
                FROM profiles
                WHERE id IN ({ph})
                """,
                profile_query_uids,
            )
            for r in cur.fetchall():
                d_row = dict(r)
                if d_row.get("date_of_birth"):
                    d_row["date_of_birth"] = ls.decrypt_pii(d_row["date_of_birth"])
                profiles_map[str(d_row["id"])] = d_row
                canon = ls.LocalStore.resolve_user_id(str(d_row["id"]))
                profiles_map.setdefault(canon, d_row)

        # Build captain display metadata map per club
        for _, _, _, c in affiliated_items:
            cid = str(c["id"])
            if cid in captain_meta_by_club:
                continue
            cname = str(c.get("name") or "跑团").strip() or "跑团"
            cap_uid = owner_uid_by_club.get(cid, "")
            cap_prof = profiles_map.get(cap_uid) or {}
            cap_role_name = _sanitize_captain_display_name(cap_prof.get("display_name"))
            captain_meta_by_club[cid] = {
                "club_id": cid,
                "club_name": cname,
                "captain_uid": cap_uid,
                "captain_name": cap_role_name,
                "captain_title": f"{cname} · {cap_role_name}",
            }

        # 2. Batch fetch running activities in date window for volume & Banister TSB
        if all_runner_aliases:
            ph = ",".join(["?"] * len(all_runner_aliases))
            cur.execute(
                f"""
                SELECT id, user_id, name, sport_type, start_time, distance_meters,
                       moving_time_seconds, elevation_gain_meters, average_heartrate, trimp, exclude_mode
                FROM activities
                WHERE user_id IN ({ph})
                  AND substr(start_time, 1, 10) >= ?
                  AND substr(start_time, 1, 10) <= ?
                  AND {ls.RUNNING_SQL_FILTER}
                ORDER BY start_time ASC
                """,
                all_runner_aliases + [min_date, max_date],
            )
            for r in cur.fetchall():
                d_act = dict(r)
                cu = alias_to_canon.get(str(d_act["user_id"]), ls.LocalStore.resolve_user_id(str(d_act["user_id"])))
                acts_by_uid.setdefault(cu, []).append(d_act)

        # 3. Batch fetch daily_health (overnight wear sanitized -> boolean flag only)
        if all_runner_aliases:
            ph = ",".join(["?"] * len(all_runner_aliases))
            try:
                cur.execute(
                    f"""
                    SELECT user_id, date, resting_heart_rate, sleep_duration_hours, sleep_duration_seconds,
                           sleep_score, hrv_last_night_avg, hrv_weekly_avg, hrv_status
                    FROM daily_health
                    WHERE user_id IN ({ph})
                      AND substr(date, 1, 10) >= ?
                      AND substr(date, 1, 10) <= ?
                    ORDER BY date DESC
                    """,
                    all_runner_aliases + [min_health_date, max_date],
                )
                for r in cur.fetchall():
                    san = _sanitize_daily_health_row(dict(r))
                    if san and san.get("overnight_wear_valid"):
                        cu = alias_to_canon.get(str(san["user_id"]), str(san["user_id"]))
                        health_by_uid.setdefault(cu, []).append(san)
            except Exception as he:
                logger.debug(f"[captain_cheer] daily_health batch query skipped: {he}")

        # 4. Batch fetch active/published training plans
        if all_runner_aliases:
            ph = ",".join(["?"] * len(all_runner_aliases))
            try:
                cur.execute(
                    f"""
                    SELECT user_id, status, schedule_data
                    FROM training_plans
                    WHERE user_id IN ({ph}) AND status IN ('active', 'published')
                    ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, updated_at DESC
                    """,
                    all_runner_aliases,
                )
                for r in cur.fetchall():
                    cu = alias_to_canon.get(str(r["user_id"]), str(r["user_id"]))
                    try:
                        sched = json.loads(r["schedule_data"] or "{}")
                    except Exception:
                        sched = {}
                    if isinstance(sched, dict):
                        plans_by_uid.setdefault(cu, []).append(sched)
            except Exception as pe:
                logger.debug(f"[captain_cheer] training_plans batch query skipped: {pe}")

        # 5. Batch fetch club event check-ins / group runs
        if all_runner_aliases:
            ph = ",".join(["?"] * len(all_runner_aliases))
            try:
                cur.execute("PRAGMA table_info(club_events)")
                ce_cols = {row[1] for row in cur.fetchall()}
                org_cols = (
                    ", ce.is_org_event, ce.scope_club_ids"
                    if "is_org_event" in ce_cols and "scope_club_ids" in ce_cols
                    else ""
                )
                cur.execute(
                    f"""
                    SELECT cep.user_id, cep.activity_id, cep.status AS part_status,
                           ce.id AS event_id, ce.club_id, ce.title, ce.event_type,
                           ce.start_date, ce.meet_time {org_cols}
                    FROM club_event_participants cep
                    JOIN club_events ce ON cep.event_id = ce.id
                    WHERE cep.user_id IN ({ph})
                      AND COALESCE(cep.status, 'joined') != 'cancelled'
                    """,
                    all_runner_aliases,
                )
                for r in cur.fetchall():
                    d_ev = dict(r)
                    cu = alias_to_canon.get(str(d_ev["user_id"]), str(d_ev["user_id"]))
                    events_by_uid.setdefault(cu, []).append(d_ev)
            except Exception as ee:
                logger.debug(f"[captain_cheer] club_events batch query skipped: {ee}")

        # 6. Batch fetch race_plans
        if all_runner_aliases:
            ph = ",".join(["?"] * len(all_runner_aliases))
            try:
                cur.execute(
                    f"""
                    SELECT user_id, name, race_type, race_date, priority, status
                    FROM race_plans
                    WHERE user_id IN ({ph})
                      AND substr(race_date, 1, 10) >= ?
                      AND substr(race_date, 1, 10) <= ?
                    ORDER BY race_date ASC
                    """,
                    all_runner_aliases + [min_date, max_race_date],
                )
                for r in cur.fetchall():
                    d_rc = dict(r)
                    cu = alias_to_canon.get(str(d_rc["user_id"]), str(d_rc["user_id"]))
                    races_by_uid.setdefault(cu, []).append(d_rc)
            except Exception as rce:
                logger.debug(f"[captain_cheer] race_plans batch query skipped: {rce}")

    except Exception as db_err:
        logger.warning(f"[captain_cheer] Batch DB read warning: {db_err}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    # Index scheduled days per runner for O(1) date lookup
    plan_day_index: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for cu, scheds in plans_by_uid.items():
        day_map: Dict[str, Dict[str, Any]] = {}
        for sched in scheds:
            for w in sched.get("weeks") or []:
                for d in w.get("days") or []:
                    d_iso = str(d.get("date") or "")[:10]
                    if len(d_iso) == 10 and d_iso not in day_map:
                        day_map[d_iso] = d
        plan_day_index[cu] = day_map

    # Pre-build per-runner daily TRIMP series cache so TSB calculation is O(N) once per runner
    def _compute_runner_metrics_for_date(
        cu: str,
        act: Dict[str, Any],
        act_d: Optional[date],
        prof: Dict[str, Any],
    ) -> Tuple[float, int, float, int, Optional[int], bool, float]:
        if act_d is None:
            dk = round(float(act.get("distance_meters") or 0.0) / 1000.0, 2)
            return dk, 1, dk, 1, None, False, 0.0

        act_iso = act_d.isoformat()
        week_monday = act_d - timedelta(days=act_d.weekday())
        month_prefix = act_iso[:7]
        cur_id = str(act.get("id") or "")

        hist = list(acts_by_uid.get(cu, []))
        # Ensure current in-memory activity is counted once (for sync pre-insert or tests)
        if not any(cur_id and str(h.get("id") or "") == cur_id for h in hist):
            if not any(
                not cur_id
                and str(h.get("start_time") or "")[:10] == act_iso
                and abs(float(h.get("distance_meters") or 0.0) - float(act.get("distance_meters") or 0.0)) < 50.0
                for h in hist
            ):
                hist.append(act)

        week_km = 0.0
        week_runs = 0
        month_km = 0.0
        run_dates: set = set()
        prev_run_dates: List[date] = []
        had_prev_hard_48h = False

        max_hr = float(prof.get("max_heart_rate") or 190.0)
        rest_hr = float(prof.get("resting_heart_rate") or 56.0)
        gender = str(prof.get("gender") or "male")
        daily_trimp: Dict[str, float] = {}

        for r in hist:
            r_d = _parse_iso_date(r.get("start_time"))
            if r_d is None or r_d > act_d:
                continue
            r_iso = r_d.isoformat()
            r_km = float(r.get("distance_meters") or 0.0) / 1000.0
            run_dates.add(r_d)

            if r_d >= week_monday:
                week_km += r_km
                week_runs += 1
            if r_iso[:7] == month_prefix:
                month_km += r_km

            if r_d < act_d:
                prev_run_dates.append(r_d)
                delta = (act_d - r_d).days
                if 1 <= delta <= 2:
                    r_name = str(r.get("name") or "")
                    r_elev = float(r.get("elevation_gain_meters") or 0.0)
                    r_trimp = float(r.get("trimp") or 0.0)
                    if r_km >= 16.0 or r_elev >= 250.0 or r_trimp >= 110.0 or any(
                        k in r_name for k in ("间歇", "变速", "节奏", "门槛", "长距离", "比赛")
                    ):
                        had_prev_hard_48h = True

            trimp_val = float(r.get("trimp") or 0.0)
            if trimp_val <= 0.0:
                dur_min = float(r.get("moving_time_seconds") or 0.0) / 60.0
                a_hr = float(r.get("average_heartrate") or 0.0)
                if dur_min > 0.0 and a_hr > rest_hr:
                    trimp_val = calculate_trimp(dur_min, a_hr, rest_hr, max_hr, gender)
                elif dur_min > 0.0:
                    trimp_val = round(dur_min * 0.8, 1)
            daily_trimp[r_iso] = daily_trimp.get(r_iso, 0.0) + trimp_val

        # Streak ending on act_d
        streak = 0
        c_day = act_d
        while c_day in run_dates:
            streak += 1
            c_day -= timedelta(days=1)

        days_since_prev = (act_d - max(prev_run_dates)).days if prev_run_dates else None

        # Banister CTL/ATL/TSB ending on act_d
        tsb_post = 0.0
        if len(hist) >= 2:
            series: List[Tuple[str, float]] = []
            cur_s = act_d - timedelta(days=45)
            while cur_s <= act_d:
                ds = cur_s.isoformat()
                series.append((ds, daily_trimp.get(ds, 0.0)))
                cur_s += timedelta(days=1)
            ban = compute_ctl_atl_tsb(series)
            if ban:
                tsb_post = float(ban[-1].get("tsb") or 0.0)

        return (
            round(week_km, 1),
            week_runs,
            round(month_km, 1),
            streak,
            days_since_prev,
            had_prev_hard_48h,
            tsb_post,
        )

    # Enrich each affiliated activity
    for act, canon_uid, act_d, chosen_club in affiliated_items:
        cid = str(chosen_club["id"])
        prof = profiles_map.get(canon_uid) or {}

        runner_name = _sanitize_display_name(
            prof.get("display_name") or act.get("display_name"),
            fallback="跑友",
        )
        gender_bucket = _normalize_gender_bucket(prof.get("gender"))
        age_bucket = _normalize_age_bucket(prof.get("date_of_birth"))
        exp_bucket = _normalize_exp_bucket(prof.get("years_running"))

        cap_meta = captain_meta_by_club.get(cid) or {
            "club_id": cid,
            "club_name": str(chosen_club.get("name") or "跑团"),
            "captain_uid": "",
            "captain_name": "团长",
            "captain_title": f"{chosen_club.get('name') or '跑团'} · 团长",
        }
        is_captain_self = bool(cap_meta.get("captain_uid") and canon_uid == cap_meta["captain_uid"])

        week_km, week_runs, month_km, streak_days, days_since_prev, had_prev_hard_48h, tsb_post = (
            _compute_runner_metrics_for_date(canon_uid, act, act_d, prof)
        )

        # Overnight low-recovery boolean only (no numbers exposed)
        overnight_low_recovery = False
        if act_d:
            act_iso = act_d.isoformat()
            prev_iso = (act_d - timedelta(days=1)).isoformat()
            for h_row in health_by_uid.get(canon_uid, []):
                h_d = str(h_row.get("date") or "")[:10]
                if h_d in (act_iso, prev_iso):
                    hrv_n = h_row.get("hrv_last_night_avg")
                    hrv_w = h_row.get("hrv_weekly_avg")
                    slp_h = h_row.get("sleep_duration_hours")
                    slp_s = h_row.get("sleep_score")
                    if hrv_n and hrv_w and float(hrv_n) < float(hrv_w) * 0.88:
                        overnight_low_recovery = True
                    if slp_h is not None and 0 < float(slp_h) < 6.0:
                        overnight_low_recovery = True
                    if slp_s is not None and 0 < float(slp_s) < 65:
                        overnight_low_recovery = True
                    break

        act_iso = act_d.isoformat() if act_d else ""
        planned_day = plan_day_index.get(canon_uid, {}).get(act_iso) if act_iso else None

        # Matched club event / group run
        matched_event = None
        act_id_str = str(act.get("id") or "")
        for ev in events_by_uid.get(canon_uid, []):
            if not _is_event_for_club(ev, cid):
                continue
            ev_act_id = str(ev.get("activity_id") or "")
            if act_id_str and ev_act_id == act_id_str:
                matched_event = ev
                break
            ev_date = str(ev.get("meet_time") or ev.get("start_date") or "")[:10]
            if act_iso and ev_date == act_iso:
                matched_event = ev
                break

        # Matched race day or upcoming target race within 14 days
        matched_race = None
        upcoming_race = None
        if act_d:
            for rc in races_by_uid.get(canon_uid, []):
                r_d = _parse_iso_date(rc.get("race_date"))
                if r_d is None:
                    continue
                if r_d == act_d:
                    matched_race = rc
                    break
                if 1 <= (r_d - act_d).days <= 14 and upcoming_race is None:
                    upcoming_race = rc

        cheer_text, scenario = _build_captain_cheer_text(
            act=act,
            act_date=act_d,
            runner_name=runner_name,
            is_captain_self=is_captain_self,
            gender_bucket=gender_bucket,
            age_bucket=age_bucket,
            exp_bucket=exp_bucket,
            week_km=week_km,
            week_runs=week_runs,
            month_km=month_km,
            streak_days=streak_days,
            days_since_prev=days_since_prev,
            had_prev_hard_48h=had_prev_hard_48h,
            tsb_post=tsb_post,
            overnight_low_recovery=overnight_low_recovery,
            planned_day=planned_day,
            matched_event=matched_event,
            matched_race=matched_race,
            upcoming_race=upcoming_race,
            target_club_id=cid,
            club_name=cap_meta["club_name"],
        )

        act["captain_cheer"] = cheer_text
        act["captain_cheer_meta"] = {
            **cap_meta,
            "badge_label": "团长加油",
            "scenario": scenario,
        }

    return activities


def generate_activity_captain_cheer(
    activity: Dict[str, Any],
    club_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Convenience single-activity wrapper around `enrich_activities_with_captain_cheer`."""
    if not activity or not isinstance(activity, dict):
        return None, None
    temp = dict(activity)
    enrich_activities_with_captain_cheer([temp], club_id=club_id, db_path=db_path)
    return temp.get("captain_cheer"), temp.get("captain_cheer_meta")
