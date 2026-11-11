import sqlite3
import time
from datetime import timedelta
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient

from config import settings
from main import app
from utils.local_store import DB_PATH, LocalStore, get_beijing_today
from utils.metrics_domain import MetricsDomainService

client = TestClient(app)


def _make_jwt(uid: str, is_super_admin: bool = False) -> str:
    return jwt.encode(
        {
            "sub": uid,
            "uid": uid,
            "aud": "authenticated",
            "is_super_admin": is_super_admin,
            "exp": int(time.time()) + 3600,
        },
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )


def test_metrics_domain_ctl_atl_tsb_parity_and_exclusion():
    uid = f"u_p1_metrics_{int(time.time() * 1000)}"
    today_bj = get_beijing_today()
    LocalStore.upsert_profile(
        uid,
        {
            "id": uid,
            "display_name": "指标一致性测试跑者",
            "gender": "male",
            "max_heart_rate": 190,
            "resting_heart_rate": 52,
        },
    )

    # 1. Warm-up run 120 days ago (inside 180d warm-up, outside 90d/30d display window)
    d_warmup = (today_bj - timedelta(days=120)).isoformat()
    LocalStore.upsert_activity(
        {
            "id": f"act_warm_{uid}",
            "user_id": uid,
            "name": "冬训有氧跑",
            "sport_type": "Run",
            "start_time": f"{d_warmup}T07:00:00",
            "distance_meters": 18000.0,
            "duration_seconds": 5400,
            "average_heartrate": 152,
            "trimp": 115.0,
        },
        notify=False,
        reconcile_plan=False,
    )

    # 2. Recent valid run 2 days ago
    d_recent = (today_bj - timedelta(days=2)).isoformat()
    LocalStore.upsert_activity(
        {
            "id": f"act_rec_{uid}",
            "user_id": uid,
            "name": "节奏跑",
            "sport_type": "TrailRun",
            "start_time": f"{d_recent}T06:30:00",
            "distance_meters": 14000.0,
            "duration_seconds": 4000,
            "average_heartrate": 164,
            "trimp": 130.0,
        },
        notify=False,
        reconcile_plan=False,
    )

    # 3. Excluded GPS anomaly run yesterday (must NOT affect CTL/ATL/TSB)
    d_excl = (today_bj - timedelta(days=1)).isoformat()
    LocalStore.upsert_activity(
        {
            "id": f"act_excl_{uid}",
            "user_id": uid,
            "name": "异常飙车记录",
            "sport_type": "Run",
            "start_time": f"{d_excl}T08:00:00",
            "distance_meters": 50000.0,
            "duration_seconds": 3600,
            "average_heartrate": 188,
            "trimp": 999.0,
            "exclude_mode": "excluded",
        },
        notify=False,
        reconcile_plan=False,
    )

    token = _make_jwt(uid)
    res_web = client.get(f"/api/science/metrics/{uid}", headers={"Authorization": f"Bearer {token}"})
    assert res_web.status_code == 200
    web_data = res_web.json()

    res_mini = client.get(f"/api/miniapp/dashboard/{uid}", headers={"Authorization": f"Bearer {token}"})
    assert res_mini.status_code == 200
    mini_metrics = res_mini.json()["fitness_form"]

    assert web_data["current_ctl"] == mini_metrics["ctl"]
    assert web_data["current_atl"] == mini_metrics["atl"]
    assert web_data["current_tsb"] == mini_metrics["tsb"]
    expected_badge = MetricsDomainService.get_tsb_badge_info(web_data["current_tsb"])
    assert web_data["current_tsb_badge"]["label"] == expected_badge["label"]
    assert mini_metrics["status_label"] == expected_badge["label"]
    assert mini_metrics["status_color"] == expected_badge["color"]
    # Excluded 999 TRIMP must not blow up ATL (>100 if included; ~16.8 when excluded)
    assert web_data["current_atl"] < 40.0


