import json
import os
import sqlite3
import time
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

import routers.coach as coach_mod
import routers.miniapp as miniapp_mod
import utils.local_store as ls_mod
from config import settings
from main import app
from utils.local_store import LocalStore, init_db


client = TestClient(app)

RICH_CRITIQUE = (
    "⚡【阈值节奏进阶】主课稳态心率 155bpm 超上限 3bpm，均心145bpm < 有氧上限150bpm"
    "（均心146bpm·约72%储备心率），较有氧上限留出8bpm安全余量，提速下均心稳守145bpm，"
    "均心下降6bpm（145bpm），组间心率回落 25bpm。"
    " 🌟【亮点】昨夜睡眠7.4h(85分)、HRV 58ms(稳居基线)、静息52bpm，当前状态良好。"
    " 💡 跑后及时拉伸，今晚务必早睡补足8h，保持7.5h+睡眠。"
    " ⚡ 明日按轻松跑 6km 衔接。"
)

RICH_SEGMENT = {
    "mode": "interval",
    "mode_label": "间歇节奏训练",
    "summary_title": "节奏推进",
    "concise_critique": "主课稳态心率 155bpm（均心146bpm·约72%储备心率），距离完成稳健。",
    "coach_advice": "保持跑姿放松，HRV 58ms(稳居基线)，今晚务必早睡补足8h。",
    "updated_ai_journal": RICH_CRITIQUE,
    "blocks": [{"index": 1, "role": "main", "label": "主课", "distance_km": 6.0}],
}


