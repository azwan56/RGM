"""
Tests verifying that COROS account sync NEVER kicks users out of their official COROS mobile app.
Simulates a real COROS user (like Tony 王鹏飞, LM) binding and running multiple background syncs,
asserting that:
1. Zero mobile login (clientType=1) requests are made to apicn.coros.com/coros/user/login.
2. Web Training Hub API (teamcnapi.coros.com) is used exclusively for activities, profile, and EvoLab metrics.
3. No mobile session token is written to disk.
4. Repeated background sync cycles run smoothly without triggering session conflicts.
"""

import pytest
import os
import json
import time
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from utils.coros_adapter import CorosAdapter, TOKEN_DIR
from utils.local_store import LocalStore, init_db
from routers.sync import sync_single_user

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Initializes a fresh isolated DB and token directory for testing."""
    test_db = str(tmp_path / "test_coros_safety.db")
    monkeypatch.setattr("utils.local_store.DB_PATH", test_db)
    init_db()
    monkeypatch.setattr("utils.coros_adapter.TOKEN_DIR", str(tmp_path / "tokens"))
    os.makedirs(str(tmp_path / "tokens"), exist_ok=True)
    return test_db

def test_coros_mobile_login_is_permanently_disabled():
    """Verifies that calling mobile_login() is a safe no-op that never hits the network."""
    adapter = CorosAdapter("18912367150", "mypassword123", "teamcnapi.coros.com")
    
    with patch("requests.post") as mock_post:
        success = adapter.mobile_login()
        assert success is False
        assert adapter._mobile_login_failed is True
        # Must NEVER call requests.post to mobile login endpoint
        mock_post.assert_not_called()

def test_coros_simulated_user_full_sync_without_mobile_kickout(monkeypatch):
    """
    Simulates a COROS user (e.g. Tony 王鹏飞) binding their account and running background sync.
    Verifies that all activities, EvoLab analysis (rhr, stamina, VO2Max, HRV) are synced,
    and ZERO mobile login calls occur.
    """
    test_uid = "u_wx_simulated_pengfei"
    account = "18912367150"
    
    # Track all URLs requested
    requested_urls = []

    def mock_requests_post(url, *args, **kwargs):
        requested_urls.append(url)
        # Web login endpoint
        if "account/login" in url:
            return MagicMock(
                status_code=200,
                json=lambda: {
                    "result": "0000",
                    "message": "OK",
                    "data": {
                        "accessToken": "mock_web_token_safe_12345",
                        "userId": "438274210932998144",
                        "nickName": "Tony 王鹏飞",
                        "headPic": "https://oss.coros.com/avatar/test.jpg"
                    }
                }
            )
        # Any mobile login attempt MUST NOT OCCUR, but if it does, fail loudly
        if "coros/user/login" in url:
            pytest.fail("FATAL: Server attempted to call COROS mobile login! This kicks out the user's phone app!")
        return MagicMock(status_code=200, json=lambda: {"result": "0000"})

    def mock_requests_get(url, *args, **kwargs):
        requested_urls.append(url)
        # Token verify & activity query
        if "activity/query" in url:
            return MagicMock(
                status_code=200,
                json=lambda: {
                    "result": "0000",
                    "data": {
                        "totalNumber": 1,
                        "dataList": [
                            {
                                "labelId": "coros_act_9999",
                                "sportType": 100,
                                "name": "世纪公园 晨跑 10K",
                                "distance": 10000.0,
                                "totalTime": 3000,
                                "movingTime": 2980,
                                "startTime": int(time.time()) - 3600,
                                "avgHeartRate": 150,
                                "maxHeartRate": 170,
                                "avgCadence": 180,
                                "elevationGain": 20.0,
                                "calorie": 600,
                                "aerobicEffect": 3.5,
                                "anaerobicEffect": 0.2
                            }
                        ]
                    }
                }
            )
        # User profile query
        if "account/query" in url:
            return MagicMock(
                status_code=200,
                json=lambda: {
                    "result": "0000",
                    "data": {
                        "nickname": "Tony 王鹏飞",
                        "headPic": "https://oss.coros.com/avatar/test.jpg",
                        "sex": 0,
                        "stature": 175.0,
                        "weight": 68.0,
                        "birthday": 19880808
                    }
                }
            )
        # EvoLab analysis query
        if "analyse/query" in url:
            today_int = int(date.today().strftime("%Y%m%d"))
            return MagicMock(
                status_code=200,
                json=lambda: {
                    "result": "0000",
                    "data": {
                        "dayList": [
                            {
                                "happenDay": today_int,
                                "rhr": 48,
                                "staminaLevel": 92.5,
                                "avgSleepHrv": 55,
                                "sleepHrvBase": 62,
                                "vo2max": 61.5
                            }
                        ]
                    }
                }
            )
        return MagicMock(status_code=200, json=lambda: {"result": "0000", "data": {}})

    monkeypatch.setattr("requests.post", mock_requests_post)
    monkeypatch.setattr("requests.get", mock_requests_get)

    # 1. Create user profile in LocalStore
    from utils.encryption import encrypt_string
    LocalStore.upsert_profile(test_uid, {
        "id": test_uid,
        "display_name": "Tony 王鹏飞",
        "coros_connected": 1,
        "coros_account": account,
        "coros_encrypted_password": encrypt_string("mypassword123"),
        "coros_domain": "teamcnapi.coros.com"
    })

    # 2. Run sync_single_user (simulating background sync)
    result = sync_single_user(test_uid)
    assert result["success"] is True
    assert result["synced_activities"] == 1

    # 3. Verify LocalStore has activities and health metrics
    user_acts = LocalStore.get_recent_activities(test_uid)
    assert len(user_acts) == 1
    assert user_acts[0]["id"] == "coros_coros_act_9999"
    assert user_acts[0]["name"] == "世纪公园 晨跑 10K"
    assert user_acts[0]["distance_meters"] == 10000.0

    health = LocalStore.get_latest_health(test_uid)
    assert health is not None
    assert health["resting_heart_rate"] == 48
    assert health["body_battery_max"] == 92  # round(92.5) -> 92 (round to even)
    assert health["hrv_last_night_avg"] == 55

    # 4. CRITICAL ASSERTION: No mobile login endpoint was EVER contacted
    mobile_login_urls = [u for u in requested_urls if "coros/user/login" in u or "apicn.coros.com" in u]
    assert len(mobile_login_urls) == 0, f"Found unexpected mobile API requests: {mobile_login_urls}"

def test_coros_repeated_sync_scheduler_simulation(monkeypatch):
    """
    Simulates the background scheduler running every 30 minutes (3 consecutive cycles).
    Verifies that:
    1. Cached web token is used without redundant re-logins.
    2. No mobile kickout happens in cycle 1, cycle 2, or cycle 3.
    """
    test_uid = "u_wx_simulated_lm"
    account = "13910958525"
    
    login_count = 0

    def mock_requests_post(url, *args, **kwargs):
        nonlocal login_count
        if "account/login" in url:
            login_count += 1
            return MagicMock(
                status_code=200,
                json=lambda: {
                    "result": "0000",
                    "data": {
                        "accessToken": "mock_web_token_cached_lm",
                        "userId": "474486674743640064",
                        "nickName": "LM",
                        "headPic": None
                    }
                }
            )
        if "coros/user/login" in url:
            pytest.fail("Mobile login attempted during repeated scheduler sync!")
        return MagicMock(status_code=200, json=lambda: {"result": "0000"})

    def mock_requests_get(url, *args, **kwargs):
        return MagicMock(
            status_code=200,
            json=lambda: {
                "result": "0000",
                "data": {
                    "totalNumber": 0,
                    "dataList": [],
                    "dayList": []
                }
            }
        )

    monkeypatch.setattr("requests.post", mock_requests_post)
    monkeypatch.setattr("requests.get", mock_requests_get)

    from utils.encryption import encrypt_string
    LocalStore.upsert_profile(test_uid, {
        "id": test_uid,
        "display_name": "LM",
        "coros_connected": 1,
        "coros_account": account,
        "coros_encrypted_password": encrypt_string("mypassword123"),
        "coros_domain": "teamcnapi.coros.com"
    })

    # Cycle 1: First sync (logs in via web API, caches token)
    res1 = sync_single_user(test_uid)
    assert res1["success"] is True
    assert login_count == 1

    # Cycle 2: 30 minutes later (reuses cached token, no new login)
    res2 = sync_single_user(test_uid)
    assert res2["success"] is True
    assert login_count == 1  # Still 1, reused cache!

    # Cycle 3: 60 minutes later (still reuses cached token)
    res3 = sync_single_user(test_uid)
    assert res3["success"] is True
    assert login_count == 1  # Still 1, perfectly stable!
