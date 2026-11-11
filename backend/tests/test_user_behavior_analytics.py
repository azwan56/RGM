import os
import sys
import tempfile
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import jwt
import pytest

# Point RGM_DB_PATH to a disposable temp file BEFORE importing `main` so `main`'s import-time `init_db()` never touches real `data/rgm.db`
_BOOT_TMP_DB = os.path.join(tempfile.gettempdir(), f"rgm_boot_test_{os.getpid()}.db")
os.environ["RGM_DB_PATH"] = _BOOT_TMP_DB

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import utils.local_store as local_store_mod
import routers.miniapp as miniapp_router_mod
import routers.profile as profile_router_mod
import routers.auth as auth_router_mod
from fastapi.testclient import TestClient
from config import settings
from main import app
from routers.admin import ADMIN_EMAIL, ADMIN_PASSWORD
from utils.local_store import LocalStore, init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_temp_db(tmp_path, monkeypatch):
    """Isolates every test onto a fresh temporary SQLite database so real rgm.db is never touched or pruned."""
    temp_db = str(tmp_path / "test_rgm_isolated.db")
    monkeypatch.setattr(local_store_mod, "DB_PATH", temp_db)
    monkeypatch.setattr(miniapp_router_mod, "DB_PATH", temp_db)
    monkeypatch.setattr(miniapp_router_mod, "supabase_admin", None)
    monkeypatch.setattr(profile_router_mod, "supabase_admin", None)
    monkeypatch.setattr(auth_router_mod, "supabase_admin", None)
    miniapp_router_mod._TELEMETRY_RATE_BUCKETS.clear()
    LocalStore._last_telemetry_prune_ts = 0.0
    init_db()
    yield temp_db
    for p in (_BOOT_TMP_DB,):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _mint_user_jwt(uid: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": uid, "uid": uid, "iat": now, "exp": now + 3600},
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )


