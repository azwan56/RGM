import time
import pytest
from datetime import datetime, timedelta
import sqlite3
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore, DB_PATH

client = TestClient(app)

def test_field_rules_customization_and_verification():
    ts = int(time.time() * 1000)
    owner_uid = f"u_org_owner_{ts}"
    invite_code = f"TEST_RULE_{ts % 100000}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "复旦戈测试管理员", "email": "fudan_admin@test.com"})

    # 1. Create org
    create_res = client.post("/api/org/create", json={
        "name": f"复旦戈测试分部_{ts}",
        "invite_code": invite_code,
        "description": "测试大群必填字段动态配置",
        "city": "上海",
        "owner_id": owner_uid
    })
    assert create_res.status_code == 200, create_res.text
    org = create_res.json()["organization"]
    org_id = org["id"]

    # 2. Get default field rules
    rules_res = client.get(f"/api/org/{org_id}/field-rules")
    assert rules_res.status_code == 200
    rules = rules_res.json()["field_rules"]
    assert any(r["field"] == "real_name" and r["required"] is True for r in rules)
    phone_rule = next((r for r in rules if r["field"] == "phone"), None)
    assert phone_rule is not None
    assert phone_rule["required"] is False  # default optional

    # 3. Admin customizes rules: set phone and emergency_contact as required
    for r in rules:
        if r["field"] in ("phone", "emergency_contact"):
            r["required"] = True

    update_res = client.put(f"/api/org/{org_id}/field-rules", json={
        "field_rules": rules,
        "operator_uid": owner_uid
    })
    assert update_res.status_code == 200
    assert update_res.json()["success"] is True

    # 4. Verify verify-code returns updated rules
    verify_res = client.post("/api/org/verify-code", json={"invite_code": invite_code})
    assert verify_res.status_code == 200
    v_rules = verify_res.json()["field_rules"]
    v_phone = next(r for r in v_rules if r["field"] == "phone")
    v_emg = next(r for r in v_rules if r["field"] == "emergency_contact")
    assert v_phone["required"] is True
    assert v_emg["required"] is True


def test_temporary_status_and_sub_club_gating_workflow():
    ts = int(time.time() * 1000)
    owner_uid = f"u_org_owner_{ts}"
    member_uid = f"u_runner_{ts}"
    stranger_uid = f"u_stranger_{ts}"
    invite_code = f"FD_GATE_{ts % 100000}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "大群主理人", "email": "gobi_lead@test.com"})
    LocalStore.upsert_profile(member_uid, {"display_name": "戈友申请人", "email": "applicant@test.com"})
    LocalStore.upsert_profile(stranger_uid, {"display_name": "路人跑友", "email": "stranger@test.com"})

    # 1. Create org
    create_res = client.post("/api/org/create", json={
        "name": f"复旦戈测试大群_{ts}",
        "invite_code": invite_code,
        "description": "测试准入拦截与有效期",
        "city": "上海",
        "owner_id": owner_uid
    })
    assert create_res.status_code == 200
    org_id = create_res.json()["organization"]["id"]

    # 2. Configure rules: phone and clothing_size are required
    rules = LocalStore.get_org_field_rules(org_id)
    for r in rules:
        if r["field"] in ("phone", "clothing_size"):
            r["required"] = True
    LocalStore.update_org_field_rules(org_id, rules)

    # 3. Create sub-club under this org
    sub_club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"复旦戈先锋分队_{ts}",
        description="复旦戈下属分跑团",
        city="上海",
        org_id=org_id,
        join_mode="free"
    )
    club_id = sub_club["id"]
    assert sub_club["org_id"] == org_id

    # 4. Stranger (not joined org) tries to join sub-club -> 400 / Forbidden
    stranger_join = client.post("/api/team/join-club", json={
        "user_id": stranger_uid,
        "club_id": club_id
    })
    assert stranger_join.status_code == 400
    assert "尚未加入该大群" in stranger_join.json()["detail"]

    # 5. Member joins org with missing required fields (phone and clothing_size omitted)
    join_res = client.post("/api/org/join", json={
        "user_id": member_uid,
        "invite_code": invite_code,
        "real_name": "王测试",
        "gender": "male",
        "date_of_birth": "1990-08-08",
        "class_name": "EMBA 23春"
    })
    assert join_res.status_code == 200
    m_data = join_res.json()["membership"]
    assert m_data["status"] == "temporary"
    assert m_data["days_remaining"] == 14
    missing_names = [m["field"] for m in m_data["missing_fields"]]
    assert "phone" in missing_names
    assert "clothing_size" in missing_names

    # 6. Temporary member tries to join sub-club -> 400 / Blocked
    temp_join = client.post("/api/team/join-club", json={
        "user_id": member_uid,
        "club_id": club_id
    })
    assert temp_join.status_code == 400
    assert "临时人员" in temp_join.json()["detail"]
    assert "尚未填写全部必填资料" in temp_join.json()["detail"]

    # 7. Member updates profile to complete required fields
    update_profile_res = client.post(f"/api/org/{org_id}/members/update-profile", json={
        "user_id": member_uid,
        "phone": "13811112222",
        "clothing_size": "L"
    })
    assert update_profile_res.status_code == 200
    up_data = update_profile_res.json()["membership"]
    assert up_data["status"] == "pending"
    assert len(up_data["missing_fields"]) == 0

    # 8. Member tries to join sub-club in pending state -> 400 / Blocked
    pending_join = client.post("/api/team/join-club", json={
        "user_id": member_uid,
        "club_id": club_id
    })
    assert pending_join.status_code == 400
    assert "等待大群管理员审核批准" in pending_join.json()["detail"]

    # 9. Admin confirms member
    confirm_res = client.post(f"/api/org/{org_id}/members/{member_uid}/confirm", json={
        "operator_uid": owner_uid
    })
    assert confirm_res.status_code == 200
    assert confirm_res.json()["success"] is True

    # Verify status in get_user_organizations
    my_orgs_res = client.get(f"/api/org/my-orgs/{member_uid}")
    assert my_orgs_res.status_code == 200
    my_org = next(o for o in my_orgs_res.json()["organizations"] if o["id"] == org_id)
    assert my_org["status"] == "confirmed"

    # 10. Member joins sub-club successfully
    ok_join = client.post("/api/team/join-club", json={
        "user_id": member_uid,
        "club_id": club_id
    })
    assert ok_join.status_code == 200
    assert "成功加入" in ok_join.json()["message"]


