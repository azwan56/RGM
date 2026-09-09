import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore

client = TestClient(app)

def test_club_join_rules_workflow():
    owner_uid = "u_owner_test_rules"
    member_uid_1 = "u_member_test_rules_1"
    member_uid_2 = "u_member_test_rules_2"
    non_owner_uid = "u_imposter_rules"

    # 1. Setup profiles
    LocalStore.upsert_profile(owner_uid, {"display_name": "规则测试团长", "email": "rules_owner@test.com"})
    LocalStore.upsert_profile(member_uid_1, {"display_name": "跑友一号", "email": "runner1@test.com"})
    LocalStore.upsert_profile(member_uid_2, {"display_name": "跑友二号", "email": "runner2@test.com"})
    LocalStore.upsert_profile(non_owner_uid, {"display_name": "路人跑友", "email": "stranger@test.com"})

    # 2. Create club with default 'free' join_mode
    club = LocalStore.create_club(
        owner_id=owner_uid,
        name="自由与凭码测试跑团",
        description="测试自由入团与邀请码入团规则",
        city="上海",
        join_mode="free"
    )
    club_id = club["id"]
    invite_code = club["invite_code"]
    assert club["join_mode"] == "free"

    # 3. Member 1 joins directly without invite code (free mode)
    join_res_1 = client.post("/api/team/join-club", json={
        "user_id": member_uid_1,
        "club_id": club_id,
        "privacy_consent": True
    })
    assert join_res_1.status_code == 200
    assert "成功加入" in join_res_1.json()["message"]

    # Verify membership
    members = LocalStore.get_club_members(club_id)
    uids = [m["user_id"] for m in members]
    assert member_uid_1 in uids

    # 4. Imposter tries to change join_mode -> 403
    fail_toggle = client.post(f"/api/team/{club_id}/join-mode", json={
        "operator_uid": non_owner_uid,
        "join_mode": "invite"
    })
    assert fail_toggle.status_code == 403

    # 5. Owner toggles join_mode to 'invite'
    ok_toggle = client.post(f"/api/team/{club_id}/join-mode", json={
        "operator_uid": owner_uid,
        "join_mode": "invite"
    })
    assert ok_toggle.status_code == 200
    assert ok_toggle.json()["club"]["join_mode"] == "invite"

    # 6. Member 2 tries to join without invite_code -> 400 Bad Request
    fail_join_no_code = client.post("/api/team/join-club", json={
        "user_id": member_uid_2,
        "club_id": club_id,
        "privacy_consent": True
    })
    assert fail_join_no_code.status_code == 400
    assert "邀请码" in fail_join_no_code.json()["detail"]

    # 7. Member 2 tries to join with wrong invite_code -> 400 Bad Request
    fail_join_wrong_code = client.post("/api/team/join-club", json={
        "user_id": member_uid_2,
        "club_id": club_id,
        "invite_code": "WRONG9",
        "privacy_consent": True
    })
    assert fail_join_wrong_code.status_code == 400
    assert "邀请码错误" in fail_join_wrong_code.json()["detail"]

    # 8. Member 2 joins with correct invite_code -> 200 OK
    ok_join = client.post("/api/team/join-club", json={
        "user_id": member_uid_2,
        "club_id": club_id,
        "invite_code": invite_code,
        "privacy_consent": True
    })
    assert ok_join.status_code == 200
    assert "成功加入" in ok_join.json()["message"]

    # Verify Member 2 is now in the club
    members_after = LocalStore.get_club_members(club_id)
    uids_after = [m["user_id"] for m in members_after]
    assert member_uid_2 in uids_after
