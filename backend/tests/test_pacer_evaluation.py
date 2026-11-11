import json
import sqlite3
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient

from main import app
from utils.local_store import DB_PATH, LocalStore, init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def _make_splits(km_paces_sec, avg_hr=148):
    splits = []
    for idx, p in enumerate(km_paces_sec, start=1):
        splits.append({
            "lapIndex": idx,
            "distance": 1000.0,
            "movingDuration": float(p),
            "averageHR": avg_hr,
            "elevationGain": 1.0,
            "elevationLoss": 1.0,
        })
    return json.dumps(splits)


def _insert_run(uid: str, act_id: str, days_ago: int, dist_km: float, pace_sec: int, avg_hr: int = 148, splits_json: str = None, name: str = "晨间稳态长距离"):
    d_str = (date.today() - timedelta(days=days_ago)).isoformat() + "T06:30:00Z"
    dur_s = int(round(dist_km * pace_sec))
    m_min = pace_sec // 60
    m_sec = pace_sec % 60
    pace_str = f"{m_min}:{m_sec:02d}"
    if splits_json is None:
        n_km = max(5, int(round(dist_km)))
        splits_json = _make_splits([pace_sec + (1 if i % 2 == 0 else -1) for i in range(n_km)], avg_hr=avg_hr)
    with sqlite3.connect(DB_PATH) as conn:
        conn.cursor().execute(
            """
            INSERT OR REPLACE INTO activities (
                id, user_id, name, sport_type, start_time, distance_meters,
                moving_time_seconds, elapsed_time_seconds, elevation_gain_meters,
                average_heartrate, max_heartrate, average_cadence, avg_pace_str,
                trimp, splits_data, exclude_mode
            ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, 35.0, ?, 172, 182.0, ?, 95.0, ?, 'normal')
            """,
            (act_id, uid, name, d_str, dist_km * 1000.0, dur_s, dur_s + 15, avg_hr, pace_str, splits_json),
        )
        conn.commit()


