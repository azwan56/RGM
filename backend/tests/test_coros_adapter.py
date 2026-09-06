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
    # 5,000 meters in 1,164 seconds = 232.8 sec/km = 3:52 /km
    assert pace_str(5000, 1164) == "3:52 /km"
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

