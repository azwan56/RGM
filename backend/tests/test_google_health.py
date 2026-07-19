import os
import sys
import pytest
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Ensure environment vars are set
os.environ.setdefault("GOOGLE_HEALTH_CLIENT_ID", "test_google_client_id")
os.environ.setdefault("GOOGLE_HEALTH_CLIENT_SECRET", "test_google_client_secret")

from tests import MockFirestoreDB, MockDocRef, MockDocSnapshot, MockResponse

def test_get_google_access_token_valid():
    from routers.google_health import get_google_access_token
    
    mock_db = MockFirestoreDB()
    user_data = {
        "google_access_token": "valid_token",
        "google_token_expires_at": int(time.time()) + 1000
    }
    
    mock_user_ref = MockDocRef(data=user_data, exists=True, doc_id="user_123")
    
    with patch("routers.google_health.db") as mock_db_module:
        mock_db_module.collection.return_value.document.return_value = mock_user_ref
        
        token = get_google_access_token("user_123")
        assert token == "valid_token"

def test_get_google_access_token_expired():
    from routers.google_health import get_google_access_token
    
    mock_db = MockFirestoreDB()
    user_data = {
        "google_access_token": "old_token",
        "google_refresh_token": "refresh_token_abc",
        "google_token_expires_at": int(time.time()) - 1000
    }
    
    mock_user_ref = MockDocRef(data=user_data, exists=True, doc_id="user_123")
    
    # Mock OAuth response
    oauth_response = {
        "access_token": "new_token",
        "expires_in": 3600
    }
    
    with patch("routers.google_health.db") as mock_db_module, \
         patch("requests.post", return_value=MockResponse(oauth_response)) as mock_post:
        
        mock_db_module.collection.return_value.document.return_value = mock_user_ref
        
        token = get_google_access_token("user_123")
        
        assert token == "new_token"
        assert mock_user_ref._data["google_access_token"] == "new_token"
        assert mock_user_ref._data["google_token_expires_at"] > time.time()
        
        # Verify OAuth payload
        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        assert called_kwargs["data"]["refresh_token"] == "refresh_token_abc"
        assert called_kwargs["data"]["grant_type"] == "refresh_token"

def test_sync_google_health_data():
    from routers.google_health import sync_google_health_data
    
    # Mock user token
    user_data = {
        "google_access_token": "valid_token",
        "google_token_expires_at": int(time.time()) + 1000,
        "google_health_connected": True
    }
    
    mock_user_ref = MockDocRef(data=user_data, exists=True, doc_id="user_123")
    
    # Mock sleep API response
    sleep_response_data = {
        "rollupDataPoints": [
            {
                "date": {"year": 2026, "month": 7, "day": 18},
                "value": {
                    "sleepDurationSeconds": 28800,
                    "sleepScore": 85
                }
            }
        ]
    }
    
    # Mock RHR API response
    rhr_response_data = {
        "rollupDataPoints": [
            {
                "date": {"year": 2026, "month": 7, "day": 18},
                "value": {
                    "beatsPerMinuteMin": 55,
                    "beatsPerMinuteMax": 65
                }
            }
        ]
    }
    
    # Mock HRV API response
    hrv_response_data = {
        "rollupDataPoints": [
            {
                "date": {"year": 2026, "month": 7, "day": 18},
                "value": {
                    "averageHeartRateVariabilityMillisecondsMin": 45,
                    "averageHeartRateVariabilityMillisecondsMax": 55
                }
            }
        ]
    }
    
    def side_effect_post(url, *args, **kwargs):
        if "sleep" in url:
            return MockResponse(sleep_response_data)
        elif "resting-heart-rate" in url:
            return MockResponse(rhr_response_data)
        elif "heart-rate-variability" in url:
            return MockResponse(hrv_response_data)
        return MockResponse({})
        
    # Set up mock DB write batch recording
    saved_docs = {}
    class RecordingBatch:
        def set(self, ref, data, merge=False):
            saved_docs[ref.id] = data
        def commit(self):
            pass
            
    mock_db = MockFirestoreDB()
    mock_db.batch = lambda: RecordingBatch()
    
    # Need to mock the document path as well
    class RecordingDocRef:
        def __init__(self, doc_id):
            self.id = doc_id
        def collection(self, name):
            return self
        def document(self, doc_id):
            return RecordingDocRef(doc_id)
            
    mock_db_collection = MagicMock()
    mock_db_collection.document.return_value = mock_user_ref
    mock_db.collection = lambda name: mock_db_collection if name == "users" else None
    
    # Patch db and requests.post
    with patch("routers.google_health.db", mock_db), \
         patch("requests.post", side_effect=side_effect_post) as mock_post:
        
        # Override collection to return custom Ref so subcollection is recorded
        original_collection = mock_db.collection
        def custom_collection(name):
            if name == "users":
                # Return doc ref that intercepts collection subcollection requests
                class MockUserDocRef:
                    def get(self):
                        return MockDocSnapshot(user_data, True, "user_123")
                    def update(self, data):
                        pass
                    def collection(self, sub_name):
                        assert sub_name == "daily_recovery"
                        class SubCollectionRef:
                            def document(self, doc_id):
                                return RecordingDocRef(doc_id)
                        return SubCollectionRef()
                user_mock = MagicMock()
                user_mock.document.return_value = MockUserDocRef()
                return user_mock
            return original_collection(name)
            
        mock_db.collection = custom_collection
        
        count = sync_google_health_data("user_123", days=3)
        
        # Verify sync returned number of successfully aggregated days
        assert count == 1
        
        # Verify the saved Firestore data content
        assert "2026-07-18" in saved_docs
        doc_data = saved_docs["2026-07-18"]
        assert doc_data["sleep_duration_sec"] == 28800
        assert doc_data["sleep_score"] == 85
        assert doc_data["resting_heart_rate"] == 60 # (55+65)/2
        assert doc_data["heart_rate_variability"] == 50 # (45+55)/2
        
        # Verify correct CivilTimeInterval range payload structure
        mock_post.assert_called()
        for call in mock_post.call_args_list:
            called_url, called_kwargs = call[0][0], call[1]
            if "oauth2" not in called_url:
                payload = called_kwargs["json"]
                assert "range" in payload
                assert "start" in payload["range"]
                assert "end" in payload["range"]
                assert "date" in payload["range"]["start"]
                assert "year" in payload["range"]["start"]["date"]
