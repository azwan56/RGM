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

    # 9. Test entering organization invite code (FDGOBI) in /api/team/join
    org_join_res = client.post("/api/team/join", json={
        "user_id": member_uid_1,
        "invite_code": "FDGOBI"
    })
    assert org_join_res.status_code == 400
    assert "复旦戈" in org_join_res.json()["detail"]
    assert "大群体" in org_join_res.json()["detail"]

    # 10. Test entering completely invalid code in /api/team/join
    invalid_res = client.post("/api/team/join", json={
        "user_id": member_uid_1,
        "invite_code": "NOTEXIST123"
    })
    assert invalid_res.status_code == 404
    assert "无效的邀请码" in invalid_res.json()["detail"]


def test_club_feed_pagination():
    owner_uid = "u_feed_test_owner"
    LocalStore.upsert_profile(owner_uid, {"display_name": "动态测试员", "email": "feed@test.com"})
    club = LocalStore.create_club(
        owner_id=owner_uid,
        name="动态分页测试跑团",
        description="测试打卡动态分页与历史记录加载",
        city="上海"
    )
    club_id = club["id"]

    # Insert 5 test activities on different dates
    import sqlite3
    from utils.local_store import DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        for i in range(5):
            act_id = f"act_feed_page_{i}"
            cursor.execute("""
                INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (act_id, owner_uid, f"晨跑 {i}", "running", f"2026-09-1{i}T08:00:00", (5 + i) * 1000, 1500 + i * 100, "5:00 /km", 20, 145, 80))
        conn.commit()

    # Fetch with limit=2, offset=0
    res1 = client.get(f"/api/team/{club_id}/feed?uid={owner_uid}&limit=2&offset=0")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["feed"]) == 2
    assert data1["total"] >= 5
    assert data1["has_more"] is True
    assert data1["offset"] == 0
    assert data1["limit"] == 2

    # Fetch second page: limit=2, offset=2
    res2 = client.get(f"/api/team/{club_id}/feed?uid={owner_uid}&limit=2&offset=2")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["feed"]) == 2
    assert data2["has_more"] is True
    assert data2["offset"] == 2
    # Ensure disjoint from page 1
    ids1 = [item["id"] for item in data1["feed"]]
    ids2 = [item["id"] for item in data2["feed"]]
    assert len(set(ids1).intersection(set(ids2))) == 0

    # Fetch last page: limit=2, offset=4
    res3 = client.get(f"/api/team/{club_id}/feed?uid={owner_uid}&limit=2&offset=4")
    assert res3.status_code == 200
    data3 = res3.json()
    assert len(data3["feed"]) >= 1
    assert data3["offset"] == 4
