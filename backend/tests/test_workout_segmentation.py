import json
import sqlite3
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
import utils.local_store as ls_mod
import routers.miniapp as miniapp_mod
from utils.local_store import LocalStore, init_db
from utils.workout_segmentation import analyze_activity_segments
from utils.coros_adapter import CorosAdapter


def _make_lap(idx: int, dist_m: float, pace_sec: int, hr: int, cad: int = 180, elev_gain: float = 0.0, intensity: str = "INTERVAL"):
    dur_s = round((dist_m / 1000.0) * pace_sec, 1)
    return {
        "lap_index": idx,
        "distance_m": dist_m,
        "duration_s": dur_s,
        "pace_sec": pace_sec,
        "gap_sec": pace_sec,
        "avg_hr": hr,
        "max_hr": hr + 4,
        "avg_cadence": cad,
        "elev_gain_m": elev_gain,
        "elev_loss_m": 0.0,
        "intensity_type": intensity,
    }


def test_planned_workout_warmup_main_cooldown_alignment():
    """
    Verifies that a 12km run (2km warmup @ 5:45 + 8km threshold @ 4:32 + 2km cooldown @ 5:50)
    aligns Main Set (8km @ 4:32/km, HR 166) accurately against the scheduled workout without
    overall average pace (4:57/km) diluting Main Set compliance.
    """
    laps = [
        _make_lap(1, 1000, 350, 132),
        _make_lap(2, 1000, 340, 140),
        _make_lap(3, 1000, 273, 163),
        _make_lap(4, 1000, 272, 165),
        _make_lap(5, 1000, 271, 166),
        _make_lap(6, 1000, 272, 166),
        _make_lap(7, 1000, 273, 167),
        _make_lap(8, 1000, 272, 167),
        _make_lap(9, 1000, 271, 168),
        _make_lap(10, 1000, 272, 168),
        _make_lap(11, 1000, 348, 148),
        _make_lap(12, 1000, 352, 138),
    ]
    total_dur = int(sum(x["duration_s"] for x in laps))
    act = {
        "id": "garmin_test_planned_1",
        "name": "周四乳酸门槛课",
        "sport_type": "Run",
        "start_time": "2026-11-03T06:30:00",
        "distance_meters": 12000.0,
        "moving_time_seconds": total_dur,
        "avg_pace_str": "4:57/km",
        "average_heartrate": 157,
    }
    planned_day = {
        "date": "2026-11-03",
        "workout_type": "tempo",
        "title": "乳酸门槛巡航",
        "distance_km": 12.0,
        "target_pace": "4:30-4:35/km",
        "target_hr_zone": "162-170 bpm",
        "description": "热身 2km + 8km 门槛巡航 (4:30-4:35/km) + 冷身 2km",
    }

    res = analyze_activity_segments(
        activity=act,
        track_data={"laps": laps, "points": []},
        planned_day=planned_day,
        preset_race=None,
        max_hr=190.0,
    )

    assert res["mode"] == "planned_workout"
    phase_types = [p["phase_type"] for p in res["phases"]]
    assert phase_types == ["warmup", "cruise", "cooldown"]

    comp = res["plan_comparison"]
    assert comp is not None
    assert comp["has_wucd_structure"] is True
    assert comp["actual_main_km"] == pytest.approx(8.0, abs=0.1)
    assert comp["compliance_pct"] == 100
    assert comp["actual_main_pace_str"] == "4:32/km"
    assert "主课配速精准" in comp["pace_verdict"]
    assert comp["actual_main_steady_hr"] == pytest.approx(166, abs=2)


