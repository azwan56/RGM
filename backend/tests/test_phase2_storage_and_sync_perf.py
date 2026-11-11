import asyncio
import json
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import utils.local_store as ls_mod
from main import app
from routers.sync import _resolve_incremental_sync_window, sync_single_user
from utils.encryption import encrypt_string
from utils.local_store import DB_PATH, LocalStore, init_db, sqlite3


def _make_jwt(uid: str) -> str:
    import time
    import jwt
    from config import settings

    payload = {
        "sub": uid,
        "uid": uid,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


def test_activity_streams_cold_hot_separation_and_legacy_migration():
    uid = "u_phase2_streams_user"
    LocalStore.upsert_profile(uid, {"id": uid, "display_name": "轨迹冷热分离测试员"})

    # 1,200 full-resolution telemetry points (~150KB JSON)
    full_points = [
        {
            "lat": round(31.2000 + i * 0.00005, 6),
            "lng": round(121.4000 + i * 0.00005, 6),
            "ele": round(8.0 + (i % 15) * 0.2, 1),
            "hr": 145 + (i % 12),
            "cadence": 180,
            "t": i * 3,
        }
        for i in range(1200)
    ]
    act_id = "garmin_phase2_stream_1200"
    today_iso = LocalStore.get_beijing_today().isoformat()
    LocalStore.upsert_activity(
        {
            "id": act_id,
            "user_id": uid,
            "name": "世纪公园节奏跑",
            "sport_type": "Run",
            "start_time": f"{today_iso}T06:30:00+08:00",
            "distance_meters": 15000.0,
            "moving_time_seconds": 4200,
            "elapsed_time_seconds": 4230,
            "average_heartrate": 152.0,
            "avg_pace_str": "4:40 /km",
            "trimp": 118.0,
            "gps_track_data": {"points": full_points, "laps": [{"lap": 1, "distance_m": 1000}]},
        },
        notify=False,
        reconcile_plan=False,
    )

    with sqlite3.connect(DB_PATH) as conn:
        raw_act = conn.execute(
            "SELECT gps_track_data, route_preview_json, has_gps_track FROM activities WHERE id = ?",
            (act_id,),
        ).fetchone()
        stream_row = conn.execute(
            "SELECT gps_track_data FROM activity_streams WHERE activity_id = ?",
            (act_id,),
        ).fetchone()

    assert raw_act is not None
    assert raw_act[0] is None, "Full GPS blob must NOT remain inline on hot activities table"
    assert raw_act[1] is not None, "Compact route_preview_json must be populated on activities"
    assert int(raw_act[2] or 0) == 1
    preview_obj = json.loads(raw_act[1])
    assert len(preview_obj["points"]) <= 250

    assert stream_row is not None
    full_stream_obj = json.loads(stream_row[0])
    assert len(full_stream_obj["points"]) == 1200

    # List endpoint receives compact preview (`<= 250` points)
    recent_list = LocalStore.get_recent_activities(uid, limit=5)
    matched = [a for a in recent_list if a["id"] == act_id]
    assert matched
    list_preview = json.loads(matched[0]["gps_track_data"])
    assert len(list_preview["points"]) <= 250

    # Detail track endpoint receives full 1,200-point stream from activity_streams
    detail_row = LocalStore.get_activity_gps_track(act_id)
    assert detail_row is not None
    raw_detail_gps = detail_row["gps_track_data"]
    detail_track = raw_detail_gps if isinstance(raw_detail_gps, dict) else json.loads(raw_detail_gps)
    assert len(detail_track["points"]) == 1200

    # Verify legacy inline migration in init_db()
    legacy_id = "garmin_phase2_legacy_inline"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO activities
            (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, gps_track_data)
            VALUES (?, ?, '旧版内联轨迹', 'Run', ?, 5000, 1500, ?)
            """,
            (legacy_id, uid, f"{today_iso}T07:30:00+08:00", json.dumps({"points": full_points[:600]})),
        )
        conn.commit()

    init_db()

    with sqlite3.connect(DB_PATH) as conn:
        migrated_act = conn.execute(
            "SELECT gps_track_data, route_preview_json, has_gps_track FROM activities WHERE id = ?",
            (legacy_id,),
        ).fetchone()
        migrated_stream = conn.execute(
            "SELECT gps_track_data FROM activity_streams WHERE activity_id = ?",
            (legacy_id,),
        ).fetchone()

    assert migrated_act[0] is None
    assert int(migrated_act[2] or 0) == 1
    assert len(json.loads(migrated_act[1])["points"]) <= 250
    assert len(json.loads(migrated_stream[0])["points"]) == 600


def test_coach_cockpit_batch_query_budget_and_zero_writes_on_get():
    coach_uid = "u_phase2_coach"
    club_id = "club_phase2_perf_25"
    today = LocalStore.get_beijing_today()

    LocalStore.upsert_profile(coach_uid, {"id": coach_uid, "display_name": "总教练Phase2"})
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO clubs (id, name, description, invite_code, owner_id, join_mode, status, created_at)
            VALUES (?, '万跑性能基准团', '25人批量查询压测', 'PH2PRF', ?, 'open', 'active', ?)
            """,
            (club_id, coach_uid, datetime.utcnow().isoformat() + "Z"),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
            VALUES (?, ?, ?, 'owner', 'active', ?, 1)
            """,
            (f"{club_id}_{coach_uid}", club_id, coach_uid, datetime.utcnow().isoformat() + "Z"),
        )
        conn.commit()

    # Seed 24 additional students with activities, health, goals, races, and active plans
    for i in range(24):
        s_uid = f"u_phase2_stu_{i:02d}"
        LocalStore.upsert_profile(
            s_uid,
            {
                "id": s_uid,
                "display_name": f"队员_{i:02d}",
                "garmin_connected": 1,
                "marathon_pb": 11400 + i * 60,
                "max_heart_rate": 192,
                "resting_heart_rate": 52,
            },
        )
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, 'member', 'active', ?, 1)
                """,
                (f"{club_id}_{s_uid}", club_id, s_uid, datetime.utcnow().isoformat() + "Z"),
            )
            conn.commit()

        for d_off in range(7):
            d_str = (today - timedelta(days=d_off)).isoformat()
            LocalStore.upsert_daily_health(
                s_uid,
                {
                    "date": d_str,
                    "resting_heart_rate": 51,
                    "sleep_score": 82,
                    "sleep_duration_seconds": 27000,
                    "hrv_last_night_avg": 64,
                    "hrv_weekly_avg": 62,
                    "hrv_status": "BALANCED",
                },
            )

        LocalStore.upsert_activity(
            {
                "id": f"garmin_p2_{i:02d}_run1",
                "user_id": s_uid,
                "name": "有氧慢跑",
                "sport_type": "Run",
                "start_time": f"{(today - timedelta(days=1)).isoformat()}T06:20:00+08:00",
                "distance_meters": 10000.0 + i * 200,
                "moving_time_seconds": 3000,
                "average_heartrate": 146.0,
                "avg_pace_str": "5:00 /km",
                "trimp": 72.0,
            },
            notify=False,
            reconcile_plan=False,
        )
        LocalStore.upsert_goal(s_uid, {"target_distance": 220.0, "weekly_target": 55.0})
        LocalStore.upsert_training_plan(
            {
                "id": f"plan_p2_{i:02d}",
                "user_id": s_uid,
                "club_id": club_id,
                "title": "全马专项四周课表",
                "goal_type": "full_marathon",
                "start_date": (today - timedelta(days=3)).isoformat(),
                "status": "active",
                "schedule_data": {
                    "weeks": [
                        {
                            "week_index": 1,
                            "days": [
                                {
                                    "date": (today - timedelta(days=1)).isoformat(),
                                    "day_of_week": 1,
                                    "workout_type": "easy_run",
                                    "title": "轻松跑 10km",
                                    "distance_km": 10.0,
                                },
                                {
                                    "date": today.isoformat(),
                                    "day_of_week": 2,
                                    "workout_type": "tempo",
                                    "title": "乳酸阈跑 12km",
                                    "distance_km": 12.0,
                                },
                            ],
                        }
                    ]
                },
            }
        )

    executed_sql = []
    orig_connect = ls_mod._raw_sqlite3.connect

    def _tracing_connect(*args, **kwargs):
        conn = orig_connect(*args, **kwargs)
        conn.set_trace_callback(lambda stmt: executed_sql.append(stmt.strip()))
        return conn

    with patch.object(ls_mod._raw_sqlite3, "connect", side_effect=_tracing_connect):
        executed_sql.clear()
        assert LocalStore.is_club_owner_or_coach(club_id, coach_uid) is True
        perm_queries = [s for s in executed_sql if not s.upper().startswith("PRAGMA")]
        assert len(perm_queries) <= 4, f"Expected <=4 permission SQL queries, got {len(perm_queries)}"

        executed_sql.clear()
        students = LocalStore.get_coach_students_metrics(club_id, coach_uid)
        cockpit_queries = [s for s in executed_sql if not s.upper().startswith("PRAGMA")]
        write_queries = [
            s for s in cockpit_queries
            if s.upper().startswith(("UPDATE ", "INSERT ", "DELETE ", "REPLACE "))
        ]

    assert len(students) == 25
    assert len(cockpit_queries) <= 16, (
        f"N+1 regression! Expected <=16 batch SQL queries for 25 students, got {len(cockpit_queries)}"
    )
    assert len(write_queries) == 0, f"GET coach metrics must perform 0 DB writes, got: {write_queries}"

    stu_sample = next(s for s in students if s["user_id"] == "u_phase2_stu_00")
    assert stu_sample["km_7d"] >= 10.0
    assert stu_sample["recovery_data_available"] is True
    assert stu_sample["plan_info"]["has_active_plan"] is True
    assert stu_sample["plan_info"]["week_execution"]["workouts_completed"] == 1


