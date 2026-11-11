import sqlite3
import time
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore, DB_PATH

client = TestClient(app)


def _bj_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=8)


def test_completed_group_runs_auto_archived_and_hidden():
    ts = int(time.time() * 1000)
    owner_uid = f"owner_arch_{ts}"
    LocalStore.upsert_profile(owner_uid, {"display_name": "张海华团长"})

    club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"复旦戈阅文站_{ts}",
        description="测试约跑归档",
        city="上海",
    )
    club_id = club["id"]

    now_bj = _bj_now()
    past_dt = now_bj - timedelta(days=6)
    ongoing_dt = now_bj - timedelta(hours=1)
    future_dt = now_bj + timedelta(days=2)

    # 1. Completed group run (6 days ago, e.g. Nov 1 06:30)
    past_res = client.post(
        f"/api/team/{club_id}/events",
        json={
            "operator_uid": owner_uid,
            "title": "第44周合练（已完赛历史约跑）",
            "event_type": "group_run",
            "start_date": past_dt.strftime("%Y-%m-%d"),
            "meet_time": f"{past_dt.strftime('%Y-%m-%d')} 06:30",
            "location": "闵行文化公园2号门",
            "target_km": 18.0,
        },
    )
    assert past_res.status_code == 200
    past_evt_id = past_res.json()["event_id"]

    # 2. Ongoing group run (started 1h ago, within 4h window)
    ongoing_res = client.post(
        f"/api/team/{club_id}/events",
        json={
            "operator_uid": owner_uid,
            "title": "正在进行中的晨跑合练",
            "event_type": "group_run",
            "start_date": ongoing_dt.strftime("%Y-%m-%d"),
            "meet_time": ongoing_dt.strftime("%Y-%m-%d %H:%M"),
            "location": "世纪公园7号门",
            "target_km": 12.0,
        },
    )
    assert ongoing_res.status_code == 200
    ongoing_evt_id = ongoing_res.json()["event_id"]

    # 3. Upcoming group run (2 days in future)
    future_res = client.post(
        f"/api/team/{club_id}/events",
        json={
            "operator_uid": owner_uid,
            "title": "第45周周末LSD合练",
            "event_type": "group_run",
            "start_date": future_dt.strftime("%Y-%m-%d"),
            "meet_time": f"{future_dt.strftime('%Y-%m-%d')} 06:30",
            "location": "闵行文化公园2号门",
            "target_km": 20.0,
        },
    )
    assert future_res.status_code == 200
    future_evt_id = future_res.json()["event_id"]

    # Default GET /events MUST auto-archive the past run and only return ongoing + upcoming
    list_res = client.get(f"/api/team/{club_id}/events?user_id={owner_uid}")
    assert list_res.status_code == 200
    active_events = list_res.json()["events"]
    active_ids = [e["id"] for e in active_events]
    assert past_evt_id not in active_ids, "Completed group run should be archived and hidden from default list"
    assert ongoing_evt_id in active_ids
    assert future_evt_id in active_ids

    # Verify DB status was persisted as 'archived'
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT status FROM club_events WHERE id = ?", (past_evt_id,)).fetchone()
        assert row is not None and row[0] == "archived"

    # Verify include_archived=true still retrieves archived record for battle report history
    all_res = client.get(f"/api/team/{club_id}/events?user_id={owner_uid}&include_archived=true")
    assert all_res.status_code == 200
    all_ids = [e["id"] for e in all_res.json()["events"]]
    assert past_evt_id in all_ids

    # Verify archived event cannot accept new signups
    late_join = client.post(
        f"/api/team/{club_id}/events/{past_evt_id}/join",
        json={"user_id": f"late_runner_{ts}", "auto_join_club": True, "join_event": True},
    )
    assert late_join.status_code == 400
    assert "归档" in late_join.json()["detail"]

    # Verify manual archive endpoint works for organizers
    arch_res = client.post(f"/api/team/{club_id}/events/{ongoing_evt_id}/archive")
    assert arch_res.status_code == 200
    list_after_manual = client.get(f"/api/team/{club_id}/events?user_id={owner_uid}").json()["events"]
    assert [e["id"] for e in list_after_manual] == [future_evt_id]


