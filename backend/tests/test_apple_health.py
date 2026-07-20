import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Ensure environment vars
os.environ.setdefault("GOOGLE_HEALTH_CLIENT_ID", "test_client")
os.environ.setdefault("GOOGLE_HEALTH_CLIENT_SECRET", "test_secret")

from tests import MockFirestoreDB, MockDocRef, MockDocSnapshot, MockResponse

def test_sync_apple_health_workouts():
    from routers.apple_health import sync_apple_health_workouts, AppleHealthSyncRequest, AppleHealthWorkout
    
    # Mock user document
    user_data = {
        "display_name": "Alex Wan",
        "email": "azwan56@gmail.com"
    }
    
    # Set up mock DB
    mock_db = MockFirestoreDB()
    
    user_ref = MockDocRef(data=user_data, exists=True, doc_id="user_123")
    
    # We will record set/update calls on activities subcollection
    activities_ref = {}
    class MockActivitiesCollection:
        def document(self, doc_id):
            class ActivityDocRef:
                def __init__(self, d_id):
                    self.id = d_id
                def get(self):
                    # Mock that it does not exist yet (new workout)
                    return MockDocSnapshot({}, False, self.id)
                def set(self, doc_data):
                    activities_ref[self.id] = doc_data
                def update(self, doc_data):
                    activities_ref[self.id].update(doc_data)
            return ActivityDocRef(doc_id)
            
        def where(self, *args, **kwargs):
            # Return empty stream for leaderboard calculation in test
            class MockStream:
                def stream(self):
                    return []
            return MockStream()
            
    # Mock user_ref.collection
    def user_collection_side_effect(name):
        if name == "activities":
            return MockActivitiesCollection()
        # For goals or other
        class EmptyCollection:
            def document(self, d_id):
                return MockDocRef(data={}, exists=False, doc_id=d_id)
        return EmptyCollection()
        
    user_ref.collection = user_collection_side_effect
    
    # Leaderboard document mock
    leaderboard_docs = {}
    class MockLeaderboardCollection:
        def document(self, doc_id):
            class LeaderboardDocRef:
                def __init__(self, d_id):
                    self.id = d_id
                def set(self, doc_data):
                    leaderboard_docs[self.id] = doc_data
            return LeaderboardDocRef(doc_id)
            
    def db_collection_side_effect(name):
        if name == "users":
            class UsersCollection:
                def document(self, doc_id):
                    return user_ref
            return UsersCollection()
        elif name == "leaderboard" or name == "leaderboard_weekly":
            return MockLeaderboardCollection()
        return None
        
    mock_db.collection = db_collection_side_effect
    
    # Request data
    workout = AppleHealthWorkout(
        uuid="workout_uuid_123",
        name="Apple Health 跑步",
        start_date_local="2026-07-20T10:00:00",
        distance_km=5.0,
        moving_time=1800, # 30 mins
        avg_heart_rate=140,
        total_elevation_gain=20.0
    )
    
    req = AppleHealthSyncRequest(
        uid="user_123",
        workouts=[workout]
    )
    
    with patch("routers.apple_health.db", mock_db):
        resp = sync_apple_health_workouts(req)
        
        # Assertions
        assert resp["success"] is True
        assert resp["synced_count"] == 1
        
        # Verify user doc connection status updated
        assert user_ref._data["apple_health_connected"] is True
        
        # Verify activity saved
        assert "workout_uuid_123" in activities_ref
        saved_act = activities_ref["workout_uuid_123"]
        assert saved_act["distance_km"] == 5.0
        assert saved_act["moving_time"] == 1800
        assert saved_act["avg_pace"] == "6:00"
        assert saved_act["source"] == "AppleHealth"
        
        # Verify leaderboard entries were set
        assert "user_123" in leaderboard_docs
