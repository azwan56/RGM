import time
import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore

client = TestClient(app)

def test_club_visibility_for_non_org_users():
    ts = int(time.time() * 1000)
    lead_uid = f"u_org_lead_{ts}"
    stranger_uid = f"u_stranger_{ts}"
    member_uid = f"u_org_member_{ts}"

    LocalStore.upsert_profile(lead_uid, {"display_name": "大群会长", "email": f"lead_{ts}@test.com"})
    LocalStore.upsert_profile(stranger_uid, {"display_name": "未加入大群跑者", "email": f"stranger_{ts}@test.com"})
    LocalStore.upsert_profile(member_uid, {"display_name": "已加入大群跑者", "email": f"member_{ts}@test.com"})

    # 1. Create a grand organization
    org_code = f"VIS_{ts % 100000}"
    create_org_res = client.post("/api/org/create", json={
        "name": f"秘密组织戈友会_{ts}",
        "invite_code": org_code,
        "description": "仅内部可见下属分队的测试大群",
        "city": "深圳",
        "owner_id": lead_uid,
        "join_mode": "free"
    })
    assert create_org_res.status_code == 200
    org_id = create_org_res.json()["organization"]["id"]

    # 2. Member joins the organization
    join_res = client.post("/api/org/join", json={
        "user_id": member_uid,
        "org_id": org_id,
        "real_name": "张三",
        "gender": "male",
        "date_of_birth": "1990-01-01",
        "class_name": "EMBA2020",
        "phone": "13800000001",
        "id_card": "110101199001011234",
        "gobi_experience": "A队老戈"
    })
    assert join_res.status_code == 200

    # 3. Create an independent club (no org_id) and a sub-club under the organization
    indep_club = LocalStore.create_club(
        owner_id=lead_uid,
        name=f"深圳市民跑团_{ts}",
        description="所有跑者均可公开浏览的独立跑团",
        city="深圳",
        org_id=None
    )
    indep_club_id = indep_club["id"]

    org_subclub = LocalStore.create_club(
        owner_id=lead_uid,
        name=f"秘密组织下属特训营_{ts}",
        description="隶属于大群的专属特训营",
        city="深圳",
        org_id=org_id
    )
    org_subclub_id = org_subclub["id"]

    # 4. Stranger (who has NOT joined the organization) browses /api/team/all-clubs
    stranger_clubs_res = client.get(f"/api/team/all-clubs?user_id={stranger_uid}")
    assert stranger_clubs_res.status_code == 200
    stranger_clubs = stranger_clubs_res.json()["clubs"]
    stranger_club_ids = [c["id"] for c in stranger_clubs]

    # Independent club MUST be visible
    assert indep_club_id in stranger_club_ids
    # Org sub-club MUST NOT be visible to stranger!
    assert org_subclub_id not in stranger_club_ids

    # 5. Member (who HAS joined the organization) browses /api/team/all-clubs
    member_clubs_res = client.get(f"/api/team/all-clubs?user_id={member_uid}")
    assert member_clubs_res.status_code == 200
    member_clubs = member_clubs_res.json()["clubs"]
    member_club_ids = [c["id"] for c in member_clubs]

    # Both independent club and org sub-club MUST be visible to org member!
    assert indep_club_id in member_club_ids
    assert org_subclub_id in member_club_ids

    # 6. Anonymous / missing user_id cannot see org sub-club either
    anon_res = client.get("/api/team/all-clubs")
    assert anon_res.status_code == 200
    anon_club_ids = [c["id"] for c in anon_res.json()["clubs"]]
    assert indep_club_id in anon_club_ids
    assert org_subclub_id not in anon_club_ids

    # 7. Stranger attempts to browse /api/org/{org_id}/sub-clubs directly -> gets empty sub_clubs list
    stranger_sub_res = client.get(f"/api/org/{org_id}/sub-clubs?user_id={stranger_uid}")
    assert stranger_sub_res.status_code == 200
    assert len(stranger_sub_res.json()["sub_clubs"]) == 0

    # Org member CAN see sub-clubs via /api/org/{org_id}/sub-clubs
    member_sub_res = client.get(f"/api/org/{org_id}/sub-clubs?user_id={member_uid}")
    assert member_sub_res.status_code == 200
    sub_ids = [c["id"] for c in member_sub_res.json()["sub_clubs"]]
    assert org_subclub_id in sub_ids


