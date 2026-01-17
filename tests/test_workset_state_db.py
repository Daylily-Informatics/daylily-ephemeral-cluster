"""Tests for DynamoDB-based workset state management."""

import datetime as dt
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

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
    now = dt.datetime.now(dt.timezone.utc)
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
    """Test lock acquisition with stale lock (auto-release).

    Note: Locking is now separate from state. A workset with a stale lock
    is identified by lock_owner/lock_acquired_at fields, not by state.
    The state remains READY or RETRYING (lockable states).
    """
    mock_table = mock_dynamodb["table"]

    # Mock get_item to return a READY workset with stale lock fields
    stale_time = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=400)
    stale_expires = (stale_time + dt.timedelta(seconds=300)).isoformat().replace("+00:00", "Z")
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "test-workset",
            "state": WorksetState.READY.value,  # State is still lockable
            "lock_owner": "dead-monitor",
            "lock_acquired_at": stale_time.isoformat() + "Z",
            "lock_expires_at": stale_expires,  # Already expired
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
    """Test getting concurrent worksets count.

    Note: Concurrency count now includes:
    - IN_PROGRESS worksets (via state GSI query)
    - Worksets with lock_owner set (via scan) - these are locked but may not have
      transitioned state yet
    """
    mock_table = mock_dynamodb["table"]
    # list_worksets_by_state uses query on state GSI
    mock_table.query.return_value = {
        "Items": [{"workset_id": "ws-001"}, {"workset_id": "ws-002"}]  # IN_PROGRESS
    }
    # list_locked_worksets uses scan with filter on lock_owner
    mock_table.scan.return_value = {
        "Items": [{"workset_id": "ws-003", "lock_owner": "monitor-1"}]  # locked
    }

    count = state_db.get_concurrent_worksets_count()

    # 2 IN_PROGRESS + 1 locked
    assert count == 3


def test_can_start_new_workset(state_db, mock_dynamodb):
    """Test checking if new workset can start."""
    mock_table = mock_dynamodb["table"]
    mock_table.query.return_value = {
        "Items": [{"workset_id": "ws-001"}]  # IN_PROGRESS
    }
    mock_table.scan.return_value = {
        "Items": []  # No locked worksets
    }

    can_start = state_db.can_start_new_workset(max_concurrent=5)

    assert can_start is True


def test_can_start_new_workset_at_limit(state_db, mock_dynamodb):
    """Test checking if new workset can start when at limit."""
    mock_table = mock_dynamodb["table"]
    mock_table.query.return_value = {
        "Items": [{"workset_id": f"ws-{i}"} for i in range(5)]  # IN_PROGRESS
    }
    mock_table.scan.return_value = {
        "Items": []  # No locked worksets
    }

    can_start = state_db.can_start_new_workset(max_concurrent=5)

    assert can_start is False


# ==================== Archive/Delete/Restore Tests ====================


def test_archive_workset_success(state_db, mock_dynamodb):
    """Test successful workset archiving."""
    mock_table = mock_dynamodb["table"]
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "test-ws-001",
            "state": WorksetState.COMPLETE.value,
            "state_history": [],
        }
    }
    mock_table.update_item.return_value = {}

    result = state_db.archive_workset(
        workset_id="test-ws-001",
        archived_by="test-user",
        archive_reason="No longer needed",
    )

    assert result is True
    mock_table.update_item.assert_called_once()

    call_args = mock_table.update_item.call_args
    assert call_args.kwargs["Key"] == {"workset_id": "test-ws-001"}
    # Check that state is set to ARCHIVED
    expr_values = call_args.kwargs["ExpressionAttributeValues"]
    assert expr_values[":state"] == WorksetState.ARCHIVED.value
    assert expr_values[":archived_by"] == "test-user"
    assert expr_values[":reason"] == "No longer needed"


def test_archive_workset_dynamodb_error(state_db, mock_dynamodb):
    """Test archiving fails on DynamoDB error."""
    mock_table = mock_dynamodb["table"]
    mock_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}},
        "UpdateItem"
    )

    result = state_db.archive_workset(workset_id="nonexistent-ws")

    assert result is False


def test_delete_workset_soft_delete_success(state_db, mock_dynamodb):
    """Test successful soft delete of a workset."""
    mock_table = mock_dynamodb["table"]
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "test-ws-001",
            "state": WorksetState.COMPLETE.value,
            "state_history": [],
        }
    }
    mock_table.update_item.return_value = {}

    result = state_db.delete_workset(
        workset_id="test-ws-001",
        deleted_by="test-user",
        delete_reason="Cleaning up old data",
        hard_delete=False,
    )

    assert result is True
    mock_table.update_item.assert_called_once()
    mock_table.delete_item.assert_not_called()

    call_args = mock_table.update_item.call_args
    expr_values = call_args.kwargs["ExpressionAttributeValues"]
    assert expr_values[":state"] == WorksetState.DELETED.value


