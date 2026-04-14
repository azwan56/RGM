"""
Tests for the admin router — webhook management and sync-all.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("STRAVA_CLIENT_ID", "test_id")
os.environ.setdefault("STRAVA_CLIENT_SECRET", "test_secret")
os.environ.setdefault("ADMIN_SECRET", "test_admin_secret")
os.environ.setdefault("BACKEND_PUBLIC_URL", "https://api.test.example.com")
os.environ.setdefault("STRAVA_WEBHOOK_VERIFY_TOKEN", "test_verify_token")


def _get_client():
    with patch("firebase_config.init_firebase") as mock_init, \
         patch("firebase_config.db", MagicMock()), \
         patch("scheduler.start_scheduler"):
        mock_init.return_value = MagicMock()
        from main import app
        return TestClient(app)


class TestAdminAuth:
    """Tests that admin endpoints require proper authentication."""

    def test_no_admin_token(self):
        client = _get_client()
        resp = client.get("/api/admin/webhook-status")
        assert resp.status_code == 403
        assert "denied" in resp.json()["detail"].lower()

    def test_wrong_admin_token(self):
        client = _get_client()
        resp = client.get("/api/admin/webhook-status",
                          headers={"X-Admin-Secret": "wrong_token"})
        assert resp.status_code == 403

    def test_valid_admin_token(self):
        """Valid token should pass auth check (may fail on Strava API, that's OK)."""
        client = _get_client()
        with patch("routers.admin.requests.get") as mock_get, \
             patch("routers.admin.db") as mock_db:
            mock_get.return_value = MagicMock(ok=True, json=lambda: [], status_code=200)
            mock_doc = MagicMock()
            mock_doc.exists = False
            mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

            resp = client.get("/api/admin/webhook-status",
                              headers={"X-Admin-Secret": "test_admin_secret"})
            assert resp.status_code == 200


class TestWebhookRegistration:
    """Tests for webhook subscription management."""

    @patch("routers.admin.requests.post")
    @patch("routers.admin.db")
    def test_register_webhook_success(self, mock_db, mock_post):
        mock_post.return_value = MagicMock(
            ok=True,
            json=lambda: {"id": 42},
        )
        mock_db.collection.return_value.document.return_value.set = MagicMock()

        client = _get_client()
        resp = client.post(
            "/api/admin/register-webhook",
            headers={"X-Admin-Secret": "test_admin_secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Webhook registered successfully"
        assert data["subscription"]["id"] == 42

        # Verify Strava was called with correct callback URL
        call_args = mock_post.call_args
        assert "callback_url" in call_args.kwargs.get("data", call_args[1].get("data", {}))

    @patch("routers.admin.requests.post")
    def test_register_webhook_already_exists(self, mock_post):
        mock_post.return_value = MagicMock(
            ok=False,
            status_code=409,
            text="Subscription already exists",
        )

        client = _get_client()
        resp = client.post(
            "/api/admin/register-webhook",
            headers={"X-Admin-Secret": "test_admin_secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_register_webhook_missing_url(self):
        """Missing BACKEND_PUBLIC_URL should return 400."""
        client = _get_client()
        with patch("routers.admin.os.getenv", side_effect=lambda k, d="": {
            "BACKEND_PUBLIC_URL": "",
            "STRAVA_WEBHOOK_VERIFY_TOKEN": "token",
            "STRAVA_CLIENT_ID": "id",
            "STRAVA_CLIENT_SECRET": "secret",
            "ADMIN_SECRET": "test_admin_secret",
        }.get(k, d)):
            resp = client.post(
                "/api/admin/register-webhook",
                headers={"X-Admin-Secret": "test_admin_secret"},
            )
            assert resp.status_code == 400


class TestWebhookStatus:
    """Tests for GET /api/admin/webhook-status."""

    @patch("routers.admin.requests.get")
    @patch("routers.admin.db")
    def test_returns_strava_and_local(self, mock_db, mock_get):
        mock_get.return_value = MagicMock(
            ok=True,
            status_code=200,
            json=lambda: [{"id": 42, "callback_url": "https://example.com/webhook"}],
        )
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"subscription_id": 42, "active": True}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        client = _get_client()
        resp = client.get("/api/admin/webhook-status",
                          headers={"X-Admin-Secret": "test_admin_secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["strava_subscriptions"]) == 1
        assert data["local_registration"]["active"] is True


class TestSchedulerStatus:
    """Tests for GET /api/admin/scheduler-status."""

    def test_scheduler_status(self):
        client = _get_client()
        with patch("scheduler.get_scheduler_status",
                    return_value={"status": "running", "jobs": [], "last_sync_result": None}):
            resp = client.get("/api/admin/scheduler-status",
                              headers={"X-Admin-Secret": "test_admin_secret"})
            assert resp.status_code == 200
