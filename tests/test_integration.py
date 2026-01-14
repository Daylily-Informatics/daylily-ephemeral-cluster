"""Integration tests for workset processing pipeline.

Tests end-to-end workflows including state transitions, concurrent processing,
and error handling.
"""

from unittest.mock import MagicMock, patch
import datetime as dt

import pytest

from daylib.workset_state_db import (
    WorksetStateDB,
    WorksetState,
    WorksetPriority,
    ErrorCategory,
)
from daylib.workset_concurrent_processor import ConcurrentWorksetProcessor
from daylib.workset_notifications import NotificationManager, SNSNotificationChannel
from daylib.workset_validation import WorksetValidator
from daylib.workset_diagnostics import ErrorAnalyzer, classify_error


@pytest.fixture
def mock_aws():
    """Mock AWS services for integration tests."""
    with patch("daylib.workset_state_db.boto3.Session") as mock_session:
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_cloudwatch = MagicMock()
        
        mock_dynamodb.Table.return_value = mock_table
        mock_session.return_value.resource.return_value = mock_dynamodb
        mock_session.return_value.client.return_value = mock_cloudwatch
        
        # Set up table responses
        mock_table.load.return_value = None
        mock_table.put_item.return_value = {}
        mock_table.update_item.return_value = {}
        mock_table.get_item.return_value = {
            "Item": {
                "workset_id": "test-ws-001",
                "state": "ready",
                "priority": "normal",
                "bucket": "test-bucket",
                "prefix": "worksets/test/",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z",
            }
        }
        
        yield {
            "session": mock_session,
            "table": mock_table,
            "dynamodb": mock_dynamodb,
            "cloudwatch": mock_cloudwatch,
        }


@pytest.fixture
def state_db(mock_aws):
    """Create WorksetStateDB instance."""
    return WorksetStateDB(
        table_name="test-worksets",
        region="us-west-2",
    )


class TestWorksetLifecycle:
    """Test complete workset lifecycle."""

    def test_register_to_complete_workflow(self, state_db, mock_aws):
        """Test workset from registration to completion."""
        mock_table = mock_aws["table"]
        
        # Step 1: Register workset
        result = state_db.register_workset(
            workset_id="integration-ws-001",
            bucket="test-bucket",
            prefix="worksets/test/",
            priority=WorksetPriority.NORMAL,
            metadata={"samples": 5},
        )
        assert result is True
        
        # Step 2: Acquire lock
        result = state_db.acquire_lock("integration-ws-001", "processor-1")
        assert result is True
        
        # Step 3: Update to in_progress
        state_db.update_state(
            "integration-ws-001",
            WorksetState.IN_PROGRESS,
            reason="Started processing",
            cluster_name="test-cluster",
        )
        
        # Step 4: Complete
        state_db.update_state(
            "integration-ws-001",
            WorksetState.COMPLETE,
            reason="Processing finished",
            metrics={"duration_seconds": 300, "cost_usd": 5.0},
        )
        
        # Verify state updates were called
        assert mock_table.update_item.call_count >= 3

    def test_register_to_error_to_retry_workflow(self, state_db, mock_aws):
        """Test workset error handling and retry."""
        mock_table = mock_aws["table"]
        
        # Setup mock for retry logic
        mock_table.get_item.return_value = {
            "Item": {
                "workset_id": "error-ws-001",
                "state": "in_progress",
                "retry_count": 0,
                "max_retries": 3,
            }
        }
        
        # Record a transient failure
        should_retry = state_db.record_failure(
            workset_id="error-ws-001",
            error_details="Connection timeout",
            error_category=ErrorCategory.TRANSIENT,
        )
        
        assert should_retry is True

    def test_permanent_failure_workflow(self, state_db, mock_aws):
        """Test permanent failure after max retries."""
        mock_table = mock_aws["table"]
        
        # Setup mock with max retries reached
        mock_table.get_item.return_value = {
            "Item": {
                "workset_id": "perm-error-ws-001",
                "state": "retrying",
                "retry_count": 3,
                "max_retries": 3,
            }
        }
        
        # Record another failure
        should_retry = state_db.record_failure(
            workset_id="perm-error-ws-001",
            error_details="Persistent error",
            error_category=ErrorCategory.TRANSIENT,
        )
        
        assert should_retry is False


