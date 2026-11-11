import gzip
import os
import time
from datetime import datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from config import settings
from main import app
from routers.sync import _parse_gpx_or_tcx_bytes
from utils.local_store import LocalStore
from utils.running_metrics import compute_canova_athlete_matrix
from utils.security import is_safe_external_url

client = TestClient(app)


def _make_jwt(uid: str, role: str = "user", is_super_admin: bool = False) -> str:
    return jwt.encode(
        {
            "sub": uid,
            "uid": uid,
            "role": role,
            "is_super_admin": is_super_admin,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )


def test_email_signup_and_login_password_enforcement():
    email = f"phase0_runner_{int(time.time() * 1000)}@example.com"

    # 1. Unregistered email login MUST fail with 401 (no passwordless account minting)
    res_unreg = client.post(
        "/api/auth/email/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert res_unreg.status_code == 401

    # 2. Signup succeeds and stores PBKDF2 hash (not plaintext)
    res_signup = client.post(
        "/api/auth/email/signup",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert res_signup.status_code == 200
    uid = res_signup.json()["user"]["id"]
    prof = LocalStore.get_profile(uid)
    assert prof is not None
    assert prof["password_hash"].startswith("pbkdf2_sha256$")
    assert "StrongPassword123!" not in prof["password_hash"]
    # New profiles should NOT fabricate default PBs
    assert prof.get("marathon_pb") is None

    try:
        # 3. Duplicate signup is rejected
        res_dup = client.post(
            "/api/auth/email/signup",
            json={"email": email, "password": "AnotherPassword999!"},
        )
        assert res_dup.status_code == 400

        # 4. Wrong password login MUST fail with 401
        res_bad = client.post(
            "/api/auth/email/login",
            json={"email": email, "password": "WrongPassword!"},
        )
        assert res_bad.status_code == 401

        # 5. Correct password login succeeds
        res_ok = client.post(
            "/api/auth/email/login",
            json={"email": email, "password": "StrongPassword123!"},
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["user"]["id"] == uid
    finally:
        LocalStore.delete_profile(uid)


def test_wechat_confirm_login_blocks_existing_profile_takeover():
    victim_uid = f"u_wx_victim_{int(time.time() * 1000)}"
    LocalStore.upsert_profile(
        victim_uid,
        {
            "display_name": "ExistingRunnerNoGarmin",
            "garmin_connected": 0,
            "coros_connected": 0,
        },
    )
    try:
        res = client.post(
            "/api/auth/wechat/confirm-login",
            json={"uid": victim_uid, "wechat_id": "AttackerName", "agree_terms": True},
        )
        assert res.status_code == 403
        assert LocalStore.get_profile(victim_uid)["display_name"] == "ExistingRunnerNoGarmin"
    finally:
        LocalStore.delete_profile(victim_uid)


def test_club_role_update_requires_owner_or_super_admin():
    owner_uid = f"u_p0_owner_{int(time.time() * 1000)}"
    member_uid = f"u_p0_member_{int(time.time() * 1000)}"
    target_uid = f"u_p0_target_{int(time.time() * 1000)}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "ClubOwner"})
    LocalStore.upsert_profile(member_uid, {"display_name": "RegularMember"})
    LocalStore.upsert_profile(target_uid, {"display_name": "TargetMember"})

    club = LocalStore.create_club(owner_uid, "Phase0SecurityClub", "desc", "上海")
    club_id = club["id"]
    LocalStore.join_club_by_id(member_uid, club_id)
    LocalStore.join_club_by_id(target_uid, club_id)

    try:
        # 1. Regular member attempting to promote self or others -> 403
        member_tok = _make_jwt(member_uid)
        res_forbid = client.post(
            f"/api/team/{club_id}/role",
            json={"operator_uid": member_uid, "target_uid": target_uid, "role": "coach"},
            headers={"Authorization": f"Bearer {member_tok}"},
        )
        assert res_forbid.status_code == 403

        # 2. Regular member spoofing owner_uid in body while holding member JWT -> 403
        res_spoof = client.post(
            f"/api/team/{club_id}/role",
            json={"operator_uid": owner_uid, "target_uid": member_uid, "role": "owner"},
            headers={"Authorization": f"Bearer {member_tok}"},
        )
        assert res_spoof.status_code == 403

        # 3. Legitimate club owner appointing coach -> 200
        owner_tok = _make_jwt(owner_uid)
        res_ok = client.post(
            f"/api/team/{club_id}/role",
            json={"operator_uid": owner_uid, "target_uid": target_uid, "role": "coach"},
            headers={"Authorization": f"Bearer {owner_tok}"},
        )
        assert res_ok.status_code == 200
    finally:
        LocalStore.delete_profile(owner_uid)
        LocalStore.delete_profile(member_uid)
        LocalStore.delete_profile(target_uid)


def test_admin_upload_logo_requires_super_admin_and_blocks_svg_xss():
    svg_payload = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

    # 1. Unauthenticated upload -> 401
    res_unauth = client.post(
        "/api/admin/upload-club-logo",
        files={"file": ("evil.svg", svg_payload, "image/svg+xml")},
    )
    assert res_unauth.status_code == 401

    # 2. Super Admin uploading SVG / XSS payload -> 400
    sa_tok = _make_jwt("rgm_super_admin", role="super_admin", is_super_admin=True)
    res_svg = client.post(
        "/api/admin/upload-club-logo",
        files={"file": ("evil.svg", svg_payload, "image/svg+xml")},
        headers={"Authorization": f"Bearer {sa_tok}"},
    )
    assert res_svg.status_code == 400

    # 3. Super Admin uploading valid PNG magic bytes -> 200
    valid_png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    res_png = client.post(
        "/api/admin/upload-club-logo",
        files={"file": ("logo.png", valid_png, "image/png")},
        headers={"Authorization": f"Bearer {sa_tok}"},
    )
    assert res_png.status_code == 200
    logo_url = res_png.json()["logo_url"]
    assert logo_url.endswith(".png")
    fname = os.path.basename(logo_url)
    uploaded_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "race_photos", fname)
    if os.path.exists(uploaded_path):
        os.remove(uploaded_path)


def test_ssrf_url_guard_blocks_loopback_private_and_cloud_metadata():
    assert is_safe_external_url("http://127.0.0.1:8000/api/admin") is False
    assert is_safe_external_url("http://localhost:8000/health") is False
    assert is_safe_external_url("http://169.254.169.254/latest/meta-data/") is False
    assert is_safe_external_url("http://100.100.100.200/latest/meta-data/") is False
    assert is_safe_external_url("http://10.0.0.8/internal.png") is False
    assert is_safe_external_url("http://192.168.1.1/admin.jpg") is False
    assert is_safe_external_url("file:///etc/passwd") is False


def test_gpx_parser_blocks_xml_entity_and_gzip_bombs():
    xxe_gpx = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
    ]>
    <gpx><trk><trkseg></trkseg></trk></gpx>
    """
    with pytest.raises(HTTPException) as exc_xml:
        _parse_gpx_or_tcx_bytes(xxe_gpx)
    assert exc_xml.value.status_code == 400

    # Gzip payload that expands past 25 MB limit
    oversized_gz = gzip.compress(b"0" * (26 * 1024 * 1024))
    with pytest.raises(HTTPException) as exc_gz:
        _parse_gpx_or_tcx_bytes(oversized_gz)
    assert exc_gz.value.status_code in (400, 413)


def test_upsert_activity_preserves_ai_journal_on_resync():
    uid = f"u_p0_act_{int(time.time() * 1000)}"
    act_id = f"act_p0_{int(time.time() * 1000)}"
    LocalStore.upsert_profile(uid, {"display_name": "JournalPreserver"})
    try:
        LocalStore.upsert_activity(
            {
                "id": act_id,
                "user_id": uid,
                "name": "Morning Run",
                "sport_type": "running",
                "start_time": "2026-11-10T06:30:00",
                "distance_meters": 10000,
                "moving_time_seconds": 3000,
                "elapsed_time_seconds": 3000,
                "ai_journal": "保持住了马拉松有氧稳态，心率漂移极小。",
            },
            notify=False,
            reconcile_plan=False,
        )
        # Re-sync without ai_journal and without segment_analysis_json
        LocalStore.upsert_activity(
            {
                "id": act_id,
                "user_id": uid,
                "name": "Morning Run",
                "sport_type": "running",
                "start_time": "2026-11-10T06:30:00",
                "distance_meters": 10000,
                "moving_time_seconds": 3000,
                "elapsed_time_seconds": 3000,
                "ai_journal": None,
            },
            notify=False,
            reconcile_plan=False,
        )
        acts = LocalStore.get_recent_activities(uid, limit=5)
        matched = next((a for a in acts if a["id"] == act_id), None)
        assert matched is not None
        assert matched["ai_journal"] == "保持住了马拉松有氧稳态，心率漂移极小。"
    finally:
        LocalStore.delete_profile(uid)


def test_daily_health_preserves_healthkit_sleep_and_sanitizes_garmin_non_wear():
    hk_uid = f"u_p0_hk_{int(time.time() * 1000)}"
    gm_uid = f"u_p0_gm_{int(time.time() * 1000)}"
    today_str = datetime.now().strftime("%Y-%m-%d")
    LocalStore.upsert_profile(hk_uid, {"display_name": "AppleWatchRunner", "apple_watch_connected": 1})
    LocalStore.upsert_profile(gm_uid, {"display_name": "GarminRunner", "garmin_connected": 1})
    try:
        # 1. Apple Watch overnight sleep (no HRV last night avg, but allow_non_hrv_sleep=True)
        LocalStore.upsert_daily_health(
            hk_uid,
            {
                "date": today_str,
                "resting_heart_rate": 49,
                "sleep_duration_seconds": 27000,
                "sleep_score": 84,
                "allow_non_hrv_sleep": True,
            },
        )
        # 2. Garmin daytime non-wear sync on another user MUST NOT wipe Apple Watch user's row
        LocalStore.upsert_daily_health(
            gm_uid,
            {
                "date": today_str,
                "resting_heart_rate": 62,
                "sleep_score": 78,
                "body_battery_max": 85,
                "hrv_last_night_avg": 0,
            },
        )

        hk_day = LocalStore.get_latest_health(hk_uid, max_age_days=5)
        assert hk_day is not None
        assert hk_day["resting_heart_rate"] == 49
        assert hk_day["sleep_duration_seconds"] == 27000
        assert hk_day["sleep_score"] == 84

        gm_day = LocalStore.get_latest_health(gm_uid, max_age_days=5)
        assert gm_day is not None
        assert gm_day["resting_heart_rate"] is None
        assert gm_day["sleep_score"] is None
    finally:
        LocalStore.delete_profile(hk_uid)
        LocalStore.delete_profile(gm_uid)


def test_canova_matrix_excludes_cycling_from_42d_km_and_vdot():
    today_iso = datetime.now().strftime("%Y-%m-%dT07:00:00")
    yesterday_iso = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT07:00:00")
    activities = [
        {
            "start_time": today_iso,
            "distance_meters": 10000,
            "moving_time_seconds": 2700,
            "duration_seconds": 2700,  # 4:30/km run
            "sport_type": "running",
            "name": "10km Tempo Run",
        },
        {
            "start_time": yesterday_iso,
            "distance_meters": 40000,
            "moving_time_seconds": 3600,
            "duration_seconds": 3600,  # 40 km/h road cycling!
            "sport_type": "cycling",
            "name": "Morning Ride",
        },
    ]
    matrix = compute_canova_athlete_matrix(profile={}, activities=activities)
    # Only the 10km run should count toward 42-day running volume (NOT 50km!)
    assert abs(matrix["km_42d"] - 10.0) < 0.2
    # VDOT for a 45:00 10K is ~45-46, NOT >80 from a 40 km/h bike ride
    assert 40.0 <= matrix["effective_vdot"] <= 52.0


def test_auth_middleware_blocks_query_uid_idor_spoofing():
    alice_uid = f"u_p0_alice_{int(time.time() * 1000)}"
    bob_uid = f"u_p0_bob_{int(time.time() * 1000)}"
    LocalStore.upsert_profile(alice_uid, {"display_name": "Alice"})
    LocalStore.upsert_profile(bob_uid, {"display_name": "Bob"})
    try:
        alice_tok = _make_jwt(alice_uid)
        res = client.get(
            f"/api/team/unaffiliated?viewer_uid={bob_uid}",
            headers={"Authorization": f"Bearer {alice_tok}"},
        )
        assert res.status_code == 403
    finally:
        LocalStore.delete_profile(alice_uid)
        LocalStore.delete_profile(bob_uid)
