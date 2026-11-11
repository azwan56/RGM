import time
import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore

client = TestClient(app)

def test_org_join_mode_and_organizer_permission_workflow():
    ts = int(time.time() * 1000)
    owner_uid = f"u_org_lead_{ts}"
    stranger_uid = f"u_stranger_{ts}"
    member_uid = f"u_regular_{ts}"
    initial_code = f"FD_INIT_{ts % 100000}"

    # 1. Setup profiles
    LocalStore.upsert_profile(owner_uid, {"display_name": "复旦戈召集人", "email": "lead@test.com"})
    LocalStore.upsert_profile(stranger_uid, {"display_name": "未入群跑友", "email": "stranger@test.com"})
    LocalStore.upsert_profile(member_uid, {"display_name": "普通成员", "email": "regular@test.com"})

    # 2. Create organization (defaults to 'invite')
    create_res = client.post("/api/org/create", json={
        "name": f"复旦管院戈友测试群_{ts}",
        "invite_code": initial_code,
        "description": "测试大群自由入会与专属邀请码切换",
        "city": "上海",
        "owner_id": owner_uid,
        "join_mode": "invite"
    })
    assert create_res.status_code == 200
    org_data = create_res.json()["organization"]
    org_id = org_data["id"]
    assert org_data["join_mode"] == "invite"
    assert org_data["invite_code"] == initial_code

    # 3. Check public info: general public can see join_mode, but NOT invite_code
    pub_res = client.get(f"/api/org/{org_id}?user_id={stranger_uid}")
    assert pub_res.status_code == 200
    pub_org = pub_res.json()["organization"]
    assert pub_org["join_mode"] == "invite"
    assert "invite_code" not in pub_org

    # Organizer sees invite_code
    lead_res = client.get(f"/api/org/{org_id}?user_id={owner_uid}")
    assert lead_res.status_code == 200
    assert lead_res.json()["organization"]["invite_code"] == initial_code

    # 4. Stranger attempts to join without invite_code when join_mode is 'invite' -> 400 Rejected
    fail_join = client.post("/api/org/join", json={
        "user_id": stranger_uid,
        "org_id": org_id,
        "real_name": "路人甲",
        "gender": "male",
        "date_of_birth": "1992-05-05",
        "class_name": "MBA 2022"
    })
    assert fail_join.status_code == 400
    assert "凭专属邀请码入会" in fail_join.json()["detail"]

    # 5. Non-organizer (stranger) attempts to switch join_mode or change invite_code -> 403 Forbidden
    hack_res = client.post(f"/api/org/{org_id}/join-mode", json={
        "operator_uid": stranger_uid,
        "join_mode": "free",
        "invite_code": "HACKED99"
    })
    assert hack_res.status_code == 403
    assert "只有大群组织者" in hack_res.json()["detail"]

    # 6. Real Organizer switches join_mode to 'free' and updates invite_code
    new_code = f"FD_FREE_{ts % 100000}"
    switch_res = client.post(f"/api/org/{org_id}/join-mode", json={
        "operator_uid": owner_uid,
        "join_mode": "free",
        "invite_code": new_code
    })
    assert switch_res.status_code == 200
    assert switch_res.json()["success"] is True
    assert "自由入会" in switch_res.json()["message"]
    updated_org = switch_res.json()["organization"]
    assert updated_org["join_mode"] == "free"
    assert updated_org["invite_code"] == new_code

    # 7. Stranger now joins freely without providing invite_code!
    free_join_res = client.post("/api/org/join", json={
        "user_id": stranger_uid,
        "org_id": org_id,
        "real_name": "路人甲",
        "gender": "male",
        "date_of_birth": "1992-05-05",
        "class_name": "MBA 2022"
    })
    assert free_join_res.status_code == 200
    assert free_join_res.json()["success"] is True
    assert "成功加入" in free_join_res.json()["message"]

    # Verify stranger is now a member
    status_info = LocalStore.check_org_member_status(org_id, stranger_uid)
    assert status_info["is_member"] is True

    # 8. As a regular member, stranger should NOT receive invite_code in my-orgs
    my_orgs_res = client.get(f"/api/org/my-orgs/{stranger_uid}")
    assert my_orgs_res.status_code == 200
    stranger_org_item = next(o for o in my_orgs_res.json()["organizations"] if o["id"] == org_id)
    assert stranger_org_item["join_mode"] == "free"
    assert "invite_code" not in stranger_org_item

    # 9. As owner, lead DOES receive invite_code in my-orgs
    owner_orgs_res = client.get(f"/api/org/my-orgs/{owner_uid}")
    assert owner_orgs_res.status_code == 200
    owner_org_item = next(o for o in owner_orgs_res.json()["organizations"] if o["id"] == org_id)
    assert owner_org_item["invite_code"] == new_code

    # 10. Organizer switches back to 'invite'
    switch_back = client.post(f"/api/org/{org_id}/join-mode", json={
        "operator_uid": owner_uid,
        "join_mode": "invite"
    })
    assert switch_back.status_code == 200
    assert switch_back.json()["organization"]["join_mode"] == "invite"

    # 11. Another member tries to join without code -> rejected
    another_fail = client.post("/api/org/join", json={
        "user_id": member_uid,
        "org_id": org_id,
        "real_name": "第二位跑友",
        "gender": "female",
        "date_of_birth": "1995-01-01",
        "class_name": "EMBA 2024"
    })
    assert another_fail.status_code == 400

    # 12. Joins with new_code -> success!
    code_join = client.post("/api/org/join", json={
        "user_id": member_uid,
        "invite_code": new_code,
        "real_name": "第二位跑友",
        "gender": "female",
        "date_of_birth": "1995-01-01",
        "class_name": "EMBA 2024"
    })
    assert code_join.status_code == 200
    assert "成功加入" in code_join.json()["message"]


