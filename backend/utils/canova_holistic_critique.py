"""
Holistic Multi-Lens Renato Canova Critique Engine (schema_version = 4).

Synthesizes non-repetitive, physiologically grounded Canova workout critiques
that integrate:
1. Diverse analytical lenses & phrasing tailored to workout physiology.
2. Weekly mileage, recent 48-72h hard-easy modulation, Banister CTL/ATL/TSB,
   and strictly sanitized overnight recovery metrics (HRV, sleep, resting HR).
3. Upcoming scheduled workouts and target race periodization countdowns.
"""

from datetime import date, datetime, timedelta
import hashlib
import json
import logging
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from utils.running_metrics import calculate_trimp, compute_ctl_atl_tsb, get_age_from_dob

logger = logging.getLogger("canova_holistic_critique")

CANOVA_CRITIQUE_SCHEMA_VERSION = 4

_RUNNING_SPORTS = {
    "run",
    "running",
    "trailrun",
    "trail run",
    "trail_running",
    "treadmill_running",
    "track_running",
    "street_running",
    "obstacle_run",
}

_QUALITY_WORKOUT_TYPES = {
    "intervals",
    "interval",
    "tempo",
    "threshold",
    "long_run",
    "marathon_pace",
    "progression",
    "race",
    "hill_repeats",
    "hills",
    "fartlek",
    "vo2max",
}

_REST_KEYWORDS = ("完全休息", "跑休", "休整日", "休息日", "rest", "off")
_TRAIL_KEYWORDS = ("越野", "山地", "爬山", "登山", "爬坡", "山", "trail", "gobi", "戈壁")
_INTERVAL_KEYWORDS = ("间歇", "变速", "法特莱克")
_TEMPO_KEYWORDS = ("速耐", "节奏", "门槛", "乳酸")


def _get_beijing_today() -> date:
    return (datetime.utcnow() + timedelta(hours=8)).date()


def _is_running_sport(sport_type: Optional[str]) -> bool:
    if not sport_type:
        return False
    return str(sport_type).strip().lower() in _RUNNING_SPORTS


def _is_trail_record(act: Dict[str, Any]) -> bool:
    sport_t = str(act.get("sport_type") or "").strip().lower()
    name = str(act.get("name") or "")
    elev = float(act.get("elevation_gain_meters") or act.get("total_elevation_gain") or act.get("elevationGain") or 0.0)
    if "trail" in sport_t or "越野" in sport_t:
        return True
    if elev >= 180.0:
        return True
    return any(k in name.lower() for k in _TRAIL_KEYWORDS)