def test_platinum_shanghai_marathon_metronome_runner_and_credentials():
    uid = "u_test_pacer_elite_01"
    # PB 2:52:00 (10320s), Half PB 1:21:00 (4860s), age 36, AHA certified
    res_prof = client.put(
        f"/api/profile/{uid}",
        json={
            "display_name": "上马节拍器老陈",
            "date_of_birth": "1990-05-12",
            "gender": "male",
            "resting_heart_rate": 50,
            "max_heart_rate": 188,
            "marathon_pb": 10320,
            "half_pb": 4860,
            "ten_k_pb": 2220,
            "five_k_pb": 1050,
            "first_aid_cert_type": "aha",
        },
    )
    assert res_prof.status_code == 200

    # Add 2 completed marathons within 24 months (one as official 330 pacer with -12s error!)
    d_last_yr = (date.today() - timedelta(days=340)).isoformat()
    d_6m_ago = (date.today() - timedelta(days=170)).isoformat()
    client.post(
        f"/api/profile/{uid}/races",
        json={
            "id": "race_pacer_sh_prev",
            "name": "上海马拉松",
            "race_type": "全程马拉松",
            "race_date": d_last_yr,
            "target_time": "03:30:00",
            "status": "completed",
            "finish_time": "03:29:48",
            "was_official_pacer": True,
            "pacer_target_time": "03:30:00",
        },
    )
    client.post(
        f"/api/profile/{uid}/races",
        json={
            "id": "race_pacer_wx_pb",
            "name": "无锡马拉松",
            "race_type": "全程马拉松",
            "race_date": d_6m_ago,
            "target_time": "02:55:00",
            "status": "completed",
            "finish_time": "02:52:00",
        },
    )

    # Seed 6 weeks of solid training (~75km/wk) + ultra-steady 28km & 32km cruise runs (with 1 red-light outlier!)
    for wk in range(6):
        base_d = wk * 7
        _insert_run(uid, f"act_elite_easy1_{wk}", base_d + 1, 14.0, 298, avg_hr=138)
        _insert_run(uid, f"act_elite_easy2_{wk}", base_d + 3, 16.0, 272, avg_hr=146)
        _insert_run(uid, f"act_elite_easy3_{wk}", base_d + 5, 14.0, 295, avg_hr=137)
        # Weekend 30km steady run with 1 traffic-light stop (+65s on km 12) + interval workout on Tuesday
        steady_paces = [298, 299, 297, 298, 300, 299, 298, 297, 299, 298, 300, 365, 298, 299, 297,
                        298, 299, 300, 298, 297, 299, 298, 299, 298, 297, 299, 298, 300, 298, 297]
        _insert_run(uid, f"act_elite_lsd_{wk}", base_d + 6, 30.0, 298, avg_hr=142, splits_json=_make_splits(steady_paces, 142))

    # Also insert a noisy interval session to prove portfolio selector ignores interval workouts!
    interval_paces = [330, 215, 390, 214, 395, 216, 385, 215, 390, 213, 380, 340]
    _insert_run(uid, "act_elite_interval_01", 4, 12.0, 295, avg_hr=165, splits_json=_make_splits(interval_paces, 165), name="周二操场间歇 1000m*5")

    # 1. Evaluate for Shanghai Marathon 330 Official Pacer -> should be A/S grade (>= 85)!
    r_330 = client.get(f"/api/science/pacer-eval/{uid}?event_name=上海马拉松&distance_type=fm&target_group=330&allow_web_search=false")
    assert r_330.status_code == 200
    d_330 = r_330.json()
    sel_330 = d_330["selected_evaluation"]
    assert d_330["event_calibration"]["strictness_tier"] == "platinum"
    assert sel_330["overall_score"] >= 85
    assert sel_330["gates"]["fitness_gate"]["status"] == "pass"
    assert sel_330["gates"]["cert_gate"]["status"] == "pass"
    assert sel_330["sigma_avg_sec"] is not None and sel_330["sigma_avg_sec"] <= 3.0
    assert d_330["showcase_run"] is not None
    assert len(d_330["showcase_run"]["splits_series"]) >= 25
    assert len(d_330["monthly_mileage_6m"]) == 6

    # 2. Evaluate same runner for Shanghai Marathon 300 Official Pacer -> PB 2:52 only has 8 min margin (<20m Platinum requirement), should cap <= 59!
    r_300 = client.get(f"/api/science/pacer-eval/{uid}?event_name=上海马拉松&distance_type=fm&target_group=300&allow_web_search=false")
    assert r_300.status_code == 200
    sel_300 = r_300.json()["selected_evaluation"]
    assert sel_300["overall_score"] <= 59
    assert sel_300["gates"]["cert_gate"]["status"] == "fail"

    # 3. Verify Lanzhou sub-plateau (1530m) requires higher margin than flat Gold Label Beijing Marathon on 315 group
    r_bj_315 = client.get(f"/api/science/pacer-eval/{uid}?event_name=北京马拉松&distance_type=fm&target_group=315&allow_web_search=false").json()
    r_lz_315 = client.get(f"/api/science/pacer-eval/{uid}?event_name=兰州马拉松&distance_type=fm&target_group=315&allow_web_search=false").json()
    assert r_lz_315["event_calibration"]["sub_plateau"] is True
    assert r_lz_315["selected_evaluation"]["req_cert_margin_sec"] > r_bj_315["selected_evaluation"]["req_cert_margin_sec"]

    # 4. Test AI Prescription & Self-Recommendation endpoint
    r_ai = client.post(
        f"/api/science/pacer-ai-prescription/{uid}",
        json={"event_name": "上海马拉松", "distance_type": "fm", "target_group": "330"},
    )
    assert r_ai.status_code == 200
    ai_data = r_ai.json()
    assert ai_data["success"] is True
    assert len(ai_data["four_week_plan"]) > 30
    assert "330" in ai_data["application_statement"] or "上海马拉松" in ai_data["application_statement"]


