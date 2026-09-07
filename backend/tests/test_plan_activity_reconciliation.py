import pytest
import sqlite3
import json
from datetime import datetime, timedelta
from utils.local_store import LocalStore, DB_PATH

TEST_UID = "u_reconcile_test_user"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Setup test runner profile
    LocalStore.upsert_profile(TEST_UID, {
        "id": TEST_UID,
        "display_name": "打卡测试跑者",
        "gender": "male"
    })

    yield

    # Teardown
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM activities WHERE user_id = ?", (TEST_UID,))
        c.execute("DELETE FROM training_plans WHERE user_id = ?", (TEST_UID,))
        c.execute("DELETE FROM profiles WHERE id = ?", (TEST_UID,))
        conn.commit()


def test_reconciliation_auto_match_and_missed_red_x():
    now_beijing = datetime.utcnow() + timedelta(hours=8)
    today_str = now_beijing.strftime("%Y-%m-%d")
    d_minus_3 = (now_beijing - timedelta(days=3)).strftime("%Y-%m-%d")
    d_minus_2 = (now_beijing - timedelta(days=2)).strftime("%Y-%m-%d")
    d_minus_1 = (now_beijing - timedelta(days=1)).strftime("%Y-%m-%d")
    d_plus_1 = (now_beijing + timedelta(days=1)).strftime("%Y-%m-%d")

    plan_id = "tp_test_reconcile_01"
    schedule_data = {
        "weeks": [
            {
                "week_index": 1,
                "week_title": "第 1 周：基础有氧建立",
                "weekly_mileage_km": 25.0,
                "days": [
                    {
                        "day_of_week": "周一",
                        "date": d_minus_3,
                        "workout_type": "easy_run",
                        "title": "轻松跑 6km",
                        "distance_km": 6.0,
                        "completed": False
                    },
                    {
                        "day_of_week": "周二",
                        "date": d_minus_2,
                        "workout_type": "rest",
                        "title": "休息与恢复",
                        "distance_km": 0.0,
                        "completed": False
                    },
                    {
                        "day_of_week": "周三",
                        "date": d_minus_1,
                        "workout_type": "tempo",
                        "title": "节奏跑 7km",
                        "distance_km": 7.0,
                        "completed": False
                    },
                    {
                        "day_of_week": "周四",
                        "date": today_str,
                        "workout_type": "easy_run",
                        "title": "今天计划跑 5km",
                        "distance_km": 5.0,
                        "completed": False
                    },
                    {
                        "day_of_week": "周五",
                        "date": d_plus_1,
                        "workout_type": "easy_run",
                        "title": "明天计划跑 7km",
                        "distance_km": 7.0,
                        "completed": False
                    }
                ]
            }
        ]
    }

    # 1. Save plan in DB
    LocalStore.save_training_plan({
        "id": plan_id,
        "user_id": TEST_UID,
        "title": "对齐测试计划",
        "goal_type": "fitness_maintenance",
        "start_date": d_minus_3,
        "weeks_count": 1,
        "status": "active",
        "schedule_data": schedule_data
    })

    # 2. Insert an activity on d_minus_3: 6.2km, avg_pace 5'15"
    LocalStore.upsert_activity({
        "id": "act_test_01",
        "user_id": TEST_UID,
        "name": "晨间轻松跑",
        "sport_type": "Run",
        "start_time": f"{d_minus_3}T06:30:00Z",
        "distance_meters": 6200.0,
        "moving_time_seconds": 1953,
        "avg_pace_str": "5'15\"",
        "average_heartrate": 145
    })

    # 3. Retrieve plan using get_training_plan (reconcile=True)
    plan = LocalStore.get_training_plan(plan_id)
    assert plan is not None
    days = plan["schedule_data"]["weeks"][0]["days"]

    # Day 0 (d_minus_3, easy run): Had activity -> should be auto completed!
    day0 = days[0]
    assert day0["date"] == d_minus_3
    assert day0["completed"] is True
    assert day0.get("auto_matched") is True
    assert day0.get("actual_distance_km") == 6.2
    assert day0.get("actual_pace") == "5'15\""
    assert day0.get("is_missed") is not True

    # Day 1 (d_minus_2, rest): Past rest day -> should be auto completed (rest accomplished)!
    day1 = days[1]
    assert day1["date"] == d_minus_2
    assert day1["completed"] is True
    assert day1.get("is_missed") is not True

    # Day 2 (d_minus_1, tempo 7km): Past run day with NO activity -> MISSED (Red X)!
    day2 = days[2]
    assert day2["date"] == d_minus_1
    assert day2["completed"] is False
    assert day2.get("is_missed") is True

    # Day 3 (today_str): Today -> NOT missed, waiting for execution!
    day3 = days[3]
    assert day3["date"] == today_str
    assert day3["completed"] is False
    assert day3.get("is_missed") is not True

    # Day 4 (d_plus_1): Future -> NOT missed!
    day4 = days[4]
    assert day4["date"] == d_plus_1
    assert day4["completed"] is False
    assert day4.get("is_missed") is not True


