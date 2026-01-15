"""Tests for workset_integration.py - State bridge between DynamoDB and S3.

Tests the integration layer that synchronizes DynamoDB state management
with S3 sentinel-based processing system.
"""

import datetime as dt
import json
from unittest.mock import MagicMock, patch, call

import pytest

from daylib.workset_integration import (
    WorksetIntegration,
    SENTINEL_FILES,
    WORK_YAML_NAME,
    INFO_YAML_NAME,
)


@pytest.fixture
def mock_state_db():
    """Create mock WorksetStateDB."""
    mock_db = MagicMock()
    mock_db.register_workset.return_value = True
    mock_db.get_workset.return_value = {
        "workset_id": "test-ws-001",
        "state": "ready",
        "priority": "normal",
        "bucket": "test-bucket",
        "prefix": "worksets/test-ws-001/",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:00:00Z",
    }
    mock_db.update_state.return_value = None
    mock_db.get_ready_worksets.return_value = []
    return mock_db


@pytest.fixture
def mock_s3_client():
    """Create mock S3 client."""
    mock_s3 = MagicMock()
    mock_s3.put_object.return_value = {}
    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: b"2024-01-15T10:00:00Z")
    }
    mock_s3.delete_object.return_value = {}
    mock_s3.list_objects_v2.return_value = {"Contents": [], "KeyCount": 0}
    return mock_s3


@pytest.fixture
def integration(mock_state_db, mock_s3_client):
    """Create WorksetIntegration instance."""
    return WorksetIntegration(
        state_db=mock_state_db,
        s3_client=mock_s3_client,
        bucket="test-bucket",
        prefix="worksets/",
        region="us-west-2",
    )


class TestWorksetIntegrationInit:
    """Test WorksetIntegration initialization."""

    def test_init_with_provided_s3_client(self, mock_state_db, mock_s3_client):
        """Test initialization with provided S3 client."""
        integration = WorksetIntegration(
            state_db=mock_state_db,
            s3_client=mock_s3_client,
            bucket="my-bucket",
            prefix="data/worksets/",
        )
        assert integration._s3 is mock_s3_client
        assert integration.bucket == "my-bucket"
        assert integration.prefix == "data/worksets/"

    def test_init_creates_s3_client_if_not_provided(self, mock_state_db):
        """Test initialization creates S3 client if not provided."""
        with patch("daylib.workset_integration.boto3") as mock_boto3:
            mock_session = MagicMock()
            mock_boto3.Session.return_value = mock_session

            integration = WorksetIntegration(
                state_db=mock_state_db,
                bucket="my-bucket",
                region="us-east-1",
            )

            mock_boto3.Session.assert_called_once_with(region_name="us-east-1")
            mock_session.client.assert_called_once_with("s3")

    def test_init_prefix_normalization(self, mock_state_db, mock_s3_client):
        """Test prefix is normalized with trailing slash."""
        integration = WorksetIntegration(
            state_db=mock_state_db,
            s3_client=mock_s3_client,
            bucket="bucket",
            prefix="worksets",  # No trailing slash
        )
        assert integration.prefix == "worksets/"


class TestRegisterWorkset:
    """Test workset registration."""

    def test_register_workset_dual_write(self, integration, mock_state_db, mock_s3_client):
        """Test registration writes to both DynamoDB and S3."""
        result = integration.register_workset(
            workset_id="new-ws-001",
            bucket="test-bucket",
            prefix="worksets/new-ws-001/",
            priority="high",
            metadata={"name": "Test Workset"},
            write_s3=True,
            write_dynamodb=True,
        )

        assert result is True
        mock_state_db.register_workset.assert_called_once()
        # S3 sentinel should be written
        assert mock_s3_client.put_object.called

    def test_register_workset_dynamodb_only(self, integration, mock_state_db, mock_s3_client):
        """Test registration to DynamoDB only."""
        result = integration.register_workset(
            workset_id="db-only-ws",
            bucket="test-bucket",
            prefix="worksets/db-only-ws/",
            write_s3=False,
            write_dynamodb=True,
        )

        assert result is True
        mock_state_db.register_workset.assert_called_once()

    def test_register_workset_s3_only(self, integration, mock_state_db, mock_s3_client):
        """Test registration to S3 only."""
        result = integration.register_workset(
            workset_id="s3-only-ws",
            bucket="test-bucket",
            prefix="worksets/s3-only-ws/",
            write_s3=True,
            write_dynamodb=False,
        )

        assert result is True
        mock_state_db.register_workset.assert_not_called()
        assert mock_s3_client.put_object.called