def test_web_club_share_and_invite_landing_workflow():
    """Verify Web club share-info returns WeChat share_text, web_invite_url, invite_code, and invite-info + join-club works for WeChat contacts."""
    ts = int(time.time() * 1000)
    owner_uid = f"u_club_inv_owner_{ts}"
    friend_uid = f"u_wechat_friend_{ts}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "王团长", "real_name": "王团长", "email": f"owner_{ts}@test.com"})
    LocalStore.upsert_profile(friend_uid, {"display_name": "微信好友小张", "email": f"friend_{ts}@test.com"})

    club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"万跑网页邀请测试团_{ts}",
        description="测试网页版转发微信跑团邀请",
        city="上海",
        join_mode="invite",
    )
    club_id = club["id"]
    club_code = club["invite_code"]

    # 1. Owner fetches share-info from Web
    share_res = client.get(f"/api/team/{club_id}/share-info?user_id={owner_uid}")
    assert share_res.status_code == 200
    s_data = share_res.json()
    assert s_data["club_id"] == club_id
    assert s_data["invite_code"] == club_code
    assert s_data["inviter_name"] == "王团长"
    assert f"invite_club_id={club_id}" in s_data["web_invite_url"]
    assert club_code in s_data["share_text"]
    assert "王团长" in s_data["share_text"]

    # 2. WeChat friend opens the Web invite link and fetches invite-info
    inv_res = client.get(
        f"/api/team/{club_id}/invite-info?invite_code={club_code}&inviter_uid={owner_uid}&user_id={friend_uid}"
    )
    assert inv_res.status_code == 200
    i_data = inv_res.json()
    assert i_data["club"]["id"] == club_id
    assert i_data["inviter_name"] == "王团长"
    assert i_data["one_click_join"] is True
    assert i_data["is_club_member"] is False

    # 3. WeChat friend clicks 1-click join on Web
    join_res = client.post("/api/team/join-club", json={
        "user_id": friend_uid,
        "club_id": club_id,
        "invite_code": club_code,
        "inviter_uid": owner_uid,
        "via_invite": True,
        "privacy_consent": True,
    })
    assert join_res.status_code == 200
    assert "成功加入" in join_res.json()["message"]


