import json
import sqlite3 as real_sqlite3
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

import routers.miniapp as miniapp_router
import utils.local_store as ls_mod
from config import settings
from main import app
from utils.local_store import RUNNING_SQL_FILTER, LocalStore, init_db


def _make_jwt(uid: str) -> str:
    payload = {
        "sub": uid,
        "uid": uid,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "miniapp_perf_test.db")
    monkeypatch.setattr(ls_mod, "DB_PATH", db_file)
    monkeypatch.setattr(miniapp_router, "DB_PATH", db_file)
    LocalStore.invalidate_uid_cache()
    init_db()
    yield db_file
    LocalStore.invalidate_uid_cache()


def _seed_runner_with_club_org_and_events(db_path: str, uid: str = "u_perf_runner_1"):
    LocalStore.upsert_profile(
        uid,
        {
            "id": uid,
            "email": f"{uid}@example.com",
            "display_name": "性能压测跑者",
            "gender": "male",
            "date_of_birth": "1990-05-20",
            "height_cm": 175.0,
            "weight_kg": 66.0,
            "resting_heart_rate": 52,
            "max_heart_rate": 190,
            "garmin_connected": True,
        },
    )

    today = LocalStore.get_beijing_today()
    now_bj = datetime.utcnow() + timedelta(hours=8)
    meet_dt_str = (now_bj + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
    meet_date_str = (now_bj + timedelta(hours=24)).strftime("%Y-%m-%d")

    with real_sqlite3.connect(db_path) as conn:
        now_iso = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT OR REPLACE INTO goals (user_id, target_distance, weekly_target)
            VALUES (?, ?, ?)
            """,
            (uid, 200.0, 50.0),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO organizations (id, name, owner_id, invite_code, join_mode, settings, created_at)
            VALUES (?, ?, ?, ?, 'invite', '{}', ?)
            """,
            ("org_perf_1", "性能大群", uid, "ORGPERF1", now_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO organization_members
            (id, org_id, user_id, role, status, real_name, gender, date_of_birth, class_name, joined_at, confirmed_by, confirmed_at)
            VALUES (?, ?, ?, 'owner', 'confirmed', ?, 'male', ?, '2025班', ?, ?, ?)
            """,
            ("om_perf_1", "org_perf_1", uid, "测试员", "1990-05-20", now_iso, uid, now_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO clubs (id, name, owner_id, org_id, invite_code, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            ("club_perf_1", "极速一分队", uid, "org_perf_1", "CLUBPERF1", now_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at)
            VALUES (?, ?, ?, 'owner', 'active', ?)
            """,
            ("cm_perf_1", "club_perf_1", uid, now_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO club_events
            (id, club_id, title, event_type, start_date, meet_time, location, creator_id, status, created_at)
            VALUES (?, ?, ?, 'group_run', ?, ?, '世纪公园一号门', ?, 'upcoming', ?)
            """,
            ("evt_perf_next", "club_perf_1", "周末LSD约跑", meet_date_str, meet_dt_str, uid, now_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO club_event_participants
            (id, event_id, club_id, user_id, status, pace_group, runner_role, joined_at)
            VALUES (?, ?, ?, ?, 'joined', '🏃 有氧组', '跟跑团员', ?)
            """,
            ("part_perf_1", "evt_perf_next", "club_perf_1", uid, now_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO system_notifications
            (id, user_id, title, content, type, is_read, created_at)
            VALUES (?, ?, '约跑提醒', '明早世纪公园集合', 'group_run', 0, ?)
            """,
            ("notif_perf_1", uid, now_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO support_tickets
            (id, user_id, category, content, status, diagnostic_context, created_at)
            VALUES (?, ?, 'bug', '反馈记录测试', 'open', '{}', ?)
            """,
            ("tkt_perf_1", uid, now_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO daily_health
            (user_id, date, resting_heart_rate, sleep_score, sleep_duration_seconds,
             body_battery_max, hrv_last_night_avg, hrv_weekly_avg, hrv_status, updated_at)
            VALUES (?, ?, 50, 88, 27000, 92, 68, 64, 'BALANCED', ?)
            """,
            (uid, today.isoformat(), now_iso),
        )
        conn.commit()

    # Insert 5 runs in the current calendar month (pre-populated critiques for warm perf budget)
    for i in range(5):
        day_num = max(1, today.day - i)
        act_date = today.replace(day=day_num).isoformat()
        LocalStore.upsert_activity(
            {
                "id": f"garmin_perf_run_{i}",
                "user_id": uid,
                "name": f"晨跑有氧 #{i+1}",
                "sport_type": "Run",
                "start_time": f"{act_date}T06:3{i}:00+08:00",
                "distance_meters": 10000.0 + i * 500,
                "moving_time_seconds": 3000 + i * 120,
                "elapsed_time_seconds": 3020 + i * 120,
                "average_heartrate": 148.0,
                "avg_pace_str": "5:00 /km",
                "trimp": 92.0,
                "ai_journal": "有氧耐力稳固构建，节奏平稳。",
            },
            notify=False,
            reconcile_plan=False,
        )


def test_explain_query_plan_uses_indexes(isolated_db):
    _seed_runner_with_club_org_and_events(isolated_db)
    with real_sqlite3.connect(isolated_db) as conn:
        # 1. profiles lookup queries (no full SCAN profiles)
        for col, val in (
            ("id", "u_perf_runner_1"),
            ("email", "u_perf_runner_1@example.com"),
            ("display_name", "性能压测跑者"),
        ):
            plan = " | ".join(
                str(r[3])
                for r in conn.execute(
                    f"EXPLAIN QUERY PLAN SELECT id FROM profiles WHERE {col} = ? LIMIT 1",
                    (val,),
                ).fetchall()
            )
            assert "SCAN profiles" not in plan, f"Unexpected table scan for profiles.{col}: {plan}"

        # 2. recent activities uses idx_activities_user_start without TEMP B-TREE
        recent_plan = " | ".join(
            str(r[3])
            for r in conn.execute(
                f"""
                EXPLAIN QUERY PLAN
                SELECT id FROM activities
                WHERE user_id = ? AND {RUNNING_SQL_FILTER}
                ORDER BY start_time DESC LIMIT 100
                """,
                ("u_perf_runner_1",),
            ).fetchall()
        )
        assert "idx_activities_user_start" in recent_plan, f"Missing index on recent activities: {recent_plan}"
        assert "USE TEMP B-TREE FOR ORDER BY" not in recent_plan, f"Temp B-Tree on recent activities: {recent_plan}"

        # 3. month activities uses idx_activities_user_start without TEMP B-TREE
        month_plan = " | ".join(
            str(r[3])
            for r in conn.execute(
                f"""
                EXPLAIN QUERY PLAN
                SELECT id FROM activities
                WHERE user_id = ? AND start_time >= ? AND start_time < ? AND {RUNNING_SQL_FILTER}
                ORDER BY start_time DESC
                """,
                ("u_perf_runner_1", "2026-11-01", "2026-12-01"),
            ).fetchall()
        )
        assert "idx_activities_user_start" in month_plan, f"Missing index on month activities: {month_plan}"
        assert "USE TEMP B-TREE FOR ORDER BY" not in month_plan, f"Temp B-Tree on month activities: {month_plan}"

        # 4. captain_cheer range window uses idx_activities_user_start
        cheer_plan = " | ".join(
            str(r[3])
            for r in conn.execute(
                f"""
                EXPLAIN QUERY PLAN
                SELECT id FROM activities
                WHERE user_id IN (?, ?) AND start_time >= ? AND start_time < ? AND {RUNNING_SQL_FILTER}
                ORDER BY start_time ASC
                """,
                ("u_perf_runner_1", "alias_uid", "2026-10-01", "2026-12-01"),
            ).fetchall()
        )
        assert "idx_activities_user_start" in cheer_plan, f"Missing index on captain_cheer window: {cheer_plan}"


def test_empty_ai_journal_critique_converges(isolated_db):
    uid = "u_critique_conv"
    LocalStore.upsert_profile(
        uid,
        {
            "id": uid,
            "display_name": "批注收敛跑者",
            "gender": "female",
            "resting_heart_rate": 54,
            "max_heart_rate": 188,
        },
    )
    today = LocalStore.get_beijing_today()
    for idx in range(2):
        act_id = f"garmin_empty_j_{idx}"
        LocalStore.upsert_activity(
            {
                "id": act_id,
                "user_id": uid,
                "name": f"节奏跑 #{idx}",
                "sport_type": "Run",
                "start_time": f"{today.isoformat()}T07:0{idx}:00+08:00",
                "distance_meters": 8000.0,
                "moving_time_seconds": 2400,
                "average_heartrate": 150.0,
                "avg_pace_str": "5:00 /km",
                "trimp": 72.0,
                "ai_journal": "",
            },
            notify=False,
            reconcile_plan=False,
        )
        with real_sqlite3.connect(isolated_db) as conn:
            conn.execute("UPDATE activities SET ai_journal = '' WHERE id = ?", (act_id,))
            conn.commit()

    with patch.object(
        LocalStore, "generate_canova_critique", wraps=LocalStore.generate_canova_critique
    ) as spy_gen:
        first_month = LocalStore.get_month_activities(uid, today.year, today.month)
        assert len(first_month) == 2
        assert all((a.get("ai_journal") or "").strip() for a in first_month)
        assert spy_gen.call_count == 2

    with real_sqlite3.connect(isolated_db) as conn:
        persisted = conn.execute(
            "SELECT ai_journal FROM activities WHERE user_id = ? ORDER BY start_time DESC",
            (uid,),
        ).fetchall()
        assert len(persisted) == 2
        assert all((r[0] or "").strip() for r in persisted)

    with patch.object(
        LocalStore, "generate_canova_critique", wraps=LocalStore.generate_canova_critique
    ) as spy_gen_warm:
        second_month = LocalStore.get_month_activities(uid, today.year, today.month)
        second_recent = LocalStore.get_recent_activities(uid, limit=10)
        assert len(second_month) == 2
        assert len(second_recent) == 2
        assert spy_gen_warm.call_count == 0


def test_miniapp_dashboard_bundle_perf_and_compat(isolated_db):
    uid = "u_perf_runner_1"
    _seed_runner_with_club_org_and_events(isolated_db, uid=uid)
    headers = {"Authorization": f"Bearer {_make_jwt(uid)}", "x-user-id": uid}
    client = TestClient(app)

    # Cold / warm baseline population (also persists any missing empty critiques)
    r_cold = client.get(
        f"/api/miniapp/dashboard/{uid}?include_home_extras=1&lite_activities=1",
        headers=headers,
    )
    assert r_cold.status_code == 200
    d_cold = r_cold.json()
    assert d_cold["unread_notif_count"] == 1
    assert d_cold["onboarding_status"]["is_completed"] is True
    assert len(d_cold["organizations"]) == 1
    assert d_cold["next_group_run"] is not None
    assert d_cold["next_group_run"]["id"] == "evt_perf_next"
    assert d_cold["current_month_info"]["total_count"] == 5
    assert len(d_cold["current_month_activities"]) == 3

    # Warm call budget measurement
    conn_count = 0
    sql_count = 0
    orig_connect = real_sqlite3.connect

    def _inc_sql(stmt: str):
        nonlocal sql_count
        if not stmt.lstrip().upper().startswith("PRAGMA"):
            sql_count += 1

    def traced_connect(*args, **kwargs):
        nonlocal conn_count
        conn_count += 1
        c = orig_connect(*args, **kwargs)
        c.set_trace_callback(_inc_sql)
        return c

    with patch.object(real_sqlite3, "connect", side_effect=traced_connect):
        r_warm = client.get(
            f"/api/miniapp/dashboard/{uid}?include_home_extras=1&lite_activities=1",
            headers=headers,
        )
    assert r_warm.status_code == 200
    assert conn_count <= 15, f"Too many SQLite connections on warm dashboard bundle: {conn_count}"
    assert sql_count <= 25, f"Too many SQL statements on warm dashboard bundle: {sql_count}"

    # Default dashboard call without flags remains 100% backward compatible (returns all 5 month acts)
    r_default = client.get(f"/api/miniapp/dashboard/{uid}", headers=headers)
    assert r_default.status_code == 200
    d_default = r_default.json()
    assert len(d_default["current_month_activities"]) == 5
    assert d_default["current_month_info"]["total_count"] == 5


def test_profile_miniapp_bundle(isolated_db):
    uid = "u_perf_runner_1"
    _seed_runner_with_club_org_and_events(isolated_db, uid=uid)
    headers = {"Authorization": f"Bearer {_make_jwt(uid)}", "x-user-id": uid}
    client = TestClient(app)

    res = client.get(f"/api/profile/{uid}?include_miniapp_bundle=1", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "organizations" in data and len(data["organizations"]) == 1
    assert "onboarding_status" in data
    assert "yearly_stats" in data
    assert data["yearly_stats"]["total_runs"] == 5
    assert len(data["yearly_stats"]["monthly_breakdown"]) == 12
    assert "vdot" in data
    assert "support_tickets" in data and len(data["support_tickets"]) == 1
