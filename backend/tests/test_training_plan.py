import pytest
import sqlite3
import os
import json
from datetime import date, timedelta
from utils.local_store import LocalStore, DB_PATH
from routers.coach import (
    generate_scientific_training_plan,
    get_user_training_plan,
    update_plan_workout_item,
    GenerateTrainingPlanRequest,
    UpdateWorkoutRequest,
    generate_fallback_training_plan
)

@pytest.fixture(autouse=True)
def setup_test_runner():
    """Sets up a test athlete with real biometrics and historical activities."""
    uid = "u_test_plan_athlete"
    LocalStore.upsert_profile(uid, {
        "email": "athlete_plan_test@example.com",
        "display_name": "测试先锋跑者",
        "gender": "female",
        "date_of_birth": "1974-05-12", # 52 years old (Masters 50+)
        "vo2max": 53.5,
        "marathon_pb": 11520, # 3:12:00
        "half_pb": 5400, # 1:30:00
        "max_heart_rate": 185,
        "resting_heart_rate": 52
    })

    # Add 12-18 months of activities
    today = date.today()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Clean previous test activities
        cursor.execute("DELETE FROM activities WHERE user_id = ?", (uid,))
        cursor.execute("DELETE FROM training_plans WHERE user_id = ?", (uid,))
        
        # Insert a long run 30km from 3 months ago
        d1 = (today - timedelta(days=90)).isoformat()
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_test_1_{uid}", uid, "长距离 30km 有氧拉练", "running", f"{d1}T07:00:00", 30100, 9600, "5:18 /km", 120, 150, 220))

        # Insert a half marathon race from 6 months ago
        d2 = (today - timedelta(days=180)).isoformat()
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_test_2_{uid}", uid, "春季半程马拉松", "running", f"{d2}T08:00:00", 21100, 5460, "4:18 /km", 60, 168, 185))

        # Insert a trail run with elevation
        d3 = (today - timedelta(days=60)).isoformat()
        cursor.execute("""
            INSERT INTO activities (id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate, trimp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"act_test_3_{uid}", uid, "佘山越野爬坡拉练", "running", f"{d3}T06:30:00", 22000, 7800, "5:54 /km", 650, 152, 195))

        conn.commit()

    yield uid


def test_extract_runner_race_history(setup_test_runner):
    uid = setup_test_runner
    hist = LocalStore.extract_runner_race_history(uid, days=540)

    assert hist["total_activities_count"] >= 3
    assert hist["max_single_distance_km"] >= 30.0
    assert hist["long_runs_count"] >= 3
    assert len(hist["recent_races"]) >= 1
    assert any("半程马拉松" in r["name"] for r in hist["recent_races"])
    assert len(hist["trail_climbing_runs"]) >= 1


def test_generate_race_prep_training_plan(setup_test_runner):
    uid = setup_test_runner
    req = GenerateTrainingPlanRequest(
        athlete_uid=uid,
        goal_type="race_prep",
        target_race_name="上海马拉松",
        target_time="3:09:30",
        race_type="marathon",
        weeks_count=8,
        days_per_week=4,
        preferred_long_run_day="Sunday",
        operator_uid=uid
    )

    res = generate_scientific_training_plan(req)
    assert res["success"] is True
    plan = res["plan"]
    assert plan["id"].startswith("plan_")
    assert plan["goal_type"] == "race_prep"
    assert plan["status"] == "active"
    assert plan["weeks_count"] == 8

    sched = plan["schedule_data"]
    assert "weeks" in sched
    assert len(sched["weeks"]) == 8

    # Check week 1 and week 8 structure
    w1 = sched["weeks"][0]
    assert "days" in w1
    assert len(w1["days"]) == 7
    assert w1["weekly_mileage_km"] > 0

    # Check Sunday long run exists
    sunday_w1 = w1["days"][-1]
    assert sunday_w1["workout_type"] == "long_run"
    assert sunday_w1["distance_km"] >= 15.0


def test_generate_fitness_maintenance_training_plan(setup_test_runner):
    uid = setup_test_runner
    req = GenerateTrainingPlanRequest(
        athlete_uid=uid,
        goal_type="fitness_maintenance",
        maintenance_focus="trail_climbing",
        weeks_count=4,
        days_per_week=4,
        operator_uid=uid
    )

    res = generate_scientific_training_plan(req)
    assert res["success"] is True
    plan = res["plan"]
    assert plan["goal_type"] == "fitness_maintenance"
    assert plan["maintenance_focus"] == "trail_climbing"
    sched = plan["schedule_data"]
    assert len(sched["weeks"]) == 4


def test_collaborative_workout_editing(setup_test_runner):
    uid = setup_test_runner
    coach_uid = "u_coach_test_specialist"

    # 1. Generate plan
    gen_req = GenerateTrainingPlanRequest(
        athlete_uid=uid,
        goal_type="race_prep",
        target_race_name="上海马拉松",
        target_time="3:09:30",
        weeks_count=4,
        days_per_week=4,
        operator_uid=uid
    )
    gen_res = generate_scientific_training_plan(gen_req)
    plan_id = gen_res["plan"]["id"]

    # 2. Coach modifies Week 1, Day 1 (Tuesday Easy Run -> 12km, new target pace, adds coach notes)
    patch_req = UpdateWorkoutRequest(
        week_index=1,
        day_index=1, # Tuesday (0 is Monday, 1 is Tuesday)
        distance_km=12.5,
        target_pace="5:15 - 5:25 /km",
        coach_notes="教练建议：近期TSB处于黄金适应期，本次有氧跑距离提升至 12.5km，注意压稳心率不超过142bpm！",
        completed=True,
        operator_uid=coach_uid
    )
    patch_res = update_plan_workout_item(plan_id, patch_req)
    assert patch_res["success"] is True

    updated_plan = patch_res["plan"]
    sched = updated_plan["schedule_data"]
    tue_day = sched["weeks"][0]["days"][1]
    assert tue_day["distance_km"] == 12.5
    assert tue_day["target_pace"] == "5:15 - 5:25 /km"
    assert "教练建议" in tue_day["coach_notes"]
    assert tue_day["completed"] is True
    assert tue_day["last_modified_by"] == coach_uid

    # 3. Retrieve user plan and verify persistence
    get_res = get_user_training_plan(uid)
    active_plan = get_res["active_plan"]
    assert active_plan["id"] == plan_id
    day_retrieved = active_plan["schedule_data"]["weeks"][0]["days"][1]
    assert day_retrieved["distance_km"] == 12.5
    assert day_retrieved["completed"] is True
