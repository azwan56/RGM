import pytest
import sqlite3
from datetime import datetime, timedelta
from utils.local_store import LocalStore, DB_PATH, RUNNING_SPORT_TYPES, RUNNING_SQL_FILTER


def test_is_running_activity_helper():
    # Valid running types
    assert LocalStore.is_running_activity("Run") is True
    assert LocalStore.is_running_activity("run") is True
    assert LocalStore.is_running_activity("running") is True
    assert LocalStore.is_running_activity("TrailRun") is True
    assert LocalStore.is_running_activity("trail_running") is True
    assert LocalStore.is_running_activity("treadmill_running") is True
    assert LocalStore.is_running_activity("track_running") is True
    assert LocalStore.is_running_activity("street_running") is True

    # Excluded types
    assert LocalStore.is_running_activity("Swim") is False
    assert LocalStore.is_running_activity("swim") is False
    assert LocalStore.is_running_activity("Ride") is False
    assert LocalStore.is_running_activity("cycling") is False
    assert LocalStore.is_running_activity("Hike") is False
    assert LocalStore.is_running_activity("Walk") is False
    assert LocalStore.is_running_activity("Workout") is False
    assert LocalStore.is_running_activity("Paddleboard") is False
    assert LocalStore.is_running_activity(None) is False
    assert LocalStore.is_running_activity("") is False


def test_mileage_aggregation_excludes_swimming_and_other_sports():
    test_uid = "u_test_runner_sports_filter"
    today = LocalStore.get_beijing_today()
    month_start = f"{today.year:04d}-{today.month:02d}-01"
    now_iso = datetime.now().isoformat() + "+08:00"

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM activities WHERE user_id = ?", (test_uid,))
        cursor.execute("DELETE FROM profiles WHERE id = ?", (test_uid,))

        # Insert test profile
        cursor.execute("""
            INSERT INTO profiles (id, display_name)
            VALUES (?, ?)
        """, (test_uid, "Filter Test Athlete"))

        # 1. Running activity: 10km (10000m)
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, elapsed_time_seconds, avg_pace_str)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_run_{test_uid}", test_uid, "晨跑 10K", "Run", now_iso, 10000.0, 3000, 3000, "5:00"))

        # 2. Trail running: 15km (15000m)
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, elapsed_time_seconds, avg_pace_str)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_trail_{test_uid}", test_uid, "越野跑拉练", "trail_running", now_iso, 15000.0, 5400, 5400, "6:00"))

        # 3. Swimming: 2.5km (2500m) -> MUST BE EXCLUDED
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, elapsed_time_seconds, avg_pace_str)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_swim_{test_uid}", test_uid, "泳池游泳", "Swim", now_iso, 2500.0, 3600, 3600, "2:24"))

        # 4. Cycling: 30km (30000m) -> MUST BE EXCLUDED
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, elapsed_time_seconds, avg_pace_str)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_ride_{test_uid}", test_uid, "公路骑行", "Ride", now_iso, 30000.0, 3600, 3600, "2:00"))

        # 5. Hiking: 8km (8000m) -> MUST BE EXCLUDED
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, elapsed_time_seconds, avg_pace_str)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_hike_{test_uid}", test_uid, "周末徒步", "Hike", now_iso, 8000.0, 7200, 7200, "15:00"))

        # 6. Walking: 3km (3000m) -> MUST BE EXCLUDED
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, elapsed_time_seconds, avg_pace_str)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_walk_{test_uid}", test_uid, "日常健走", "Walk", now_iso, 3000.0, 2400, 2400, "13:20"))

        # 7. Workout: 0m -> EXCLUDED
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, elapsed_time_seconds, avg_pace_str)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_work_{test_uid}", test_uid, "跑后力量训练", "Workout", now_iso, 0.0, 1800, 1800, "—"))

        conn.commit()

    try:
        # Expected total running distance = 10km + 15km = 25km (25000m)
        # All sports combined would be: 10 + 15 + 2.5 + 30 + 8 + 3 = 68.5km
        month_dist_m = LocalStore.get_month_distance_meters(test_uid, month_start)
        assert month_dist_m == 25000.0, f"Expected 25000m running only, got {month_dist_m}"

        # Weekly stats
        weekly = LocalStore.get_weekly_stats(test_uid, target_km=50.0)
        assert weekly["current_week_km"] == 25.0, f"Expected 25.0km in weekly stats, got {weekly['current_week_km']}"
        assert weekly["total_runs"] == 2, f"Expected 2 runs in weekly stats, got {weekly['total_runs']}"

        # Monthly trend
        trend = LocalStore.get_monthly_trend(test_uid, num_months=1)
        assert trend["current_month_km"] == 25.0, f"Expected 25.0km in monthly trend, got {trend['current_month_km']}"

        # Yearly stats
        yearly = LocalStore.get_yearly_stats(test_uid, year=today.year)
        assert yearly["total_km"] == 25.0, f"Expected 25.0km in yearly stats, got {yearly['total_km']}"
        assert yearly["total_runs"] == 2, f"Expected 2 runs in yearly stats, got {yearly['total_runs']}"

        # Month activities list (must only have 2 activities: run & trail_run)
        month_acts = LocalStore.get_month_activities(test_uid, today.year, today.month)
        assert len(month_acts) == 2
        act_types = {a["sport_type"] for a in month_acts}
        assert act_types == {"Run", "trail_running"}

    finally:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM activities WHERE user_id = ?", (test_uid,))
            cursor.execute("DELETE FROM profiles WHERE id = ?", (test_uid,))
            conn.commit()


def test_canova_critique_non_running():
    # Test Swim critique
    swim_act = {"name": "泳池游泳", "sport_type": "Swim", "distance_meters": 2000.0}
    swim_critique = LocalStore.generate_canova_critique(swim_act)
    assert "游泳" in swim_critique
    assert "交叉训练" in swim_critique
    assert "不计入跑量统计" in swim_critique
    assert "短程奔跑" not in swim_critique

    # Test Ride critique
    ride_act = {"name": "公路骑行", "sport_type": "Ride", "distance_meters": 30000.0}
    ride_critique = LocalStore.generate_canova_critique(ride_act)
    assert "骑行" in ride_critique
    assert "交叉训练" in ride_critique
    assert "不计入跑量统计" in ride_critique
    assert "短程奔跑" not in ride_critique
