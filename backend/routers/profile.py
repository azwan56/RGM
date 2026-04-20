"""
Profile router — manages extended user attributes stored in Firestore.

Fields stored under users/{uid}:
  display_name, date_of_birth, gender, years_running,
  height_cm, weight_kg,
  marathon_pb_sec, half_pb_sec, ten_k_pb_sec, five_k_pb_sec,
  training_goal, phone, bio,
  upcoming_races (list of up to 3 race dicts)
  (strava_name, email are read-only — set by OAuth / Firebase Auth)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from firebase_config import db

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

EDITABLE_FIELDS = {
    "display_name", "date_of_birth", "gender", "years_running",
    "height_cm", "weight_kg",
    "marathon_pb_sec", "half_pb_sec", "ten_k_pb_sec", "five_k_pb_sec",
    "training_goal", "phone", "bio",
    "discord_webhook_url", "wecom_webhook_url",
    # upcoming_races handled separately as a list
}

READONLY_FIELDS = {"email", "strava_name", "strava_profile_url", "uid"}


def _format_pb(seconds: Optional[int]) -> Optional[str]:
    """Convert seconds to HH:MM:SS string."""
    if not seconds or seconds <= 0:
        return None
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ── GET profile ────────────────────────────────────────────────────────────────

@router.get("/{uid}")
def get_profile(uid: str):
    """Return the full user profile including formatted PB strings and computed age."""
    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    data = doc.to_dict() or {}

    # Strip sensitive / internal fields before returning
    safe = {k: v for k, v in data.items()
            if not k.startswith("strava_access") and not k.startswith("strava_refresh")}

    # Compute age from date_of_birth if present
    dob = data.get("date_of_birth")
    if dob:
        try:
            from datetime import date
            born = date.fromisoformat(dob)
            today = date.today()
            safe["age"] = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except (ValueError, TypeError):
            safe["age"] = data.get("age", 0)
    else:
        safe["age"] = data.get("age", 0)

    # Annotate with formatted PBs for display
    safe["marathon_pb_fmt"]  = _format_pb(data.get("marathon_pb_sec"))
    safe["half_pb_fmt"]      = _format_pb(data.get("half_pb_sec"))
    safe["ten_k_pb_fmt"]     = _format_pb(data.get("ten_k_pb_sec"))
    safe["five_k_pb_fmt"]    = _format_pb(data.get("five_k_pb_sec"))

    return safe


# ── POST update profile ────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    uid:              str
    display_name:     Optional[str]  = None
    date_of_birth:    Optional[str]  = None   # "YYYY-MM-DD"
    gender:           Optional[str]  = None   # "male" | "female" | "other"
    years_running:    Optional[int]  = None
    height_cm:        Optional[float] = None  # cm
    weight_kg:        Optional[float] = None  # kg
    marathon_pb_sec:  Optional[int]  = None   # seconds (0 = unset)
    half_pb_sec:      Optional[int]  = None
    ten_k_pb_sec:     Optional[int]  = None
    five_k_pb_sec:    Optional[int]  = None
    training_goal:    Optional[str]  = None   # "fitness"|"finish_marathon"|"pb"|"elite"
    phone:            Optional[str]  = None
    bio:              Optional[str]  = None
    upcoming_races:   Optional[List[dict]] = None  # list of up to 3 race dicts
    discord_webhook_url: Optional[str] = None   # Discord channel webhook URL
    wecom_webhook_url:   Optional[str] = None   # 企业微信机器人 webhook URL


@router.post("/update")
def update_profile(req: ProfileUpdate):
    """Partial-update user profile. Only provided (non-None) fields are written."""
    user_ref = db.collection("users").document(req.uid)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")

    updates = {}
    for field in EDITABLE_FIELDS:
        val = getattr(req, field, None)
        if val is not None:
            updates[field] = val

    # Handle upcoming_races list separately (max 3)
    if req.upcoming_races is not None:
        # Filter out past races and limit to 3
        from datetime import date
        valid = []
        for r in req.upcoming_races[:3]:
            race_date = r.get("date", "")
            if race_date:
                try:
                    if date.fromisoformat(race_date) < date.today():
                        continue  # skip past races
                except ValueError:
                    pass
            valid.append(r)
        updates["upcoming_races"] = valid

    if not updates:
        return {"message": "Nothing to update"}

    # Also keep leaderboard in sync if display_name changed
    if "display_name" in updates:
        try:
            db.collection("leaderboard").document(req.uid).set(
                {"display_name": updates["display_name"]}, merge=True
            )
        except Exception:
            pass  # Non-critical

    user_ref.set(updates, merge=True)
    return {"message": "Profile updated", "updated_fields": list(updates.keys())}


# ── GET runner persona ─────────────────────────────────────────────────────────

@router.get("/{uid}/persona")
def get_runner_persona(uid: str):
    """
    Compute the runner's archetype / persona based on:
    VDOT, marathon PB, years_running, age, gender, recent monthly mileage.
    Returns level (0-5), title, emoji, humorous description, and stat bars.
    """
    from firebase_config import db as firestore_db
    from datetime import date, timedelta

    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        raise HTTPException(404, "User not found")

    profile = doc.to_dict() or {}

    # ── Gather signals ─────────────────────────────────────────────────────────
    # Compute age from date_of_birth, fallback to legacy 'age' field
    dob = profile.get("date_of_birth")
    if dob:
        try:
            born = date.fromisoformat(dob)
            today = date.today()
            age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except (ValueError, TypeError):
            age = profile.get("age", 30)
    else:
        age = profile.get("age", 30)
    gender        = profile.get("gender", "other")
    years_running = profile.get("years_running", 0) or 0
    fm_pb_sec     = profile.get("marathon_pb_sec", 0) or 0  # 0 = no PB
    training_goal = profile.get("training_goal", "fitness")

    # VDOT — 42-day exponential decay (half-life 14 days), same as race-predictor
    import math as _math
    cutoff_42d = (date.today() - timedelta(days=42)).isoformat()
    HALF_LIFE  = 14.0
    acts = (db.collection("users").document(uid)
              .collection("activities")
              .order_by("start_date_local", direction="DESCENDING")
              .limit(80).stream())
    _wsum = 0.0; _wtot = 0.0; _fallback_v = None
    for _a in acts:
        _d  = _a.to_dict()
        _v  = _d.get("vdot")
        _r2 = float(_d.get("vdot_r2", 0) or 0)
        _dt = _d.get("start_date_local", "")[:10]
        if not _v or float(_v) < 20:
            continue
        if _fallback_v is None:
            _fallback_v = float(_v)
        if _dt >= cutoff_42d:
            _days = max((date.today() - date.fromisoformat(_dt)).days, 0)
            _q    = min(3.0, max(0.3, _math.exp(_r2 * 4)))
            _w    = _math.pow(2.0, -_days / HALF_LIFE) * _q
            _wsum += float(_v) * _w; _wtot += _w
    vdot = round(_wsum / _wtot, 1) if _wtot > 0 else (_fallback_v and round(_fallback_v, 1))

    # Monthly distance (this month)
    first_of_month = date.today().replace(day=1).isoformat()
    month_acts = (db.collection("users").document(uid)
                    .collection("activities")
                    .where("start_date_local", ">=", first_of_month)
                    .stream())
    monthly_km = sum(a.to_dict().get("distance_km", 0) for a in month_acts)

    # ── Determine level ────────────────────────────────────────────────────────
    score = 0
    if vdot:
        if vdot >= 58:   score += 5
        elif vdot >= 50: score += 4
        elif vdot >= 42: score += 3
        elif vdot >= 35: score += 2
        elif vdot >= 30: score += 1
    if fm_pb_sec > 0:
        if fm_pb_sec <= 10800:   score += 2   # sub-3h
        elif fm_pb_sec <= 12600: score += 1   # sub-3:30
    if years_running >= 5: score += 1
    if monthly_km >= 150:  score += 1

    level = min(score // 2, 5)  # 0..5

    # ── Dynamic persona builder ─────────────────────────────────────────────────
    _LEVEL_BASE = [
        {"emoji": "🛋️", "title": "沙发薯", "color": "#6b7280",
         "stats": {"耐力": 1, "速度": 1, "抗乳酸": 0, "朋友圈素材": 5, "放弃借口": 5}},
        {"emoji": "🐢", "title": "马路新手", "color": "#10b981",
         "stats": {"耐力": 2, "速度": 1, "抗乳酸": 1, "朋友圈素材": 4, "放弃借口": 3}},
        {"emoji": "🦘", "title": "跑圈游民", "color": "#f59e0b",
         "stats": {"耐力": 3, "速度": 2, "抗乳酸": 2, "朋友圈素材": 3, "放弃借口": 2}},
        {"emoji": "🏃", "title": "配速猎人", "color": "#3b82f6",
         "stats": {"耐力": 4, "速度": 3, "抗乳酸": 3, "朋友圈素材": 2, "放弃借口": 1}},
        {"emoji": "🔥", "title": "破风侠",   "color": "#f97316",
         "stats": {"耐力": 5, "速度": 4, "抗乳酸": 4, "朋友圈素材": 1, "放弃借口": 0}},
        {"emoji": "👑", "title": "跑界传说", "color": "#a855f7",
         "stats": {"耐力": 5, "速度": 5, "抗乳酸": 5, "朋友圈素材": 0, "放弃借口": 0}},
    ]

    pronoun   = "他" if gender == "male" else ("她" if gender == "female" else "TA")
    age_i     = int(age or 30)
    age_tag   = "老将" if age_i >= 45 else ("青壮派" if age_i <= 30 else "黄金年龄段")
    yr_str    = f"跑龄{years_running}年" if years_running >= 1 else "刚入坑"
    has_pb    = bool(fm_pb_sec)
    sub3      = has_pb and fm_pb_sec <= 10800
    sub330    = has_pb and fm_pb_sec <= 12600
    def _fmt_pb(sec: int) -> str:
        h, r = divmod(sec, 3600); m = r // 60; return f"{h}:{m:02d}"
    fm_pb_str  = _fmt_pb(fm_pb_sec) if has_pb else ""
    pb_ctx     = f"全马PB {fm_pb_str}" if has_pb else "还没有全马战绩"
    goal_speed = any(x in str(training_goal) for x in ["speed","race","marathon","半马PB","全马PB","提速","破PB"])
    goal_fit   = any(x in str(training_goal) for x in ["fitness","健康","health","减脂","体重"])

    _subtitles = {
        0: f"{age_tag}里的起步者",
        1: f"乌龟也是在跑的{age_tag}跑者",
        2: f"{'赛道'if goal_speed else '健康'}导向型稳定输出者",
        3: f"超越99%人类的{'黄金' if age_i<=45 else '资深'}配速手",
        4: f"令路人驻足的{age_tag}两足飞行器",
        5: "已不需要等级标签的存在",
    }
    _descs = {
        0: f"{yr_str}，{'立志第一个5K' if years_running < 1 else '每周都想跑但总有借口'}。"
           f"肌肉还在怀念上一次运动。{'目标是先跑健康' if goal_fit else '已经看上一场马拉松报名了'}，很好，很有精神。",
        1: f"{yr_str}，{'已能不停跑完10K' if years_running >= 1 else '刚完成第一个5K'}，路人可能认为在快走。"
           f"热情是真的，{pb_ctx}。{'以健康为主' if goal_fit else ('想尽快提速' if goal_speed else '慢慢享受过程')}。",
        2: f"{yr_str}，月跑量开始稳定输出。{pb_ctx}，"
           f"{'全马还是遥远传说' if not has_pb else ('还有提升空间' if not sub330 else '成绩不赖')}。"
           f"{'正在冲破PB' if goal_speed else '以健康为主，兼顾比赛乐趣'}。",
        3: f"{yr_str}，{pb_ctx}{'，破330射程之内' if not sub330 and has_pb else ''}。"
           f"路过的普通人以为{pronoun}在逃什么。"
           f"{'配速已稳，继续冲更快' if goal_speed else '月跑量三位数，全马只是基本操作'}。",
        4: f"{yr_str}，{pb_ctx}。{'sub-3:00在望' if sub330 and not sub3 else ('已破3小时，更高目标在路上' if sub3 else '成绩强劲持续进化')}。"
           f"配速让普通人觉得自己在原地踏步。{age_tag}里少见的实力派。",
        5: f"{yr_str}，{pb_ctx}。普通人看不见{pronoun}，只看见风。"
           f"比赛号码布多到可以装修一面墙。{'越野公路通吃' if 'ultra' in str(training_goal) or '越野' in str(training_goal) else '全马为王，配速随心'}。",
    }
    _facts = {
        0: "最快配速发生在便利店关门前五分钟",
        1: f"Strava曾把{yr_str}的{pronoun}识别为'散步'活动",
        2: f"已开始研究碳板跑鞋，但怀疑自己配不配穿{'（其实配的）' if has_pb else ''}",
        3: f"跑步途中能淡定接电话；目标是{'破' + fm_pb_str if has_pb and goal_speed else '跑得更从容'}，每天都在接近",
        4: f"超市有人问'是专业运动员吗'，{pronoun}礼貌否认，{'但sub-3的成绩说明一切' if sub3 else f'{age_i}岁的实力已经给出了答案'}",
        5: f"{'sub-3h彼岸的'if sub3 else ''}{yr_str}，休息日跑量是别人的训练日跑量",
    }

    base    = _LEVEL_BASE[level]
    persona = {
        **base,
        "level":       level,
        "subtitle":    _subtitles.get(level, ""),
        "description": _descs.get(level, ""),
        "fun_fact":    _facts.get(level, ""),
    }

    return {
        "level":         level,
        "gender":        gender,
        "age":           age_i,
        "vdot":          vdot,
        "monthly_km":    round(monthly_km, 1),
        "fm_pb_sec":     fm_pb_sec,
        "years_running": years_running,
        "training_goal": training_goal,
        **persona,
    }


# ── GET strava PBs ─────────────────────────────────────────────────────────────

@router.get("/{uid}/strava-pbs")
def get_strava_pbs(uid: str):
    """
    Derives personal bests entirely from the Firestore activity cache (no Strava API calls).

    For marathon & half marathon: the entire run IS the race, so moving_time is exact.
    For 10K & 5K: find the best-paced run in the distance range, normalise time to
    exactly 10.0km or 5.0km using the average pace.  This is the same method Strava
    uses internally for its "estimated best effort" badges.

    Why not use Strava best_efforts API?
    The /activities/{id}?include_all_efforts=true endpoint is slow (3-8s per call)
    and we'd need to call it for 5-10 candidate activities → 30-60s total, which
    causes HTTP timeouts in the browser.

    Trade-off: pace-normalised estimate may differ from a true 5K / 10K race PB
    by ±30s, but it's instant and already captures the best training run.
    Users can always override the imported value manually.

    Results are saved to Firestore only if the field is currently empty.
    """
    # ── Load user ─────────────────────────────────────────────────────────────
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(404, "User not found")

    profile = user_doc.to_dict() or {}

    # ── Scan all cached activities ────────────────────────────────────────────
    acts_stream = (db.collection("users").document(uid)
                     .collection("activities")
                     .order_by("start_date_local", direction="DESCENDING")
                     .limit(500)
                     .stream())
    activities = [d.to_dict() for d in acts_stream]

    # Distance categories: (key, min_m, max_m, normalise_km)
    CATS = [
        ("marathon", 41800, 99999,  None),   # full run = PB
        ("half",     20500, 30000,  None),   # full run = PB
        ("ten_k",     9800, 12000, 10.0),    # normalise to 10km
        ("five_k",    4750,  6500,  5.0),    # normalise to 5km
    ]

    def fmt(secs: int) -> str:
        h, r = divmod(int(secs), 3600)
        m, s  = divmod(r, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    results  = {}

    for key, d_min, d_max, norm_km in CATS:
        # Bucket: all runs in the distance range with valid moving_time
        bucket = [
            (a.get("moving_time", 0), a.get("distance_km", 0),
             a.get("activity_id", 0), a.get("name", ""))
            for a in activities
            if d_min <= a.get("distance_km", 0) * 1000 <= d_max
            and a.get("moving_time", 0) > 0
        ]
        if not bucket:
            results[key] = None
            continue

        # Sort by pace (moving_time / dist_km) then pick fastest
        bucket.sort(key=lambda x: x[0] / x[1] if x[1] else float("inf"))
        mt, dist_km, act_id, name = bucket[0]

        if norm_km:
            # Normalise pace to standard distance
            pace_sec_per_km = mt / dist_km
            final_secs = round(pace_sec_per_km * norm_km)
            source     = "estimated_from_pace"
            dist_out   = norm_km
        else:
            final_secs = mt
            source     = "strava_activity"
            dist_out   = round(dist_km, 2)

        results[key] = {
            "seconds":   final_secs,
            "formatted": fmt(final_secs),
            "distance":  dist_out,
            "source":    source,
            "note":      name,
        }

    # ── Auto-save if field is currently empty ─────────────────────────────────
    saves = {}
    field_map = {
        "marathon": "marathon_pb_sec",
        "half":     "half_pb_sec",
        "ten_k":    "ten_k_pb_sec",
        "five_k":   "five_k_pb_sec",
    }
    for key, firestore_field in field_map.items():
        if results[key] and not profile.get(firestore_field):
            saves[firestore_field] = results[key]["seconds"]

    if saves:
        user_ref.set(saves, merge=True)


    return {
        "pbs":        results,
        "auto_saved": list(saves.keys()),
    }