def _make_jwt(uid: str) -> str:
    return jwt.encode(
        {
            "sub": uid,
            "uid": uid,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_canova_critique_visibility.db"
    monkeypatch.setattr(ls_mod, "DB_PATH", str(db_file))
    monkeypatch.setattr(miniapp_mod, "DB_PATH", str(db_file))
    monkeypatch.setattr(coach_mod, "DB_PATH", str(db_file))
    init_db()
    yield db_file


def _seed_club_ecosystem(suffix: str = "1"):
    runner = f"u_vis_runner_{suffix}"
    peer_a = f"u_vis_peer_a_{suffix}"
    peer_b = f"u_vis_peer_b_{suffix}"
    peer_dual = f"u_vis_peer_dual_{suffix}"
    coach_a = f"u_vis_coach_a_{suffix}"
    mentor = f"u_vis_mentor_{suffix}"
    owner_a = f"u_vis_owner_a_{suffix}"
    admin_a = f"u_vis_admin_a_{suffix}"
    outsider = f"u_vis_outsider_{suffix}"
    super_admin = next(iter(LocalStore.SUPER_ADMIN_UIDS))

    club_a = f"club_vis_a_{suffix}"
    club_b = f"club_vis_b_{suffix}"
    club_deleted = f"club_vis_del_{suffix}"

    for uid, name in [
        (runner, "测试跑者"),
        (peer_a, "A团跑友"),
        (peer_b, "B团跑友"),
        (peer_dual, "双团跑友"),
        (coach_a, "A团教练"),
        (mentor, "1v1师傅"),
        (owner_a, "A团团长"),
        (admin_a, "A团管理员"),
        (outsider, "外团陌生人"),
        (super_admin, "超管"),
    ]:
        LocalStore.upsert_profile(uid, {"id": uid, "display_name": name})

    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO clubs (id, name, invite_code, owner_id, status) VALUES (?, ?, ?, ?, 'active')",
            (club_a, "飞羽先锋一团", f"CVA{suffix}", owner_a),
        )
        conn.execute(
            "INSERT OR REPLACE INTO clubs (id, name, invite_code, owner_id, status) VALUES (?, ?, ?, ?, 'active')",
            (club_b, "晨光夜跑二团", f"CVB{suffix}", peer_b),
        )
        conn.execute(
            "INSERT OR REPLACE INTO clubs (id, name, invite_code, owner_id, status) VALUES (?, ?, ?, ?, 'deleted')",
            (club_deleted, "已注销旧团", f"CVD{suffix}", outsider),
        )

        memberships = [
            (club_a, runner, "member", "active"),
            (club_b, runner, "member", "active"),
            (club_deleted, runner, "member", "active"),
            (club_a, peer_a, "member", "active"),
            (club_b, peer_b, "member", "active"),
            (club_a, peer_dual, "member", "active"),
            (club_b, peer_dual, "member", "active"),
            (club_a, coach_a, "coach", "active"),
            (club_a, owner_a, "owner", "active"),
            (club_a, admin_a, "admin", "active"),
            (club_deleted, outsider, "member", "active"),
        ]
        for cid, uid, role, status in memberships:
            conn.execute(
                """
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, privacy_consent)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (f"cm_{cid}_{uid}", cid, uid, role, status),
            )

        conn.execute(
            """
            INSERT OR REPLACE INTO mentor_relationships (id, mentor_id, mentee_id, status, created_at)
            VALUES (?, ?, ?, 'active', '2026-11-14T00:00:00')
            """,
            (f"mr_{mentor}_{runner}", mentor, runner),
        )
        conn.commit()

    today = LocalStore.get_beijing_today()
    act_id = f"coros_vis_{suffix}"
    start_time = f"{today.isoformat()}T07:30:00"
    LocalStore.upsert_activity(
        {
            "id": act_id,
            "user_id": runner,
            "name": "晨间阈值节奏跑",
            "sport_type": "Run",
            "start_time": start_time,
            "distance_meters": 12000.0,
            "moving_time_seconds": 3240,
            "elapsed_time_seconds": 3240,
            "avg_pace_str": "4:30",
            "average_heartrate": 155,
            "max_heartrate": 172,
            "trimp": 112.0,
            "elevation_gain_meters": 42.0,
            "ai_journal": RICH_CRITIQUE,
            "segment_analysis_json": json.dumps(RICH_SEGMENT, ensure_ascii=False),
            "gps_track_data": json.dumps(
                {
                    "points": [
                        {"latitude": 31.2304, "longitude": 121.4737},
                        {"latitude": 31.2320, "longitude": 121.4755},
                    ],
                    "elevation_profile": [
                        {"dist_km": 0.0, "elevation_m": 10.0, "hr": 140},
                        {"dist_km": 6.0, "elevation_m": 30.0, "hr": 160},
                    ],
                }
            ),
        },
        notify=False,
        reconcile_plan=False,
    )

    return {
        "runner": runner,
        "peer_a": peer_a,
        "peer_b": peer_b,
        "peer_dual": peer_dual,
        "coach_a": coach_a,
        "mentor": mentor,
        "owner_a": owner_a,
        "admin_a": admin_a,
        "outsider": outsider,
        "super_admin": super_admin,
        "club_a": club_a,
        "club_b": club_b,
        "club_deleted": club_deleted,
        "act_id": act_id,
        "year": today.year,
        "month": today.month,
    }


def _assert_viewer_sees_critique(
    *,
    viewer: str,
    env: dict,
    expect_visible: bool,
    club_id: str | None = None,
    expect_scrubbed: bool = False,
    check_track: bool = True,
):
    runner = env["runner"]
    act_id = env["act_id"]
    eff_club = club_id or env["club_a"]
    headers = {"Authorization": f"Bearer {_make_jwt(viewer)}"} if viewer else {}

    # 1. Club feed (note: team feed route is /api/team/{club_id}/feed?user_id=... with key 'feed')
    feed_res = client.get(
        f"/api/team/{eff_club}/feed?user_id={viewer}" if viewer else f"/api/team/{eff_club}/feed",
        headers=headers,
    )
    if feed_res.status_code == 200:
        feed_items = [a for a in feed_res.json().get("feed", []) if a["id"] == act_id]
        assert feed_items, f"Activity {act_id} missing from feed for viewer={viewer}, club={eff_club}"
        item = feed_items[0]
        if expect_visible:
            assert item["is_critique_hidden"] is False
            assert item["ai_journal"]
            if expect_scrubbed:
                assert "bpm" not in item["ai_journal"].lower()
                assert "hrv" not in item["ai_journal"].lower()
                assert "72%" not in item["ai_journal"]
                assert "85分" not in item["ai_journal"]
                assert "早睡补足8h" in item["ai_journal"]
            else:
                assert "145bpm" in item["ai_journal"]
                assert "HRV 58ms" in item["ai_journal"]
        else:
            assert item["is_critique_hidden"] is True
            assert item["ai_journal"] is None
    else:
        # Non-club-member (e.g. 1v1 mentor not in this club) gets 403 from validate_sub_club_access
        assert feed_res.status_code == 403

    # 2. Miniapp track endpoint (unscoped by club_id unless omitted for dual-club feed/share-card tests)
    if check_track:
        track_q = f"?viewer_uid={viewer}" if viewer else ""
        track_res = client.get(f"/api/miniapp/activities/{act_id}/track{track_q}", headers=headers)
        assert track_res.status_code == 200, track_res.text
        t_json = track_res.json()
        if expect_visible:
            assert t_json["is_critique_hidden"] is False
            assert t_json["activity"]["is_critique_hidden"] is False
            assert t_json["activity"]["ai_journal"]
            if not t_json["is_segment_hidden"]:
                assert t_json["segment_analysis"]["concise_critique"] is not None
                assert t_json["segment_analysis"]["coach_advice"] is not None
            if expect_scrubbed:
                assert "bpm" not in t_json["activity"]["ai_journal"].lower()
                assert "hrv" not in t_json["activity"]["ai_journal"].lower()
            else:
                assert "145bpm" in t_json["activity"]["ai_journal"]
        else:
            assert t_json["is_critique_hidden"] is True
            assert t_json["activity"]["is_critique_hidden"] is True
            assert t_json["activity"]["ai_journal"] is None
            if t_json.get("segment_analysis"):
                assert t_json["segment_analysis"].get("concise_critique") is None
                assert t_json["segment_analysis"].get("coach_advice") is None

    # 3. Share card endpoint
    with patch("utils.wechat.wechat_client.get_wxacode_by_path", return_value=b""), patch(
        "utils.wechat.wechat_client.get_wxacode_unlimit", return_value=b""
    ):
        sc_res = client.get(
            f"/api/miniapp/personal-share-card/{runner}?activity_id={act_id}&club_id={eff_club}",
            headers=headers,
        )
    assert sc_res.status_code == 200, sc_res.text
    sc_json = sc_res.json()
    if expect_visible:
        assert sc_json["is_critique_hidden"] is False
        assert len(sc_json["commentary_options"]) > 0
        assert sc_json["canova_commentary"]
        if expect_scrubbed:
            joined = sc_json["canova_commentary"] + " ".join(o["text"] for o in sc_json["commentary_options"])
            assert "bpm" not in joined.lower()
            assert "hrv" not in joined.lower()
            assert "85分" not in joined
    else:
        assert sc_json["is_critique_hidden"] is True
        assert sc_json["canova_commentary"] == ""
        assert sc_json["commentary_options"] == []


def test_default_self_visibility_and_legacy_null_normalization(isolated_db):
    env = _seed_club_ecosystem("self")
    runner = env["runner"]
    act_id = env["act_id"]

    # Simulate legacy SQLite NULL values and re-run init_db() normalization
    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            "UPDATE profiles SET canova_critique_visibility = NULL, canova_critique_club_ids = NULL WHERE id = ?",
            (runner,),
        )
        conn.commit()
    init_db()

    prof_after = LocalStore.get_profile(runner)
    assert prof_after["canova_critique_visibility"] == "self"
    assert prof_after["canova_critique_club_ids"] == []

    # Owner sees full critique across feed, dashboard, activities, month, track, share card, mentee detail
    _assert_viewer_sees_critique(viewer=runner, env=env, expect_visible=True, expect_scrubbed=False)
    for url in [
        f"/api/miniapp/dashboard/{runner}?viewer_uid={runner}",
        f"/api/miniapp/activities/{runner}?viewer_uid={runner}",
        f"/api/miniapp/activities/month/{runner}?year={env['year']}&month={env['month']}&viewer_uid={runner}",
    ]:
        r = client.get(url, headers={"Authorization": f"Bearer {_make_jwt(runner)}"})
        assert r.status_code == 200
        key = "recent_activities" if "dashboard" in url else "activities"
        match = [a for a in r.json()[key] if a["id"] == act_id][0]
        assert match["is_critique_hidden"] is False
        assert "145bpm" in match["ai_journal"]

    assert LocalStore.get_user_club_feed_summary(runner)["coach_critique_count"] >= 1

    # Everyone else is hidden under 'self' — peer, club owner, admin, certified coach, active 1v1 mentor, and SUPER_ADMIN
    for denied in [
        env["peer_a"],
        env["owner_a"],
        env["admin_a"],
        env["coach_a"],
        env["mentor"],
        env["super_admin"],
    ]:
        _assert_viewer_sees_critique(viewer=denied, env=env, expect_visible=False)
        for url in [
            f"/api/miniapp/dashboard/{runner}?viewer_uid={denied}",
            f"/api/miniapp/activities/{runner}?viewer_uid={denied}",
            f"/api/miniapp/activities/month/{runner}?year={env['year']}&month={env['month']}&viewer_uid={denied}",
        ]:
            r = client.get(url, headers={"Authorization": f"Bearer {_make_jwt(denied)}"})
            if denied == env["peer_a"] or LocalStore.can_view_specific_workout_records(denied, runner):
                assert r.status_code == 200
                key = "recent_activities" if "dashboard" in url else "activities"
                match = [a for a in r.json()[key] if a["id"] == act_id][0]
                assert match["is_critique_hidden"] is True
                assert match["ai_journal"] is None

    # Mentee detail hides critique under 'self' even for coach/mentor/super_admin
    mentee_detail = LocalStore.get_mentee_full_detail(env["mentor"], runner)
    assert mentee_detail["recent_activities"][0]["ai_journal"] == ""
    assert mentee_detail["recent_activities"][0]["is_critique_hidden"] is True

    # Feed summary for peer_a must not count runner's 'self'-only critique
    peer_summary = LocalStore.get_user_club_feed_summary(env["peer_a"])
    assert peer_summary["coach_critique_count"] == 0


def test_coach_mentor_visibility_strict_role_boundary(isolated_db):
    env = _seed_club_ecosystem("cm")
    runner = env["runner"]
    LocalStore.upsert_profile(runner, {"canova_critique_visibility": "coach_mentor"})

    # Self, certified coach (even when opening share card with another club_id!), and active 1v1 mentor are allowed
    _assert_viewer_sees_critique(viewer=runner, env=env, expect_visible=True)
    _assert_viewer_sees_critique(viewer=env["coach_a"], env=env, club_id=env["club_a"], expect_visible=True)
    _assert_viewer_sees_critique(viewer=env["coach_a"], env=env, club_id=env["club_b"], expect_visible=True)
    _assert_viewer_sees_critique(viewer=env["mentor"], env=env, club_id=env["club_a"], expect_visible=True)

    mentee_detail = LocalStore.get_mentee_full_detail(env["mentor"], runner)
    assert "145bpm" in mentee_detail["recent_activities"][0]["ai_journal"]
    assert mentee_detail["recent_activities"][0]["is_critique_hidden"] is False

    # Owner, admin, SUPER_ADMIN, and regular peers are strictly denied
    for denied in [env["owner_a"], env["admin_a"], env["super_admin"], env["peer_a"]]:
        _assert_viewer_sees_critique(viewer=denied, env=env, expect_visible=False)


def test_selected_clubs_visibility_scoping(isolated_db):
    env = _seed_club_ecosystem("sel")
    runner = env["runner"]
    LocalStore.upsert_profile(
        runner,
        {
            "canova_critique_visibility": "selected_clubs",
            "canova_critique_club_ids": [env["club_a"]],
        },
    )

    # Member of whitelisted club_a sees critique on club_a feed / track / share card
    _assert_viewer_sees_critique(viewer=env["peer_a"], env=env, club_id=env["club_a"], expect_visible=True)
    assert LocalStore.get_user_club_feed_summary(env["peer_a"])["coach_critique_count"] == 1

    # Member of non-whitelisted club_b is denied on track, share card, and club_b feed
    _assert_viewer_sees_critique(viewer=env["peer_b"], env=env, club_id=env["club_b"], expect_visible=False)

    # Dual-club peer sees critique inside club_a context, NOT inside club_b feed/share-card context
    _assert_viewer_sees_critique(viewer=env["peer_dual"], env=env, club_id=env["club_a"], expect_visible=True)
    _assert_viewer_sees_critique(
        viewer=env["peer_dual"], env=env, club_id=env["club_b"], expect_visible=False, check_track=False
    )

    # Certified coach and active mentor still retain access
    _assert_viewer_sees_critique(viewer=env["coach_a"], env=env, club_id=env["club_a"], expect_visible=True)
    _assert_viewer_sees_critique(viewer=env["mentor"], env=env, club_id=env["club_b"], expect_visible=True)


def test_all_clubs_visibility_and_inactive_or_deleted_club_exclusion(isolated_db):
    env = _seed_club_ecosystem("all")
    runner = env["runner"]
    LocalStore.upsert_profile(runner, {"canova_critique_visibility": "all_clubs"})

    # Active members of club_a and club_b see critique
    _assert_viewer_sees_critique(viewer=env["peer_a"], env=env, club_id=env["club_a"], expect_visible=True)
    _assert_viewer_sees_critique(viewer=env["peer_b"], env=env, club_id=env["club_b"], expect_visible=True)

    # User sharing only a deleted club cannot see critique
    assert LocalStore.can_view_canova_critique(env["outsider"], runner) is False

    # Pending/inactive membership in club_a is excluded even under 'all_clubs'
    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            "UPDATE club_memberships SET status = 'pending' WHERE club_id = ? AND user_id = ?",
            (env["club_a"], env["peer_a"]),
        )
        conn.commit()
    assert LocalStore.can_view_canova_critique(env["peer_a"], runner, club_id=env["club_a"]) is False


def test_linked_biometrics_scrubbing_and_profile_api_roundtrip(isolated_db):
    env = _seed_club_ecosystem("bio")
    runner = env["runner"]
    act_id = env["act_id"]

    # Profile API roundtrip & normalization of invalid tier
    put_bad = client.put(
        f"/api/profile/{runner}",
        json={"canova_critique_visibility": "everyone", "canova_critique_club_ids": [env["club_a"], " ", env["club_a"]]},
        headers={"Authorization": f"Bearer {_make_jwt(runner)}"},
    )
    assert put_bad.status_code == 200
    get_bad = client.get(f"/api/profile/{runner}", headers={"Authorization": f"Bearer {_make_jwt(runner)}"})
    assert get_bad.status_code == 200
    assert get_bad.json()["profile"]["canova_critique_visibility"] == "self"
    assert get_bad.json()["profile"]["canova_critique_club_ids"] == [env["club_a"]]
    assert any(c["id"] == env["club_a"] for c in get_bad.json()["clubs"])

    # Enable all_clubs + hide_biometrics=True via Profile API
    put_ok = client.put(
        f"/api/profile/{runner}",
        json={
            "canova_critique_visibility": "all_clubs",
            "canova_critique_club_ids": [env["club_a"]],
            "hide_biometrics": True,
        },
        headers={"Authorization": f"Bearer {_make_jwt(runner)}"},
    )
    assert put_ok.status_code == 200

    # Also validate direct unit sanitizer edge cases (adjacent Chinese+HRV, ranges, generic sleep preserved)
    sample = (
        "提速下均心稳守145bpm，中文HRV62ms(正常)，心率区间 140-155 bpm，"
        "昨夜睡眠7.4h(85分)，今晚务必早睡补足8h，保持7.5h+睡眠。"
    )
    scrubbed = LocalStore.sanitize_canova_critique_biometrics(sample)
    assert "提速下节奏稳控" in scrubbed
    assert "bpm" not in scrubbed.lower()
    assert "hrv" not in scrubbed.lower()
    assert "62ms" not in scrubbed
    assert "7.4h" not in scrubbed
    assert "85分" not in scrubbed
    assert "早睡补足8h" in scrubbed
    assert "7.5h+睡眠" in scrubbed

    # Regular club peer gets is_critique_hidden=False with biometrics scrubbed across feed, dashboard, activities, track, share card
    _assert_viewer_sees_critique(viewer=env["peer_a"], env=env, club_id=env["club_a"], expect_visible=True, expect_scrubbed=True)

    for url in [
        f"/api/miniapp/dashboard/{runner}?viewer_uid={env['peer_a']}",
        f"/api/miniapp/activities/{runner}?viewer_uid={env['peer_a']}",
        f"/api/miniapp/activities/month/{runner}?year={env['year']}&month={env['month']}&viewer_uid={env['peer_a']}",
    ]:
        r = client.get(url, headers={"Authorization": f"Bearer {_make_jwt(env['peer_a'])}"})
        assert r.status_code == 200
        key = "recent_activities" if "dashboard" in url else "activities"
        item = [a for a in r.json()[key] if a["id"] == act_id][0]
        assert item["is_critique_hidden"] is False
        assert item["average_heartrate"] is None
        assert "bpm" not in item["ai_journal"].lower()
        assert "hrv" not in item["ai_journal"].lower()
        assert "早睡补足8h" in item["ai_journal"]

    # Self, strict coach, and active 1v1 mentor receive unredacted critiques
    for privileged in [runner, env["coach_a"], env["mentor"]]:
        _assert_viewer_sees_critique(viewer=privileged, env=env, club_id=env["club_a"], expect_visible=True, expect_scrubbed=False)

    # Underlying SQLite ai_journal remains completely unredacted
    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        raw_db_journal = conn.execute("SELECT ai_journal FROM activities WHERE id = ?", (act_id,)).fetchone()[0]
    assert raw_db_journal == RICH_CRITIQUE