def test_dual_gatekeeper_detrained_veteran_vs_dark_horse_missing_cert():
    # Case A: Detrained Veteran (PB 2:38 certificate, but almost zero recent training -> current pred > 3:05)
    uid_vet = "u_test_pacer_detrained_vet"
    client.put(
        f"/api/profile/{uid_vet}",
        json={
            "display_name": "缺练老大神",
            "date_of_birth": "1985-03-10",
            "marathon_pb": 9480,  # 2:38:00
            "half_pb": 4560,
        },
    )
    client.post(
        f"/api/profile/{uid_vet}/races",
        json={
            "id": "race_vet_01",
            "name": "无锡马拉松",
            "race_type": "全马",
            "race_date": (date.today() - timedelta(days=400)).isoformat(),
            "target_time": "02:40:00",
            "status": "completed",
            "finish_time": "02:38:00",
        },
    )
    # Only 1 short slow 6km jog in last 6 weeks!
    _insert_run(uid_vet, "act_vet_jog_1", 5, 6.0, 355, avg_hr=158)

    res_vet = client.get(f"/api/science/pacer-eval/{uid_vet}?event_name=北京马拉松&distance_type=fm&target_group=300&allow_web_search=false").json()
    sel_vet = res_vet["selected_evaluation"]
    assert sel_vet["gates"]["fitness_gate"]["status"] in ("fail", "warn")
    assert sel_vet["overall_score"] <= 68  # Capped safely against bonk risk despite 2:38 historical PB!

    # Case B: Dark Horse (No FM certificate at all, only 5K/10K/training, but training 85km/wk at 4:00/km!)
    uid_dh = "u_test_pacer_dark_horse"
    client.put(
        f"/api/profile/{uid_dh}",
        json={
            "display_name": "黑马小李",
            "date_of_birth": "1996-08-20",
            "marathon_pb": 0,
            "half_pb": 0,
            "ten_k_pb": 2160,  # 36:00
            "five_k_pb": 1020,
            "resting_heart_rate": 48,
            "max_heart_rate": 192,
        },
    )
    for wk in range(6):
        b = wk * 7
        _insert_run(uid_dh, f"act_dh_a_{wk}", b + 1, 16.0, 255, avg_hr=145)
        _insert_run(uid_dh, f"act_dh_b_{wk}", b + 3, 18.0, 250, avg_hr=148)
        _insert_run(uid_dh, f"act_dh_c_{wk}", b + 6, 32.0, 260, avg_hr=150)

    # On Official Gold Label FM 330 -> fitness passes easily, cert_gate flags 'missing_cert' ("胜任私兔/拉练兔 · 官兔初审缺证")
    res_dh_off = client.get(f"/api/science/pacer-eval/{uid_dh}?event_name=北京马拉松&distance_type=fm&target_group=330&allow_web_search=false").json()
    sel_dh_off = res_dh_off["selected_evaluation"]
    assert sel_dh_off["gates"]["fitness_gate"]["status"] == "pass"
    assert sel_dh_off["gates"]["cert_gate"]["status"] == "missing_cert"
    assert "私兔" in sel_dh_off["verdict_label"]
    assert sel_dh_off["private_pacer_score"] >= 80

    # On Custom Club 30km LSD @ 5:00/km -> cert_gate is exempt, overall_score >= 82!
    res_dh_lsd = client.get(
        f"/api/science/pacer-eval/{uid_dh}?distance_type=custom&custom_distance_km=30&custom_target_pace=5:00&allow_web_search=false"
    ).json()
    assert res_dh_lsd["selected_evaluation"]["gates"]["cert_gate"]["status"] == "exempt"
    assert res_dh_lsd["selected_evaluation"]["overall_score"] >= 80


