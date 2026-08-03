import pytest
from utils.activity_utils import deduplicate_activities

def test_deduplicate_garmin_and_strava():
    activities = [
        {
            "id": "strava_123",
            "source": "strava",
            "name": "Morning Run",
            "start_date_local": "2026-08-02T06:57:00",
            "distance_km": 16.01,
            "moving_time": 5900,
        },
        {
            "id": "garmin_456",
            "source": "garmin",
            "name": "闵行区 跑步",
            "start_date_local": "2026-08-02T06:57:00",
            "distance_km": 16.01,
            "moving_time": 5900,
        },
        {
            "id": "garmin_789",
            "source": "garmin",
            "name": "闵行区 跑步",
            "start_date_local": "2026-08-01T06:08:00",
            "distance_km": 12.49,
            "moving_time": 4500,
        },
        {
            "id": "strava_999",
            "source": "strava",
            "name": "Morning Run",
            "start_date_local": "2026-08-01T06:08:00",
            "distance_km": 12.49,
            "moving_time": 4500,
        },
    ]

    deduped = deduplicate_activities(activities)
    assert len(deduped) == 2
    sources = [a["source"] for a in deduped]
    assert sources == ["garmin", "garmin"]
    distances = [a["distance_km"] for a in deduped]
    assert distances == [16.01, 12.49]
