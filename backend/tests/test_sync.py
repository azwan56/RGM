"""
Tests for the sync router — core data synchronization logic.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Set env vars before import
os.environ.setdefault("STRAVA_CLIENT_ID", "test_id")
os.environ.setdefault("STRAVA_CLIENT_SECRET", "test_secret")


class TestPaceStr:
    """Unit tests for pace string calculation."""

    def test_normal_pace(self):
        from routers.sync import pace_str
        # 10km in 50 min = 5:00/km
        result = pace_str(10000, 3000)
        assert result == "5:00"

    def test_slow_pace(self):
        from routers.sync import pace_str
        # 5km in 40 min = 8:00/km
        result = pace_str(5000, 2400)
        assert result == "8:00"

    def test_fast_pace(self):
        from routers.sync import pace_str
        # 10km in 35 min = 3:30/km
        result = pace_str(10000, 2100)
        assert result == "3:30"

    def test_zero_distance(self):
        from routers.sync import pace_str
        result = pace_str(0, 3000)
        assert result == "—"

    def test_zero_time(self):
        from routers.sync import pace_str
        result = pace_str(10000, 0)
        assert result == "—"

    def test_negative_distance(self):
        from routers.sync import pace_str
        result = pace_str(-100, 600)
        assert result == "—"


class TestFormatDuration:
    """Unit tests for duration formatting."""

    def test_hours(self):
        from routers.sync import format_duration
        assert format_duration(3661) == "1:01:01"

    def test_minutes_only(self):
        from routers.sync import format_duration
        assert format_duration(305) == "5:05"

    def test_zero(self):
        from routers.sync import format_duration
        assert format_duration(0) == "0:00"


class TestBuildActDoc:
    """Unit tests for Strava activity → Firestore doc conversion."""

    def test_normal_run(self):
        from routers.sync import _build_act_doc
        from datetime import datetime

        act = {
            "id": 123456,
            "name": "Morning Run",
            "start_date_local": "2026-04-14T07:30:00Z",
            "distance": 10000.0,
            "moving_time": 3000,
            "elapsed_time": 3200,
            "average_speed": 3.33,
            "max_speed": 4.5,
            "average_heartrate": 155,
            "max_heartrate": 178,
            "has_heartrate": True,
            "total_elevation_gain": 45,
            "average_cadence": 85,
            "achievement_count": 2,
            "kudos_count": 5,
            "map": {"summary_polyline": "abc123"},
        }
        period_start = datetime(2026, 4, 1, 0, 0, 0)

        doc = _build_act_doc(act, "monthly", period_start)

        assert doc["activity_id"] == 123456
        assert doc["distance_km"] == 10.0
        assert doc["moving_time"] == 3000
        assert doc["avg_pace"] == "5:00"
        assert doc["avg_heart_rate"] == 155
        assert doc["has_heartrate"] is True
        assert doc["avg_cadence"] == 170  # 85 * 2
        assert doc["period"] == "monthly"
        assert doc["summary_polyline"] == "abc123"

    def test_no_heartrate(self):
        from routers.sync import _build_act_doc
        from datetime import datetime

        act = {
            "id": 999,
            "distance": 5000,
            "moving_time": 1500,
            "has_heartrate": False,
            "map": {},
        }
        period_start = datetime(2026, 4, 1)
        doc = _build_act_doc(act, "weekly", period_start)

        assert doc["avg_heart_rate"] == 0
        assert doc["has_heartrate"] is False
        assert doc["summary_polyline"] == ""

    def test_zero_distance(self):
        from routers.sync import _build_act_doc
        from datetime import datetime

        act = {"id": 1, "distance": 0, "moving_time": 0, "map": {}}
        period_start = datetime(2026, 1, 1)
        doc = _build_act_doc(act, "monthly", period_start)

        assert doc["distance_km"] == 0
        assert doc["avg_pace"] == "—"


class TestGetPeriodStart:
    """Unit tests for period start calculation."""

    def test_monthly(self):
        from routers.sync import get_period_start
        result = get_period_start("monthly")
        today = date.today()
        assert result.year == today.year
        assert result.month == today.month
        assert result.day == 1

    def test_weekly(self):
        from routers.sync import get_period_start
        result = get_period_start("weekly")
        # Should be a Monday
        assert result.weekday() == 0

    def test_default_is_monthly(self):
        from routers.sync import get_period_start
        result = get_period_start("unknown")
        today = date.today()
        assert result.day == 1
