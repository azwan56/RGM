import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore, DB_PATH
import sqlite3

client = TestClient(app)

def test_club_periodic_reports_and_permissions():
    owner_uid = "u_rep_owner_test"
    member_1 = "u_rep_m1_test"
    member_2 = "u_rep_m2_test"
    outsider = "u_rep_outsider_test"

    # 1. Setup profiles
    LocalStore.upsert_profile(owner_uid, {"display_name": "战报团长", "email": "rep_owner@test.com"})
    LocalStore.upsert_profile(member_1, {"display_name": "闪电跑者", "email": "rep_m1@test.com"})
    LocalStore.upsert_profile(member_2, {"display_name": "耐力大师", "email": "rep_m2@test.com"})
    LocalStore.upsert_profile(outsider, {"display_name": "路人跑友", "email": "rep_out@test.com"})

    # 2. Create club
    club = LocalStore.create_club(
        owner_id=owner_uid,
        name="战报荣耀跑团",
        description="测试周报月报生成与转发功能",
        city="北京"
    )
    club_id = club["id"]

    # 3. Add members
    LocalStore.join_club_by_id(user_id=member_1, club_id=club_id, privacy_consent=True)
    LocalStore.join_club_by_id(user_id=member_2, club_id=club_id, privacy_consent=True)

    # 4. Insert activities in current month / week
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM activities WHERE id = 'act_rep_trail_1'")
        cursor.execute("""
            INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("act_rep_1", member_1, "节奏跑", "running", now_iso, 15000, 4500, "5:00 /km", 120, 155, 130))

        cursor.execute("""
            INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("act_rep_2", member_1, "间歇跑", "running", now_iso, 8000, 2160, "4:30 /km", 50, 168, 90))

        cursor.execute("""
            INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("act_rep_3", member_2, "LSD长距离", "running", now_iso, 21097, 6600, "5:12 /km", 200, 142, 160))
        conn.commit()

    # 5. Permission Test: Outsider access -> 403 Forbidden
    res_out = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": outsider, "period_type": "week"})
    assert res_out.status_code == 403
    assert "只有跑团成员和团长有权" in res_out.json()["detail"]

    res_out_export = client.get(f"/api/team/{club_id}/reports/export", params={"operator_uid": outsider, "period_type": "week"})
    assert res_out_export.status_code == 403

    # Member access -> 200 OK
    res_m1 = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": member_1, "period_type": "week"})
    assert res_m1.status_code == 200

    res_m1_export = client.get(f"/api/team/{club_id}/reports/export", params={"operator_uid": member_1, "period_type": "week"})
    assert res_m1_export.status_code == 200

    # 6. Owner Access Test: Weekly Report
    res_week = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": owner_uid, "period_type": "week"})
    assert res_week.status_code == 200
    w_data = res_week.json()
    assert w_data["club_id"] == club_id
    assert w_data["period_type"] == "week"
    assert w_data["total_members_count"] >= 2
    assert w_data["active_members_count"] == 2
    assert w_data["total_activities_count"] == 3
    assert round(w_data["total_distance_km"], 1) == 44.1 # 15 + 8 + 21.097
    assert len(w_data["leaderboard"]) >= 2
    assert len(w_data["podium"]) >= 1
    assert len(w_data["canova_critique"]) > 20 and "教练建议" in w_data["canova_critique"]
    assert "战报荣耀跑团" in w_data["forward_text"]
    assert "【荣耀榜单 Top 3】" in w_data["forward_text"]

    # Verify member_progress_list & targets
    assert "member_progress_list" in w_data
    assert len(w_data["member_progress_list"]) >= 2
    for prog in w_data["member_progress_list"]:
        assert "target_km" in prog
        assert "distance_km" in prog
        assert "completion_rate" in prog
        assert "is_achieved" in prog
        assert "status" in prog
        assert prog["target_km"] > 0
    assert w_data["total_target_km"] > 0
    assert "team_completion_rate" in w_data
    assert "achieved_members_count" in w_data
    assert "【全员跑量目标与完成度】" in w_data["forward_text"]

    # 7. Owner Access Test: Monthly Report
    res_month = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": owner_uid, "period_type": "month"})
    assert res_month.status_code == 200
    m_data = res_month.json()
    assert m_data["period_type"] == "month"
    assert round(m_data["total_distance_km"], 1) == 44.1
    assert "member_progress_list" in m_data
    assert len(m_data["member_progress_list"]) >= 2
    assert m_data["member_progress_list"][0]["target_km"] > 0

    # 7b. Test Past Period: status should be 未达标 instead of 进行中
    res_past = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": owner_uid, "period_type": "month", "year": 2025, "period_index": 1})
    assert res_past.status_code == 200
    past_data = res_past.json()
    assert past_data["is_past_period"] is True
    unachieved = next(p for p in past_data["member_progress_list"] if not p["is_achieved"])
    assert unachieved["status"] == "未达标"

    # 8. Set custom goal for member_1 and re-verify
    LocalStore.upsert_goal(member_1, {
        "target_distance": 100.0,
        "weekly_target": 20.0,
        "monthly_targets": [100.0] * 12
    })
    res_custom = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": owner_uid, "period_type": "week"})
    custom_data = res_custom.json()
    m1_item = next(p for p in custom_data["member_progress_list"] if p["user_id"] == member_1)
    assert m1_item["target_km"] == 20.0
    assert m1_item["distance_km"] == 23.0 # 15 + 8
    assert m1_item["is_achieved"] is True
    assert m1_item["status"] == "已达标"
    assert m1_item["completion_rate"] == 115.0

    # 9. Owner Export Test: PlainText download
    res_export = client.get(f"/api/team/{club_id}/reports/export", params={"operator_uid": owner_uid, "period_type": "week"})
    assert res_export.status_code == 200
    assert "text/plain" in res_export.headers.get("content-type", "")
    assert "attachment" in res_export.headers.get("content-disposition", "")
    content = res_export.text
    assert "战报荣耀跑团" in content
    assert "km" in content
    assert "【全员跑量目标与完成度】" in content

    # 10. Coach Access Test: Coach can also generate and export reports
    coach_uid = "u_rep_coach_test"
    LocalStore.upsert_profile(coach_uid, {"display_name": "Canova教练", "email": "rep_coach@test.com"})
    LocalStore.join_club_by_id(user_id=coach_uid, club_id=club_id, privacy_consent=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.cursor().execute("UPDATE club_memberships SET role = 'coach' WHERE club_id = ? AND user_id = ?", (club_id, coach_uid))
        conn.commit()

    res_coach_week = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": coach_uid, "period_type": "week"})
    assert res_coach_week.status_code == 200
    assert res_coach_week.json()["club_id"] == club_id
    assert "战报荣耀跑团" in res_coach_week.json()["forward_text"]

    res_coach_month = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": coach_uid, "period_type": "month"})
    assert res_coach_month.status_code == 200
    assert res_coach_month.json()["period_type"] == "month"

    res_coach_export = client.get(f"/api/team/{club_id}/reports/export", params={"operator_uid": coach_uid, "period_type": "week"})
    assert res_coach_export.status_code == 200
    assert "战报荣耀跑团" in res_coach_export.text

    # 11. Trail running filtering test (include / exclude_pace / exclude_all)
    with sqlite3.connect(DB_PATH) as conn:
        conn.cursor().execute("""
            INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("act_rep_trail_1", member_1, "莫干山越野赛", "trail_running", now_iso, 20000, 14400, "12:00 /km", 1200, 150, 220))
        conn.commit()

    # Default (include): 44.1 + 20.0 = 64.1 km, 4 activities
    res_inc = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": owner_uid, "period_type": "week"})
    assert res_inc.status_code == 200
    inc_data = res_inc.json()
    assert inc_data["trail_mode"] == "include"
    assert inc_data["trail_activities_count"] == 1
    assert round(inc_data["trail_distance_km"], 1) == 20.0
    assert round(inc_data["total_distance_km"], 1) == 64.1
    assert inc_data["total_activities_count"] == 4
    # Team pace with trail included: (4500+2160+6600+14400) / 64.097 = 431.53 s/km -> 7:12 /km
    assert inc_data["avg_pace_str"] == "7:12 /km"

    # exclude_pace: mileage stays 64.1 km, but pace excludes trail (13260 / 44.097 = 300.7 s/km -> 5:01 /km)
    res_ex_pace = client.get(
        f"/api/team/{club_id}/reports",
        params={"operator_uid": owner_uid, "period_type": "week", "trail_mode": "exclude_pace"}
    )
    assert res_ex_pace.status_code == 200
    ex_pace_data = res_ex_pace.json()
    assert ex_pace_data["trail_mode"] == "exclude_pace"
    assert round(ex_pace_data["total_distance_km"], 1) == 64.1
    assert ex_pace_data["total_activities_count"] == 4
    assert ex_pace_data["avg_pace_str"] == "5:01 /km"
    m1_ex_pace = next(p for p in ex_pace_data["leaderboard"] if p["user_id"] == member_1)
    assert round(m1_ex_pace["distance_km"], 1) == 43.0  # 15 + 8 + 20
    assert m1_ex_pace["avg_pace_str"] == "4:50 /km"  # (4500+2160)/23 = 289.56 -> 4:50 /km
    assert "仅去除越野配速" in ex_pace_data["forward_text"]

    # exclude_all: both mileage and pace exclude trail (total_distance_km = 44.1, total_activities_count = 3, avg_pace = 5:01 /km)
    res_ex_all = client.get(
        f"/api/team/{club_id}/reports",
        params={"operator_uid": owner_uid, "period_type": "week", "trail_mode": "exclude_all"}
    )
    assert res_ex_all.status_code == 200
    ex_all_data = res_ex_all.json()
    assert ex_all_data["trail_mode"] == "exclude_all"
    assert round(ex_all_data["total_distance_km"], 1) == 44.1
    assert ex_all_data["total_activities_count"] == 3
    assert ex_all_data["avg_pace_str"] == "5:01 /km"
    m1_ex_all = next(p for p in ex_all_data["leaderboard"] if p["user_id"] == member_1)
    assert round(m1_ex_all["distance_km"], 1) == 23.0  # 15 + 8
    assert m1_ex_all["avg_pace_str"] == "4:50 /km"
    assert "去除越野跑量与配速" in ex_all_data["forward_text"]
    assert "微血管" not in ex_all_data["canova_critique"]

    # 12. Personal periodic report test (week / month & trail_mode)
    res_p_inc = client.get(f"/api/science/personal-report/{member_1}", params={"period_type": "week", "trail_mode": "include"})
    assert res_p_inc.status_code == 200
    p_inc = res_p_inc.json()
    assert round(p_inc["total_distance_km"], 1) == 43.0
    assert p_inc["total_activities_count"] == 3
    assert "微血管" not in p_inc["canova_critique"]
    assert "教练建议" in p_inc["canova_critique"]

    res_p_ex_pace = client.get(f"/api/science/personal-report/{member_1}", params={"period_type": "week", "trail_mode": "exclude_pace"})
    assert res_p_ex_pace.status_code == 200
    p_ex_pace = res_p_ex_pace.json()
    assert round(p_ex_pace["total_distance_km"], 1) == 43.0
    assert p_ex_pace["avg_pace_str"] == "4:50 /km"

    res_p_ex_all = client.get(f"/api/science/personal-report/{member_1}", params={"period_type": "week", "trail_mode": "exclude_all"})
    assert res_p_ex_all.status_code == 200
    p_ex_all = res_p_ex_all.json()
    assert round(p_ex_all["total_distance_km"], 1) == 23.0
    assert p_ex_all["total_activities_count"] == 2
    assert p_ex_all["avg_pace_str"] == "4:50 /km"


