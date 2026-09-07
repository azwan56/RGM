import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore, init_db
from utils.running_metrics import get_age_from_dob
from utils.garmin_adapter import GarminAdapter
from utils.coros_adapter import CorosAdapter
from utils.encryption import encrypt_string

client = TestClient(app)

def test_profile_biometrics_crud():
    init_db()
    test_uid = "u_test_biometrics_runner"
    
    # 1. Upsert initial profile
    LocalStore.upsert_profile(test_uid, {
        "id": test_uid,
        "display_name": "Biometric Runner",
        "email": "bio@test.cn",
        "date_of_birth": "1973-12-18",
        "gender": "female",
        "height_cm": 170.0,
        "weight_kg": 52.8,
        "vo2max": 54.0,
        "max_heart_rate": 182,
        "resting_heart_rate": 48
    })

    # 2. Test GET profile
    res = client.get(f"/api/profile/{test_uid}")
    assert res.status_code == 200
    data = res.json()
    profile = data.get("profile", {})
    assert profile.get("date_of_birth") == "1973-12-18"
    assert profile.get("gender") == "female"
    assert profile.get("height_cm") == 170.0
    assert profile.get("weight_kg") == 52.8
    assert profile.get("vo2max") == 54.0
    assert profile.get("age") == get_age_from_dob("1973-12-18")
    assert profile.get("age") >= 50

    # 3. Test PUT profile update
    update_res = client.put(f"/api/profile/{test_uid}", json={
        "weight_kg": 51.5,
        "vo2max": 55.2,
        "date_of_birth": "1980-05-20"
    })
    assert update_res.status_code == 200
    
    # Verify updated values via GET
    res2 = client.get(f"/api/profile/{test_uid}")
    p2 = res2.json().get("profile", {})
    assert p2.get("weight_kg") == 51.5
    assert p2.get("vo2max") == 55.2
    assert p2.get("date_of_birth") == "1980-05-20"
    assert p2.get("age") == get_age_from_dob("1980-05-20")

    # Cleanup
    LocalStore.delete_profile(test_uid)

def test_sync_device_profile_mock(monkeypatch):
    init_db()
    test_uid = "u_test_sync_device_runner"
    
    LocalStore.upsert_profile(test_uid, {
        "id": test_uid,
        "display_name": "Device Runner",
        "garmin_connected": 1,
        "garmin_email": "garmin@test.cn",
        "garmin_encrypted_password": encrypt_string("valid_test_password"),
        "garmin_domain": "garmin.cn"
    })

    # Mock GarminAdapter
    monkeypatch.setattr(GarminAdapter, "login", lambda self: True)
    monkeypatch.setattr(GarminAdapter, "fetch_user_profile_info", lambda self: {
        "avatar_url": "https://garmin.com/test_avatar.jpg",
        "display_name": "Vivian Chen",
        "gender": "female",
        "date_of_birth": "1973-12-18",
        "height_cm": 170.0,
        "weight_kg": 52.8,
        "vo2max": 54.0,
        "max_heart_rate": 180,
        "resting_heart_rate": 49
    })

    sync_res = client.post(f"/api/profile/{test_uid}/sync-device-profile")
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data.get("success") is True
    p = sync_data.get("profile", {})
    assert p.get("date_of_birth") == "1973-12-18"
    assert p.get("gender") == "female"
    assert p.get("height_cm") == 170.0
    assert p.get("weight_kg") == 52.8
    assert p.get("vo2max") == 54.0
    assert p.get("age") == get_age_from_dob("1973-12-18")

    # Also test COROS sync
    coros_uid = "u_test_sync_coros_runner"
    LocalStore.upsert_profile(coros_uid, {
        "id": coros_uid,
        "display_name": "Coros Runner",
        "coros_connected": 1,
        "coros_account": "13900000000",
        "coros_encrypted_password": encrypt_string("coros_valid_pwd"),
        "coros_domain": "teamcnapi.coros.com"
    })

    monkeypatch.setattr(CorosAdapter, "login", lambda self: True)
    monkeypatch.setattr(CorosAdapter, "fetch_user_profile_info", lambda self: {
        "avatar_url": "https://coros.com/avatar.jpg",
        "display_name": "Coach Coros",
        "gender": "male",
        "date_of_birth": "1988-08-08",
        "height_cm": 178.0,
        "weight_kg": 64.5,
        "vo2max": 58.5,
        "max_heart_rate": 192,
        "resting_heart_rate": 52
    })

    sync_coros_res = client.post(f"/api/profile/{coros_uid}/sync-device-profile")
    assert sync_coros_res.status_code == 200
    c_data = sync_coros_res.json()
    assert c_data.get("success") is True
    cp = c_data.get("profile", {})
    assert cp.get("date_of_birth") == "1988-08-08"
    assert cp.get("gender") == "male"
    assert cp.get("height_cm") == 178.0
    assert cp.get("weight_kg") == 64.5
    assert cp.get("vo2max") == 58.5
    assert cp.get("age") == get_age_from_dob("1988-08-08")

    # Cleanup
    LocalStore.delete_profile(test_uid)
    LocalStore.delete_profile(coros_uid)

def test_estimate_vo2max_api():
    init_db()
    test_uid = "u_test_estimate_vdot_runner"
    
    # User with 5K PB 18:25 (1105s), 10K PB 36:52 (2212s), Full PB 3:12:05 (11525s)
    LocalStore.upsert_profile(test_uid, {
        "id": test_uid,
        "display_name": "PB Runner",
        "five_k_pb": 1105,
        "ten_k_pb": 2212,
        "marathon_pb": 11525,
        "max_heart_rate": 190,
        "resting_heart_rate": 52
    })

    # Test estimate without body (falls back to profile)
    res = client.post(f"/api/profile/{test_uid}/estimate-vo2max")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["estimated_vo2max"] is not None
    assert data["estimated_vo2max"] >= 50.0
    assert len(data["candidates"]) >= 3
    assert any("VDOT" in c["method"] for c in data["candidates"])

    # Test estimate with custom override in body and save=True
    override_res = client.post(f"/api/profile/{test_uid}/estimate-vo2max", json={
        "five_k_pb": "18:00", # 1080s -> VDOT ~55.9
        "save": True
    })
    assert override_res.status_code == 200
    odata = override_res.json()
    assert odata["success"] is True
    assert odata["estimated_vo2max"] >= 55.0

    # Verify profile vo2max was saved
    p = LocalStore.get_profile(test_uid)
    assert p["vo2max"] == odata["estimated_vo2max"]

    # Cleanup
    LocalStore.delete_profile(test_uid)

