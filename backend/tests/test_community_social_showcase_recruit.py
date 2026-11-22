import base64
import os
import sqlite3
import time
from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

import utils.local_store as ls_mod
from config import settings
from main import app
from utils.local_store import LocalStore, get_beijing_today, init_db

MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00"
    b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_jwt(uid: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": uid, "uid": uid, "aud": "authenticated", "iat": now, "exp": now + 3600},
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )


def _headers(uid: str):
    return {"Authorization": f"Bearer {_make_jwt(uid)}", "x-user-id": uid}


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    db_file = str(tmp_path / "community_test.db")
    monkeypatch.setattr(ls_mod, "DB_PATH", db_file)
    LocalStore.invalidate_uid_cache()
    init_db()

    today = get_beijing_today()
    yesterday = (today - timedelta(days=1)).isoformat() + "T07:00:00+08:00"
    two_days_ago = (today - timedelta(days=2)).isoformat() + "T07:00:00+08:00"

    # Seed org + 2 org clubs + 1 public club + 5 runners
    with sqlite3.connect(db_file) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO organizations (id, name, invite_code, owner_id, join_mode, created_at) VALUES (?, ?, ?, ?, 'free', ?)",
            ("org_fudan", "复旦戈壁大群", "FUDAN0", "u_captain", two_days_ago),
        )
        c.execute(
            "INSERT OR REPLACE INTO clubs (id, org_id, name, city, invite_code, owner_id, join_mode, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'invite', 'active', ?)",
            ("club_a", "org_fudan", "复旦21班分团", "上海", "FD21AA", "u_captain", two_days_ago),
        )
        c.execute(
            "INSERT OR REPLACE INTO clubs (id, org_id, name, city, invite_code, owner_id, join_mode, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'invite', 'active', ?)",
            ("club_b", "org_fudan", "张江破330特训营", "上海", "ZJ330B", "u_coach_b", two_days_ago),
        )
        c.execute(
            "INSERT OR REPLACE INTO clubs (id, org_id, name, city, invite_code, owner_id, join_mode, status, created_at) VALUES (?, NULL, ?, ?, ?, ?, 'free', 'active', ?)",
            ("club_pub", "世纪公园公开团", "上海", "SJPARK", "u_pub_owner", two_days_ago),
        )

    LocalStore.upsert_profile("u_captain", {
        "display_name": "陈团长", "gender": "male", "date_of_birth": "1986-04-12", "vo2max": 49.5,
        "city": "上海", "running_landmarks": ["世纪公园", "徐汇滨江"], "garmin_connected": 1, "marathon_pb": 10620,
    })
    LocalStore.upsert_profile("u_coach_b", {
        "display_name": "林教练", "gender": "female", "date_of_birth": "1988-09-01", "vo2max": 50.0,
        "city": "上海", "running_landmarks": ["世纪公园"], "coros_connected": 1, "marathon_pb": 11100,
        "first_aid_cert_type": "AHA急救", "pacer_bio_tags": "上马官兔,戈赛导师",
    })
    LocalStore.upsert_profile("u_newcomer", {
        "display_name": "林晓月", "real_name": "林真名绝不可露出", "phone": "13900001234",
        "gender": "female", "date_of_birth": "1991-06-15", "vo2max": 48.0,
        "city": "上海", "running_landmarks": ["世纪公园", "陆家嘴"],
        "hide_gps_route": True, "hide_biometrics": True, "canova_critique_visibility": "self",
        "allow_buddy_search_scope": "org_and_clubs", "allow_club_search_scope": "same_org",
        "garmin_connected": 1,
    })
    LocalStore.upsert_profile("u_hidden", {
        "display_name": "隐身跑者", "gender": "male", "date_of_birth": "1982-01-01", "vo2max": 49.0,
        "city": "上海", "running_landmarks": ["世纪公园"],
        "allow_buddy_search_scope": "none", "allow_club_search_scope": "none",
    })
    LocalStore.upsert_profile("u_outsider", {
        "display_name": "外部公开跑友", "gender": "male", "date_of_birth": "1990-02-02", "vo2max": 48.5,
        "city": "上海", "running_landmarks": ["徐汇滨江"],
        "allow_buddy_search_scope": "public", "allow_club_search_scope": "public",
    })
    LocalStore.upsert_profile("u_pub_owner", {"display_name": "公开团长", "city": "上海"})

    with sqlite3.connect(db_file) as conn:
        c = conn.cursor()
        # Org memberships
        for uid_m, role_m in [("u_captain", "owner"), ("u_coach_b", "coach"), ("u_newcomer", "confirmed"), ("u_hidden", "confirmed")]:
            st = "confirmed"
            c.execute(
                "INSERT OR REPLACE INTO organization_members (id, org_id, user_id, real_name, gender, date_of_birth, class_name, role, status, joined_at) VALUES (?, 'org_fudan', ?, ?, 'male', '1990-01-01', 'EMBA21班', ?, ?, ?)",
                (f"om_{uid_m}", uid_m, f"姓名_{uid_m}", "owner" if uid_m == "u_captain" else "member", st, two_days_ago),
            )
        # Club memberships: u_newcomer & u_hidden are in club_a ONLY (not club_b yet!)
        for mid, cid, uid_m, role_m in [
            ("cm_cap_a", "club_a", "u_captain", "owner"),
            ("cm_coach_b", "club_b", "u_coach_b", "owner"),
            ("cm_new_a", "club_a", "u_newcomer", "member"),
            ("cm_hid_a", "club_a", "u_hidden", "member"),
            ("cm_pub_own", "club_pub", "u_pub_owner", "owner"),
            ("cm_out_pub", "club_pub", "u_outsider", "member"),
        ]:
            c.execute(
                "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent) VALUES (?, ?, ?, ?, 'active', ?, 1)",
                (mid, cid, uid_m, role_m, two_days_ago),
            )
        # Seed running activities for 30d mileage & weekly PK + privacy filter test
        for idx, (aid, auid, km, avg_hr, gps, crit) in enumerate([
            ("act_new_1", "u_newcomer", 120000.0, 152, "[[31.2,121.5],[31.21,121.51]]", "私密评语仅自己可见"),
            ("act_cap_1", "u_captain", 60000.0, 145, "[[31.2,121.5],[31.22,121.52]]", "团长有氧课表"),
            ("act_out_1", "u_outsider", 140000.0, 150, None, None),
        ]):
            c.execute(
                """
                INSERT OR REPLACE INTO activities
                (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, average_heartrate, gps_track_data, ai_journal, avg_pace_str)
                VALUES (?, ?, ?, 'running', ?, ?, 3600, ?, ?, ?, '4:50')
                """,
                (aid, auid, f"晨跑_{idx}", yesterday, km, avg_hr, gps, crit),
            )
        # Seed coach pacer race record
        c.execute(
            """
            INSERT OR REPLACE INTO race_plans
            (id, user_id, name, race_type, race_date, target_time, status, finish_time, was_official_pacer, pacer_target_time, created_at)
            VALUES ('race_coach_1', 'u_coach_b', '2025 上海马拉松', 'full', '2025-11-30', '3:05:00', 'completed', '3:05:00', 1, '3:15:00', ?)
            """,
            (two_days_ago,),
        )
        conn.commit()

    created_files = []
    yield {"db_file": db_file, "client": TestClient(app), "created_files": created_files}

    # Cleanup any temporary showcase photos created on disk
    photos_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "showcase_photos")
    for fn in created_files:
        p = os.path.join(photos_dir, fn)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    LocalStore.invalidate_uid_cache()


