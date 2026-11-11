import uuid
from datetime import date, timedelta
from fastapi.testclient import TestClient

from main import app
from utils.coros_adapter import CorosAdapter
from utils.local_store import LocalStore, init_db
from utils.running_metrics import (
    compute_canova_athlete_matrix,
    predict_realistic_race_times,
)

client = TestClient(app)


def test_coros_ascent_and_cadence_normalization():
    adapter = CorosAdapter("test@example.com", "pass", domain="teamcnapi.coros.com")
    sample_live_coros_item = {
        "labelId": "481496971364827540",
        "name": "上海市 跑步",
        "sportType": 100,
        "startTime": 1730500000,
        "distance": 18381.3,
        "totalTime": 5800,
        "workoutTime": 5760,
        "avgHr": 151,
        "cadence": 184,
        "ascent": 43,
        "totalDescent": 40,
        "calorie": 1120,
    }
    norm = adapter._normalize_activity(sample_live_coros_item)
    assert norm is not None
    assert norm["elevation_gain_meters"] == 43.0
    assert norm["total_elevation_gain"] == 43.0
    assert norm["average_cadence"] == 184


def test_vdot_decoupled_from_inflated_watch_vo2max_and_dashboard_parity():
    init_db()
    uid = f"u_vdot_cal_{uuid.uuid4().hex[:6]}"
    today = date.today()

    LocalStore.upsert_profile(
        uid,
        {
            "display_name": "校准测试跑者",
            "garmin_connected": 1,
            "vo2max": 52.0,
            "half_pb": "1:54:00",
            "ten_k_pb": "51:30",
            "resting_heart_rate": 56,
            "max_heart_rate": 188,
        },
    )

    for idx in range(5):
        run_day = (today - timedelta(days=idx * 5 + 1)).isoformat()
        LocalStore.upsert_activity(
            {
                "id": f"garmin_cal_{uid}_{idx}",
                "user_id": uid,
                "name": "日常有氧跑",
                "sport_type": "Run",
                "start_time": f"{run_day}T06:30:00Z",
                "distance_meters": 10000.0 if idx < 4 else 16000.0,
                "moving_time_seconds": 3450 if idx < 4 else 5600,
                "avg_pace_str": "5:45 /km",
                "average_heartrate": 152,
                "elevation_gain_meters": 25.0,
                "average_cadence": 176,
                "trimp": 85.0,
            },
            notify=False,
        )

    sci = client.get(f"/api/science/metrics/{uid}").json()
    dash = client.get(f"/api/miniapp/dashboard/{uid}").json()

    assert sci["vo2max"] == 52.0
    assert sci["canova_matrix"]["watch_vo2max"] == 52.0
    # Effective VDOT must reflect real ~38-41 running output, NOT raw watch VO2Max 52.0
    assert 36.5 <= sci["vdot"] <= 42.5
    assert sci["vdot"] < 45.0
    # Dashboard and Science endpoints must match 100%
    assert dash["vdot"] == sci["vdot"]

    # Marathon prediction must include mileage/long-run endurance decay (nowhere near VO2Max 52's 2:58!)
    fm_str = sci["race_predictions"]["marathon"]
    fm_hours = int(fm_str.split(":")[0])
    assert fm_hours >= 4