def test_org_periodic_report_and_cross_club_events_workflow():
    """Verify Org Owner/Admin periodic reports (sub-club PK, deduplicated total km, unaffiliated members assignment) and cross-club joint events."""
    from datetime import datetime
    ts = int(time.time() * 1000)
    org_owner_uid = f"u_org_master_{ts}"
    dual_runner_uid = f"u_dual_runner_{ts}"
    club2_runner_uid = f"u_club2_runner_{ts}"
    unaffiliated_uid = f"u_unaff_org_{ts}"

    LocalStore.upsert_profile(org_owner_uid, {"display_name": "大群主理人老周", "real_name": "周主理", "email": f"master_{ts}@test.com"})
    LocalStore.upsert_profile(dual_runner_uid, {"display_name": "跨团双栖大神", "real_name": "张双栖", "email": f"dual_{ts}@test.com"})
    LocalStore.upsert_profile(club2_runner_uid, {"display_name": "二团主力小陈", "real_name": "陈主力", "email": f"c2_{ts}@test.com"})
    LocalStore.upsert_profile(unaffiliated_uid, {"display_name": "游离戈友小刘", "real_name": "刘游离", "email": f"unaff_{ts}@test.com"})

    # 1. Create Grand Organization
    org_res = client.post("/api/org/create", json={
        "name": f"交大高金戈友总会_{ts}",
        "invite_code": f"SAIF_{ts % 100000}",
        "description": "测试大群主理人分跑团报表与跨团活动",
        "city": "上海",
        "owner_id": org_owner_uid,
        "join_mode": "free",
    })
    assert org_res.status_code == 200
    org_id = org_res.json()["organization"]["id"]

    # 2. Create 2 Sub-Clubs under this Organization
    sub_club_1 = LocalStore.create_club(
        owner_id=org_owner_uid,
        name=f"浦东世纪分团_{ts}",
        description="浦东分部",
        city="上海",
        org_id=org_id,
        join_mode="free",
    )
    sub_club_2 = LocalStore.create_club(
        owner_id=org_owner_uid,
        name=f"徐汇滨江分团_{ts}",
        description="徐汇分部",
        city="上海",
        org_id=org_id,
        join_mode="free",
    )
    cid1 = sub_club_1["id"]
    cid2 = sub_club_2["id"]

    # 3. Join members into Organization and Sub-Clubs:
    # - dual_runner_uid joins BOTH sub_club_1 and sub_club_2 (to verify deduplication at org level!)
    # - club2_runner_uid joins sub_club_2 only
    # - unaffiliated_uid joins Organization only (no sub-club)
    for uid, rname, cname in [
        (dual_runner_uid, "张双栖", "EMBA 2023"),
        (club2_runner_uid, "陈主力", "MBA 2024"),
        (unaffiliated_uid, "刘游离", "DBA 2022"),
    ]:
        jr = client.post("/api/org/join", json={
            "user_id": uid,
            "org_id": org_id,
            "real_name": rname,
            "gender": "male",
            "date_of_birth": "1988-08-08",
            "class_name": cname,
        })
        assert jr.status_code == 200

    LocalStore._insert_active_club_membership(cid1, dual_runner_uid, True)
    LocalStore._insert_active_club_membership(cid2, dual_runner_uid, True)
    LocalStore._insert_active_club_membership(cid2, club2_runner_uid, True)

    # 4. Insert running activities for current week/month
    now_iso = datetime.now().strftime("%Y-%m-%dT07:00:00")
    # dual_runner runs 20km (in both clubs, but org total should count 20km ONCE!)
    LocalStore.upsert_activity({
        "id": f"act_dual_{ts}",
        "user_id": dual_runner_uid,
        "name": "世纪公园20km长距离",
        "sport_type": "Run",
        "start_time": now_iso,
        "distance_meters": 20000.0,
        "moving_time_seconds": 6000,
        "elapsed_time_seconds": 6000,
        "average_heartrate": 148,
        "avg_pace_str": "5:00",
    }, notify=False)
    # club2_runner runs 16km
    LocalStore.upsert_activity({
        "id": f"act_c2_{ts}",
        "user_id": club2_runner_uid,
        "name": "徐汇滨江16km节奏跑",
        "sport_type": "Run",
        "start_time": now_iso,
        "distance_meters": 16000.0,
        "moving_time_seconds": 4800,
        "elapsed_time_seconds": 4800,
        "average_heartrate": 152,
        "avg_pace_str": "5:00",
    }, notify=False)
    # unaffiliated_uid runs 10km
    LocalStore.upsert_activity({
        "id": f"act_unaff_{ts}",
        "user_id": unaffiliated_uid,
        "name": "个人晨跑10km",
        "sport_type": "Run",
        "start_time": now_iso,
        "distance_meters": 10000.0,
        "moving_time_seconds": 3300,
        "elapsed_time_seconds": 3300,
        "average_heartrate": 142,
        "avg_pace_str": "5:30",
    }, notify=False)

    # 5. Fetch Org Periodic Report as Org Owner (non-super-admin)
    rep_res = client.get(f"/api/org/{org_id}/reports?operator_uid={org_owner_uid}&period_type=week")
    assert rep_res.status_code == 200
    rep = rep_res.json()
    assert rep["org_id"] == org_id
    # Deduplicated org total distance should be 20 + 16 + 10 = 46.0 km (NOT 20+20+16+10 = 66km!)
    assert rep["summary"]["total_distance_km"] == 46.0
    assert rep["summary"]["sub_clubs_count"] == 2
    assert rep["summary"]["unaffiliated_count"] == 1
    assert len(rep["unaffiliated_members"]) == 1
    assert rep["unaffiliated_members"][0]["user_id"] == unaffiliated_uid

    # Verify sub-club rankings:
    # sub_club_2 has dual_runner (20km) + club2_runner (16km) + org_owner (0km) = 36km
    # sub_club_1 has dual_runner (20km) + org_owner (0km) = 20km
    sc_map = {sc["club_id"]: sc for sc in rep["sub_club_rankings"]}
    assert sc_map[cid2]["total_distance_km"] == 36.0
    assert sc_map[cid1]["total_distance_km"] == 20.0
    assert "微信" in rep["wechat_summary_text"] or "战报" in rep["wechat_summary_text"]

    # 6. Assign unaffiliated member into sub_club_1 via 1-click API
    assign_res = client.post(f"/api/org/{org_id}/members/{unaffiliated_uid}/assign-club", json={
        "operator_uid": org_owner_uid,
        "club_id": cid1,
    })
    assert assign_res.status_code == 200
    assert assign_res.json()["success"] is True

    # Re-fetch report: unaffiliated_count should now be 0, and sub_club_1 total distance becomes 20 + 10 = 30km!
    rep_after = client.get(f"/api/org/{org_id}/reports?operator_uid={org_owner_uid}&period_type=week").json()
    assert rep_after["summary"]["unaffiliated_count"] == 0
    sc_map_after = {sc["club_id"]: sc for sc in rep_after["sub_club_rankings"]}
    assert sc_map_after[cid1]["total_distance_km"] == 30.0
    # Org deduplicated total is still 46.0 km
    assert rep_after["summary"]["total_distance_km"] == 46.0

    # 6b. Verify period_offset=-1 (last week & last month) returns previous period instead of current period
    rep_this_month = client.get(f"/api/org/{org_id}/reports?operator_uid={org_owner_uid}&period_type=month&period_offset=0").json()
    rep_last_month = client.get(f"/api/org/{org_id}/reports?operator_uid={org_owner_uid}&period_type=month&period_offset=-1").json()
    assert rep_this_month["period_label"] != rep_last_month["period_label"]
    assert rep_this_month["date_range_str"] != rep_last_month["date_range_str"]
    assert rep_this_month["summary"]["total_distance_km"] == 46.0
    assert rep_last_month["summary"]["total_distance_km"] == 0.0

    rep_last_week = client.get(f"/api/org/{org_id}/reports?operator_uid={org_owner_uid}&period_type=week&period_offset=-1").json()
    assert rep_after["period_label"] != rep_last_week["period_label"]
    assert rep_after["date_range_str"] != rep_last_week["date_range_str"]
    assert rep_last_week["summary"]["total_distance_km"] == 0.0

    club_this_month = client.get(f"/api/team/{cid1}/reports?operator_uid={org_owner_uid}&period_type=month&period_offset=0").json()
    club_last_month = client.get(f"/api/team/{cid1}/reports?operator_uid={org_owner_uid}&period_type=month&period_offset=-1").json()
    assert club_this_month["period_label"] != club_last_month["period_label"]
    assert club_this_month["total_distance_km"] == 30.0
    assert club_last_month["total_distance_km"] == 0.0

    # 7. Publish a Cross-Club Joint Event from Org Owner
    evt_res = client.post(f"/api/org/{org_id}/events", json={
        "operator_uid": org_owner_uid,
        "title": "全群跨分跑团25km周末大拉练",
        "event_type": "group_run",
        "meet_time": "2026-11-15 06:30",
        "location": "世纪公园7号门",
        "target_km": 25.0,
        "pace_requirement": "A组430 / B组530",
        "rules": "全群各大分跑团联合拉练，共享饮水补给站",
        "scope_club_ids": "all",
    })
    assert evt_res.status_code == 200
    org_event_id = evt_res.json()["event"]["id"]

    # 8. Verify both Sub-Club 1 and Sub-Club 2 automatically see this Cross-Club Event at the top of their events list
    c1_events = LocalStore.get_club_events(cid1, user_id=dual_runner_uid)
    c2_events = LocalStore.get_club_events(cid2, user_id=club2_runner_uid)
    assert any(e["id"] == org_event_id and e.get("is_org_event") is True for e in c1_events)
    assert any(e["id"] == org_event_id and e.get("is_org_event") is True for e in c2_events)

    # 9. Runners from different sub-clubs register for the shared event
    LocalStore.join_club_event(cid1, org_event_id, dual_runner_uid)
    LocalStore.join_club_event(cid2, org_event_id, club2_runner_uid)

    # 10. Fetch Org Events list and verify sub-club breakdown
    org_evts_res = client.get(f"/api/org/{org_id}/events?operator_uid={org_owner_uid}")
    assert org_evts_res.status_code == 200
    org_evts_data = org_evts_res.json()
    target_ev = next(e for e in org_evts_data["org_events"] if e["id"] == org_event_id)
    # org_owner (auto-joined as creator) + dual_runner + club2_runner = 3 participants
    assert target_ev["participants_count"] >= 2
    bd_map = {b["club_id"]: b for b in target_ev["club_breakdown"]}
    assert bd_map[cid1]["registered_count"] >= 2
    assert bd_map[cid2]["registered_count"] >= 2


