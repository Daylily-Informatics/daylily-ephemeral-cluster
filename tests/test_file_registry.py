"""
Tests for file_registry.py - File registration and metadata storage.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from daylib.file_registry import (
    BiosampleMetadata,
    FileMetadata,
    FileRegistration,
    FileRegistry,
    FileSet,
    FileWorksetUsage,
    SequencingMetadata,
)


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB resource."""
    with patch("daylib.file_registry.boto3.Session") as mock_session:
        mock_dynamodb_resource = MagicMock()
        mock_session.return_value.resource.return_value = mock_dynamodb_resource
        yield mock_dynamodb_resource


@pytest.fixture
def file_registry(mock_dynamodb):
    """Create a FileRegistry instance with mocked DynamoDB."""
    registry = FileRegistry(
        files_table_name="test-files",
        filesets_table_name="test-filesets",
        file_workset_usage_table_name="test-file-workset-usage",
    )
    registry.files_table = MagicMock()
    registry.filesets_table = MagicMock()
    registry.file_workset_usage_table = MagicMock()
    return registry


class TestFileMetadata:
    """Test FileMetadata dataclass."""
    
    def test_create_file_metadata(self):
        """Test creating file metadata."""
        metadata = FileMetadata(
            file_id="file-001",
            s3_uri="s3://bucket/sample_R1.fastq.gz",
            file_size_bytes=1024000,
            md5_checksum="abc123def456",
            file_format="fastq",
        )
        
        assert metadata.file_id == "file-001"
        assert metadata.s3_uri == "s3://bucket/sample_R1.fastq.gz"
        assert metadata.file_size_bytes == 1024000
        assert metadata.md5_checksum == "abc123def456"
        assert metadata.file_format == "fastq"
        assert metadata.created_at is not None


class TestBiosampleMetadata:
    """Test BiosampleMetadata dataclass."""
    
    def test_create_biosample_metadata(self):
        """Test creating biosample metadata."""
        metadata = BiosampleMetadata(
            biosample_id="biosample-001",
            subject_id="HG002",
            sample_type="blood",
            tissue_type="whole blood",
            collection_date="2024-01-15",
            preservation_method="frozen",
        )
        
        assert metadata.biosample_id == "biosample-001"
        assert metadata.subject_id == "HG002"
        assert metadata.sample_type == "blood"
        assert metadata.tissue_type == "whole blood"
        assert metadata.collection_date == "2024-01-15"
        assert metadata.preservation_method == "frozen"


class TestSequencingMetadata:
    """Test SequencingMetadata dataclass."""
    
    def test_create_sequencing_metadata(self):
        """Test creating sequencing metadata."""
        metadata = SequencingMetadata(
            platform="ILLUMINA_NOVASEQ_X",
            vendor="ILMN",
            run_id="run-001",
            lane=1,
            barcode_id="S1",
            flowcell_id="FLOWCELL123",
        )
        
        assert metadata.platform == "ILLUMINA_NOVASEQ_X"
        assert metadata.vendor == "ILMN"
        assert metadata.run_id == "run-001"
        assert metadata.lane == 1
        assert metadata.barcode_id == "S1"
        assert metadata.flowcell_id == "FLOWCELL123"


class TestFileRegistration:
    """Test FileRegistration dataclass."""
    
    def test_create_file_registration(self):
        """Test creating a complete file registration."""
        file_meta = FileMetadata(
            file_id="file-001",
            s3_uri="s3://bucket/sample_R1.fastq.gz",
            file_size_bytes=1024000,
        )
        seq_meta = SequencingMetadata(run_id="run-001")
        bio_meta = BiosampleMetadata(biosample_id="bio-001", subject_id="HG002")
        
        registration = FileRegistration(
            file_id="file-001",
            customer_id="cust-001",
            file_metadata=file_meta,
            sequencing_metadata=seq_meta,
            biosample_metadata=bio_meta,
            read_number=1,
            quality_score=35.5,
            percent_q30=85.0,
            tags=["wgs", "high-quality"],
        )
        
        assert registration.file_id == "file-001"
        assert registration.customer_id == "cust-001"
        assert registration.read_number == 1
        assert registration.quality_score == 35.5
        assert registration.percent_q30 == 85.0
        assert "wgs" in registration.tags


