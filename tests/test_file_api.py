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
    # By default, pretend there is no existing registration for a given S3 URI so
    # tests exercise the happy-path flow unless they override this behavior.
    registry.find_file_by_s3_uri.return_value = None
    return registry


@pytest.fixture
def mock_file_registry_with_get():
    """Mock FileRegistry with get_file support for update/download tests."""
    registry = MagicMock(spec=FileRegistry)
    registry.update_file.return_value = True

    # Mock get_file to return a file registration with a valid S3 URI so that
    # download and metadata update flows can exercise the happy path.
    from daylib.file_registry import (
        FileRegistration,
        FileMetadata,
        SequencingMetadata,
        BiosampleMetadata,
    )

    file_reg = FileRegistration(
        file_id="file-001",
        customer_id="cust-001",
        file_metadata=FileMetadata(
            file_id="file-001",
            s3_uri="s3://bucket/sample_R1.fastq.gz",
            file_size_bytes=1024000,
            md5_checksum="abc123",
            file_format="fastq",
        ),
        sequencing_metadata=SequencingMetadata(
            platform="ILLUMINA_NOVASEQ_X",
            vendor="ILMN",
            run_id="run-001",
        ),
        biosample_metadata=BiosampleMetadata(
            biosample_id="bio-001",
            subject_id="HG002",
            sample_type="blood",
        ),
        read_number=1,
        tags=["wgs"],
    )
    registry.get_file.return_value = file_reg
    return registry


@pytest.fixture
def client_with_update(mock_file_registry_with_get):
    """Create client with update/download capability using a registry with get."""
    app = FastAPI()
    router = create_file_api_router(mock_file_registry_with_get)
    app.include_router(router)
    return TestClient(app)


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

    def test_register_file_conflict_existing_s3_uri(self, client, mock_file_registry):
        """Test conflict when a file with the same S3 URI already exists.

        This exercises the S3-URI-based uniqueness check that calls
        FileRegistry.find_file_by_s3_uri before attempting registration.
        """
        # Simulate an existing registration returned from the registry
        existing = MagicMock()
        existing.file_id = "file-existing-1234"
        mock_file_registry.find_file_by_s3_uri.return_value = existing

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
        data = response.json()
        # Ensure the error message references the existing file_id for clarity
        assert "file-existing-1234" in data["detail"]


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


