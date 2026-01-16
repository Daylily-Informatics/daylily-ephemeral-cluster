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
from daylib.file_registry import FileRegistry, BucketFileDiscovery
from daylib.s3_bucket_validator import (
    S3BucketValidator,
    LinkedBucketManager,
    BucketValidationResult,
    LinkedBucket,
)


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


class TestBucketValidationEndpoint:
    """Test bucket validation endpoints."""

    @pytest.fixture
    def mock_s3_validator(self):
        """Mock S3BucketValidator."""
        validator = MagicMock(spec=S3BucketValidator)
        validator.validate_bucket.return_value = BucketValidationResult(
            bucket_name="test-bucket",
            exists=True,
            accessible=True,
            can_read=True,
            can_write=True,
            can_list=True,
            region="us-west-2",
        )
        return validator

    @pytest.fixture
    def mock_linked_bucket_manager(self):
        """Mock LinkedBucketManager."""
        manager = MagicMock(spec=LinkedBucketManager)
        manager.link_bucket.return_value = (
            LinkedBucket(
                bucket_id="bucket-abc123",
                customer_id="cust-001",
                bucket_name="test-bucket",
                bucket_type="secondary",
                display_name="Test Bucket",
                is_validated=True,
                can_read=True,
                can_write=True,
                can_list=True,
                region="us-west-2",
                linked_at="2024-01-15T00:00:00Z",
            ),
            BucketValidationResult(
                bucket_name="test-bucket",
                exists=True,
                accessible=True,
                can_read=True,
                can_write=True,
                can_list=True,
                region="us-west-2",
            ),
        )
        manager.list_customer_buckets.return_value = []
        return manager

    @pytest.fixture
    def app_with_bucket_validation(self, mock_file_registry, mock_s3_validator, mock_linked_bucket_manager):
        """Create FastAPI app with bucket validation enabled."""
        app = FastAPI()
        router = create_file_api_router(
            mock_file_registry,
            s3_bucket_validator=mock_s3_validator,
            linked_bucket_manager=mock_linked_bucket_manager,
        )
        app.include_router(router)
        return app

    @pytest.fixture
    def client_with_validation(self, app_with_bucket_validation):
        """FastAPI test client with bucket validation."""
        return TestClient(app_with_bucket_validation)

    def test_validate_bucket_success(self, client_with_validation, mock_s3_validator):
        """Test successful bucket validation."""
        response = client_with_validation.post(
            "/api/files/buckets/validate?bucket_name=test-bucket"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["bucket_name"] == "test-bucket"
        assert data["exists"] is True
        assert data["accessible"] is True
        assert data["can_read"] is True
        assert data["can_write"] is True
        assert data["can_list"] is True
        assert data["is_valid"] is True
        mock_s3_validator.validate_bucket.assert_called_once_with("test-bucket")

    def test_validate_bucket_not_found(self, client_with_validation, mock_s3_validator):
        """Test validation of non-existent bucket."""
        mock_s3_validator.validate_bucket.return_value = BucketValidationResult(
            bucket_name="nonexistent-bucket",
            exists=False,
            accessible=False,
            errors=["Bucket 'nonexistent-bucket' does not exist"],
        )

        response = client_with_validation.post(
            "/api/files/buckets/validate?bucket_name=nonexistent-bucket"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False
        assert data["is_valid"] is False
        assert len(data["errors"]) > 0

    def test_validate_bucket_access_denied(self, client_with_validation, mock_s3_validator):
        """Test validation of bucket with access denied."""
        mock_s3_validator.validate_bucket.return_value = BucketValidationResult(
            bucket_name="private-bucket",
            exists=True,
            accessible=False,
            errors=["Access denied to bucket 'private-bucket'"],
        )

        response = client_with_validation.post(
            "/api/files/buckets/validate?bucket_name=private-bucket"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["accessible"] is False
        assert data["is_valid"] is False

    def test_validate_bucket_without_validator_returns_501(self, client, mock_file_registry):
        """Test that validation without validator returns 501."""
        # client fixture uses app without s3_bucket_validator
        response = client.post(
            "/api/files/buckets/validate?bucket_name=test-bucket"
        )

        assert response.status_code == 501
        data = response.json()
        assert "not configured" in data["detail"].lower()


class TestLinkBucketEndpoint:
    """Test bucket linking endpoints."""

    @pytest.fixture
    def mock_s3_validator(self):
        """Mock S3BucketValidator."""
        validator = MagicMock(spec=S3BucketValidator)
        return validator

    @pytest.fixture
    def mock_linked_bucket_manager(self):
        """Mock LinkedBucketManager."""
        manager = MagicMock(spec=LinkedBucketManager)
        manager.link_bucket.return_value = (
            LinkedBucket(
                bucket_id="bucket-abc123",
                customer_id="cust-001",
                bucket_name="my-bucket",
                bucket_type="secondary",
                display_name="My Bucket",
                is_validated=True,
                can_read=True,
                can_write=True,
                can_list=True,
                region="us-west-2",
                linked_at="2024-01-15T00:00:00Z",
            ),
            BucketValidationResult(
                bucket_name="my-bucket",
                exists=True,
                accessible=True,
                can_read=True,
                can_write=True,
                can_list=True,
                region="us-west-2",
            ),
        )
        manager.list_customer_buckets.return_value = [
            LinkedBucket(
                bucket_id="bucket-abc123",
                customer_id="cust-001",
                bucket_name="my-bucket",
                bucket_type="secondary",
                display_name="My Bucket",
                is_validated=True,
                can_read=True,
                can_write=True,
                can_list=True,
                region="us-west-2",
                linked_at="2024-01-15T00:00:00Z",
            )
        ]
        return manager

    @pytest.fixture
    def app_with_bucket_linking(self, mock_file_registry, mock_s3_validator, mock_linked_bucket_manager):
        """Create FastAPI app with bucket linking enabled."""
        app = FastAPI()
        router = create_file_api_router(
            mock_file_registry,
            s3_bucket_validator=mock_s3_validator,
            linked_bucket_manager=mock_linked_bucket_manager,
        )
        app.include_router(router)
        return app

    @pytest.fixture
    def client_with_linking(self, app_with_bucket_linking):
        """FastAPI test client with bucket linking."""
        return TestClient(app_with_bucket_linking)

    def test_link_bucket_success(self, client_with_linking, mock_linked_bucket_manager):
        """Test successful bucket linking."""
        response = client_with_linking.post(
            "/api/files/buckets/link?customer_id=cust-001",
            json={
                "bucket_name": "my-bucket",
                "bucket_type": "secondary",
                "display_name": "My Bucket",
                "description": "Test bucket",
                "validate": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["bucket_id"] == "bucket-abc123"
        assert data["bucket_name"] == "my-bucket"
        assert data["is_validated"] is True
        assert data["can_read"] is True
        assert data["can_write"] is True
        mock_linked_bucket_manager.link_bucket.assert_called_once()

    def test_link_bucket_without_manager_returns_501(self, client, mock_file_registry):
        """Test that linking without manager returns 501."""
        response = client.post(
            "/api/files/buckets/link?customer_id=cust-001",
            json={
                "bucket_name": "my-bucket",
            },
        )

        assert response.status_code == 501
        data = response.json()
        assert "not configured" in data["detail"].lower()

    def test_list_linked_buckets(self, client_with_linking, mock_linked_bucket_manager):
        """Test listing linked buckets."""
        response = client_with_linking.get(
            "/api/files/buckets/list?customer_id=cust-001"
        )

        assert response.status_code == 200
        data = response.json()
        assert "buckets" in data
        assert len(data["buckets"]) == 1
        assert data["buckets"][0]["bucket_name"] == "my-bucket"
        mock_linked_bucket_manager.list_customer_buckets.assert_called_once_with("cust-001")

    def test_list_linked_buckets_empty(self, client_with_linking, mock_linked_bucket_manager):
        """Test listing linked buckets when none exist."""
        mock_linked_bucket_manager.list_customer_buckets.return_value = []

        response = client_with_linking.get(
            "/api/files/buckets/list?customer_id=cust-002"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["buckets"] == []

    def test_link_bucket_dynamodb_error(self, client_with_linking, mock_linked_bucket_manager):
        """Test error handling when DynamoDB operation fails."""
        from botocore.exceptions import ClientError

        # Simulate ResourceNotFoundException
        error_response = {
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "Requested resource not found",
            }
        }
        mock_linked_bucket_manager.link_bucket.side_effect = ClientError(
            error_response, "PutItem"
        )

        response = client_with_linking.post(
            "/api/files/buckets/link?customer_id=cust-001",
            json={
                "bucket_name": "my-bucket",
                "bucket_type": "secondary",
            },
        )

        assert response.status_code == 500
        data = response.json()
        assert "ResourceNotFoundException" in data["detail"] or "table" in data["detail"].lower()

    def test_link_bucket_generic_error(self, client_with_linking, mock_linked_bucket_manager):
        """Test error handling for generic exceptions."""
        mock_linked_bucket_manager.link_bucket.side_effect = ValueError("Invalid bucket name")

        response = client_with_linking.post(
            "/api/files/buckets/link?customer_id=cust-001",
            json={
                "bucket_name": "my-bucket",
                "bucket_type": "secondary",
            },
        )

        assert response.status_code == 500
        data = response.json()
        assert "Invalid bucket name" in data["detail"]


class TestBucketBrowseEndpoint:
    """Test bucket browsing endpoint."""

    @pytest.fixture
    def mock_linked_bucket_manager_browse(self):
        """Mock LinkedBucketManager for browse tests."""
        manager = MagicMock(spec=LinkedBucketManager)
        bucket = LinkedBucket(
            bucket_id="bucket-123",
            customer_id="cust-001",
            bucket_name="test-bucket",
            bucket_type="secondary",
            display_name="Test Bucket",
            is_validated=True,
            can_read=True,
            can_write=True,
            can_list=True,
            region="us-west-2",
            linked_at="2024-01-01T00:00:00Z",
            read_only=False,
            prefix_restriction=None,
        )
        manager.get_bucket.return_value = bucket
        return manager

    @pytest.fixture
    def client_with_browse(self, mock_file_registry, mock_linked_bucket_manager_browse):
        """Create client with browse capability."""
        app = FastAPI()
        router = create_file_api_router(
            mock_file_registry,
            linked_bucket_manager=mock_linked_bucket_manager_browse,
        )
        app.include_router(router)
        return TestClient(app)

    @patch("boto3.Session")
    def test_browse_bucket_success(self, mock_session, client_with_browse, mock_linked_bucket_manager_browse):
        """Test successful bucket browsing."""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_session.return_value.client.return_value = mock_s3

        # Mock paginator
        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "CommonPrefixes": [{"Prefix": "folder1/"}],
                "Contents": [
                    {"Key": "file1.fastq.gz", "Size": 1024, "LastModified": MagicMock(isoformat=lambda: "2024-01-01T00:00:00Z")},
                ],
            }
        ]

        response = client_with_browse.get(
            "/api/files/buckets/bucket-123/browse?customer_id=cust-001"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["bucket_id"] == "bucket-123"
        assert data["bucket_name"] == "test-bucket"
        assert len(data["items"]) == 2  # 1 folder + 1 file

    def test_browse_bucket_not_found(self, client_with_browse, mock_linked_bucket_manager_browse):
        """Test browsing non-existent bucket."""
        mock_linked_bucket_manager_browse.get_bucket.return_value = None

        response = client_with_browse.get(
            "/api/files/buckets/nonexistent/browse?customer_id=cust-001"
        )

        assert response.status_code == 404

    def test_browse_bucket_wrong_customer(self, client_with_browse, mock_linked_bucket_manager_browse):
        """Test browsing bucket belonging to different customer."""
        response = client_with_browse.get(
            "/api/files/buckets/bucket-123/browse?customer_id=other-customer"
        )

        assert response.status_code == 403


class TestCreateFolderEndpoint:
    """Test folder creation endpoint."""

    @pytest.fixture
    def mock_linked_bucket_manager_folder(self):
        """Mock LinkedBucketManager for folder tests."""
        manager = MagicMock(spec=LinkedBucketManager)
        bucket = LinkedBucket(
            bucket_id="bucket-123",
            customer_id="cust-001",
            bucket_name="test-bucket",
            bucket_type="secondary",
            display_name="Test Bucket",
            is_validated=True,
            can_read=True,
            can_write=True,
            can_list=True,
            region="us-west-2",
            linked_at="2024-01-01T00:00:00Z",
            read_only=False,
            prefix_restriction=None,
        )
        manager.get_bucket.return_value = bucket
        return manager

    @pytest.fixture
    def client_with_folder(self, mock_file_registry, mock_linked_bucket_manager_folder):
        """Create client with folder creation capability."""
        app = FastAPI()
        router = create_file_api_router(
            mock_file_registry,
            linked_bucket_manager=mock_linked_bucket_manager_folder,
        )
        app.include_router(router)
        return TestClient(app)

    @patch("boto3.Session")
    def test_create_folder_success(self, mock_session, client_with_folder):
        """Test successful folder creation."""
        mock_s3 = MagicMock()
        mock_session.return_value.client.return_value = mock_s3

        response = client_with_folder.post(
            "/api/files/buckets/bucket-123/folders?customer_id=cust-001&prefix=",
            json={"folder_name": "new-folder"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "new-folder/" in data["folder_key"]

    def test_create_folder_read_only_bucket(self, client_with_folder, mock_linked_bucket_manager_folder):
        """Test folder creation on read-only bucket."""
        bucket = mock_linked_bucket_manager_folder.get_bucket.return_value
        bucket.read_only = True

        response = client_with_folder.post(
            "/api/files/buckets/bucket-123/folders?customer_id=cust-001",
            json={"folder_name": "new-folder"},
        )

        assert response.status_code == 403

    def test_create_folder_empty_name(self, client_with_folder):
        """Test folder creation with empty name."""
        response = client_with_folder.post(
            "/api/files/buckets/bucket-123/folders?customer_id=cust-001",
            json={"folder_name": ""},
        )

        # Pydantic validation should fail
        assert response.status_code == 422


class TestDeleteFileEndpoint:
    """Test file deletion endpoint."""

    @pytest.fixture
    def mock_linked_bucket_manager_delete(self):
        """Mock LinkedBucketManager for delete tests."""
        manager = MagicMock(spec=LinkedBucketManager)
        bucket = LinkedBucket(
            bucket_id="bucket-123",
            customer_id="cust-001",
            bucket_name="test-bucket",
            bucket_type="secondary",
            display_name="Test Bucket",
            is_validated=True,
            can_read=True,
            can_write=True,
            can_list=True,
            region="us-west-2",
            linked_at="2024-01-01T00:00:00Z",
            read_only=False,
            prefix_restriction=None,
        )
        manager.get_bucket.return_value = bucket
        return manager

    @pytest.fixture
    def client_with_delete(self, mock_file_registry, mock_linked_bucket_manager_delete):
        """Create client with delete capability."""
        app = FastAPI()
        router = create_file_api_router(
            mock_file_registry,
            linked_bucket_manager=mock_linked_bucket_manager_delete,
        )
        app.include_router(router)
        return TestClient(app)

    @patch("boto3.Session")
    def test_delete_file_success(self, mock_session, client_with_delete, mock_file_registry):
        """Test successful file deletion."""
        mock_s3 = MagicMock()
        mock_session.return_value.client.return_value = mock_s3
        mock_file_registry.get_file.return_value = None  # File not registered

        response = client_with_delete.delete(
            "/api/files/buckets/bucket-123/files?customer_id=cust-001&file_key=test-file.txt"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_registered_file_blocked(self, client_with_delete, mock_file_registry):
        """Test that registered files cannot be deleted."""
        mock_file_registry.get_file.return_value = MagicMock()  # File is registered

        response = client_with_delete.delete(
            "/api/files/buckets/bucket-123/files?customer_id=cust-001&file_key=registered-file.fastq.gz"
        )

        assert response.status_code == 409
        assert "registered" in response.json()["detail"].lower()

    def test_delete_file_read_only_bucket(self, client_with_delete, mock_linked_bucket_manager_delete):
        """Test file deletion on read-only bucket."""
        bucket = mock_linked_bucket_manager_delete.get_bucket.return_value
        bucket.read_only = True

        response = client_with_delete.delete(
            "/api/files/buckets/bucket-123/files?customer_id=cust-001&file_key=test-file.txt"
        )

        assert response.status_code == 403

