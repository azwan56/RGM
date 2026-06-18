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

def test_group_activities_into_sessions_same_type():
    """Same-type activities within 30-min gap should be grouped."""
    # Act 1: 08:00:00 -> 08:15:00 (Run)
    act1 = {
        "activity_id": "act1",
        "name": "Warmup",
        "start_date_local": "2026-06-13T08:00:00",
        "elapsed_time": 900,  # 15 mins
        "distance_km": 2.0,
        "activity_type": "run"
    }
    # Act 2: 08:20:00 (5 mins gap from Act 1 end, also Run)
    act2 = {
        "activity_id": "act2",
        "name": "Main Run",
        "start_date_local": "2026-06-13T08:20:00",
        "elapsed_time": 3600,  # 60 mins
        "distance_km": 10.0,
        "activity_type": "run"
    }
    # Act 3: 09:50:00 (30 mins gap from Act 2 end 09:20:00, also Run — exactly at 30 min boundary)
    act3 = {
        "activity_id": "act3",
        "name": "Cool down",
        "start_date_local": "2026-06-13T09:50:00",
        "elapsed_time": 600,  # 10 mins
        "distance_km": 2.0,
        "activity_type": "run"
    }

    activities = [act1, act2, act3]
    sessions = group_activities_into_sessions(activities)

    # All three should be grouped (5 min gap + 30 min gap, both <= 30 min)
    assert len(sessions) == 1
    assert len(sessions[0]) == 3


def test_group_activities_into_sessions_gap_too_large():
    """Same-type activities with gap > 30 min should NOT be grouped."""
    act1 = {
        "activity_id": "act1",
        "name": "Morning Run",
        "start_date_local": "2026-06-13T06:00:00",
        "elapsed_time": 1800,  # 30 mins -> ends at 06:30
        "distance_km": 5.0,
        "activity_type": "run"
    }
    # Act 2 starts at 07:01 -> gap = 31 min (> 30 min)
    act2 = {
        "activity_id": "act2",
        "name": "Evening Run",
        "start_date_local": "2026-06-13T07:01:00",
        "elapsed_time": 1800,
        "distance_km": 5.0,
        "activity_type": "run"
    }

    sessions = group_activities_into_sessions([act1, act2])
    assert len(sessions) == 2


def test_group_activities_different_types_not_merged():
    """Different activity types should NEVER be merged, even if gap is small."""
    # Run: 08:00 -> 08:52 (52 mins)
    run_act = {
        "activity_id": "run1",
        "name": "晨间跑步",
        "start_date_local": "2026-06-18T08:00:00",
        "elapsed_time": 3141,  # ~52 mins
        "distance_km": 9.02,
        "activity_type": "run",
        "sport_type": "Run"
    }
    # WeightTraining: 08:55 (3 min gap — very close!) -> 09:33
    weight_act = {
        "activity_id": "wt1",
        "name": "Lunch Weight Training",
        "start_date_local": "2026-06-18T08:55:00",
        "elapsed_time": 2318,  # ~38 mins
        "distance_km": 0.0,
        "activity_type": "cross_training",
        "sport_type": "WeightTraining"
    }

    sessions = group_activities_into_sessions([run_act, weight_act])

    # Must be 2 separate sessions — different types
    assert len(sessions) == 2
    assert sessions[0][0]["activity_id"] == "run1"
    assert sessions[1][0]["activity_id"] == "wt1"


def test_group_activities_mixed_types_interleaved():
    """Run + WeightTraining + Run should produce 3 separate sessions."""
    run1 = {
        "activity_id": "r1",
        "name": "Run 1",
        "start_date_local": "2026-06-18T07:00:00",
        "elapsed_time": 1800,
        "distance_km": 5.0,
        "activity_type": "run"
    }
    weight = {
        "activity_id": "w1",
        "name": "Weights",
        "start_date_local": "2026-06-18T07:35:00",
        "elapsed_time": 2400,
        "distance_km": 0.0,
        "activity_type": "cross_training"
    }
    run2 = {
        "activity_id": "r2",
        "name": "Run 2",
        "start_date_local": "2026-06-18T08:20:00",
        "elapsed_time": 1200,
        "distance_km": 3.0,
        "activity_type": "run"
    }

    sessions = group_activities_into_sessions([run1, weight, run2])
    assert len(sessions) == 3


def test_group_activities_error_fallback_creates_new_session():
    """When date parsing fails, the activity should start a new session (not merge blindly)."""
    act1 = {
        "activity_id": "a1",
        "name": "Good Run",
        "start_date_local": "2026-06-13T08:00:00",
        "elapsed_time": 900,
        "activity_type": "run"
    }
    act2 = {
        "activity_id": "a2",
        "name": "Bad Date Run",
        "start_date_local": "INVALID_DATE",
        "elapsed_time": 900,
        "activity_type": "run"
    }

    sessions = group_activities_into_sessions([act1, act2])
    # Should NOT blindly merge on error — creates separate session
    assert len(sessions) == 2


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

def test_build_runs_str_same_type():
    """Same-type activities within gap should show as composite."""
    act1 = {
        "activity_id": 111,
        "name": "Warmup",
        "start_date_local": "2026-06-13T08:00:00",
        "moving_time": 600,
        "elapsed_time": 600,
        "distance_km": 2.0,
        "avg_heart_rate": 120,
        "avg_pace": "5:00",
        "activity_type": "run"
    }
    act2 = {
        "activity_id": 222,
        "name": "Main Run",
        "start_date_local": "2026-06-13T08:10:00",
        "moving_time": 1800,
        "elapsed_time": 1800,
        "distance_km": 4.0,
        "avg_heart_rate": 160,
        "avg_pace": "4:30",
        "activity_type": "run"
    }

    result = _build_runs_str([act1, act2])
    # Should build a composite runs string
    assert "大课组合训练" in result
    assert "总共6.00km" in result
    assert "包含: Warmup(2.0km,配速5:00) + Main Run(4.0km,配速4:30)" in result


def test_build_runs_str_different_types_not_merged():
    """Different-type activities should appear as separate entries, not combined."""
    run_act = {
        "activity_id": 111,
        "name": "晨间跑步",
        "start_date_local": "2026-06-18T08:00:00",
        "moving_time": 3141,
        "elapsed_time": 3141,
        "distance_km": 9.02,
        "avg_heart_rate": 140,
        "avg_pace": "5:48",
        "total_elevation_gain": 29.0,
        "activity_type": "run"
    }
    weight_act = {
        "activity_id": 222,
        "name": "Lunch Weight Training",
        "start_date_local": "2026-06-18T08:55:00",
        "moving_time": 2318,
        "elapsed_time": 2318,
        "distance_km": 0.0,
        "avg_heart_rate": 100,
        "avg_pace": "—",
        "total_elevation_gain": 0.0,
        "activity_type": "cross_training"
    }

    result = _build_runs_str([run_act, weight_act])
    # Should NOT contain composite training markers
    assert "大课组合训练" not in result
    # Each activity should appear separately
    assert "晨间跑步" in result
    assert "Lunch Weight Training" in result