def test_coach_cockpit_tsb_status_sorting():
    club_owner = "u_tsb_owner"
    coach_uid = "u_tsb_coach"
    user_danger = "u_tsb_danger"
    user_tired = "u_tsb_tired"
    user_optimal = "u_tsb_optimal"
    user_peak = "u_tsb_peak"

    for uid, name in [
        (club_owner, "主理人"), (coach_uid, "主教练"),
        (user_danger, "过载学员"), (user_tired, "疲劳学员"),
        (user_optimal, "适应学员"), (user_peak, "巅峰学员")
    ]:
        LocalStore.upsert_profile(uid, {"display_name": name})

    club = LocalStore.create_club(owner_id=club_owner, name="体能罗盘跑团", city="上海")
    club_id = club["id"]

    for uid in [coach_uid, user_danger, user_tired, user_optimal, user_peak]:
        LocalStore.join_club_by_id(user_id=uid, club_id=club_id, privacy_consent=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.cursor().execute("UPDATE club_memberships SET role = 'coach' WHERE club_id = ? AND user_id = ?", (club_id, coach_uid))
        conn.commit()

    # Create dummy health and activities with different TRIMP loads to generate distinct TSBs
    from datetime import date, timedelta
    today = date.today()

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # 1. Danger: huge recent load in past 7 days (huge ATL -> TSB < -50)
        for i in range(5):
            cur.execute("""
                INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, trimp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"act_dan_{i}", user_danger, "超高负荷间歇", "running", (today - timedelta(days=i)).isoformat() + "T08:00:00Z", 20000, 5400, 280))

        # 2. Tired: moderate recent load (TSB around -40)
        for i in range(3):
            cur.execute("""
                INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, trimp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"act_tir_{i}", user_tired, "专项课", "running", (today - timedelta(days=i*2)).isoformat() + "T08:00:00Z", 15000, 4200, 150))

        # 3. Optimal: steady training load evenly distributed
        for i in range(12):
            cur.execute("""
                INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, trimp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"act_opt_{i}", user_optimal, "有氧慢跑", "running", (today - timedelta(days=i*4)).isoformat() + "T08:00:00Z", 10000, 3000, 60))

        # 4. Peak: long CTL built up 40 days ago, zero load in past 7 days (ATL near 0, high CTL -> TSB > 5)
        for i in range(10, 40, 3):
            cur.execute("""
                INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, trimp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"act_pk_{i}", user_peak, "基础期拉练", "running", (today - timedelta(days=i)).isoformat() + "T08:00:00Z", 16000, 4800, 120))

        conn.commit()

    # Verify danger_first sort order (Default)
    res_danger_first = client.get(f"/api/team/{club_id}/coach-cockpit", params={"coach_uid": coach_uid, "sort_order": "danger_first"})
    assert res_danger_first.status_code == 200
    st_danger = res_danger_first.json()["students"]
    assert len(st_danger) >= 4
    
    # Check that students with status danger/tired appear before optimal/peak
    status_order = [s["status_level"] for s in st_danger if s["user_id"] in (user_danger, user_tired, user_optimal, user_peak)]
    assert status_order.index("danger") < status_order.index("optimal")
    assert status_order.index("danger") < status_order.index("peak")

    # Verify peak_first sort order
    res_peak_first = client.get(f"/api/team/{club_id}/coach-cockpit", params={"coach_uid": coach_uid, "sort_order": "peak_first"})
    assert res_peak_first.status_code == 200
    st_peak = res_peak_first.json()["students"]
    peak_status_order = [s["status_level"] for s in st_peak if s["user_id"] in (user_danger, user_tired, user_optimal, user_peak)]
    assert peak_status_order.index("peak") < peak_status_order.index("danger")