def test_phase1_broadcast_pulse_and_micro_cheer_privacy(isolated_env):
    c = isolated_env["client"]
    # Captain creates pinned broadcast
    res = c.post(
        "/api/community/clubs/club_a/broadcasts",
        headers=_headers("u_captain"),
        json={
            "author_id": "u_captain",
            "category": "group_run",
            "title": "周六06:00 世纪公园长距离集结",
            "content": "A/B/C 三组同步发车，欢迎新入团跑友！",
            "target_audience": "all",
            "pin_hours": 72,
        },
    )
    assert res.status_code == 200
    bid = res.json()["broadcast"]["id"]

    # Member views home pulse -> sees pinned broadcast, newcomer anonymized, privacy enforced on newcomer's activity
    pulse_res = c.get("/api/community/home-pulse?viewer_uid=u_captain&club_id=club_a&tab=all", headers=_headers("u_captain"))
    assert pulse_res.status_code == 200
    pdata = pulse_res.json()
    assert pdata["pinned_broadcast"]["id"] == bid

    newcomer_cards = [x for x in pdata["pulse_items"] if x["kind"] == "newcomer_icebreaker"]
    assert len(newcomer_cards) >= 1
    nc = newcomer_cards[0]
    assert nc["user_id"] == "u_newcomer"
    assert nc["age_group"] == "中坚组"
    assert "real_name" not in nc and "phone" not in nc and "date_of_birth" not in nc

    # Newcomer's activity respects hide_gps_route + hide_biometrics + critique='self'
    act_cards = [x for x in pdata["pulse_items"] if x["kind"] == "activity_checkin" and x["activity"]["user_id"] == "u_newcomer"]
    assert len(act_cards) == 1
    assert act_cards[0]["activity"]["is_gps_hidden"] is True
    assert act_cards[0]["activity"]["average_heartrate"] is None
    assert act_cards[0]["activity"]["is_critique_hidden"] is True

    # Member acknowledges broadcast & cheers newcomer
    ack = c.post(f"/api/community/broadcasts/{bid}/ack", headers=_headers("u_newcomer"), json={"user_id": "u_newcomer"})
    assert ack.status_code == 200
    assert ack.json()["viewer_acked"] is True
    assert ack.json()["ack_count"] == 2

    cheer = c.post(
        "/api/community/micro-cheer",
        headers=_headers("u_captain"),
        json={
            "sender_id": "u_captain",
            "target_type": "newcomer",
            "target_id": nc["item_id"],
            "recipient_id": "u_newcomer",
            "cheer_key": "welcome_pat",
            "club_id": "club_a",
        },
    )
    assert cheer.status_code == 200
    assert cheer.json()["active"] is True
    assert cheer.json()["counts_by_key"]["welcome_pat"] == 1

    # Most-frequently-followed club affinity ranking:
    # u_newcomer is in club_a and joins club_b; interacting more in club_b surfaces club_b automatically on home-pulse
    with sqlite3.connect(isolated_env["db_file"]) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent) VALUES ('cm_new_b', 'club_b', 'u_newcomer', 'member', 'active', '2026-11-01T00:00:00Z', 1)"
        )
        conn.commit()
    for cheer_k in ("steady_aerobic", "high_intensity"):
        c.post(
            "/api/community/micro-cheer",
            headers=_headers("u_newcomer"),
            json={
                "sender_id": "u_newcomer",
                "target_type": "activity",
                "target_id": "act_cap_1",
                "recipient_id": "u_coach_b",
                "cheer_key": cheer_k,
                "club_id": "club_b",
            },
        )
    auto_pulse = c.get("/api/community/home-pulse?viewer_uid=u_newcomer", headers=_headers("u_newcomer"))
    assert auto_pulse.status_code == 200
    ap = auto_pulse.json()
    assert ap["club_id"] == "club_b"
    assert ap["club_name"] == "张江破330特训营"
    assert ap["club_selection_reason"] == "常关注"
    assert ap["clubs"][0]["id"] == "club_b" and ap["clubs"][0]["is_most_frequent"] is True

    switched_pulse = c.get("/api/community/home-pulse?viewer_uid=u_newcomer&club_id=club_a", headers=_headers("u_newcomer"))
    assert switched_pulse.status_code == 200
    assert switched_pulse.json()["club_id"] == "club_a"
    assert switched_pulse.json()["club_selection_reason"] == "当前切换"


