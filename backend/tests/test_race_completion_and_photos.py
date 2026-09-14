import pytest
import os
import json
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore, init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_race_completion_and_finish_time():
    test_uid = "test_user_race_complete_001"
    
    # 1. Create a race plan with target time
    race_data = {
        "id": "race_test_001",
        "name": "2026 无锡马拉松",
        "race_type": "全马 (42.195K)",
        "race_date": "2026-03-22",
        "target_time": "03:30:00",
        "priority": 1
    }
    LocalStore.upsert_race_plan(test_uid, race_data)
    
    races = LocalStore.get_race_plans(test_uid)
    assert len(races) >= 1
    race = next(r for r in races if r["id"] == "race_test_001")
    assert race["status"] == "upcoming"
    assert not race["is_completed"]
    
    # 2. Complete race with actual finish time: 03:24:15 (faster than 03:30:00)
    res = client.post(
        f"/api/profile/{test_uid}/races/race_test_001/complete",
        json={
            "status": "completed",
            "finish_time": "03:24:15",
            "finish_notes": "后半程稳住配速，超额PB！",
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "races" in data
    
    updated_races = LocalStore.get_race_plans(test_uid)
    updated = next(r for r in updated_races if r["id"] == "race_test_001")
    assert updated["status"] == "completed"
    assert updated["is_completed"] is True
    assert updated["finish_time"] == "03:24:15"
    assert updated["finish_notes"] == "后半程稳住配速，超额PB！"
    assert updated["diff_seconds"] == -345  # 5 min 45 sec ahead
    assert "超额达标" in updated["performance_badge"]
    assert "-05:45" in updated["diff_str"]

def test_race_photo_base64_and_delete():
    test_uid = "test_user_race_photo_002"
    race_data = {
        "id": "race_test_002",
        "name": "崇礼168",
        "race_type": "越野跑 50K",
        "race_date": "2026-07-15",
        "target_time": "08:00:00",
        "priority": 2
    }
    LocalStore.upsert_race_plan(test_uid, race_data)
    
    # Small 1x1 transparent gif as base64
    tiny_gif = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    
    # Upload photo via Base64 (used by WeChat miniapp)
    res = client.post(
        f"/api/profile/{test_uid}/races/race_test_002/photo-base64",
        json={
            "image_base64": tiny_gif,
            "ext": ".jpg"
        }
    )
    assert res.status_code == 200
    data = res.json()
    photo_url = data["photo_url"]
    assert "/api/race-photos/" in photo_url
    assert len(data["photos"]) == 1
    
    races = LocalStore.get_race_plans(test_uid)
    race = next(r for r in races if r["id"] == "race_test_002")
    assert race["photo_url"] == photo_url
    assert photo_url in race["photos"]
    
    # Delete photo
    del_res = client.request(
        "DELETE",
        f"/api/profile/{test_uid}/races/race_test_002/photo",
        json={"photo_url": photo_url}
    )
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert photo_url not in del_data["photos"]

def test_matched_activity_lookup():
    test_uid = "test_user_race_match_003"
    import sqlite3
    from utils.local_store import DB_PATH
    
    # 1. Insert a synthetic activity on 2026-09-12
    with sqlite3.connect(DB_PATH) as conn:
        conn.cursor().execute("""
            INSERT OR REPLACE INTO activities (
                id, user_id, name, sport_type, start_time, distance_meters, moving_time_seconds, elapsed_time_seconds, avg_pace_str
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "garmin_test_wugong_001",
            test_uid,
            "武功山越野赛50K",
            "trail_running",
            "2026-09-12T06:00:00Z",
            52000.0,
            28800,
            29520,
            "9:27 /km"
        ))
        conn.commit()
        
    # 2. Add race plan for that date
    race_data = {
        "id": "race_wugong_003",
        "name": "武功山越野",
        "race_type": "越野跑 50K",
        "race_date": "2026-09-12",
        "target_time": "08:30:00",
        "priority": 1
    }
    LocalStore.upsert_race_plan(test_uid, race_data)
    
    # 3. Query matched activity endpoint
    res = client.get(f"/api/profile/{test_uid}/races/race_wugong_003/matched-activity")
    assert res.status_code == 200
    data = res.json()
    assert data["matched"] is True
    act = data["activity"]
    assert act["id"] == "garmin_test_wugong_001"
    assert act["formatted_time"] == "8:12:00"  # 29520 seconds = 8h 12m
    assert act["distance_km"] == 52.0
