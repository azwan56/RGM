import pytest
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore

client = TestClient(app)

def test_new_user_clubs_empty():
    """Verify a brand new user does not auto-join any club and has empty clubs list."""
    new_uid = "u_test_brand_new_isolated_runner_999"
    clubs = LocalStore.get_user_clubs(new_uid)
    assert clubs == [], "New user should not automatically be added to any club"
    
    # API test
    resp = client.get(f"/api/team/my-clubs/{new_uid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["clubs"] == []

def test_new_user_dashboard_empty_metrics():
    """Verify a new user with no watch connected gets 0.0 metrics and empty history."""
    new_uid = "u_test_brand_new_isolated_runner_999"
    resp = client.get(f"/api/miniapp/dashboard/{new_uid}")
    assert resp.status_code == 200
    data = resp.json()
    
    # Check fitness form is clean
    ff = data.get("fitness_form", {})
    assert ff.get("ctl") == 0.0
    assert ff.get("atl") == 0.0
    assert ff.get("tsb") == 0.0
    assert ff.get("status_label") == "未连接"
    assert ff.get("history") == []
    
    # Check progress does not show mock 119.9 km
    prog = data.get("progress", {})
    assert prog.get("current_month_km") == 0.0
    
    # Check recent activities is empty
    acts = data.get("recent_activities", [])
    assert acts == []

def test_club_dashboard_404_on_invalid_club():
    """Verify querying a non-existent club returns 404 instead of falling back to flagship club."""
    resp = client.get("/api/team/non_existent_club_xyz/dashboard")
    assert resp.status_code == 404

def test_science_metrics_empty_when_no_activities():
    """Verify science metrics endpoint returns empty history and 0.0 values for user with no runs."""
    new_uid = "u_test_brand_new_isolated_runner_999"
    resp = client.get(f"/api/science/metrics/{new_uid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("current_ctl") == 0.0
    assert data.get("current_atl") == 0.0
    assert data.get("current_tsb") == 0.0
    assert data.get("ctl_atl_tsb_history") == []
    assert data.get("current_tsb_badge", {}).get("label") == "未连接"
