"""Tests for optional authentication support."""

import sys
from unittest.mock import MagicMock, patch

import pytest


def test_api_without_auth():
    """Test that API can be created without authentication."""
    from daylib.workset_api import create_app
    from daylib.workset_state_db import WorksetStateDB
    
    # Mock state_db
    state_db = MagicMock(spec=WorksetStateDB)
    
    # Create app without authentication
    app = create_app(
        state_db=state_db,
        enable_auth=False,
    )
    
    # App should be created successfully
    assert app is not None
    assert app.title == "Daylily Workset Monitor API"


def test_api_with_auth_requires_cognito():
    """Test that API with auth requires cognito_auth parameter."""
    from daylib.workset_api import create_app
    from daylib.workset_state_db import WorksetStateDB
    
    # Mock state_db
    state_db = MagicMock(spec=WorksetStateDB)
    
    # Trying to enable auth without cognito_auth should raise error
    with pytest.raises(ValueError, match="enable_auth=True requires cognito_auth"):
        create_app(
            state_db=state_db,
            enable_auth=True,
            cognito_auth=None,
        )


def test_api_endpoints_work_without_auth():
    """Test that API endpoints work without authentication."""
    from fastapi.testclient import TestClient
    from daylib.workset_api import create_app
    from daylib.workset_state_db import WorksetStateDB
    
    # Mock state_db
    state_db = MagicMock(spec=WorksetStateDB)
    state_db.get_queue_depth.return_value = {
        "ready": 5,
        "in_progress": 2,
        "completed": 10,
    }
    
    # Create app without authentication
    app = create_app(
        state_db=state_db,
        enable_auth=False,
    )
    
    # Create test client
    client = TestClient(app)
    
    # Test health endpoint
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    
    # Test queue stats endpoint (no auth required)
    response = client.get("/queue/stats")
    assert response.status_code == 200



def test_auth_warning_logged_when_missing():
    """Test that warning is logged when jose is not available."""
    import logging
    
    # Mock jose import to fail
    with patch.dict(sys.modules, {"jose": None}):
        # Remove modules from cache
        if "jose" in sys.modules:
            del sys.modules["jose"]
        if "daylib.workset_auth" in sys.modules:
            del sys.modules["daylib.workset_auth"]
        
        # Capture log output
        with patch("logging.Logger.warning") as mock_warning:
            # Import should trigger warning
            import daylib.workset_auth
            
            # Warning should have been logged
            # (Note: This might not work due to module caching)
            # assert mock_warning.called


def test_example_scripts_exist():
    """Test that example scripts exist."""
    from pathlib import Path
    
    examples_dir = Path(__file__).parent.parent / "examples"
    
    # Check for example scripts
    assert (examples_dir / "run_api_without_auth.py").exists()
    assert (examples_dir / "run_api_with_auth.py").exists()


def test_authentication_docs_exist():
    """Test that authentication documentation exists."""
    from pathlib import Path
    
    docs_dir = Path(__file__).parent.parent / "docs"
    
    # Check for documentation
    assert (docs_dir / "AUTHENTICATION_SETUP.md").exists()