def test_phase2_buddy_discovery_privacy_follow_pk_and_purge(isolated_env):
    c = isolated_env["client"]

    # Org scope finds u_newcomer (org_and_clubs) & NOT u_hidden (none) & NOT u_outsider (not in org)
    res_org = c.get(
        "/api/community/discover?viewer_uid=u_captain&scope=org&gender=female&match_my_vdot=1&landmark=世纪公园",
        headers=_headers("u_captain"),
    )
    assert res_org.status_code == 200
    uids_org = [x["user_id"] for x in res_org.json()["candidates"]]
    assert "u_newcomer" in uids_org
    assert "u_hidden" not in uids_org
    assert "u_outsider" not in uids_org

    # Public scope finds u_outsider ('public') and NOT u_newcomer ('org_and_clubs')
    res_pub = c.get("/api/community/discover?viewer_uid=u_captain&scope=public&city=上海", headers=_headers("u_captain"))
    assert res_pub.status_code == 200
    uids_pub = [x["user_id"] for x in res_pub.json()["candidates"]]
    assert "u_outsider" in uids_pub
    assert "u_newcomer" not in uids_pub

    # One-way follow then reverse follow -> mutual buddy -> weekly PK
    f1 = c.post("/api/community/follow", headers=_headers("u_captain"), json={"follower_id": "u_captain", "target_uid": "u_newcomer"})
    assert f1.status_code == 200 and f1.json()["is_mutual_buddy"] is False
    f2 = c.post("/api/community/follow", headers=_headers("u_newcomer"), json={"follower_id": "u_newcomer", "target_uid": "u_captain"})
    assert f2.status_code == 200 and f2.json()["is_mutual_buddy"] is True

    pk = c.get("/api/community/buddies/u_newcomer/pk?viewer_uid=u_captain", headers=_headers("u_captain"))
    assert pk.status_code == 200
    assert pk.json()["is_mutual_buddy"] is True
    assert pk.json()["buddy"]["month_km"] == 120.0

    # Purge privacy resets search scopes to 'none' and removes follows
    purge = c.post("/api/profile/u_newcomer/purge-privacy", headers=_headers("u_newcomer"))
    assert purge.status_code == 200
    after_org = c.get("/api/community/discover?viewer_uid=u_captain&scope=org", headers=_headers("u_captain"))
    assert "u_newcomer" not in [x["user_id"] for x in after_org.json()["candidates"]]


def test_phase3_showcase_plaza_club_coach_and_photo_upload(isolated_env):
    c = isolated_env["client"]

    # Outsider cannot inspect org-bound club_b without invite_token
    r_forbid = c.get("/api/community/showcase/clubs/club_b?viewer_uid=u_outsider", headers=_headers("u_outsider"))
    assert r_forbid.status_code == 403

    # Coach updates Club B showcase & uploads Base64 photo
    up_sc = c.put(
        "/api/community/showcase/clubs/club_b",
        headers=_headers("u_coach_b"),
        json={
            "operator_uid": "u_coach_b",
            "slogan": "张江科学长跑 · 科学破330训练营",
            "style_tags": ["破330特训", "世纪公园晨跑"],
            "home_landmarks": ["世纪公园"],
            "schedule_summary": "周六 06:00 世纪公园 7 号门",
            "group_paces": [{"group": "A组", "pace": "4:20-4:40"}],
        },
    )
    assert up_sc.status_code == 200
    assert up_sc.json()["showcase"]["slogan"] == "张江科学长跑 · 科学破330训练营"

    b64_png = base64.b64encode(MINIMAL_PNG).decode("ascii")
    up_ph = c.post(
        "/api/community/showcase/photos/upload-base64",
        headers=_headers("u_coach_b"),
        json={
            "uploader_uid": "u_coach_b",
            "owner_type": "club",
            "owner_id": "club_b",
            "category": "group_run",
            "caption": "世纪公园 30km 拉练合影",
            "is_cover": True,
            "image_base64": b64_png,
            "ext": ".png",
        },
    )
    assert up_ph.status_code == 200
    photo_obj = up_ph.json()["photo"]
    isolated_env["created_files"].append(os.path.basename(photo_obj["photo_url"]))
    assert photo_obj["is_cover"] is True

    # Coach updates public resume & inspect anti-fake verified stamps
    up_coach = c.put(
        "/api/community/showcase/coaches/u_coach_b",
        headers=_headers("u_coach_b"),
        json={
            "operator_uid": "u_coach_b",
            "headline": "张江破330主教练 · AHA 急救持证",
            "specialty_tags": ["Canova 阻断训练", "全马配速稳控"],
            "certifications": [{"title": "中国田协中级教练", "verified": True}],
        },
    )
    assert up_coach.status_code == 200
    cdetail = up_coach.json()
    assert cdetail["verified_achievements"]["watch_verified"] is True
    assert "高驰" in cdetail["verified_achievements"]["watch_brands"]
    assert cdetail["verified_achievements"]["official_pacer_count"] == 1
    assert cdetail["verified_achievements"]["verified_pbs"]["marathon_pb"] == "3:05:00"

    # Org member can see both org showcase & coach in plaza
    plaza = c.get("/api/community/showcase/plaza?viewer_uid=u_newcomer&city=上海", headers=_headers("u_newcomer"))
    assert plaza.status_code == 200
    assert any(x["club_id"] == "club_b" and x["photo_count"] == 1 for x in plaza.json()["clubs"])
    assert any(x["user_id"] == "u_coach_b" and x["watch_verified"] for x in plaza.json()["coaches"])

    # Strict ownership permission checks:
    # Seed a non-owner coach in club_b and ensure super_admin (u_df65d9a588c9) + coach + other club owner CANNOT edit club_b or u_coach_b
    LocalStore.upsert_profile("u_coach_sub", {"display_name": "分团教练非团长", "city": "上海"})
    LocalStore.upsert_profile("u_df65d9a588c9", {"display_name": "平台超管", "city": "上海"})
    with sqlite3.connect(isolated_env["db_file"]) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent) VALUES ('cm_sub_b', 'club_b', 'u_coach_sub', 'coach', 'active', '2026-11-01T00:00:00Z', 1)"
        )
        conn.commit()

    # Only club_b owner (u_coach_b) gets can_edit=True on club_b showcase
    assert c.get("/api/community/showcase/clubs/club_b?viewer_uid=u_coach_b", headers=_headers("u_coach_b")).json()["can_edit"] is True
    for unauthorized_uid in ("u_coach_sub", "u_captain", "u_newcomer", "u_df65d9a588c9"):
        detail_u = c.get(f"/api/community/showcase/clubs/club_b?viewer_uid={unauthorized_uid}", headers=_headers(unauthorized_uid))
        assert detail_u.status_code == 200
        assert detail_u.json()["can_edit"] is False
        assert c.put(
            "/api/community/showcase/clubs/club_b",
            headers=_headers(unauthorized_uid),
            json={"operator_uid": unauthorized_uid, "slogan": "越权篡改"},
        ).status_code == 403
        assert c.post(
            "/api/community/showcase/photos/upload-base64",
            headers=_headers(unauthorized_uid),
            json={"uploader_uid": unauthorized_uid, "owner_type": "club", "owner_id": "club_b", "category": "group_run", "image_base64": b64_png, "ext": ".png"},
        ).status_code == 403
        assert c.patch(
            f"/api/community/showcase/photos/{photo_obj['id']}",
            headers=_headers(unauthorized_uid),
            json={"operator_uid": unauthorized_uid, "caption": "越权改图"},
        ).status_code == 403
        assert c.delete(
            f"/api/community/showcase/photos/{photo_obj['id']}?operator_uid={unauthorized_uid}",
            headers=_headers(unauthorized_uid),
        ).status_code == 403

    # Identity spoofing in JSON body with mismatched JWT must fail with 403
    assert c.put(
        "/api/community/showcase/clubs/club_b",
        headers=_headers("u_coach_sub"),
        json={"operator_uid": "u_coach_b", "slogan": "冒充团长UID"},
    ).status_code == 403

    # Coach showcase & coach photo wall: ONLY u_coach_b himself/herself can edit
    c_ph = c.post(
        "/api/community/showcase/photos/upload-base64",
        headers=_headers("u_coach_b"),
        json={"uploader_uid": "u_coach_b", "owner_type": "coach", "owner_id": "u_coach_b", "category": "certificate", "image_base64": b64_png, "ext": ".png"},
    )
    assert c_ph.status_code == 200
    coach_photo_id = c_ph.json()["photo"]["id"]
    isolated_env["created_files"].append(os.path.basename(c_ph.json()["photo"]["photo_url"]))

    assert c.get("/api/community/showcase/coaches/u_coach_b?viewer_uid=u_coach_b", headers=_headers("u_coach_b")).json()["can_edit"] is True
    for bad_coach_editor in ("u_coach_sub", "u_captain", "u_newcomer", "u_df65d9a588c9"):
        c_det = c.get(f"/api/community/showcase/coaches/u_coach_b?viewer_uid={bad_coach_editor}", headers=_headers(bad_coach_editor))
        assert c_det.status_code == 200
        assert c_det.json()["can_edit"] is False
        assert c.put(
            "/api/community/showcase/coaches/u_coach_b",
            headers=_headers(bad_coach_editor),
            json={"operator_uid": bad_coach_editor, "headline": "越权修改教练履历"},
        ).status_code == 403
        assert c.post(
            "/api/community/showcase/photos/upload-base64",
            headers=_headers(bad_coach_editor),
            json={"uploader_uid": bad_coach_editor, "owner_type": "coach", "owner_id": "u_coach_b", "category": "certificate", "image_base64": b64_png, "ext": ".png"},
        ).status_code == 403
        assert c.delete(
            f"/api/community/showcase/photos/{coach_photo_id}?operator_uid={bad_coach_editor}",
            headers=_headers(bad_coach_editor),
        ).status_code == 403

    # Regular member (not coach or owner anywhere) cannot open/edit own coach resume
    assert c.put(
        "/api/community/showcase/coaches/u_newcomer",
        headers=_headers("u_newcomer"),
        json={"operator_uid": "u_newcomer", "headline": "普通队员自封名帅"},
    ).status_code == 403


