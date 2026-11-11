"""
Unit tests for COROS 2FA (Two-Factor Authentication / 手机二次安全验证).
Tests:
1. Detecting 2FA requirement during password login
2. Triggering SMS verification code
3. Exchanging 2FA code for accessToken and userId
4. End-to-end binding via auth router (bind_coros)
5. Device login with COROS 2FA code
"""

import pytest
import os
import json
from unittest.mock import MagicMock, patch

from utils.coros_adapter import CorosAdapter
from utils.local_store import LocalStore, init_db
from routers.auth import bind_coros, device_login, CorosBindRequest, DeviceLoginRequest, PENDING_COROS_2FA_ADAPTERS
from fastapi import BackgroundTasks

@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_coros_2fa.db")
    monkeypatch.setattr("utils.local_store.DB_PATH", test_db)
    init_db()
    monkeypatch.setattr("utils.coros_adapter.TOKEN_DIR", str(tmp_path / "tokens"))
    os.makedirs(str(tmp_path / "tokens"), exist_ok=True)
    PENDING_COROS_2FA_ADAPTERS.clear()
    return test_db


def test_coros_adapter_2fa_flow():
    adapter = CorosAdapter("18912367150", "SecretPassword123", "teamcnapi.coros.com")
    
    # Mock requests.post
    def mock_post(url, *args, **kwargs):
        if "/account/login" in url:
            return MagicMock(
                status_code=200,
                json=lambda: {
                    "result": "0000",
                    "message": "OK",
                    "data": {
                        "twoFactorRequired": True,
                        "loginTicket": "test_ticket_abc",
                        "appKey": "test_app_key_xyz",
                        "account": "+86-18912367150",
                        "accountType2fa": 1,
                        "regionId": 2
                    }
                }
            )
        elif "/account/captcha" in url:
            json_body = kwargs.get("json", {})
            assert json_body.get("codeType") == 20
            assert json_body.get("lengthType") == 2
            return MagicMock(status_code=200, json=lambda: {"result": "0000", "message": "OK"})
        elif "/account/2fa/login/verify" in url:
            json_body = kwargs.get("json", {})
            assert json_body.get("loginTicket") == "test_ticket_abc"
            assert json_body.get("appKey") == "test_app_key_xyz"
            if json_body.get("code") == "123456":
                return MagicMock(
                    status_code=200,
                    json=lambda: {
                        "result": "0000",
                        "data": {
                            "accessToken": "verified_access_token_999",
                            "userId": "438274210932998144",
                            "regionId": 2
                        }
                    }
                )
            else:
                return MagicMock(status_code=200, json=lambda: {"result": "2102", "message": "验证码错误"})
        return MagicMock(status_code=404)

    with patch("requests.post", side_effect=mock_post):
        # 1. First login attempt -> triggers 2FA
        ok = adapter.login(force=True, trigger_2fa_sms=True)
        assert ok is False
        assert adapter.needs_2fa is True
        assert adapter.login_ticket == "test_ticket_abc"
        assert adapter.app_key == "test_app_key_xyz"
        assert "6 位验证码" in adapter.last_error

        # 2. Complete 2FA with wrong code
        ok_wrong = adapter.complete_2fa("000000")
        assert ok_wrong is False
        assert "验证码错误" in adapter.last_error

        # 3. Complete 2FA with correct code
        with patch.object(adapter, "fetch_user_profile_info", return_value={"display_name": "Tony", "avatar_url": ""}):
            ok_correct = adapter.complete_2fa("123456")
            assert ok_correct is True
            assert adapter.access_token == "verified_access_token_999"
            assert adapter.user_id == "438274210932998144"
            assert adapter.needs_2fa is False


def test_coros_bind_endpoint_2fa_workflow():
    bg_tasks = BackgroundTasks()
    uid = "u_wx_test_pengfei"
    LocalStore.upsert_profile(uid, {"id": uid, "display_name": "测试跑者"})

    def mock_post(url, *args, **kwargs):
        if "/account/login" in url:
            return MagicMock(
                status_code=200,
                json=lambda: {
                    "result": "0000",
                    "data": {
                        "twoFactorRequired": True,
                        "loginTicket": "ticket_123",
                        "appKey": "key_456",
                        "account": "+86-18912367150",
                        "accountType2fa": 1
                    }
                }
            )
        elif "/account/captcha" in url:
            return MagicMock(status_code=200, json=lambda: {"result": "0000"})
        elif "/account/2fa/login/verify" in url:
            if kwargs.get("json", {}).get("code") == "654321":
                return MagicMock(
                    status_code=200,
                    json=lambda: {
                        "result": "0000",
                        "data": {
                            "accessToken": "coros_token_success_888",
                            "userId": "438274210932998144"
                        }
                    }
                )
            return MagicMock(status_code=200, json=lambda: {"result": "2102", "message": "验证码不正确"})
        return MagicMock(status_code=404)

    with patch("requests.post", side_effect=mock_post):
        # Step 1: Initial bind request without code -> Returns needs_2fa
        req1 = CorosBindRequest(
            uid=uid,
            account="18912367150",
            password="MySecretPassword",
            domain="teamcnapi.coros.com"
        )
        res1 = bind_coros(req1, bg_tasks)
        assert res1["needs_2fa"] is True
        assert res1["connected"] is False
        assert "验证码" in res1["message"]

        # Step 2: Second bind request with verification code -> Completes binding
        req2 = CorosBindRequest(
            uid=uid,
            account="18912367150",
            password="MySecretPassword",
            domain="teamcnapi.coros.com",
            code="654321"
        )
        res2 = bind_coros(req2, bg_tasks)
        assert res2["success"] is True
        assert res2["connected"] is True
        assert "绑定成功" in res2["message"]

        # Check DB updated
        profile = LocalStore.get_profile(uid)
        assert profile["coros_connected"] == 1
        assert profile["coros_account"] == "18912367150"