def _admin_headers() -> dict:
    login_resp = client.post(
        "/api/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert login_resp.status_code == 200
    return {"Authorization": f"Bearer {login_resp.json()['token']}"}


def test_end_to_end_user_behavior_telemetry_and_security(isolated_temp_db):
    sid = f"s_test_ux_{int(time.time() * 1000)}"
    old_sid = f"s_prev_leftover_{int(time.time() * 1000)}"
    test_uid = f"u_wx_ux_runner_{int(time.time())}"
    attacker_uid = "u_wx_attacker_888"
    spoof_uid = "u_wx_spoofed_victim_999"
    client_uuid = f"dev_iphone_15_pro_{int(time.time())}"
    base_ts = int(time.time() * 1000) - 3600_000  # 1 hour ago

    LocalStore.upsert_profile(
        test_uid,
        {
            "display_name": "张晓跑",
            "coros_connected": 1,
            "onboarding_completed": 1,
        },
    )

    # 1. Oversized events array (> 120) must be rejected by Pydantic validation
    oversized_resp = client.post(
        "/api/miniapp/telemetry/batch",
        json={
            "session_id": sid,
            "events": [{"event_name": f"ev_{i}"} for i in range(125)],
        },
    )
    assert oversized_resp.status_code == 422

    # 2. Pre-login batch WITH spoofed user_id in body (no Authorization JWT)
    batch1_resp = client.post(
        "/api/miniapp/telemetry/batch",
        json={
            "session_id": sid,
            "user_id": spoof_uid,
            "client_uuid": client_uuid,
            "scene": 1047,
            "entry_page": "pages/index/index",
            "device_model": "iPhone 15 Pro",
            "platform": "ios",
            "app_version": "2.0.0",
            "env_version": "release",
            "events": [
                {
                    "event_id": "e_1",
                    "event_type": "session_start",
                    "event_name": "app_open",
                    "event_label": "长按识别战报海报小程序码",
                    "page_path": "pages/index/index",
                    "client_ts": base_ts,
                },
                {
                    "event_id": "e_2",
                    "event_type": "page_enter",
                    "event_name": "page_view",
                    "event_label": "进入「首页」",
                    "page_path": "pages/index/index",
                    "client_ts": base_ts + 200,
                },
                {
                    "event_id": "e_3",
                    "event_type": "module_view",
                    "event_name": "home.goal_progress",
                    "event_label": "首页-周/月目标进度卡",
                    "page_path": "pages/index/index",
                    "client_ts": base_ts + 600,
                },
                {
                    "event_id": "e_4",
                    "event_type": "button_click",
                    "event_name": "home_sync_watch",
                    "event_label": "点击同步手表数据",
                    "page_path": "pages/index/index",
                    "client_ts": base_ts + 4200,
                },
                {
                    "event_id": "e_5",
                    "event_type": "app_background",
                    "event_name": "app_background",
                    "event_label": "切入后台或打开系统选择器",
                    "page_path": "pages/index/index",
                    "stay_ms": 5000,
                    "scroll_pct": None,
                    "client_ts": base_ts + 5000,
                },
            ],
        },
    )
    assert batch1_resp.status_code == 200
    assert batch1_resp.json()["accepted"] == 5
    assert batch1_resp.json()["user_id"] is None

    # 3. Attempting to bind a different JWT WITHOUT matching client_uuid must NOT hijack the session
    attacker_jwt = _mint_user_jwt(attacker_uid)
    hijack_resp = client.post(
        "/api/miniapp/telemetry/batch",
        headers={"Authorization": f"Bearer {attacker_jwt}"},
        json={
            "session_id": sid,
            # Omitted client_uuid intentionally!
            "events": [],
        },
    )
    assert hijack_resp.status_code == 200
    assert hijack_resp.json()["user_id"] is None

    with sqlite3.connect(isolated_temp_db) as conn:
        row = conn.execute(
            "SELECT user_id, duration_ms, ended_at, max_scroll_pct FROM miniapp_sessions WHERE session_id = ?",
            (sid,),
        ).fetchone()
        assert row is not None
        assert row[0] is None
        assert row[1] >= 5000
        assert row[2] is None  # app_background did NOT prematurely close session
        assert row[3] == 0

    # 4. Post-login batch WITH valid Bearer JWT + matching client_uuid + timed-out session_end timestamp
    end_client_ts = (base_ts // 1000) * 1000 + 33000  # exact second ~1 hour before current wall clock
    expected_ended_iso = datetime.fromtimestamp(
        end_client_ts / 1000.0, tz=timezone(timedelta(hours=8))
    ).isoformat(timespec="seconds")
    assert expected_ended_iso.endswith("+08:00")

    user_jwt = _mint_user_jwt(test_uid)
    batch2_resp = client.post(
        "/api/miniapp/telemetry/batch",
        headers={"Authorization": f"Bearer {user_jwt}"},
        json={
            "session_id": sid,
            "user_id": spoof_uid,
            "client_uuid": client_uuid,
            "events": [
                {
                    "event_id": "e_old_1",
                    "session_id": old_sid,
                    "event_type": "button_click",
                    "event_name": "leftover_prev_session_click",
                    "event_label": "上次会话残留点击",
                    "page_path": "pages/profile/profile",
                    "client_ts": base_ts - 600000,
                },
                {
                    "event_id": "e_6",
                    "event_type": "page_leave",
                    "event_name": "page_stay",
                    "event_label": "离开「首页」",
                    "page_path": "pages/index/index",
                    "stay_ms": 18500,
                    "scroll_pct": 88,
                    "props": {"max_scroll_px": 920, "reached_bottom": True},
                    "client_ts": base_ts + 18700,
                },
                {
                    "event_id": "e_7",
                    "event_type": "page_enter",
                    "event_name": "page_view",
                    "event_label": "进入「跑团」",
                    "page_path": "pages/team/team",
                    "client_ts": base_ts + 18800,
                },
                {
                    "event_id": "e_8",
                    "event_type": "funnel_step",
                    "event_name": "team_join_club_success",
                    "event_label": "成功加入跑团",
                    "page_path": "pages/team/team",
                    "client_ts": base_ts + 26000,
                },
                {
                    "event_id": "e_9",
                    "event_type": "page_leave",
                    "event_name": "page_stay",
                    "event_label": "离开「跑团」",
                    "page_path": "pages/team/team",
                    "stay_ms": 14000,
                    "scroll_pct": 62,
                    "client_ts": base_ts + 32800,
                },
                {
                    "event_id": "e_10",
                    "event_type": "session_end",
                    "event_name": "session_timeout_end",
                    "event_label": "后台超时结束会话",
                    "page_path": "pages/team/team",
                    "stay_ms": 33000,
                    "scroll_pct": 88,
                    "client_ts": end_client_ts,
                },
            ],
        },
    )
    assert batch2_resp.status_code == 200
    assert batch2_resp.json()["accepted"] == 6
    assert batch2_resp.json()["user_id"] == test_uid

    # Verify unauthorized admin analytics access is blocked
    unauth_resp = client.get("/api/admin/analytics/overview?days=7&include_wechat=false")
    assert unauth_resp.status_code in (401, 403)

    headers = _admin_headers()
    # Check raw SQLite column directly to ensure +08:00 suffix is stored at write time (not just added on read)
    with sqlite3.connect(isolated_temp_db) as conn:
        raw_ended = conn.execute(
            "SELECT ended_at FROM miniapp_sessions WHERE session_id = ?", (sid,)
        ).fetchone()[0]
        assert raw_ended == expected_ended_iso
        assert raw_ended.endswith("+08:00")

    tl_resp = client.get(f"/api/admin/analytics/sessions/{sid}", headers=headers)
    assert tl_resp.status_code == 200
    tl = tl_resp.json()
    assert tl["session"]["user_id"] == test_uid
    assert tl["session"]["display_name"] == "张晓跑"
    assert tl["session"]["ended_at"] == expected_ended_iso
    assert len(tl["events"]) == 10
    assert all(ev["event_name"] != "leftover_prev_session_click" for ev in tl["events"])


def test_duplicate_event_batches_are_idempotent():
    """P1 #3: Network retries or crash-queue replays of the same events must never double-insert or inflate counts."""
    sid = "s_dedup_outdoor_weak_net"
    ts = int(time.time() * 1000)
    payload = {
        "session_id": sid,
        "client_uuid": "c_outdoor_runner",
        "entry_page": "pages/index/index",
        "events": [
            {
                "event_id": "ev_open_1",
                "event_type": "page_enter",
                "event_name": "page_view",
                "page_path": "pages/index/index",
                "client_ts": ts,
            },
            {
                "event_id": "ev_click_sync_1",
                "event_type": "button_click",
                "event_name": "home_sync_watch",
                "page_path": "pages/index/index",
                "client_ts": ts + 1500,
            },
            {
                # Also test deterministic fallback dedup when event_id is omitted
                "event_type": "module_view",
                "event_name": "home.today_workout",
                "page_path": "pages/index/index",
                "client_ts": ts + 800,
            },
        ],
    }

    r1 = client.post("/api/miniapp/telemetry/batch", json=payload)
    assert r1.status_code == 200
    assert r1.json()["accepted"] == 3

    # Replay identical batch twice (simulating timeout + retry)
    r2 = client.post("/api/miniapp/telemetry/batch", json=payload)
    r3 = client.post("/api/miniapp/telemetry/batch", json=payload)
    assert r2.status_code == 200 and r2.json()["accepted"] == 0
    assert r3.status_code == 200 and r3.json()["accepted"] == 0

    headers = _admin_headers()
    tl = client.get(f"/api/admin/analytics/sessions/{sid}", headers=headers).json()
    assert len(tl["events"]) == 3
    assert tl["session"]["click_count"] == 1
    assert tl["session"]["page_count"] == 1


def test_module_exposure_rate_uses_same_page_sessions_denominator():
    """P1 #4b: Sessions that deep-link into non-Home pages must NOT dilute Home card exposure rates."""
    ts = int(time.time() * 1000)

    # Session 1 visits Home, sees both today_workout and goal_progress
    client.post(
        "/api/miniapp/telemetry/batch",
        json={
            "session_id": "s_home_1",
            "client_uuid": "c_1",
            "entry_page": "pages/index/index",
            "events": [
                {"event_type": "page_enter", "event_name": "page_view", "page_path": "pages/index/index", "client_ts": ts},
                {"event_type": "module_view", "event_name": "home.today_workout", "event_label": "首页-今日课表卡片", "page_path": "pages/index/index", "client_ts": ts + 100},
                {"event_type": "module_view", "event_name": "home.goal_progress", "event_label": "首页-周/月目标进度卡", "page_path": "pages/index/index", "client_ts": ts + 200},
            ],
        },
    )

    # Session 2 visits Home, sees only today_workout (bounces before scrolling to goal_progress)
    client.post(
        "/api/miniapp/telemetry/batch",
        json={
            "session_id": "s_home_2",
            "client_uuid": "c_2",
            "entry_page": "pages/index/index",
            "events": [
                {"event_type": "page_enter", "event_name": "page_view", "page_path": "pages/index/index", "client_ts": ts + 300},
                {"event_type": "module_view", "event_name": "home.today_workout", "event_label": "首页-今日课表卡片", "page_path": "pages/index/index", "client_ts": ts + 400},
            ],
        },
    )

    # Sessions 3, 4, 5 deep-link directly to share / group-run pages and NEVER visit Home
    for idx in (3, 4, 5):
        client.post(
            "/api/miniapp/telemetry/batch",
            json={
                "session_id": f"s_deeplink_{idx}",
                "client_uuid": f"c_{idx}",
                "entry_page": "pages/share/share",
                "events": [
                    {"event_type": "page_enter", "event_name": "page_view", "page_path": "pages/share/share", "client_ts": ts + idx * 500},
                ],
            },
        )

    headers = _admin_headers()
    ov = client.get("/api/admin/analytics/overview?days=7&include_wechat=false", headers=headers).json()
    assert ov["behavior"]["summary"]["total_sessions"] == 5

    mods = {m["event_name"]: m for m in ov["behavior"]["module_exposures"]}
    assert mods["home.today_workout"]["page_sessions"] == 2
    assert mods["home.today_workout"]["unique_sessions"] == 2
    assert mods["home.today_workout"]["exposure_pct"] == 100.0

    assert mods["home.goal_progress"]["page_sessions"] == 2
    assert mods["home.goal_progress"]["unique_sessions"] == 1
    assert mods["home.goal_progress"]["exposure_pct"] == 50.0


def test_weekly_goal_lock_preserved_on_dashboard_and_independent_monthly_preserved():
    """P1 #1 & P1 #2: Setting next week's target must NOT alter locked current-week target on Home dashboard or overwrite custom 300k monthly targets."""
    uid = "u_wx_goal_lock_runner"
    user_headers = {"Authorization": f"Bearer {_mint_user_jwt(uid)}"}

    LocalStore.upsert_profile(uid, {"display_name": "周目标跑者"})
    # Seed initial state (enforce_started_lock=False): current week = 50k, monthly = 300k across all 12 months
    LocalStore.upsert_goal(
        uid,
        {
            "target_distance": 300.0,
            "weekly_target": 50.0,
            "current_week_target": 50.0,
            "monthly_targets": [300] * 12,
            "period_type": "monthly",
        },
        enforce_started_lock=False,
    )

    # Simulate GoalSheetModal saving next week = 75k while preserving user's independent 300k/month targets
    save_resp = client.put(
        f"/api/profile/{uid}/goal",
        headers=user_headers,
        json={
            "weekly_target": 75,
            "next_weekly_target": 75,
            "target_distance": 300,
            "monthly_targets": [300] * 12,
            "period_type": "monthly",
            "target_period": "next_week",
            "enforce_started_lock": True,
        },
    )
    assert save_resp.status_code == 200
    saved_goal = save_resp.json()["goal"]
    assert saved_goal["current_week_target"] == 50.0
    assert saved_goal["next_weekly_target"] == 75.0
    assert saved_goal["monthly_targets"] == [300.0] * 12

    # Fetch MiniApp Home dashboard and verify current week remains 50k while next week shows 75k!
    dash_resp = client.get(f"/api/miniapp/dashboard/{uid}", headers=user_headers)
    assert dash_resp.status_code == 200
    dash = dash_resp.json()
    assert dash["weekly_progress"]["target_week_km"] == 50.0
    assert dash["weekly_progress"]["next_week_target_km"] == 75.0
    assert dash["progress"]["target_month_km"] == 300.0


def test_default_placeholder_nickname_is_upgraded_on_relogin():
    fake_openid = f"o_test_nick_fix_{int(time.time() * 1000)}"
    with patch("routers.auth.wechat_client.code_to_session", return_value={"openid": fake_openid}):
        r1 = client.post("/api/auth/wechat/miniapp-login", json={"code": "mock_wx_code_1"})
        assert r1.status_code == 200
        u1 = r1.json()
        assert u1["display_name"].startswith("跑者_")

        r2 = client.post(
            "/api/auth/wechat/miniapp-login",
            json={
                "code": "mock_wx_code_2",
                "nick_name": "林破三",
                "avatar_url": "https://rgm.vanpower.net/uploads/custom_avatar.jpg",
            },
        )
        assert r2.status_code == 200
        u2 = r2.json()
        assert u2["uid"] == u1["uid"]
        assert u2["display_name"] == "林破三"
        assert u2["avatar_url"] == "https://rgm.vanpower.net/uploads/custom_avatar.jpg"

        r3 = client.post(
            "/api/auth/wechat/miniapp-login",
            json={"code": "mock_wx_code_3", "nick_name": "微信用户"},
        )
        assert r3.status_code == 200
        assert r3.json()["display_name"] == "林破三"


def test_docker_bridge_proxy_ip_isolation_and_429_rate_limit():
    """P0 fix: Behind Docker Nginx (172.18.0.2), X-Real-IP isolates users, CGNAT shares 600/min, and limit returns 429."""
    docker_client = TestClient(app, client=("172.18.0.2", 51234))

    # Device A sends 45 batches from carrier IP 223.104.10.1 -> all 200 OK
    for i in range(45):
        r = docker_client.post(
            "/api/miniapp/telemetry/batch",
            headers={"X-Real-IP": "223.104.10.1"},
            json={"session_id": "s_rate_a", "client_uuid": "c_dev_a", "events": []},
        )
        assert r.status_code == 200

    # Batch #46 from Device A hits per-device 45/min cap -> MUST return HTTP 429 (not 200!)
    r_blocked = docker_client.post(
        "/api/miniapp/telemetry/batch",
        headers={"X-Real-IP": "223.104.10.1"},
        json={"session_id": "s_rate_a", "client_uuid": "c_dev_a", "events": []},
    )
    assert r_blocked.status_code == 429
    assert r_blocked.json()["rate_limited"] is True

    # Device B on SAME carrier CGNAT IP (223.104.10.1) behind SAME Docker Nginx (172.18.0.2) is NOT blocked!
    r_same_nat = docker_client.post(
        "/api/miniapp/telemetry/batch",
        headers={"X-Real-IP": "223.104.10.1"},
        json={"session_id": "s_rate_b", "client_uuid": "c_dev_b", "events": []},
    )
    assert r_same_nat.status_code == 200

    # Device C on another IP behind SAME Docker Nginx (172.18.0.2) is NOT blocked!
    r_other_ip = docker_client.post(
        "/api/miniapp/telemetry/batch",
        headers={"X-Real-IP": "117.136.20.2"},
        json={"session_id": "s_rate_c", "client_uuid": "c_dev_c", "events": []},
    )
    assert r_other_ip.status_code == 200


def test_stale_os_killed_sessions_auto_close_after_30_minutes(isolated_temp_db):
    """P2 #4 fix: Sessions killed by OS with no events for >= 30m automatically get ended_at = last_event_at."""
    cn_tz = timezone(timedelta(hours=8))
    stale_iso = (datetime.now(cn_tz) - timedelta(minutes=45)).isoformat(timespec="seconds")
    fresh_iso = (datetime.now(cn_tz) - timedelta(minutes=5)).isoformat(timespec="seconds")

    with sqlite3.connect(isolated_temp_db) as conn:
        conn.execute(
            """
            INSERT INTO miniapp_sessions (session_id, client_uuid, entry_page, started_at, last_event_at, ended_at, duration_ms)
            VALUES (?, 'c_stale', 'pages/index/index', ?, ?, NULL, 12000)
            """,
            ("s_killed_45m_ago", stale_iso, stale_iso),
        )
        conn.execute(
            """
            INSERT INTO miniapp_sessions (session_id, client_uuid, entry_page, started_at, last_event_at, ended_at, duration_ms)
            VALUES (?, 'c_fresh', 'pages/index/index', ?, ?, NULL, 4000)
            """,
            ("s_active_5m_ago", fresh_iso, fresh_iso),
        )
        conn.commit()

    headers = _admin_headers()
    ov = client.get("/api/admin/analytics/overview?days=7&include_wechat=false", headers=headers).json()
    by_sid = {s["session_id"]: s for s in ov["behavior"]["recent_sessions"]}

    assert by_sid["s_killed_45m_ago"]["ended_at"] == stale_iso
    assert by_sid["s_active_5m_ago"]["ended_at"] is None

