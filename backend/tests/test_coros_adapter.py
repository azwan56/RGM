import pytest
import time
import os
import json
from datetime import datetime
from utils.coros_adapter import CorosAdapter, pace_str
from utils.running_metrics import calculate_trimp
from utils.local_store import LocalStore, init_db

def test_pace_str():
    # 10,000 meters in 3,000 seconds = 300 sec/km = 5:00 /km
    assert pace_str(10000, 3000) == "5:00 /km"
    # 5,000 meters in 1,164 seconds = 232.8 sec/km -> rounded to 233s = 3:53 /km
    assert pace_str(5000, 1164) == "3:53 /km"
    # 5,000 meters in 1,161 seconds = 232.2 sec/km -> rounded to 232s = 3:52 /km
    assert pace_str(5000, 1161) == "3:52 /km"
    # Target case: 15,344.27 meters in 3,803 seconds = 247.85 sec/km -> 4:08 /km
    assert pace_str(15344.27, 3803) == "4:08 /km"
    # Edge cases
    assert pace_str(0, 0) == "—"
    assert pace_str(1000, 0) == "—"

def test_coros_adapter_domain_init():
    adapter_cn = CorosAdapter("runner@example.com", "password123", "teamcnapi.coros.com")
    assert adapter_cn.is_cn is True
    assert adapter_cn.base_url == "https://teamcnapi.coros.com"

    adapter_global = CorosAdapter("runner@example.com", "password123", "teamapi.coros.com")
    assert adapter_global.is_cn is False
    assert adapter_global.base_url == "https://teamapi.coros.com"

def test_coros_adapter_normalize_activity():
    adapter = CorosAdapter("runner@example.com", "password123")
    
    # Simulated COROS activity item returned by /activity/query
    raw_coros_act = {
        "labelId": "987654321",
        "sportType": 100, # Outdoor run
        "name": "世纪公园晨跑 10K",
        "distance": 10000.0,
        "totalTime": 3000,
        "movingTime": 2980,
        "startTime": 1741219200, # Unix epoch timestamp
        "avgHeartRate": 152,
        "maxHeartRate": 175,
        "avgCadence": 182,
        "maxSpeed": 4.2,
        "elevationGain": 35.5,
        "calorie": 620,
        "aerobicEffect": 3.6,
        "anaerobicEffect": 0.4
    }

    norm = adapter._normalize_activity(raw_coros_act)
    assert norm is not None
    assert norm["id"] == "coros_987654321"
    assert norm["source"] == "coros_cn"
    assert norm["name"] == "世纪公园晨跑 10K"
    assert norm["sport_type"] == "Run"
    assert norm["distance_meters"] == 10000.0
    assert norm["moving_time_seconds"] == 2980
    assert norm["average_heartrate"] == 152
    assert norm["max_heartrate"] == 175
    assert norm["average_cadence"] == 182
    assert norm["total_elevation_gain"] == 35.5
    assert norm["calories"] == 620
    assert norm["aerobic_training_effect"] == 3.6
    assert norm["anaerobic_training_effect"] == 0.4
    assert norm["avg_pace_str"] == "4:58 /km"

    # Test TRIMP calculation
    trimp = calculate_trimp(
        duration_minutes=norm["moving_time_seconds"] / 60.0,
        avg_hr=norm["average_heartrate"],
        rest_hr=55,
        max_hr=190,
        gender="male"
    )
    assert trimp > 0
    assert round(trimp, 1) > 40.0

