import pytest
from unittest.mock import MagicMock, patch
from utils.garmin_adapter import GarminAdapter, HAS_GARMINCONNECT
import garminconnect.client as gc_client

def test_garminconnect_patch_applied():
    """Verify garminconnect client has been properly patched with CN support."""
    if not HAS_GARMINCONNECT:
        pytest.skip("garminconnect not installed")

    assert getattr(gc_client, "_rgm_cn_patched", False) is True

def test_garmin_adapter_error_formatting():
    """Verify error messages are formatted clearly for users."""
    msg1 = GarminAdapter._format_error("ACCOUNT_LOCKED generalLoginAccountLocked", "garmin.cn")
    assert "锁定" in msg1

    msg2 = GarminAdapter._format_error("429 rate limit exceeded", "garmin.cn")
    assert "频繁" in msg2

    msg3 = GarminAdapter._format_error("401 Unauthorized (Invalid Username or Password)", "garmin.cn")
    assert "中国版 (garmin.cn)" in msg3

    msg4 = GarminAdapter._format_error("Portal login failed (non-JSON): HTTP 403", "garmin.cn")
    assert "中国版 (garmin.cn)" in msg4

def test_garmin_adapter_domain_parsing():
    """Verify domain initialization flags."""
    adapter_cn = GarminAdapter("user@test.com", "pass", "garmin.cn")
    assert adapter_cn.is_cn is True
    assert adapter_cn.domain == "garmin.cn"

    adapter_com = GarminAdapter("user@test.com", "pass", "garmin.com")
    assert adapter_com.is_cn is False
    assert adapter_com.domain == "garmin.com"

def test_garmin_adapter_cn_token_url():
    """Verify that Client uses domain-aware diauth URL."""
    if not HAS_GARMINCONNECT:
        pytest.skip("garminconnect not installed")

    client = gc_client.Client(domain="garmin.cn")
    with patch.object(client, "_http_post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "dummy.eyJzdWIiOiIxMjMifQ.sig",
            "refresh_token": "dummy_refresh",
        }
        mock_post.return_value = mock_resp

        client._exchange_service_ticket("ST-123-ticket", service_url="https://mobile.integration.garmin.com/gcm/ios")

        # Verify that the URL posted to is diauth.garmin.cn
        assert mock_post.called
        call_url = mock_post.call_args[0][0]
        assert "diauth.garmin.cn" in call_url
        assert client.di_token == "dummy.eyJzdWIiOiIxMjMifQ.sig"
