import pytest
import os
import sqlite3
import json
from datetime import date
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore

client = TestClient(app)

TEST_UID = "u_align_test_123"
TEST_EMAIL = "align_runner@example.com"

@pytest.fixture(autouse=True)
def setup_test_runner():
    # Insert test user profile
    LocalStore.upsert_profile(TEST_UID, {
        "email": TEST_EMAIL,
        "display_name": "对齐测试跑者",
        "gender": "male",
        "date_of_birth": "1980-05-15",
        "vo2max": 48.0,
        "marathon_pb": 12600, # 3:30:00
        "half_pb": 5700
    })

    # Set custom user goals: 60km/week, 240km/month
    LocalStore.upsert_goal(TEST_UID, {
        "weekly_target": 60.0,
        "target_distance": 240.0,
        "period_type": "monthly",
        "monthly_targets": [240.0] * 12
    })

    yield

    # Cleanup test data
    with sqlite3.connect(LocalStore.get_db_path() if hasattr(LocalStore, "get_db_path") else "data/rgm.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM goals WHERE user_id = ? OR user_id = ?", (TEST_UID, TEST_EMAIL))
        c.execute("DELETE FROM profiles WHERE id = ? OR email = ?", (TEST_UID, TEST_EMAIL))
        c.execute("DELETE FROM training_plans WHERE user_id = ? OR user_id = ?", (TEST_UID, TEST_EMAIL))
        conn.commit()


def test_goal_resolution_and_retrieval():
    """Verify LocalStore resolves goal by both canonical_uid and email."""
    goal_by_uid = LocalStore.get_goal(TEST_UID)
    assert goal_by_uid is not None
    assert float(goal_by_uid["weekly_target"]) == 60.0
    assert float(goal_by_uid["target_distance"]) == 240.0

    goal_by_email = LocalStore.get_goal(TEST_EMAIL)
    assert goal_by_email is not None
    assert float(goal_by_email["weekly_target"]) == 60.0


def test_plan_generation_anchoring_and_alignment():
    """Verify training plan generation anchors to the runner's weekly target."""
    req_payload = {
        "athlete_uid": TEST_UID,
        "goal_type": "race_prep",
        "target_race_name": "杭州马拉松",
        "target_time": "3:25:00",
        "race_type": "marathon",
        "weeks_count": 8,
        "days_per_week": 4,
        "user_weekly_target": 60.0
    }
    resp = client.post("/api/coach/plan/generate", json=req_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    plan = data["plan"]
    assert plan is not None

    schedule = plan.get("schedule_data", {})
    weeks = schedule.get("weeks", [])
    assert len(weeks) == 8

    # Alignment metadata should be present
    alignment = schedule.get("user_goal_alignment")
    assert alignment is not None
    assert float(alignment["weekly_target"]) == 60.0

    # Week 1 mileage should be anchored reasonably close to 60km (e.g. within 45~70km)
    week1_km = float(weeks[0]["weekly_mileage_km"])
    assert 45.0 <= week1_km <= 70.0


def test_sync_plan_to_goals_endpoint():
    """Verify POST /api/coach/plan/{plan_id}/sync-to-goals updates the goals table."""
    # First generate plan with 45km/week
    req_payload = {
        "athlete_uid": TEST_UID,
        "goal_type": "fitness_maintenance",
        "maintenance_focus": "aerobic_base",
        "weeks_count": 6,
        "days_per_week": 4,
        "user_weekly_target": 45.0
    }
    gen_resp = client.post("/api/coach/plan/generate", json=req_payload)
    assert gen_resp.status_code == 200
    plan_id = gen_resp.json()["plan"]["id"]

    # Now call sync-to-goals
    sync_resp = client.post(f"/api/coach/plan/{plan_id}/sync-to-goals", json={"user_id": TEST_UID})
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["success"] is True
    assert "weekly_target" in sync_data
    new_weekly_tgt = float(sync_data["weekly_target"])

    # Verify that goals in DB actually updated
    updated_goal = LocalStore.get_goal(TEST_UID)
    assert float(updated_goal["weekly_target"]) == new_weekly_tgt
    assert float(updated_goal["target_distance"]) == float(sync_data["monthly_target"])


def test_get_user_plan_returns_goal():
    """Verify GET /api/coach/plan/user/{uid} returns user_goal."""
    resp = client.get(f"/api/coach/plan/user/{TEST_UID}")
    assert resp.status_code == 200
    data = resp.json()
    assert "user_goal" in data
    assert float(data["user_goal"]["weekly_target"]) > 0
