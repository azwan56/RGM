"""
Tests for the auth router — Strava OAuth exchange.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("STRAVA_CLIENT_ID", "test_id")
os.environ.setdefault("STRAVA_CLIENT_SECRET", "test_secret")


def _get_client():
    with patch("firebase_config.init_firebase") as mock_init, \
         patch("firebase_config.db", MagicMock()), \
         patch("scheduler.start_scheduler"):
        mock_init.return_value = MagicMock()
        from main import app
        return TestClient(app)


class TestStravaOAuth:
    """Tests for POST /api/auth/strava — OAuth code exchange."""

    @patch("routers.auth.requests.post")
    @patch("routers.auth.db")
    def test_successful_exchange(self, mock_db, mock_post):
        """Valid code should exchange for tokens and save to Firestore."""
        mock_post.return_value = MagicMock(
            ok=True,
            json=lambda: {
                "access_token": "access_123",
                "refresh_token": "refresh_456",
                "expires_at": 9999999999,
                "athlete": {
                    "id": 12345,
                    "firstname": "Test",
                    "lastname": "Runner",
                    "profile": "https://example.com/avatar.jpg",
                }
            }
        )
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_lb_doc = MagicMock()
        mock_lb_doc.exists = False
        mock_doc_ref.get.return_value = mock_lb_doc

        client = _get_client()
        # Need to bypass Firebase auth middleware for test
        with patch("middleware.auth.firebase_auth.verify_id_token", return_value={"uid": "test_uid"}):
            resp = client.post(
                "/api/auth/strava",
                json={"code": "valid_code", "uid": "test_uid"},
                headers={"Authorization": "Bearer fake_token"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Strava connected successfully"
        assert data["athlete_id"] == 12345
        assert data["name"] == "Test Runner"

    @patch("routers.auth.requests.post")
    @patch("routers.auth.db")
    def test_invalid_code(self, mock_db, mock_post):
        """Invalid code should return 400."""
        mock_post.return_value = MagicMock(
            ok=False,
            json=lambda: {"error": "invalid_code"}
        )

        client = _get_client()
        with patch("middleware.auth.firebase_auth.verify_id_token", return_value={"uid": "test_uid"}):
            resp = client.post(
                "/api/auth/strava",
                json={"code": "bad_code", "uid": "test_uid"},
                headers={"Authorization": "Bearer fake_token"},
            )

        assert resp.status_code == 400

    def test_missing_credentials(self):
        """Missing Strava env vars should return 500."""
        client = _get_client()
        with patch("middleware.auth.firebase_auth.verify_id_token", return_value={"uid": "test_uid"}), \
             patch.dict(os.environ, {"STRAVA_CLIENT_ID": "", "STRAVA_CLIENT_SECRET": ""}):
            # Force re-read of env vars
            with patch("routers.auth.os.getenv", side_effect=lambda k, d="": {"STRAVA_CLIENT_ID": "", "STRAVA_CLIENT_SECRET": ""}.get(k, d)):
                resp = client.post(
                    "/api/auth/strava",
                    json={"code": "code", "uid": "uid"},
                    headers={"Authorization": "Bearer fake_token"},
                )
                assert resp.status_code == 500