def test_14_days_expiration_and_access_block():
    ts = int(time.time() * 1000)
    owner_uid = f"u_org_owner_{ts}"
    expired_runner_uid = f"u_expired_runner_{ts}"
    invite_code = f"FD_EXP_{ts % 100000}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "大群主理人", "email": "gobi_lead2@test.com"})
    LocalStore.upsert_profile(expired_runner_uid, {"display_name": "超期临时跑友", "email": "expired@test.com"})

    # 1. Create org
    create_res = client.post("/api/org/create", json={
        "name": f"复旦戈过期测试大群_{ts}",
        "invite_code": invite_code,
        "description": "测试超期自动变为已过期并拒绝进入大群",
        "city": "上海",
        "owner_id": owner_uid
    })
    assert create_res.status_code == 200
    org_id = create_res.json()["organization"]["id"]

    # 2. Member joins org
    join_res = client.post("/api/org/join", json={
        "user_id": expired_runner_uid,
        "invite_code": invite_code,
        "real_name": "赵超期",
        "gender": "male",
        "date_of_birth": "1992-02-02",
        "class_name": "MBA 21级"
    })
    assert join_res.status_code == 200

    # 3. Simulate 15 days elapsed since joined_at
    past_15_days = (datetime.utcnow() - timedelta(days=15)).isoformat() + "Z"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE organization_members SET joined_at = ?, status = 'temporary' WHERE org_id = ? AND user_id = ?",
                     (past_15_days, org_id, expired_runner_uid))
        conn.commit()

    # 4. Check status calculation
    status_info = LocalStore.check_org_member_status(org_id, expired_runner_uid)
    assert status_info["status"] == "expired"
    assert status_info["is_valid"] is False
    assert status_info["days_remaining"] == 0

    # 5. Expired user attempts to enter org details -> 403 Forbidden
    org_detail_res = client.get(f"/api/org/{org_id}?user_id={expired_runner_uid}")
    assert org_detail_res.status_code == 403
    assert "临时访问权限已到期" in org_detail_res.json()["detail"]

    # 6. Expired user attempts to view org members roster -> 403 Forbidden
    roster_res = client.get(f"/api/org/{org_id}/members?operator_uid={expired_runner_uid}")
    assert roster_res.status_code == 403
    assert "临时访问权限已到期" in roster_res.json()["detail"]

    # 7. Create sub-club and verify expired user cannot join
    sub_club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"复旦戈测试分队二_{ts}",
        description="分跑团",
        city="上海",
        org_id=org_id,
        join_mode="free"
    )
    fail_join = client.post("/api/team/join-club", json={
        "user_id": expired_runner_uid,
        "club_id": sub_club["id"]
    })
    assert fail_join.status_code == 400
    assert "临时身份已过期" in fail_join.json()["detail"]

    # 8. Rejoining with invite code grants a fresh start
    rejoin_res = client.post("/api/org/join", json={
        "user_id": expired_runner_uid,
        "invite_code": invite_code,
        "real_name": "赵重新激活",
        "gender": "male",
        "date_of_birth": "1992-02-02",
        "class_name": "MBA 21级"
    })
    assert rejoin_res.status_code == 200
    re_membership = rejoin_res.json()["membership"]
    assert re_membership["status"] == "pending"
    assert re_membership["days_remaining"] == 14


