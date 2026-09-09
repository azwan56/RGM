import time
import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore

client = TestClient(app)

def test_org_admin_management_workflow():
    owner_uid = f"u_org_owner_{int(time.time())}"
    member_uid = f"u_org_member_{int(time.time())}"
    invite_code = f"SJ_{int(time.time()) % 1000000}"

    # 1. Setup profiles
    LocalStore.upsert_profile(owner_uid, {"display_name": "交大戈主理人", "email": "sjtu_owner@test.com"})
    LocalStore.upsert_profile(member_uid, {"display_name": "交大戈友小李", "email": "sjtu_runner@test.com"})

    # 2. Admin creates a new grand community (交大戈)
    create_res = client.post("/api/org/create", json={
        "name": "交大安泰戈友会",
        "invite_code": invite_code,
        "description": "上海交通大学安泰经管学院戈壁挑战赛大群体",
        "city": "上海",
        "owner_id": owner_uid
    })
    assert create_res.status_code == 200, create_res.text
    org_data = create_res.json()["organization"]
    org_id = org_data["id"]
    assert org_data["name"] == "交大安泰戈友会"
    assert org_data["invite_code"] == invite_code

    # 3. List all orgs with invite code via admin endpoint
    admin_list_res = client.get("/api/org/admin/all-list")
    assert admin_list_res.status_code == 200
    all_orgs = admin_list_res.json()["organizations"]
    matched = [o for o in all_orgs if o["id"] == org_id]
    assert len(matched) == 1
    assert matched[0]["invite_code"] == invite_code
    assert matched[0]["owner_name"] == "交大戈主理人"

    # 4. Admin updates org details
    update_res = client.put(f"/api/org/{org_id}", json={
        "description": "更新后的交大安泰戈友会介绍",
        "city": "上海徐汇"
    })
    assert update_res.status_code == 200
    updated_org = update_res.json()["organization"]
    assert updated_org["description"] == "更新后的交大安泰戈友会介绍"
    assert updated_org["city"] == "上海徐汇"

    # 5. Create a standalone club and bind it to the organization
    test_club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"交大戈闵行先锋队_{int(time.time())}",
        description="交大戈下属闵行训练营",
        city="上海"
    )
    club_id = test_club["id"]
    assert test_club["org_id"] is None

    # Bind club to org
    bind_res = client.post(f"/api/org/{org_id}/bind-club", json={
        "club_id": club_id,
        "action": "bind"
    })
    assert bind_res.status_code == 200
    assert bind_res.json()["club"]["org_id"] == org_id

    # Verify sub-clubs API
    sub_res = client.get(f"/api/org/{org_id}/sub-clubs")
    assert sub_res.status_code == 200
    sub_ids = [sc["id"] for sc in sub_res.json()["sub_clubs"]]
    assert club_id in sub_ids

    # 6. Member joins organization with real credentials
    join_res = client.post("/api/org/join", json={
        "user_id": member_uid,
        "invite_code": invite_code,
        "real_name": "李安泰",
        "gender": "male",
        "date_of_birth": "1988-06-18",
        "class_name": "EMBA 22秋",
        "phone": "13800000000"
    })
    assert join_res.status_code == 200
    assert "成功加入" in join_res.json()["message"]

    # 7. Query roster
    members_res = client.get(f"/api/org/{org_id}/members")
    assert members_res.status_code == 200
    members = members_res.json()["members"]
    assert any(m["user_id"] == member_uid and m["real_name"] == "李安泰" for m in members)

    # 8. Unbind club
    unbind_res = client.post(f"/api/org/{org_id}/bind-club", json={
        "club_id": club_id,
        "action": "unbind"
    })
    assert unbind_res.status_code == 200
    assert unbind_res.json()["club"]["org_id"] is None