def test_interval_workout_detection():
    """Verifies 6x1km interval detection with jog recoveries."""
    laps = [
        _make_lap(1, 2000, 345, 135, intensity="WARMUP"),
    ]
    idx = 2
    for rep in range(6):
        laps.append(_make_lap(idx, 1000, 232 + (rep % 2), 175 + (rep // 2), cad=190, intensity="ACTIVE"))
        idx += 1
        laps.append(_make_lap(idx, 400, 390, 146, cad=164, intensity="RECOVERY"))
        idx += 1
    laps.append(_make_lap(idx, 1600, 355, 138, intensity="COOLDOWN"))

    total_m = sum(x["distance_m"] for x in laps)
    total_s = int(sum(x["duration_s"] for x in laps))
    act = {
        "id": "coros_test_interval_1",
        "name": "间歇跑 6x1000m",
        "sport_type": "Run",
        "distance_meters": total_m,
        "moving_time_seconds": total_s,
        "avg_pace_str": "4:48/km",
        "average_heartrate": 158,
    }

    res = analyze_activity_segments(activity=act, track_data={"laps": laps}, planned_day=None, preset_race=None)
    assert res["mode"] == "free_workout"
    iv_phase = next((p for p in res["phases"] if p["phase_type"] == "intervals"), None)
    assert iv_phase is not None
    assert iv_phase["interval_detail"]["rep_count"] == 6
    assert iv_phase["interval_detail"]["work_pace_str"] in ("3:52/km", "3:53/km")
    assert iv_phase["interval_detail"]["hr_recovery_drop"] >= 20


def test_strict_preset_race_vs_non_preset_half_marathon_lsd():
    """
    Verifies User Rule #2:
    - A 21.2km run WITHOUT preset_race MUST stay in training review ('free_workout'), never guessed as a race.
    - A marathon matching preset_race MUST trigger 'race' mode with stages, split delta, and physiological cause.
    """
    lsd_laps = [_make_lap(i + 1, 1000, 310 - (12 if i >= 15 else 0), 148 + (6 if i >= 15 else 0)) for i in range(21)]
    lsd_act = {
        "id": "garmin_sunday_lsd",
        "name": "周日半马距离拉练",
        "sport_type": "Run",
        "distance_meters": 21200.0,
        "moving_time_seconds": sum(int(x["duration_s"]) for x in lsd_laps),
        "avg_pace_str": "5:06/km",
        "average_heartrate": 150,
    }
    lsd_res = analyze_activity_segments(activity=lsd_act, track_data={"laps": lsd_laps}, planned_day=None, preset_race=None)
    assert lsd_res["mode"] == "free_workout"
    assert lsd_res["race_diagnosis"] is None

    # Now test Preset Full Marathon with late glycogen bonk (pace drops after 32km + HR/cadence drop)
    fm_laps = []
    for km in range(1, 43):
        if km <= 31:
            fm_laps.append(_make_lap(km, 1000, 270, 164, cad=184))
        else:
            fm_laps.append(_make_lap(km, 1000, 308, 154, cad=172))
    fm_act = {
        "id": "coros_shanghai_marathon",
        "name": "上海马拉松",
        "sport_type": "Run",
        "distance_meters": 42250.0,
        "moving_time_seconds": int(sum(x["duration_s"] for x in fm_laps)),
        "avg_pace_str": "4:40/km",
        "average_heartrate": 161,
    }
    preset_race = {
        "id": "rp_1",
        "name": "2026上海马拉松",
        "race_type": "全马",
        "race_date": "2026-11-29",
        "target_time": "3:15:00",
    }
    race_res = analyze_activity_segments(
        activity=fm_act,
        track_data={"laps": fm_laps},
        planned_day=None,
        preset_race=preset_race,
        max_hr=188.0,
    )
    assert race_res["mode"] == "race"
    rd = race_res["race_diagnosis"]
    assert rd is not None
    assert rd["race_name"] == "2026上海马拉松"
    assert rd["half_split"]["split_code"] == "positive"
    assert rd["fade_inflection_km"] == 32
    assert rd["cause_code"] == "glycogen_bonk"
    assert len(rd["stages"]) == 5


def test_coros_detail_query_unit_normalization_and_zero_mobile_login(monkeypatch):
    """
    Verifies CorosAdapter.fetch_activity_gps_track parses Web /activity/detail/query units
    (cm -> km/m, 0.01s -> s, 1e7 -> GCJ-02) and strictly passes trigger_2fa_sms=False.
    """
    import utils.coros_adapter as coros_mod

    adapter = CorosAdapter(account="runner@example.com", password="secret")
    adapter.access_token = "mock_web_token"
    login_spy = MagicMock(return_value=True)
    adapter.login = login_spy

    mock_detail_resp = MagicMock()
    mock_detail_resp.status_code = 200
    mock_detail_resp.json.return_value = {
        "result": "0000",
        "data": {
            "frequencyList": [
                {"distance": 0, "timestamp": 10000, "gpsLat": 312304000, "gpsLon": 1214737000, "altitude": 8.0, "heart": 128, "cadence": 176, "speed": 320},
                {"distance": 100000, "timestamp": 42000, "gpsLat": 312394000, "gpsLon": 1214737000, "altitude": 10.0, "heart": 148, "cadence": 180, "speed": 300},
                {"distance": 200000, "timestamp": 72000, "gpsLat": 312484000, "gpsLon": 1214737000, "altitude": 11.0, "heart": 152, "cadence": 182, "speed": 295},
            ],
            "lapList": [
                {
                    "type": 2,
                    "lapDistance": 100000,
                    "lapItemList": [
                        {"lapIndex": 1, "distance": 100000, "time": 32000, "avgPace": 320, "avgHr": 142, "avgCadence": 178},
                        {"lapIndex": 2, "distance": 100000, "time": 30000, "avgPace": 300, "avgHr": 151, "avgCadence": 181},
                    ],
                }
            ],
        },
    }
    monkeypatch.setattr(coros_mod.requests, "post", MagicMock(return_value=mock_detail_resp))

    res = adapter.fetch_activity_gps_track("coros_476689894480098409", sport_type_hint=100)
    assert res is not None
    assert res["has_gps_points"] is True
    assert len(res["points"]) == 3
    assert len(res["km_splits"]) == 2
    assert res["km_splits"][0]["distance_m"] == 1000.0
    assert res["km_splits"][0]["duration_s"] == 320.0
    assert res["km_splits"][0]["pace_str"] == "5:20/km"
    assert res["telemetry_series"][-1]["dist_km"] == pytest.approx(2.0, abs=0.01)


def test_confidentiality_self_mentor_coach_vs_other_viewer(tmp_path, monkeypatch):
    """
    Verifies User Rule #3:
    Runner (本人), Mentor (师傅), and Coach (教练) ALWAYS see segment_analysis even when
    hide_biometrics / hide_gps_route is enabled; all other viewers receive segment_analysis=None
    and is_segment_hidden=True.
    """
    temp_db = str(tmp_path / "test_seg_privacy.db")
    monkeypatch.setattr(ls_mod, "DB_PATH", temp_db)
    monkeypatch.setattr(miniapp_mod, "DB_PATH", temp_db)
    init_db()

    runner_uid = "u_runner_priv"
    mentor_uid = "u_mentor_priv"
    coach_uid = "u_coach_priv"
    peer_uid = "u_peer_priv"
    club_id = "club_priv_test"

    LocalStore.upsert_profile(runner_uid, {"display_name": "保密跑者", "hide_biometrics": 1, "hide_gps_route": 0})
    LocalStore.upsert_profile(mentor_uid, {"display_name": "专属师傅"})
    LocalStore.upsert_profile(coach_uid, {"display_name": "跑团教练"})
    LocalStore.upsert_profile(peer_uid, {"display_name": "普通团友"})

    with sqlite3.connect(temp_db) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO clubs (id, name, owner_id, created_at) VALUES (?, ?, ?, '2026-01-01T00:00:00Z')",
            (club_id, "测试跑团", coach_uid),
        )
        for uid, role in [(coach_uid, "coach"), (mentor_uid, "member"), (runner_uid, "member"), (peer_uid, "member")]:
            cur.execute(
                "INSERT INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES (?, ?, ?, ?, 'active', '2026-01-01T00:00:00Z')",
                (f"cm_{uid}", club_id, uid, role),
            )
        cur.execute(
            """
            INSERT INTO mentor_relationships (id, club_id, mentor_id, mentee_id, status, created_at)
            VALUES (?, ?, ?, ?, 'active', '2026-01-02T00:00:00Z')
            """,
            (f"mr_{uuid.uuid4().hex[:6]}", club_id, mentor_uid, runner_uid),
        )
        # Also add a preset race for runner_uid on 2026-11-15 to verify end-to-end DB preset_race detection!
        cur.execute(
            """
            INSERT INTO race_plans (id, user_id, name, race_type, race_date, target_time, status)
            VALUES ('rp_half_1', ?, '2026苏州半程马拉松', '半马', '2026-11-15', '1:40:00', 'upcoming')
            """,
            (runner_uid,),
        )
        conn.commit()

    act_id = "coros_priv_race_001"
    laps = [_make_lap(i + 1, 1000, 282, 165) for i in range(21)]
    LocalStore.upsert_activity(
        {
            "id": act_id,
            "user_id": runner_uid,
            "name": "苏州半马",
            "sport_type": "Run",
            "start_time": "2026-11-15T07:30:00",
            "distance_meters": 21100.0,
            "moving_time_seconds": 21 * 282,
            "avg_pace_str": "4:42/km",
            "average_heartrate": 165,
            "gps_track_data": {
                "points": [{"latitude": 31.30, "longitude": 120.60}, {"latitude": 31.35, "longitude": 120.65}],
                "laps": laps,
            },
        },
        notify=False,
    )

    client = TestClient(app)

    # 1. Self (本人) -> sees preset race segment_analysis
    r_self = client.get(f"/api/miniapp/activities/{act_id}/track?viewer_uid={runner_uid}").json()
    assert r_self["success"] is True
    assert r_self["is_segment_hidden"] is False
    assert r_self["segment_analysis"] is not None
    assert r_self["segment_analysis"]["mode"] == "race"
    assert r_self["segment_analysis"]["race_diagnosis"]["race_name"] == "2026苏州半程马拉松"

    # 2. Mentor (师傅) -> sees segment_analysis
    r_mentor = client.get(f"/api/miniapp/activities/{act_id}/track?viewer_uid={mentor_uid}").json()
    assert r_mentor["is_segment_hidden"] is False
    assert r_mentor["segment_analysis"] is not None
    assert r_mentor["segment_analysis"]["mode"] == "race"

    # 3. Coach (教练) -> sees segment_analysis
    r_coach = client.get(f"/api/miniapp/activities/{act_id}/track?viewer_uid={coach_uid}").json()
    assert r_coach["is_segment_hidden"] is False
    assert r_coach["segment_analysis"] is not None

    # 4. Regular Club Peer (其他人) -> hidden!
    r_peer = client.get(f"/api/miniapp/activities/{act_id}/track?viewer_uid={peer_uid}").json()
    assert r_peer["is_segment_hidden"] is True
    assert r_peer["segment_analysis"] is None
    assert r_peer["activity"]["average_heartrate"] is None

    # 5. Unidentified caller -> hidden!
    r_anon = client.get(f"/api/miniapp/activities/{act_id}/track").json()
    assert r_anon["is_segment_hidden"] is True
    assert r_anon["segment_analysis"] is None


def test_garmin_rwd_overlapping_summary_buckets_do_not_shadow_real_laps():
    """
    Regression test for live Garmin activities where Garmin's typed-splits / splitSummaries
    returns overlapping Run/Walk Detection buckets (INTERVAL_ACTIVE=14410m + RWD_RUN=14408.2m),
    which must never shadow the 15 sequential physical 1km laps in laps_data / track['laps'].
    """
    real_laps = [_make_lap(i + 1, 1000 if i < 14 else 410, 315 - (8 if i >= 10 else 0), 146 + (5 if i >= 10 else 0)) for i in range(15)]
    overlapping_rwd_buckets = [
        {"splitType": "INTERVAL_ACTIVE", "distance": 14410.0, "duration": 4480.0, "averageHR": 148},
        {"type": "RWD_RUN", "distance": 14408.2, "duration": 4478.0, "averageHR": 148},
        {"type": "RWD_WALK", "distance": 1.8, "duration": 2.0, "averageHR": 115},
    ]
    act = {
        "id": "garmin_658362791_sim",
        "name": "晨跑 14.4km",
        "sport_type": "Run",
        "distance_meters": 14410.0,
        "moving_time_seconds": 4480,
        "avg_pace_str": "5:11/km",
        "average_heartrate": 148,
        "splits_data": json.dumps(overlapping_rwd_buckets),
        "laps_data": json.dumps(real_laps),
    }

    res = analyze_activity_segments(
        activity=act,
        track_data={"laps": real_laps, "structured_splits": overlapping_rwd_buckets},
        planned_day=None,
        preset_race=None,
    )
    assert res["has_granular_splits"] is True
    assert len(res["km_splits"]) == 15
    assert sum(s["distance_m"] for s in res["km_splits"]) == pytest.approx(14410.0, abs=1.0)


def test_large_plan_discrepancy_skips_schedule_comparison_and_critiques_training_effect(tmp_path, monkeypatch):
    """
    Verifies that when an activity's pace, distance, or workout combination/structure
    differs significantly from the scheduled training plan day:
    1) analyze_activity_segments skips 'planned_workout' comparison and routes directly
       to 'free_workout' training effect analysis (plan_comparison is None).
    2) LocalStore.generate_canova_critique directly critiques the training effect
       without '📋【课表...' comparison text.
    """
    temp_db = str(tmp_path / "test_discrepancy.db")
    monkeypatch.setattr(ls_mod, "DB_PATH", temp_db)
    monkeypatch.setattr(miniapp_mod, "DB_PATH", temp_db)
    init_db()

    uid = "u_discrepancy_runner"
    LocalStore.upsert_profile(uid, {"display_name": "测试跑者", "max_heartrate": 190, "resting_heartrate": 52})

    # Seed an active training plan with several distinct scheduled days
    plan_schedule = {
        "weeks": [
            {
                "week_index": 1,
                "phase": "专项强化期",
                "week_title": "第1周",
                "days": [
                    {
                        "date": "2026-11-01",
                        "workout_type": "easy_run",
                        "title": "有氧基础慢跑",
                        "distance_km": 10.0,
                        "target_pace": "5:45-6:15 /km",
                        "target_hr_zone": "135-148 bpm",
                        "description": "10km 轻松有氧跑，结束后做 4 组 100m 跨步冲刺 (Strides)。",
                    },
                    {
                        "date": "2026-11-02",
                        "workout_type": "long_run",
                        "title": "周日有氧耐力长距离 (LSD)",
                        "distance_km": 22.0,
                        "target_pace": "5:30-5:50 /km",
                        "target_hr_zone": "140-154 bpm",
                        "description": "22km 稳态长距离有氧跑。",
                    },
                    {
                        "date": "2026-11-03",
                        "workout_type": "trail_climb",
                        "title": "山地爬坡与阶梯抗阻专项",
                        "distance_km": 15.0,
                        "target_pace": "5:40-6:10 /km",
                        "target_hr_zone": "145-162 bpm",
                        "description": "15km 山地起伏路或楼梯爬升训练（目标累计爬升 +400m）。",
                    },
                    {
                        "date": "2026-11-04",
                        "workout_type": "rest",
                        "title": "大课前休整日",
                        "distance_km": 0.0,
                        "target_pace": "完全休息",
                        "target_hr_zone": "—",
                        "description": "今日完全跑休，促进超量恢复。",
                    },
                ],
            }
        ]
    }
    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            INSERT INTO training_plans (
                id, user_id, title, goal_type, target_race_name, target_date,
                schedule_data, status, creator_id, created_at
            )
            VALUES ('tp_disc_1', ?, '全马专项计划', 'race', '上海马拉松', '2026-12-06', ?, 'active', ?, '2026-10-25T00:00:00Z')
            """,
            (uid, json.dumps(plan_schedule, ensure_ascii=False), uid),
        )
        conn.commit()

    days_by_date = {d["date"]: d for d in plan_schedule["weeks"][0]["days"]}

    # Case A: Combination & Pace Discrepancy — Scheduled 10km easy run (5:45-6:15/km),
    # but runner actually executed a 6x1000m track interval session!
    iv_laps = [_make_lap(1, 2000, 340, 136, intensity="WARMUP")]
    idx = 2
    for rep in range(6):
        iv_laps.append(_make_lap(idx, 1000, 238, 176, cad=190, intensity="ACTIVE"))
        idx += 1
        iv_laps.append(_make_lap(idx, 400, 390, 145, cad=164, intensity="RECOVERY"))
        idx += 1
    iv_laps.append(_make_lap(idx, 1600, 350, 138, intensity="COOLDOWN"))
    act_iv = {
        "id": "act_disc_intervals_on_easy_day",
        "user_id": uid,
        "name": "田径场间歇 6x1000m",
        "sport_type": "Run",
        "start_time": "2026-11-01T06:30:00",
        "distance_meters": sum(x["distance_m"] for x in iv_laps),
        "moving_time_seconds": int(sum(x["duration_s"] for x in iv_laps)),
        "avg_pace_str": "4:46/km",
        "average_heartrate": 162,
    }
    seg_iv = analyze_activity_segments(
        activity=act_iv,
        track_data={"laps": iv_laps},
        planned_day=days_by_date["2026-11-01"],
        preset_race=None,
    )
    assert seg_iv["mode"] == "free_workout"
    assert seg_iv["plan_comparison"] is None
    assert "间歇训练" in seg_iv["summary_title"]
    critique_iv = LocalStore.generate_canova_critique(act_iv, uid)
    assert "📋【课表" not in critique_iv
    assert "【间歇专项刺激】" in critique_iv

    # Case B: Distance Discrepancy — Scheduled 22km LSD, but runner only jogged 8km recovery
    short_laps = [_make_lap(i + 1, 1000, 345, 138) for i in range(8)]
    act_short = {
        "id": "act_disc_short_on_lsd_day",
        "user_id": uid,
        "name": "晨间恢复跑",
        "sport_type": "Run",
        "start_time": "2026-11-02T07:00:00",
        "distance_meters": 8000.0,
        "moving_time_seconds": 8 * 345,
        "avg_pace_str": "5:45/km",
        "average_heartrate": 138,
    }
    seg_short = analyze_activity_segments(
        activity=act_short,
        track_data={"laps": short_laps},
        planned_day=days_by_date["2026-11-02"],
        preset_race=None,
    )
    assert seg_short["mode"] == "free_workout"
    assert seg_short["plan_comparison"] is None
    critique_short = LocalStore.generate_canova_critique(act_short, uid)
    assert "📋【课表" not in critique_short
    assert "达成率" not in critique_short
    assert "【" in critique_short

    # Case C: Combination Discrepancy — Scheduled 15km mountain climb (+400m), but ran flat road (+18m)
    flat_laps = [_make_lap(i + 1, 1000, 325, 148, elev_gain=1.2) for i in range(15)]
    act_flat = {
        "id": "act_disc_flat_on_climb_day",
        "user_id": uid,
        "name": "世纪公园平路有氧",
        "sport_type": "Run",
        "start_time": "2026-11-03T06:40:00",
        "distance_meters": 15000.0,
        "moving_time_seconds": 15 * 325,
        "avg_pace_str": "5:25/km",
        "average_heartrate": 148,
        "elevation_gain_meters": 18.0,
    }
    seg_flat = analyze_activity_segments(
        activity=act_flat,
        track_data={"laps": flat_laps},
        planned_day=days_by_date["2026-11-03"],
        preset_race=None,
    )
    assert seg_flat["mode"] == "free_workout"
    assert seg_flat["plan_comparison"] is None
    critique_flat = LocalStore.generate_canova_critique(act_flat, uid)
    assert "📋【课表" not in critique_flat

    # Case D: Scheduled Rest Day — Runner ran 30km LSD on a rest day
    rest_laps = [_make_lap(i + 1, 1000, 330, 146) for i in range(30)]
    act_rest_lsd = {
        "id": "act_disc_lsd_on_rest_day",
        "user_id": uid,
        "name": "30km 长距离拉练",
        "sport_type": "Run",
        "start_time": "2026-11-04T06:00:00",
        "distance_meters": 30000.0,
        "moving_time_seconds": 30 * 330,
        "avg_pace_str": "5:30/km",
        "average_heartrate": 146,
    }
    seg_rest = analyze_activity_segments(
        activity=act_rest_lsd,
        track_data={"laps": rest_laps},
        planned_day=days_by_date["2026-11-04"],
        preset_race=None,
    )
    assert seg_rest["mode"] == "free_workout"
    assert seg_rest["plan_comparison"] is None
    critique_rest = LocalStore.generate_canova_critique(act_rest_lsd, uid)
    assert "📋【课表" not in critique_rest
    assert "休整日" not in critique_rest
    assert "【长距离有氧耐力】" in critique_rest

    # Case E: Pace Discrepancy — Scheduled 10km easy run @ 5:45-6:15/km, but ran 10km @ 4:25/km threshold pace
    fast_laps = [_make_lap(i + 1, 1000, 265, 170) for i in range(10)]
    act_fast = {
        "id": "act_disc_fast_on_easy_day",
        "user_id": uid,
        "name": "节奏跑 10km",
        "sport_type": "Run",
        "start_time": "2026-11-01T18:00:00",
        "distance_meters": 10000.0,
        "moving_time_seconds": 10 * 265,
        "avg_pace_str": "4:25/km",
        "average_heartrate": 170,
    }
    seg_fast = analyze_activity_segments(
        activity=act_fast,
        track_data={"laps": fast_laps},
        planned_day=days_by_date["2026-11-01"],
        preset_race=None,
    )
    assert seg_fast["mode"] == "free_workout"
    assert seg_fast["plan_comparison"] is None
    critique_fast = LocalStore.generate_canova_critique(act_fast, uid)
    assert "📋【课表" not in critique_fast
    assert "【" in critique_fast

    # Case F: Aligned Workout — Scheduled 10km easy run @ 5:45-6:15/km, ran 10km @ 5:55/km steady
    aligned_laps = [_make_lap(i + 1, 1000, 355, 140) for i in range(10)]
    act_aligned = {
        "id": "act_aligned_easy_day",
        "user_id": uid,
        "name": "有氧慢跑 10km",
        "sport_type": "Run",
        "start_time": "2026-11-01T07:00:00",
        "distance_meters": 10000.0,
        "moving_time_seconds": 10 * 355,
        "avg_pace_str": "5:55/km",
        "average_heartrate": 140,
    }
    seg_aligned = analyze_activity_segments(
        activity=act_aligned,
        track_data={"laps": aligned_laps},
        planned_day=days_by_date["2026-11-01"],
        preset_race=None,
    )
    assert seg_aligned["mode"] == "planned_workout"
    assert seg_aligned["plan_comparison"] is not None
    critique_aligned = LocalStore.generate_canova_critique(act_aligned, uid)
    assert "📋【课表" in critique_aligned