class TestValidationToProcessing:
    """Test validation and processing integration."""

    def test_validation_before_registration(self, state_db, mock_aws):
        """Test validating workset before registration."""
        with patch("daylib.workset_validation.boto3.Session"):
            validator = WorksetValidator(region="us-west-2")

            # Valid workset config - use the schema directly
            config = {
                "workset_id": "validated-ws-001",
                "samples": [
                    {"sample_id": "S1", "fastq_r1": "s3://bucket/S1_R1.fq.gz"}
                ],
                "reference_genome": "hg38",
            }

            # Validate using jsonschema directly
            import jsonschema
            try:
                jsonschema.validate(config, WorksetValidator.WORK_YAML_SCHEMA)
                is_valid = True
            except jsonschema.ValidationError:
                is_valid = False

            assert is_valid

            # Register after validation
            result = state_db.register_workset(
                workset_id=config["workset_id"],
                bucket="test-bucket",
                prefix="worksets/validated-ws-001/",
                metadata={"samples": config["samples"]},
            )
            assert result is True


class TestDiagnosticsIntegration:
    """Test diagnostics integration with state management."""

    def test_error_classification_and_recording(self, state_db, mock_aws):
        """Test classifying error and recording in state DB."""
        mock_table = mock_aws["table"]

        # Simulate an error
        error_text = "Out of memory: Cannot allocate 16GB"

        # Classify the error
        classification = classify_error(error_text)

        assert classification["error_code"] == "WS-RES-001"
        assert classification["category"] == "resource"
        assert classification["retryable"] is True

        # Setup mock for retry
        mock_table.get_item.return_value = {
            "Item": {
                "workset_id": "diag-ws-001",
                "state": "in_progress",
                "retry_count": 0,
                "max_retries": 3,
            }
        }

        # Record failure with classification
        error_category = (
            ErrorCategory.TRANSIENT if classification["retryable"]
            else ErrorCategory.PERMANENT
        )

        should_retry = state_db.record_failure(
            workset_id="diag-ws-001",
            error_details=error_text,
            error_category=error_category,
        )

        # Should retry since it's a transient resource error
        assert should_retry is True

    def test_non_retryable_error_classification(self, state_db, mock_aws):
        """Test non-retryable error handling."""
        mock_table = mock_aws["table"]

        # Simulate a data error
        error_text = "Invalid FASTQ format: truncated quality string"

        # Classify the error
        classification = classify_error(error_text)

        assert classification["error_code"] == "WS-DAT-001"
        assert classification["retryable"] is False

        # Setup mock
        mock_table.get_item.return_value = {
            "Item": {
                "workset_id": "data-error-ws-001",
                "state": "in_progress",
                "retry_count": 0,
                "max_retries": 3,
            }
        }

        # Record as permanent failure
        should_retry = state_db.record_failure(
            workset_id="data-error-ws-001",
            error_details=error_text,
            error_category=ErrorCategory.PERMANENT,
        )

        # Should not retry data errors
        assert should_retry is False


class TestConcurrentProcessingIntegration:
    """Test concurrent processing integration."""

    def test_state_db_concurrency_limits(self, state_db, mock_aws):
        """Test state DB respects concurrency limits."""
        mock_table = mock_aws["table"]

        # Setup mock to return worksets at limit for query
        mock_table.query.return_value = {
            "Items": [
                {"workset_id": f"ws-{i}", "state": "in_progress"}
                for i in range(5)  # 5 concurrent worksets
            ],
            "Count": 5,
        }

        # Check if can start new workset
        can_start = state_db.can_start_new_workset(max_concurrent=5)
        # The mock returns 5 in_progress + 5 locked = 10, so should be False
        # But since query is called twice (for in_progress and locked),
        # we get 10 total which is >= 5
        assert can_start is False

    def test_state_db_cluster_affinity(self, state_db, mock_aws):
        """Test state DB cluster affinity."""
        mock_table = mock_aws["table"]

        # Set cluster affinity
        state_db.set_cluster_affinity("test-ws-001", "test-cluster")

        # Verify update was called
        mock_table.update_item.assert_called()