def test_web_wechat_qr_login_lifecycle_and_replay_protection():
    uid = f"u_wx_qr_{int(time.time() * 1000)}"
    LocalStore.upsert_profile(
        uid,
        {
            "id": uid,
            "display_name": "扫码登录跑者",
            "avatar_url": "https://rgm.vanpower.net/api/avatars/rgm-logo.png",
            "garmin_connected": 1,
        },
    )
    fake_png = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 600)

    with patch("routers.auth.wechat_client.get_wxacode_unlimit", return_value=fake_png):
        res_create = client.post("/api/auth/wechat/web-qr/create")
    assert res_create.status_code == 200
    c_data = res_create.json()
    scene_id = c_data["scene_id"]
    assert scene_id.startswith("wlogin_")
    assert len(scene_id) <= 32
    assert c_data["has_official_wxacode"] is True
    assert c_data["qrcode_base64"].startswith("data:image/png;base64,")
    assert c_data["miniapp_path"] == f"/pages/share/share?scene={scene_id}"

    # Initial poll -> pending
    r_p1 = client.get(f"/api/auth/wechat/web-qr/status/{scene_id}")
    assert r_p1.status_code == 200
    assert r_p1.json()["status"] == "pending"

    # Phone scans QR code -> scanned
    r_scan = client.post(
        "/api/auth/wechat/web-qr/scan",
        json={"scene_id": scene_id, "display_name": "扫码登录跑者"},
    )
    assert r_scan.status_code == 200
    r_p2 = client.get(f"/api/auth/wechat/web-qr/status/{scene_id}")
    assert r_p2.json()["status"] == "scanned"
    assert r_p2.json()["display_name"] == "扫码登录跑者"

    # Unauthenticated confirm attempt MUST fail with 401
    r_unauth = client.post("/api/auth/wechat/web-qr/confirm", json={"scene_id": scene_id})
    assert r_unauth.status_code == 401

    # Authenticated confirm with MiniApp Bearer JWT succeeds
    mini_token = _make_jwt(uid)
    r_conf = client.post(
        "/api/auth/wechat/web-qr/confirm",
        json={"scene_id": scene_id},
        headers={"Authorization": f"Bearer {mini_token}"},
    )
    assert r_conf.status_code == 200
    assert r_conf.json()["status"] == "confirmed"

    # First Web status poll claims JWT session
    r_claim = client.get(f"/api/auth/wechat/web-qr/status/{scene_id}")
    assert r_claim.status_code == 200
    claim_json = r_claim.json()
    assert claim_json["status"] == "confirmed"
    assert claim_json["uid"] == uid
    assert claim_json["user"]["id"] == uid
    assert claim_json["user"]["display_name"] == "扫码登录跑者"
    decoded = jwt.decode(
        claim_json["token"],
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    assert decoded["uid"] == uid

    # Replay poll MUST NOT mint a second token
    r_replay = client.get(f"/api/auth/wechat/web-qr/status/{scene_id}")
    assert r_replay.status_code == 200
    assert r_replay.json()["status"] == "consumed"
    assert "token" not in r_replay.json()


def test_atomic_merge_user_profiles_preserves_clubs_plans_and_redirects_uid():
    ts = int(time.time() * 1000)
    src_uid = f"u_wx_src_{ts}"
    tgt_uid = f"u_garmin_tgt_{ts}"
    club_id = f"club_merge_{ts}"

    LocalStore.upsert_profile(src_uid, {"id": src_uid, "display_name": "微信临时号", "wechat_openid": f"oid_{ts}"})
    LocalStore.upsert_profile(tgt_uid, {"id": tgt_uid, "display_name": "佳明老账号", "garmin_connected": 1})

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO clubs (id, name, city, invite_code, owner_id, created_at) VALUES (?, ?, '上海', ?, ?, '2026-01-01T00:00:00Z')",
            (club_id, "合并测试跑团", f"MG{ts % 10000:04d}", tgt_uid),
        )
        # Source is coach, target is member -> merged target must retain 'coach'
        conn.execute(
            "INSERT INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES (?, ?, ?, 'coach', 'active', '2026-01-01T00:00:00Z')",
            (f"{club_id}_{src_uid}", club_id, src_uid),
        )
        conn.execute(
            "INSERT INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES (?, ?, ?, 'member', 'active', '2026-01-01T00:00:00Z')",
            (f"{club_id}_{tgt_uid}", club_id, tgt_uid),
        )
        conn.execute(
            """
            INSERT INTO training_plans (id, user_id, title, goal_type, status, schedule_data, creator_id, created_at, updated_at)
            VALUES (?, ?, '全马破三课表', 'race_prep', 'active', '{"weeks":[]}', ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """,
            (f"tp_{ts}", src_uid, src_uid),
        )
        conn.commit()

    LocalStore.upsert_activity(
        {
            "id": f"act_keep_{ts}",
            "user_id": src_uid,
            "name": "合并保留跑",
            "sport_type": "Run",
            "start_time": "2026-03-01T07:00:00",
            "distance_meters": 10000.0,
            "duration_seconds": 3000,
        },
        notify=False,
        reconcile_plan=False,
    )
    LocalStore.upsert_daily_health(src_uid, {"date": "2026-03-01", "sleep_duration_seconds": 28800, "hrv_last_night_avg": 62})

    merged = LocalStore.merge_user_profiles(src_uid, tgt_uid, drop_transient_watch_activities=True)
    assert merged == tgt_uid
    assert LocalStore.resolve_user_id(src_uid) == tgt_uid

    tgt_p = LocalStore.get_profile(tgt_uid)
    assert tgt_p["wechat_openid"] == f"oid_{ts}"

    plan = LocalStore.get_user_active_training_plan(tgt_uid)
    assert plan is not None and plan["id"] == f"tp_{ts}"

    with sqlite3.connect(DB_PATH) as conn:
        role_row = conn.execute(
            "SELECT role FROM club_memberships WHERE club_id = ? AND user_id = ?",
            (club_id, tgt_uid),
        ).fetchone()
        assert role_row is not None and role_row[0] == "coach"
        dh_row = conn.execute(
            "SELECT sleep_duration_seconds, hrv_last_night_avg FROM daily_health WHERE id = ?",
            (f"{tgt_uid}_2026-03-01",),
        ).fetchone()
        assert dh_row is not None and dh_row[0] == 28800 and dh_row[1] == 62


