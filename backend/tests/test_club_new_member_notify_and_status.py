import os
import tempfile
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_client():
    fd, tmp_db = tempfile.mkstemp(suffix="_rgm_new_member.db")
    os.close(fd)
    old_db = os.environ.get("RGM_DB_PATH")
    os.environ["RGM_DB_PATH"] = tmp_db
    import utils.local_store as ls

    ls.DB_PATH = tmp_db
    ls.init_db()
    from main import app

    client = TestClient(app)
    yield client, ls.LocalStore
    if old_db is not None:
        os.environ["RGM_DB_PATH"] = old_db
        ls.DB_PATH = old_db
    else:
        os.environ.pop("RGM_DB_PATH", None)
    try:
        os.remove(tmp_db)
    except OSError:
        pass


def test_new_member_notifies_existing_members_and_new_members_status(isolated_client):
    client, LocalStore = isolated_client

    # 1. Seed owner + 1 existing member + club
    owner_uid = "u_club_owner_01"
    member1_uid = "u_existing_member_01"
    new_runner_uid = "u_new_runner_02"

    LocalStore.upsert_profile(owner_uid, {"display_name": "张团长", "garmin_connected": True})
    LocalStore.upsert_goal(owner_uid, {"weekly_target": 60.0, "target_distance": 240.0})

    LocalStore.upsert_profile(member1_uid, {"display_name": "老队员李四", "coros_connected": True})
    LocalStore.upsert_goal(member1_uid, {"weekly_target": 45.0, "target_distance": 180.0})

    club = LocalStore.create_club(
        name="世纪公园先锋跑团",
        owner_id=owner_uid,
        description="每周例跑",
        city="上海",
        join_mode="free",
    )
    club_id = club["id"]

    # Member 1 joins first
    LocalStore.join_club_by_id(user_id=member1_uid, club_id=club_id)
    owner_notifs_after_m1 = LocalStore.get_user_notifications(owner_uid)
    assert any("老队员李四" in n["title"] or "老队员李四" in n["content"] for n in owner_notifs_after_m1)

    # Clear notifications count baseline before new_runner_uid joins
    owner_count_before = len(LocalStore.get_user_notifications(owner_uid))
    m1_count_before = len(LocalStore.get_user_notifications(member1_uid))

    # 2. New runner joins club via API (without watch bound or goal set yet)
    LocalStore.upsert_profile(new_runner_uid, {"display_name": "新跑友王五", "garmin_connected": False})
    resp = client.post(
        "/api/team/join-club",
        json={
            "user_id": new_runner_uid,
            "club_id": club_id,
            "display_name": "新跑友王五",
        },
    )
    assert resp.status_code == 200

    # Both owner and existing member1 should receive a club_new_member notification
    owner_notifs = LocalStore.get_user_notifications(owner_uid)
    m1_notifs = LocalStore.get_user_notifications(member1_uid)
    new_runner_notifs = LocalStore.get_user_notifications(new_runner_uid)

    assert len(owner_notifs) == owner_count_before + 1
    assert len(m1_notifs) == m1_count_before + 1
    assert not any(n.get("type") == "club_new_member" for n in new_runner_notifs)

    latest_owner_notif = owner_notifs[0]
    assert latest_owner_notif["type"] == "club_new_member"
    assert "新跑友王五" in latest_owner_notif["title"]
    assert "新队员管理" in latest_owner_notif["content"]

    latest_m1_notif = m1_notifs[0]
    assert latest_m1_notif["type"] == "club_new_member"
    assert "新跑友王五" in latest_m1_notif["content"]

    # Re-joining when already active should NOT send duplicate notifications
    client.post(
        "/api/team/join-club",
        json={
            "user_id": new_runner_uid,
            "club_id": club_id,
        },
    )
    assert len(LocalStore.get_user_notifications(owner_uid)) == owner_count_before + 1
    assert len(LocalStore.get_user_notifications(member1_uid)) == m1_count_before + 1

    # 3. Verify GET /api/team/{club_id}/new-members returns accurate onboarding status
    status_resp = client.get(f"/api/team/{club_id}/new-members?user_id={owner_uid}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()

    summary = status_data["summary"]
    assert summary["total_members"] == 3
    assert summary["watch_bound_count"] == 2
    assert summary["watch_unbound_count"] == 1
    assert summary["goal_set_count"] == 2
    assert summary["goal_unset_count"] == 1
    assert summary["pending_setup_count"] == 1

    members_list = status_data["members"]
    # Newest member should be first
    newest = members_list[0]
    assert newest["user_id"] == new_runner_uid
    assert newest["watch_bound"] is False
    assert newest["watch_status_label"] == "未绑定手表"
    assert newest["goal_set"] is False
    assert newest["joined_at_display"]
    assert newest["is_new_7d"] is True

    # 4. Owner sends 1-tap setup reminder to new_runner_uid
    remind_resp = client.post(
        f"/api/team/{club_id}/remind-member",
        json={
            "operator_uid": owner_uid,
            "target_uid": new_runner_uid,
        },
    )
    assert remind_resp.status_code == 200
    remind_json = remind_resp.json()
    assert remind_json["success"] is True

    runner_notifs_after = LocalStore.get_user_notifications(new_runner_uid)
    assert len(runner_notifs_after) == 1
    assert runner_notifs_after[0]["type"] == "club_onboarding_reminder"
    assert "运动手表绑定" in runner_notifs_after[0]["content"]
    assert "周/月跑量目标设定" in runner_notifs_after[0]["content"]
