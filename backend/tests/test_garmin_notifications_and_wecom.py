"""
Unit tests for Garmin notification dispatch and WeCom monthly stats calculations.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timedelta
from tests import MockFirestoreDB, MockDocRef, MockDocSnapshot, MockCollectionRef


def test_garmin_sync_triggers_notification():
    """Verify sync_garmin_user_data triggers notification for recent activities."""
    from routers.sync import sync_garmin_user_data
    from utils.encryption import encrypt_string

    today_str = date.today().isoformat()
    mock_activities = [
        {
            "id": "garmin_99991",
            "activity_id": "garmin_99991",
            "garmin_raw_id": "99991",
            "name": "Today Garmin Run",
            "start_date_local": f"{today_str}T07:00:00",
            "distance_km": 10.0,
            "moving_time": 3000,
            "avg_pace": "5:00",
            "avg_heart_rate": 150,
            "activity_type": "run",
            "source": "garmin",
        }
    ]

    mock_db = MockFirestoreDB()
    user_ref = MockDocRef(data={"display_name": "Runner A", "email": "a@example.com"}, doc_id="user_123")

    user_data = {
        "garmin_email": "test@garmin.cn",
        "garmin_encrypted_password": encrypt_string("mypassword"),
        "garmin_domain": "garmin.cn",
        "garmin_connected": True,
    }

    with patch("routers.sync.db", mock_db), \
         patch("utils.garmin_adapter.GarminAdapter.login", return_value=True), \
         patch("utils.garmin_adapter.GarminAdapter.fetch_recent_activities", return_value=mock_activities), \
         patch("utils.garmin_adapter.GarminAdapter.fetch_daily_health_metrics", return_value={}), \
         patch("routers.sync.update_user_leaderboards") as mock_lb, \
         patch("routers.sync._trigger_garmin_journal_and_notification") as mock_trigger:

        res = sync_garmin_user_data(user_data, user_ref)
        assert res["success"] is True
        assert res["count"] == 1
        mock_lb.assert_called_once()
        mock_trigger.assert_called_once_with("user_123", "garmin_99991")


def test_wecom_monthly_stats_period_start_validation():
    """Verify _fetch_user_monthly_stats validates period_start and does dynamic recalculation if expired."""
    from utils.wecom_bot import _fetch_user_monthly_stats
    from routers.sync import get_period_start

    current_month_start = get_period_start("monthly").isoformat()
    last_month_start = (get_period_start("monthly") - timedelta(days=35)).isoformat()

    # 1. Valid current month document in leaderboard
    valid_data = {
        "uid": "user_valid",
        "total_distance_km": 88.5,
        "run_count": 8,
        "avg_pace": "5:15",
        "period_start": current_month_start,
    }
    valid_doc = MockDocSnapshot(data=valid_data, exists=True, doc_id="user_valid")

    mock_db = MagicMock()
    mock_db.collection("leaderboard").document.return_value.get.return_value = valid_doc

    with patch("utils.wecom_bot.db", mock_db):
        res = _fetch_user_monthly_stats("user_valid")
        assert res["total_distance_km"] == 88.5
        assert res["run_count"] == 8

    # 2. Stale document (from last month) -> should trigger dynamic recalculation from activities
    stale_data = {
        "uid": "user_stale",
        "total_distance_km": 150.0,
        "run_count": 15,
        "avg_pace": "5:00",
        "period_start": last_month_start,
    }
    stale_doc = MockDocSnapshot(data=stale_data, exists=True, doc_id="user_stale")

    today_str = date.today().isoformat()
    mock_act_docs = [
        MockDocSnapshot(data={
            "activity_id": "act_1",
            "name": "Current Month Run",
            "start_date_local": f"{today_str}T07:00:00",
            "distance_km": 12.0,
            "moving_time": 3600,
            "avg_heart_rate": 145,
            "activity_type": "run",
            "source": "garmin",
        }, exists=True)
    ]

    mock_db.collection("leaderboard").document.return_value.get.return_value = stale_doc
    mock_db.collection("users").document.return_value.collection.return_value.where.return_value.stream.return_value = mock_act_docs

    with patch("utils.wecom_bot.db", mock_db):
        res = _fetch_user_monthly_stats("user_stale")
        assert res["total_distance_km"] == 12.0
        assert res["run_count"] == 1
        assert res["period_start"] == current_month_start


def test_wecom_fetch_monthly_leaderboard_filters_expired():
    """Verify _fetch_monthly_leaderboard resets users with old period_start to 0."""
    from utils.wecom_bot import _fetch_monthly_leaderboard
    from routers.sync import get_period_start

    current_month_start = get_period_start("monthly").isoformat()
    last_month_start = (get_period_start("monthly") - timedelta(days=35)).isoformat()

    mock_docs = [
        MockDocSnapshot(data={
            "uid": "user_active",
            "display_name": "Active Runner",
            "total_distance_km": 50.0,
            "period_start": current_month_start,
        }, exists=True),
        MockDocSnapshot(data={
            "uid": "user_old",
            "display_name": "Old Runner",
            "total_distance_km": 200.0,
            "period_start": last_month_start,
        }, exists=True),
    ]

    mock_db = MagicMock()
    mock_db.collection("leaderboard").stream.return_value = mock_docs

    with patch("utils.wecom_bot.db", mock_db):
        entries = _fetch_monthly_leaderboard(10)
        assert len(entries) == 1
        assert entries[0]["uid"] == "user_active"
        assert entries[0]["total_distance_km"] == 50.0


def test_coach_weekly_progress_deduplication():
    """Verify deduplication works correctly when calculating weekly progress across Garmin and Strava."""
    from utils.activity_utils import deduplicate_activities
    from routers.sync import get_period_start

    week_start_dt = get_period_start("weekly")
    week_start_str = week_start_dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Simulate 5 distinct days with duplicate Garmin and Strava entries
    activities = [
        {"activity_id": "garmin_1", "start_date_local": f"{week_start_str[:10]}T07:00:00", "distance_km": 10.0, "source": "garmin", "activity_type": "run"},
        {"activity_id": "strava_1", "start_date_local": f"{week_start_str[:10]}T07:00:00Z", "distance_km": 10.0, "source": "strava", "activity_type": "run"},
        {"activity_id": "garmin_2", "start_date_local": f"{week_start_str[:10]}T19:00:00", "distance_km": 5.0, "source": "garmin", "activity_type": "run"},
        {"activity_id": "strava_2", "start_date_local": f"{week_start_str[:10]}T19:00:00Z", "distance_km": 5.0, "source": "strava", "activity_type": "run"},
        {"activity_id": "garmin_3", "start_date_local": f"{week_start_str[:10]}T08:00:00", "distance_km": 0.0, "source": "garmin", "activity_type": "cross_training"},
        {"activity_id": "apple_1", "start_date_local": f"{week_start_str[:10]}T09:00:00", "distance_km": 3.0, "source": "AppleHealth", "activity_type": "run"},
    ]

    deduped = deduplicate_activities(activities)
    runs = [a for a in deduped if a.get("activity_type", "run") == "run" and a.get("source") != "AppleHealth"]

    week_km = round(sum(float(a.get("distance_km", 0) or 0) for a in runs), 2)
    week_runs = len(runs)

    assert week_km == 15.0
    assert week_runs == 2

