import json
import sqlite3
import time

import jwt
import pytest
from fastapi.testclient import TestClient

import routers.coach as coach_mod
import routers.miniapp as miniapp_mod
import utils.local_store as ls_mod
from config import settings
from main import app
from utils.captain_cheer import enrich_activities_with_captain_cheer, generate_activity_captain_cheer
from utils.local_store import LocalStore, init_db


client = TestClient(app)


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
    db_file = tmp_path / "test_captain_cheer.db"
    monkeypatch.setattr(ls_mod, "DB_PATH", str(db_file))
    monkeypatch.setattr(miniapp_mod, "DB_PATH", str(db_file))
    monkeypatch.setattr(coach_mod, "DB_PATH", str(db_file))
    init_db()
    yield db_file


def _seed_club(
    club_id: str,
    club_name: str,
    owner_id: str,
    members: list[tuple[str, str]],
    *,
    status: str = "active",
    invite_code: str,
):
    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO clubs (id, name, invite_code, owner_id, status) VALUES (?, ?, ?, ?, ?)",
            (club_id, club_name, invite_code, owner_id, status),
        )
        for uid, role in members:
            conn.execute(
                """
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, privacy_consent)
                VALUES (?, ?, ?, ?, 'active', 1)
                """,
                (f"cm_{club_id}_{uid}", club_id, uid, role),
            )
        conn.commit()


def _seed_run(
    act_id: str,
    user_id: str,
    *,
    name: str = "晨间有氧跑",
    sport_type: str = "Run",
    start_time: str,
    distance_meters: float = 10000.0,
    moving_time_seconds: int = 3000,
    elevation_gain_meters: float = 35.0,
    average_heartrate: float = 152.0,
    trimp: float = 95.0,
    ai_journal: str = "Canova私密复盘：均心152bpm HRV 54ms",
):
    LocalStore.upsert_activity(
        {
            "id": act_id,
            "user_id": user_id,
            "name": name,
            "sport_type": sport_type,
            "start_time": start_time,
            "distance_meters": distance_meters,
            "moving_time_seconds": moving_time_seconds,
            "elapsed_time_seconds": moving_time_seconds,
            "avg_pace_str": "5:00",
            "average_heartrate": average_heartrate,
            "max_heartrate": 176,
            "trimp": trimp,
            "elevation_gain_meters": elevation_gain_meters,
            "ai_journal": ai_journal,
            "gps_track_data": json.dumps(
                {
                    "points": [
                        {"latitude": 31.2304, "longitude": 121.4737},
                        {"latitude": 31.2320, "longitude": 121.4755},
                    ],
                    "elevation_profile": [
                        {"dist_km": 0.0, "elevation_m": 10.0, "hr": 140},
                        {"dist_km": 5.0, "elevation_m": 25.0, "hr": 158},
                    ],
                }
            ),
        },
        notify=False,
        reconcile_plan=False,
    )


