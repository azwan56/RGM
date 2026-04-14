"""
Shared pytest fixtures for RGM backend tests.

Provides:
- Mock Firestore database
- Mock Strava API responses
- FastAPI TestClient
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure backend is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Set test environment variables before importing anything
os.environ.setdefault("STRAVA_CLIENT_ID", "test_client_id")
os.environ.setdefault("STRAVA_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("STRAVA_WEBHOOK_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("ADMIN_SECRET", "test_admin_secret")
os.environ.setdefault("BACKEND_PUBLIC_URL", "https://api.test.example.com")


# ── Mock Firebase before any app imports ──────────────────────────────────────

class MockDocSnapshot:
    """Simulates a Firestore DocumentSnapshot."""
    def __init__(self, data=None, exists=True, doc_id="mock_id"):
        self._data = data or {}
        self.exists = exists
        self.id = doc_id

    def to_dict(self):
        return self._data if self.exists else None


class MockDocRef:
    """Simulates a Firestore DocumentReference."""
    def __init__(self, data=None, exists=True, doc_id="mock_id"):
        self._data = data or {}
        self._exists = exists
        self.id = doc_id

    def get(self):
        return MockDocSnapshot(self._data, self._exists, self.id)

    def set(self, data, merge=False):
        if merge:
            self._data.update(data)
        else:
            self._data = data

    def update(self, data):
        self._data.update(data)

    def collection(self, name):
        return MockCollectionRef()


class MockCollectionRef:
    """Simulates a Firestore CollectionReference."""
    def __init__(self, docs=None):
        self._docs = docs or []

    def document(self, doc_id=""):
        return MockDocRef(doc_id=doc_id)

    def where(self, field, op, value):
        return self

    def order_by(self, field, direction=None):
        return self

    def limit(self, n):
        return self

    def stream(self):
        return iter(self._docs)


class MockBatch:
    """Simulates a Firestore WriteBatch."""
    def __init__(self):
        self.operations = []

    def set(self, ref, data, merge=False):
        self.operations.append(("set", ref, data, merge))

    def commit(self):
        pass


class MockFirestoreDB:
    """Simulates a Firestore client for testing."""
    def __init__(self):
        self._collections = {}

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollectionRef()
        return self._collections[name]

    def batch(self):
        return MockBatch()


@pytest.fixture
def mock_db():
    """Provides a fresh mock Firestore database."""
    return MockFirestoreDB()


# ── Strava API Mock Responses ─────────────────────────────────────────────────

MOCK_STRAVA_TOKEN_RESPONSE = {
    "access_token": "test_access_token_123",
    "refresh_token": "test_refresh_token_456",
    "expires_at": 9999999999,
    "token_type": "Bearer",
    "athlete": {
        "id": 12345,
        "firstname": "Test",
        "lastname": "Runner",
        "profile": "https://example.com/avatar.jpg",
    }
}

MOCK_STRAVA_ACTIVITY = {
    "id": 9876543210,
    "name": "Morning Run",
    "type": "Run",
    "distance": 10000.0,  # 10km in metres
    "moving_time": 3000,  # 50 minutes
    "elapsed_time": 3200,
    "start_date_local": "2026-04-14T07:30:00Z",
    "average_speed": 3.33,
    "max_speed": 4.5,
    "average_heartrate": 155,
    "max_heartrate": 178,
    "has_heartrate": True,
    "total_elevation_gain": 45,
    "average_cadence": 85,
    "achievement_count": 2,
    "kudos_count": 5,
    "map": {"summary_polyline": "abc123polyline"},
}

MOCK_STRAVA_ACTIVITY_WALK = {
    "id": 1111111111,
    "name": "Walk",
    "type": "Walk",
    "distance": 3000.0,
    "moving_time": 1800,
}


class MockResponse:
    """Simulates a requests.Response."""
    def __init__(self, json_data, status_code=200, ok=True):
        self._json_data = json_data
        self.status_code = status_code
        self.ok = ok
        self.text = str(json_data)

    def json(self):
        return self._json_data


@pytest.fixture
def mock_strava_token():
    """Mock a successful Strava token refresh."""
    return MockResponse(MOCK_STRAVA_TOKEN_RESPONSE)


@pytest.fixture
def mock_strava_activities():
    """Mock a Strava activities list response."""
    return MockResponse([MOCK_STRAVA_ACTIVITY, MOCK_STRAVA_ACTIVITY_WALK])


# ── FastAPI TestClient ────────────────────────────────────────────────────────

@pytest.fixture
def test_client(mock_db):
    """Creates a FastAPI TestClient with mocked Firebase."""
    with patch("firebase_config.db", mock_db), \
         patch("firebase_config.init_firebase", return_value=mock_db):
        # Re-import after patching
        from httpx import ASGITransport, AsyncClient
        from main import app
        yield app, mock_db
