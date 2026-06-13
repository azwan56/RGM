import os
import sys
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from routers.coach import (
    group_activities_into_sessions,
    aggregate_activities,
    merge_stream_stats,
    _build_runs_str
)

def test_group_activities_into_sessions():
    # Setup mock activities
    # Act 1: 08:00:00 -> 08:15:00
    act1 = {
        "activity_id": "act1",
        "name": "Warmup",
        "start_date_local": "2026-06-13T08:00:00",
        "elapsed_time": 900,  # 15 mins
        "distance_km": 2.0
    }
    # Act 2: 08:20:00 (5 mins gap)
    act2 = {
        "activity_id": "act2",
        "name": "Main Run",
        "start_date_local": "2026-06-13T08:20:00",
        "elapsed_time": 3600,  # 60 mins
        "distance_km": 10.0
    }
    # Act 3: 09:40:00 (20 mins gap from Act 2 end 09:20:00)
    act3 = {
        "activity_id": "act3",
        "name": "Cool down",
        "start_date_local": "2026-06-13T09:40:00",
        "elapsed_time": 600,  # 10 mins
        "distance_km": 2.0
    }

    activities = [act1, act2, act3]
    sessions = group_activities_into_sessions(activities)

    # Act 1 and Act 2 should be grouped together (5 mins gap <= 15 mins)
    # Act 3 should be in a separate session (20 mins gap > 15 mins)
    assert len(sessions) == 2
    assert len(sessions[0]) == 2
    assert sessions[0][0]["activity_id"] == "act1"
    assert sessions[0][1]["activity_id"] == "act2"
    assert len(sessions[1]) == 1
    assert sessions[1][0]["activity_id"] == "act3"

def test_aggregate_activities():
    # Session: Warmup + Main Run
    act1 = {
        "activity_id": 111,
        "name": "Warmup",
        "start_date_local": "2026-06-13T08:00:00",
        "moving_time": 600,
        "elapsed_time": 600,
        "distance_km": 2.0,
        "avg_heart_rate": 120,
        "max_heart_rate": 140,
        "avg_cadence": 160,
        "activity_type": "run",
        "splits_metric": [{"distance": 1000, "elapsed_time": 300}, {"distance": 1000, "elapsed_time": 300}],
        "stream_stats": {
            "pace_splits": [{"km": 1, "pace": "5:00"}, {"km": 2, "pace": "5:00"}]
        }
    }
    act2 = {
        "activity_id": 222,
        "name": "Main Run",
        "start_date_local": "2026-06-13T08:10:00",
        "moving_time": 1800,
        "elapsed_time": 1800,
        "distance_km": 4.0,
        "avg_heart_rate": 160,
        "max_heart_rate": 180,
        "avg_cadence": 180,
        "activity_type": "run",
        "splits_metric": [{"distance": 1000, "elapsed_time": 270}],
        "stream_stats": {
            "pace_splits": [{"km": 1, "pace": "4:30"}, {"km": 2, "pace": "4:30"}]
        }
    }

    agg = aggregate_activities([act1, act2])

    assert agg["is_composite"] is True
    assert agg["activity_id"] == 111  # canonical ID is the first activity
    assert agg["name"] == "Warmup + Main Run"
    assert agg["distance_km"] == 6.0
    assert agg["moving_time"] == 2400
    assert agg["elapsed_time"] == 2400
    assert agg["max_heart_rate"] == 180
    
    # Weighted HR: (120*600 + 160*1800) / 2400 = (72000 + 288000) / 2400 = 360000 / 2400 = 150
    assert agg["avg_heart_rate"] == 150
    
    # Weighted Cadence: (160*600 + 180*1800) / 2400 = (96000 + 324000) / 2400 = 420000 / 2400 = 175
    assert agg["avg_cadence"] == 175

    # Check merged stream splits (K1, K2 from act1, K3, K4 from act2)
    pace_splits = agg["stream_stats"]["pace_splits"]
    assert len(pace_splits) == 4
    assert pace_splits[0]["km"] == 1
    assert pace_splits[0]["pace"] == "5:00"
    assert pace_splits[2]["km"] == 3
    assert pace_splits[2]["pace"] == "4:30"

def test_build_runs_str():
    act1 = {
        "activity_id": 111,
        "name": "Warmup",
        "start_date_local": "2026-06-13T08:00:00",
        "moving_time": 600,
        "elapsed_time": 600,
        "distance_km": 2.0,
        "avg_heart_rate": 120,
        "avg_pace": "5:00"
    }
    act2 = {
        "activity_id": 222,
        "name": "Main Run",
        "start_date_local": "2026-06-13T08:10:00",
        "moving_time": 1800,
        "elapsed_time": 1800,
        "distance_km": 4.0,
        "avg_heart_rate": 160,
        "avg_pace": "4:30"
    }

    result = _build_runs_str([act1, act2])
    # Should build a composite runs string
    assert "大课组合训练" in result
    assert "总共6.00km" in result
    assert "包含: Warmup(2.0km,配速5:00) + Main Run(4.0km,配速4:30)" in result