def test_wechat_group_invite_direct_open_and_signup_existing_and_new_users():
    ts = int(time.time() * 1000)
    owner_uid = f"owner_inv_{ts}"
    LocalStore.upsert_profile(owner_uid, {"display_name": "发起人老王"})

    # Create a parent organization with required fields + a sub-club under it
    org = LocalStore.create_organization(
        owner_id=owner_uid,
        name=f"商学院戈友大群_{ts}",
        description="含必填字段的大群",
        invite_code=f"ORG{str(ts)[-5:]}",
    )
    org_id = org["id"]
    club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"阅文合练分队_{ts}",
        description="微信群转发直接报名测试",
        city="上海",
        org_id=org_id,
    )
    club_id = club["id"]

    future_dt = _bj_now() + timedelta(days=3)
    ev_res = client.post(
        f"/api/team/{club_id}/events",
        json={
            "operator_uid": owner_uid,
            "title": "周日徐汇滨江18km合练",
            "event_type": "group_run",
            "start_date": future_dt.strftime("%Y-%m-%d"),
            "meet_time": f"{future_dt.strftime('%Y-%m-%d')} 06:30",
            "location": "徐汇滨江市民跑步驿站",
            "location_detail": "龙腾大道瑞宁路集合，沿江折返",
            "latitude": 31.1892,
            "longitude": 121.4619,
            "target_km": 18.0,
            "pace_requirement": "5:30-6:00/km",
            "rules": "集合热身15分钟，配速员带队补水",
        },
    )
    assert ev_res.status_code == 200
    event_id = ev_res.json()["event_id"]

    # A. Unauthenticated WeChat group visitor opens invite link -> sees full activity content directly
    guest_detail_res = client.get(f"/api/team/{club_id}/events/{event_id}")
    assert guest_detail_res.status_code == 200
    ev_detail = guest_detail_res.json()["event"]
    assert ev_detail["title"] == "周日徐汇滨江18km合练"
    assert ev_detail["location"] == "徐汇滨江市民跑步驿站"
    assert ev_detail["location_detail"] == "龙腾大道瑞宁路集合，沿江折返"
    assert ev_detail["rules"] == "集合热身15分钟，配速员带队补水"
    assert ev_detail["is_archived"] is False

    # B. Existing RGM user (not previously in this club) clicks WeChat invite -> links profile & shows on Home
    existing_uuid = f"existing_client_{ts}"
    reg_existing = client.post(
        "/api/auth/wechat/miniapp-login",
        json={"code": f"mock_code_{existing_uuid}", "client_uuid": existing_uuid, "nick_name": "老跑友阿杰"},
    )
    assert reg_existing.status_code == 200
    existing_uid = reg_existing.json()["uid"]
    LocalStore.upsert_profile(existing_uid, {"display_name": "老跑友阿杰", "phone": "13800138000"})

    # Silent check_only recognizes existing user and restores profile
    check_existing = client.post(
        "/api/auth/wechat/miniapp-login",
        json={"code": f"mock_code_2_{existing_uuid}", "client_uuid": existing_uuid, "check_only": True},
    )
    assert check_existing.status_code == 200
    assert check_existing.json()["found_existing"] is True
    assert check_existing.json()["uid"] == existing_uid
    assert check_existing.json()["display_name"] == "老跑友阿杰"

    # 1-tap join links existing profile, auto-joins club, and enrolls in group run
    join_existing = client.post(
        f"/api/team/{club_id}/events/{event_id}/join",
        json={
            "user_id": existing_uid,
            "auto_join_club": True,
            "join_event": True,
            "inviter_uid": owner_uid,
        },
    )
    assert join_existing.status_code == 200
    je_data = join_existing.json()
    assert je_data["is_joined"] is True
    assert je_data["is_club_member"] is True
    assert je_data["is_existing_user"] is True
    assert je_data["display_name"] == "老跑友阿杰"
    assert je_data["is_profile_incomplete"] is False

    # Home page fetchMyNextGroupRun path: my-clubs + club events returns the joined group run!
    my_clubs_existing = client.get(f"/api/team/my-clubs/{existing_uid}").json()["clubs"]
    matched_club_ex = next((c for c in my_clubs_existing if c["id"] == club_id), None)
    assert matched_club_ex is not None
    assert matched_club_ex["is_access_suspended"] is False
    home_events_ex = client.get(f"/api/team/{club_id}/events?user_id={existing_uid}").json()["events"]
    assert any(e["id"] == event_id and e["is_joined"] is True for e in home_events_ex)

    # C. Brand-new WeChat user clicks invite -> check_only does NOT pre-create account; 1-tap Join adds directly to club with deferred profile
    new_uuid = f"brand_new_client_{ts}"
    check_new = client.post(
        "/api/auth/wechat/miniapp-login",
        json={"code": f"mock_new_{new_uuid}", "client_uuid": new_uuid, "check_only": True},
    )
    assert check_new.status_code == 200
    assert check_new.json()["found_existing"] is False
    assert check_new.json()["uid"] is None

    # User taps 1-tap Join -> authenticates + joins directly with ZERO profile fields filled upfront
    login_new = client.post(
        "/api/auth/wechat/miniapp-login",
        json={"code": f"mock_new_{new_uuid}", "client_uuid": new_uuid, "inviter_uid": owner_uid},
    )
    assert login_new.status_code == 200
    new_uid = login_new.json()["uid"]
    assert login_new.json()["is_new_user"] is True

    join_new = client.post(
        f"/api/team/{club_id}/events/{event_id}/join",
        json={
            "user_id": new_uid,
            "auto_join_club": True,
            "join_event": True,
            "inviter_uid": owner_uid,
        },
    )
    assert join_new.status_code == 200
    jn_data = join_new.json()
    assert jn_data["is_joined"] is True
    assert jn_data["is_club_member"] is True
    assert jn_data["auto_joined_club"] is True
    assert jn_data["is_profile_incomplete"] is True

    # New user is immediately an active member of the club (and temporary member of org) & sees group run on Home!
    my_clubs_new = client.get(f"/api/team/my-clubs/{new_uid}").json()["clubs"]
    matched_club_new = next((c for c in my_clubs_new if c["id"] == club_id), None)
    assert matched_club_new is not None
    assert matched_club_new["is_access_suspended"] is False
    home_events_new = client.get(f"/api/team/{club_id}/events?user_id={new_uid}").json()["events"]
    assert any(e["id"] == event_id and e["is_joined"] is True for e in home_events_new)