def test_public_visibility_across_all_surfaces_under_strict_privacy(isolated_db):
    runner = "u_cc_runner_1"
    peer = "u_cc_peer_1"
    mentor = "u_cc_mentor_1"
    owner = "u_cc_owner_1"
    club_id = "club_cc_main"

    LocalStore.upsert_profile(
        runner,
        {
            "id": runner,
            "display_name": "阿哲",
            "gender": "male",
            "date_of_birth": "1992-06-15",
            "years_running": 4,
            "canova_critique_visibility": "self",
            "hide_biometrics": True,
            "hide_gps_route": True,
        },
    )
    LocalStore.upsert_profile(peer, {"id": peer, "display_name": "同团跑友"})
    LocalStore.upsert_profile(mentor, {"id": mentor, "display_name": "1v1师傅"})
    LocalStore.upsert_profile(owner, {"id": owner, "display_name": "老周"})

    _seed_club(
        club_id,
        "滨江晨跑团",
        owner,
        [(owner, "owner"), (runner, "member"), (peer, "member")],
        invite_code="CCMAIN1",
    )

    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO mentor_relationships (id, mentor_id, mentee_id, status, created_at)
            VALUES (?, ?, ?, 'active', '2026-11-14T00:00:00')
            """,
            (f"mr_{mentor}_{runner}", mentor, runner),
        )
        conn.commit()

    today = LocalStore.get_beijing_today()
    act_id = "act_cc_priv_1"
    _seed_run(
        act_id,
        runner,
        start_time=f"{today.isoformat()}T07:00:00",
        distance_meters=12000.0,
    )

    # 1. Club feed (get_club_recent_activities & HTTP /api/team/{club_id}/feed)
    club_acts, _ = LocalStore.get_club_recent_activities(club_id, current_uid=peer, limit=10)
    row = next(a for a in club_acts if a["id"] == act_id)
    assert row["is_critique_hidden"] is True
    assert row["ai_journal"] is None
    assert row["is_gps_hidden"] is True
    assert row["captain_cheer"]
    assert row["captain_cheer_meta"]["captain_title"] == "滨江晨跑团 · 老周团长"

    feed_res = client.get(
        f"/api/team/{club_id}/feed?user_id={peer}",
        headers={"Authorization": f"Bearer {_make_jwt(peer)}"},
    )
    assert feed_res.status_code == 200
    feed_row = next(a for a in feed_res.json()["feed"] if a["id"] == act_id)
    assert feed_row["is_critique_hidden"] is True
    assert feed_row["captain_cheer"] == row["captain_cheer"]

    # 2. MiniApp Dashboard, Activities, Month Activities
    dash_res = client.get(f"/api/miniapp/dashboard/{runner}?viewer_uid={peer}")
    assert dash_res.status_code == 200
    dash_json = dash_res.json()
    dash_item = next(a for a in dash_json["recent_activities"] if a["id"] == act_id)
    assert dash_item["is_critique_hidden"] is True
    assert dash_item["captain_cheer"]
    month_dash_item = next(a for a in dash_json["current_month_activities"] if a["id"] == act_id)
    assert month_dash_item["captain_cheer"] == dash_item["captain_cheer"]

    acts_res = client.get(f"/api/miniapp/activities/{runner}?viewer_uid={peer}")
    assert acts_res.status_code == 200
    acts_item = next(a for a in acts_res.json()["activities"] if a["id"] == act_id)
    assert acts_item["captain_cheer"]

    month_res = client.get(
        f"/api/miniapp/activities/month/{runner}?year={today.year}&month={today.month}&viewer_uid={peer}"
    )
    assert month_res.status_code == 200
    month_item = next(a for a in month_res.json()["activities"] if a["id"] == act_id)
    assert month_item["captain_cheer"]

    # 3. Track detail endpoint (both GPS hidden for peer and GPS open for owner/runner)
    track_peer = client.get(f"/api/miniapp/activities/{act_id}/track?viewer_uid={peer}&club_id={club_id}")
    assert track_peer.status_code == 200
    tp_json = track_peer.json()
    assert tp_json["is_gps_hidden"] is True
    assert tp_json["captain_cheer"] == row["captain_cheer"]
    assert tp_json["activity"]["captain_cheer"] == row["captain_cheer"]

    track_self = client.get(f"/api/miniapp/activities/{act_id}/track?viewer_uid={runner}&club_id={club_id}")
    assert track_self.status_code == 200
    ts_json = track_self.json()
    assert ts_json["is_gps_hidden"] is False
    assert ts_json["captain_cheer"] == row["captain_cheer"]

    # 4. Moments Share Card preserves Canova hidden contract while exposing captain_cheer
    share_peer = client.get(
        f"/api/miniapp/personal-share-card/{runner}?activity_id={act_id}&viewer_uid={peer}"
    )
    assert share_peer.status_code == 200
    sp_json = share_peer.json()
    assert sp_json["is_critique_hidden"] is True
    assert sp_json["canova_commentary"] == ""
    assert sp_json["commentary_options"] == []
    assert sp_json["captain_cheer"]
    assert sp_json["captain_cheer_meta"]["captain_title"] == "滨江晨跑团 · 老周团长"

    # 5. Mentor Cockpit full detail
    mentee_detail = LocalStore.get_mentee_full_detail(mentor, runner)
    m_item = next(a for a in mentee_detail["recent_activities"] if a["id"] == act_id)
    assert m_item["captain_cheer"]


def test_hard_privacy_red_lines_never_leak_sensitive_data(isolated_db):
    runner = "u_cc_priv_guard"
    owner = "u_cc_priv_cap"
    club_id = "club_cc_priv"
    today = LocalStore.get_beijing_today()

    LocalStore.upsert_profile(
        runner,
        {
            "id": runner,
            "display_name": "小光",
            "real_name": "张真名",
            "phone": "13800138000",
            "email": "secret@test.com",
            "id_card": "310101197005201234",
            "gender": "male",
            "date_of_birth": "1970-05-20",
            "years_running": 6,
            "resting_heart_rate": 48,
            "max_heart_rate": 185,
            "canova_critique_visibility": "self",
            "hide_biometrics": True,
        },
    )
    LocalStore.upsert_profile(owner, {"id": owner, "display_name": "周团长"})
    _seed_club(club_id, "森林晨曦团", owner, [(owner, "owner"), (runner, "member")], invite_code="CCPRIV")

    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO daily_health
            (id, user_id, date, resting_heart_rate, vo2_max, sleep_duration_seconds,
             sleep_duration_hours, sleep_score, hrv_status, hrv_weekly_avg, hrv_last_night_avg)
            VALUES (?, ?, ?, 52, 54.0, 18720, 5.2, 62, 'low', 55.0, 38.0)
            """,
            (f"dh_{runner}_{today.isoformat()}", runner, today.isoformat()),
        )
        conn.commit()

    act_id = "act_cc_redline"
    _seed_run(
        act_id,
        runner,
        start_time=f"{today.isoformat()}T06:45:00",
        distance_meters=21100.0,
        average_heartrate=162.0,
        trimp=145.0,
    )

    cheer, cheer_meta = generate_activity_captain_cheer(
        {
            "id": act_id,
            "user_id": runner,
            "name": "早课长跑",
            "sport_type": "Run",
            "start_time": f"{today.isoformat()}T06:45:00",
            "distance_meters": 21100.0,
            "moving_time_seconds": 6200,
            "trimp": 145.0,
        },
        club_id=club_id,
    )
    cheer = cheer or ""
    assert cheer
    assert "小光" in cheer
    assert cheer_meta["captain_title"] == "森林晨曦团 · 周团长"

    forbidden_tokens = [
        "张真名",
        "13800138000",
        "secret@test.com",
        "secret",
        "310101",
        "1970",
        "岁",
        "bpm",
        "HRV",
        "hrv",
        "心率",
        "静息",
        "睡眠",
        "CTL",
        "ATL",
        "TSB",
        "TRIMP",
        "VDOT",
        "vo2",
    ]
    lower_cheer = cheer.lower()
    for tok in forbidden_tokens:
        assert tok.lower() not in lower_cheer, f"Forbidden token '{tok}' leaked in cheer: {cheer}"