def test_org_program_and_gobi_experience():
    ts = int(time.time() * 1000)
    owner_uid = f"u_org_owner_gobi_{ts}"
    runner_new_uid = f"u_runner_newbie_{ts}"
    runner_vet_uid = f"u_runner_veteran_{ts}"
    invite_code = f"FD_GOBI_{ts % 100000}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "复旦戈测试管理员", "email": "gobi_admin@test.com"})
    LocalStore.upsert_profile(runner_new_uid, {"display_name": "新戈小明", "email": "xiaoming@test.com"})
    LocalStore.upsert_profile(runner_vet_uid, {"display_name": "老戈老王", "email": "laowang@test.com"})

    # 1. Create org
    create_res = client.post("/api/org/create", json={
        "name": f"复旦戈测试院_{ts}",
        "invite_code": invite_code,
        "description": "测试商学院项目与戈壁经历",
        "city": "上海",
        "owner_id": owner_uid
    })
    assert create_res.status_code == 200
    org_id = create_res.json()["organization"]["id"]

    # 2. Check default rules include gobi_experience
    rules_res = client.get(f"/api/org/{org_id}/field-rules")
    assert rules_res.status_code == 200
    rules = rules_res.json()["field_rules"]
    gobi_rule = next((r for r in rules if r["field"] == "gobi_experience"), None)
    assert gobi_rule is not None
    assert gobi_rule["required"] is False

    # 3. Join with program + class_detail and gobi_experience = "新戈"
    join_res1 = client.post("/api/org/join", json={
        "user_id": runner_new_uid,
        "invite_code": invite_code,
        "real_name": "张小明",
        "gender": "male",
        "date_of_birth": "1995-05-15",
        "program": "中文EMBA",
        "class_detail": "23春",
        "gobi_experience": "新戈"
    })
    assert join_res1.status_code == 200
    m1 = join_res1.json()["membership"]
    assert m1["class_name"] == "中文EMBA 23春"
    assert m1["program"] == "中文EMBA"
    assert m1["class_detail"] == "23春"
    assert m1["gobi_experience"] == "新戈"
    assert m1["status"] == "pending"

    # 4. Join with program + class_detail and veteran gobi_experience = "戈20 A组"
    join_res2 = client.post("/api/org/join", json={
        "user_id": runner_vet_uid,
        "invite_code": invite_code,
        "real_name": "王戈老",
        "gender": "male",
        "date_of_birth": "1988-08-18",
        "program": "复旦-BI（挪威）",
        "class_detail": "18班",
        "gobi_experience": "戈20 A组"
    })
    assert join_res2.status_code == 200
    m2 = join_res2.json()["membership"]
    assert m2["class_name"] == "复旦-BI（挪威） 18班"
    assert m2["program"] == "复旦-BI（挪威）"
    assert m2["class_detail"] == "18班"
    assert m2["gobi_experience"] == "戈20 A组"

    # 5. Verify get_user_organizations returns structured fields
    user_orgs = client.get(f"/api/org/my-orgs/{runner_vet_uid}").json()["organizations"]
    target_org = next(o for o in user_orgs if o["id"] == org_id)
    assert target_org["program"] == "复旦-BI（挪威）"
    assert target_org["class_detail"] == "18班"
    assert target_org["gobi_experience"] == "戈20 A组"

    # 6. Set gobi_experience as REQUIRED and test temporary status
    for r in rules:
        if r["field"] == "gobi_experience":
            r["required"] = True
    client.put(f"/api/org/{org_id}/field-rules", json={"field_rules": rules, "operator_uid": owner_uid})

    runner3_uid = f"u_runner_empty_{ts}"
    LocalStore.upsert_profile(runner3_uid, {"display_name": "未填经历者", "email": "empty@test.com"})
    join_res3 = client.post("/api/org/join", json={
        "user_id": runner3_uid,
        "invite_code": invite_code,
        "real_name": "李空空",
        "gender": "female",
        "date_of_birth": "1993-03-03",
        "program": "台大班",
        "class_detail": "2022秋"
        # gobi_experience omitted
    })
    assert join_res3.status_code == 200
    m3 = join_res3.json()["membership"]
    assert m3["status"] == "temporary"
    missing = [mf["field"] for mf in m3["missing_fields"]]
    assert "gobi_experience" in missing

    # Update profile to complete gobi_experience
    up_res = client.post(f"/api/org/{org_id}/members/update-profile", json={
        "user_id": runner3_uid,
        "gobi_experience": "戈19 B组"
    })
    assert up_res.status_code == 200
    up_m = up_res.json()["membership"]
    assert up_m["status"] == "pending"
    assert up_m["gobi_experience"] == "戈19 B组"

    # 7. Test roster search by gobi_experience and program
    members_res1 = client.get(f"/api/org/{org_id}/members?operator_uid={owner_uid}&search=戈20")
    assert members_res1.status_code == 200
    m_list1 = members_res1.json()["members"]
    assert len(m_list1) == 1
    assert m_list1[0]["user_id"] == runner_vet_uid

    members_res2 = client.get(f"/api/org/{org_id}/members?operator_uid={owner_uid}&search=新戈")
    assert members_res2.status_code == 200
    m_list2 = members_res2.json()["members"]
    assert len(m_list2) == 1
    assert m_list2[0]["user_id"] == runner_new_uid

    members_res3 = client.get(f"/api/org/{org_id}/members?operator_uid={owner_uid}&search=挪威")
    assert members_res3.status_code == 200
    m_list3 = members_res3.json()["members"]
    assert len(m_list3) == 1
    assert m_list3[0]["user_id"] == runner_vet_uid