def test_coros_adapter_workout_time_pause_rest_exclusion():
    adapter = CorosAdapter("runner@example.com", "password123")

    # Coros activity where the user paused/stopped the watch to rest
    # 10.01 km (10010m):
    # totalTime is 4635 seconds (~77 min, which would mistakenly yield 7:43 /km if used for pace)
    # workoutTime is 3280 seconds (~54 min 40 sec, giving true active pace of 5:28 /km rounded)
    raw_coros_act = {
        "labelId": "1122334455",
        "sportType": 100,
        "name": "上海市 跑步",
        "distance": 10010.0,
        "totalTime": 4635,
        "workoutTime": 3280,
        "startTime": 1741219200,
        "avgHeartRate": 140,
        "maxHeartRate": 160,
        "avgCadence": 178,
        "elevationGain": 0.0,
        "calorie": 650
    }

    norm = adapter._normalize_activity(raw_coros_act)
    assert norm is not None
    assert norm["distance_meters"] == 10010.0
    # moving_time_seconds must use workoutTime (excluding paused rest)
    assert norm["moving_time_seconds"] == 3280
    assert norm["elapsed_time_seconds"] == 4635
    # Average pace must be 5:28 /km (3280 / 10.01 = 327.67s -> 328s), NOT 7:43 /km!
    assert norm["avg_pace_str"] == "5:28 /km"
    # Average speed must be calculated using moving time (3280s), not total time (4635s)
    assert norm["average_speed_mps"] == round(10010.0 / 3280, 3)

    # Activity matching user report: 15.34km with pauses
    user_report_act = {
        "labelId": "480279389475471569",
        "sportType": 100,
        "name": "上海市 跑步",
        "distance": 15344.27,
        "totalTime": 5169,      # 1h 26m 09s including rest/pause
        "workoutTime": 3803,    # 1h 03m 23s moving time
        "avgSpeed": 247.84,     # Coros pace in sec/km
        "startTime": 1757629035,
        "avgHeartRate": 151,
        "maxHeartRate": 172,
        "avgCadence": 180,
        "elevationGain": 25.0,
        "calorie": 980
    }
    norm_user = adapter._normalize_activity(user_report_act)
    assert norm_user is not None
    assert norm_user["distance_meters"] == 15344.27
    assert norm_user["moving_time_seconds"] == 3803
    assert norm_user["elapsed_time_seconds"] == 5169
    # Must match official COROS app: 4'08" /km, NOT 5:36 /km and NOT 4:07 /km!
    assert norm_user["avg_pace_str"] == "4:08 /km"

def test_coros_token_persistence(tmp_path):
    adapter = CorosAdapter("test_runner_cache@coros.com", "mypassword")
    adapter.token_path = str(tmp_path / "test_coros_token.json")
    adapter.access_token = "mock_jwt_access_token_xyz"
    adapter.user_id = "12345678"
    adapter.nick_name = "超马跑者"
    adapter.avatar_url = "https://coros.com/avatar.jpg"
    
    adapter._save_cached_token()
    assert os.path.exists(adapter.token_path)

    # Reload in new instance
    new_adapter = CorosAdapter("test_runner_cache@coros.com", "mypassword")
    new_adapter.token_path = adapter.token_path
    loaded = new_adapter._load_cached_token()
    assert loaded is True
    assert new_adapter.access_token == "mock_jwt_access_token_xyz"
    assert new_adapter.user_id == "12345678"
    assert new_adapter.nick_name == "超马跑者"

def test_local_store_coros_support():
    init_db()
    test_uid = "u_test_coros_runner_01"
    
    profile_data = {
        "id": test_uid,
        "email": "coros_runner@example.com",
        "display_name": "高驰跑者小强",
        "coros_connected": 1,
        "coros_account": "13800138000",
        "coros_encrypted_password": "encrypted_dummy_pwd",
        "coros_domain": "teamcnapi.coros.com"
    }
    LocalStore.upsert_profile(test_uid, profile_data)

    retrieved = LocalStore.get_profile(test_uid)
    assert retrieved is not None
    assert retrieved.get("coros_connected") == 1
    assert retrieved.get("coros_account") == "13800138000"

    # Query by coros account
    by_acc = LocalStore.get_profile_by_coros_account("13800138000")
    assert by_acc is not None
    assert by_acc["id"] == test_uid

    # Verify get_all_syncable_users includes this runner
    syncable = LocalStore.get_all_syncable_users()
    uids = [u["id"] for u in syncable]
    assert test_uid in uids

    # Cleanup
    LocalStore.delete_profile(test_uid)

