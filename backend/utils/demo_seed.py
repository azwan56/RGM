"""
Demo account seeding for App Store review / product demos.

Creates (idempotently) a dedicated demo runner with fully synthetic data so the
iOS "演示账号体验登录" flow never exposes any real user's personal information.

Seeding is relative to "today", and is topped up on every demo login so the
dashboard / CTL-ATL / coach analysis always look populated:
  - profile (neutral name, no PII)
  - ~84 days of synthetic running activities (deterministic per date)
  - 30 days of synthetic daily health metrics
  - monthly mileage goal
  - one upcoming A race + one completed race
"""
import json
import random
import sqlite3
import logging
from datetime import timedelta, datetime

from utils.local_store import LocalStore, DB_PATH, get_beijing_today
from utils.running_metrics import calculate_trimp

logger = logging.getLogger("demo_seed")

DEMO_UID = "u_demo_runner"
DEMO_DISPLAY_NAME = "演示跑者"
DEMO_EMAIL = "demo@rgm.run"

ACTIVITY_DAYS = 84
HEALTH_DAYS = 30

# Weekly template (Mon=0 … Sun=6): (name, base_km, pace_sec_per_km, avg_hr) or None for rest day
WEEK_TEMPLATE = {
    0: None,
    1: ("间歇训练 6×1000m", 11.0, 285, 158),
    2: ("轻松跑", 8.0, 345, 138),
    3: ("节奏跑", 12.0, 300, 152),
    4: None,
    5: ("恢复跑", 6.0, 360, 132),
    6: ("周末长距离", 24.0, 330, 145),
}


def _pace_str(distance_m: float, moving_s: int) -> str:
    km = distance_m / 1000.0
    if km <= 0 or moving_s <= 0:
        return "—"
    total = int(round(moving_s / km))
    return f"{total // 60}:{total % 60:02d} /km"


def _seed_profile():
    LocalStore.upsert_profile(DEMO_UID, {
        "display_name": DEMO_DISPLAY_NAME,
        "email": DEMO_EMAIL,
        "avatar_url": "",
        "bio": "这是一个演示账号，所有数据均为系统生成的模拟数据。",
        "gender": "male",
        "height_cm": 175.0,
        "weight_kg": 66.0,
        "resting_heart_rate": 52,
        "max_heart_rate": 188,
        "years_running": 4,
        "marathon_pb": 12600,   # 3:30:00
        "half_pb": 6000,        # 1:40:00
        "ten_k_pb": 2700,       # 45:00
        "five_k_pb": 1290,      # 21:30
        "garmin_connected": 0,
        "coros_connected": 0,
    })


def _seed_activities(today):
    rows = []
    for offset in range(ACTIVITY_DAYS, -1, -1):
        d = today - timedelta(days=offset)
        tpl = WEEK_TEMPLATE.get(d.weekday())
        if not tpl:
            continue
        rng = random.Random(d.toordinal())
        name, base_km, base_pace, base_hr = tpl
        # Gradual build-up over the block (+0~15% volume)
        progress = (ACTIVITY_DAYS - offset) / ACTIVITY_DAYS
        km = round(base_km * (0.9 + 0.15 * progress) * rng.uniform(0.95, 1.05), 2)
        pace = int(base_pace * rng.uniform(0.97, 1.03))
        dist_m = km * 1000.0
        moving_s = int(km * pace)
        avg_hr = int(base_hr + rng.randint(-3, 3))
        start = datetime(d.year, d.month, d.day, 6, 30) + timedelta(minutes=rng.randint(0, 40))
        rows.append({
            "id": f"demo_act_{d.strftime('%Y%m%d')}",
            "user_id": DEMO_UID,
            "name": name,
            "sport_type": "Run",
            "start_time": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "distance_meters": round(dist_m, 1),
            "moving_time_seconds": moving_s,
            "elapsed_time_seconds": moving_s + rng.randint(30, 240),
            "elevation_gain_meters": round(rng.uniform(20, 120), 1),
            "average_heartrate": avg_hr,
            "max_heartrate": min(188, avg_hr + rng.randint(12, 22)),
            "average_cadence": round(rng.uniform(172, 182), 1),
            "avg_pace_str": _pace_str(dist_m, moving_s),
            "calories": int(km * 62),
            "aerobic_training_effect": round(rng.uniform(2.8, 4.2), 1),
            "anaerobic_training_effect": round(rng.uniform(0.5, 2.5), 1),
            "trimp": calculate_trimp(moving_s / 60.0, avg_hr, 52, 188, "male"),
        })

    cols = [
        "id", "user_id", "name", "sport_type", "start_time", "distance_meters",
        "moving_time_seconds", "elapsed_time_seconds", "elevation_gain_meters",
        "average_heartrate", "max_heartrate", "average_cadence", "avg_pace_str",
        "calories", "aerobic_training_effect", "anaerobic_training_effect", "trimp", "ai_journal",
    ]
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        existing = {r[0] for r in cur.execute(
            "SELECT id FROM activities WHERE user_id = ?", (DEMO_UID,)
        ).fetchall()}
        inserted = 0
        for r in rows:
            if r["id"] in existing:
                cur.execute(
                    "UPDATE activities SET trimp = ? WHERE id = ? AND (trimp IS NULL OR trimp = 0)",
                    (r["trimp"], r["id"]),
                )
                continue
            try:
                r["ai_journal"] = LocalStore.generate_canova_critique(r)
            except Exception:
                r["ai_journal"] = ""
            cur.execute(
                f"INSERT OR IGNORE INTO activities ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
                [r.get(c) for c in cols],
            )
            inserted += 1
        conn.commit()
    return inserted