def test_club_search_by_city_and_keyword():
    ts = int(time.time() * 1000)
    uid = f"u_city_test_{ts}"
    LocalStore.upsert_profile(uid, {"display_name": "城市搜索测试者", "email": f"city_{ts}@test.com"})

    club_sh_obj = LocalStore.create_club(owner_id=uid, name=f"上海世纪公园跑团_{ts}", city="上海", org_id=None)
    club_bj_obj = LocalStore.create_club(owner_id=uid, name=f"北京奥森夜跑团_{ts}", city="北京", org_id=None)
    club_gz_obj = LocalStore.create_club(owner_id=uid, name=f"广州珠江新城夜跑_{ts}", city="广州", org_id=None)

    club_sh = club_sh_obj["id"]
    club_bj = club_bj_obj["id"]
    club_gz = club_gz_obj["id"]

    # 1. Filter by city="北京"
    res_bj = client.get(f"/api/team/all-clubs?user_id={uid}&city=北京")
    assert res_bj.status_code == 200
    bj_ids = [c["id"] for c in res_bj.json()["clubs"]]
    assert club_bj in bj_ids
    assert club_sh not in bj_ids
    assert club_gz not in bj_ids

    # 2. Filter by search="世纪公园"
    res_search = client.get(f"/api/team/all-clubs?user_id={uid}&search=世纪公园")
    assert res_search.status_code == 200
    sh_ids = [c["id"] for c in res_search.json()["clubs"]]
    assert club_sh in sh_ids
    assert club_bj not in sh_ids

    # 3. Check cities list in response
    cities = res_bj.json().get("cities", [])
    assert "上海" in cities
    assert "北京" in cities
    assert "广州" in cities


def test_onboarding_status_and_actions():
    ts = int(time.time() * 1000)
    uid = f"u_onboard_{ts}"

    # 1. Check fresh user status
    LocalStore.upsert_profile(uid, {"display_name": "微信跑者"}) # Default initial name
    status_res = client.get(f"/api/profile/{uid}/onboarding-status")
    assert status_res.status_code == 200
    st = status_res.json()
    assert st["is_completed"] is False
    assert st["steps"]["profile"] is False
    assert st["steps"]["club"] is False
    assert st["steps"]["device"] is False
    assert st["steps"]["history"] is False
    assert st["steps"]["goals"] is False

    # 2. Step 1: Complete profile
    update_prof = client.put(f"/api/profile/{uid}", json={
        "display_name": "闪电侠",
        "gender": "male",
        "date_of_birth": "1995-08-18",
        "height_cm": 178.0,
        "weight_kg": 68.0,
        "years_running": 2
    })
    assert update_prof.status_code == 200

    st1 = client.get(f"/api/profile/{uid}/onboarding-status").json()
    assert st1["steps"]["profile"] is True

    # 3. Step 2: Choose solo runner (skip club)
    act_res = client.post(f"/api/profile/{uid}/onboarding-action", json={
        "action": "skip_club_solo"
    })
    assert act_res.status_code == 200
    st2 = act_res.json()
    assert st2["steps"]["club"] is True
    assert st2["details"]["is_solo_runner"] is True

    # 4. Step 3: Skip device
    act_res3 = client.post(f"/api/profile/{uid}/onboarding-action", json={
        "action": "skip_device"
    })
    assert act_res3.status_code == 200
    st3 = act_res3.json()
    assert st3["steps"]["device"] is True

    # 5. Step 4: Skip history
    act_res4 = client.post(f"/api/profile/{uid}/onboarding-action", json={
        "action": "skip_history"
    })
    assert act_res4.status_code == 200
    st4 = act_res4.json()
    assert st4["steps"]["history"] is True

    # 6. Step 5: Set goal
    goal_res = client.put(f"/api/profile/{uid}/goal", json={
        "target_distance": 220.0
    })
    assert goal_res.status_code == 200
    st5 = client.get(f"/api/profile/{uid}/onboarding-status").json()
    assert st5["steps"]["goals"] is True
    assert st5["is_completed"] is True
    assert st5["completed_count"] == 5
    assert st5["percent"] == 100