def test_club_7d_leaderboard_weekly_target_and_broadcast_day_index_base():
    ts = int(time.time() * 1000)
    uid = f"u_lb_{ts}"
    club_id = f"club_lb_{ts}"
    today_str = get_beijing_today().isoformat()

    LocalStore.upsert_profile(uid, {"id": uid, "display_name": "周榜测试员"})
    LocalStore.upsert_goal(uid, {"target_distance": 200.0, "weekly_target": 50.0})
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO clubs (id, name, city, invite_code, owner_id, created_at) VALUES (?, '周榜跑团', '上海', ?, ?, ?)",
            (club_id, f"LB{ts % 10000:04d}", uid, f"{today_str}T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES (?, ?, ?, 'owner', 'active', ?)",
            (f"{club_id}_{uid}", club_id, uid, f"{today_str}T00:00:00Z"),
        )
        conn.commit()

    LocalStore.upsert_activity(
        {
            "id": f"act_lb_{ts}",
            "user_id": uid,
            "name": "周中25km长距离",
            "sport_type": "Run",
            "start_time": f"{today_str}T06:30:00",
            "distance_meters": 25000.0,
            "duration_seconds": 7500,
        },
        notify=False,
        reconcile_plan=False,
    )

    lb_week = LocalStore.get_club_leaderboard(club_id, time_range="week")
    entry_w = next(x for x in lb_week if x["user_id"] == uid)
    assert entry_w["target_km"] == 50.0
    assert entry_w["completion_rate"] == 50.0

    lb_month = LocalStore.get_club_leaderboard(club_id, time_range="month")
    entry_m = next(x for x in lb_month if x["user_id"] == uid)
    assert entry_m["target_km"] == 200.0
    assert entry_m["completion_rate"] == 12.5

    bs = LocalStore.get_runner_basic_status(uid)
    assert bs["target_km"] == bs["monthly_target_km"]
    assert bs["completion_rate"] == bs["month_progress_pct"]

    # Create a simple active plan and verify deterministic day_index_base + workout feedback aliases
    token = _make_jwt(uid)
    auth_headers = {"Authorization": f"Bearer {token}"}
    gen_res = client.post(
        "/api/coach/plan/generate",
        json={
            "athlete_uid": uid,
            "goal_type": "fitness_maintenance",
            "maintenance_focus": "aerobic_base",
            "weeks_count": 4,
            "days_per_week": 4,
            "operator_uid": uid,
        },
        headers=auth_headers,
    )
    assert gen_res.status_code == 200
    plan_id = gen_res.json()["plan"]["id"]

    # Broadcast with day_index_base=0, day_index=1 -> Tuesday (index 1)
    bc0 = client.post(
        "/api/coach/plan/club-broadcast-workout",
        json={
            "club_id": club_id,
            "operator_uid": uid,
            "day_index": 1,
            "day_index_base": 0,
            "title": "周二间歇合练A",
            "distance_km": 12.0,
        },
        headers=auth_headers,
    )
    assert bc0.status_code == 200
    assert "周二" in bc0.json()["message"]

    # Broadcast with day_index_base=1, day_index=2 -> ALSO Tuesday (index 1)
    bc1 = client.post(
        "/api/coach/plan/club-broadcast-workout",
        json={
            "club_id": club_id,
            "operator_uid": uid,
            "day_index": 2,
            "day_index_base": 1,
            "title": "周二间歇合练B",
            "distance_km": 14.0,
        },
        headers=auth_headers,
    )
    assert bc1.status_code == 200
    assert "周二" in bc1.json()["message"]

    # Update workout with `notes` & `feeling` aliases
    wk_upd = client.put(
        f"/api/coach/plan/{plan_id}/workout",
        json={
            "week_index": 1,
            "day_index": 1,
            "completed": True,
            "notes": "体感轻盈，心率稳定",
            "feeling": "😊 轻松舒适",
            "operator_uid": uid,
        },
        headers=auth_headers,
    )
    assert wk_upd.status_code == 200
    day_obj = wk_upd.json()["plan"]["schedule_data"]["weeks"][0]["days"][1]
    assert day_obj["athlete_notes"] == "体感轻盈，心率稳定"
    assert day_obj["feeling_tag"] == "😊 轻松舒适"


