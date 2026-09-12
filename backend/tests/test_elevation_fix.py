import pytest
import sqlite3

from utils.local_store import LocalStore, DB_PATH, init_db
from utils.garmin_adapter import GarminAdapter
from utils.coros_adapter import CorosAdapter


def test_garmin_adapter_elevation_normalization():
    adapter = GarminAdapter("test@example.com", "pass", domain="garmin.cn")
    sample_garmin_act = {
        "activityId": 12345678,
        "activityName": "萍乡市 越野跑",
        "activityType": {"typeKey": "trail_running"},
        "startTimeLocal": "2026-09-12 06:00:57",
        "distance": 58983.0,
        "duration": 24000,
        "movingDuration": 23500,
        "averageSpeed": 2.5,
        "maxSpeed": 4.5,
        "averageHR": 125,
        "maxHR": 165,
        "elevationGain": 4159.2,
        "elevationLoss": 4168.5,
        "calories": 3500,
    }
    norm = adapter._normalize_activity(sample_garmin_act)
    assert norm is not None
    assert norm["elevation_gain_meters"] == 4159.2
    assert norm["total_elevation_gain"] == 4159.2


def test_coros_adapter_elevation_normalization():
    adapter = CorosAdapter("test@example.com", "pass", domain="coros.com")
    sample_coros_act = {
        "activityId": 987654321,
        "name": "崇礼 越野跑",
        "mode": 100,
        "startTime": 1726100000,
        "distance": 30000.0,
        "totalTime": 12000,
        "avgHeartRate": 130,
        "maxHeartRate": 160,
        "elevationGain": 1850.5,
        "calorie": 2000,
    }
    norm = adapter._normalize_activity(sample_coros_act)
    assert norm is not None
    assert norm["elevation_gain_meters"] == 1850.5
    assert norm["total_elevation_gain"] == 1850.5


def test_local_store_upsert_activity_elevation_aliases():
    init_db()
    test_act_id = "test_trail_elev_001"
    
    # Simulate an adapter that only provided total_elevation_gain
    act_data = {
        "id": test_act_id,
        "user_id": "test_runner_elev",
        "name": "武功山 越野突破",
        "sport_type": "Run",
        "start_time": "2026-09-12T06:00:00Z",
        "distance_meters": 58983.0,
        "moving_time_seconds": 23500,
        "elapsed_time_seconds": 24000,
        "avg_pace_str": "11:35 /km",
        "average_heartrate": 125,
        "max_heartrate": 165,
        "total_elevation_gain": 4159.2, # only alias provided
        "trimp": 656.1,
    }

    LocalStore.upsert_activity(act_data)

    # Check database column
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT elevation_gain_meters, ai_journal FROM activities WHERE id = ?", (test_act_id,))
        row = cursor.fetchone()
        assert row is not None
        elev_gain, critique = row
        assert elev_gain == 4159.2
        assert "+4159m" in critique, f"Critique should reflect +4159m, got: {critique}"