def _seed_health(today):
    for offset in range(HEALTH_DAYS, -1, -1):
        d = today - timedelta(days=offset)
        rng = random.Random(d.toordinal() * 7)
        sleep_h = round(rng.uniform(6.6, 8.2), 2)
        LocalStore.upsert_daily_health(DEMO_UID, {
            "date": d.isoformat(),
            "resting_heart_rate": rng.randint(49, 55),
            "vo2_max": 52.0,
            "sleep_duration_hours": sleep_h,
            "sleep_duration_seconds": int(sleep_h * 3600),
            "sleep_score": rng.randint(72, 90),
            "body_battery_max": rng.randint(70, 95),
            "body_battery_min": rng.randint(15, 35),
            "hrv_status": "BALANCED",
            "hrv_weekly_avg": 62.0,
            "hrv_last_night_avg": float(rng.randint(55, 70)),
        })


def _seed_races(today):
    LocalStore.upsert_race_plan(DEMO_UID, {
        "id": "demo_race_upcoming",
        "name": "城市马拉松（演示）",
        "race_type": "全马",
        "race_date": (today + timedelta(days=70)).isoformat(),
        "target_time": "3:25:00",
        "priority": 1,
        "status": "upcoming",
    })
    LocalStore.upsert_race_plan(DEMO_UID, {
        "id": "demo_race_done",
        "name": "春季半程马拉松（演示）",
        "race_type": "半马",
        "race_date": (today - timedelta(days=45)).isoformat(),
        "target_time": "1:40:00",
        "priority": 2,
        "status": "completed",
        "finish_time": "1:38:42",
        "finish_notes": "前程控速，后程渐进，顺利达成目标。",
    })


def ensure_demo_account() -> dict:
    """Idempotently create / top up the demo account. Returns the profile dict."""
    today = get_beijing_today()
    _seed_profile()
    try:
        n = _seed_activities(today)
        logger.info(f"[demo_seed] inserted {n} demo activities")
    except Exception as e:
        logger.warning(f"[demo_seed] activities seeding failed: {e}")
    try:
        _seed_health(today)
    except Exception as e:
        logger.warning(f"[demo_seed] health seeding failed: {e}")
    try:
        LocalStore.upsert_goal(DEMO_UID, {"target_distance": 200.0, "weekly_target": 50.0, "period_type": "monthly"})
    except Exception as e:
        logger.warning(f"[demo_seed] goal seeding failed: {e}")
    try:
        _seed_races(today)
    except Exception as e:
        logger.warning(f"[demo_seed] race seeding failed: {e}")
    return LocalStore.get_profile(DEMO_UID) or {"id": DEMO_UID, "display_name": DEMO_DISPLAY_NAME}