class TestFileSet:
    """Test FileSet dataclass."""
    
    def test_create_fileset(self):
        """Test creating a file set."""
        bio_meta = BiosampleMetadata(biosample_id="bio-001", subject_id="HG002")
        seq_meta = SequencingMetadata(run_id="run-001")
        
        fileset = FileSet(
            fileset_id="fileset-001",
            customer_id="cust-001",
            name="HG002 WGS",
            description="Whole genome sequencing of HG002",
            biosample_metadata=bio_meta,
            sequencing_metadata=seq_meta,
            file_ids=["file-001", "file-002"],
        )
        
        assert fileset.fileset_id == "fileset-001"
        assert fileset.customer_id == "cust-001"
        assert fileset.name == "HG002 WGS"
        assert len(fileset.file_ids) == 2
        assert fileset.biosample_metadata.subject_id == "HG002"


class TestFileRegistryRegisterFile:
    """Test file registration."""
    
    def test_register_file_success(self, file_registry):
        """Test successful file registration."""
        file_registry.files_table.put_item.return_value = {}
        
        file_meta = FileMetadata(
            file_id="file-001",
            s3_uri="s3://bucket/sample_R1.fastq.gz",
            file_size_bytes=1024000,
        )
        seq_meta = SequencingMetadata(run_id="run-001")
        bio_meta = BiosampleMetadata(biosample_id="bio-001", subject_id="HG002")
        
        registration = FileRegistration(
            file_id="file-001",
            customer_id="cust-001",
            file_metadata=file_meta,
            sequencing_metadata=seq_meta,
            biosample_metadata=bio_meta,
        )
        
        result = file_registry.register_file(registration)
        
        assert result is True
        file_registry.files_table.put_item.assert_called_once()
    
    def test_register_file_already_exists(self, file_registry):
        """Test registering a file that already exists."""
        from botocore.exceptions import ClientError
        
        error_response = {"Error": {"Code": "ConditionalCheckFailedException"}}
        file_registry.files_table.put_item.side_effect = ClientError(error_response, "PutItem")
        
        file_meta = FileMetadata(
            file_id="file-001",
            s3_uri="s3://bucket/sample_R1.fastq.gz",
            file_size_bytes=1024000,
        )
        seq_meta = SequencingMetadata(run_id="run-001")
        bio_meta = BiosampleMetadata(biosample_id="bio-001", subject_id="HG002")
        
        registration = FileRegistration(
            file_id="file-001",
            customer_id="cust-001",
            file_metadata=file_meta,
            sequencing_metadata=seq_meta,
            biosample_metadata=bio_meta,
        )
        
        result = file_registry.register_file(registration)
        
        assert result is False


class TestFileRegistryGetFile:
    """Test file retrieval."""
    
    def test_get_file_success(self, file_registry):
        """Test retrieving a registered file."""
        import json
        
        file_meta = FileMetadata(
            file_id="file-001",
            s3_uri="s3://bucket/sample_R1.fastq.gz",
            file_size_bytes=1024000,
        )
        seq_meta = SequencingMetadata(run_id="run-001")
        bio_meta = BiosampleMetadata(biosample_id="bio-001", subject_id="HG002")
        
        item = {
            "file_id": "file-001",
            "customer_id": "cust-001",
            "file_metadata": json.dumps({
                "file_id": "file-001",
                "s3_uri": "s3://bucket/sample_R1.fastq.gz",
                "file_size_bytes": 1024000,
                "md5_checksum": None,
                "file_format": "fastq",
                "created_at": "2024-01-15T00:00:00Z",
            }),
            "sequencing_metadata": json.dumps({
                "platform": "ILLUMINA_NOVASEQ_X",
                "vendor": "ILMN",
                "run_id": "run-001",
                "lane": 0,
                "barcode_id": "S1",
                "flowcell_id": None,
                "run_date": None,
            }),
            "biosample_metadata": json.dumps({
                "biosample_id": "bio-001",
                "subject_id": "HG002",
                "sample_type": "blood",
                "tissue_type": None,
                "collection_date": None,
                "preservation_method": None,
                "tumor_fraction": None,
            }),
            "read_number": 1,
            "registered_at": "2024-01-15T00:00:00Z",
            "updated_at": "2024-01-15T00:00:00Z",
            "tags": [],
        }
        
        file_registry.files_table.get_item.return_value = {"Item": item}
        
        result = file_registry.get_file("file-001")
        
        assert result is not None
        assert result.file_id == "file-001"
        assert result.customer_id == "cust-001"
        assert result.biosample_metadata.subject_id == "HG002"
    
    def test_get_file_not_found(self, file_registry):
        """Test retrieving a non-existent file."""
        file_registry.files_table.get_item.return_value = {}
        
        result = file_registry.get_file("nonexistent")
        
        assert result is None


