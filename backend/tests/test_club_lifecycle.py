import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore, DB_PATH
import sqlite3

client = TestClient(app)

def test_club_lifecycle_management():
    owner_uid = "u_owner_lifecycle"
    member_uid = "u_member_lifecycle"
    stranger_uid = "u_stranger_lifecycle"

    # 1. Setup profiles
    LocalStore.upsert_profile(owner_uid, {"display_name": "生命周期测试团长", "email": "lifecycle_owner@test.com"})
    LocalStore.upsert_profile(member_uid, {"display_name": "生命周期测试跑友", "email": "lifecycle_member@test.com"})
    LocalStore.upsert_profile(stranger_uid, {"display_name": "普通路人跑友", "email": "lifecycle_stranger@test.com"})

    # Setup personal activity for member (MUST NEVER be deleted)
    personal_act_id = "act_lifecycle_preserved"
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (personal_act_id, member_uid, "世纪公园晨跑", "running", "2026-09-20T07:00:00", 10000, 3000, "5:00 /km", 50, 150, 120))
        conn.commit()


    # 2. Create club
    club = LocalStore.create_club(
        owner_id=owner_uid,
        name="极速马拉松训练营",
        description="专注全马破三训练",
        city="上海",
        join_mode="free"
    )
    club_id = club["id"]
    assert club.get("status") == "active"

    # Member joins
    join_res = client.post("/api/team/join-club", json={
        "user_id": member_uid,
        "club_id": club_id,
        "privacy_consent": True
    })
    assert join_res.status_code == 200

    # 3. Test Owner pauses club
    pause_res = client.post(f"/api/team/{club_id}/status", json={
        "operator_uid": owner_uid,
        "status": "paused"
    })
    assert pause_res.status_code == 200
    assert pause_res.json()["club"]["status"] == "paused"

    # In paused status:
    # A. Stranger cannot find club in public list
    public_clubs = client.get(f"/api/team/all-clubs?user_id={stranger_uid}").json()["clubs"]
    assert not any(c["id"] == club_id for c in public_clubs)

    # Existing member CAN still see their joined club
    my_clubs = client.get(f"/api/team/my-clubs/{member_uid}").json()["clubs"]
    assert any(c["id"] == club_id for c in my_clubs)

    # B. Stranger tries to join -> REJECTED
    stranger_join = client.post("/api/team/join-club", json={
        "user_id": stranger_uid,
        "club_id": club_id,
        "privacy_consent": True
    })
    assert stranger_join.status_code == 400
    assert "暂停" in stranger_join.json()["detail"]

    # C. Owner cannot create event in paused club -> REJECTED
    event_res = client.post(f"/api/team/{club_id}/events", json={
        "operator_uid": owner_uid,
        "title": "金秋百公里挑战赛"
    })
    assert event_res.status_code == 400
    assert "暂停" in event_res.json()["detail"]

    # D. Removing member in paused club -> REJECTED
    remove_res = client.delete(f"/api/team/{club_id}/members/{member_uid}")
    assert remove_res.status_code == 400
    assert "暂停" in remove_res.json()["detail"]

    # 4. Test Owner locks club
    lock_res = client.post(f"/api/team/{club_id}/status", json={
        "operator_uid": owner_uid,
        "status": "locked"
    })
    assert lock_res.status_code == 200
    assert lock_res.json()["club"]["status"] == "locked"

    # In locked status:
    # A. Stranger cannot find club in public list
    public_clubs_locked = client.get(f"/api/team/all-clubs?user_id={stranger_uid}").json()["clubs"]
    assert not any(c["id"] == club_id for c in public_clubs_locked)

    # B. Stranger tries to join -> REJECTED
    stranger_join_locked = client.post("/api/team/join-club", json={
        "user_id": stranger_uid,
        "club_id": club_id,
        "privacy_consent": True
    })
    assert stranger_join_locked.status_code == 400
    assert "锁定" in stranger_join_locked.json()["detail"]

    # C. Removing member in locked club -> REJECTED
    remove_res_locked = client.delete(f"/api/team/{club_id}/members/{member_uid}")
    assert remove_res_locked.status_code == 400
    assert "锁定" in remove_res_locked.json()["detail"]

    # 5. Non-owner cannot change status -> 403
    fail_status = client.post(f"/api/team/{club_id}/status", json={
        "operator_uid": stranger_uid,
        "status": "active"
    })
    assert fail_status.status_code == 403

    # 6. Restore to active
    restore_res = client.post(f"/api/team/{club_id}/status", json={
        "operator_uid": owner_uid,
        "status": "active"
    })
    assert restore_res.status_code == 200
    assert restore_res.json()["club"]["status"] == "active"

    # Public visibility restored
    public_clubs_restored = client.get(f"/api/team/all-clubs?user_id={stranger_uid}").json()["clubs"]
    assert any(c["id"] == club_id for c in public_clubs_restored)

    # 7. Dissolve / Delete Club
    # Non-owner cannot dissolve -> 403
    fail_dissolve = client.delete(f"/api/team/{club_id}?operator_uid={stranger_uid}")
    assert fail_dissolve.status_code == 403

    # Owner dissolves club
    del_res = client.delete(f"/api/team/{club_id}?operator_uid={owner_uid}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Check club is gone
    assert LocalStore.get_club(club_id) is None
    assert len(LocalStore.get_club_members(club_id)) == 0

    # CRITICAL DATA SAFETY VERIFICATION:
    # 1. Member's profile is completely INTACT
    member_profile = LocalStore.get_profile(member_uid)
    assert member_profile is not None
    assert member_profile["display_name"] == "生命周期测试跑友"

    # 2. Member's personal activity is completely INTACT
    acts = LocalStore.get_month_activities(member_uid, 2026, 9)
    assert any(a["id"] == personal_act_id for a in acts)


def test_super_admin_club_lifecycle():
    import jwt
    from config import settings

    admin_token = jwt.encode({"is_super_admin": True, "sub": "admin"}, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    headers = {"Authorization": f"Bearer {admin_token}"}

    owner_uid = "u_admin_lc_owner"
    LocalStore.upsert_profile(owner_uid, {"display_name": "管理测试团长", "email": "admin_lc@test.com"})

    club = LocalStore.create_club(
        owner_id=owner_uid,
        name="超管测试跑团",
        description="用于超管生命周期测试",
        city="北京"
    )
    club_id = club["id"]

    # 1. Admin pauses club
    res = client.post(f"/api/admin/clubs/{club_id}/status", json={"status": "paused"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["club"]["status"] == "paused"

    # 2. Admin locks club
    res = client.post(f"/api/admin/clubs/{club_id}/status", json={"status": "locked"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["club"]["status"] == "locked"

    # 3. Admin deletes club
    res = client.delete(f"/api/admin/clubs/{club_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Confirm gone
    assert LocalStore.get_club(club_id) is None


