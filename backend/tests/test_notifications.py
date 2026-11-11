import time
from unittest.mock import patch
import jwt
import pytest
from fastapi.testclient import TestClient
from config import settings
from main import app
from utils.local_store import LocalStore

client = TestClient(app)
TEST_UID = "u_notif_runner_test"


def _auth_headers(uid: str = TEST_UID):
    token = jwt.encode(
        {
            "sub": uid,
            "uid": uid,
            "aud": "authenticated",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_test_runner():
    LocalStore.upsert_profile(TEST_UID, {
        "display_name": "推送测试跑者",
        "email": "notif_runner@example.com",
        "wechat_openid": "ogDgjx_mock_openid_123"
    })
    yield
    # Cleanup notifications
    import sqlite3
    from utils.local_store import DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        conn.cursor().execute("DELETE FROM system_notifications WHERE user_id = ?", (TEST_UID,))
        conn.cursor().execute("DELETE FROM profiles WHERE id = ?", (TEST_UID,))
        conn.commit()


def test_notifications_lifecycle():
    headers = _auth_headers()
    # 1. Initially 0 unread
    res = client.get(f"/api/notifications?user_id={TEST_UID}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["unread_count"] == 0

    # 2. Trigger test push (mock external WeChat subscribe send)
    with patch("utils.wechat.wechat_client.send_subscribe_message", return_value={"errcode": 0, "errmsg": "ok"}):
        push_res = client.post(
            "/api/notifications/test-push",
            json={
                "user_id": TEST_UID,
                "activity_name": "早间 10km 有氧跑",
                "distance_km": 10.0,
                "critique": "【测试评语】配速与心率处于良好稳态区间！",
            },
            headers=headers,
        )
    assert push_res.status_code == 200
    push_data = push_res.json()
    assert push_data["success"] is True
    assert push_data["wechat_bound"] is True
    assert "wechat_openid" not in push_data
    assert push_data["notification"] is not None

    notif_id = push_data["notification"]["id"]

    # 3. Check notifications list
    list_res = client.get(f"/api/notifications?user_id={TEST_UID}", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["unread_count"] == 1
    assert len(list_data["notifications"]) >= 1
    assert "Canova教练" in list_data["notifications"][0]["title"]

    # 4. Mark single as read
    read_res = client.post(f"/api/notifications/{notif_id}/read?user_id={TEST_UID}", headers=headers)
    assert read_res.status_code == 200
    assert read_res.json()["unread_count"] == 0

    # 5. Create another and test read-all
    with patch("utils.wechat.wechat_client.send_subscribe_message", return_value={"errcode": 0, "errmsg": "ok"}):
        client.post("/api/notifications/test-push", json={"user_id": TEST_UID}, headers=headers)
    read_all_res = client.post("/api/notifications/read-all", json={"user_id": TEST_UID}, headers=headers)
    assert read_all_res.status_code == 200
    assert read_all_res.json()["unread_count"] == 0