def test_club_pacer_radar_privacy_and_assign_event_pacer():
    owner_uid = "u_test_club_owner_pacer"
    member_uid = "u_test_club_member_pacer"
    outsider_uid = "u_test_club_outsider_pacer"

    client.put(
        f"/api/profile/{owner_uid}",
        json={"display_name": "王团长", "date_of_birth": "1982-01-01"},
    )
    client.put(
        f"/api/profile/{member_uid}",
        json={
            "display_name": "保密达人阿杰",
            "real_name": "张阿杰",
            "date_of_birth": "1991-06-15",
            "marathon_pb": 11400,  # 3:10:00
            "hide_biometrics": True,
        },
    )
    client.put(f"/api/profile/{outsider_uid}", json={"display_name": "普通团员"})

    # Seed steady runs & HRV data for member_uid
    for wk in range(4):
        _insert_run(member_uid, f"act_mem_pacer_{wk}", wk * 7 + 2, 26.0, 298, avg_hr=144)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT OR REPLACE INTO daily_health (id, user_id, date, resting_heart_rate, sleep_score, hrv_last_night_avg)
            VALUES ('dh_pacer_priv_1', ?, ?, 49, 88, 76.0)
            """,
            (member_uid, date.today().isoformat()),
        )
        c.execute(
            """
            INSERT OR REPLACE INTO clubs (id, name, city, invite_code, owner_id, status, created_at)
            VALUES ('club_pacer_test_01', '浦东破三营', '上海', 'PD300X', ?, 'active', '2026-01-01T00:00:00Z')
            """,
            (owner_uid,),
        )
        c.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_pt_1', 'club_pacer_test_01', ?, 'owner', 'active', '2026-01-01')",
            (owner_uid,),
        )
        c.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_pt_2', 'club_pacer_test_01', ?, 'member', 'active', '2026-01-02')",
            (member_uid,),
        )
        c.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at) VALUES ('cm_pt_3', 'club_pacer_test_01', ?, 'member', 'active', '2026-01-03')",
            (outsider_uid,),
        )
        c.execute(
            """
            INSERT OR REPLACE INTO club_events (id, club_id, title, event_type, start_date, meet_time, target_km, pace_requirement, status)
            VALUES ('evt_pacer_lsd_01', 'club_pacer_test_01', '上马赛前30km世纪公园模拟拉练', 'group_run', '2026-11-15', '2026-11-15 06:30', 30.0, '5:00/km', 'upcoming')
            """
        )
        conn.commit()

    # Non-coach/non-owner member should be blocked (403)
    r_forbid = client.get(f"/api/team/club_pacer_test_01/pacer-radar?operator_uid={outsider_uid}&event_name=上海马拉松")
    assert r_forbid.status_code == 403

    # Club owner (who is NOT certified coach/mentor) runs radar -> succeeds AND masks raw HRV/RHR for member_uid!
    r_radar = client.get(
        f"/api/team/club_pacer_test_01/pacer-radar?operator_uid={owner_uid}&event_name=上海马拉松&distance_type=fm&target_groups=330,400&allow_web_search=false"
    )
    assert r_radar.status_code == 200
    radar_data = r_radar.json()
    assert radar_data["total_members_evaluated"] == 3
    g_330 = next(g for g in radar_data["groups_ranking"] if g["group_code"] == "330")
    cand_ajie = next(c for c in g_330["candidates"] if c["uid"] == member_uid)
    rec_dim = next(d for d in cand_ajie["dimensions"] if d["key"] == "recovery_reliability")
    assert "76ms" not in rec_dim["display_value"] and "49bpm" not in rec_dim["display_value"]
    assert "隐私保护已脱敏" in rec_dim["display_value"]

    # Owner assigns member_uid as '🐰 领跑兔' for evt_pacer_lsd_01 -> writes participant & creates notification!
    r_assign = client.post(
        "/api/team/club_pacer_test_01/events/evt_pacer_lsd_01/assign-pacer",
        json={
            "operator_uid": owner_uid,
            "target_uid": member_uid,
            "pace_group": "⚡ 330备战组 (4:58/km)",
            "note": "控速最稳，拜托带队！",
        },
    )
    assert r_assign.status_code == 200
    assign_data = r_assign.json()
    assert assign_data["success"] is True
    assert assign_data["runner_role"] == "🐰 领跑兔"

    notifs = LocalStore.get_user_notifications(member_uid, limit=5)
    assert any(n["type"] == "pacer_invite" and "330备战组" in n["content"] for n in notifs)