def test_delete_workset_hard_delete_success(state_db, mock_dynamodb):
    """Test successful hard delete of a workset."""
    mock_table = mock_dynamodb["table"]
    mock_table.get_item.return_value = {
        "Item": {
            "workset_id": "test-ws-001",
            "state": WorksetState.COMPLETE.value,
        }
    }
    mock_table.delete_item.return_value = {}

    result = state_db.delete_workset(
        workset_id="test-ws-001",
        deleted_by="test-user",
        hard_delete=True,
    )

    assert result is True
    mock_table.delete_item.assert_called_once()
    call_args = mock_table.delete_item.call_args
    assert call_args.kwargs["Key"] == {"workset_id": "test-ws-001"}


def test_delete_workset_dynamodb_error(state_db, mock_dynamodb):
    """Test deleting fails on DynamoDB error."""
    mock_table = mock_dynamodb["table"]
    mock_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError"}},
        "UpdateItem"
    )

    result = state_db.delete_workset(workset_id="test-ws-001", hard_delete=False)

    assert result is False


def test_delete_workset_hard_delete_error(state_db, mock_dynamodb):
    """Test hard delete fails on DynamoDB error."""
    mock_table = mock_dynamodb["table"]
    mock_table.delete_item.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError"}},
        "DeleteItem"
    )

    result = state_db.delete_workset(workset_id="test-ws-001", hard_delete=True)

    assert result is False


def test_restore_workset_success(state_db, mock_dynamodb):
    """Test successful restoration of an archived workset."""
    mock_table = mock_dynamodb["table"]
    mock_table.update_item.return_value = {}

    result = state_db.restore_workset(
        workset_id="test-ws-001",
        restored_by="test-user",
    )

    assert result is True
    mock_table.update_item.assert_called_once()

    call_args = mock_table.update_item.call_args
    expr_values = call_args.kwargs["ExpressionAttributeValues"]
    assert expr_values[":state"] == WorksetState.READY.value
    # restore_workset has a ConditionExpression that requires state == archived
    assert expr_values[":archived"] == WorksetState.ARCHIVED.value


def test_restore_workset_not_archived_fails(state_db, mock_dynamodb):
    """Test restoring a non-archived workset fails due to condition check."""
    mock_table = mock_dynamodb["table"]
    # DynamoDB returns ConditionalCheckFailedException when condition not met
    mock_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}},
        "UpdateItem"
    )

    result = state_db.restore_workset(workset_id="test-ws-001")

    assert result is False


def test_list_archived_worksets(state_db, mock_dynamodb):
    """Test listing archived worksets."""
    mock_table = mock_dynamodb["table"]
    mock_table.query.return_value = {
        "Items": [
            {"workset_id": "ws-001", "state": WorksetState.ARCHIVED.value},
            {"workset_id": "ws-002", "state": WorksetState.ARCHIVED.value},
        ]
    }

    result = state_db.list_archived_worksets(limit=50)

    assert len(result) == 2
    assert result[0]["workset_id"] == "ws-001"
    mock_table.query.assert_called_once()


def test_archive_workset_with_reason(state_db, mock_dynamodb):
    """Test archiving a workset with a reason."""
    mock_table = mock_dynamodb["table"]
    mock_table.update_item.return_value = {}

    result = state_db.archive_workset(
        workset_id="test-ws-001",
        archived_by="admin",
        archive_reason="Data retention policy"
    )

    assert result is True
    call_args = mock_table.update_item.call_args
    expr_values = call_args.kwargs["ExpressionAttributeValues"]
    assert expr_values[":reason"] == "Data retention policy"


def test_delete_workset_with_reason(state_db, mock_dynamodb):
    """Test soft deleting a workset with a reason."""
    mock_table = mock_dynamodb["table"]
    mock_table.update_item.return_value = {}

    result = state_db.delete_workset(
        workset_id="test-ws-001",
        deleted_by="admin",
        delete_reason="Customer request",
        hard_delete=False
    )

    assert result is True
    call_args = mock_table.update_item.call_args
    expr_values = call_args.kwargs["ExpressionAttributeValues"]
    assert expr_values[":reason"] == "Customer request"