def test_coros_passwordless_reauth_and_cached_auth_state():
    """
    Verifies:
    1. CorosAdapter.get_cached_auth_state reports needs_reauth=True when 2FA circuit breaker is active.
    2. An already-bound owner can trigger 2FA SMS and complete verification with password="" (reusing stored encrypted password).
    3. A non-owner uid cannot trigger passwordless SMS for another runner's COROS account.
    4. Completing 2FA with rmbm=1 stores acct_ext_2 cookie and flips needs_reauth to False.
    """
    from fastapi import HTTPException
    from utils.encryption import encrypt_string

    bg_tasks = BackgroundTasks()
    owner_uid = "u_wx_82320f8a14"
    stranger_uid = "u_wx_other_runner"
    LocalStore.upsert_profile(owner_uid, {
        "id": owner_uid,
        "display_name": "王鹏飞",
        "coros_connected": 1,
        "coros_account": "18912367150",
        "coros_encrypted_password": encrypt_string("SavedSecret999"),
        "coros_domain": "teamcnapi.coros.com",
    })
    LocalStore.upsert_profile(stranger_uid, {
        "id": stranger_uid,
        "display_name": "其他跑者",
    })

    # Simulate legacy 7-day token expiring during background sync (trigger_2fa_sms=False)
    blocked_adapter = CorosAdapter("18912367150", "SavedSecret999", "teamcnapi.coros.com")
    blocked_adapter._save_auth_blocked(
        "needs_2fa",
        "高驰安全授权已到期，请前往【我的 → 手表连接】输入手机短信验证码完成重新授权。",
    )

    state_before = CorosAdapter.get_cached_auth_state("18912367150", "teamcnapi.coros.com")
    assert state_before["needs_reauth"] is True
    assert state_before["has_token"] is False
    assert state_before["blocked_reason"] == "needs_2fa"

    # Security check: stranger cannot omit password for owner's account
    with pytest.raises(HTTPException) as exc_info:
        bind_coros(
            CorosBindRequest(uid=stranger_uid, account="18912367150", password="", domain="teamcnapi.coros.com"),
            bg_tasks,
        )
    assert exc_info.value.status_code == 400

    def mock_post(url, *args, **kwargs):
        if "/account/login" in url:
            body = kwargs.get("json", {})
            assert body.get("rmbm") == 1
            return MagicMock(
                status_code=200,
                json=lambda: {
                    "result": "0000",
                    "data": {
                        "twoFactorRequired": True,
                        "loginTicket": "reauth_ticket_777",
                        "appKey": "reauth_key_888",
                        "account": "+86-18912367150",
                        "accountType2fa": 1,
                    },
                },
            )
        elif "/account/captcha" in url:
            return MagicMock(status_code=200, json=lambda: {"result": "0000"})
        elif "/account/2fa/login/verify" in url:
            body = kwargs.get("json", {})
            assert body.get("rmbm") == 1
            resp = MagicMock(
                status_code=200,
                json=lambda: {
                    "result": "0000",
                    "data": {
                        "accessToken": "rolling_30d_token_abc",
                        "userId": "438274210932998144",
                    },
                },
            )
            resp.cookies = {"acct_ext_2": "rolling_cookie_30d_xyz", "acct_uid_2": "438274210932998144"}
            return resp
        return MagicMock(status_code=404)

    with patch("requests.post", side_effect=mock_post), patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"result": "0000", "data": {}})

        # Owner requests SMS without re-entering password
        step1 = bind_coros(
            CorosBindRequest(uid=owner_uid, account="18912367150", password="", domain="teamcnapi.coros.com"),
            bg_tasks,
        )
        assert step1["needs_2fa"] is True

        # Circuit breaker stays active while waiting for user to type SMS code
        mid_state = CorosAdapter.get_cached_auth_state("18912367150", "teamcnapi.coros.com")
        assert mid_state["needs_reauth"] is True

        # Owner submits 6-digit SMS code without password
        step2 = bind_coros(
            CorosBindRequest(
                uid=owner_uid,
                account="18912367150",
                password="",
                domain="teamcnapi.coros.com",
                code="888666",
            ),
            bg_tasks,
        )
        assert step2["success"] is True
        assert step2["connected"] is True

    state_after = CorosAdapter.get_cached_auth_state("18912367150", "teamcnapi.coros.com")
    assert state_after["needs_reauth"] is False
    assert state_after["has_token"] is True
    assert state_after["has_refresh_cookie"] is True