def test_web_qr_telemetry_bridge_for_legacy_miniapp_and_security():
    uid = f"u_wx_bridge_{int(time.time() * 1000)}"
    LocalStore.upsert_profile(
        uid,
        {
            "id": uid,
            "display_name": "正式版扫码跑者",
            "avatar_url": "https://rgm.vanpower.net/api/avatars/rgm-logo.png",
        },
    )
    fake_png = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 400)
    with patch("routers.auth.wechat_client.get_wxacode_unlimit", return_value=fake_png):
        res_create = client.post("/api/auth/wechat/web-qr/create")
    assert res_create.status_code == 200
    scene_id = res_create.json()["scene_id"]

    # 1. Unauthenticated telemetry batch MUST NOT mark scanned or confirm
    unauth_batch = {
        "session_id": f"s_unauth_{int(time.time() * 1000)}",
        "client_uuid": "c_attacker",
        "scene": 1047,
        "entry_page": "pages/share/share",
        "events": [
            {
                "event_id": "e_unauth_1",
                "event_type": "session_start",
                "event_name": "app_open",
                "page_path": "pages/share/share",
                "client_ts": int(time.time() * 1000),
                "props": {"scene": 1047, "query": {"scene": scene_id}},
            },
            {
                "event_id": "e_unauth_2",
                "event_type": "button_click",
                "event_name": "share_cta_home",
                "page_path": "pages/share/share",
                "client_ts": int(time.time() * 1000) + 500,
            },
        ],
    }
    r_b0 = client.post("/api/miniapp/telemetry/batch", json=unauth_batch)
    assert r_b0.status_code == 200
    r_st0 = client.get(f"/api/auth/wechat/web-qr/status/{scene_id}")
    assert r_st0.json()["status"] == "pending"

    # 2. Signed-JWT telemetry batch on scan arrival -> marks `scanned`
    token = _make_jwt(uid)
    auth_headers = {"Authorization": f"Bearer {token}"}
    sid = f"s_legit_{int(time.time() * 1000)}"
    scan_batch = {
        "session_id": sid,
        "client_uuid": "c_iphone14",
        "scene": 1047,
        "entry_page": "pages/share/share",
        "events": [
            {
                "event_id": "e_legit_1",
                "event_type": "session_start",
                "event_name": "app_open",
                "page_path": "pages/share/share",
                "client_ts": int(time.time() * 1000),
                "props": {"scene": 1047, "query": {"scene": scene_id}},
            }
        ],
    }
    r_b1 = client.post("/api/miniapp/telemetry/batch", json=scan_batch, headers=auth_headers)
    assert r_b1.status_code == 200
    r_st1 = client.get(f"/api/auth/wechat/web-qr/status/{scene_id}")
    assert r_st1.json()["status"] == "scanned"
    assert r_st1.json()["display_name"] == "正式版扫码跑者"

    # 3. Follow-up batch with `share_cta_home` ("立即进入小程序") -> confirms & issues one-time Web JWT
    cta_batch = {
        "session_id": sid,
        "client_uuid": "c_iphone14",
        "scene": 1047,
        "entry_page": "pages/share/share",
        "events": [
            {
                "event_id": "e_legit_2",
                "event_type": "button_click",
                "event_name": "share_cta_home",
                "page_path": "pages/share/share",
                "client_ts": int(time.time() * 1000) + 1200,
            }
        ],
    }
    r_b2 = client.post("/api/miniapp/telemetry/batch", json=cta_batch, headers=auth_headers)
    assert r_b2.status_code == 200
    r_st2 = client.get(f"/api/auth/wechat/web-qr/status/{scene_id}")
    st2_data = r_st2.json()
    assert st2_data["status"] == "confirmed"
    assert st2_data["user"]["id"] == uid
    assert st2_data["token"]

    # 4. Subsequent poll sees `consumed` (atomically consumed)
    r_st3 = client.get(f"/api/auth/wechat/web-qr/status/{scene_id}")
    assert r_st3.json()["status"] == "consumed"