def test_phase4_non_exclusive_targeted_recruit_invite_and_funnel(isolated_env):
    c = isolated_env["client"]

    # Attach a club photo to showcase so invite card carries showcase preview
    b64_png = base64.b64encode(MINIMAL_PNG).decode("ascii")
    ph_res = c.post(
        "/api/community/showcase/photos/upload-base64",
        headers=_headers("u_coach_b"),
        json={"uploader_uid": "u_coach_b", "owner_type": "club", "owner_id": "club_b", "category": "group_run", "image_base64": b64_png},
    )
    isolated_env["created_files"].append(os.path.basename(ph_res.json()["photo"]["photo_url"]))

    # Non-exclusive rule: u_newcomer is ALREADY in club_a, yet MUST appear in club_b's candidate pool with other_clubs_count == 1
    cand_res = c.get(
        "/api/community/clubs/club_b/recruit-candidates?operator_uid=u_coach_b&pool=same_org&gender=female&monthly_km_min=100",
        headers=_headers("u_coach_b"),
    )
    assert cand_res.status_code == 200
    cands = cand_res.json()["candidates"]
    nc = next((x for x in cands if x["user_id"] == "u_newcomer"), None)
    assert nc is not None
    assert nc["other_clubs_count"] == 1
    assert all(x["user_id"] != "u_hidden" for x in cands)

    # Send targeted invite with preassigned_group = 'A组'
    inv_res = c.post(
        "/api/community/clubs/club_b/targeted-invites",
        headers=_headers("u_coach_b"),
        json={
            "inviter_uid": "u_coach_b",
            "target_user_ids": ["u_newcomer"],
            "preassigned_group": "A组",
            "reason_tag": "同属复旦戈大群 · 常跑世纪公园 · 月跑120km+",
            "attach_showcase": True,
        },
    )
    assert inv_res.status_code == 200
    token = inv_res.json()["invites"][0]["invite_token"]

    # Cooldown: u_newcomer is immediately excluded from club_b's recruit candidates for 30 days
    cand_after = c.get("/api/community/clubs/club_b/recruit-candidates?operator_uid=u_coach_b&pool=same_org", headers=_headers("u_coach_b"))
    assert all(x["user_id"] != "u_newcomer" for x in cand_after.json()["candidates"])

    # Targeted user sees pending invite & opens Golden Invite Landing Preview (embedded showcase)
    pend = c.get("/api/community/invites/my-pending?user_id=u_newcomer", headers=_headers("u_newcomer"))
    assert pend.status_code == 200 and len(pend.json()["invites"]) == 1
    pend_inv = pend.json()["invites"][0]
    assert "showcase_summary" in pend_inv
    assert "verified_stats" in pend_inv

    prev = c.get(f"/api/community/invites/{token}?viewer_uid=u_newcomer", headers=_headers("u_newcomer"))
    assert prev.status_code == 200
    assert prev.json()["invite"]["preassigned_group"] == "A组"
    assert prev.json()["showcase_preview"]["club"]["id"] == "club_b"
    assert "verified_stats" in prev.json()["invite"]
    assert "showcase_summary" in prev.json()

    # Club share-info and invite-info also synthesize club main info & images for the invite card
    share_res = c.get("/api/team/club_b/share-info?user_id=u_coach_b", headers=_headers("u_coach_b"))
    assert share_res.status_code == 200
    assert "showcase_summary" in share_res.json()
    assert "verified_stats" in share_res.json()

    inv_info_res = c.get("/api/team/club_b/invite-info?inviter_uid=u_coach_b&user_id=u_newcomer", headers=_headers("u_newcomer"))
    assert inv_info_res.status_code == 200
    assert inv_info_res.json()["one_click_join"] is True
    assert "verified_stats" in inv_info_res.json()["club"]

    # Zero-code accept: joins club_b with training_group='A组' AND preserves club_a membership!
    acc = c.post(
        f"/api/community/invites/{token}/respond",
        headers=_headers("u_newcomer"),
        json={"user_id": "u_newcomer", "action": "accept"},
    )
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"
    assert acc.json()["preassigned_group"] == "A组"

    my_clubs = c.get("/api/team/my-clubs/u_newcomer", headers=_headers("u_newcomer")).json()["clubs"]
    club_ids_joined = {x["id"] for x in my_clubs}
    assert {"club_a", "club_b"}.issubset(club_ids_joined)

    # Funnel metrics reflect sent=1, viewed=1, accepted=1
    funnel = c.get("/api/community/clubs/club_b/recruit-funnel?operator_uid=u_coach_b", headers=_headers("u_coach_b"))
    assert funnel.status_code == 200
    f = funnel.json()["funnel"]
    assert f["sent_count"] == 1
    assert f["viewed_count"] == 1
    assert f["accepted_count"] == 1


