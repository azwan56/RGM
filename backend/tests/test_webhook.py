"""
Tests for the webhook router — Strava event handling.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("STRAVA_CLIENT_ID", "test_id")
os.environ.setdefault("STRAVA_CLIENT_SECRET", "test_secret")
os.environ.setdefault("STRAVA_WEBHOOK_VERIFY_TOKEN", "test_verify_token")


class TestWebhookValidation:
    """Tests for GET /api/webhook/strava — subscription validation."""

    def _get_client(self):
        with patch("firebase_config.init_firebase") as mock_init, \
             patch("firebase_config.db", MagicMock()), \
             patch("scheduler.start_scheduler"):
            mock_init.return_value = MagicMock()
            from main import app
            return TestClient(app)

    def test_valid_challenge(self):
        client = self._get_client()
        resp = client.get("/api/webhook/strava", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "challenge_abc_123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hub.challenge"] == "challenge_abc_123"

    def test_bad_verify_token(self):
        client = self._get_client()
        resp = client.get("/api/webhook/strava", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "challenge_abc_123",
        })
        assert resp.status_code == 403
        assert "error" in resp.json()

    def test_missing_challenge(self):
        client = self._get_client()
        resp = client.get("/api/webhook/strava", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
        })
        assert resp.status_code == 403

    def test_wrong_mode(self):
        client = self._get_client()
        resp = client.get("/api/webhook/strava", params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "test",
        })
        assert resp.status_code == 403


class TestWebhookEvent:
    """Tests for POST /api/webhook/strava — event receiver."""

    def _get_client(self):
        with patch("firebase_config.init_firebase") as mock_init, \
             patch("firebase_config.db", MagicMock()), \
             patch("scheduler.start_scheduler"):
            mock_init.return_value = MagicMock()
            from main import app
            return TestClient(app)

    def test_activity_create_event(self):
        """POST with activity create should return 200 immediately."""
        client = self._get_client()
        resp = client.post("/api/webhook/strava", json={
            "object_type": "activity",
            "aspect_type": "create",
            "object_id": 12345,
            "owner_id": 67890,
            "event_time": 1700000000,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_activity_delete_event_ignored(self):
        """Delete events should still return 200 but not trigger sync."""
        client = self._get_client()
        resp = client.post("/api/webhook/strava", json={
            "object_type": "activity",
            "aspect_type": "delete",
            "object_id": 12345,
            "owner_id": 67890,
        })
        assert resp.status_code == 200

    def test_athlete_event_ignored(self):
        """Non-activity events should return 200 without processing."""
        client = self._get_client()
        resp = client.post("/api/webhook/strava", json={
            "object_type": "athlete",
            "aspect_type": "update",
            "object_id": 67890,
            "owner_id": 67890,
        })
        assert resp.status_code == 200


class TestFindUidByStravaId:
    """Tests for the Strava athlete ID → Firebase UID lookup."""

    def test_found(self):
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.id = "firebase_uid_123"
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = [mock_doc]

        with patch("routers.webhook.db", mock_db):
            from routers.webhook import _find_uid_by_strava_id
            result = _find_uid_by_strava_id(12345)
            assert result == "firebase_uid_123"

    def test_not_found(self):
        mock_db = MagicMock()
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []

        with patch("routers.webhook.db", mock_db):
            from routers.webhook import _find_uid_by_strava_id
            result = _find_uid_by_strava_id(99999)
            assert result is None