def test_coros_auth_api_routes(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    # 1. Mock CorosAdapter network calls
    monkeypatch.setattr(CorosAdapter, "login", lambda self: True)
    monkeypatch.setattr(CorosAdapter, "fetch_activities_by_date", lambda self, start_date=None, end_date=None: [])
    monkeypatch.setattr(CorosAdapter, "fetch_recent_activities", lambda self, limit=100: [])
    monkeypatch.setattr(CorosAdapter, "fetch_user_profile_info", lambda self: {
        "avatar_url": None,
        "display_name": "测试跑者",
        "gender": None, "height_cm": None, "weight_kg": None, "vo2max": None
    })

    test_uid = "u_test_api_runner_coros"
    LocalStore.upsert_profile(test_uid, {
        "id": test_uid,
        "display_name": "测试跑者",
        "email": "test@runner.cn"
    })

    bind_res = client.post("/api/auth/coros/bind", json={
        "uid": test_uid,
        "account": "coros_user_123",
        "password": "mypassword123",
        "domain": "teamcnapi.coros.com"
    })
    assert bind_res.status_code == 200
    bind_data = bind_res.json()
    assert bind_data["success"] is True
    assert bind_data["connected"] is True
    assert "token" in bind_data

    # Check profile updated in LocalStore
    p = LocalStore.get_profile(test_uid)
    assert p["coros_connected"] == 1
    assert p["coros_account"] == "coros_user_123"

    # Test unbind with authorization token
    token = bind_data["token"]
    unbind_res = client.post("/api/auth/coros/unbind", 
        json={"uid": test_uid},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert unbind_res.status_code == 200
    unbind_data = unbind_res.json()
    assert unbind_data["success"] is True
    assert unbind_data["connected"] is False

    # Check profile updated to disconnected
    p_after = LocalStore.get_profile(test_uid)
    assert p_after["coros_connected"] == 0

    # Cleanup
    LocalStore.delete_profile(test_uid)


def test_coros_fetch_profile_and_daily_health(monkeypatch):
    adapter = CorosAdapter("test@coros.com", "pass")
    adapter.access_token = "mock_token"
    adapter.user_id = "468893544451424256"

    mock_account_resp = {
        "result": "0000",
        "data": {
            "nickname": "高九凯",
            "headPic": "https://oss.coros.com/avatar.jpg",
            "sex": 0,
            "stature": 168.0,
            "weight": 60.0,
            "birthday": 19900622,
            "rhr": 46,
            "maxHr": 187,
            "zoneData": {
                "lthr": 168,
                "ltsp": 236
            }
        }
    }

    mock_analyse_resp = {
        "result": "0000",
        "data": {
            "dayList": [
                {"happenDay": 20260906, "avgSleepHrv": 69, "sleepHrvBase": 66, "vo2max": 61, "tib": -22.0},
                {"happenDay": 20260907, "avgSleepHrv": 48, "sleepHrvBase": 66, "tib": -1.0}
            ],
            "t7dayList": [
                {"happenDay": 20260907, "avgSleepHrv": 48, "vo2max": 61}
            ]
        }
    }

    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code
            self.text = json.dumps(json_data)
        def json(self):
            return self._json

    def mock_get(url, *args, **kwargs):
        if "account/query" in url:
            return MockResponse(mock_account_resp)
        elif "analyse/query" in url:
            return MockResponse(mock_analyse_resp)
        return MockResponse({"result": "0000"})

    import requests
    monkeypatch.setattr(requests, "get", mock_get)

    # Test profile info
    info = adapter.fetch_user_profile_info()
    assert info["display_name"] == "高九凯"
    assert info["gender"] == "male"
    assert info["height_cm"] == 168.0
    assert info["weight_kg"] == 60.0
    assert info["date_of_birth"] == "1990-06-22"
    assert info["resting_heart_rate"] == 46
    assert info["max_heart_rate"] == 187
    assert info["vo2max"] == 61.0

    # Test daily health metrics on 2026-09-07
    h_07 = adapter.fetch_daily_health_metrics("2026-09-07")
    assert h_07["resting_heart_rate"] == 46
    assert h_07["hrv_last_night_avg"] == 48
    assert h_07["hrv_weekly_avg"] == 66
    assert h_07["vo2_max"] == 61.0

    # Test daily health metrics on 2026-09-06
    h_06 = adapter.fetch_daily_health_metrics("2026-09-06")
    assert h_06["resting_heart_rate"] == 46
    assert h_06["hrv_last_night_avg"] == 69
    assert h_06["vo2_max"] == 61.0


def test_coros_mobile_encryption_and_sleep_data(monkeypatch):
    from utils.coros_adapter import _encrypt_mobile_param

    # 1. Test encryption deterministic output
    encrypted = _encrypt_mobile_param("test@example.com", "1234567890123456")
    assert encrypted == "G5jn3WY5dtqcmiYdTZEWSbaFTodE1gLa3msMUW5cYQE="

    # 2. Test mobile sleep parsing & consolidation
    adapter = CorosAdapter("test@coros.com", "mypassword")
    adapter.mobile_access_token = "mock_mobile_token"
    adapter.access_token = "mock_web_token"
    adapter.user_id = "12345"

    mock_sleep_api_resp = {
        "result": "0000",
        "data": {
            "statisticData": {
                "dayDataList": [
                    {
                        "happenDay": 20260918,
                        "performance": -1,
                        "sleepData": {
                            "totalSleepTime": 515,
                            "deepTime": 101,
                            "eyeTime": 99,
                            "lightTime": 315,
                            "wakeTime": 26,
                            "minHeartRate": 44,
                            "avgHeartRate": 55,
                            "maxHeartRate": 89
                        }
                    },
                    {
                        "happenDay": 20260917,
                        "performance": 85,
                        "sleepData": {
                            "totalSleepTime": 420,
                            "deepTime": 80,
                            "eyeTime": 70,
                            "lightTime": 270,
                            "wakeTime": 15,
                            "minHeartRate": 48,
                            "avgHeartRate": 58,
                            "maxHeartRate": 92
                        }
                    }
                ]
            }
        }
    }

    mock_analyse_resp = {
        "result": "0000",
        "data": {
            "dayList": [
                {
                    "happenDay": 20260918,
                    "rhr": 48,
                    "staminaLevel": 91.7,
                    "avgSleepHrv": 41,
                    "sleepHrvBase": 64,
                    "vo2max": 62
                },
                {
                    "happenDay": 20260917,
                    "rhr": 41,
                    "staminaLevel": 85.0,
                    "avgSleepHrv": 69,
                    "sleepHrvBase": 64,
                    "vo2max": 62
                }
            ]
        }
    }

    class MockResp:
        def __init__(self, json_data):
            self._json = json_data
            self.status_code = 200
        def json(self):
            return self._json

    def mock_post(url, *args, **kwargs):
        if "data/statistic/daily" in url:
            return MockResp(mock_sleep_api_resp)
        return MockResp({"result": "0000"})

    def mock_get(url, *args, **kwargs):
        if "analyse/query" in url:
            return MockResp(mock_analyse_resp)
        return MockResp({"result": "0000"})

    import requests
    monkeypatch.setattr(requests, "post", mock_post)
    monkeypatch.setattr(requests, "get", mock_get)

    # Test fetch_sleep_data directly
    sleeps = adapter.fetch_sleep_data("2026-09-17", "2026-09-18")
    assert "2026-09-18" in sleeps
    s18 = sleeps["2026-09-18"]
    assert s18["sleep_duration_seconds"] == 515 * 60
    assert s18["sleep_duration_hours"] == 8.6
    assert s18["deep_sleep_seconds"] == 101 * 60
    assert s18["rem_sleep_seconds"] == 99 * 60
    assert s18["min_heart_rate"] == 44
    assert s18["sleep_score"] > 80  # Calculated realistic score

    s17 = sleeps["2026-09-17"]
    assert s17["sleep_duration_seconds"] == 420 * 60
    assert s17["sleep_duration_hours"] == 7.0
    assert s17["sleep_score"] == 85  # Taken from performance

    # Test consolidated fetch_daily_health_metrics
    m18 = adapter.fetch_daily_health_metrics("2026-09-18")
    assert m18["date"] == "2026-09-18"
    assert m18["sleep_duration_seconds"] == 515 * 60
    assert m18["sleep_duration_hours"] == 8.6
    assert m18["sleep_score"] == s18["sleep_score"]
    assert m18["resting_heart_rate"] == 48  # From EvoLab daily rhr
    assert m18["body_battery_max"] == 92    # From staminaLevel 91.7 rounded
    assert m18["hrv_last_night_avg"] == 41
    assert m18["hrv_weekly_avg"] == 64
    assert m18["vo2_max"] == 62.0
    assert m18["hrv_status"] == "low"       # 41 / 64 = 0.64 < 0.85

    m17 = adapter.fetch_daily_health_metrics("2026-09-17")
    assert m17["date"] == "2026-09-17"
    assert m17["sleep_duration_seconds"] == 420 * 60
    assert m17["sleep_score"] == 85
    assert m17["resting_heart_rate"] == 41
    assert m17["body_battery_max"] == 85
    assert m17["hrv_last_night_avg"] == 69
    assert m17["hrv_status"] == "balanced"  # 69 / 64 = 1.07 within 0.85~1.15



