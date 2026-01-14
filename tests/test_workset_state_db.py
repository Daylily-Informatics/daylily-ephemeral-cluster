"""Tests for DynamoDB-based workset state management."""

import datetime as dt
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest

from daylib.workset_state_db import (
    ErrorCategory,
    WorksetPriority,
    WorksetState,
    WorksetStateDB,
)


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB resource."""
    with patch("daylib.workset_state_db.boto3.Session") as mock_session:
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_client = MagicMock()
        
        mock_session.return_value.resource.return_value = mock_resource
        mock_session.return_value.client.return_value = mock_client
        mock_resource.Table.return_value = mock_table
        
        yield {
            "session": mock_session,
            "resource": mock_resource,
            "table": mock_table,
            "client": mock_client,
        }


@pytest.fixture
def state_db(mock_dynamodb):
    """Create WorksetStateDB instance with mocked DynamoDB."""
    db = WorksetStateDB(
        table_name="test-worksets",
        region="us-west-2",
        profile=None,
        lock_timeout_seconds=300,
    )
    return db


def test_register_workset_success(state_db, mock_dynamodb):
    """Test successful workset registration."""
    mock_table = mock_dynamodb["table"]
    mock_table.put_item.return_value = {}
    
    result = state_db.register_workset(
        workset_id="test-workset-001",
        bucket="test-bucket",
        prefix="worksets/test-001/",
        priority=WorksetPriority.NORMAL,
        metadata={"samples": 10, "estimated_cost": 50.0},
    )
    
    assert result is True
    mock_table.put_item.assert_called_once()
    
    call_args = mock_table.put_item.call_args
    item = call_args.kwargs["Item"]
    
    assert item["workset_id"] == "test-workset-001"
    assert item["state"] == WorksetState.READY.value
    assert item["priority"] == WorksetPriority.NORMAL.value
    assert item["bucket"] == "test-bucket"
    assert item["prefix"] == "worksets/test-001/"
    assert "created_at" in item
    assert "state_history" in item


def test_register_workset_already_exists(state_db, mock_dynamodb):
    """Test registering a workset that already exists."""
    from botocore.exceptions import ClientError
    
    mock_table = mock_dynamodb["table"]
    mock_table.put_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}},
        "PutItem",
    )
    
    result = state_db.register_workset(
        workset_id="existing-workset",
        bucket="test-bucket",
        prefix="worksets/existing/",
    )
    
    assert result is False


def test_acquire_lock_success(state_db, mock_dynamodb):
    """Test successful lock acquisition."""
    mock_table = mock_dynamodb["table"]
    
    # Mock get_item to return a ready workset
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "test-workset",
            "state": WorksetState.READY.value,
            "priority": WorksetPriority.NORMAL.value,
        }
    }
    
    # Mock update_item to succeed
    mock_table.update_item.return_value = {}
    
    result = state_db.acquire_lock(
        workset_id="test-workset",
        owner_id="monitor-instance-1",
    )
    
    assert result is True
    mock_table.update_item.assert_called_once()


def test_acquire_lock_already_locked(state_db, mock_dynamodb):
    """Test lock acquisition when workset is already locked."""
    mock_table = mock_dynamodb["table"]
    
    # Mock get_item to return a locked workset (recent lock)
    now = dt.datetime.utcnow()
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "test-workset",
            "state": WorksetState.LOCKED.value,
            "lock_owner": "other-monitor",
            "lock_acquired_at": now.isoformat() + "Z",
        }
    }
    
    result = state_db.acquire_lock(
        workset_id="test-workset",
        owner_id="monitor-instance-1",
    )
    
    assert result is False
    mock_table.update_item.assert_not_called()


def test_acquire_lock_stale_lock(state_db, mock_dynamodb):
    """Test lock acquisition with stale lock (auto-release)."""
    mock_table = mock_dynamodb["table"]
    
    # Mock get_item to return a locked workset with stale lock
    stale_time = dt.datetime.utcnow() - dt.timedelta(seconds=400)
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "test-workset",
            "state": WorksetState.LOCKED.value,
            "lock_owner": "dead-monitor",
            "lock_acquired_at": stale_time.isoformat() + "Z",
        }
    }
    
    mock_table.update_item.return_value = {}
    
    result = state_db.acquire_lock(
        workset_id="test-workset",
        owner_id="monitor-instance-1",
    )
    
    assert result is True
    mock_table.update_item.assert_called_once()


def test_release_lock_success(state_db, mock_dynamodb):
    """Test successful lock release."""
    mock_table = mock_dynamodb["table"]
    mock_table.update_item.return_value = {}

    result = state_db.release_lock(
        workset_id="test-workset",
        owner_id="monitor-instance-1",
    )

    assert result is True
    mock_table.update_item.assert_called_once()


def test_update_state(state_db, mock_dynamodb):
    """Test state update with audit trail."""
    mock_table = mock_dynamodb["table"]
    mock_table.update_item.return_value = {}

    state_db.update_state(
        workset_id="test-workset",
        new_state=WorksetState.IN_PROGRESS,
        reason="Pipeline started",
        cluster_name="test-cluster",
        metrics={"vcpus": 32, "cost": 10.5},
    )

    mock_table.update_item.assert_called_once()
    call_args = mock_table.update_item.call_args

    assert call_args.kwargs["ExpressionAttributeValues"][":state"] == WorksetState.IN_PROGRESS.value
    assert call_args.kwargs["ExpressionAttributeValues"][":cluster"] == "test-cluster"


def test_get_ready_worksets_prioritized(state_db, mock_dynamodb):
    """Test getting ready worksets ordered by priority."""
    mock_table = mock_dynamodb["table"]

    # Mock query to return worksets for each priority
    urgent_worksets = [
        {"workset_id": "urgent-1", "priority": "urgent", "state": "ready"}
    ]
    normal_worksets = [
        {"workset_id": "normal-1", "priority": "normal", "state": "ready"},
        {"workset_id": "normal-2", "priority": "normal", "state": "ready"},
    ]

    mock_table.query.side_effect = [
        {"Items": urgent_worksets},
        {"Items": normal_worksets},
        {"Items": []},  # low priority
    ]

    worksets = state_db.get_ready_worksets_prioritized(limit=10)

    assert len(worksets) == 3
    assert worksets[0]["workset_id"] == "urgent-1"
    assert worksets[1]["workset_id"] == "normal-1"


def test_serialize_metadata(state_db):
    """Test metadata serialization for DynamoDB."""
    data = {
        "cost": 10.5,
        "samples": 5,
        "nested": {
            "value": 3.14,
            "list": [1.1, 2.2, 3.3],
        },
    }

    serialized = state_db._serialize_metadata(data)

    assert isinstance(serialized["cost"], Decimal)
    assert serialized["samples"] == 5
    assert isinstance(serialized["nested"]["value"], Decimal)
    assert all(isinstance(v, Decimal) for v in serialized["nested"]["list"])


def test_deserialize_item(state_db):
    """Test item deserialization from DynamoDB."""
    item = {
        "workset_id": "test",
        "cost": Decimal("10.5"),
        "metrics": {
            "vcpus": Decimal("32"),
            "values": [Decimal("1.1"), Decimal("2.2")],
        },
    }

    deserialized = state_db._deserialize_item(item)

    assert deserialized["cost"] == 10.5
    assert deserialized["metrics"]["vcpus"] == 32.0
    assert deserialized["metrics"]["values"] == [1.1, 2.2]


def test_record_failure_transient(state_db, mock_dynamodb):
    """Test recording a transient failure."""
    mock_table = mock_dynamodb["table"]
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "ws-001",
            "state": WorksetState.IN_PROGRESS.value,
            "retry_count": 0,
            "max_retries": 3,
        }
    }
    mock_table.update_item.return_value = {}

    should_retry = state_db.record_failure(
        "ws-001",
        "Network timeout",
        ErrorCategory.TRANSIENT,
    )

    assert should_retry is True
    mock_table.update_item.assert_called_once()


def test_record_failure_permanent(state_db, mock_dynamodb):
    """Test recording a permanent failure."""
    mock_table = mock_dynamodb["table"]
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "ws-001",
            "state": WorksetState.IN_PROGRESS.value,
            "retry_count": 0,
            "max_retries": 3,
        }
    }
    mock_table.update_item.return_value = {}

    should_retry = state_db.record_failure(
        "ws-001",
        "Invalid configuration",
        ErrorCategory.CONFIGURATION,
    )

    assert should_retry is False
    mock_table.update_item.assert_called_once()


def test_record_failure_max_retries_exceeded(state_db, mock_dynamodb):
    """Test recording failure when max retries exceeded."""
    mock_table = mock_dynamodb["table"]
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "ws-001",
            "state": WorksetState.RETRYING.value,
            "retry_count": 3,
            "max_retries": 3,
        }
    }
    mock_table.update_item.return_value = {}

    should_retry = state_db.record_failure(
        "ws-001",
        "Still failing",
        ErrorCategory.TRANSIENT,
    )

    assert should_retry is False


def test_get_retryable_worksets(state_db, mock_dynamodb):
    """Test getting retryable worksets."""
    mock_table = mock_dynamodb["table"]
    past_time = "2024-01-01T00:00:00Z"
    future_time = "2099-01-01T00:00:00Z"

    mock_table.query.return_value = {
        "Items": [
            {
                "workset_id": "ws-001",
                "state": WorksetState.RETRYING.value,
                "retry_after": past_time,
            },
            {
                "workset_id": "ws-002",
                "state": WorksetState.RETRYING.value,
                "retry_after": future_time,
            },
        ]
    }

    retryable = state_db.get_retryable_worksets()

    # Only ws-001 should be retryable (past time)
    assert len(retryable) == 1
    assert retryable[0]["workset_id"] == "ws-001"


def test_set_cluster_affinity(state_db, mock_dynamodb):
    """Test setting cluster affinity."""
    mock_table = mock_dynamodb["table"]
    mock_table.update_item.return_value = {}

    success = state_db.set_cluster_affinity(
        "ws-001",
        "cluster-us-west-2a",
        "data_locality",
    )

    assert success is True
    mock_table.update_item.assert_called_once()


def test_get_concurrent_worksets_count(state_db, mock_dynamodb):
    """Test getting concurrent worksets count."""
    mock_table = mock_dynamodb["table"]
    mock_table.query.side_effect = [
        {"Items": [{"workset_id": "ws-001"}, {"workset_id": "ws-002"}]},  # IN_PROGRESS
        {"Items": [{"workset_id": "ws-003"}]},  # LOCKED
    ]

    count = state_db.get_concurrent_worksets_count()

    assert count == 3


def test_can_start_new_workset(state_db, mock_dynamodb):
    """Test checking if new workset can start."""
    mock_table = mock_dynamodb["table"]
    mock_table.query.side_effect = [
        {"Items": [{"workset_id": "ws-001"}]},  # IN_PROGRESS
        {"Items": []},  # LOCKED
    ]

    can_start = state_db.can_start_new_workset(max_concurrent=5)

    assert can_start is True


def test_can_start_new_workset_at_limit(state_db, mock_dynamodb):
    """Test checking if new workset can start when at limit."""
    mock_table = mock_dynamodb["table"]
    mock_table.query.side_effect = [
        {"Items": [{"workset_id": f"ws-{i}"} for i in range(5)]},  # IN_PROGRESS
        {"Items": []},  # LOCKED
    ]

    can_start = state_db.can_start_new_workset(max_concurrent=5)

    assert can_start is False

