import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore
from config import settings
import jwt
import time

client = TestClient(app)

def test_unbind_garmin_and_coros_scenarios():
    test_uid = "u_test_unbind_999"
    LocalStore.upsert_profile(test_uid, {
        "display_name": "UnbindTester",
        "garmin_connected": 1,
        "garmin_email": "test@garmin.com",
        "coros_connected": 1,
        "coros_account": "test_coros",
    })

    # Verify initial connected state
    p0 = LocalStore.get_profile(test_uid)
    assert p0["garmin_connected"] == 1
    assert p0["coros_connected"] == 1

    # 1. Unbind Garmin WITHOUT authorization header (should succeed because profile exists)
    res_garmin = client.post("/api/auth/garmin/unbind", json={"uid": test_uid})
    assert res_garmin.status_code == 200
    assert res_garmin.json()["success"] is True
    assert res_garmin.json()["connected"] is False

    p1 = LocalStore.get_profile(test_uid)
    assert p1["garmin_connected"] == 0
    assert p1["garmin_email"] == ""

    # 2. Re-bind Garmin state in local store
    LocalStore.upsert_profile(test_uid, {
        "garmin_connected": 1,
        "garmin_email": "test@garmin.com",
    })

    # 3. Unbind Garmin WITH valid authorization header
    token = jwt.encode(
        {"sub": test_uid, "uid": test_uid, "exp": int(time.time()) + 3600},
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256"
    )
    res_garmin_auth = client.post(
        "/api/auth/garmin/unbind",
        json={"uid": test_uid},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_garmin_auth.status_code == 200
    assert res_garmin_auth.json()["success"] is True

    p2 = LocalStore.get_profile(test_uid)
    assert p2["garmin_connected"] == 0

    # 4. Unbind COROS WITHOUT authorization header
    res_coros = client.post("/api/auth/coros/unbind", json={"uid": test_uid})
    assert res_coros.status_code == 200
    assert res_coros.json()["success"] is True
    assert res_coros.json()["connected"] is False

    p3 = LocalStore.get_profile(test_uid)
    assert p3["coros_connected"] == 0
    assert p3["coros_account"] == ""

    # 5. Non-existent profile should return 404
    res_404 = client.post("/api/auth/garmin/unbind", json={"uid": "u_non_existent_9999999"})
    assert res_404.status_code == 404

    # Cleanup
    LocalStore.delete_profile(test_uid)