def test_sub_club_access_suspension_and_admin_confirmation_flow():
    ts = int(time.time() * 1000)
    owner_uid = f"u_org_admin_{ts}"
    runner_uid = f"u_test_runner_{ts}"
    invite_code = f"FD_SUSP_{ts % 100000}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "复旦戈大团管理员", "email": "fudan_admin2@test.com"})
    LocalStore.upsert_profile(runner_uid, {"display_name": "复旦戈受试队员", "email": "tested_runner@test.com"})

    # 1. Create grand org (e.g. 复旦戈)
    org_res = client.post("/api/org/create", json={
        "name": f"复旦戈测试总团_{ts}",
        "invite_code": invite_code,
        "description": "测试超期2周暂停下属跑团浏览与活动使用",
        "city": "上海",
        "owner_id": owner_uid
    })
    assert org_res.status_code == 200
    org_id = org_res.json()["organization"]["id"]

    # 2. Create sub-club under this org (e.g. 复旦戈闵文跑团)
    sub_club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"复旦戈闵文测试跑团_{ts}",
        description="复旦戈闵文下属跑团",
        city="上海",
        org_id=org_id,
        join_mode="free"
    )
    sub_club_id = sub_club["id"]

    # 3. Create independent club (e.g. RGM先锋跑团) with org_id = None
    indep_club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"RGM先锋独立测试跑团_{ts}",
        description="独立跑团不属于任何大群体",
        city="上海",
        org_id=None,
        join_mode="free"
    )
    indep_club_id = indep_club["id"]

    # 4. Runner joins org
    join_res = client.post("/api/org/join", json={
        "user_id": runner_uid,
        "invite_code": invite_code,
        "real_name": "李戈友",
        "gender": "female",
        "date_of_birth": "1995-05-05",
        "class_name": "MBA 2024秋",
        "program": "全日制MBA",
        "class_detail": "2024秋"
    })
    assert join_res.status_code == 200
    assert join_res.json()["membership"]["status"] == "pending"

    # Also add runner as member of sub-club and independent club for test
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES (?, ?, ?, 'member', 'active', ?)",
                     (f"{sub_club_id}_{runner_uid}", sub_club_id, runner_uid, datetime.utcnow().isoformat()))
        conn.execute("INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES (?, ?, ?, 'member', 'active', ?)",
                     (f"{indep_club_id}_{runner_uid}", indep_club_id, runner_uid, datetime.utcnow().isoformat()))
        conn.commit()

    # 5. Within 14 days, runner CAN access sub-club dashboard, feed, leaderboard, events, members
    dash_res = client.get(f"/api/team/{sub_club_id}/dashboard?user_id={runner_uid}")
    assert dash_res.status_code == 200

    feed_res = client.get(f"/api/team/{sub_club_id}/feed?uid={runner_uid}")
    assert feed_res.status_code == 200

    mem_res = client.get(f"/api/team/{sub_club_id}/members?user_id={runner_uid}")
    assert mem_res.status_code == 200

    # 6. Now simulate 15 days elapsed without admin confirmation
    past_15_days = (datetime.utcnow() - timedelta(days=15)).isoformat() + "Z"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE organization_members SET joined_at = ? WHERE org_id = ? AND user_id = ?",
                     (past_15_days, org_id, runner_uid))
        conn.commit()

    # Verify status in check_org_member_status is expired/suspended
    st = LocalStore.check_org_member_status(org_id, runner_uid)
    assert st["status"] == "expired"
    assert st["is_valid"] is False

    # 7. Expired/suspended runner tries to browse or use sub-club -> 403 Forbidden!
    dash_blocked = client.get(f"/api/team/{sub_club_id}/dashboard?user_id={runner_uid}")
    assert dash_blocked.status_code == 403
    assert "访问被暂停" in dash_blocked.json()["detail"]

    feed_blocked = client.get(f"/api/team/{sub_club_id}/feed?uid={runner_uid}")
    assert feed_blocked.status_code == 403
    assert "访问被暂停" in feed_blocked.json()["detail"]

    mem_blocked = client.get(f"/api/team/{sub_club_id}/members?user_id={runner_uid}")
    assert mem_blocked.status_code == 403
    assert "访问被暂停" in mem_blocked.json()["detail"]

    evt_blocked = client.get(f"/api/team/{sub_club_id}/events?user_id={runner_uid}")
    assert evt_blocked.status_code == 403
    assert "访问被暂停" in evt_blocked.json()["detail"]

    lead_blocked = client.get(f"/api/team/{sub_club_id}/leaderboard?user_id={runner_uid}")
    assert lead_blocked.status_code == 403
    assert "访问被暂停" in lead_blocked.json()["detail"]

    sub_clubs_blocked = client.get(f"/api/org/{org_id}/sub-clubs?user_id={runner_uid}")
    assert sub_clubs_blocked.status_code == 403
    assert "临时访问权限已到期" in sub_clubs_blocked.json()["detail"]

    # 8. Check my-clubs list flags is_access_suspended = True
    my_clubs = LocalStore.get_user_clubs(runner_uid)
    sub_c = next(c for c in my_clubs if c["id"] == sub_club_id)
    assert sub_c["is_access_suspended"] is True
    assert "暂停使用" in sub_c["suspension_reason"]

    # 9. Independent club (RGM先锋跑团) is NOT blocked!
    indep_dash = client.get(f"/api/team/{indep_club_id}/dashboard?user_id={runner_uid}")
    assert indep_dash.status_code == 200

    indep_feed = client.get(f"/api/team/{indep_club_id}/feed?uid={runner_uid}")
    assert indep_feed.status_code == 200

    indep_c = next(c for c in my_clubs if c["id"] == indep_club_id)
    assert indep_c["is_access_suspended"] is False

    # 10. Admin confirms member
    confirm_res = client.post(f"/api/org/{org_id}/members/{runner_uid}/confirm", json={
        "operator_uid": owner_uid
    })
    assert confirm_res.status_code == 200

    # 11. Now runner is confirmed formal member! All sub-club endpoints are restored (200 OK)!
    st2 = LocalStore.check_org_member_status(org_id, runner_uid)
    assert st2["status"] == "confirmed"
    assert st2["is_valid"] is True

    dash_ok = client.get(f"/api/team/{sub_club_id}/dashboard?user_id={runner_uid}")
    assert dash_ok.status_code == 200

    feed_ok = client.get(f"/api/team/{sub_club_id}/feed?uid={runner_uid}")
    assert feed_ok.status_code == 200

    mem_ok = client.get(f"/api/team/{sub_club_id}/members?user_id={runner_uid}")
    assert mem_ok.status_code == 200

    lead_ok = client.get(f"/api/team/{sub_club_id}/leaderboard?user_id={runner_uid}")
    assert lead_ok.status_code == 200


