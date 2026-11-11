import pytest
import time
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore

client = TestClient(app)

def test_club_and_org_wechat_invite_flows():
    ts = int(time.time() * 1000)
    user_owner = f"u_owner_{ts}"
    user_member = f"u_member_{ts}"
    user_guest = f"u_guest_{ts}"

    LocalStore.upsert_profile(user_owner, {"email": f"owner_{ts}@test.com", "display_name": "团长"})
    LocalStore.upsert_profile(user_member, {"email": f"member_{ts}@test.com", "display_name": "老队员"})
    LocalStore.upsert_profile(user_guest, {"email": f"guest_{ts}@test.com", "display_name": "新微信跑友"})

    # 1. Create an organization with invite mode
    org_code = f"FD{ts % 10000}"
    org = LocalStore.create_organization(
        name=f"复旦戈友会_{ts}",
        invite_code=org_code,
        description="商学院戈壁挑战赛大本营",
        city="上海",
        owner_id=user_owner,
        join_mode="invite"
    )
    org_id = org["id"]

    # 2. Test Org Invite Preview info
    res_org_invite = client.get(f"/api/org/{org_id}/invite-info?invite_code={org_code}&user_id={user_guest}")
    assert res_org_invite.status_code == 200
    data_org = res_org_invite.json()
    assert data_org["organization"]["name"] == f"复旦戈友会_{ts}"
    assert data_org["is_code_valid"] is True
    assert data_org["is_member"] is False

    # Test with wrong invite code
    res_wrong = client.get(f"/api/org/{org_id}/invite-info?invite_code=WRONGCODE&user_id={user_guest}")
    assert res_wrong.status_code == 200
    assert res_wrong.json()["is_code_valid"] is False

    # 3. Test Org Share info (for owner/member)
    res_org_share = client.get(f"/api/org/{org_id}/share-info?user_id={user_owner}")
    assert res_org_share.status_code == 200
    assert res_org_share.json()["invite_code"] == org_code

    # 4. Guest joins Org directly using the invite code without manual typing
    res_join_org = client.post("/api/org/join", json={
        "user_id": user_guest,
        "org_id": org_id,
        "invite_code": org_code,
        "real_name": "新戈小明",
        "gender": "male",
        "date_of_birth": "1990-05-12",
        "phone": "13800001111",
        "id_card": "310101199005121234",
        "emergency_contact": "13900002222",
        "program": "中文EMBA",
        "class_detail": "2024春季班",
        "gobi_experience": "新戈"
    })
    assert res_join_org.status_code == 200

    # Confirm member in org so they can join sub-clubs
    LocalStore.confirm_org_member(org_id, user_guest, operator_uid=user_owner)

    # 5. Create a sub-club with invite mode
    club_code = f"CL{ts % 10000}"
    club = LocalStore.create_club(
        name=f"陆家嘴戈友分队_{ts}",
        owner_id=user_owner,
        description="复旦戈陆家嘴晨跑团",
        city="上海",
        org_id=org_id,
        join_mode="invite"
    )
    club_id = club["id"]
    LocalStore.update_club(club_id, {"invite_code": club_code})

    # Also join user_member into org and confirm
    LocalStore.join_organization(
        user_id=user_member,
        org_id=org_id,
        invite_code=org_code,
        real_name="老戈友",
        gender="male",
        date_of_birth="1988-01-01",
        phone="13800003333",
        id_card="310101198801011234",
        program="中文EMBA",
        class_detail="2022秋",
        gobi_experience="老戈"
    )
    LocalStore.confirm_org_member(org_id, user_member, operator_uid=user_owner)

    # Owner adds member into club
    LocalStore.join_club_by_id(user_member, club_id, invite_code=club_code)

    # 6. Test Club Share info for existing member
    res_club_share = client.get(f"/api/team/{club_id}/share-info?user_id={user_member}")
    assert res_club_share.status_code == 200
    assert res_club_share.json()["invite_code"] == club_code

    # 7. Test Club Invite preview info for guest
    res_club_invite = client.get(f"/api/team/{club_id}/invite-info?invite_code={club_code}&user_id={user_guest}")
    assert res_club_invite.status_code == 200
    data_club = res_club_invite.json()
    assert data_club["club"]["name"] == f"陆家嘴戈友分队_{ts}"
    assert data_club["club"]["org_name"] == f"复旦戈友会_{ts}"
    assert data_club["is_code_valid"] is True
    assert data_club["is_club_member"] is False
    assert data_club["is_org_member"] is True

    # 8. Guest joins Club using the invite info directly
    res_join_club = client.post("/api/team/join-club", json={
        "user_id": user_guest,
        "club_id": club_id,
        "invite_code": club_code,
        "privacy_consent": True
    })
    assert res_join_club.status_code == 200
    assert "成功加入跑团" in res_join_club.json()["message"]

    # Now verify guest is indeed member
    res_after = client.get(f"/api/team/{club_id}/invite-info?invite_code={club_code}&user_id={user_guest}")
    assert res_after.json()["is_club_member"] is True