class TestFileRegistryCreateFileset:
    """Test file set creation."""
    
    def test_create_fileset_success(self, file_registry):
        """Test successful file set creation."""
        file_registry.filesets_table.put_item.return_value = {}
        
        bio_meta = BiosampleMetadata(biosample_id="bio-001", subject_id="HG002")
        fileset = FileSet(
            fileset_id="fileset-001",
            customer_id="cust-001",
            name="HG002 WGS",
            biosample_metadata=bio_meta,
            file_ids=["file-001", "file-002"],
        )
        
        result = file_registry.create_fileset(fileset)
        
        assert result is True
        file_registry.filesets_table.put_item.assert_called_once()


class TestFileRegistryListCustomerFiles:
    """Test listing customer files."""
    
    def test_list_customer_files(self, file_registry):
        """Test listing files for a customer."""
        import json
        
        items = [
            {
                "file_id": "file-001",
                "customer_id": "cust-001",
                "file_metadata": json.dumps({
                    "file_id": "file-001",
                    "s3_uri": "s3://bucket/sample_R1.fastq.gz",
                    "file_size_bytes": 1024000,
                    "md5_checksum": None,
                    "file_format": "fastq",
                    "created_at": "2024-01-15T00:00:00Z",
                }),
                "sequencing_metadata": json.dumps({
                    "platform": "ILLUMINA_NOVASEQ_X",
                    "vendor": "ILMN",
                    "run_id": "run-001",
                    "lane": 0,
                    "barcode_id": "S1",
                    "flowcell_id": None,
                    "run_date": None,
                }),
                "biosample_metadata": json.dumps({
                    "biosample_id": "bio-001",
                    "subject_id": "HG002",
                    "sample_type": "blood",
                    "tissue_type": None,
                    "collection_date": None,
                    "preservation_method": None,
                    "tumor_fraction": None,
                }),
                "read_number": 1,
                "registered_at": "2024-01-15T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
                "tags": [],
            }
        ]
        
        file_registry.files_table.query.return_value = {"Items": items}

        results = file_registry.list_customer_files("cust-001")

        assert len(results) == 1
        assert results[0].file_id == "file-001"
        assert results[0].customer_id == "cust-001"


class TestFileWorksetUsage:
    """Test FileWorksetUsage dataclass."""

    def test_create_file_workset_usage(self):
        """Test creating file-workset usage record."""
        usage = FileWorksetUsage(
            file_id="file-001",
            workset_id="ws-001",
            customer_id="cust-001",
            usage_type="input",
            workset_state="RUNNING",
            notes="Test usage",
        )

        assert usage.file_id == "file-001"
        assert usage.workset_id == "ws-001"
        assert usage.customer_id == "cust-001"
        assert usage.usage_type == "input"
        assert usage.workset_state == "RUNNING"
        assert usage.notes == "Test usage"


class TestFileRegistryWorksetUsage:
    """Test file-workset usage tracking methods."""

    def test_record_file_workset_usage(self, file_registry):
        """Test recording file-workset usage."""
        result = file_registry.record_file_workset_usage(
            file_id="file-001",
            workset_id="ws-001",
            customer_id="cust-001",
            usage_type="input",
            workset_state="READY",
        )

        assert result is True
        file_registry.file_workset_usage_table.put_item.assert_called_once()

    def test_get_file_workset_history(self, file_registry):
        """Test getting file workset history."""
        items = [
            {
                "file_id": "file-001",
                "workset_id": "ws-001",
                "customer_id": "cust-001",
                "usage_type": "input",
                "added_at": "2024-01-15T00:00:00Z",
                "workset_state": "COMPLETED",
            },
            {
                "file_id": "file-001",
                "workset_id": "ws-002",
                "customer_id": "cust-001",
                "usage_type": "input",
                "added_at": "2024-01-16T00:00:00Z",
                "workset_state": "RUNNING",
            },
        ]

        file_registry.file_workset_usage_table.query.return_value = {"Items": items}

        results = file_registry.get_file_workset_history("file-001")

        assert len(results) == 2
        assert results[0].workset_id == "ws-001"
        assert results[1].workset_id == "ws-002"

    def test_get_workset_files(self, file_registry):
        """Test getting files used in a workset."""
        items = [
            {
                "file_id": "file-001",
                "workset_id": "ws-001",
                "customer_id": "cust-001",
                "usage_type": "input",
                "added_at": "2024-01-15T00:00:00Z",
            },
            {
                "file_id": "file-002",
                "workset_id": "ws-001",
                "customer_id": "cust-001",
                "usage_type": "input",
                "added_at": "2024-01-15T00:00:00Z",
            },
        ]

        file_registry.file_workset_usage_table.query.return_value = {"Items": items}

        results = file_registry.get_workset_files("ws-001")

        assert len(results) == 2
        assert results[0].file_id == "file-001"
        assert results[1].file_id == "file-002"
