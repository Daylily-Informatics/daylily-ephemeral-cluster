"""
Integration tests for file API with workset_api.py.

Tests the complete integration including authentication and customer scoping.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from daylib.workset_api import create_app
from daylib.workset_state_db import WorksetStateDB
from daylib.file_registry import FileRegistry


@pytest.fixture
def mock_state_db():
    """Mock WorksetStateDB."""
    db = MagicMock(spec=WorksetStateDB)
    db.get_workset.return_value = None
    db.list_worksets_by_state.return_value = []
    return db


@pytest.fixture
def mock_file_registry():
    """Mock FileRegistry."""
    registry = MagicMock(spec=FileRegistry)
    registry.register_file.return_value = True
    registry.create_fileset.return_value = True
    registry.list_customer_files.return_value = []
    # By default, simulate no existing registrations for any S3 URI so
    # integration tests exercise the successful registration path.
    registry.find_file_by_s3_uri.return_value = None
    return registry


@pytest.fixture
def app_without_auth(mock_state_db, mock_file_registry):
    """Create app without authentication."""
    app = create_app(
        state_db=mock_state_db,
        file_registry=mock_file_registry,
        enable_auth=False,
    )
    return app


@pytest.fixture
def client_without_auth(app_without_auth):
    """Test client without authentication."""
    return TestClient(app_without_auth)


class TestFileAPIIntegrationWithoutAuth:
    """Test file API integration without authentication."""
    
    def test_file_endpoints_available(self, client_without_auth):
        """Test that file endpoints are registered."""
        # Check OpenAPI docs include file endpoints
        response = client_without_auth.get("/openapi.json")
        assert response.status_code == 200
        openapi = response.json()
        
        # Verify file endpoints are present
        paths = openapi.get("paths", {})
        assert "/api/files/register" in paths
        assert "/api/files/list" in paths
        assert "/api/files/filesets" in paths
        assert "/api/files/bulk-import" in paths
    
    def test_register_file_without_auth(self, client_without_auth, mock_file_registry):
        """Test file registration without authentication."""
        payload = {
            "file_metadata": {
                "s3_uri": "s3://test-bucket/sample_R1.fastq.gz",
                "file_size_bytes": 1024000,
            },
            "sequencing_metadata": {
                "platform": "ILLUMINA_NOVASEQ_X",
                "vendor": "ILMN",
            },
            "biosample_metadata": {
                "biosample_id": "bio-001",
                "subject_id": "HG002",
            },
        }
        
        response = client_without_auth.post(
            "/api/files/register?customer_id=test-customer",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "test-customer"
        assert data["s3_uri"] == "s3://test-bucket/sample_R1.fastq.gz"
        assert "file_id" in data
    
    def test_list_files_without_auth(self, client_without_auth):
        """Test listing files without authentication."""
        response = client_without_auth.get("/api/files/list?customer_id=test-customer")
        
        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "test-customer"
        assert "files" in data
    
    def test_create_fileset_without_auth(self, client_without_auth):
        """Test creating fileset without authentication."""
        payload = {
            "name": "Test FileSet",
            "description": "Integration test fileset",
        }
        
        response = client_without_auth.post(
            "/api/files/filesets?customer_id=test-customer",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test FileSet"
        assert data["customer_id"] == "test-customer"
    
    def test_bulk_import_without_auth(self, client_without_auth):
        """Test bulk import without authentication."""
        payload = {
            "files": [
                {
                    "file_metadata": {
                        "s3_uri": "s3://test-bucket/sample1_R1.fastq.gz",
                        "file_size_bytes": 1024000,
                    },
                    "sequencing_metadata": {
                        "platform": "ILLUMINA_NOVASEQ_X",
                        "vendor": "ILMN",
                    },
                    "biosample_metadata": {
                        "biosample_id": "bio-001",
                        "subject_id": "HG002",
                    },
                },
            ],
        }
        
        response = client_without_auth.post(
            "/api/files/bulk-import?customer_id=test-customer",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] >= 0
        assert "failed_count" in data


class TestFileAPIIntegrationWithAuth:
    """Test file API integration with authentication."""
    
    def test_app_creation_with_auth_requires_cognito(self, mock_state_db, mock_file_registry):
        """Test that enabling auth without cognito_auth raises error."""
        with pytest.raises((ImportError, ValueError)):
            create_app(
                state_db=mock_state_db,
                file_registry=mock_file_registry,
                enable_auth=True,  # Enable auth without cognito_auth
                cognito_auth=None,
            )

