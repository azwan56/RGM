import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore

client = TestClient(app)

def test_wechat_app_login_consistency_with_miniapp():
    """
    Verify that when an iOS App user logs in via WeChat with the same UnionID,
    it maps to the existing user profile created by the WeChat Mini Program.
    """
    test_unionid = "test_unionid_12345_runners"
    test_miniapp_openid = "test_openid_miniapp_6789"
    test_uid = "u_wx_testconsistency"

    # Seed an existing runner profile (simulating Mini-Program user)
    LocalStore.upsert_profile(test_uid, {
        "id": test_uid,
        "display_name": "马拉松老兵",
        "wechat_openid": test_miniapp_openid,
        "wechat_unionid": test_unionid,
        "garmin_connected": 1,
        "garmin_email": "runner@test.com",
    })

    # iOS App performs WeChat login with the same UnionID
    resp = client.post("/api/auth/app/wechat-login", json={
        "unionid": test_unionid,
        "openid": "test_openid_ios_app",
        "nick_name": "马拉松老兵"
    })

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["uid"] == test_uid, f"Expected uid {test_uid}, got {data['uid']}"
    assert data["display_name"] == "马拉松老兵"
    assert data["garmin_connected"] is True
    assert "token" in data and len(data["token"]) > 10

def test_apple_login_and_subsequent_login():
    """
    Verify Sign in with Apple creates profile and issues JWT,
    and second login returns the identical user.
    """
    test_apple_id = "001234.apple.test.sub"
    resp = client.post("/api/auth/apple/login", json={
        "apple_user_id": test_apple_id,
        "full_name": "Apple跑友",
        "email": "apple_runner@privaterelay.appleid.com"
    })

    assert resp.status_code == 200, resp.text
    data = resp.json()
    uid = data["uid"]
    assert "u_apl_" in uid
    assert data["display_name"] == "Apple跑友"
    assert "token" in data

    # Second login with same Apple ID
    resp2 = client.post("/api/auth/apple/login", json={
        "apple_user_id": test_apple_id,
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["uid"] == uid, "Subsequent Apple login must match identical user"
