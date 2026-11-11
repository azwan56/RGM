import time
import pytest
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore, DB_PATH
import sqlite3

client = TestClient(app)

def test_club_event_creator_and_repeat_weekly():
    ts = int(time.time() * 1000)
    owner_uid = f"owner_evt_{ts}"
    runner_uid = f"runner_evt_{ts}"

    # 1. Setup profiles
    LocalStore.upsert_profile(owner_uid, {"display_name": "老团长", "email": f"owner_{ts}@test.com"})
    LocalStore.upsert_profile(runner_uid, {"display_name": "领跑员小李", "email": f"runner_{ts}@test.com"})

    # 2. Create club
    club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"例跑测试跑团_{ts}",
        description="测试重复例跑与发起人标识",
        city="上海"
    )
    club_id = club["id"]

    # 3. Add runner to club as coach/member
    LocalStore.join_club_by_id(user_id=runner_uid, club_id=club_id, privacy_consent=True)

    # 4. Runner creates a recurring weekly group run (repeat_weeks = 4)
    start_date = (date.today() + timedelta(days=2)).isoformat() # say Saturday
    create_res = client.post(f"/api/team/{club_id}/events", json={
        "operator_uid": runner_uid,
        "title": "世纪公园周六例跑",
        "event_type": "group_run",
        "start_date": start_date,
        "meet_time": f"{start_date} 07:00",
        "location": "世纪公园1号门",
        "target_km": 15.0,
        "pace_requirement": "5:30 /km",
        "repeat_rule": "weekly",
        "repeat_weeks": 4,
        "rules": "自带水壶，跑后拉伸"
    })
    assert create_res.status_code == 200, f"Create event failed: {create_res.text}"
    assert "未来 4 周" in create_res.json()["message"]

    # 5. Fetch events list and verify creator info and recurrence
    events_res = client.get(f"/api/team/{club_id}/events?user_id={runner_uid}")
    assert events_res.status_code == 200
    events = events_res.json()["events"]
    assert len(events) == 4

    # Check creator info on all generated sessions
    group_ids = set()
    for ev in events:
        assert ev["creator_name"] == "领跑员小李"
        assert ev["creator_id"] == runner_uid
        assert ev["creator_role"] in ("团长", "教练", "发起人")
        assert ev["repeat_rule"] == "weekly"
        assert ev["is_joined"] is True # Creator automatically joined!
        assert ev["repeat_group_id"] is not None
        group_ids.add(ev["repeat_group_id"])

    assert len(group_ids) == 1 # All 4 belong to same recurring group

    # Verify dates are spaced 7 days apart
    dates = sorted([ev["start_date"] for ev in events])
    d0 = datetime.strptime(dates[0], "%Y-%m-%d").date()
    d1 = datetime.strptime(dates[1], "%Y-%m-%d").date()
    d2 = datetime.strptime(dates[2], "%Y-%m-%d").date()
    d3 = datetime.strptime(dates[3], "%Y-%m-%d").date()
    assert (d1 - d0).days == 7
    assert (d2 - d1).days == 7
    assert (d3 - d2).days == 7

    # 6. Test legacy event fallback to owner_id
    legacy_evt_id = f"legacy_evt_{ts}"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO club_events (id, club_id, title, event_type, start_date, meet_time, location, creator_id, created_at)
            VALUES (?, ?, ?, 'group_run', ?, ?, '老地点', NULL, '2026-01-01T00:00:00Z')
        """, (legacy_evt_id, club_id, "历史无发起人约跑", start_date, f"{start_date} 08:00"))
        conn.commit()

    events_res2 = client.get(f"/api/team/{club_id}/events?user_id={owner_uid}")
    evs2 = events_res2.json()["events"]
    legacy_ev = next(e for e in evs2 if e["id"] == legacy_evt_id)
    assert legacy_ev["creator_name"] == "老团长" # Fallback to owner!
    assert legacy_ev["creator_role"] == "团长"
