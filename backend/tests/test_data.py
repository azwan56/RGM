import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def test_dashboard_wtd_goal_progress():
    """Test that dashboard computes WTD distance and progress when goal_period is weekly."""
    from routers.data import get_dashboard_all
    from routers.sync import get_period_start

    uid = "test_user_123"

    user_data = {
        "email": "runner@example.com",
        "display_name": "Test Runner",
    }
    goal_data = {
        "period": "weekly",
        "target_distance": 50.0,
    }

    # Create fake runs:
    # 1 run from current week (WTD) -> 10 km
    # 1 run from earlier in the month (not in current week) -> 20 km
    week_start = get_period_start("weekly")
    wtd_date_str = (week_start + timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%S")
    mtd_only_date_str = (week_start - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")

    activities = [
        {
            "id": 1,
            "activity_type": "run",
            "distance_km": 10.0,
            "moving_time": 3600,
            "start_date_local": wtd_date_str,
            "avg_heart_rate": 140,
        },
        {
            "id": 2,
            "activity_type": "run",
            "distance_km": 20.0,
            "moving_time": 7200,
            "start_date_local": mtd_only_date_str,
            "avg_heart_rate": 145,
        },
    ]

    with patch("routers.data._read_user_doc", return_value=user_data), \
         patch("routers.data._read_goal_doc", return_value=goal_data), \
         patch("routers.data._read_leaderboard_doc", return_value=None), \
         patch("routers.data._read_leaderboard_list", return_value=[]), \
         patch("routers.data._read_activities", return_value=activities), \
         patch("routers.data._read_latest_health", return_value=None):

        result = get_dashboard_all(uid)

        stats = result["stats"]
        assert stats["period"] == "weekly"
        # Total distance should be WTD distance (10.0 km), NOT MTD distance (30.0 km)
        assert stats["total_distance_km"] == 10.0
        # Run count should be WTD count (1 run)
        assert stats["run_count"] == 1
        # Goal progress percentage should be (10.0 / 50.0) * 100 = 20%
        assert stats["goal_completion_percentage"] == 20
