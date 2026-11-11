import os
import json
import sqlite3
import tempfile
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_client():
    fd, tmp_db = tempfile.mkstemp(suffix="_rgm_privacy.db")
    os.close(fd)
    old_db = os.environ.get("RGM_DB_PATH")
    os.environ["RGM_DB_PATH"] = tmp_db
    import utils.local_store as ls

    ls.DB_PATH = tmp_db
    ls.init_db()
    from main import app

    client = TestClient(app)
    yield client, ls.LocalStore, tmp_db
    if old_db is not None:
        os.environ["RGM_DB_PATH"] = old_db
        ls.DB_PATH = old_db
    else:
        os.environ.pop("RGM_DB_PATH", None)
    try:
        os.remove(tmp_db)
    except OSError:
        pass


def test_unaffiliated_roster_and_cross_club_workout_privacy(isolated_client):
    client, LocalStore, tmp_db = isolated_client

    # 1. Seed 2 unaffiliated users (u_free_1 with watch bound & custom goal, u_free_2 unbound)
    LocalStore.upsert_profile("u_free_1", {"display_name": "自由跑友甲", "garmin_connected": True})
    LocalStore.upsert_goal("u_free_1", {"weekly_target": 60.0, "target_distance": 260.0})

    LocalStore.upsert_profile("u_free_2", {"display_name": "自由跑友乙", "garmin_connected": False})

    # 2. Seed 3 club users: u_club_a1 & u_club_a2 in Club A, u_club_b1 in Club B
    LocalStore.upsert_profile("u_club_a1", {"display_name": "A团跑友1", "garmin_connected": True})
    LocalStore.upsert_goal("u_club_a1", {"weekly_target": 70.0, "target_distance": 300.0})

    LocalStore.upsert_profile("u_club_a2", {"display_name": "A团跑友2", "garmin_connected": True})
    LocalStore.upsert_goal("u_club_a2", {"weekly_target": 65.0, "target_distance": 280.0})

    LocalStore.upsert_profile("u_club_b1", {"display_name": "B团跑友1", "garmin_connected": True})
    LocalStore.upsert_goal("u_club_b1", {"weekly_target": 70.0, "target_distance": 300.0})

    club_a = LocalStore.create_club(name="测试A跑团", owner_id="u_club_a1", city="上海", join_mode="free")
    club_b = LocalStore.create_club(name="测试B跑团", owner_id="u_club_b1", city="北京", join_mode="free")
    LocalStore.join_club_by_id(user_id="u_club_a2", club_id=club_a["id"])

    # 3. Insert workout records for u_free_1 and u_club_a1
    now_month_prefix = LocalStore.get_runner_basic_status("u_free_1")["joined_at_display"][:7]
    conn = sqlite3.connect(tmp_db)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, average_heartrate, avg_pace_str, gps_track_data)
        VALUES ('act_free_1', 'u_free_1', '自由晨跑10.5k', 'running', ?, 10500, 3150, 148, '5:00', ?)
        """,
        (f"{now_month_prefix}-09T07:00:00", json.dumps([[31.2, 121.4], [31.21, 121.41]])),
    )
    c.execute(
        """
        INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, average_heartrate, avg_pace_str, gps_track_data)
        VALUES ('act_club_a1', 'u_club_a1', 'A团合练15k', 'running', ?, 15000, 4500, 152, '5:00', ?)
        """,
        (f"{now_month_prefix}-09T06:30:00", json.dumps({"points": [{"lat": 31.2, "lng": 121.4}, {"lat": 31.22, "lng": 121.42}]})),
    )
    conn.commit()
    conn.close()

    # ── Verification 1: Super Admin can view unaffiliated roster and send setup reminder ──
    res_sa = client.get("/api/team/unaffiliated-members?user_id=u_df65d9a588c9")
    assert res_sa.status_code == 200
    data_sa = res_sa.json()
    uids_in_unaffiliated = {m["user_id"] for m in data_sa["members"]}
    assert "u_free_1" in uids_in_unaffiliated
    assert "u_free_2" in uids_in_unaffiliated
    assert "u_club_a1" not in uids_in_unaffiliated
    assert "u_club_a2" not in uids_in_unaffiliated
    assert "u_club_b1" not in uids_in_unaffiliated

    free1_item = next(m for m in data_sa["members"] if m["user_id"] == "u_free_1")
    assert free1_item["watch_bound"] is True
    assert free1_item["goal_set"] is True
    assert free1_item["weekly_target_km"] == 60.0
    assert free1_item["monthly_target_km"] == 260.0

    rem_res = client.post(
        "/api/team/unaffiliated/remind-member",
        json={"operator_uid": "u_df65d9a588c9", "target_uid": "u_free_2"},
    )
    assert rem_res.status_code == 200
    assert rem_res.json()["success"] is True

    # ── Verification 2: Unaffiliated users can see each other in the unaffiliated list ──
    res_peer = client.get("/api/team/unaffiliated-members?user_id=u_free_2")
    assert res_peer.status_code == 200
    peer_uids = {m["user_id"] for m in res_peer.json()["members"]}
    assert "u_free_1" in peer_uids
    assert "u_free_2" in peer_uids

    # ── Verification 3: Users NOT in the same club CAN see basic status, CANNOT see specific workout records ──
    # Case A: Two unaffiliated users (u_free_2 viewing u_free_1)
    basic_res = client.get("/api/team/runner-basic-status/u_free_1?viewer_uid=u_free_2")
    assert basic_res.status_code == 200
    assert basic_res.json()["can_view_records"] is False
    assert basic_res.json()["watch_bound"] is True
    assert basic_res.json()["month_km"] == 10.5

    sci_res = client.get("/api/science/metrics/u_free_1?viewer_uid=u_free_2")
    assert sci_res.status_code == 200
    sci_json = sci_res.json()
    assert sci_json["basic_status_only"] is True
    assert sci_json["basic_status"]["display_name"] == "自由跑友甲"
    assert sci_json["ctl_atl_tsb_history"] == []
    assert sci_json["canova_matrix"] is None

    # Blocked from specific workout records:
    act_list_res = client.get("/api/miniapp/activities/u_free_1?viewer_uid=u_free_2")
    assert act_list_res.status_code == 403

    act_month_res = client.get("/api/miniapp/activities/month/u_free_1?year=2026&month=11&viewer_uid=u_free_2")
    assert act_month_res.status_code == 403

    act_track_res = client.get("/api/miniapp/activities/act_free_1/track?viewer_uid=u_free_2")
    assert act_track_res.status_code == 403

    # Case B: Two users in DIFFERENT clubs (u_club_b1 in Club B viewing u_club_a1 in Club A)
    cross_basic = client.get("/api/science/metrics/u_club_a1?viewer_uid=u_club_b1")
    assert cross_basic.status_code == 200
    assert cross_basic.json()["basic_status_only"] is True
    assert cross_basic.json()["basic_status"]["month_km"] == 15.0

    cross_act = client.get("/api/miniapp/activities/u_club_a1?viewer_uid=u_club_b1")
    assert cross_act.status_code == 403

    cross_track = client.get("/api/miniapp/activities/act_club_a1/track?viewer_uid=u_club_b1")
    assert cross_track.status_code == 403

    # ── Verification 4: Users in the SAME club & Super Admin CAN view specific workout records ──
    same_club_act = client.get("/api/miniapp/activities/u_club_a1?viewer_uid=u_club_a2")
    assert same_club_act.status_code == 200
    assert len(same_club_act.json()["activities"]) == 1

    same_club_track = client.get("/api/miniapp/activities/act_club_a1/track?viewer_uid=u_club_a2")
    assert same_club_track.status_code == 200
    assert same_club_track.json()["has_track"] is True

    super_admin_act = client.get("/api/miniapp/activities/u_free_1?viewer_uid=u_df65d9a588c9")
    assert super_admin_act.status_code == 200
    assert len(super_admin_act.json()["activities"]) == 1

    # ── Verification 5: Club Owner removing member & Member voluntarily leaving club ──
    # Add a 3rd member u_club_a3 to Club A so we can test both member leave and owner remove
    LocalStore.upsert_profile("u_club_a3", {"display_name": "A团队员丙", "garmin_connected": True})
    LocalStore.join_club_by_id(user_id="u_club_a3", club_id=club_a["id"])

    # 5a. Non-owner (u_club_a2) attempting to remove u_club_a3 is blocked with 403
    bad_rem = client.delete(f"/api/team/{club_a['id']}/members/u_club_a3?operator_uid=u_club_a2")
    assert bad_rem.status_code == 403

    # 5b. Club Owner (u_club_a1) attempting to leave directly without transferring ownership is blocked with 400
    owner_leave = client.post(f"/api/team/{club_a['id']}/leave", json={"user_id": "u_club_a1"})
    assert owner_leave.status_code == 400
    assert "团长" in owner_leave.json()["detail"]

    # 5c. Regular member (u_club_a3) voluntarily leaves Club A
    leave_res = client.post(f"/api/team/{club_a['id']}/leave", json={"user_id": "u_club_a3"})
    assert leave_res.status_code == 200
    assert leave_res.json()["success"] is True

    # 5d. Club Owner (u_club_a1) removes u_club_a2 from Club A
    owner_rem = client.delete(f"/api/team/{club_a['id']}/members/u_club_a2?operator_uid=u_club_a1")
    assert owner_rem.status_code == 200
    assert owner_rem.json()["success"] is True

    # Verify only u_club_a1 remains in Club A
    mem_after = client.get(f"/api/team/{club_a['id']}/members?user_id=u_club_a1")
    assert mem_after.status_code == 200
    remaining_ids = [m["user_id"] for m in mem_after.json()["members"]]
    assert remaining_ids == ["u_club_a1"]

