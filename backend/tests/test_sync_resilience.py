import pytest
from utils.local_store import LocalStore
from routers.sync import sync_single_user

def test_sync_unbound_variable_resilience():
    # User with only coros
    uid_coros = "test_resilience_coros"
    LocalStore.upsert_profile(uid_coros, {
        "display_name": "高驰用户",
        "garmin_connected": 0,
        "coros_connected": 1,
        "coros_account": "coros@test.com",
        "coros_encrypted_password": "invalid_pwd_here"
    })
    res = sync_single_user(uid_coros)
    # Must not raise UnboundLocalError
    assert "garmin_adapter" not in str(res.get("error", ""))

    # User with only garmin but invalid decryption/auth
    uid_garmin = "test_resilience_garmin"
    LocalStore.upsert_profile(uid_garmin, {
        "display_name": "佳明用户",
        "garmin_connected": 1,
        "garmin_email": "garmin@test.com",
        "garmin_encrypted_password": "invalid_pwd_here",
        "coros_connected": 0
    })
    res2 = sync_single_user(uid_garmin)
    # Must not raise UnboundLocalError
    assert "garmin_adapter" not in str(res2.get("error", ""))