def test_five_dimension_matrix_strict_curves_hrv_rhr_and_missing_nocturnal():
    today = date.today()
    runs_40k_wk = []
    for w in range(6):
        for d_off, dist_m in [(0, 10000.0), (2, 12000.0), (5, 18000.0)]:
            day_s = (today - timedelta(days=w * 7 + d_off)).isoformat()
            runs_40k_wk.append(
                {
                    "id": f"r_{w}_{d_off}",
                    "sport_type": "Run",
                    "start_time": f"{day_s}T07:00:00Z",
                    "distance_meters": dist_m,
                    "moving_time_seconds": dist_m / 1000.0 * 320.0,
                    "average_heartrate": 150,
                    "elevation_gain_meters": dist_m / 1000.0 * 3.5,  # flat barometer drift (~840m total)
                    "average_cadence": 178,
                }
            )

    # 1. Missing nocturnal wear -> conservative recovery score (<=64), no fake 74
    mat_no_wear = compute_canova_athlete_matrix(
        profile={"vo2max": 50.0, "resting_heart_rate": 56, "max_heart_rate": 188},
        activities=runs_40k_wk,
        current_ctl=42.0,
        current_tsb=-8.0,
        health_trend=[],
    )
    dims_no_wear = {d["key"]: d for d in mat_no_wear["dimensions"]}
    assert mat_no_wear["recovery_data_status"] == "missing_nocturnal"
    assert dims_no_wear["autonomic_recovery"]["score"] <= 62
    # 40km/wk & flat road barometer drift must NOT hit 90+ saturation
    assert 55 <= dims_no_wear["aerobic_base"]["score"] <= 78
    assert dims_no_wear["climbing_strength"]["score"] <= 55

    # 2. Good HRV/RHR vs suppressed HRV & elevated RHR
    good_trend = []
    fatigued_trend = []
    for i in range(20, -1, -1):
        ds = (today - timedelta(days=i)).isoformat()
        is_recent = i < 7
        good_trend.append(
            {
                "date": ds,
                "sleep_score": 84 if is_recent else 78,
                "hrv": 68 if is_recent else 60,
                "resting_heart_rate": 51 if is_recent else 53,
            }
        )
        fatigued_trend.append(
            {
                "date": ds,
                "sleep_score": 68 if is_recent else 78,
                "hrv": 46 if is_recent else 60,
                "resting_heart_rate": 58 if is_recent else 53,
            }
        )

    mat_good = compute_canova_athlete_matrix(
        profile={"resting_heart_rate": 53, "max_heart_rate": 188},
        activities=runs_40k_wk,
        current_ctl=45.0,
        current_tsb=4.0,
        health_trend=good_trend,
    )
    mat_fatigued = compute_canova_athlete_matrix(
        profile={"resting_heart_rate": 53, "max_heart_rate": 188},
        activities=runs_40k_wk,
        current_ctl=45.0,
        current_tsb=-26.0,
        health_trend=fatigued_trend,
    )
    rec_good = {d["key"]: d["score"] for d in mat_good["dimensions"]}["autonomic_recovery"]
    rec_bad = {d["key"]: d["score"] for d in mat_fatigued["dimensions"]}["autonomic_recovery"]
    assert rec_good - rec_bad >= 22

    # 3. Race prediction endurance decay: low volume vs high volume at identical effective_vdot=50
    pred_low_vol = predict_realistic_race_times(
        {
            "effective_vdot": 50.0,
            "weekly_km_avg": 28.0,
            "longest_km_42d": 16.0,
            "long_runs_25k_42d": 0,
            "avg_long_run_drift_pct": 9.2,
        }
    )
    pred_high_vol = predict_realistic_race_times(
        {
            "effective_vdot": 50.0,
            "weekly_km_avg": 82.0,
            "longest_km_42d": 32.5,
            "long_runs_25k_42d": 3,
            "avg_long_run_drift_pct": 2.1,
        }
    )
    assert pred_low_vol["marathon_seconds"] - pred_high_vol["marathon_seconds"] >= 1200  # >= 20 min slower for under-trained marathoner