def test_showcase_plaza_prioritizes_decorated_and_active_clubs_and_coaches(isolated_env):
    """Decorated clubs/coaches rank first, then clubs with highest recent check-in & event activity."""
    c = isolated_env["client"]
    db_file = isolated_env["db_file"]
    today = get_beijing_today()
    recent_ts = (today - timedelta(days=2)).isoformat() + "T07:00:00+08:00"
    newest_ts = today.isoformat() + "T23:59:00+08:00"
    older_ts = (today - timedelta(days=60)).isoformat() + "T07:00:00+08:00"

    # Seed additional public clubs with deliberately inverted created_at timestamps:
    # - club_newest_empty: created newest, undecorated, 0 activity -> must rank LAST
    # - club_undec_hot: created oldest, undecorated, lots of check-ins + group event -> must lead undecorated clubs
    # - club_dec_quiet: decorated with photo, 0 recent activity -> ahead of undecorated, behind active decorated
    # - club_dec_hot: decorated with photo + slogan + active recent check-ins -> must rank #1
    with sqlite3.connect(db_file) as conn:
        cur = conn.cursor()
        for uid, name in [
            ("u_owner_hot", "热力团长"),
            ("u_owner_quiet", "静默团长"),
            ("u_owner_undec_hot", "活跃未装修团长"),
            ("u_owner_empty", "新空团长"),
            ("u_runner_extra", "打卡达人"),
        ]:
            cur.execute(
                "INSERT OR REPLACE INTO profiles (id, display_name, city, garmin_connected, created_at) VALUES (?, ?, '上海', 1, ?)",
                (uid, name, older_ts),
            )

        clubs_seed = [
            ("club_dec_hot", "精装活跃团", "HOTDEC", "u_owner_hot", older_ts),
            ("club_dec_quiet", "精装静默团", "QUTDEC", "u_owner_quiet", newest_ts),
            ("club_undec_hot", "未装超活跃团", "HOTUND", "u_owner_undec_hot", older_ts),
            ("club_newest_empty", "最新空跑团", "NEWEMP", "u_owner_empty", newest_ts),
        ]
        for cid, cname, code, owner, ts in clubs_seed:
            cur.execute(
                "INSERT OR REPLACE INTO clubs (id, org_id, name, city, invite_code, owner_id, join_mode, status, created_at) VALUES (?, NULL, ?, '上海', ?, ?, 'free', 'active', ?)",
                (cid, cname, code, owner, ts),
            )
            cur.execute(
                "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES (?, ?, ?, 'owner', 'active', ?)",
                (f"cm_{cid}_own", cid, owner, ts),
            )

        # Also make u_owner_hot an owner of club_newest_empty (newer) to verify primary_club picks club_dec_hot!
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_multi_hot', 'club_newest_empty', 'u_owner_hot', 'coach', 'active', ?)",
            (newest_ts,),
        )
        # Add extra runner to club_undec_hot & club_dec_hot
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_und_r', 'club_undec_hot', 'u_runner_extra', 'member', 'active', ?)",
            (older_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_dec_r', 'club_dec_hot', 'u_runner_extra', 'member', 'active', ?)",
            (older_ts,),
        )

        # Decorate club_dec_hot and club_dec_quiet (both with cover photo)
        for cid, slogan in [("club_dec_hot", "精装活跃宣言"), ("club_dec_quiet", "精装静默宣言")]:
            cur.execute(
                "INSERT OR REPLACE INTO club_showcase_profiles (club_id, slogan, hero_cover_url, is_published, updated_at) VALUES (?, ?, ?, 1, ?)",
                (cid, slogan, f"/api/showcase-photos/{cid}.jpg", recent_ts),
            )
            cur.execute(
                "INSERT OR REPLACE INTO showcase_photos (id, owner_type, owner_id, uploader_id, photo_url, category, is_cover, created_at) VALUES (?, 'club', ?, ?, ?, 'group_run', 1, ?)",
                (f"sp_{cid}", cid, "u_owner_hot", f"/api/showcase-photos/{cid}.jpg", recent_ts),
            )

        # Decorate u_owner_quiet as a coach with a personal photo & bio so decorated coach leads coach tab
        cur.execute(
            "INSERT OR REPLACE INTO coach_public_resumes (user_id, headline, bio_story, is_published, updated_at) VALUES ('u_owner_quiet', '资深科学训练教练', '执教十年', 1, ?)",
            (recent_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO showcase_photos (id, owner_type, owner_id, uploader_id, photo_url, category, is_cover, created_at) VALUES ('sp_coach_quiet', 'coach', 'u_owner_quiet', 'u_owner_quiet', '/api/showcase-photos/coach_q.jpg', 'certificate', 1, ?)",
            (recent_ts,),
        )

        # Seed recent 30d running check-ins:
        # u_owner_hot: 6 runs; u_runner_extra: 10 runs; u_owner_undec_hot: 8 runs
        for i in range(6):
            cur.execute(
                "INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, distance_meters, moving_time_seconds, start_time) VALUES (?, 'u_owner_hot', '晨跑', 'running', 10000, 3000, ?)",
                (f"act_oh_{i}", (today - timedelta(days=i + 1)).isoformat() + "T07:00:00+08:00"),
            )
        for i in range(10):
            cur.execute(
                "INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, distance_meters, moving_time_seconds, start_time) VALUES (?, 'u_runner_extra', '打卡', 'running', 12000, 3600, ?)",
                (f"act_re_{i}", (today - timedelta(days=i + 1)).isoformat() + "T07:00:00+08:00"),
            )
        for i in range(8):
            cur.execute(
                "INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, distance_meters, moving_time_seconds, start_time) VALUES (?, 'u_owner_undec_hot', '拉练', 'running', 15000, 4500, ?)",
                (f"act_uh_{i}", (today - timedelta(days=i + 1)).isoformat() + "T07:00:00+08:00"),
            )

        # Seed a recent group-run event with 2 participants for club_undec_hot
        cur.execute(
            "INSERT OR REPLACE INTO club_events (id, club_id, title, event_type, start_date, end_date, status, created_at) VALUES ('ev_und_1', 'club_undec_hot', '周日20km合练', 'group_run', ?, ?, 'archived', ?)",
            ((today - timedelta(days=3)).isoformat(), (today - timedelta(days=3)).isoformat(), recent_ts),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_event_participants (id, event_id, club_id, user_id, joined_at, status) VALUES ('ep_und_1', 'ev_und_1', 'club_undec_hot', 'u_owner_undec_hot', ?, 'joined')",
            (recent_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_event_participants (id, event_id, club_id, user_id, joined_at, status) VALUES ('ep_und_2', 'ev_und_1', 'club_undec_hot', 'u_runner_extra', ?, 'joined')",
            (recent_ts,),
        )
        conn.commit()

    res = c.get("/api/community/showcase/plaza?viewer_uid=u_stranger&city=上海", headers=_headers("u_stranger"))
    assert res.status_code == 200
    body = res.json()
    club_ids = [x["club_id"] for x in body["clubs"]]
    # Decorated clubs come first (active decorated > quiet decorated), then active undecorated > newest empty
    assert club_ids.index("club_dec_hot") < club_ids.index("club_dec_quiet")
    assert club_ids.index("club_dec_quiet") < club_ids.index("club_undec_hot")
    assert club_ids.index("club_undec_hot") < club_ids.index("club_newest_empty")

    by_cid = {x["club_id"]: x for x in body["clubs"]}
    assert by_cid["club_dec_hot"]["is_decorated"] is True
    assert by_cid["club_undec_hot"]["is_decorated"] is False
    assert by_cid["club_undec_hot"]["verified_stats"]["recent_30d_checkins"] == 18
    assert by_cid["club_undec_hot"]["verified_stats"]["recent_30d_events"] == 1
    assert by_cid["club_undec_hot"]["verified_stats"]["recent_30d_event_participants"] == 2

    # Coach tab: decorated coach first; next coach leading decorated/active club; inactive empty club coach last
    coaches = body["coaches"]
    coach_uids = [x["user_id"] for x in coaches]
    assert coach_uids[0] == "u_owner_quiet"
    assert coach_uids.index("u_owner_hot") < coach_uids.index("u_owner_empty")
    assert coach_uids.index("u_owner_undec_hot") < coach_uids.index("u_owner_empty")

    # Multi-club coach u_owner_hot picks decorated active club_dec_hot as primary_club (NOT newer club_newest_empty)
    by_uid = {x["user_id"]: x for x in coaches}
    assert by_uid["u_owner_hot"]["primary_club_id"] == "club_dec_hot"
    assert by_uid["u_owner_hot"]["primary_club_name"] == "精装活跃团"


def test_showcase_org_club_priority_and_free_runner_isolation(isolated_env):
    """Org clubs prioritize for org members; free runners never see org clubs anywhere (plaza, all-clubs, coach detail)."""
    c = isolated_env["client"]
    db_file = isolated_env["db_file"]
    today = get_beijing_today()
    recent_ts = (today - timedelta(days=1)).isoformat() + "T08:00:00+08:00"

    # Decorate free club `club_pub` heavily + make `u_pub_owner` ALSO coach `club_a` (org_fudan)
    # to test multi-scope coach isolation and primary_club scope priority.
    with sqlite3.connect(db_file) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO club_showcase_profiles (club_id, slogan, hero_cover_url, is_published, updated_at) VALUES ('club_pub', '超豪华自由跑团', '/api/showcase-photos/pub.jpg', 1, ?)",
            (recent_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO showcase_photos (id, owner_type, owner_id, uploader_id, photo_url, category, is_cover, created_at) VALUES ('sp_pub_cov', 'club', 'club_pub', 'u_pub_owner', '/api/showcase-photos/pub.jpg', 'group_run', 1, ?)",
            (recent_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_pub_in_org', 'club_a', 'u_pub_owner', 'coach', 'active', ?)",
            (recent_ts,),
        )
        # Decorate free-only coach u_outsider (make them owner of a free club `club_free_2`)
        cur.execute(
            "INSERT OR REPLACE INTO clubs (id, org_id, name, city, invite_code, owner_id, join_mode, status, created_at) VALUES ('club_free_2', NULL, '自由二团', '上海', 'FREE02', 'u_outsider', 'free', 'active', ?)",
            (recent_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_free2_own', 'club_free_2', 'u_outsider', 'owner', 'active', ?)",
            (recent_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO coach_public_resumes (user_id, headline, bio_story, is_published, updated_at) VALUES ('u_outsider', '自由团明星教练', '履历丰富', 1, ?)",
            (recent_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO showcase_photos (id, owner_type, owner_id, uploader_id, photo_url, category, is_cover, created_at) VALUES ('sp_out_coach', 'coach', 'u_outsider', 'u_outsider', '/api/showcase-photos/out.jpg', 'certificate', 1, ?)",
            (recent_ts,),
        )
        conn.commit()

    # 1) Free runner (u_outsider, not in org_fudan): MUST NOT see any org_fudan clubs anywhere!
    free_plaza = c.get("/api/community/showcase/plaza?viewer_uid=u_outsider&city=上海", headers=_headers("u_outsider"))
    assert free_plaza.status_code == 200
    fp = free_plaza.json()
    free_club_ids = [x["club_id"] for x in fp["clubs"]]
    assert "club_a" not in free_club_ids and "club_b" not in free_club_ids
    assert all(not x.get("org_id") for x in fp["clubs"])
    # Decorated free club `club_pub` comes before undecorated free club `club_free_2`
    assert free_club_ids.index("club_pub") < free_club_ids.index("club_free_2")
    # Org-only coaches (u_captain, u_coach_b) are invisible to free runner
    free_coach_uids = [x["user_id"] for x in fp["coaches"]]
    assert "u_captain" not in free_coach_uids and "u_coach_b" not in free_coach_uids
    # Multi-scope coach u_pub_owner shows free club_pub (never org club_a) to free runner
    pub_coach_card = next(x for x in fp["coaches"] if x["user_id"] == "u_pub_owner")
    assert pub_coach_card["primary_club_id"] == "club_pub"

    # Coach detail viewed by free runner MUST NOT leak org club `club_a`
    coach_det_free = c.get("/api/community/showcase/coaches/u_pub_owner?viewer_uid=u_outsider", headers=_headers("u_outsider"))
    assert coach_det_free.status_code == 200
    leaked_cids = [x["id"] for x in coach_det_free.json()["coaching_impact"]["coached_clubs"]]
    assert "club_a" not in leaked_cids
    assert "club_pub" in leaked_cids

    # /api/team/all-clubs for free runner also hides org clubs
    all_free = c.get("/api/team/all-clubs?user_id=u_outsider&city=上海", headers=_headers("u_outsider"))
    assert all_free.status_code == 200
    assert all(not x.get("org_id") for x in all_free.json()["clubs"])

    # Direct org club showcase detail blocked for free runner (403)
    assert c.get("/api/community/showcase/clubs/club_a?viewer_uid=u_outsider", headers=_headers("u_outsider")).status_code == 403

    # 2) Org member (u_newcomer, in org_fudan): MUST see org_fudan clubs FIRST, even ahead of decorated free club_pub!
    org_plaza = c.get("/api/community/showcase/plaza?viewer_uid=u_newcomer&city=上海", headers=_headers("u_newcomer"))
    assert org_plaza.status_code == 200
    op = org_plaza.json()
    org_club_ids = [x["club_id"] for x in op["clubs"]]
    assert org_club_ids.index("club_a") < org_club_ids.index("club_pub")
    assert org_club_ids.index("club_b") < org_club_ids.index("club_pub")
    assert op["clubs"][0]["in_viewer_org"] is True

    # Org coaches (u_captain, u_coach_b, u_pub_owner) MUST rank ahead of free-only decorated coach u_outsider!
    org_coach_uids = [x["user_id"] for x in op["coaches"]]
    assert org_coach_uids.index("u_captain") < org_coach_uids.index("u_outsider")
    assert org_coach_uids.index("u_coach_b") < org_coach_uids.index("u_outsider")
    assert org_coach_uids.index("u_pub_owner") < org_coach_uids.index("u_outsider")
    # For org member, multi-scope coach u_pub_owner highlights their shared org club `club_a`
    pub_coach_for_org = next(x for x in op["coaches"] if x["user_id"] == "u_pub_owner")
    assert pub_coach_for_org["primary_club_id"] == "club_a"

    # /api/team/all-clubs for org member also lists org clubs ahead of free clubs
    all_org = c.get("/api/team/all-clubs?user_id=u_newcomer&city=上海", headers=_headers("u_newcomer"))
    assert all_org.status_code == 200
    all_org_cids = [x["id"] for x in all_org.json()["clubs"]]
    assert all_org_cids.index("club_a") < all_org_cids.index("club_pub")
    assert all_org_cids.index("club_b") < all_org_cids.index("club_pub")


def test_buddy_discovery_uses_age_groups_without_numeric_brackets(isolated_env):
    """Buddy discovery displays and filters by 青年组/中坚组/壮年组/大师组 (never numeric 5-year brackets),
    while remaining backwards-compatible with legacy 50+/40-44 filter params."""
    c = isolated_env["client"]
    cur_year = get_beijing_today().year
    LocalStore.upsert_profile("u_masters_runner", {
        "display_name": "资深大师跑友", "gender": "male", "date_of_birth": f"{cur_year - 54}-03-10",
        "city": "上海", "allow_buddy_search_scope": "public", "allow_club_search_scope": "public",
    })
    LocalStore.upsert_profile("u_prime_runner", {
        "display_name": "壮年精英跑友", "gender": "female", "date_of_birth": f"{cur_year - 43}-06-15",
        "city": "上海", "allow_buddy_search_scope": "public", "allow_club_search_scope": "public",
    })
    LocalStore.upsert_profile("u_youth_runner", {
        "display_name": "青年新生代", "gender": "female", "date_of_birth": f"{cur_year - 25}-09-20",
        "city": "上海", "allow_buddy_search_scope": "public", "allow_club_search_scope": "public",
    })

    # Public discover lists canonical group labels only
    r_all = c.get("/api/community/discover?viewer_uid=u_captain&scope=public&match_my_vdot=0", headers=_headers("u_captain"))
    assert r_all.status_code == 200
    body = r_all.json()
    assert body["age_bracket_options"] == ["青年组", "中坚组", "壮年组", "大师组"]
    by_uid = {x["user_id"]: x for x in body["candidates"]}
    assert by_uid["u_masters_runner"]["age_group"] == "大师组"
    assert by_uid["u_prime_runner"]["age_group"] == "壮年组"
    assert by_uid["u_youth_runner"]["age_group"] == "青年组"

    # Filter by canonical group label '大师组'
    r_masters = c.get("/api/community/discover?viewer_uid=u_captain&scope=public&match_my_vdot=0&age_group=大师组", headers=_headers("u_captain"))
    assert r_masters.status_code == 200
    m_uids = {x["user_id"] for x in r_masters.json()["candidates"]}
    assert "u_masters_runner" in m_uids
    assert "u_prime_runner" not in m_uids and "u_youth_runner" not in m_uids

    # Backwards-compatible legacy filter param '50+' -> 大师组 and '40-44' -> 壮年组
    r_legacy_50 = c.get("/api/community/discover?viewer_uid=u_captain&scope=public&match_my_vdot=0&age_group=50%2B", headers=_headers("u_captain"))
    assert r_legacy_50.status_code == 200
    assert "u_masters_runner" in {x["user_id"] for x in r_legacy_50.json()["candidates"]}

    r_legacy_40 = c.get("/api/community/discover?viewer_uid=u_captain&scope=public&match_my_vdot=0&age_group=40-44", headers=_headers("u_captain"))
    assert r_legacy_40.status_code == 200
    assert "u_prime_runner" in {x["user_id"] for x in r_legacy_40.json()["candidates"]}


def test_showcase_club_and_coach_metadata_org_free_status_and_coached_clubs(isolated_env):
    """Club plaza/detail and coach detail must expose org vs free club type, join_mode, status, and is_member."""
    c = isolated_env["client"]
    db_file = isolated_env["db_file"]
    today = get_beijing_today()
    recent_ts = (today - timedelta(days=1)).isoformat() + "T08:00:00+08:00"

    # Make u_coach_b coach BOTH an org invite club (club_b), a free open club (club_pub), and a locked free club (club_locked)
    with sqlite3.connect(db_file) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO clubs (id, org_id, name, city, invite_code, owner_id, join_mode, status, created_at) VALUES ('club_locked', NULL, '历史锁定团', '上海', 'LOCK01', 'u_coach_b', 'free', 'locked', ?)",
            (recent_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_cb_pub', 'club_pub', 'u_coach_b', 'coach', 'active', ?)",
            (recent_ts,),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_cb_lock', 'club_locked', 'u_coach_b', 'owner', 'active', ?)",
            (recent_ts,),
        )
        conn.commit()

    # 1) Plaza returns is_org_club, org_name, join_mode, status, is_member for clubs and coached_clubs for coaches
    plaza = c.get("/api/community/showcase/plaza?viewer_uid=u_newcomer&city=上海", headers=_headers("u_newcomer"))
    assert plaza.status_code == 200
    p_clubs = {x["club_id"]: x for x in plaza.json()["clubs"]}
    assert p_clubs["club_b"]["is_org_club"] is True
    assert p_clubs["club_b"]["org_name"] == "复旦戈壁大群"
    assert p_clubs["club_b"]["join_mode"] == "invite"
    assert p_clubs["club_b"]["status"] == "active"
    assert p_clubs["club_b"]["is_member"] is False

    assert p_clubs["club_pub"]["is_org_club"] is False
    assert p_clubs["club_pub"]["org_name"] == ""
    assert p_clubs["club_pub"]["join_mode"] == "free"
    assert p_clubs["club_pub"]["status"] == "active"

    # 2) Club showcase detail exposes is_org_club, org_name, join_mode, status
    det = c.get("/api/community/showcase/clubs/club_b?viewer_uid=u_newcomer", headers=_headers("u_newcomer"))
    assert det.status_code == 200
    dc = det.json()["club"]
    assert dc["is_org_club"] is True
    assert dc["org_name"] == "复旦戈壁大群"
    assert dc["join_mode"] == "invite"
    assert dc["status"] == "active"

    # 3) Coach showcase detail lists all visible coached clubs with org/free/join_mode/status/is_member metadata
    cdet = c.get("/api/community/showcase/coaches/u_coach_b?viewer_uid=u_newcomer", headers=_headers("u_newcomer"))
    assert cdet.status_code == 200
    c_clubs = {x["id"]: x for x in cdet.json()["coaching_impact"]["coached_clubs"]}
    assert {"club_b", "club_pub", "club_locked"}.issubset(set(c_clubs.keys()))
    assert c_clubs["club_b"]["is_org_club"] is True
    assert c_clubs["club_b"]["org_name"] == "复旦戈壁大群"
    assert c_clubs["club_b"]["join_mode"] == "invite"
    assert c_clubs["club_b"]["status"] == "active"
    assert c_clubs["club_b"]["is_member"] is False

    assert c_clubs["club_pub"]["is_org_club"] is False
    assert c_clubs["club_pub"]["join_mode"] == "free"
    assert c_clubs["club_pub"]["status"] == "active"

    assert c_clubs["club_locked"]["is_org_club"] is False
    assert c_clubs["club_locked"]["status"] == "locked"


