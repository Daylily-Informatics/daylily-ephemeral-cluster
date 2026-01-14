"""Tests for concurrent workset processor."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from daylib.workset_concurrent_processor import ConcurrentWorksetProcessor, ProcessorConfig
from daylib.workset_state_db import ErrorCategory, WorksetPriority, WorksetState


@pytest.fixture
def mock_state_db():
    """Mock WorksetStateDB."""
    db = MagicMock()
    db.get_concurrent_worksets_count.return_value = 2
    db.list_worksets_by_state.return_value = [
        {
            "workset_id": "ws-001",
            "state": WorksetState.READY.value,
            "priority": WorksetPriority.NORMAL.value,
            "bucket": "test-bucket",
            "prefix": "worksets/ws-001/",
            "metadata": {},
        }
    ]
    db.get_retryable_worksets.return_value = []
    db.acquire_lock.return_value = True
    db.update_state.return_value = True
    db.release_lock.return_value = True
    return db


@pytest.fixture
def mock_scheduler():
    """Mock WorksetScheduler."""
    scheduler = MagicMock()
    scheduler.schedule_workset.return_value = Mock(
        workset_id="ws-001",
        cluster_name="test-cluster",
        should_create_cluster=False,
        estimated_start_delay_minutes=0,
        reason="Scheduled to existing cluster",
    )
    return scheduler


@pytest.fixture
def processor_config():
    """Create processor configuration."""
    return ProcessorConfig(
        max_concurrent_worksets=5,
        max_workers=2,
        poll_interval_seconds=1,
        enable_retry=True,
        enable_validation=False,
        enable_notifications=False,
    )


@pytest.fixture
def processor(mock_state_db, mock_scheduler, processor_config):
    """Create ConcurrentWorksetProcessor instance."""
    return ConcurrentWorksetProcessor(
        state_db=mock_state_db,
        scheduler=mock_scheduler,
        config=processor_config,
    )


def test_processor_initialization(processor, processor_config):
    """Test processor initialization."""
    assert processor.config.max_concurrent_worksets == 5
    assert processor.config.max_workers == 2
    assert not processor.running


def test_process_cycle_at_capacity(processor, mock_state_db):
    """Test processing cycle when at max capacity."""
    mock_state_db.get_concurrent_worksets_count.return_value = 5

    processor._process_cycle()

    # Should not attempt to schedule new worksets
    mock_state_db.list_worksets_by_state.assert_not_called()


def test_process_cycle_with_available_slots(processor, mock_state_db, mock_scheduler):
    """Test processing cycle with available slots."""
    mock_state_db.get_concurrent_worksets_count.return_value = 2

    # Mock successful execution
    processor.workset_executor = Mock(return_value=True)

    processor._process_cycle()

    # Should list ready worksets
    mock_state_db.list_worksets_by_state.assert_called_once()

    # Should schedule workset
    mock_scheduler.schedule_workset.assert_called_once()


def test_process_retries(processor, mock_state_db):
    """Test retry processing."""
    mock_state_db.get_retryable_worksets.return_value = [
        {
            "workset_id": "ws-retry",
            "state": WorksetState.RETRYING.value,
            "retry_count": 1,
        }
    ]
    mock_state_db.reset_for_retry.return_value = True

    processor._process_retries()

    mock_state_db.reset_for_retry.assert_called_once_with("ws-retry")


def test_validate_workset_success(processor, mock_state_db):
    """Test successful workset validation."""
    validator = MagicMock()
    validator.validate_workset.return_value = Mock(
        is_valid=True,
        errors=[],
        warnings=[],
        estimated_cost_usd=10.0,
    )
    processor.validator = validator
    processor.config.enable_validation = True

    workset = {
        "workset_id": "ws-001",
        "bucket": "test-bucket",
        "prefix": "worksets/ws-001/",
        "metadata": {},
    }

    result = processor._validate_workset(workset)

    assert result is True
    validator.validate_workset.assert_called_once_with("test-bucket", "worksets/ws-001/")


def test_validate_workset_failure(processor, mock_state_db):
    """Test workset validation failure."""
    validator = MagicMock()
    validator.validate_workset.return_value = Mock(
        is_valid=False,
        errors=["Missing required field: samples"],
        warnings=[],
    )
    processor.validator = validator
    processor.config.enable_validation = True

    workset = {
        "workset_id": "ws-001",
        "bucket": "test-bucket",
        "prefix": "worksets/ws-001/",
        "metadata": {},
    }

    result = processor._validate_workset(workset)

    assert result is False
    mock_state_db.record_failure.assert_called_once()