def test_elite_runner_injury_recovery_dual_track_and_anti_glitch_filter():
    init_db()
    uid = f"u_elite_rec_{uuid.uuid4().hex[:6]}"
    today = date.today()

    # Profile still has legacy untouched schema placeholder PBs (10800/5100/2400/1140)
    LocalStore.upsert_profile(
        uid,
        {
            "display_name": "伤后恢复精英跑者",
            "coros_connected": 1,
            "vo2max": 60.0,
            "marathon_pb": 10800,
            "half_pb": 5100,
            "ten_k_pb": 2400,
            "five_k_pb": 1140,
            "resting_heart_rate": 45,
            "max_heart_rate": 190,
        },
    )

    # 1. Historical verified Spring Half Marathon (~210 days ago, >100 activities ago if high frequency): 21.56km in 72:13 (~2:31 FM potential)
    spring_day = (today - timedelta(days=210)).isoformat()
    LocalStore.upsert_activity(
        {
            "id": f"coros_spring_hm_{uid}",
            "user_id": uid,
            "name": "上海市 跑步",
            "sport_type": "Run",
            "start_time": f"{spring_day}T07:00:00Z",
            "distance_meters": 21560.0,
            "moving_time_seconds": 4333,
            "elapsed_time_seconds": 4335,
            "average_heartrate": 170,
            "average_cadence": 189,
            "elevation_gain_meters": 45.0,
            "trimp": 185.0,
        },
        notify=False,
    )

    # 2. Corrupted historical records that MUST be rejected from PB/Peak extraction:
    # (a) Cycling logged as Run (cadence 69)
    LocalStore.upsert_activity(
        {
            "id": f"coros_bike_glitch_{uid}",
            "user_id": uid,
            "name": "骑行误记跑步",
            "sport_type": "Run",
            "start_time": f"{(today - timedelta(days=150)).isoformat()}T07:00:00Z",
            "distance_meters": 21100.0,
            "moving_time_seconds": 3600,
            "elapsed_time_seconds": 3600,
            "average_heartrate": 120,
            "average_cadence": 69,
            "trimp": 60.0,
        },
        notify=False,
    )
    # (b) Heavily paused interval session (mov=30m, elp=75m)
    LocalStore.upsert_activity(
        {
            "id": f"coros_paused_iv_{uid}",
            "user_id": uid,
            "name": "间歇停表课",
            "sport_type": "Run",
            "start_time": f"{(today - timedelta(days=120)).isoformat()}T07:00:00Z",
            "distance_meters": 10000.0,
            "moving_time_seconds": 1800,
            "elapsed_time_seconds": 4500,
            "average_heartrate": 168,
            "average_cadence": 188,
            "trimp": 90.0,
        },
        notify=False,
    )

    # 3. Over 105 recent easy rehab runs (~34 km/wk, max 14.2km, elevated rehab HR ~160) so spring HM is beyond limit=100
    for idx in range(106):
        d_str = (today - timedelta(days=idx + 1)).isoformat()
        is_recent_6w = idx < 24
        dist_m = 10000.0 if (idx == 2) else (14250.0 if idx == 0 else (8500.0 if is_recent_6w else 5000.0))
        mov_s = 2671 if (idx == 2) else (4483 if idx == 0 else int(dist_m / 1000.0 * 312))
        if is_recent_6w and idx % 2 == 1:
            dist_m = 5000.0
            mov_s = 1600
        LocalStore.upsert_activity(
            {
                "id": f"coros_rehab_{uid}_{idx}",
                "user_id": uid,
                "name": "伤后恢复跑",
                "sport_type": "Run",
                "start_time": f"{d_str}T19:00:00Z",
                "distance_meters": dist_m,
                "moving_time_seconds": mov_s,
                "elapsed_time_seconds": mov_s + 10,
                "average_heartrate": 160,
                "average_cadence": 180,
                "elevation_gain_meters": 22.0,
                "trimp": 72.0,
            },
            notify=False,
        )

    sci = client.get(f"/api/science/metrics/{uid}").json()
    dash = client.get(f"/api/miniapp/dashboard/{uid}").json()
    cm = sci["canova_matrix"]
    rp = sci["race_predictions"]

    # Must recognize Spring 21.56km HM (VDOT ~67.5), while rejecting the 60-min bike glitch (VDOT >78) and 30-min paused 10k
    assert 66.5 <= cm["peak_vdot"] <= 68.5
    assert cm["is_recovery_phase"] is True
    assert "恢复/休整期" in cm["recovery_phase_label"]
    assert "2:31:" in cm["peak_marathon_potential"] or "2:30:" in cm["peak_marathon_potential"] or "2:32:" in cm["peak_marathon_potential"]

    # Current effective VDOT stays in safe rehab zone (~49-53) and matches MiniApp dashboard 100%
    assert 48.5 <= sci["vdot"] <= 53.5
    assert dash["vdot"] == sci["vdot"]
    assert dash["fitness_form"]["is_recovery_phase"] is True
    assert dash["fitness_form"]["peak_vdot"] == cm["peak_vdot"]

    # Current Marathon prediction has structural base cushion (~3:15 - 3:32, NOT double-penalized to 3:52!)
    assert 3 * 3600 + 12 * 60 <= rp["marathon_seconds"] <= 3 * 3600 + 34 * 60
    assert "恢复/休整期保护" in rp["endurance_note"]