class TestWriteSentinel:
    """Test S3 sentinel writing."""

    def test_write_ready_sentinel(self, integration, mock_s3_client):
        """Test writing ready sentinel file."""
        timestamp = "2024-01-15T10:00:00Z"
        integration._write_sentinel(
            bucket="test-bucket",
            prefix="worksets/test/",
            state="ready",
            timestamp=timestamp,
        )

        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "worksets/test/daylily.ready"
        assert call_kwargs["Body"] == timestamp.encode()

    def test_write_in_progress_sentinel(self, integration, mock_s3_client):
        """Test writing in_progress sentinel file."""
        integration._write_sentinel(
            bucket="test-bucket",
            prefix="worksets/test/",
            state="in_progress",
            timestamp="2024-01-15T11:00:00Z",
        )

        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert "daylily.in_progress" in call_kwargs["Key"]

    def test_write_complete_sentinel(self, integration, mock_s3_client):
        """Test writing complete sentinel file."""
        integration._write_sentinel(
            bucket="test-bucket",
            prefix="worksets/test/",
            state="complete",
            timestamp="2024-01-15T12:00:00Z",
        )

        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert "daylily.complete" in call_kwargs["Key"]

    def test_write_error_sentinel(self, integration, mock_s3_client):
        """Test writing error sentinel file."""
        integration._write_sentinel(
            bucket="test-bucket",
            prefix="worksets/test/",
            state="error",
            timestamp="2024-01-15T12:00:00Z",
        )

        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert "daylily.error" in call_kwargs["Key"]


class TestUpdateState:
    """Test state update synchronization."""

    def test_update_state_syncs_both(self, integration, mock_state_db, mock_s3_client):
        """Test state update syncs to both DynamoDB and S3."""
        integration.update_state(
            workset_id="test-ws-001",
            new_state="in_progress",
            reason="Started processing",
            write_s3=True,
            write_dynamodb=True,
        )

        mock_state_db.update_state.assert_called_once()
        # Should write new sentinel
        assert mock_s3_client.put_object.called

    def test_update_state_dynamodb_only(self, integration, mock_state_db, mock_s3_client):
        """Test state update to DynamoDB only."""
        mock_s3_client.reset_mock()

        integration.update_state(
            workset_id="test-ws-001",
            new_state="in_progress",
            reason="Processing started",
            write_s3=False,
            write_dynamodb=True,
        )

        mock_state_db.update_state.assert_called_once()

    def test_update_state_s3_only(self, integration, mock_state_db, mock_s3_client):
        """Test state update to S3 only."""
        mock_state_db.reset_mock()
        mock_s3_client.reset_mock()

        integration.update_state(
            workset_id="test-ws-001",
            new_state="complete",
            reason="Processing finished",
            write_s3=True,
            write_dynamodb=False,
        )

        mock_state_db.update_state.assert_not_called()
        assert mock_s3_client.put_object.called


class TestGetReadyWorksets:
    """Test getting ready worksets from DynamoDB."""

    def test_get_ready_worksets(self, integration, mock_state_db):
        """Test getting ready worksets from DynamoDB."""
        mock_state_db.get_ready_worksets_prioritized.return_value = [
            {
                "workset_id": "ws-001",
                "bucket": "test-bucket",
                "prefix": "worksets/ws-001/",
                "priority": "high",
            },
            {
                "workset_id": "ws-002",
                "bucket": "test-bucket",
                "prefix": "worksets/ws-002/",
                "priority": "normal",
            },
        ]

        worksets = integration.get_ready_worksets()

        assert len(worksets) == 2
        assert worksets[0]["workset_id"] == "ws-001"
        mock_state_db.get_ready_worksets_prioritized.assert_called_once()


