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

from tests import MockFirestoreDB, MockDocRef, MockDocSnapshot

@pytest.mark.anyio
async def test_sync_apple_health_workouts_deprecated():
    from routers.apple_health import sync_apple_health_workouts, AppleHealthSyncRequest, AppleHealthWorkout
    
    # Mock user document
    user_data = {
        "display_name": "Alex Wan",
        "email": "azwan56@gmail.com"
    }
    
    mock_db = MockFirestoreDB()
    user_ref = MockDocRef(data=user_data, exists=True, doc_id="user_123")
    
    def db_collection_side_effect(name):
        if name == "users":
            class UsersCollection:
                def document(self, doc_id):
                    return user_ref
            return UsersCollection()
        return None
        
    mock_db.collection = db_collection_side_effect
    
    req = AppleHealthSyncRequest(
        uid="user_123",
        workouts=[]
    )
    
    with patch("routers.apple_health.db", mock_db):
        resp = await sync_apple_health_workouts(req)
        assert resp["success"] is True
        assert resp["synced_count"] == 0
        assert user_ref._data["apple_health_connected"] is True


@pytest.mark.anyio
async def test_sync_apple_health_recovery():
    from routers.apple_health import sync_apple_health_recovery, AppleHealthRecoverySyncRequest, AppleHealthRecoveryItem
    
    user_data = {
        "display_name": "Alex Wan",
        "email": "azwan56@gmail.com"
    }
    
    mock_db = MockFirestoreDB()
    user_ref = MockDocRef(data=user_data, exists=True, doc_id="user_123")
    
    recovery_docs = {}
    class RecordingBatch:
        def set(self, ref, data, merge=False):
            recovery_docs[ref.id] = data
        def commit(self):
            pass
            
    mock_db.batch = lambda: RecordingBatch()
    
    class MockDocRefWithId:
        def __init__(self, doc_id):
            self.id = doc_id
            
    class MockRecoveryCollection:
        def document(self, doc_id):
            return MockDocRefWithId(doc_id)
            
    def user_collection_side_effect(name):
        if name == "daily_recovery":
            return MockRecoveryCollection()
        return None
        
    user_ref.collection = user_collection_side_effect
    
    def db_collection_side_effect(name):
        if name == "users":
            class UsersCollection:
                def document(self, doc_id):
                    return user_ref
            return UsersCollection()
        return None
        
    mock_db.collection = db_collection_side_effect
    
    item1 = AppleHealthRecoveryItem(
        date="2026-07-20",
        sleep_duration_sec=28800, # 8 hours
        sleep_score=85,
        resting_heart_rate=55,
        heart_rate_variability=62
    )
    
    req = AppleHealthRecoverySyncRequest(
        uid="user_123",
        recovery_data=[item1]
    )
    
    with patch("routers.apple_health.db", mock_db):
        resp = await sync_apple_health_recovery(req)
        assert resp["success"] is True
        assert resp["synced_count"] == 1
        assert user_ref._data["apple_health_connected"] is True
        
        assert "2026-07-20" in recovery_docs
        saved = recovery_docs["2026-07-20"]
        assert saved["sleep_duration_sec"] == 28800
        assert saved["sleep_score"] == 85
        assert saved["resting_heart_rate"] == 55
        assert saved["heart_rate_variability"] == 62
        assert "last_sync" in saved
