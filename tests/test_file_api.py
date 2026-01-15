"""
Tests for file_api.py - File registration API endpoints.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from daylib.file_api import (
    BiosampleMetadataRequest,
    FileMetadataRequest,
    FileRegistrationRequest,
    FileSetRequest,
    SequencingMetadataRequest,
    create_file_api_router,
)
from daylib.file_registry import FileRegistry


@pytest.fixture
def mock_file_registry():
    """Mock FileRegistry."""
    registry = MagicMock(spec=FileRegistry)
    registry.register_file.return_value = True
    registry.create_fileset.return_value = True
    registry.list_customer_files.return_value = []
    return registry


@pytest.fixture
def app_with_file_api(mock_file_registry):
    """Create FastAPI app with file API router."""
    app = FastAPI()
    router = create_file_api_router(mock_file_registry)
    app.include_router(router)
    return app


@pytest.fixture
def client(app_with_file_api):
    """FastAPI test client."""
    return TestClient(app_with_file_api)


class TestFileRegistrationEndpoint:
    """Test file registration endpoint."""
    
    def test_register_file_success(self, client, mock_file_registry):
        """Test successful file registration."""
        payload = {
            "file_metadata": {
                "s3_uri": "s3://bucket/sample_R1.fastq.gz",
                "file_size_bytes": 1024000,
                "md5_checksum": "abc123",
                "file_format": "fastq",
            },
            "sequencing_metadata": {
                "platform": "ILLUMINA_NOVASEQ_X",
                "vendor": "ILMN",
                "run_id": "run-001",
                "lane": 1,
                "barcode_id": "S1",
            },
            "biosample_metadata": {
                "biosample_id": "bio-001",
                "subject_id": "HG002",
                "sample_type": "blood",
            },
            "read_number": 1,
            "tags": ["wgs"],
        }
        
        response = client.post(
            "/api/files/register?customer_id=cust-001",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "cust-001"
        assert data["s3_uri"] == "s3://bucket/sample_R1.fastq.gz"
        assert data["subject_id"] == "HG002"
        assert data["status"] == "registered"
    
    def test_register_file_conflict(self, client, mock_file_registry):
        """Test registering a file that already exists."""
        mock_file_registry.register_file.return_value = False
        
        payload = {
            "file_metadata": {
                "s3_uri": "s3://bucket/sample_R1.fastq.gz",
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
        
        response = client.post(
            "/api/files/register?customer_id=cust-001",
            json=payload,
        )
        
        assert response.status_code == 409


class TestListFilesEndpoint:
    """Test list files endpoint."""
    
    def test_list_customer_files_empty(self, client, mock_file_registry):
        """Test listing files for customer with no files."""
        response = client.get("/api/files/list?customer_id=cust-001")
        
        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "cust-001"
        assert data["file_count"] == 0
        assert data["files"] == []
    
    def test_list_customer_files_with_limit(self, client, mock_file_registry):
        """Test listing files with custom limit."""
        response = client.get("/api/files/list?customer_id=cust-001&limit=50")
        
        assert response.status_code == 200
        mock_file_registry.list_customer_files.assert_called_with("cust-001", limit=50)


class TestCreateFilesetEndpoint:
    """Test file set creation endpoint."""
    
    def test_create_fileset_success(self, client, mock_file_registry):
        """Test successful file set creation."""
        payload = {
            "name": "HG002 WGS",
            "description": "Whole genome sequencing of HG002",
            "biosample_metadata": {
                "biosample_id": "bio-001",
                "subject_id": "HG002",
                "sample_type": "blood",
            },
            "file_ids": ["file-001", "file-002"],
        }
        
        response = client.post(
            "/api/files/filesets?customer_id=cust-001",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "cust-001"
        assert data["name"] == "HG002 WGS"
        assert data["file_count"] == 2
    
    def test_create_fileset_minimal(self, client, mock_file_registry):
        """Test file set creation with minimal fields."""
        payload = {
            "name": "Test FileSet",
        }
        
        response = client.post(
            "/api/files/filesets?customer_id=cust-001",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test FileSet"
        assert data["file_count"] == 0


class TestBulkImportEndpoint:
    """Test bulk import endpoint."""
    
    def test_bulk_import_success(self, client, mock_file_registry):
        """Test successful bulk import."""
        payload = {
            "files": [
                {
                    "file_metadata": {
                        "s3_uri": "s3://bucket/sample1_R1.fastq.gz",
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
                {
                    "file_metadata": {
                        "s3_uri": "s3://bucket/sample1_R2.fastq.gz",
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
            "fileset_name": "HG002 WGS",
        }
        
        response = client.post(
            "/api/files/bulk-import?customer_id=cust-001",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 2
        assert data["failed_count"] == 0
        assert data["fileset_id"] is not None
    
    def test_bulk_import_partial_failure(self, client, mock_file_registry):
        """Test bulk import with some failures."""
        # First call succeeds, second fails
        mock_file_registry.register_file.side_effect = [True, False]
        
        payload = {
            "files": [
                {
                    "file_metadata": {
                        "s3_uri": "s3://bucket/sample1_R1.fastq.gz",
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
                {
                    "file_metadata": {
                        "s3_uri": "s3://bucket/sample2_R1.fastq.gz",
                        "file_size_bytes": 1024000,
                    },
                    "sequencing_metadata": {
                        "platform": "ILLUMINA_NOVASEQ_X",
                        "vendor": "ILMN",
                    },
                    "biosample_metadata": {
                        "biosample_id": "bio-002",
                        "subject_id": "HG003",
                    },
                },
            ],
        }
        
        response = client.post(
            "/api/files/bulk-import?customer_id=cust-001",
            json=payload,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 1
        assert data["failed_count"] == 1
        assert len(data["errors"]) == 1

