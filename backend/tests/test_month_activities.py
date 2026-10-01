import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore, DB_PATH
import sqlite3

client = TestClient(app)

def test_month_activities_retrieval_and_dashboard():
    uid = "u_test_month_runner"
    LocalStore.upsert_profile(uid, {"display_name": "月跑量测试员", "email": "month@runner.com"})

    from datetime import date
    today = date.today()
    cur_year = today.year
    cur_month = today.month
    prev_month = 12 if cur_month == 1 else cur_month - 1
    prev_year = cur_year - 1 if cur_month == 1 else cur_year

    cur_prefix = f"{cur_year}-{cur_month:02d}"
    prev_prefix = f"{prev_year}-{prev_month:02d}"

    # Insert activities in different months
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM activities WHERE user_id = ?", (uid,))
        # 3 activities in current month
        for i in range(1, 4):
            cursor.execute("""
                INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"act_cur_{i}", uid, f"当月第{i}跑", "running", f"{cur_prefix}-0{i}T07:00:00", 10000, 3000, "5:00 /km", 50, 150, 120))
        
        # 2 activities in previous month
        for i in range(1, 3):
            cursor.execute("""
                INSERT OR REPLACE INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"act_prev_{i}", uid, f"上月第{i}跑", "running", f"{prev_prefix}-1{i}T07:00:00", 12000, 3600, "5:00 /km", 30, 148, 140))
        conn.commit()

    # 1. Test LocalStore.get_month_activities directly
    cur_acts = LocalStore.get_month_activities(uid, cur_year, cur_month)
    assert len(cur_acts) == 3
    assert all(cur_prefix in a["start_time"] for a in cur_acts)

    prev_acts = LocalStore.get_month_activities(uid, prev_year, prev_month)
    assert len(prev_acts) == 2
    assert all(prev_prefix in a["start_time"] for a in prev_acts)

    # 2. Test /api/miniapp/dashboard/{uid} endpoint
    dash_res = client.get(f"/api/miniapp/dashboard/{uid}")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "current_month_activities" in dash_data
    assert "current_month_info" in dash_data
    assert dash_data["current_month_info"]["total_count"] >= 3
    assert dash_data["current_month_info"]["total_km"] >= 30.0
    # recent_activities must contain all current month activities
    assert len(dash_data["recent_activities"]) >= 3

    # 3. Test /api/miniapp/activities/month/{uid} endpoint
    month_res = client.get(f"/api/miniapp/activities/month/{uid}?year={prev_year}&month={prev_month}")
    assert month_res.status_code == 200
    m_data = month_res.json()
    assert m_data["year"] == prev_year
    assert m_data["month"] == prev_month
    assert m_data["total_count"] == 2
    assert m_data["total_km"] == 24.0
    assert len(m_data["activities"]) == 2

    # 4. Test /api/team/{club_id}/feed returns all current month activities by default
    club = LocalStore.create_club(
        owner_id=uid,
        name="月度动态测试跑团",
        description="测试动态墙默认返回当月全部记录",
        city="上海"
    )
    club_id = club["id"]
    feed_res = client.get(f"/api/team/{club_id}/feed?uid={uid}")
    assert feed_res.status_code == 200
    f_data = feed_res.json()
    assert len(f_data["feed"]) == 3  # 3 activities in current month
    assert f_data["month_total"] == 3
    assert f_data["is_current_month"] is True