def test_scenarios_plan_group_trail_race_and_captain_self(isolated_db):
    today = LocalStore.get_beijing_today()
    today_iso = today.isoformat()
    owner = "u_cc_sc_owner"
    runner = "u_cc_sc_runner"
    club_id = "club_cc_scenarios"

    LocalStore.upsert_profile(owner, {"id": owner, "display_name": "陈队"})
    LocalStore.upsert_profile(
        runner,
        {"id": runner, "display_name": "林林", "gender": "female", "date_of_birth": "1995-04-01", "years_running": 3},
    )
    _seed_club(club_id, "海岸线跑团", owner, [(owner, "owner"), (runner, "member")], invite_code="CCSCEN")

    # 1. Completed 20km scheduled plan
    sched = {
        "weeks": [
            {
                "week": 1,
                "days": [
                    {"date": today_iso, "title": "马拉松专项课", "distance_km": 20, "workout_type": "Long"}
                ],
            }
        ]
    }
    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO training_plans
            (id, user_id, title, goal_type, status, schedule_data, creator_id, created_at, updated_at)
            VALUES (?, ?, '备赛计划', 'marathon', 'active', ?, ?, ?, ?)
            """,
            ("tp_cc_1", runner, json.dumps(sched, ensure_ascii=False), runner, today_iso, today_iso),
        )
        conn.commit()

    plan_act = {
        "id": "act_cc_plan_20k",
        "user_id": runner,
        "name": "周日20K专项",
        "sport_type": "Run",
        "start_time": f"{today_iso}T07:00:00",
        "distance_meters": 20100.0,
        "moving_time_seconds": 6100,
    }
    plan_cheer, plan_meta = generate_activity_captain_cheer(plan_act, club_id=club_id)
    assert plan_meta["scenario"] == "plan_completed"
    assert "课表" in plan_cheer
    assert "20公里" in plan_cheer
    assert "林林" in plan_cheer
    assert "加油" in plan_cheer

    # 2. Club Group Run check-in (priority higher than daily plan when linked)
    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO club_events
            (id, club_id, title, event_type, start_date, end_date, meet_time, created_at)
            VALUES (?, ?, '周末奥森合练课', 'lsd_group_run', ?, ?, '07:00', ?)
            """,
            ("ev_cc_1", club_id, today_iso, today_iso, today_iso),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO club_event_participants
            (id, event_id, club_id, user_id, joined_at, status, activity_id)
            VALUES (?, 'ev_cc_1', ?, ?, ?, 'joined', ?)
            """,
            ("cep_cc_1", club_id, runner, today_iso, "act_cc_group_1"),
        )
        conn.commit()

    grp_cheer, grp_meta = generate_activity_captain_cheer(
        {
            "id": "act_cc_group_1",
            "user_id": runner,
            "name": "奥森合练",
            "sport_type": "Run",
            "start_time": f"{today_iso}T07:05:00",
            "distance_meters": 15000.0,
            "moving_time_seconds": 4500,
        },
        club_id=club_id,
    )
    assert grp_meta["scenario"] == "group_run"
    assert "合练" in grp_cheer
    assert "休息" in grp_cheer

    # Remove plan & group links on another user for trail, race, and captain-self tests
    trail_runner = "u_cc_trail"
    LocalStore.upsert_profile(trail_runner, {"id": trail_runner, "display_name": "山野侠"})
    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, privacy_consent)
            VALUES (?, ?, ?, 'member', 'active', 1)
            """,
            (f"cm_{club_id}_{trail_runner}", club_id, trail_runner),
        )
        conn.commit()

    trail_cheer, trail_meta = generate_activity_captain_cheer(
        {
            "id": "act_cc_trail_1",
            "user_id": trail_runner,
            "name": "九溪越野拉练",
            "sport_type": "TrailRun",
            "start_time": f"{today_iso}T06:30:00",
            "distance_meters": 18500.0,
            "moving_time_seconds": 7800,
            "elevation_gain_meters": 620.0,
        },
        club_id=club_id,
    )
    assert trail_meta["scenario"] == "trail"
    assert "620米" in trail_cheer

    # Race takes top precedence on race day
    with sqlite3.connect(ls_mod.DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO race_plans (id, user_id, name, race_type, race_date, status, created_at)
            VALUES (?, ?, '2026杭州马拉松', 'full_marathon', ?, 'upcoming', ?)
            """,
            ("rp_cc_1", trail_runner, today_iso, today_iso),
        )
        conn.commit()
    race_day_str = today_iso
    race_cheer, race_meta = generate_activity_captain_cheer(
        {
            "id": "act_cc_race_1",
            "user_id": trail_runner,
            "name": "杭州马拉松正式赛",
            "sport_type": "Run",
            "start_time": f"{race_day_str}T07:30:00",
            "distance_meters": 42195.0,
            "moving_time_seconds": 12600,
        },
        club_id=club_id,
    )
    assert race_meta["scenario"] == "race"
    assert "杭州马" in race_cheer
    assert "42.2公里" in race_cheer

    # Captain self-run uses leader / first-person tone instead of cheering herself as a third-party member
    cap_cheer, cap_meta = generate_activity_captain_cheer(
        {
            "id": "act_cc_cap_self",
            "user_id": owner,
            "name": "清晨打卡",
            "sport_type": "Run",
            "start_time": f"{today_iso}T06:00:00",
            "distance_meters": 8000.0,
            "moving_time_seconds": 2400,
        },
        club_id=club_id,
    )
    assert cap_cheer
    assert "陈队加油" not in cap_cheer
    assert "陈队" not in cap_cheer
    assert cap_meta["captain_title"] == "海岸线跑团 · 陈队团长"


def test_persona_and_state_adaptation(isolated_db):
    today = LocalStore.get_beijing_today()
    today_iso = today.isoformat()
    owner = "u_cc_p_owner"
    masters_woman = "u_cc_masters_f"
    youth_man = "u_cc_youth_m"
    club_id = "club_cc_persona"

    LocalStore.upsert_profile(owner, {"id": owner, "display_name": "张团长"})
    LocalStore.upsert_profile(
        masters_woman,
        {
            "id": masters_woman,
            "display_name": "梅姐",
            "gender": "female",
            "date_of_birth": "1972-03-10",
            "years_running": 8,
        },
    )
    LocalStore.upsert_profile(
        youth_man,
        {
            "id": youth_man,
            "display_name": "小凯",
            "gender": "male",
            "date_of_birth": "2002-08-15",
            "years_running": 0.5,
        },
    )
    _seed_club(
        club_id,
        "天坛常青团",
        owner,
        [(owner, "owner"), (masters_woman, "member"), (youth_man, "member")],
        invite_code="CCPERS",
    )

    # Give masters_woman high monthly volume (>= 100km) across earlier runs this month
    first_of_month = today.replace(day=1).isoformat()
    _seed_run(
        "act_cc_hist_1",
        masters_woman,
        start_time=f"{first_of_month}T06:30:00",
        distance_meters=90000.0,
        trimp=220.0,
    )

    acts = [
        {
            "id": "act_cc_mf_today",
            "user_id": masters_woman,
            "name": "日常稳健跑",
            "sport_type": "Run",
            "start_time": f"{today_iso}T07:00:00",
            "distance_meters": 14000.0,
            "moving_time_seconds": 4500,
        },
        {
            "id": "act_cc_ym_today",
            "user_id": youth_man,
            "name": "日常打卡",
            "sport_type": "Run",
            "start_time": f"{today_iso}T07:00:00",
            "distance_meters": 8000.0,
            "moving_time_seconds": 2500,
        },
    ]
    enrich_activities_with_captain_cheer(acts, club_id=club_id)
    mf_cheer = acts[0]["captain_cheer"]
    ym_cheer = acts[1]["captain_cheer"]

    assert mf_cheer != ym_cheer
    assert "梅姐" in mf_cheer
    assert "前辈" in mf_cheer
    assert "小凯" in ym_cheer
    assert any(tok in ym_cheer for tok in ("朝气", "新手", "成长刻度", "冲劲"))
    assert "岁" not in mf_cheer and "1972" not in mf_cheer
    assert "岁" not in ym_cheer and "2002" not in ym_cheer


def test_multi_club_attribution_and_solo_runner_exclusion(isolated_db):
    today_iso = LocalStore.get_beijing_today().isoformat()
    owner_a = "u_cc_own_a"
    owner_b = "u_cc_own_b"
    dual_runner = "u_cc_dual"
    solo_runner = "u_cc_solo"
    deleted_only_runner = "u_cc_del_only"

    LocalStore.upsert_profile(owner_a, {"id": owner_a, "display_name": "陈团长"})
    LocalStore.upsert_profile(owner_b, {"id": owner_b, "display_name": "林哥"})
    LocalStore.upsert_profile(dual_runner, {"id": dual_runner, "display_name": "双团阿明"})
    LocalStore.upsert_profile(solo_runner, {"id": solo_runner, "display_name": "独行侠"})
    LocalStore.upsert_profile(deleted_only_runner, {"id": deleted_only_runner, "display_name": "旧团友"})

    club_a = "club_cc_multi_a"
    club_b = "club_cc_multi_b"
    club_del = "club_cc_multi_del"

    _seed_club(club_a, "飞羽一团", owner_a, [(owner_a, "owner"), (dual_runner, "member")], invite_code="CCM1")
    _seed_club(club_b, "星火二团", owner_b, [(owner_b, "owner"), (dual_runner, "member")], invite_code="CCM2")
    _seed_club(
        club_del,
        "已解散旧团",
        owner_a,
        [(deleted_only_runner, "member")],
        status="deleted",
        invite_code="CCMDEL",
    )

    act_dual = {
        "id": "act_cc_dual_1",
        "user_id": dual_runner,
        "name": "城市晨跑",
        "sport_type": "Run",
        "start_time": f"{today_iso}T07:00:00",
        "distance_meters": 10000.0,
        "moving_time_seconds": 3000,
    }
    _, meta_a = generate_activity_captain_cheer(dict(act_dual), club_id=club_a)
    _, meta_b = generate_activity_captain_cheer(dict(act_dual), club_id=club_b)
    _, meta_unscoped = generate_activity_captain_cheer(dict(act_dual))

    # Avoid duplicate "团长团长" on owner display_name="陈团长"
    assert meta_a["captain_title"] == "飞羽一团 · 陈团长"
    assert "团长团长" not in meta_a["captain_title"]

    assert meta_b["captain_title"] == "星火二团 · 林哥团长"
    primary_club = LocalStore.get_user_clubs(dual_runner)[0]["id"]
    assert meta_unscoped["club_id"] == primary_club

    # Solo / unaffiliated or deleted-club-only runners get None
    solo_cheer, solo_meta = generate_activity_captain_cheer(
        {
            "id": "act_cc_solo_1",
            "user_id": solo_runner,
            "name": "公园散心跑",
            "sport_type": "Run",
            "start_time": f"{today_iso}T08:00:00",
            "distance_meters": 6000.0,
            "moving_time_seconds": 2100,
        }
    )
    assert solo_cheer is None
    assert solo_meta is None

    del_cheer, del_meta = generate_activity_captain_cheer(
        {
            "id": "act_cc_del_1",
            "user_id": deleted_only_runner,
            "name": "旧团打卡",
            "sport_type": "Run",
            "start_time": f"{today_iso}T08:00:00",
            "distance_meters": 6000.0,
            "moving_time_seconds": 2100,
        }
    )
    assert del_cheer is None
    assert del_meta is None
