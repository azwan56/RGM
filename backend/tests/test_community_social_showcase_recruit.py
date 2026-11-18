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
    assert nc["age_group"] in ("30-34", "35-39")
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

    prev = c.get(f"/api/community/invites/{token}?viewer_uid=u_newcomer", headers=_headers("u_newcomer"))
    assert prev.status_code == 200
    assert prev.json()["invite"]["preassigned_group"] == "A组"
    assert prev.json()["showcase_preview"]["club"]["id"] == "club_b"

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
