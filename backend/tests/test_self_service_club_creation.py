import time
import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore

client = TestClient(app)


def test_self_service_club_creation_requires_three_watch_bound_referrals():
    ts = int(time.time() * 1000)
    inviter_uid = f"u_inviter_{ts}"
    LocalStore.upsert_profile(inviter_uid, {
        "display_name": "准团长老王",
        "email": f"inviter_{ts}@test.com",
        "created_at": "2026-01-01T00:00:00Z",
    })

    # 1. Initially 0 referrals -> cannot create club (required_count = 3)
    elig_0 = client.get(f"/api/team/creation-eligibility/{inviter_uid}")
    assert elig_0.status_code == 200
    data_0 = elig_0.json()
    assert data_0["invited_count"] == 0
    assert data_0["required_count"] == 3
    assert data_0["remaining_count"] == 3
    assert data_0["can_create_club"] is False
    assert data_0["org_creation_enabled"] is False

    res_blocked = client.post("/api/team/clubs", json={
        "owner_id": inviter_uid,
        "name": f"未解锁跑团_{ts}",
        "city": "上海",
        "description": "还没满3人不应该能创建",
    })
    assert res_blocked.status_code == 403
    assert "0/3" in res_blocked.json()["detail"]

    # 2. Old existing user logging in with inviter_uid MUST NOT count as new user referral
    old_openid = f"wx_old_{ts}"
    old_uid = f"u_wx_old_{ts}"
    LocalStore.upsert_profile(old_uid, {
        "wechat_openid": old_openid,
        "display_name": "老用户",
        "created_at": "2025-01-01T00:00:00Z",
    })
    assert LocalStore.record_referral(inviter_uid, inviter_uid) is False  # self-referral blocked

    # 3. Invite 3 brand-new users via WeChat miniapp login with inviter_uid (NOT bound to watch yet)
    invited_uids = []
    for i in range(1, 4):
        login_res = client.post("/api/auth/wechat/miniapp-login", json={
            "code": f"mock_code_{ts}_{i}",
            "client_uuid": f"client_uuid_{ts}_{i}",
            "nick_name": f"新跑友_{i}号",
            "inviter_uid": inviter_uid,
        })
        assert login_res.status_code == 200
        body = login_res.json()
        assert body["is_new_user"] is True
        assert body["referral_recorded"] is True
        invited_uids.append(body["uid"])

        # Re-login by same user must not double-count
        repeat_res = client.post("/api/auth/wechat/miniapp-login", json={
            "code": f"mock_code_{ts}_{i}",
            "client_uuid": f"client_uuid_{ts}_{i}",
            "nick_name": f"新跑友_{i}号",
            "inviter_uid": inviter_uid,
        })
        assert repeat_res.status_code == 200
        assert repeat_res.json()["referral_recorded"] is False

    # Circular referral check: invitee_1 cannot retroactively invite inviter_uid
    assert LocalStore.record_referral(invited_uids[0], inviter_uid) is False

    # 4. All 3 invited users registered, but 0 have bound a watch -> invited_count == 0, still blocked!
    elig_unbound = client.get(f"/api/team/creation-eligibility/{inviter_uid}").json()
    assert elig_unbound["invited_count"] == 0
    assert elig_unbound["registered_count"] == 3
    assert elig_unbound["pending_watch_count"] == 3
    assert elig_unbound["remaining_count"] == 3
    assert elig_unbound["can_create_club"] is False

    # 5. First 2 invited users bind their watches (Garmin & COROS) -> 2/3 qualified, still blocked
    LocalStore.upsert_profile(invited_uids[0], {"garmin_connected": 1})
    LocalStore.upsert_profile(invited_uids[1], {"coros_connected": 1})

    elig_2 = client.get(f"/api/team/creation-eligibility/{inviter_uid}").json()
    assert elig_2["invited_count"] == 2
    assert elig_2["pending_watch_count"] == 1
    assert elig_2["remaining_count"] == 1
    assert elig_2["can_create_club"] is False

    res_blocked_2 = client.post("/api/team/clubs", json={
        "owner_id": inviter_uid,
        "name": f"差一人跑团_{ts}",
        "city": "上海",
    })
    assert res_blocked_2.status_code == 403
    assert "2/3" in res_blocked_2.json()["detail"]

    # 6. The 3rd invited user binds their watch -> 3/3 qualified, unlocks club creation!
    LocalStore.upsert_profile(invited_uids[2], {"garmin_connected": 1})

    elig_3 = client.get(f"/api/team/creation-eligibility/{inviter_uid}").json()
    assert elig_3["invited_count"] == 3
    assert elig_3["pending_watch_count"] == 0
    assert elig_3["remaining_count"] == 0
    assert elig_3["can_create_club"] is True
    assert len(elig_3["invited_users"]) == 3

    # 7. Create club now succeeds!
    custom_code = f"RGM{ts % 10000:04d}"
    create_res = client.post("/api/team/clubs", json={
        "owner_id": inviter_uid,
        "name": f"浦东晨光战队_{ts % 1000}",
        "city": "上海",
        "description": "满3位绑表新用户解锁的自建跑团",
        "join_mode": "invite",
        "invite_code": custom_code,
    })
    assert create_res.status_code == 200
    club = create_res.json()["club"]
    assert club["owner_id"] == inviter_uid
    assert club["org_id"] is None
    assert club["join_mode"] == "invite"
    assert club["invite_code"] == custom_code

    # 6. Owner can edit club info via PUT /api/team/{club_id}/info
    update_res = client.put(f"/api/team/{club['id']}/info", json={
        "operator_uid": inviter_uid,
        "name": f"浦东破三精英团_{ts % 1000}",
        "city": "杭州",
        "description": "全新升级的跑团简介",
    })
    assert update_res.status_code == 200
    updated_club = update_res.json()["club"]
    assert updated_club["name"] == f"浦东破三精英团_{ts % 1000}"
    assert updated_club["city"] == "杭州"
    assert updated_club["description"] == "全新升级的跑团简介"