def test_manual_checkin_and_buka_on_missed_day():
    """Verify runner can click to manually 补卡 on a missed day."""
    now_beijing = datetime.utcnow() + timedelta(hours=8)
    d_past = (now_beijing - timedelta(days=2)).strftime("%Y-%m-%d")

    plan_id = "tp_test_reconcile_02"
    schedule_data = {
        "weeks": [
            {
                "week_index": 1,
                "days": [
                    {
                        "day_of_week": "周二",
                        "date": d_past,
                        "workout_type": "easy_run",
                        "title": "跑步机补跑 6km",
                        "distance_km": 6.0,
                        "completed": False
                    }
                ]
            }
        ]
    }

    LocalStore.save_training_plan({
        "id": plan_id,
        "user_id": TEST_UID,
        "title": "补卡测试计划",
        "start_date": d_past,
        "status": "active",
        "schedule_data": schedule_data
    })

    # Initially before manual check-in: should be missed
    plan = LocalStore.get_training_plan(plan_id)
    day = plan["schedule_data"]["weeks"][0]["days"][0]
    assert day["completed"] is False
    assert day["is_missed"] is True

    # Now runner manually clicks 补卡 (completed: True)
    updated = LocalStore.update_training_plan_workout(
        plan_id=plan_id,
        week_index=1,
        day_index=0,
        workout_update={"completed": True},
        operator_uid=TEST_UID
    )
    assert updated is not None
    day_after = updated["schedule_data"]["weeks"][0]["days"][0]
    assert day_after["completed"] is True
    assert day_after["is_missed"] is False
    assert day_after.get("manual_completed") is True

    # When retrieved again via API, it remains completed (does not revert to missed)
    refetched = LocalStore.get_training_plan(plan_id)
    day_refetched = refetched["schedule_data"]["weeks"][0]["days"][0]
    assert day_refetched["completed"] is True
    assert day_refetched["is_missed"] is False

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_reconciliation_and_upsert_activity_trigger():
    """Verify HTTP endpoints return reconciled plan and upsert_activity triggers reconciliation."""
    now_beijing = datetime.utcnow() + timedelta(hours=8)
    d_past = (now_beijing - timedelta(days=2)).strftime("%Y-%m-%d")
    plan_id = "tp_test_reconcile_api"

    LocalStore.upsert_training_plan({
        "id": plan_id,
        "user_id": TEST_UID,
        "title": "API对齐计划",
        "start_date": d_past,
        "status": "active",
        "schedule_data": {
            "weeks": [
                {
                    "week_index": 1,
                    "days": [
                        {
                            "day_of_week": "周二",
                            "date": d_past,
                            "workout_type": "easy_run",
                            "title": "轻松跑 8km",
                            "distance_km": 8.0,
                            "completed": False
                        }
                    ]
                }
            ]
        }
    })

    # Call GET /api/coach/plan/user/{uid}
    res = client.get(f"/api/coach/plan/user/{TEST_UID}")
    assert res.status_code == 200
    plan_data = res.json().get("active_plan")
    assert plan_data is not None
    day = plan_data["schedule_data"]["weeks"][0]["days"][0]
    # No activity yet on past run day -> missed
    assert day["completed"] is False
    assert day["is_missed"] is True

    # Now simulate activity sync arriving (e.g. Garmin/Coros adapter calls upsert_activity)
    LocalStore.upsert_activity({
        "id": "act_sync_001",
        "user_id": TEST_UID,
        "name": "佳明同步轻松跑",
        "sport_type": "Run",
        "start_time": f"{d_past}T07:15:00Z",
        "distance_meters": 8100.0,
        "moving_time_seconds": 2520,
        "avg_pace_str": "5'11\"",
        "average_heartrate": 142
    })

    # Call GET /api/coach/plan/{plan_id}
    detail_res = client.get(f"/api/coach/plan/{plan_id}")
    assert detail_res.status_code == 200
    detail_day = detail_res.json()["plan"]["schedule_data"]["weeks"][0]["days"][0]
    assert detail_day["completed"] is True
    assert detail_day["auto_matched"] is True
    assert detail_day["actual_distance_km"] == 8.1
    assert detail_day["actual_pace"] == "5'11\""
    assert detail_day["is_missed"] is False

    # Now runner manually unchecks via PATCH
    patch_res = client.patch(f"/api/coach/plan/{plan_id}/workout", json={
        "week_index": 1,
        "day_index": 0,
        "completed": False,
        "operator_uid": TEST_UID
    })
    assert patch_res.status_code == 200
    patched_day = patch_res.json()["plan"]["schedule_data"]["weeks"][0]["days"][0]
    assert patched_day["completed"] is False
    # Since it's in the past and manual_override is True, it turns back to missed
    assert patched_day["is_missed"] is True
