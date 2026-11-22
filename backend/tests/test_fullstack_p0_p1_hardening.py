import json
import math
import os
import sqlite3
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from config import settings
from main import _ensure_default_static_assets, app
from routers import assistant as assistant_mod
from routers import sync as sync_mod
from utils import garmin_adapter as garmin_mod
from utils.encryption import compute_phone_hmac, encrypt_string
from utils.geo_utils import compute_smoothed_elevation_gain, out_of_china
from utils.llm import LLMClient
from utils.local_store import DB_PATH, LocalStore, init_db
from utils.running_metrics import compute_ctl_atl_tsb
from utils.security import reset_rate_limits
from utils.wechat import WeChatAPI


@pytest.fixture(autouse=True)
def _clean_db_tables():
    reset_rate_limits()
    init_db()
    yield
    reset_rate_limits()


def _make_jwt(uid: str, extra: dict = None) -> str:
    payload = {
        "sub": uid,
        "uid": uid,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


def test_strict_jwt_middleware_and_public_legal_footers(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    client = TestClient(app)

    # 1. Public health + legal pages (with ICP footer) remain reachable without JWT
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["database"] == "ok"

    for legal_path in ("/privacy", "/citations"):
        r_leg = client.get(legal_path)
        assert r_leg.status_code == 200
        assert "© 2026 万跑科技（上海）有限公司." in r_leg.text
        assert "沪ICP备2026018807" in r_leg.text

    # 2. Invalid Bearer JWT returns 401
    r_bad_jwt = client.get(
        "/api/profile/u_strict_target",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert r_bad_jwt.status_code == 401

    # 3. Missing Bearer JWT on private route returns 401 in strict mode
    r_no_auth = client.get("/api/profile/u_strict_target")
    assert r_no_auth.status_code == 401

    # 4. Spoofing viewer_uid / operator_uid / x-user-id returns 403
    alice_tok = _make_jwt("u_hardening_alice")
    LocalStore.upsert_profile("u_hardening_alice", {"display_name": "Alice"})
    r_spoof_header = client.get(
        "/api/profile/u_hardening_alice",
        headers={"Authorization": f"Bearer {alice_tok}", "x-user-id": "u_someone_else"},
    )
    assert r_spoof_header.status_code == 403

    r_spoof_query = client.get(
        "/api/notifications/u_hardening_alice?viewer_uid=u_someone_else",
        headers={"Authorization": f"Bearer {alice_tok}"},
    )
    assert r_spoof_query.status_code == 403


def test_local_store_column_allowlist_phone_hmac_ttl_and_pipl_deletion():
    uid = "u_pipl_hardening_01"
    phone = "13912345678"
    # Arbitrary SQL/unknown column should be filtered without raising SQL error or altering schema
    LocalStore.upsert_profile(
        uid,
        {
            "display_name": "合规跑者",
            "phone": phone,
            "malicious_col": "DROP TABLE profiles;",
        },
    )
    with sqlite3.connect(DB_PATH) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(profiles)").fetchall()]
        assert "malicious_col" not in cols
        row = conn.execute("SELECT phone_hmac FROM profiles WHERE id = ?", (uid,)).fetchone()
        assert row is not None
        assert row[0] == compute_phone_hmac(phone)

    # Race intel cache honors 90-day TTL
    cache_key = "test_shanghai_ttl::42.2"
    LocalStore.set_cached_race_intel(
        cache_key=cache_key,
        event_name="上海马拉松测试",
        race_category="road",
        race_info={"race_distance_km": 42.195},
        source="official_web_search",
    )
    assert LocalStore.get_cached_race_intel(cache_key) is not None
    stale_iso = (datetime.utcnow() - timedelta(days=95)).isoformat() + "Z"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE race_intel_cache SET updated_at = ? WHERE cache_key = ?", (stale_iso, cache_key))
        conn.commit()
    assert LocalStore.get_cached_race_intel(cache_key) is None

    # Full PIPL account deletion erases profile and notifications
    LocalStore.create_system_notification(uid, "测试通知", "测试内容")
    LocalStore.delete_user_account_completely(uid)
    assert LocalStore.get_profile(uid) is None
    assert LocalStore.get_user_notifications(uid) == []


def test_garmin_circuit_breaker_no_fake_pb_and_sync_abort(tmp_path, monkeypatch):
    monkeypatch.setattr(garmin_mod, "TOKEN_DIR", str(tmp_path))
    monkeypatch.setattr(garmin_mod, "HAS_GARMINCONNECT", True)

    login_calls = {"count": 0}

    class FakeFailingGarmin:
        def __init__(self, email, password, is_cn=True, return_on_mfa=True):
            self.client = None

        def login(self, tokenstore=None):
            login_calls["count"] += 1
            return "needs_mfa", None

    monkeypatch.setattr(garmin_mod, "Garmin", FakeFailingGarmin, raising=False)

    adapter = garmin_mod.GarminAdapter("runner@garmin.cn", "SecretPwd123", domain="garmin.cn")
    assert adapter.login(use_token=True) is False
    assert adapter.needs_mfa is True
    assert adapter.auth_blocked is True
    assert adapter._login_failed is True
    assert os.path.exists(adapter.auth_blocked_path)
    assert login_calls["count"] == 1

    # Subsequent calls on same instance or fresh background sync hit persistent circuit breaker immediately
    assert adapter.fetch_activities_by_date("2026-01-01") == []
    assert adapter.fetch_daily_health_metrics("2026-11-19") == {}
    assert login_calls["count"] == 1

    adapter2 = garmin_mod.GarminAdapter("runner@garmin.cn", "SecretPwd123", domain="garmin.cn")
    assert adapter2.login(use_token=True) is False
    assert adapter2.auth_blocked is True
    assert login_calls["count"] == 1

    # Unbind helper cleans both token and .blocked.json
    garmin_mod.remove_cached_garmin_tokens("runner@garmin.cn")
    assert not os.path.exists(adapter.auth_blocked_path)

    # Personal records must never fabricate 1140 (19:00) 5K PB
    pb_adapter = garmin_mod.GarminAdapter("pb@garmin.cn", "SecretPwd123", domain="garmin.cn")
    pb_adapter.client = MagicMock()
    pb_adapter.client.get_personal_record.return_value = [{"typeId": 4, "value": 2400}]
    prs = pb_adapter.fetch_personal_records()
    assert prs["ten_k_pb"] == 2400
    assert prs["five_k_pb"] is None

    # sync_single_user aborts on auth block and does NOT overwrite garmin_last_sync_at
    uid = "u_garmin_cb_sync"
    old_sync_ts = "2026-11-10T08:00:00Z"
    LocalStore.upsert_profile(
        uid,
        {
            "display_name": "GarminBlockedRunner",
            "garmin_connected": 1,
            "garmin_email": "blocked_sync@garmin.cn",
            "garmin_encrypted_password": encrypt_string("SecretPwd123"),
            "garmin_domain": "garmin.cn",
            "garmin_last_sync_at": old_sync_ts,
        },
    )
    blocked_adapter = garmin_mod.GarminAdapter("blocked_sync@garmin.cn", "SecretPwd123", domain="garmin.cn")
    blocked_adapter._save_auth_blocked("needs_mfa", "佳明安全验证码过期")
    try:
        res = sync_mod.sync_single_user(uid)
        assert res["success"] is False
        assert bool(res.get("error"))
        assert LocalStore.get_profile(uid).get("garmin_last_sync_at") == old_sync_ts
    finally:
        garmin_mod.remove_cached_garmin_tokens("blocked_sync@garmin.cn")


def test_china_geo_boundaries_elevation_smoothing_and_pmc_math():
    # Mainland China coordinates -> out_of_china(lng, lat) is False (requires GCJ-02 shift)
    for lng, lat in [
        (114.05, 22.55),   # Shenzhen
        (121.47, 31.23),   # Shanghai
        (116.40, 39.90),   # Beijing
        (109.51, 18.25),   # Sanya (Hainan)
        (126.64, 45.75),   # Harbin
    ]:
        assert out_of_china(lng, lat) is False

    # Outside Mainland China datum -> True (no GCJ-02 shift)
    for lng, lat in [
        (114.17, 22.28),   # Hong Kong
        (113.54, 22.19),   # Macau
        (121.56, 25.03),   # Taipei
        (139.69, 35.68),   # Tokyo
        (126.97, 37.56),   # Seoul
    ]:
        assert out_of_china(lng, lat) is True

    # Flat road with +/-0.5m barometric jitter -> ~0m gain
    jitter = [10.0, 10.6, 9.9, 10.5, 10.1, 10.4, 9.8, 10.2] * 3
    assert (compute_smoothed_elevation_gain(jitter) or 0.0) <= 1.5

    # Continuous Banister exponential decay 1 - exp(-1 / tau)
    series = [("2026-11-01", 100.0)]
    pmc = compute_ctl_atl_tsb(series)
    assert len(pmc) == 1
    expected_ctl = round(100.0 * (1.0 - math.exp(-1.0 / 42.0)), 1)
    expected_atl = round(100.0 * (1.0 - math.exp(-1.0 / 7.0)), 1)
    assert pmc[0]["ctl"] == expected_ctl
    assert pmc[0]["atl"] == expected_atl


def test_llm_tiers_assistant_short_circuit_wechat_ugc_and_static_svgs(monkeypatch):
    assert settings.LLM_MODEL_REASONING == "qwen-max"
    assert settings.LLM_MODEL_WORKHORSE == "qwen-plus"
    assert settings.LLM_MODEL_FAST == "qwen-flash"
    assert settings.LLM_MODEL_OCR == "qwen3.5-ocr"
    assert isinstance(LLMClient(), LLMClient)

    # Strong deterministic query short-circuits without calling LLM
    called = {"llm": False}
    monkeypatch.setattr(assistant_mod.llm_client, "_get_client", lambda: object())

    def _spy_chat(*args, **kwargs):
        called["llm"] = True
        return "{}"

    monkeypatch.setattr(assistant_mod.llm_client, "chat_completion", _spy_chat)
    client = TestClient(app)
    res_det = client.post(
        "/api/assistant/navigate",
        json={"query": "绑定佳明手表", "user_roles": {"logged_in": True}},
    )
    assert res_det.status_code == 200
    assert res_det.json()["primary_id"] == "bind-garmin"
    assert res_det.json()["engine"] == "deterministic"
    assert called["llm"] is False

    # WeChat msg_sec_check rejects risky text with HTTP 400
    wx = WeChatAPI(app_id="wx_test_appid", app_secret="wx_test_secret")
    monkeypatch.setattr(wx, "get_access_token", lambda force_refresh=False: "tok_123")
    with patch("utils.wechat.requests.post") as m_post:
        m_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"errcode": 0, "result": {"suggest": "risky", "label": 20001}},
        )
        with pytest.raises(HTTPException) as exc:
            wx.ensure_ugc_text_safe("违规文本", openid="o_test", scene=2)
        assert exc.value.status_code == 400

    # Default SVG static assets are seeded and served cleanly
    _ensure_default_static_assets()
    for fname in ("default-avatar.svg", "default-club.svg", "default-banner.svg", "default-run.svg"):
        r_svg = client.get(f"/api/avatars/{fname}")
        assert r_svg.status_code == 200
        assert "<svg" in r_svg.text