def test_zero_ghost_profile_on_miniapp_dashboard_and_yearly_stats_default_year():
    ghost_uid = "u_phase2_never_created_ghost"
    client = TestClient(app)
    resp = client.get(f"/api/miniapp/dashboard/{ghost_uid}")
    assert resp.status_code == 200
    assert LocalStore.get_profile(ghost_uid) is None, "GET /dashboard/{uid} must NOT write ghost profiles"

    stats = LocalStore.get_yearly_stats("u_phase2_stu_00")
    assert stats["year"] == LocalStore.get_beijing_today().year
    assert len(stats["monthly_breakdown"]) == 12
    assert stats["total_runs"] >= 1


def test_sync_incremental_window_nondestructive_coros_and_cross_brand_dedup():
    uid = "u_phase2_dual_watch"
    today = LocalStore.get_beijing_today()
    yesterday_iso = (today - timedelta(days=1)).isoformat()

    LocalStore.upsert_profile(
        uid,
        {
            "id": uid,
            "display_name": "双表跑者",
            "weight_kg": 64.5,
            "height_cm": 176.0,
            "max_heart_rate": 198,
            "resting_heart_rate": 46,
            "garmin_connected": 1,
            "garmin_email": "dual@example.com",
            "garmin_encrypted_password": encrypt_string("garmin_secret"),
            "garmin_last_sync_at": f"{yesterday_iso}T08:00:00Z",
            "coros_connected": 1,
            "coros_account": "13800138000",
            "coros_encrypted_password": encrypt_string("coros_secret"),
            "coros_last_sync_at": f"{yesterday_iso}T08:00:00Z",
        },
    )

    # First sync (no prior brand activities in DB) -> falls back to full YTD
    start_init, h_days_init = _resolve_incremental_sync_window(
        uid=uid,
        brand_prefix="coros",
        explicit_start_date=None,
        last_sync_iso=f"{yesterday_iso}T08:00:00Z",
        default_health_days=30,
    )
    assert start_init == f"{today.year}-01-01"
    assert h_days_init == 30

    # Seed one historical activity per brand so subsequent auto-sync uses incremental window
    for prefix in ("garmin", "coros"):
        LocalStore.upsert_activity(
            {
                "id": f"{prefix}_seed_old",
                "user_id": uid,
                "name": "历史跑",
                "sport_type": "Run",
                "start_time": f"{(today - timedelta(days=10)).isoformat()}T07:00:00+08:00",
                "distance_meters": 8000.0,
                "moving_time_seconds": 2400,
            },
            notify=False,
            reconcile_plan=False,
        )

    inc_start, inc_h_days = _resolve_incremental_sync_window(
        uid=uid,
        brand_prefix="coros",
        explicit_start_date=None,
        last_sync_iso=f"{yesterday_iso}T08:00:00Z",
        default_health_days=30,
    )
    assert inc_start == max(date(today.year, 1, 1), today - timedelta(days=4)).isoformat()
    assert inc_h_days == 3

    garmin_calls = {}
    coros_calls = {}

    class FakeGarminAdapter:
        last_error = None

        def __init__(self, *args, **kwargs):
            pass

        def fetch_user_profile_info(self):
            return {"vo2max": 58.0}

        def fetch_activities_by_date(self, start_date):
            garmin_calls["start_date"] = start_date
            return [
                {
                    "id": "garmin_dual_morning",
                    "name": "晨跑10公里(Garmin)",
                    "sport_type": "Run",
                    "start_time": f"{today.isoformat()}T06:30:00+08:00",
                    "distance_meters": 10020.0,
                    "moving_time_seconds": 2850,
                    "average_heartrate": 151.0,
                    "avg_pace_str": "4:44 /km",
                }
            ]

        def fetch_daily_health_metrics(self, d):
            garmin_calls.setdefault("health_dates", []).append(d)
            return None

        def fetch_activity_gps_track(self, act_id):
            return None

    class FakeCorosAdapter:
        last_error = None
        needs_2fa = False
        _login_failed = False

        def __init__(self, *args, **kwargs):
            pass

        def login(self, trigger_2fa_sms=False):
            return True

        def fetch_user_profile_info(self):
            # Returns default/stale uncalibrated COROS biometrics that MUST NOT overwrite user's calibrated values
            return {
                "weight_kg": 70.0,
                "max_heart_rate": 185,
                "resting_heart_rate": 60,
                "vo2max": 59.0,
            }

        def fetch_activities_by_date(self, start_date):
            coros_calls["start_date"] = start_date
            return [
                # Duplicate of garmin_dual_morning (+70s start offset, +60m distance diff -> within ±15min & ±12%)
                {
                    "id": "coros_dual_morning_dup",
                    "name": "晨跑10公里(COROS)",
                    "sport_type": "Run",
                    "start_time": f"{today.isoformat()}T06:31:10+08:00",
                    "distance_meters": 10080.0,
                    "moving_time_seconds": 2855,
                    "average_heartrate": 152.0,
                    "avg_pace_str": "4:43 /km",
                },
                # Distinct evening recovery jog only recorded on COROS -> must be kept!
                {
                    "id": "coros_evening_jog",
                    "name": "傍晚排酸慢跑",
                    "sport_type": "Run",
                    "start_time": f"{today.isoformat()}T19:15:00+08:00",
                    "distance_meters": 5200.0,
                    "moving_time_seconds": 1750,
                    "average_heartrate": 132.0,
                    "avg_pace_str": "5:36 /km",
                },
            ]

        def fetch_daily_health_metrics(self, d):
            coros_calls.setdefault("health_dates", []).append(d)
            return None

        def fetch_activity_gps_track(self, act_id, sport_type_hint=None):
            return None

    with patch("routers.sync.GarminAdapter", FakeGarminAdapter), patch(
        "routers.sync.CorosAdapter", FakeCorosAdapter
    ):
        res = sync_single_user(uid)

    assert res["success"] is True
    assert res["skipped_cross_brand_duplicates"] == 1
    assert res["synced_activities"] == 2  # garmin_dual_morning + coros_evening_jog
    assert len(coros_calls["health_dates"]) == 3  # 3 incremental days instead of 30!

    updated_prof = LocalStore.get_profile(uid)
    assert float(updated_prof["weight_kg"]) == 64.5, "COROS sync must not overwrite calibrated weight_kg"
    assert int(updated_prof["max_heart_rate"]) == 198, "COROS sync must not overwrite calibrated max_heart_rate"
    assert int(updated_prof["resting_heart_rate"]) == 46, "COROS sync must not overwrite calibrated resting_heart_rate"

    acts_after = LocalStore.get_recent_activities(uid, limit=10)
    ids_after = {a["id"] for a in acts_after}
    assert "garmin_dual_morning" in ids_after
    assert "coros_evening_jog" in ids_after
    assert "coros_dual_morning_dup" not in ids_after


