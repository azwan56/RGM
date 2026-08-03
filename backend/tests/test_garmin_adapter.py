"""
Unit tests for Garmin Adapter, Encryption, and Garmin Auth endpoints.
"""

import pytest
from utils.encryption import encrypt_string, decrypt_string
from utils.garmin_adapter import GarminAdapter

def test_encryption_decryption():
    raw_text = "MySecretGarminPassword123!"
    encrypted = encrypt_string(raw_text)
    assert encrypted != raw_text
    assert len(encrypted) > 0

    decrypted = decrypt_string(encrypted)
    assert decrypted == raw_text

def test_encryption_empty():
    assert encrypt_string("") == ""
    assert decrypt_string("") == ""

def test_garmin_adapter_normalize():
    adapter = GarminAdapter(email="test@example.com", password="pass", domain="garmin.cn")
    mock_raw_act = {
        "activityId": 123456789,
        "activityName": "Morning Tempo Run",
        "activityType": {"typeKey": "running"},
        "distance": 10000.0,
        "duration": 3000,
        "elapsedDuration": 3100,
        "startTimeLocal": "2026-08-03 07:00:00",
        "averageSpeed": 3.33,
        "maxSpeed": 4.5,
        "averageHR": 152,
        "maxHR": 175,
        "averageRunningCadenceInStepsPerMinute": 178,
        "elevationGain": 45.0,
        "summaryPolyline": "xyz123abc"
    }

    norm = adapter._normalize_activity(mock_raw_act)
    assert norm is not None
    assert norm["id"] == "garmin_123456789"
    assert norm["source"] == "garmin"
    assert norm["name"] == "Morning Tempo Run"
    assert norm["type"] == "Run"
    assert norm["distance"] == 10000.0
    assert norm["moving_time"] == 3000
    assert norm["average_heartrate"] == 152
    assert norm["average_cadence"] == 178
    assert norm["garmin_domain"] == "garmin.cn"

def test_garmin_adapter_domain_parsing():
    adapter_cn = GarminAdapter("user@test.com", "pass", domain="garmin.cn")
    assert adapter_cn.is_cn is True

    adapter_global = GarminAdapter("user@test.com", "pass", domain="garmin.com")
    assert adapter_global.is_cn is False
