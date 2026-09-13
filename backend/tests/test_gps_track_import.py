import pytest
import json
from unittest.mock import MagicMock, patch
from utils.geo_utils import wgs84_to_gcj02, downsample_points, out_of_china
from utils.local_store import LocalStore, init_db
from utils.garmin_adapter import GarminAdapter
from fastapi.testclient import TestClient
from main import app

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()

def test_wgs84_to_gcj02_conversion():
    # Test coordinate in China (Wugong Mountain)
    wgs_lat, wgs_lng = 27.493589, 114.123498
    gcj_lat, gcj_lng = wgs84_to_gcj02(wgs_lat, wgs_lng)
    
    assert not out_of_china(wgs_lng, wgs_lat)
    assert round(gcj_lat, 2) == 27.49
    assert round(gcj_lng, 2) == 114.13
    # Ensure there is an offset from raw WGS84
    assert gcj_lat != wgs_lat
    assert gcj_lng != wgs_lng

    # Test coordinate outside China (e.g. New York)
    ny_lat, ny_lng = 40.7128, -74.0060
    assert out_of_china(ny_lng, ny_lat)
    res_lat, res_lng = wgs84_to_gcj02(ny_lat, ny_lng)
    assert res_lat == ny_lat
    assert res_lng == ny_lng

def test_downsample_points():
    points = [{"latitude": i * 0.01, "longitude": i * 0.01} for i in range(500)]
    downsampled = downsample_points(points, max_points=100)
    assert len(downsampled) == 100
    assert downsampled[0] == points[0]
    assert downsampled[-1] == points[-1]

    # Fewer points than max_points should remain intact
    few = [{"latitude": 1, "longitude": 2}]
    assert downsample_points(few, max_points=100) == few

def test_local_store_gps_track():
    test_act_id = "test_gps_act_999"
    test_track = {
        "activity_id": test_act_id,
        "total_points": 2,
        "center": {"latitude": 27.49, "longitude": 114.12},
        "points": [
            {"latitude": 27.49, "longitude": 114.12},
            {"latitude": 27.50, "longitude": 114.13}
        ],
        "elevation_profile": [
            {"dist_km": 0.0, "elevation_m": 400.0},
            {"dist_km": 1.0, "elevation_m": 450.0}
        ]
    }
    
    act_data = {
        "id": test_act_id,
        "user_id": "u_test_runner_gps",
        "name": "武功山越野测试",
        "sport_type": "Run",
        "start_time": "2026-09-12T07:00:00+08:00",
        "distance_meters": 58980.0,
        "moving_time_seconds": 36000,
        "elevation_gain_meters": 4159.0,
        "gps_track_data": test_track,
        "map_image_url": "https://example.com/map.jpg"
    }
    LocalStore.upsert_activity(act_data)

    retrieved = LocalStore.get_activity_gps_track(test_act_id)
    assert retrieved is not None
    assert retrieved["id"] == test_act_id
    assert retrieved["map_image_url"] == "https://example.com/map.jpg"
    assert isinstance(retrieved["gps_track_data"], dict)
    assert retrieved["gps_track_data"]["total_points"] == 2
    assert len(retrieved["gps_track_data"]["points"]) == 2

def test_miniapp_track_api():
    client = TestClient(app)
    
    # Query the activity saved in the previous test
    resp = client.get("/api/miniapp/activities/test_gps_act_999/track")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["has_track"] is True
    assert data["track"]["total_points"] == 2
    assert data["activity"]["distance_km"] == 58.98
    assert data["activity"]["elevation_gain_meters"] == 4159.0