def test_unified_scheduler_and_nonblocking_screenshot_upload():
    import scheduler.tasks as sched_tasks

    with patch.object(sched_tasks.settings, "ENABLE_SCHEDULER", True), patch.object(
        sched_tasks.scheduler, "start"
    ), patch.object(sched_tasks.scheduler, "add_job") as mock_add_job:
        sched_tasks.start_scheduler()

    job_ids = [c.kwargs.get("id") for c in mock_add_job.call_args_list]
    assert "periodic_watch_sync" in job_ids
    assert "overnight_watch_sync" in job_ids
    assert "morning_pre_push_sync" not in job_ids
    assert "daytime_activity_nap_stress_sync" not in job_ids

    # Verify import_screenshot_upload delegates via run_in_threadpool
    uid = "u_phase2_ocr_user"
    LocalStore.upsert_profile(uid, {"id": uid, "display_name": "截图异步测试员"})
    token = _make_jwt(uid)
    client = TestClient(app)

    called_in_threadpool = {"flag": False}

    async def _spy_threadpool(func, *args, **kwargs):
        called_in_threadpool["flag"] = True
        return {"success": True, "imported": 1, "records": []}

    with patch("routers.sync.run_in_threadpool", side_effect=_spy_threadpool):
        resp = client.post(
            "/api/sync/import-screenshot-upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"uid": uid, "source_brand": "huawei"},
            files={"file": ("run.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        )
    assert resp.status_code == 200
    assert called_in_threadpool["flag"] is True
