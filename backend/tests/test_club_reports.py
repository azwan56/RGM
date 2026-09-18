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

    # 5. Permission Test: Non-owner access -> 403 Forbidden
    res_m1 = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": member_1, "period_type": "week"})
    assert res_m1.status_code == 403
    assert "只有跑团团长有权" in res_m1.json()["detail"]

    res_out = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": outsider, "period_type": "week"})
    assert res_out.status_code == 403

    res_m1_export = client.get(f"/api/team/{club_id}/reports/export", params={"operator_uid": member_1, "period_type": "week"})
    assert res_m1_export.status_code == 403

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

    # 7. Owner Access Test: Monthly Report
    res_month = client.get(f"/api/team/{club_id}/reports", params={"operator_uid": owner_uid, "period_type": "month"})
    assert res_month.status_code == 200
    m_data = res_month.json()
    assert m_data["period_type"] == "month"
    assert round(m_data["total_distance_km"], 1) == 44.1

    # 8. Owner Export Test: PlainText download
    res_export = client.get(f"/api/team/{club_id}/reports/export", params={"operator_uid": owner_uid, "period_type": "week"})
    assert res_export.status_code == 200
    assert "text/plain" in res_export.headers.get("content-type", "")
    assert "attachment" in res_export.headers.get("content-disposition", "")
    content = res_export.text
    assert "战报荣耀跑团" in content
    assert "km" in content