def _sanitize_daily_health_row(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Strips fabricated daytime fallbacks when overnight watch wear is absent."""
    if not d or not isinstance(d, dict):
        return d
    out = dict(d)
    allow_non_hrv = bool(out.pop("allow_non_hrv_sleep", False))
    has_overnight_hrv = bool(
        out.get("hrv_last_night_avg") is not None and float(out.get("hrv_last_night_avg") or 0) > 0
    )
    has_verified_hk_sleep = bool(
        (allow_non_hrv or out.get("hrv_status") == "HK_SLEEP")
        and out.get("sleep_duration_seconds") is not None
        and float(out.get("sleep_duration_seconds") or 0) >= 7200
    )
    if not (has_overnight_hrv or has_verified_hk_sleep):
        for field in (
            "resting_heart_rate",
            "sleep_score",
            "sleep_duration_hours",
            "sleep_duration_seconds",
            "body_battery_max",
            "body_battery_min",
            "body_battery_current",
            "hrv_last_night_avg",
            "hrv_weekly_avg",
            "hrv_status",
        ):
            out[field] = None
        out["overnight_wear_valid"] = False
    else:
        if has_verified_hk_sleep and not has_overnight_hrv and not out.get("hrv_status"):
            out["hrv_status"] = "HK_SLEEP"
        out["overnight_wear_valid"] = True
    return out


def _parse_pace_to_sec(p_str: Optional[str]) -> Optional[int]:
    if not p_str:
        return None
    clean = (
        str(p_str)
        .replace("/km", "")
        .replace("'", ":")
        .replace("’", ":")
        .replace("″", "")
        .replace('"', "")
        .strip()
    )
    m_match = re.search(r"(\d{1,2})\s*[:分]\s*(\d{1,2})", clean)
    if m_match:
        val = int(m_match.group(1)) * 60 + int(m_match.group(2))
        return val if 150 <= val <= 1200 else None
    return None


def _fmt_pace_sec(sec_val: float, with_unit: bool = True) -> str:
    s_int = max(150, int(round(sec_val)))
    base = f"{s_int // 60}:{s_int % 60:02d}"
    return f"{base}/km" if with_unit else base


def _parse_time_to_sec(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = str(v).strip()
    if not s:
        return None
    parts = s.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(s)
    except Exception:
        return None


def _clean_plan_title(raw_title: str, max_len: int = 8) -> str:
    title = re.sub(r"\s*[\(（].*?[\)）]", "", str(raw_title or "")).strip()
    title = title.replace("休整日", "跑休").replace("完全休息", "跑休")
    title = re.sub(r"[\s·]+", "", title)
    if len(title) > max_len:
        title = title[:max_len]
    return title or "计划课"


def _shorten_race_name(raw_name: str, max_len: int = 8) -> str:
    s = str(raw_name or "").strip()
    s = re.sub(r"^20\d{2}\s*年?", "", s).strip()
    s = re.sub(r"^(?:China|20\d{2})\s*", "", s, flags=re.IGNORECASE).strip()
    s = s.replace("全程马拉松", "全马").replace("半程马拉松", "半马").replace("马拉松", "马")
    s = re.sub(r"\s+", "", s)
    if len(s) > max_len:
        s = s[:max_len]
    return s or "目标赛"


def _derive_race_pace_str(race_name: str, race_type: str, target_time: str) -> str:
    t_sec = _parse_time_to_sec(target_time)
    if not t_sec or t_sec < 1200:
        return ""
    rt = str(race_type or "").lower()
    rn = str(race_name or "").lower()
    if "trail" in rt or "越野" in rn or "ultra" in rt or "50k" in rn or "100k" in rn:
        return ""
    if "half" in rt or "半马" in rn:
        return f"目标HMP {_fmt_pace_sec(t_sec / 21.0975)}"
    if "10k" in rt or "10公里" in rn:
        return f"目标10K配速 {_fmt_pace_sec(t_sec / 10.0)}"
    if "marathon" in rt or "full" in rt or "全马" in rn or "马" in rn:
        return f"目标MP {_fmt_pace_sec(t_sec / 42.195)}"
    return ""


def _parse_iso_date(raw_val: Any) -> Optional[date]:
    s = str(raw_val or "").strip()[:10]
    if len(s) != 10:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _weekday_label(target_d: date, ref_d: date) -> str:
    diff = (target_d - ref_d).days
    if diff == 1:
        return "明日"
    if diff == 2:
        return "后日"
    names = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    return names[target_d.weekday()]


def _is_rest_day_dict(d: Dict[str, Any]) -> bool:
    wt = str(d.get("workout_type") or "").strip().lower()
    dist = float(d.get("distance_km") or 0.0)
    title = str(d.get("title") or "").strip().lower()
    return wt in ("rest", "off") or dist <= 0.0 or any(k in title for k in _REST_KEYWORDS)


def _is_quality_day_dict(d: Dict[str, Any]) -> bool:
    if _is_rest_day_dict(d):
        return False
    wt = str(d.get("workout_type") or "").strip().lower()
    dist = float(d.get("distance_km") or 0.0)
    title = str(d.get("title") or "").strip().lower()
    if wt in _QUALITY_WORKOUT_TYPES or dist >= 15.0:
        return True
    return any(k in title for k in ("间歇", "门槛", "节奏", "长距离", "渐进", "专项", "爬坡", "lsd", "比赛"))


def _compute_aerobic_efficiency(act: Dict[str, Any]) -> Optional[float]:
    dist_m = float(act.get("distance_meters") or 0.0)
    mov_s = float(act.get("moving_time_seconds") or 0.0)
    hr = act.get("average_heartrate")
    if not hr or dist_m < 2000.0 or mov_s <= 60.0:
        return None
    hr_f = float(hr)
    if hr_f <= 85.0 or hr_f >= 215.0:
        return None
    speed_m_per_min = dist_m / (mov_s / 60.0)
    return speed_m_per_min / hr_f


def _build_prev_hard_label(prev_act: Dict[str, Any], days_ago: int) -> str:
    day_word = {1: "昨日", 2: "前日"}.get(days_ago, f"{days_ago}天前")
    name = str(prev_act.get("name") or "")
    d_km = round(float(prev_act.get("distance_meters") or 0.0) / 1000.0, 1)
    elev = float(prev_act.get("elevation_gain_meters") or prev_act.get("total_elevation_gain") or 0.0)
    if any(k in name for k in _INTERVAL_KEYWORDS) or re.search(r"\d+\s*[*xX×]\s*\d+", name):
        return f"{day_word}间歇课"
    if any(k in name for k in _TEMPO_KEYWORDS):
        return f"{day_word}{d_km:g}km节奏课"
    if elev >= 250.0 or _is_trail_record(prev_act):
        return f"{day_word}{d_km:g}km爬坡课"
    if d_km >= 16.0:
        return f"{day_word}{d_km:g}km长距离"
    return f"{day_word}{d_km:g}km强度课"


def _format_day_workout_phrase(day_obj: Dict[str, Any], prefix: str) -> str:
    if _is_rest_day_dict(day_obj):
        return f"{prefix}跑休恢复"
    dist = float(day_obj.get("distance_km") or 0.0)
    title = _clean_plan_title(str(day_obj.get("title") or "有氧跑"), max_len=7)
    dist_tag = f"{dist:g}km" if dist > 0 else ""
    if dist_tag and dist_tag.lower() not in title.lower():
        return f"{prefix}{dist_tag}{title}"
    return f"{prefix}{title}"


def build_canova_holistic_context(
    db_path: str,
    uid: Optional[str],
    activity: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
    canonical_uid: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetches read-only holistic training, recovery, plan, and race context anchored
    to the activity date using a single SQLite connection and zero write operations.
    """
    today_bj = _get_beijing_today()
    parsed_act_date = _parse_iso_date(activity.get("start_time"))
    has_explicit_date = parsed_act_date is not None
    act_date = parsed_act_date or today_bj
    act_date_iso = act_date.isoformat()

    empty_ctx: Dict[str, Any] = {
        "has_context": False,
        "act_date": act_date_iso,
        "has_explicit_date": has_explicit_date,
        "week_runs_count": 1 if _is_running_sport(activity.get("sport_type")) else 0,
        "week_km": round(float(activity.get("distance_meters") or 0.0) / 1000.0, 1),
        "weekly_target_km": None,
        "recent_7d_runs": 1,
        "recent_7d_km": round(float(activity.get("distance_meters") or 0.0) / 1000.0, 1),
        "consecutive_days": 1,
        "days_since_prev_run": None,
        "prev_hard_or_long": None,
        "comparable": None,
        "load": {"ctl": 0.0, "atl": 0.0, "tsb_pre": 0.0, "tsb_post": 0.0, "acwr": 0.0, "has_load_history": False},
        "recovery": {"overnight_available": False, "readiness": "untracked"},
        "plan": {"has_plan": False, "plan_title": "", "weekly_target_km": None, "tomorrow_workout": None, "next_key_workout": None},
        "race": None,
    }
    if not uid:
        return empty_ctx

    eff_canonical = str(canonical_uid or uid)
    uid_str = str(uid)
    prof = profile or {}
    max_hr = float(prof.get("max_heart_rate") or 190.0)
    rest_hr = float(prof.get("resting_heart_rate") or 56.0)
    gender = str(prof.get("gender") or "male")
    hrr = max(20.0, max_hr - rest_hr)
    threshold_ceiling = rest_hr + hrr * 0.88

    win_45_start = (act_date - timedelta(days=45)).isoformat()
    win_7_start = (act_date - timedelta(days=6)).isoformat()
    week_monday = act_date - timedelta(days=act_date.weekday())
    week_monday_iso = week_monday.isoformat()

    acts_45d: List[Dict[str, Any]] = []
    health_7d: List[Dict[str, Any]] = []
    goal_weekly_target: Optional[float] = None
    plan_rows: List[Dict[str, Any]] = []
    race_rows: List[Dict[str, Any]] = []

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT id, name, sport_type, start_time, distance_meters, moving_time_seconds,
                       elevation_gain_meters, avg_pace_str, average_heartrate, trimp, exclude_mode
                FROM activities
                WHERE (user_id = ? OR user_id = ?)
                  AND substr(start_time, 1, 10) >= ?
                  AND substr(start_time, 1, 10) <= ?
                  AND COALESCE(exclude_mode, 'normal') != 'excluded'
                ORDER BY start_time ASC
                """,
                (eff_canonical, uid_str, win_45_start, act_date_iso),
            )
            acts_45d = [dict(r) for r in cur.fetchall()]
        except Exception:
            acts_45d = []

        try:
            cur.execute(
                """
                SELECT * FROM daily_health
                WHERE user_id = ? OR user_id = ?
                ORDER BY date DESC LIMIT 20
                """,
                (eff_canonical, uid_str),
            )
            for hr_row in cur.fetchall():
                d_str = str(hr_row["date"] or "")[:10]
                if win_7_start <= d_str <= act_date_iso:
                    sanitized = _sanitize_daily_health_row(dict(hr_row))
                    if sanitized:
                        health_7d.append(sanitized)
        except Exception:
            health_7d = []

        try:
            cur.execute(
                "SELECT weekly_target FROM goals WHERE user_id = ? OR user_id = ? LIMIT 1",
                (eff_canonical, uid_str),
            )
            g_row = cur.fetchone()
            if g_row and g_row["weekly_target"] and float(g_row["weekly_target"]) > 0:
                goal_weekly_target = float(g_row["weekly_target"])
        except Exception:
            goal_weekly_target = None

        try:
            cur.execute(
                """
                SELECT id, title, start_date, end_date, target_race_name, target_date, goal_type, schedule_data
                FROM training_plans
                WHERE (user_id = ? OR user_id = ?) AND status IN ('active', 'published')
                ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, updated_at DESC
                LIMIT 5
                """,
                (eff_canonical, uid_str),
            )
            plan_rows = [dict(r) for r in cur.fetchall()]
        except Exception:
            plan_rows = []

        try:
            cur.execute(
                """
                SELECT name, race_type, race_date, target_time, priority, status, finish_time
                FROM race_plans
                WHERE (user_id = ? OR user_id = ?) AND race_date > ?
                ORDER BY race_date ASC
                """,
                (eff_canonical, uid_str, act_date_iso),
            )
            race_rows = [dict(r) for r in cur.fetchall()]
        except Exception:
            race_rows = []
    except Exception as exc:
        logger.debug(f"[canova_ctx] Read fallback for {uid}: {exc}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    # Merge current activity in-memory (important during upsert_activity pre-insert)
    cur_id = str(activity.get("id") or "")
    cur_st = str(activity.get("start_time") or f"{act_date_iso}T12:00:00")
    cur_dist = float(activity.get("distance_meters") or 0.0)
    already_present = False
    for existing in acts_45d:
        ex_id = str(existing.get("id") or "")
        if cur_id and ex_id == cur_id:
            already_present = True
            break
        if (
            not cur_id
            and str(existing.get("start_time") or "")[:16] == cur_st[:16]
            and abs(float(existing.get("distance_meters") or 0.0) - cur_dist) < 50.0
        ):
            already_present = True
            break

    merged_45d = list(acts_45d)
    if not already_present:
        cur_copy = dict(activity)
        if not cur_copy.get("start_time"):
            cur_copy["start_time"] = cur_st
        merged_45d.append(cur_copy)

    # 1. Banister CTL / ATL / TSB up to act_date
    daily_trimp: Dict[str, float] = {}
    for row in merged_45d:
        st_day = _parse_iso_date(row.get("start_time"))
        if st_day is None or st_day > act_date:
            continue
        d_iso = st_day.isoformat()
        trimp_val = float(row.get("trimp") or 0.0)
        if trimp_val <= 0.0:
            dur_min = float(row.get("moving_time_seconds") or 0.0) / 60.0
            a_hr = float(row.get("average_heartrate") or 0.0)
            if dur_min > 0.0 and a_hr > rest_hr:
                trimp_val = calculate_trimp(dur_min, a_hr, rest_hr, max_hr, gender)
            elif dur_min > 0.0:
                trimp_val = round(dur_min * 0.8, 1)
        daily_trimp[d_iso] = daily_trimp.get(d_iso, 0.0) + trimp_val

    series: List[Tuple[str, float]] = []
    cursor_d = act_date - timedelta(days=45)
    while cursor_d <= act_date:
        d_s = cursor_d.isoformat()
        series.append((d_s, daily_trimp.get(d_s, 0.0)))
        cursor_d += timedelta(days=1)

    tsb_curve = compute_ctl_atl_tsb(series)
    latest_tsb = tsb_curve[-1] if tsb_curve else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}
    prev_tsb_row = tsb_curve[-2] if len(tsb_curve) >= 2 else latest_tsb
    ctl_val = float(latest_tsb["ctl"])
    atl_val = float(latest_tsb["atl"])
    tsb_post = float(latest_tsb["tsb"])
    tsb_pre = float(prev_tsb_row["tsb"])
    load_ctx = {
        "ctl": ctl_val,
        "atl": atl_val,
        "tsb_pre": tsb_pre,
        "tsb_post": tsb_post,
        "acwr": round(atl_val / max(1.0, ctl_val), 2),
        "has_load_history": len(merged_45d) >= 2,
    }

    # 2. Weekly & recent running aggregation + hard-easy detection
    running_45d = [r for r in merged_45d if _is_running_sport(r.get("sport_type"))]
    week_runs = [r for r in running_45d if week_monday_iso <= str(r.get("start_time") or "")[:10] <= act_date_iso]
    week_km = round(sum(float(r.get("distance_meters") or 0.0) for r in week_runs) / 1000.0, 1)

    runs_7d = [r for r in running_45d if win_7_start <= str(r.get("start_time") or "")[:10] <= act_date_iso]
    recent_7d_km = round(sum(float(r.get("distance_meters") or 0.0) for r in runs_7d) / 1000.0, 1)

    run_dates_set = {str(r.get("start_time") or "")[:10] for r in running_45d if len(str(r.get("start_time") or "")) >= 10}
    consecutive_days = 0
    chk_d = act_date
    while chk_d.isoformat() in run_dates_set and consecutive_days < 30:
        consecutive_days += 1
        chk_d -= timedelta(days=1)

    prior_runs = [
        r for r in running_45d
        if (not cur_id or str(r.get("id") or "") != cur_id) and str(r.get("start_time") or "") < cur_st
    ]
    prior_runs_before_today = [r for r in prior_runs if str(r.get("start_time") or "")[:10] < act_date_iso]
    days_since_prev_run: Optional[int] = None
    if prior_runs_before_today:
        prev_d = _parse_iso_date(prior_runs_before_today[-1].get("start_time"))
        if prev_d:
            days_since_prev_run = (act_date - prev_d).days

    prev_hard_or_long: Optional[Dict[str, Any]] = None
    best_demand_score = -1.0
    for pr in prior_runs_before_today:
        pr_d = _parse_iso_date(pr.get("start_time"))
        if not pr_d:
            continue
        days_ago = (act_date - pr_d).days
        if not (1 <= days_ago <= 3):
            continue
        d_km_pr = float(pr.get("distance_meters") or 0.0) / 1000.0
        elev_pr = float(pr.get("elevation_gain_meters") or 0.0)
        trimp_pr = float(pr.get("trimp") or 0.0)
        hr_pr = float(pr.get("average_heartrate") or 0.0)
        name_pr = str(pr.get("name") or "")
        is_demanding = bool(
            d_km_pr >= 16.0
            or elev_pr >= 250.0
            or trimp_pr >= 100.0
            or (hr_pr > 0 and hr_pr >= threshold_ceiling - 3)
            or any(k in name_pr for k in ("间歇", "变速", "节奏", "门槛", "渐进", "比赛", "拉练"))
        )
        if not is_demanding:
            continue
        score = trimp_pr + d_km_pr * 4.0 + (20.0 if days_ago == 1 else 0.0)
        if score > best_demand_score:
            best_demand_score = score
            prev_hard_or_long = {
                "days_ago": days_ago,
                "dist_km": round(d_km_pr, 1),
                "trimp": round(trimp_pr, 1),
                "short_label": _build_prev_hard_label(pr, days_ago),
            }

    # 3. Comparable prior runs (separated by trail vs road/track)
    cur_is_trail = _is_trail_record(activity)
    comp_candidates = [
        r for r in reversed(prior_runs)
        if float(r.get("distance_meters") or 0.0) >= 2000.0 and _is_trail_record(r) == cur_is_trail
    ][:15]

    comparable: Optional[Dict[str, Any]] = None
    if comp_candidates:
        c_dists = [round(float(r["distance_meters"]) / 1000.0, 1) for r in comp_candidates if r.get("distance_meters")]
        c_paces = [p for p in (_parse_pace_to_sec(r.get("avg_pace_str")) for r in comp_candidates) if p is not None]
        c_hrs = [float(r["average_heartrate"]) for r in comp_candidates if r.get("average_heartrate") and float(r["average_heartrate"]) > 80]
        c_efs = [ef for ef in (_compute_aerobic_efficiency(r) for r in comp_candidates) if ef is not None]
        ef_curr = _compute_aerobic_efficiency(activity)
        ef_prev_avg = (sum(c_efs) / len(c_efs)) if c_efs else None
        ef_gain_pct = round(((ef_curr - ef_prev_avg) / ef_prev_avg) * 100.0, 1) if (ef_curr and ef_prev_avg and ef_prev_avg > 0) else None
        comparable = {
            "count": len(comp_candidates),
            "is_trail": cur_is_trail,
            "avg_dist": round(sum(c_dists) / len(c_dists), 1) if c_dists else 0.0,
            "max_dist": max(c_dists) if c_dists else 0.0,
            "avg_pace_sec": (sum(c_paces) / len(c_paces)) if c_paces else None,
            "avg_hr": (sum(c_hrs) / len(c_hrs)) if c_hrs else None,
            "ef_gain_pct": ef_gain_pct,
        }

    # 4. Strict Sanitized Recovery Context
    target_health_date = act_date_iso if has_explicit_date else today_bj.isoformat()
    health_row = next((h for h in health_7d if str(h.get("date") or "")[:10] == target_health_date), None)
    valid_nights_7d = sum(1 for h in health_7d if h.get("overnight_wear_valid"))
    non_wear_7d = sum(1 for h in health_7d if not h.get("overnight_wear_valid"))
    overnight_ok = bool(health_row and health_row.get("overnight_wear_valid"))

    recovery_ctx: Dict[str, Any] = {"overnight_available": False, "readiness": "untracked"}
    if overnight_ok and health_row:
        raw_status = str(health_row.get("hrv_status") or "").strip().upper()
        hrv_val = float(health_row["hrv_last_night_avg"]) if health_row.get("hrv_last_night_avg") else None
        hrv_base_raw = float(health_row["hrv_weekly_avg"]) if health_row.get("hrv_weekly_avg") else None
        baseline_valid = bool(
            hrv_val
            and hrv_base_raw
            and raw_status not in ("NONE", "UNAVAILABLE", "POOR_QUALITY", "MISSING")
            and (valid_nights_7d >= 5 or non_wear_7d == 0)
        )
        hrv_base = hrv_base_raw if baseline_valid else None
        sleep_h = float(health_row["sleep_duration_hours"]) if health_row.get("sleep_duration_hours") else (
            round(float(health_row["sleep_duration_seconds"]) / 3600.0, 1) if health_row.get("sleep_duration_seconds") else None
        )
        sleep_sc = int(round(float(health_row["sleep_score"]))) if health_row.get("sleep_score") else None
        rhr_val = int(round(float(health_row["resting_heart_rate"]))) if health_row.get("resting_heart_rate") else None
        bb_max = int(round(float(health_row["body_battery_max"]))) if health_row.get("body_battery_max") else None

        readiness = "normal"
        if (hrv_val and hrv_base and hrv_val < hrv_base * 0.86) or (sleep_h and sleep_h < 6.0) or (sleep_sc and sleep_sc < 62):
            readiness = "suppressed"
        elif (hrv_val and hrv_base and hrv_val >= hrv_base * 1.04) or (sleep_sc and sleep_sc >= 82):
            readiness = "prime"

        recovery_ctx = {
            "overnight_available": True,
            "readiness": readiness,
            "sleep_hours": round(sleep_h, 1) if sleep_h is not None else None,
            "sleep_score": sleep_sc,
            "hrv_ms": int(round(hrv_val)) if hrv_val is not None else None,
            "hrv_baseline_ms": int(round(hrv_base)) if hrv_base is not None else None,
            "hrv_status": raw_status or None,
            "rhr_bpm": rhr_val,
            "body_battery_max": bb_max,
        }

    # 5. Active Training Plan, Weekly Target, Tomorrow & Next Key Session
    plan_ctx: Dict[str, Any] = {
        "has_plan": False,
        "plan_title": "",
        "weekly_target_km": goal_weekly_target,
        "tomorrow_workout": None,
        "next_key_workout": None,
        "plan_target_race_name": None,
        "plan_target_date": None,
    }
    selected_plan = None
    for prow in plan_rows:
        sd = str(prow.get("start_date") or "")[:10]
        ed = str(prow.get("end_date") or "")[:10]
        if (not sd or sd <= act_date_iso) and (not ed or ed >= act_date_iso):
            selected_plan = prow
            break
    if not selected_plan and plan_rows:
        selected_plan = plan_rows[0]

    if selected_plan:
        try:
            sched = json.loads(selected_plan.get("schedule_data") or "{}")
        except Exception:
            sched = {}
        weeks = sched.get("weeks") or []
        future_days: List[Tuple[date, Dict[str, Any]]] = []
        active_week = None
        for wk in weeks:
            days_list = wk.get("days") or []
            for d in days_list:
                d_obj = _parse_iso_date(d.get("date"))
                if not d_obj:
                    continue
                if d_obj == act_date:
                    active_week = wk
                if week_monday <= d_obj <= week_monday + timedelta(days=6) and active_week is None:
                    active_week = wk
                if 1 <= (d_obj - act_date).days <= 6:
                    future_days.append((d_obj, d))

        if active_week is None and weeks:
            active_week = weeks[-1]

        wk_target = None
        if active_week:
            raw_wk_m = float(active_week.get("weekly_mileage_km") or 0.0)
            if raw_wk_m <= 0:
                raw_wk_m = sum(float(x.get("distance_km") or 0.0) for x in (active_week.get("days") or []) if not _is_rest_day_dict(x))
            if raw_wk_m > 0:
                wk_target = round(raw_wk_m, 1)

        future_days.sort(key=lambda pair: pair[0])
        tomorrow_day = next((d for dt, d in future_days if (dt - act_date).days == 1), None)
        next_key_pair = next(((dt, d) for dt, d in future_days if _is_quality_day_dict(d)), None)

        tmr_info = None
        if tomorrow_day:
            tmr_info = {
                "is_rest": _is_rest_day_dict(tomorrow_day),
                "distance_km": float(tomorrow_day.get("distance_km") or 0.0),
                "phrase": _format_day_workout_phrase(tomorrow_day, "明日"),
            }

        key_info = None
        if next_key_pair:
            kd_dt, kd_obj = next_key_pair
            k_prefix = _weekday_label(kd_dt, act_date)
            key_info = {
                "days_away": (kd_dt - act_date).days,
                "distance_km": float(kd_obj.get("distance_km") or 0.0),
                "phrase": _format_day_workout_phrase(kd_obj, k_prefix),
            }

        plan_ctx = {
            "has_plan": True,
            "plan_title": _clean_plan_title(selected_plan.get("title") or "周期课表", max_len=10),
            "weekly_target_km": wk_target or goal_weekly_target,
            "tomorrow_workout": tmr_info,
            "next_key_workout": key_info,
            "plan_target_race_name": selected_plan.get("target_race_name") or sched.get("target_race"),
            "plan_target_date": selected_plan.get("target_date") or sched.get("target_date"),
        }

    # 6. Upcoming Race & Canova Periodization Phase
    upcoming_races = [
        r for r in race_rows
        if str(r.get("status") or "upcoming").lower() != "completed" and not str(r.get("finish_time") or "").strip()
    ]
    next_race_row = upcoming_races[0] if upcoming_races else None
    if not next_race_row and plan_ctx.get("plan_target_race_name") and plan_ctx.get("plan_target_date"):
        p_r_date = _parse_iso_date(plan_ctx["plan_target_date"])
        if p_r_date and p_r_date > act_date:
            next_race_row = {
                "name": plan_ctx["plan_target_race_name"],
                "race_type": "marathon",
                "race_date": p_r_date.isoformat(),
                "target_time": "",
            }

    race_ctx: Optional[Dict[str, Any]] = None
    if next_race_row:
        r_dt = _parse_iso_date(next_race_row.get("race_date"))
        if r_dt and r_dt > act_date:
            days_left = (r_dt - act_date).days
            if days_left <= 14:
                period_phase = "赛前减量期"
            elif days_left <= 42:
                period_phase = "专项决战期"
            elif days_left <= 84:
                period_phase = "专项准备期"
            else:
                period_phase = "基础建构期"
            r_name = str(next_race_row.get("name") or "目标赛事")
            r_type = str(next_race_row.get("race_type") or "")
            race_ctx = {
                "name": r_name,
                "short_name": _shorten_race_name(r_name, max_len=8),
                "days_left": days_left,
                "race_type": r_type,
                "is_trail": ("trail" in r_type.lower() or any(k in r_name for k in _TRAIL_KEYWORDS)),
                "period_phase": period_phase,
                "target_pace_note": _derive_race_pace_str(r_name, r_type, str(next_race_row.get("target_time") or "")),
            }

    return {
        "has_context": True,
        "act_date": act_date_iso,
        "has_explicit_date": has_explicit_date,
        "week_runs_count": len(week_runs),
        "week_km": week_km,
        "weekly_target_km": plan_ctx["weekly_target_km"],
        "recent_7d_runs": len(runs_7d),
        "recent_7d_km": recent_7d_km,
        "consecutive_days": consecutive_days,
        "days_since_prev_run": days_since_prev_run,
        "prev_hard_or_long": prev_hard_or_long,
        "comparable": comparable,
        "load": load_ctx,
        "recovery": recovery_ctx,
        "plan": plan_ctx,
        "race": race_ctx,
    }


def _choose_lens_lead(
    activity: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    holistic_ctx: Dict[str, Any],
    plan_exec_block: str,
    seg_result: Optional[Dict[str, Any]],
    seed: int,
) -> Tuple[str, str]:
    """Selects Canova analytical lens key and builds diverse lead diagnostic block."""
    if plan_exec_block:
        return "planned", plan_exec_block.strip()

    if isinstance(seg_result, dict) and seg_result.get("mode") == "planned_workout" and seg_result.get("concise_critique"):
        concise_plan = str(seg_result["concise_critique"]).split("💡")[0].strip()
        return "planned", concise_plan

    dist_m = float(activity.get("distance_meters") or 0.0)
    dist_km = round(dist_m / 1000.0, 2)
    pace_str = str(activity.get("avg_pace_str") or "5:30").replace("/km", "").strip() + "/km"
    pace_sec = _parse_pace_to_sec(pace_str) or 330
    avg_hr = activity.get("average_heartrate")
    elev_gain = float(activity.get("elevation_gain_meters") or activity.get("total_elevation_gain") or activity.get("elevationGain") or 0.0)
    act_name = str(activity.get("name") or "")

    max_hr = float((profile or {}).get("max_heart_rate") or 190.0)
    rest_hr = float((profile or {}).get("resting_heart_rate") or 56.0)
    hrr = max(20.0, max_hr - rest_hr)
    recovery_ceiling = rest_hr + hrr * 0.62
    aerobic_ceiling = rest_hr + hrr * 0.75
    threshold_ceiling = rest_hr + hrr * 0.88

    is_trail = _is_trail_record(activity)
    prev_hard = holistic_ctx.get("prev_hard_or_long")
    race_ctx = holistic_ctx.get("race")

    # Extract split structure line if coming from segment analysis
    seg_phases = (seg_result or {}).get("phases") if isinstance(seg_result, dict) else None
    structure_line = str((seg_result or {}).get("summary_verdict") or "").strip() if isinstance(seg_result, dict) else ""
    venue_tag = "🏟️ 田径场 · " if (isinstance(seg_result, dict) and seg_result.get("is_track_run") and not is_trail) else ""
    main_decoupling = next((p.get("decoupling_pct") for p in (seg_phases or []) if p.get("decoupling_pct") is not None), None)

    hr_brief = f"，均心{int(round(float(avg_hr)))}bpm" if avg_hr else ""
    hrr_pct = int(round(((float(avg_hr) - rest_hr) / hrr) * 100)) if avg_hr and float(avg_hr) > rest_hr else None

    # 1. Trail / Mountain Lens
    if is_trail:
        elev_int = int(round(elev_gain))
        header = "【山地专项耐力】" if (elev_gain >= 500 or dist_km >= 20) else ("【山地有氧爬坡】" if seed % 2 == 0 else "【山地垂直耐力】")
        if structure_line and seg_phases:
            return "trail", f"【{venue_tag}{header[1:-1]}】爬升+{elev_int}m（陡坡主动徒步/Power Hiking），分段：{structure_line}，下坡稳控步频。"
        variants = [
            f"{header}{dist_km}km爬升+{elev_int}m（{pace_str}{hr_brief}），陡坡以徒步(Power Hiking)控心率，强壮下肢耐力。",
            f"{header}{dist_km}km累计爬升+{elev_int}m（均速{pace_str}{hr_brief}），长坡徒步节能与平缓跑动衔接合理，巩固垂直耐力。",
        ]
        return "trail", variants[seed % len(variants)]

    # 2. Interval / VO2max Lens
    has_seg_intervals = bool(seg_phases and any(p.get("phase_type") == "intervals" for p in seg_phases))
    is_name_interval = bool(
        re.search(r"(\d+\s*[*xX×]\s*\d+|\d+\s*(?:m|米|km|k)\s*[*xX×+]|\b(?:1st|2nd|3rd|\d+th)\b|间歇|变速|法特莱克)", act_name, re.I)
    )
    if has_seg_intervals or is_name_interval:
        if has_seg_intervals and isinstance(seg_result, dict):
            title = str(seg_result.get("summary_title") or "变速/间歇训练")
            if title.startswith("🏟️ 田径场 · "):
                title_body = title
            else:
                title_body = f"{venue_tag}{title}"
            return "intervals", f"【{title_body}】分段表现：{structure_line}，快慢交替有效触发最大摄氧量与快速恢复动能。"
        variants = [
            f"【间歇专项刺激】{dist_km}km @ {pace_str}{hr_brief}，高强度快跑段激发最大摄氧量与步频神经募集，锻炼间歇心率回落速率。",
            f"【间歇专项刺激】{dist_km}km变速刺激（{pace_str}{hr_brief}），通过短间歇高输出提升糖酵解缓冲与跑姿经济性。",
        ]
        return "intervals", variants[seed % len(variants)]

    # 3. Warmup / Cooldown special short names
    if dist_km < 5.0 and "热身" in act_name:
        return "warmup", f"【热身激活跑】{dist_km}km @ {pace_str}{hr_brief}，循序抬升体温与肌腱弹性，唤醒神经募集为后续强刺激蓄势。"
    if dist_km < 5.0 and "冷身" in act_name:
        return "cooldown", f"【冷身排酸跑】{dist_km}km @ {pace_str}{hr_brief}，平缓回落交感张力并冲刷局部乳酸，加速课后微循环恢复。"

    # 4. Progression / Negative Split Lens
    has_seg_prog = bool(seg_phases and any(p.get("phase_type") == "progression" for p in seg_phases))
    if has_seg_prog or "渐进" in act_name:
        mp_ref = f"（逼近{race_ctx['target_pace_note']}）" if (race_ctx and race_ctx.get("target_pace_note")) else ""
        if structure_line and seg_phases:
            dec_note = f"，解耦率仅{main_decoupling}%" if (main_decoupling is not None and main_decoupling <= 5.5) else ""
            return "progression", f"【{venue_tag}渐进加速跑】分段表现：{structure_line}{dec_note}，后程按节奏递进募集快肌纤维{mp_ref}。"
        return "progression", f"【渐进加速征召】{dist_km}km @ {pace_str}{hr_brief}，前稳后快逐级调用糖原与耐疲劳肌群{mp_ref}。"

    # 5. Late Fade Diagnostic Lens (connects fade to fatigue/sleep/pace)
    has_seg_fade = bool(seg_phases and any(p.get("phase_type") == "fade" for p in seg_phases))
    if has_seg_fade and structure_line:
        rec = holistic_ctx.get("recovery") or {}
        load = holistic_ctx.get("load") or {}
        if rec.get("readiness") == "suppressed" or float(load.get("tsb_post") or 0.0) < -25 or (prev_hard and prev_hard["days_ago"] <= 2):
            reason = "叠加近期累积疲劳/休息不足致后程降速"
        else:
            reason = "提示起跑节奏偏急，后程心肺余量收窄"
        dec_note = f"（解耦率{main_decoupling}%）" if main_decoupling is not None else ""
        return "fade", f"【{venue_tag}前快后慢有氧诊断】分段表现：{structure_line}{dec_note}，{reason}。"

    # 6. Threshold / Tempo / Specificity Lens
    is_tempo = bool(
        any(k in act_name for k in _TEMPO_KEYWORDS)
        or (dist_km >= 3.0 and avg_hr and float(avg_hr) >= threshold_ceiling)
    )
    if is_tempo:
        is_lt = bool(avg_hr and float(avg_hr) >= threshold_ceiling)
        header = "【混氧门槛突破】" if is_lt else "【专项节奏进阶】"
        mp_note = f"，直指{race_ctx['target_pace_note']}" if (race_ctx and race_ctx.get("target_pace_note")) else ""
        if structure_line and seg_phases:
            return "threshold", f"【{venue_tag}{header[1:-1]}】分段表现：{structure_line}，高稳态输出强化乳酸穿梭平衡{mp_note}。"
        variants = [
            f"{header}{dist_km}km @ {pace_str}{hr_brief}，稳守乳酸清除与生成拐点，拉高专项定速巡航上限{mp_note}。",
            f"{header}{dist_km}km核心节奏刺激（{pace_str}{hr_brief}），在可控负荷下提升比赛配速持续耐受度{mp_note}。",
        ]
        return "threshold", variants[seed % len(variants)]

    # 7. Long Run Durability Lens (>= 18km; keep exact 【长距离有氧耐力】 when >=20km & < aerobic_ceiling)
    if dist_km >= 20.0:
        if avg_hr and float(avg_hr) < aerobic_ceiling:
            if structure_line and seg_phases:
                return "lsd", f"【长距离有氧耐力】分段表现：{structure_line}，均心{int(round(float(avg_hr)))}bpm低于有氧上限{int(round(aerobic_ceiling))}bpm，糖脂代谢与抗漂移稳固。"
            variants = [
                f"【长距离有氧耐力】{dist_km}km @ {pace_str}（均心{int(round(float(avg_hr)))}bpm < 有氧上限{int(round(aerobic_ceiling))}bpm），长时稳态供能扎实，抗漂移余量足。",
                f"【长距离有氧耐力】{dist_km}km有氧长课（{pace_str}{hr_brief}），心肺储备稳守有氧区，深度扩容线粒体密度与慢肌耐力。",
            ]
            return "lsd", variants[seed % len(variants)]
        else:
            dec_txt = f"、核心解耦率{main_decoupling}%" if main_decoupling is not None else ""
            if structure_line and seg_phases:
                return "lsd", f"【马拉松专项耐力】分段表现：{structure_line}{dec_txt}，高续航出力打磨后程抗掉速韧性。"
            return "lsd", f"【马拉松专项耐力】{dist_km}km @ {pace_str}{hr_brief}，持续强化长距离肌群抗衰与补给耐受度。"

    if dist_km >= 18.0:
        if structure_line and seg_phases:
            return "lsd", f"【{venue_tag}长距离有氧耐力跑（LSD）】分段表现：{structure_line}，筑牢长距离有氧底座。"
        return "lsd", f"【长距离有氧耐力】{dist_km}km @ {pace_str}{hr_brief}，延伸慢肌糖原利用半径，扎实巩固长跑续航。"

    # 8. Recovery & Hard-Easy Modulation Lens
    is_recovery_hr = bool(avg_hr and float(avg_hr) < recovery_ceiling)
    is_post_hard_easy = bool(prev_hard and prev_hard["days_ago"] <= 2 and dist_km <= 13.0 and (not avg_hr or float(avg_hr) < aerobic_ceiling))
    if (dist_km >= 5.0 and (is_recovery_hr or is_post_hard_easy)) or (avg_hr and float(avg_hr) < recovery_ceiling):
        mod_note = f"承接{prev_hard['short_label']}进行强弱交替排酸，" if prev_hard else "主动压低输出节奏，"
        if is_recovery_hr and dist_km >= 5.0:
            variants = [
                f"【低心率恢复跑】{dist_km}km @ {pace_str}（均心{int(round(float(avg_hr)))}bpm < 恢复上限{int(round(recovery_ceiling))}bpm），{mod_note}零额外疲劳促进微循环。",
                f"【低心率恢复调制】{dist_km}km @ {pace_str}{hr_brief}，{mod_note}用无压有氧清除肌纤维微损伤。",
            ]
            return "modulation", variants[seed % len(variants)]
        return "modulation", f"【强弱交替调制跑】{dist_km}km @ {pace_str}{hr_brief}，{mod_note}严格贯彻Canova高低负荷交替节律。"

    # 9. Steady Aerobic Efficiency Lens (rotates method focus deterministically)
    if dist_km < 6.0:
        return "short", f"【短程激活跑】{dist_km}km @ {pace_str}{hr_brief}，步频轻快衔接良好，适合日常保持神经肌肉弹性。"

    if structure_line and seg_phases:
        title_seg = str((seg_result or {}).get("summary_title") or ("稳态有氧巡航" if dist_km >= 12.0 else "基础有氧跑"))
        title_seg = title_seg.replace("🏟️ 田径场 · ", "")
        dec_seg = f"，核心解耦率{main_decoupling}%" if main_decoupling is not None else ""
        return "aerobic", f"【{venue_tag}{title_seg}】分段表现：{structure_line}{dec_seg}，节奏平稳输出可控。"

    margin_bpm = int(round(aerobic_ceiling - float(avg_hr))) if avg_hr else None
    header = "【稳态有氧进阶】" if dist_km >= 12.0 else "【基础有氧效率】"
    variant_idx = seed % 3
    if variant_idx == 0 and hrr_pct is not None:
        return "aerobic", f"{header}{dist_km}km @ {pace_str}（均心{int(round(float(avg_hr)))}bpm·约{hrr_pct}%储备心率），毛细血管网与有氧经济性稳步累积。"
    if variant_idx == 1 and margin_bpm is not None and margin_bpm >= 0:
        return "aerobic", f"{header}{dist_km}km有氧巡航（{pace_str}），较有氧上限留出{margin_bpm}bpm安全余量，心肺底座稳固。"
    return "aerobic", f"{header}{dist_km}km @ {pace_str}{hr_brief}，步频与呼吸节律均衡，持续夯实脂代谢有氧底座。"


def _build_highlight_block(
    lens_key: str,
    activity: Dict[str, Any],
    holistic_ctx: Dict[str, Any],
    seed: int,
) -> str:
    """Builds 🌟【亮点】 uniting workout performance metrics with weekly/recent microcycle load."""
    dist_km = round(float(activity.get("distance_meters") or 0.0) / 1000.0, 2)
    pace_str = str(activity.get("avg_pace_str") or "5:30").replace("/km", "").strip() + "/km"
    pace_sec = _parse_pace_to_sec(pace_str) or 330
    avg_hr = activity.get("average_heartrate")
    elev_gain = float(activity.get("elevation_gain_meters") or activity.get("total_elevation_gain") or activity.get("elevationGain") or 0.0)

    comp = holistic_ctx.get("comparable")
    prev_hard = holistic_ctx.get("prev_hard_or_long")
    week_runs = int(holistic_ctx.get("week_runs_count") or 0)
    week_km = float(holistic_ctx.get("week_km") or 0.0)
    weekly_target = holistic_ctx.get("weekly_target_km")
    recent_7d_km = float(holistic_ctx.get("recent_7d_km") or 0.0)
    consecutive_days = int(holistic_ctx.get("consecutive_days") or 0)
    days_since_prev = holistic_ctx.get("days_since_prev_run")

    core_hl = ""
    if comp and lens_key not in ("trail", "intervals"):
        avg_prev_dist = float(comp.get("avg_dist") or dist_km)
        max_prev_dist = float(comp.get("max_dist") or dist_km)
        avg_prev_pace = comp.get("avg_pace_sec")
        avg_prev_hr = comp.get("avg_hr")
        ef_gain = comp.get("ef_gain_pct")

        pace_diff = int(round(float(avg_prev_pace) - pace_sec)) if avg_prev_pace else 0
        hr_diff = int(round(float(avg_prev_hr) - float(avg_hr))) if (avg_hr and avg_prev_hr) else 0

        if lens_key == "planned" or (pace_diff >= 3 and hr_diff >= 2):
            parts = []
            if dist_km > max_prev_dist + 0.3:
                parts.append(f"距离{dist_km}km创近期新高")
            elif dist_km >= avg_prev_dist + 0.5:
                parts.append(f"{dist_km}km（较均值+{round(dist_km - avg_prev_dist, 1)}km）")
            else:
                parts.append(f"稳健完成{dist_km}km")
            if pace_diff >= 3:
                parts.append(f"较近期提速{pace_diff}秒/km")
            elif abs(pace_diff) < 3:
                parts.append(f"配速稳在{pace_str}")
            else:
                parts.append(f"控速{pace_str}稳守有氧")
            if avg_hr and avg_prev_hr:
                hr_int = int(round(float(avg_hr)))
                if hr_diff >= 2:
                    parts.append(f"均心下降{hr_diff}bpm（{hr_int}bpm）")
                elif pace_diff >= 3 and hr_diff >= -2:
                    parts.append(f"提速下均心稳守{hr_int}bpm")
                else:
                    parts.append(f"均心{hr_int}bpm")
            core_hl = "、".join(parts)
        elif ef_gain is not None and ef_gain >= 1.5 and seed % 2 == 0:
            core_hl = f"{dist_km}km有氧效率(EF)较近期提升{ef_gain:.1f}%"

    if not core_hl:
        if lens_key == "trail":
            density = int(round(elev_gain / max(0.5, dist_km)))
            hr_s = f"均心稳控{int(round(float(avg_hr)))}bpm" if avg_hr else f"爬升+{int(round(elev_gain))}m"
            core_hl = f"越野垂直密度+{density}m/km，{hr_s}"
        elif lens_key == "intervals":
            core_hl = f"{dist_km}km快慢节奏清晰，神经募集响应快"
        elif lens_key == "modulation" and prev_hard:
            core_hl = f"衔接{prev_hard['short_label']}完成强弱交替排酸"
        elif prev_hard and prev_hard["days_ago"] == 1 and lens_key in ("lsd", "threshold", "progression"):
            core_hl = f"背靠背衔接{prev_hard['short_label']}抗疲劳耐受扎实"
        elif consecutive_days >= 3:
            core_hl = f"连续第{consecutive_days}天打卡保持有氧刺激"
        elif days_since_prev is not None and days_since_prev >= 3:
            core_hl = f"休整{days_since_prev - 1}天后重启训练，心肺响应轻快"
        else:
            hr_tag = f"（均心{int(round(float(avg_hr)))}bpm）" if avg_hr else ""
            core_hl = f"顺利完成{dist_km}km @ {pace_str}{hr_tag}"

    # Weekly / 7d training context tail
    week_tail = ""
    if holistic_ctx.get("has_context") and week_runs >= 1:
        if weekly_target and weekly_target > 0:
            tgt_i = int(round(float(weekly_target)))
            if week_runs == 1:
                week_tail = f"，开启本周首练（周目标{tgt_i}km）"
            else:
                week_tail = f"，本周第{week_runs}练推进至{week_km:g}/{tgt_i}km"
        elif week_runs >= 2:
            week_tail = f"，本周{week_runs}练累计{week_km:g}km"
        elif recent_7d_km > dist_km + 0.5:
            week_tail = f"，近7天累计{recent_7d_km:g}km"
    elif not holistic_ctx.get("has_context"):
        week_tail = "，建立清晰单次基线"

    return f" 🌟【亮点】{core_hl}{week_tail}。"


def _build_recovery_clause(
    lens_key: str,
    activity: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    holistic_ctx: Dict[str, Any],
    seed: int,
) -> str:
    """Combines sanitized overnight recovery metrics, CTL/TSB load, and actionable recovery advice."""
    dist_km = round(float(activity.get("distance_meters") or 0.0) / 1000.0, 2)
    age = get_age_from_dob((profile or {}).get("date_of_birth"))
    is_master_long = bool(age and age >= 50 and dist_km >= 10.0)

    rec = holistic_ctx.get("recovery") or {}
    load = holistic_ctx.get("load") or {}

    status_bits: List[str] = []
    if rec.get("overnight_available"):
        rec_parts: List[str] = []
        if rec.get("sleep_hours") is not None:
            sc_s = f"({rec['sleep_score']}分)" if rec.get("sleep_score") else ""
            rec_parts.append(f"睡眠{rec['sleep_hours']}h{sc_s}")
        elif rec.get("sleep_score") is not None:
            rec_parts.append(f"睡眠{rec['sleep_score']}分")
        if rec.get("hrv_ms") is not None:
            if rec.get("hrv_baseline_ms"):
                rel = "低于基线" if rec["hrv_ms"] < rec["hrv_baseline_ms"] * 0.88 else "稳居基线"
                rec_parts.append(f"HRV {rec['hrv_ms']}ms({rel})")
            else:
                rec_parts.append(f"HRV {rec['hrv_ms']}ms")
        elif rec.get("rhr_bpm") is not None:
            rec_parts.append(f"静息{rec['rhr_bpm']}bpm")
        if rec_parts:
            status_bits.append("·".join(rec_parts))

    tsb_post = float(load.get("tsb_post") or 0.0)
    ctl_val = float(load.get("ctl") or 0.0)
    if load.get("has_load_history"):
        tsb_sign = f"{'+' if tsb_post >= 0 else ''}{int(round(tsb_post))}"
        if tsb_post < -30:
            load_state = "疲劳红线"
        elif tsb_post < -12:
            load_state = "负荷吸收期"
        elif tsb_post > 10:
            load_state = "体能充沛"
        else:
            load_state = "状态平衡"
        status_bits.append(f"CTL {int(round(ctl_val))}·TSB {tsb_sign}({load_state})")

    status_prefix = "、".join(status_bits[:2])

    # Specific recovery action
    is_trail_act = lens_key == "trail" or _is_trail_record(activity)
    if is_trail_act and is_master_long:
        action = "大师组关注股四头肌离心放松与48-72h超量恢复"
    elif is_trail_act:
        action = "重视股四头肌离心放松与补糖"
    elif is_master_long:
        action = "大师组留足48-72h超量恢复"
    elif rec.get("readiness") == "suppressed" or (load.get("has_load_history") and tsb_post < -30):
        action = "今晚务必早睡补足8h以修复自主神经"
    elif lens_key in ("intervals", "threshold", "planned"):
        actions = ("跑后30分内补碳水并深滚筋膜", "重视跟腱小腿拉伸与碳水回填")
        action = actions[seed % len(actions)]
    elif lens_key == "lsd":
        action = "及时回填肌糖原并关注48h延迟酸痛"
    elif lens_key == "modulation":
        action = "保持水分补给与轻度髋踝激活即可"
    else:
        actions = ("跑后拉伸腘绳与臀中肌防僵硬", "保持7.5h+睡眠巩固有氧恢复")
        action = actions[seed % len(actions)]

    if status_prefix:
        return f"{status_prefix}，{action}"
    return action


def _build_forward_clause(
    lens_key: str,
    holistic_ctx: Dict[str, Any],
    seed: int,
) -> str:
    """Combines upcoming scheduled workout(s) and next target race periodization."""
    plan = holistic_ctx.get("plan") or {}
    race = holistic_ctx.get("race")
    load = holistic_ctx.get("load") or {}
    tsb_post = float(load.get("tsb_post") or 0.0)

    tmr = plan.get("tomorrow_workout")
    nkey = plan.get("next_key_workout")

    parts: List[str] = []
    if race:
        p_note = f"·{race['target_pace_note']}" if (race.get("target_pace_note") and lens_key in ("threshold", "progression", "lsd", "planned")) else ""
        parts.append(f"距{race['short_name']}D-{race['days_left']}（{race['period_phase']}{p_note}）")

    if tmr:
        tmr_p = tmr["phrase"]
        if tmr.get("is_rest") and nkey and nkey.get("days_away", 9) >= 2:
            parts.append(f"{tmr_p}，蓄力{nkey['phrase']}")
        else:
            parts.append(tmr_p)
    elif nkey:
        parts.append(f"下一步蓄力{nkey['phrase']}")
    elif race:
        phase = race["period_phase"]
        if phase == "赛前减量期":
            parts.append("严控跑量保状态，维持神经轻快")
        elif phase == "专项决战期":
            parts.append("主课收敛至比赛专项配速")
        else:
            parts.append("稳步推进专项有氧与长距离")
    elif plan.get("has_plan"):
        parts.append(f"紧扣《{plan['plan_title']}》节奏，下课前有氧过渡")
    else:
        if tsb_post < -28 or lens_key in ("intervals", "threshold", "lsd", "trail"):
            parts.append("下课优先安排48h低心率慢跑或跑休衔接")
        else:
            opts = ("下次主课前保持轻松跑过渡积累", "下次可衔接1次渐进加速或门槛课")
            parts.append(opts[seed % len(opts)])

    return "，".join(parts)


def _compact_critique(
    lead_block: str,
    highlight_block: str,
    recovery_clause: str,
    forward_clause: str,
    is_trail: bool,
    is_master_long: bool,
    limit: int = 226,
) -> str:
    def _assemble(lb: str, hb: str, rc: str, fc: str) -> str:
        rc_clean = rc.strip().rstrip("。.")
        fc_clean = fc.strip().rstrip("。.")
        text = f"{lb.strip()}{hb} 💡 {rc_clean}。⚡ {fc_clean}。"
        return text.replace("休整日", "跑休")

    full = _assemble(lead_block, highlight_block, recovery_clause, forward_clause)
    if len(full) <= limit:
        return full

    # Step 1: Trim non-critical parentheticals inside lead_block while keeping core tags
    lead_c = re.sub(r"（目标[^）]*）", "", lead_block)
    full = _assemble(lead_c, highlight_block, recovery_clause, forward_clause)
    if len(full) <= limit:
        return full

    # Step 2: Trim optional trailing clauses in highlight_block before weekly tail
    hb_c = re.sub(r"（周目标\d+km）", "", highlight_block)
    full = _assemble(lead_c, hb_c, recovery_clause, forward_clause)
    if len(full) <= limit:
        return full

    # Step 3: Compact lead_block sentence slightly while keeping 【...】 title & numbers
    if "。" in lead_c:
        lead_c2 = lead_c.split("。")[0] + "。"
        full = _assemble(lead_c2, hb_c, recovery_clause, forward_clause)
        if len(full) <= limit:
            return full
        lead_c = lead_c2

    # Step 4: Compact recovery / forward clauses while preserving mandatory trail/master keywords
    rc_c = recovery_clause
    if "，" in rc_c and len(_assemble(lead_c, hb_c, rc_c, forward_clause)) > limit:
        first_r, second_r = rc_c.split("，", 1)
        short_first_r = first_r.split("、")[0]
        candidate_rc = f"{short_first_r}，{second_r}" if short_first_r and short_first_r != first_r else second_r
        if len(_assemble(lead_c, hb_c, candidate_rc, forward_clause)) <= limit:
            rc_c = candidate_rc
        elif is_trail or is_master_long:
            rc_c = second_r
        else:
            rc_c = second_r if len(second_r) >= 8 else short_first_r

    fc_c = forward_clause
    full = _assemble(lead_c, hb_c, rc_c, fc_c)
    if len(full) <= limit:
        return full

    # Step 5: Trim secondary clauses in fc_c / rc_c before touching lead_c
    if "，" in fc_c:
        fc_head, _ = fc_c.split("，", 1)
        if len(fc_head) >= 8:
            fc_c = fc_head
    full = _assemble(lead_c, hb_c, rc_c, fc_c)
    if len(full) <= limit:
        return full

    if "，" in rc_c and (is_trail or is_master_long):
        _, rc_tail = rc_c.split("，", 1)
        if rc_tail:
            rc_c = rc_tail
    full = _assemble(lead_c, hb_c, rc_c, fc_c)
    if len(full) <= limit:
        return full

    # Guarantee absolute <= limit without breaking mandatory keywords
    if len(full) > limit and len(lead_c) > 50:
        keep = max(42, len(lead_c) - (len(full) - limit) - 1)
        lead_c = lead_c[:keep].rstrip("，,、 ") + "。"
        full = _assemble(lead_c, hb_c, rc_c, fc_c)
    if len(full) > limit:
        return full[:limit - 1].rstrip("，,、 ") + "。"
    return full


def build_segmented_coach_advice(
    activity: Dict[str, Any],
    holistic_ctx: Optional[Dict[str, Any]],
    base_split_advice: str,
    mode: str = "free_workout",
) -> str:
    """Enriches segmented split modal `coach_advice` with load, recovery, and upcoming race/plan context."""
    base = str(base_split_advice or "").strip().replace("休整日", "跑休")
    if not holistic_ctx or not holistic_ctx.get("has_context"):
        return base

    rec = holistic_ctx.get("recovery") or {}
    load = holistic_ctx.get("load") or {}
    plan = holistic_ctx.get("plan") or {}
    race = holistic_ctx.get("race")

    extras: List[str] = []
    week_runs = int(holistic_ctx.get("week_runs_count") or 0)
    week_km = float(holistic_ctx.get("week_km") or 0.0)
    weekly_target = holistic_ctx.get("weekly_target_km")
    if week_runs >= 1:
        if weekly_target and weekly_target > 0:
            extras.append(f"本周{week_runs}练累计{week_km:g}/{int(round(float(weekly_target)))}km")
        else:
            extras.append(f"本周{week_runs}练累计{week_km:g}km")

    if rec.get("overnight_available"):
        rec_bits = []
        if rec.get("sleep_hours") is not None:
            rec_bits.append(f"睡眠{rec['sleep_hours']}h")
        if rec.get("hrv_ms") is not None:
            rec_bits.append(f"HRV {rec['hrv_ms']}ms")
        if rec_bits:
            extras.append("·".join(rec_bits))

    if load.get("has_load_history"):
        tsb_v = float(load.get("tsb_post") or 0.0)
        extras.append(f"CTL {int(round(float(load.get('ctl') or 0)))} / TSB {'+' if tsb_v >= 0 else ''}{int(round(tsb_v))}")

    next_bits: List[str] = []
    if plan.get("tomorrow_workout"):
        next_bits.append(plan["tomorrow_workout"]["phrase"])
    if race:
        next_bits.append(f"距{race['short_name']}{race['days_left']}天({race['period_phase']})")
    if next_bits:
        extras.append("，".join(next_bits))

    if not extras:
        return base
    return f"{base}（{'；'.join(extras)}）"


def synthesize_canova_holistic_critique(
    activity: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
    holistic_ctx: Optional[Dict[str, Any]] = None,
    plan_exec_block: str = "",
    seg_result: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Produces a holistic <=226-char Renato Canova critique combining:
    - Non-repetitive physiological lens diagnosis
    - Weekly/recent microcycle progress & hard-easy modulation (🌟【亮点】)
    - Sanitized overnight recovery + Banister CTL/TSB (💡)
    - Upcoming scheduled workout & target race periodization (⚡)
    """
    ctx = holistic_ctx or {
        "has_context": False,
        "week_runs_count": 0,
        "week_km": 0.0,
        "weekly_target_km": None,
        "recent_7d_km": 0.0,
        "consecutive_days": 0,
        "days_since_prev_run": None,
        "prev_hard_or_long": None,
        "comparable": None,
        "load": {"ctl": 0.0, "atl": 0.0, "tsb_post": 0.0, "has_load_history": False},
        "recovery": {"overnight_available": False, "readiness": "untracked"},
        "plan": {"has_plan": False, "tomorrow_workout": None, "next_key_workout": None},
        "race": None,
    }

    act_id = str(activity.get("id") or activity.get("name") or "")
    act_start = str(activity.get("start_time") or "")
    dist_km = round(float(activity.get("distance_meters") or 0.0) / 1000.0, 2)
    pace_sec = _parse_pace_to_sec(activity.get("avg_pace_str")) or 330
    seed_src = f"{act_id}:{act_start}:{dist_km}:{pace_sec}".encode("utf-8", errors="ignore")
    seed = int(hashlib.md5(seed_src).hexdigest()[:8], 16)

    lens_key, lead_block = _choose_lens_lead(
        activity=activity,
        profile=profile,
        holistic_ctx=ctx,
        plan_exec_block=plan_exec_block,
        seg_result=seg_result,
        seed=seed,
    )
    highlight_block = _build_highlight_block(lens_key, activity, ctx, seed)
    recovery_clause = _build_recovery_clause(lens_key, activity, profile, ctx, seed)
    forward_clause = _build_forward_clause(lens_key, ctx, seed)

    # Guard against forbidden substrings outside aligned plan comparisons
    if lens_key != "planned" and "达成率" in highlight_block:
        highlight_block = highlight_block.replace("达成率", "完成")

    age = get_age_from_dob((profile or {}).get("date_of_birth"))
    is_master_long = bool(age and age >= 50 and dist_km >= 10.0)
    is_trail = (lens_key == "trail") or _is_trail_record(activity)

    return _compact_critique(
        lead_block=lead_block,
        highlight_block=highlight_block,
        recovery_clause=recovery_clause,
        forward_clause=forward_clause,
        is_trail=is_trail,
        is_master_long=is_master_long,
        limit=226,
    )
