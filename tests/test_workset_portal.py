"""Tests for customer portal routes."""

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from daylib.workset_state_db import WorksetStateDB, WorksetState
from daylib.workset_api import create_app


@pytest.fixture
def mock_state_db():
    """Create mock state database."""
    mock_db = MagicMock(spec=WorksetStateDB)
    mock_db.list_worksets_by_state.return_value = [
        {
            "workset_id": "test-workset-001",
            "state": "ready",
            "priority": "normal",
            "bucket": "test-bucket",
            "prefix": "worksets/test/",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
        },
        {
            "workset_id": "test-workset-002",
            "state": "in_progress",
            "priority": "high",
            "bucket": "test-bucket",
            "prefix": "worksets/test2/",
            "created_at": "2024-01-15T11:00:00Z",
            "updated_at": "2024-01-15T11:30:00Z",
        },
    ]
    mock_db.get_workset.return_value = {
        "workset_id": "test-workset-001",
        "state": "ready",
        "priority": "normal",
        "bucket": "test-bucket",
        "prefix": "worksets/test/",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:00:00Z",
    }
    return mock_db


@pytest.fixture
def client(mock_state_db):
    """Create test client."""
    app = create_app(state_db=mock_state_db, enable_auth=False)
    return TestClient(app)


class TestPortalRoutes:
    """Test portal HTML routes."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "daylily-workset-monitor"

    def test_portal_dashboard(self, client):
        """Test dashboard page loads."""
        response = client.get("/portal")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Dashboard" in response.content or b"dashboard" in response.content.lower()

    def test_portal_login(self, client):
        """Test login page loads."""
        response = client.get("/portal/login")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Sign" in response.content or b"login" in response.content.lower()

    def test_portal_register(self, client):
        """Test registration page loads."""
        response = client.get("/portal/register")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Create" in response.content or b"register" in response.content.lower()

    def test_portal_worksets_list(self, client):
        """Test worksets list page loads."""
        response = client.get("/portal/worksets")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Workset" in response.content

    def test_portal_worksets_new(self, client):
        """Test new workset page loads."""
        response = client.get("/portal/worksets/new")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Submit" in response.content or b"New" in response.content

    def test_portal_workset_detail(self, client, mock_state_db):
        """Test workset detail page loads."""
        response = client.get("/portal/worksets/test-workset-001")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        mock_state_db.get_workset.assert_called_with("test-workset-001")

    def test_portal_workset_detail_not_found(self, client, mock_state_db):
        """Test workset detail page returns 404 for missing workset."""
        mock_state_db.get_workset.return_value = None
        response = client.get("/portal/worksets/nonexistent")
        assert response.status_code == 404

    def test_portal_yaml_generator(self, client):
        """Test YAML generator page loads."""
        response = client.get("/portal/yaml-generator")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"YAML" in response.content

    def test_portal_files(self, client):
        """Test files page loads."""
        response = client.get("/portal/files")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"File" in response.content

    def test_portal_usage(self, client):
        """Test usage page loads."""
        response = client.get("/portal/usage")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Usage" in response.content or b"Billing" in response.content


class TestAPIEndpoints:
    """Test API endpoints."""

    def test_list_worksets(self, client, mock_state_db):
        """Test listing worksets via API."""
        response = client.get("/worksets")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_workset(self, client, mock_state_db):
        """Test getting a single workset."""
        response = client.get("/worksets/test-workset-001")
        assert response.status_code == 200
        data = response.json()
        assert data["workset_id"] == "test-workset-001"

    def test_get_queue_stats(self, client, mock_state_db):
        """Test queue statistics endpoint."""
        mock_state_db.get_queue_depth.return_value = {
            "ready": 5,
            "in_progress": 3,
            "completed": 10,
            "error": 1,
        }
        response = client.get("/queue/stats")
        assert response.status_code == 200
        data = response.json()
        assert "queue_depth" in data
        assert "total_worksets" in data