class TestBuildWorkYaml:
    """Test work YAML generation from template."""

    def test_build_work_yaml_uses_template(self, integration):
        """Test that work YAML uses the template file structure."""
        metadata = {
            "samples": [{"sample_id": "S1", "fastq_r1": "s3://bucket/S1_R1.fq.gz"}],
            "reference_genome": "GRCh38",
        }

        # Returns string now, not dict
        work_yaml_content = integration._build_work_yaml("test-ws", metadata, "test-bucket", "worksets/test-ws/")

        # Should be a string (YAML content)
        assert isinstance(work_yaml_content, str)

        # Should contain template structure elements
        assert "day-clone:" in work_yaml_content
        assert "dy-r:" in work_yaml_content
        assert "export_uri:" in work_yaml_content

        # Should have {workdir_name} replaced with workset_id
        assert "test-ws" in work_yaml_content
        assert "{workdir_name}" not in work_yaml_content

    def test_build_work_yaml_with_export_uri(self, integration):
        """Test building work YAML with custom export URI."""
        metadata = {
            "samples": [{"sample_id": "S1", "fastq_r1": "s3://bucket/S1_R1.fq.gz"}],
            "reference_genome": "hg38",
            "export_uri": "s3://export-bucket/results/",
        }

        work_yaml_content = integration._build_work_yaml("test-ws", metadata, "test-bucket", "worksets/test-ws/")

        # Should contain the custom export_uri
        assert 's3://export-bucket/results/' in work_yaml_content

    def test_build_work_yaml_default_export_uri(self, integration):
        """Test that default export URI uses customer bucket."""
        metadata = {
            "samples": [{"sample_id": "S1", "fastq_r1": "s3://bucket/S1_R1.fq.gz"}],
            "reference_genome": "GRCh38",
        }

        work_yaml_content = integration._build_work_yaml("test-ws", metadata, "customer-bucket", "worksets/test-ws/")

        # Should contain the default export_uri with customer bucket
        assert 's3://customer-bucket/worksets/test-ws/results/' in work_yaml_content


class TestSyncDynamoDBToS3:
    """Test syncing DynamoDB worksets to S3."""

    def test_sync_dynamodb_to_s3(self, integration, mock_state_db, mock_s3_client):
        """Test syncing a single workset to S3."""
        # Return a dict with metadata as a dict, not a JSON string
        mock_state_db.get_workset.return_value = {
            "workset_id": "sync-ws",
            "state": "ready",
            "bucket": "test-bucket",
            "prefix": "worksets/sync-ws/",
            "metadata": {
                "samples": [{"sample_id": "S1", "fastq_r1": "s3://b/r1.fq.gz"}],
                "reference_genome": "GRCh38",
            },
        }

        result = integration.sync_dynamodb_to_s3("sync-ws")

        assert result is True
        # Should write work YAML and sentinel
        assert mock_s3_client.put_object.call_count >= 1


class TestAcquireReleaseLock:
    """Test lock acquisition and release."""

    def test_acquire_lock(self, integration, mock_state_db):
        """Test acquiring a lock."""
        mock_state_db.acquire_lock.return_value = True

        result = integration.acquire_lock("test-ws-001", "processor-1")

        assert result is True
        mock_state_db.acquire_lock.assert_called_once()

    def test_release_lock(self, integration, mock_state_db):
        """Test releasing a lock."""
        mock_state_db.release_lock.return_value = True

        result = integration.release_lock("test-ws-001", "processor-1")

        assert result is True
        mock_state_db.release_lock.assert_called_once()