def test_incomplete_profile_cannot_be_confirmed_and_auto_downgrades():
    ts = int(time.time() * 1000)
    owner_uid = f"u_org_owner_inc_{ts}"
    runner_uid = f"u_runner_inc_{ts}"
    invite_code = f"INC_{ts % 100000}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "测试主理人", "email": "lead_inc@test.com"})
    LocalStore.upsert_profile(runner_uid, {"display_name": "未填全跑友", "email": "runner_inc@test.com"})

    # 1. Create org
    create_res = client.post("/api/org/create", json={
        "name": f"复旦戈测试_{ts}",
        "invite_code": invite_code,
        "description": "测试不完整资料审核与降级",
        "city": "上海",
        "owner_id": owner_uid
    })
    assert create_res.status_code == 200
    org_id = create_res.json()["organization"]["id"]

    # 2. Field rules: real_name, date_of_birth, class_name, gobi_experience required
    rules = LocalStore.get_org_field_rules(org_id)
    for r in rules:
        if r["field"] in ("real_name", "date_of_birth", "class_name", "gobi_experience"):
            r["required"] = True
    LocalStore.update_org_field_rules(org_id, rules)

    # 3. Runner joins with placeholder class '复旦戈友' and no gobi_experience
    join_res = client.post("/api/org/join", json={
        "user_id": runner_uid,
        "invite_code": invite_code,
        "real_name": "王某某",
        "gender": "male",
        "date_of_birth": "1990-01-01",
        "class_name": "复旦戈友",  # Placeholder!
        "phone": "13800001111"
    })
    assert join_res.status_code == 200
    membership = join_res.json()["membership"]
    assert membership["status"] == "temporary"  # Must be temporary!

    # 4. Admin attempts to confirm member with missing fields -> MUST FAIL with 400!
    confirm_fail = client.post(f"/api/org/{org_id}/members/{runner_uid}/confirm", json={
        "operator_uid": owner_uid
    })
    assert confirm_fail.status_code == 400
    assert "尚未补齐" in confirm_fail.json()["detail"]

    # 5. Simulate legacy / hardcoded confirmed record in DB (like what scripts did)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE organization_members 
            SET status = 'confirmed', confirmed_by = 'legacy_admin', confirmed_at = '2026-01-01T00:00:00Z'
            WHERE org_id = ? AND user_id = ?
        """, (org_id, runner_uid))

    # 6. check_org_member_status MUST automatically detect missing fields, demote to temporary, and clear confirmed_by
    st = LocalStore.check_org_member_status(org_id, runner_uid)
    assert st["status"] == "temporary"
    assert len(st["missing_fields"]) > 0
    missing_fields_names = [f["field"] for f in st["missing_fields"]]
    assert "class_name" in missing_fields_names  # '复旦戈友' recognized as placeholder!
    assert "gobi_experience" in missing_fields_names

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT status, confirmed_by FROM organization_members WHERE org_id = ? AND user_id = ?", (org_id, runner_uid)).fetchone()
        assert row[0] == "temporary"
        assert row[1] is None

    # 7. Runner fills in real program/class and gobi_experience
    up_res = client.post(f"/api/org/{org_id}/members/update-profile", json={
        "user_id": runner_uid,
        "program": "中文EMBA",
        "class_detail": "23春",
        "gobi_experience": "新戈"
    })
    assert up_res.status_code == 200
    assert up_res.json()["membership"]["status"] == "pending"

    # 8. Now all required fields are filled, admin confirms successfully!
    confirm_ok = client.post(f"/api/org/{org_id}/members/{runner_uid}/confirm", json={
        "operator_uid": owner_uid
    })
    assert confirm_ok.status_code == 200
    st_final = LocalStore.check_org_member_status(org_id, runner_uid)
    assert st_final["status"] == "confirmed"
    assert len(st_final["missing_fields"]) == 0