class TestUpdateFileMetadataEndpoint:
    """Test file metadata update endpoint - PATCH /api/files/{file_id}"""

    def test_update_file_metadata_md5_checksum(self, client_with_update, mock_file_registry_with_get):
        """Test updating MD5 checksum in file metadata."""
        payload = {
            "file_metadata": {
                "md5_checksum": "new_md5_hash_123456",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == "file-001"
        assert data["status"] == "updated"

        # Verify update_file was called with correct parameters
        mock_file_registry_with_get.update_file.assert_called_once()
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["file_id"] == "file-001"
        assert call_kwargs["file_metadata"]["md5_checksum"] == "new_md5_hash_123456"

    def test_update_file_metadata_file_format(self, client_with_update, mock_file_registry_with_get):
        """Test updating file format in file metadata."""
        payload = {
            "file_metadata": {
                "file_format": "bam",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["file_metadata"]["file_format"] == "bam"

    def test_update_file_metadata_multiple_fields(self, client_with_update, mock_file_registry_with_get):
        """Test updating multiple file metadata fields at once."""
        payload = {
            "file_metadata": {
                "md5_checksum": "new_md5_hash",
                "file_format": "bam",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["file_metadata"]["md5_checksum"] == "new_md5_hash"
        assert call_kwargs["file_metadata"]["file_format"] == "bam"


class TestFileDownloadEndpoint:
    """Tests for GET /api/files/{file_id}/download."""

    def test_get_file_download_url_success(self, client_with_update, mock_file_registry_with_get):
        """Return a presigned URL for an existing registered file."""

        # The mock registry created in mock_file_registry_with_get already returns
        # a FileRegistration with a valid s3://bucket/key URI.
        with patch("daylib.file_api.boto3.client") as mock_boto_client:
            mock_s3 = mock_boto_client.return_value
            mock_s3.generate_presigned_url.return_value = "https://signed-url"

            response = client_with_update.get("/api/files/file-001/download")

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://signed-url"

        # Ensure we called S3 with the expected bucket and key components.
        mock_s3.generate_presigned_url.assert_called_once()
        args, kwargs = mock_s3.generate_presigned_url.call_args
        assert args[0] == "get_object"
        assert kwargs["Params"]["Bucket"] == "bucket"
        assert kwargs["Params"]["Key"] == "sample_R1.fastq.gz"
        # Default expiry should be 3600 seconds
        assert kwargs["ExpiresIn"] == 3600

    def test_get_file_download_url_not_found(self, client_with_update, mock_file_registry_with_get):
        """Return 404 when the file_id is not registered."""

        mock_file_registry_with_get.get_file.return_value = None

        response = client_with_update.get("/api/files/unknown-file/download")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_file_download_url_custom_expiry(self, client_with_update, mock_file_registry_with_get):
        """Allow overriding URL expiry via query parameter."""

        with patch("daylib.file_api.boto3.client") as mock_boto_client:
            mock_s3 = mock_boto_client.return_value
            mock_s3.generate_presigned_url.return_value = "https://signed-url"

            response = client_with_update.get("/api/files/file-001/download?expires_in=600")

        assert response.status_code == 200
        mock_s3.generate_presigned_url.assert_called_once()
        _, kwargs = mock_s3.generate_presigned_url.call_args
        assert kwargs["ExpiresIn"] == 600

    def test_get_file_download_url_invalid_expiry(self, client_with_update):
        """Reject expiry values outside the allowed range."""

        # Too short (< 60 seconds) should fail validation
        response = client_with_update.get("/api/files/file-001/download?expires_in=10")
        assert response.status_code == 422


    def test_get_file_download_url_enforces_customer_ownership_mismatch(self, mock_file_registry_with_get):
        """Return 403 when authenticated customer does not own the file."""

        app = FastAPI()

        async def fake_auth_mismatch():
            # Authenticated user belongs to a different customer
            return {"customer_id": "cust-OTHER"}

        router = create_file_api_router(
            mock_file_registry_with_get,
            auth_dependency=fake_auth_mismatch,
        )
        app.include_router(router)
        client = TestClient(app)

        with patch("daylib.file_api.boto3.client") as mock_boto_client:
            response = client.get("/api/files/file-001/download")

        assert response.status_code == 403
        assert "does not belong" in response.json()["detail"]
        # Ownership check should fail before any S3 interaction
        mock_boto_client.assert_not_called()


    def test_get_file_download_url_allows_matching_customer_id(self, mock_file_registry_with_get):
        """Allow download when authenticated customer_id matches the file's customer_id."""

        app = FastAPI()

        async def fake_auth_match():
            return {"customer_id": "cust-001"}

        router = create_file_api_router(
            mock_file_registry_with_get,
            auth_dependency=fake_auth_match,
        )
        app.include_router(router)
        client = TestClient(app)

        with patch("daylib.file_api.boto3.client") as mock_boto_client:
            mock_s3 = mock_boto_client.return_value
            mock_s3.generate_presigned_url.return_value = "https://signed-url"

            response = client.get("/api/files/file-001/download")

        assert response.status_code == 200
        assert response.json()["url"] == "https://signed-url"


    def test_get_file_download_url_allows_matching_custom_customer_claim(self, mock_file_registry_with_get):
        """Support Cognito-style custom:customer_id claim for ownership checks."""

        app = FastAPI()

        async def fake_auth_custom_claim():
            # Simulate CognitoAuth.get_current_user() style payload
            return {"custom:customer_id": "cust-001"}

        router = create_file_api_router(
            mock_file_registry_with_get,
            auth_dependency=fake_auth_custom_claim,
        )
        app.include_router(router)
        client = TestClient(app)

        with patch("daylib.file_api.boto3.client") as mock_boto_client:
            mock_s3 = mock_boto_client.return_value
            mock_s3.generate_presigned_url.return_value = "https://signed-url"

            response = client.get("/api/files/file-001/download")

        assert response.status_code == 200
        assert response.json()["url"] == "https://signed-url"


class TestAddFileToFilesetEndpoint:
    """Tests for POST /api/files/{file_id}/add-to-fileset."""

    def test_add_file_to_fileset_success(self, client, mock_file_registry):
        """Successfully add a single file to a fileset."""

        # Ensure the file exists and fileset update succeeds.
        mock_file_registry.get_file.return_value = object()
        mock_file_registry.add_files_to_fileset.return_value = True

        response = client.post(
            "/api/files/file-123/add-to-fileset",
            json={"fileset_id": "fs-001"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["fileset_id"] == "fs-001"
        assert data["file_id"] == "file-123"
        assert data["status"] == "updated"

        mock_file_registry.add_files_to_fileset.assert_called_once_with("fs-001", ["file-123"])

    def test_add_file_to_fileset_file_not_found(self, client, mock_file_registry):
        """Return 404 when the file_id does not exist."""

        mock_file_registry.get_file.return_value = None

        response = client.post(
            "/api/files/missing-file/add-to-fileset",
            json={"fileset_id": "fs-001"},
        )

        assert response.status_code == 404
        assert "file" in response.json()["detail"].lower()

    def test_add_file_to_fileset_fileset_not_found(self, client, mock_file_registry):
        """Return 404 when the target fileset does not exist."""

        mock_file_registry.get_file.return_value = object()
        mock_file_registry.add_files_to_fileset.return_value = False

        response = client.post(
            "/api/files/file-123/add-to-fileset",
            json={"fileset_id": "missing-fs"},
        )

        assert response.status_code == 404
        assert "fileset" in response.json()["detail"].lower()

    def test_update_biosample_metadata_biosample_id(self, client_with_update, mock_file_registry_with_get):
        """Test updating biosample ID."""
        payload = {
            "biosample_metadata": {
                "biosample_id": "bio-updated",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["biosample_metadata"]["biosample_id"] == "bio-updated"

    def test_update_biosample_metadata_subject_id(self, client_with_update, mock_file_registry_with_get):
        """Test updating subject ID."""
        payload = {
            "biosample_metadata": {
                "subject_id": "HG003",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["biosample_metadata"]["subject_id"] == "HG003"

    def test_update_biosample_metadata_sample_type(self, client_with_update, mock_file_registry_with_get):
        """Test updating sample type."""
        payload = {
            "biosample_metadata": {
                "sample_type": "tissue",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["biosample_metadata"]["sample_type"] == "tissue"

    def test_update_biosample_metadata_all_fields(self, client_with_update, mock_file_registry_with_get):
        """Test updating all biosample metadata fields."""
        payload = {
            "biosample_metadata": {
                "biosample_id": "bio-new",
                "subject_id": "HG004",
                "sample_type": "saliva",
                "tissue_type": "oral",
                "collection_date": "2024-01-15",
                "preservation_method": "frozen",
                "tumor_fraction": 0.35,
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        bio_meta = call_kwargs["biosample_metadata"]
        assert bio_meta["biosample_id"] == "bio-new"
        assert bio_meta["subject_id"] == "HG004"
        assert bio_meta["sample_type"] == "saliva"
        assert bio_meta["tissue_type"] == "oral"
        assert bio_meta["collection_date"] == "2024-01-15"
        assert bio_meta["preservation_method"] == "frozen"
        assert bio_meta["tumor_fraction"] == 0.35

    def test_update_sequencing_metadata_platform(self, client_with_update, mock_file_registry_with_get):
        """Test updating sequencing platform."""
        payload = {
            "sequencing_metadata": {
                "platform": "ILLUMINA_HISEQ",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["sequencing_metadata"]["platform"] == "ILLUMINA_HISEQ"

    def test_update_sequencing_metadata_vendor(self, client_with_update, mock_file_registry_with_get):
        """Test updating sequencing vendor."""
        payload = {
            "sequencing_metadata": {
                "vendor": "10X",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["sequencing_metadata"]["vendor"] == "10X"

    def test_update_sequencing_metadata_run_id(self, client_with_update, mock_file_registry_with_get):
        """Test updating run ID."""
        payload = {
            "sequencing_metadata": {
                "run_id": "run-new-123",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["sequencing_metadata"]["run_id"] == "run-new-123"

    def test_update_sequencing_metadata_lane(self, client_with_update, mock_file_registry_with_get):
        """Test updating lane number."""
        payload = {
            "sequencing_metadata": {
                "lane": 3,
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["sequencing_metadata"]["lane"] == 3

    def test_update_sequencing_metadata_barcode_id(self, client_with_update, mock_file_registry_with_get):
        """Test updating barcode ID."""
        payload = {
            "sequencing_metadata": {
                "barcode_id": "S42",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["sequencing_metadata"]["barcode_id"] == "S42"

    def test_update_sequencing_metadata_flowcell_id(self, client_with_update, mock_file_registry_with_get):
        """Test updating flowcell ID."""
        payload = {
            "sequencing_metadata": {
                "flowcell_id": "FLOWCELL123",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["sequencing_metadata"]["flowcell_id"] == "FLOWCELL123"

    def test_update_sequencing_metadata_run_date(self, client_with_update, mock_file_registry_with_get):
        """Test updating run date."""
        payload = {
            "sequencing_metadata": {
                "run_date": "2024-01-15",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["sequencing_metadata"]["run_date"] == "2024-01-15"

    def test_update_sequencing_metadata_all_fields(self, client_with_update, mock_file_registry_with_get):
        """Test updating all sequencing metadata fields."""
        payload = {
            "sequencing_metadata": {
                "platform": "ILLUMINA_HISEQ",
                "vendor": "ILMN",
                "run_id": "run-updated",
                "lane": 2,
                "barcode_id": "S99",
                "flowcell_id": "FC123456",
                "run_date": "2024-01-20",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        seq_meta = call_kwargs["sequencing_metadata"]
        assert seq_meta["platform"] == "ILLUMINA_HISEQ"
        assert seq_meta["vendor"] == "ILMN"
        assert seq_meta["run_id"] == "run-updated"
        assert seq_meta["lane"] == 2
        assert seq_meta["barcode_id"] == "S99"
        assert seq_meta["flowcell_id"] == "FC123456"
        assert seq_meta["run_date"] == "2024-01-20"

    def test_update_read_number(self, client_with_update, mock_file_registry_with_get):
        """Test updating read number."""
        payload = {
            "read_number": 2,
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["read_number"] == 2

    def test_update_paired_with(self, client_with_update, mock_file_registry_with_get):
        """Test updating paired file reference."""
        payload = {
            "paired_with": "file-002",
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["paired_with"] == "file-002"

    def test_update_quality_score(self, client_with_update, mock_file_registry_with_get):
        """Test updating quality score."""
        payload = {
            "quality_score": 38.5,
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["quality_score"] == 38.5

    def test_update_percent_q30(self, client_with_update, mock_file_registry_with_get):
        """Test updating percent Q30."""
        payload = {
            "percent_q30": 92.5,
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["percent_q30"] == 92.5

    def test_update_is_positive_control(self, client_with_update, mock_file_registry_with_get):
        """Test updating positive control flag."""
        payload = {
            "is_positive_control": True,
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["is_positive_control"] is True

    def test_update_is_negative_control(self, client_with_update, mock_file_registry_with_get):
        """Test updating negative control flag."""
        payload = {
            "is_negative_control": True,
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["is_negative_control"] is True

    def test_update_tags(self, client_with_update, mock_file_registry_with_get):
        """Test updating tags."""
        payload = {
            "tags": ["wgs", "high-quality", "validated"],
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["tags"] == ["wgs", "high-quality", "validated"]

    def test_update_all_fields_together(self, client_with_update, mock_file_registry_with_get):
        """Test updating all metadata fields at once."""
        payload = {
            "file_metadata": {
                "md5_checksum": "new_md5",
                "file_format": "bam",
            },
            "biosample_metadata": {
                "biosample_id": "bio-new",
                "subject_id": "HG005",
                "sample_type": "tissue",
            },
            "sequencing_metadata": {
                "platform": "ILLUMINA_HISEQ",
                "run_id": "run-new",
                "lane": 4,
            },
            "read_number": 2,
            "paired_with": "file-002",
            "quality_score": 40.0,
            "percent_q30": 95.0,
            "is_positive_control": False,
            "is_negative_control": False,
            "tags": ["wgs", "validated"],
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]

        # Verify all fields were passed
        assert call_kwargs["file_id"] == "file-001"
        assert call_kwargs["file_metadata"]["md5_checksum"] == "new_md5"
        assert call_kwargs["file_metadata"]["file_format"] == "bam"
        assert call_kwargs["biosample_metadata"]["biosample_id"] == "bio-new"
        assert call_kwargs["biosample_metadata"]["subject_id"] == "HG005"
        assert call_kwargs["sequencing_metadata"]["platform"] == "ILLUMINA_HISEQ"
        assert call_kwargs["read_number"] == 2
        assert call_kwargs["paired_with"] == "file-002"
        assert call_kwargs["quality_score"] == 40.0
        assert call_kwargs["percent_q30"] == 95.0
        assert call_kwargs["is_positive_control"] is False
        assert call_kwargs["is_negative_control"] is False
        assert call_kwargs["tags"] == ["wgs", "validated"]

    def test_update_file_not_found(self, client_with_update, mock_file_registry_with_get):
        """Test updating a file that doesn't exist."""
        mock_file_registry_with_get.get_file.return_value = None

        payload = {
            "file_metadata": {
                "md5_checksum": "new_md5",
            }
        }

        response = client_with_update.patch(
            "/api/files/nonexistent-file",
            json=payload,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_file_failure(self, client_with_update, mock_file_registry_with_get):
        """Test handling of update failure."""
        mock_file_registry_with_get.update_file.return_value = False

        payload = {
            "file_metadata": {
                "md5_checksum": "new_md5",
            }
        }

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 500
        assert "Failed to update" in response.json()["detail"]

    def test_update_empty_payload(self, client_with_update, mock_file_registry_with_get):
        """Test updating with empty payload (should still succeed)."""
        payload = {}

        response = client_with_update.patch(
            "/api/files/file-001",
            json=payload,
        )

        assert response.status_code == 200
        # update_file should still be called with file_id
        mock_file_registry_with_get.update_file.assert_called_once()
        call_kwargs = mock_file_registry_with_get.update_file.call_args[1]
        assert call_kwargs["file_id"] == "file-001"


class TestManifestGenerationEndpoints:
    """Test manifest generation endpoints for single files and filesets."""

    @pytest.fixture
    def mock_file_registry_with_manifest(self):
        """Mock FileRegistry with manifest generation support."""
        from daylib.file_registry import (
            FileRegistration,
            BiosampleMetadata,
            SequencingMetadata,
            FileMetadata,
        )

        registry = MagicMock(spec=FileRegistry)

        # Create a mock file for single file manifest generation
        mock_file = FileRegistration(
            file_id="file-001",
            customer_id="cust-001",
            file_metadata=FileMetadata(
                file_id="file-001",
                s3_uri="s3://bucket/path/file.fastq.gz",
                file_size_bytes=1000000,
                file_format="fastq",
                md5_checksum="abc123",
            ),
            biosample_metadata=BiosampleMetadata(
                biosample_id="bio-001",
                subject_id="subj-001",
                sample_type="blood",
            ),
            sequencing_metadata=SequencingMetadata(
                platform="ILLUMINA_NOVASEQ_X",
                vendor="ILMN",
                lane=1,
                barcode_id="ATCG",
            ),
            read_number=1,
            paired_with=None,
            is_positive_control=False,
            is_negative_control=False,
        )

        registry.get_file.return_value = mock_file
        registry.get_fileset.return_value = None
        return registry

    @pytest.fixture
    def client_with_manifest(self, mock_file_registry_with_manifest):
        """Create test client with manifest generation support."""
        app = FastAPI()
        router = create_file_api_router(
            file_registry=mock_file_registry_with_manifest,
            auth_dependency=None,
        )
        app.include_router(router)
        return TestClient(app)

    def test_generate_manifest_for_file_success(self, client_with_manifest, mock_file_registry_with_manifest):
        """Test generating manifest for a single file."""
        response = client_with_manifest.post(
            "/api/files/file-001/manifest",
            params={
                "run_id": "R0",
                "stage_target": "/fsx/staged_sample_data/",
                "include_header": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "tsv_content" in data
        assert data["sample_count"] == 1
        assert data["file_count"] == 1
        assert data["warnings"] == []
        # Verify the TSV content contains expected headers
        assert "RUN_ID" in data["tsv_content"]
        assert "SAMPLE_ID" in data["tsv_content"]

    def test_generate_manifest_for_file_not_found(self, client_with_manifest, mock_file_registry_with_manifest):
        """Test generating manifest for non-existent file."""
        mock_file_registry_with_manifest.get_file.return_value = None

        response = client_with_manifest.post(
            "/api/files/nonexistent-file/manifest",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_generate_manifest_for_file_with_custom_params(self, client_with_manifest):
        """Test generating manifest with custom run_id and stage_target."""
        response = client_with_manifest.post(
            "/api/files/file-001/manifest",
            params={
                "run_id": "R1",
                "stage_target": "/custom/path/",
                "include_header": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sample_count"] == 1
        assert data["file_count"] == 1

    def test_generate_manifest_for_fileset_success(self, client_with_manifest, mock_file_registry_with_manifest):
        """Test generating manifest for a fileset."""
        from daylib.file_registry import FileSet

        # Create a mock fileset
        mock_fileset = FileSet(
            fileset_id="fileset-001",
            customer_id="cust-001",
            name="Test FileSet",
            file_ids=["file-001"],
        )

        mock_file_registry_with_manifest.get_fileset.return_value = mock_fileset

        response = client_with_manifest.post(
            "/api/files/filesets/fileset-001/manifest",
            params={
                "run_id": "R0",
                "stage_target": "/fsx/staged_sample_data/",
                "include_header": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "tsv_content" in data
        assert data["sample_count"] == 1
        assert data["file_count"] == 1
        assert data["warnings"] == []

    def test_generate_manifest_for_fileset_not_found(self, client_with_manifest, mock_file_registry_with_manifest):
        """Test generating manifest for non-existent fileset."""
        mock_file_registry_with_manifest.get_fileset.return_value = None

        response = client_with_manifest.post(
            "/api/files/filesets/nonexistent-fileset/manifest",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_generate_manifest_for_empty_fileset(self, client_with_manifest, mock_file_registry_with_manifest):
        """Test generating manifest for fileset with no files."""
        from daylib.file_registry import FileSet

        # Create a mock fileset with no files
        mock_fileset = FileSet(
            fileset_id="fileset-001",
            customer_id="cust-001",
            name="Empty FileSet",
            file_ids=[],
        )

        mock_file_registry_with_manifest.get_fileset.return_value = mock_fileset

        response = client_with_manifest.post(
            "/api/files/filesets/fileset-001/manifest",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sample_count"] == 0
        assert data["file_count"] == 0
        assert len(data["warnings"]) > 0

