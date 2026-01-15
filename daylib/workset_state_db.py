"""DynamoDB-based state management for workset monitoring.

Replaces S3 sentinel files with a more robust, queryable state tracking system.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger("daylily.workset_state_db")


class WorksetState(str, Enum):
    """Workset lifecycle states."""
    READY = "ready"
    LOCKED = "locked"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    ERROR = "error"
    IGNORED = "ignored"
    RETRYING = "retrying"  # Retry logic state
    FAILED = "failed"  # Permanent failure after max retries
    ARCHIVED = "archived"  # Moved to archive storage
    DELETED = "deleted"  # Hard deleted from S3


class WorksetPriority(str, Enum):
    """Workset execution priority levels."""
    URGENT = "urgent"
    NORMAL = "normal"
    LOW = "low"


class ErrorCategory(str, Enum):
    """Error classification for retry logic."""
    TRANSIENT = "transient"  # Temporary errors (network, throttling)
    RESOURCE = "resource"  # Resource exhaustion (OOM, disk full)
    CONFIGURATION = "configuration"  # Config errors (invalid params)
    DATA = "data"  # Data quality issues
    PERMANENT = "permanent"  # Unrecoverable errors


STATE_PRIORITY_ORDER = {
    WorksetState.ERROR: 0,
    WorksetState.RETRYING: 1,
    WorksetState.IN_PROGRESS: 2,
    WorksetState.LOCKED: 3,
    WorksetState.READY: 4,
    WorksetState.COMPLETE: 5,
    WorksetState.FAILED: 6,
    WorksetState.IGNORED: 7,
}

EXECUTION_PRIORITY_ORDER = {
    WorksetPriority.URGENT: 0,
    WorksetPriority.NORMAL: 1,
    WorksetPriority.LOW: 2,
}

# Retry configuration defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_BASE = 2  # Exponential backoff base (seconds)
DEFAULT_RETRY_BACKOFF_MAX = 3600  # Max backoff time (1 hour)


class WorksetStateDB:
    """DynamoDB-based workset state management with distributed locking."""

    def __init__(
        self,
        table_name: str,
        region: str,
        profile: Optional[str] = None,
        lock_timeout_seconds: int = 3600,
    ):
        """Initialize the state database.
        
        Args:
            table_name: DynamoDB table name
            region: AWS region
            profile: AWS profile name (optional)
            lock_timeout_seconds: Time before locks auto-expire
        """
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile
        
        session = boto3.Session(**session_kwargs)
        self.dynamodb = session.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
        self.lock_timeout_seconds = lock_timeout_seconds
        self.cloudwatch = session.client("cloudwatch")

        # Sanity logging/guards so mis-bound DynamoDB resources surface immediately
        LOGGER.info(
            "WorksetStateDB bound to table: %s (region=%s)",
            self.table.table_name,
            region,
        )
        assert hasattr(self.table, "table_name")
	        
    def create_table_if_not_exists(self) -> None:
        """Create the DynamoDB table with appropriate schema."""
        try:
            self.table.load()
            LOGGER.info("Table %s already exists", self.table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        
        LOGGER.info("Creating table %s", self.table_name)
        table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {"AttributeName": "workset_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "workset_id", "AttributeType": "S"},
                {"AttributeName": "state", "AttributeType": "S"},
                {"AttributeName": "priority", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "state-priority-index",
                    "KeySchema": [
                        {"AttributeName": "state", "KeyType": "HASH"},
                        {"AttributeName": "priority", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "created-at-index",
                    "KeySchema": [
                        {"AttributeName": "state", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("Table %s created successfully", self.table_name)

    def register_workset(
        self,
        workset_id: str,
        bucket: str,
        prefix: str,
        priority: WorksetPriority = WorksetPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        customer_id: Optional[str] = None,
    ) -> bool:
        """Register a new workset in the database.

        Args:
            workset_id: Unique workset identifier
            bucket: S3 bucket name
            prefix: S3 prefix for workset files
            priority: Execution priority
            metadata: Additional workset metadata
            customer_id: Customer ID who owns this workset

        Returns:
            True if registered, False if already exists
        """
        now = dt.datetime.utcnow().isoformat() + "Z"
        item = {
            "workset_id": workset_id,
            "state": WorksetState.READY.value,
            "priority": priority.value,
            "bucket": bucket,
            "prefix": prefix,
            "created_at": now,
            "updated_at": now,
            "state_history": [
                {
                    "state": WorksetState.READY.value,
                    "timestamp": now,
                    "reason": "Initial registration",
                }
            ],
        }

        # Add customer_id as a top-level field if provided
        if customer_id:
            item["customer_id"] = customer_id

        if metadata:
            item["metadata"] = self._serialize_metadata(metadata)

        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(workset_id)",
            )
            self._emit_metric("WorksetRegistered", 1.0)
            LOGGER.info("Registered workset %s with priority %s", workset_id, priority.value)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning("Workset %s already exists", workset_id)
                return False
            raise

    def acquire_lock(
        self,
        workset_id: str,
        owner_id: str,
        force: bool = False,
    ) -> bool:
        """Acquire a distributed lock on a workset.

        Uses DynamoDB conditional writes for atomic lock acquisition.
        Automatically releases stale locks based on lock_timeout_seconds.

        Args:
            workset_id: Workset to lock
            owner_id: Identifier of the lock owner (e.g., monitor instance ID)
            force: If True, steal lock from current owner (for priority preemption)

        Returns:
            True if lock acquired, False otherwise
        """
        now = dt.datetime.utcnow()
        now_iso = now.isoformat() + "Z"

        try:
            # First, check current state
            response = self.table.get_item(Key={"workset_id": workset_id})
            if "Item" not in response:
                LOGGER.warning("Workset %s not found", workset_id)
                return False

            item = response["Item"]
            current_state = item.get("state")

            # Check if workset is in a lockable state
            if current_state not in [WorksetState.READY.value, WorksetState.LOCKED.value]:
                LOGGER.info(
                    "Workset %s in state %s, cannot acquire lock",
                    workset_id,
                    current_state,
                )
                return False

            # Check for stale lock
            if current_state == WorksetState.LOCKED.value:
                lock_acquired_at = item.get("lock_acquired_at")
                lock_owner = item.get("lock_owner")

                if lock_acquired_at and not force:
                    lock_time = dt.datetime.fromisoformat(lock_acquired_at.rstrip("Z"))
                    elapsed = (now - lock_time).total_seconds()

                    if elapsed < self.lock_timeout_seconds:
                        LOGGER.info(
                            "Workset %s locked by %s (%.0f seconds ago)",
                            workset_id,
                            lock_owner,
                            elapsed,
                        )
                        return False

                    LOGGER.warning(
                        "Releasing stale lock on %s (held by %s for %.0f seconds)",
                        workset_id,
                        lock_owner,
                        elapsed,
                    )

            # Attempt to acquire lock
            condition = "attribute_exists(workset_id)"
            if not force and current_state == WorksetState.LOCKED.value:
                # Only acquire if lock is stale or from same owner
                condition += " AND (attribute_not_exists(lock_owner) OR lock_owner = :owner)"

            update_expr = (
                "SET #state = :locked, "
                "lock_owner = :owner, "
                "lock_acquired_at = :now, "
                "updated_at = :now, "
                "state_history = list_append(if_not_exists(state_history, :empty_list), :history)"
            )

            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression=update_expr,
                ConditionExpression=condition,
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":locked": WorksetState.LOCKED.value,
                    ":owner": owner_id,
                    ":now": now_iso,
                    ":empty_list": [],
                    ":history": [
                        {
                            "state": WorksetState.LOCKED.value,
                            "timestamp": now_iso,
                            "reason": f"Locked by {owner_id}",
                        }
                    ],
                },
            )

            self._emit_metric("LockAcquired", 1.0)
            LOGGER.info("Acquired lock on workset %s for %s", workset_id, owner_id)
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.debug("Failed to acquire lock on %s (contention)", workset_id)
                return False
            raise

    def release_lock(self, workset_id: str, owner_id: str) -> bool:
        """Release a lock on a workset.

        Args:
            workset_id: Workset to unlock
            owner_id: Lock owner identifier (must match current owner)

        Returns:
            True if released, False if not owned by this owner
        """
        now_iso = dt.datetime.utcnow().isoformat() + "Z"

        try:
            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression=(
                    "SET #state = :ready, "
                    "updated_at = :now, "
                    "state_history = list_append(state_history, :history) "
                    "REMOVE lock_owner, lock_acquired_at"
                ),
                ConditionExpression="lock_owner = :owner",
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":ready": WorksetState.READY.value,
                    ":owner": owner_id,
                    ":now": now_iso,
                    ":history": [
                        {
                            "state": WorksetState.READY.value,
                            "timestamp": now_iso,
                            "reason": f"Lock released by {owner_id}",
                        }
                    ],
                },
            )
            LOGGER.info("Released lock on workset %s", workset_id)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning("Cannot release lock on %s (not owner)", workset_id)
                return False
            raise

    def update_state(
        self,
        workset_id: str,
        new_state: WorksetState,
        reason: str,
        error_details: Optional[str] = None,
        cluster_name: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update workset state with audit trail.

        Args:
            workset_id: Workset identifier
            new_state: New state to transition to
            reason: Reason for state change
            error_details: Error message if state is ERROR
            cluster_name: Associated cluster name
            metrics: Performance/cost metrics
        """
        now_iso = dt.datetime.utcnow().isoformat() + "Z"

        update_expr = (
            "SET #state = :state, "
            "updated_at = :now, "
            "state_history = list_append(state_history, :history)"
        )

        expr_values = {
            ":state": new_state.value,
            ":now": now_iso,
            ":history": [
                {
                    "state": new_state.value,
                    "timestamp": now_iso,
                    "reason": reason,
                }
            ],
        }

        if error_details:
            update_expr += ", error_details = :error"
            expr_values[":error"] = error_details

        if cluster_name:
            update_expr += ", cluster_name = :cluster"
            expr_values[":cluster"] = cluster_name

        if metrics:
            update_expr += ", metrics = :metrics"
            expr_values[":metrics"] = self._serialize_metadata(metrics)

        self.table.update_item(
            Key={"workset_id": workset_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues=expr_values,
        )

        # Emit CloudWatch metrics
        self._emit_metric(f"WorksetState{new_state.value.title()}", 1.0)

        LOGGER.info("Updated workset %s to state %s: %s", workset_id, new_state.value, reason)

    def get_workset(self, workset_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve workset details.

        Args:
            workset_id: Workset identifier

        Returns:
            Workset data or None if not found
        """
        try:
            response = self.table.get_item(Key={"workset_id": workset_id})
            if "Item" in response:
                return self._deserialize_item(response["Item"])
            return None
        except ClientError as e:
            LOGGER.error("Failed to get workset %s: %s", workset_id, str(e))
            return None

    def list_worksets_by_state(
        self,
        state: WorksetState,
        priority: Optional[WorksetPriority] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List worksets in a specific state, optionally filtered by priority.

        Args:
            state: State to filter by
            priority: Optional priority filter
            limit: Maximum number of results

        Returns:
            List of workset records
        """
        query_kwargs = {
            "IndexName": "state-priority-index",
            "KeyConditionExpression": "#state = :state",
            "ExpressionAttributeNames": {"#state": "state"},
            "ExpressionAttributeValues": {":state": state.value},
            "Limit": limit,
        }

        if priority:
            query_kwargs["KeyConditionExpression"] += " AND priority = :priority"
            query_kwargs["ExpressionAttributeValues"][":priority"] = priority.value

        try:
            query_kwargs.pop("TableName", None)
            assert "TableName" not in query_kwargs, (
                "TableName must not be passed to DynamoDB Table.query"
            )
            response = self.table.query(**query_kwargs)
            return [self._deserialize_item(item) for item in response.get("Items", [])]
        except ClientError as e:
            LOGGER.error("Failed to list worksets: %s", str(e))
            return []

    def get_ready_worksets_prioritized(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get ready worksets ordered by priority (urgent first).

        Args:
            limit: Maximum number of results

        Returns:
            List of ready worksets sorted by priority
        """
        worksets = []
        for priority in [WorksetPriority.URGENT, WorksetPriority.NORMAL, WorksetPriority.LOW]:
            batch = self.list_worksets_by_state(
                WorksetState.READY,
                priority=priority,
                limit=limit - len(worksets),
            )
            worksets.extend(batch)
            if len(worksets) >= limit:
                break

        return worksets

    def get_queue_depth(self) -> Dict[str, int]:
        """Get count of worksets in each state.

        Returns:
            Dictionary mapping state to count
        """
        counts = {}
        for state in WorksetState:
            worksets = self.list_worksets_by_state(state, limit=1000)
            counts[state.value] = len(worksets)

        # Emit metrics
        for state, count in counts.items():
            self._emit_metric(f"QueueDepth{state.title()}", float(count))

        return counts

    def _serialize_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Python types to DynamoDB-compatible types."""
        def convert(obj):
            if isinstance(obj, float):
                return Decimal(str(obj))
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            return obj

        return convert(data)

    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB types to Python types."""
        def convert(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            return obj

        return convert(item)

    def _emit_metric(self, metric_name: str, value: float) -> None:
        """Emit CloudWatch metric for monitoring.

        Args:
            metric_name: Metric name
            value: Metric value
        """
        try:
            self.cloudwatch.put_metric_data(
                Namespace="Daylily/WorksetMonitor",
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": "Count",
                        "Timestamp": dt.datetime.utcnow(),
                    }
                ],
            )
        except Exception as e:
            LOGGER.debug("Failed to emit metric %s: %s", metric_name, str(e))

    # ========== Retry and Recovery Methods ==========

    def record_failure(
        self,
        workset_id: str,
        error_details: str,
        error_category: ErrorCategory = ErrorCategory.TRANSIENT,
        failed_step: Optional[str] = None,
    ) -> bool:
        """Record a workset failure and determine if retry is appropriate.

        Args:
            workset_id: Workset identifier
            error_details: Error description
            error_category: Classification of error
            failed_step: Optional step that failed (for partial retry)

        Returns:
            True if workset should be retried, False if permanently failed
        """
        workset = self.get_workset(workset_id)
        if not workset:
            LOGGER.error("Cannot record failure for non-existent workset %s", workset_id)
            return False

        # Get current retry count
        retry_count = workset.get("retry_count", 0)
        max_retries = workset.get("max_retries", DEFAULT_MAX_RETRIES)

        # Determine if we should retry
        should_retry = (
            retry_count < max_retries
            and error_category in [ErrorCategory.TRANSIENT, ErrorCategory.RESOURCE]
        )

        if should_retry:
            # Calculate exponential backoff
            backoff_seconds = min(
                DEFAULT_RETRY_BACKOFF_BASE ** retry_count,
                DEFAULT_RETRY_BACKOFF_MAX,
            )
            retry_after = (
                dt.datetime.utcnow() + dt.timedelta(seconds=backoff_seconds)
            ).isoformat() + "Z"

            new_state = WorksetState.RETRYING
            reason = f"Retry {retry_count + 1}/{max_retries} after {error_category.value} error"
        else:
            new_state = WorksetState.FAILED
            reason = f"Permanent failure after {retry_count} retries: {error_category.value}"
            retry_after = None

        # Update workset state
        now = dt.datetime.utcnow().isoformat() + "Z"
        try:
            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression=(
                    "SET #state = :state, updated_at = :now, "
                    "retry_count = :retry_count, error_details = :error, "
                    "error_category = :category, failed_step = :step, "
                    "retry_after = :retry_after, "
                    "state_history = list_append(state_history, :history)"
                ),
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":state": new_state.value,
                    ":now": now,
                    ":retry_count": retry_count + 1,
                    ":error": error_details,
                    ":category": error_category.value,
                    ":step": failed_step or "unknown",
                    ":retry_after": retry_after,
                    ":history": [
                        {
                            "state": new_state.value,
                            "timestamp": now,
                            "reason": reason,
                            "error_category": error_category.value,
                        }
                    ],
                },
            )

            self._emit_metric(
                "WorksetRetry" if should_retry else "WorksetPermanentFailure",
                1.0,
            )
            LOGGER.info("%s: %s", workset_id, reason)
            return should_retry

        except ClientError as e:
            LOGGER.error("Failed to record failure for %s: %s", workset_id, str(e))
            return False

    def get_retryable_worksets(self) -> List[Dict[str, Any]]:
        """Get worksets that are ready to be retried.

        Returns:
            List of worksets in RETRYING state where retry_after time has passed
        """
        worksets = self.list_worksets_by_state(WorksetState.RETRYING, limit=1000)
        now = dt.datetime.utcnow().isoformat() + "Z"

        retryable = []
        for workset in worksets:
            retry_after = workset.get("retry_after")
            if not retry_after or retry_after <= now:
                retryable.append(workset)

        LOGGER.info("Found %d worksets ready for retry", len(retryable))
        return retryable

    def reset_for_retry(self, workset_id: str) -> bool:
        """Reset a workset from RETRYING to READY state.

        Args:
            workset_id: Workset identifier

        Returns:
            True if successful
        """
        return self.update_state(
            workset_id,
            WorksetState.READY,
            reason="Reset for retry attempt",
        )

    # ========== Concurrent Processing Methods ==========

    def set_cluster_affinity(
        self,
        workset_id: str,
        cluster_name: str,
        affinity_reason: str = "manual",
    ) -> bool:
        """Set cluster affinity for a workset.

        Args:
            workset_id: Workset identifier
            cluster_name: Preferred cluster name
            affinity_reason: Reason for affinity (e.g., 'data_locality', 'cost')

        Returns:
            True if successful
        """
        try:
            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression=(
                    "SET preferred_cluster = :cluster, "
                    "affinity_reason = :reason, "
                    "updated_at = :now"
                ),
                ExpressionAttributeValues={
                    ":cluster": cluster_name,
                    ":reason": affinity_reason,
                    ":now": dt.datetime.utcnow().isoformat() + "Z",
                },
            )
            LOGGER.info(
                "Set cluster affinity for %s to %s (%s)",
                workset_id,
                cluster_name,
                affinity_reason,
            )
            return True
        except ClientError as e:
            LOGGER.error("Failed to set cluster affinity: %s", str(e))
            return False

    def get_worksets_by_cluster(self, cluster_name: str) -> List[Dict[str, Any]]:
        """Get all worksets assigned to a specific cluster.

        Args:
            cluster_name: Cluster name

        Returns:
            List of worksets
        """
        try:
            scan_kwargs = {
                "FilterExpression": "cluster_name = :cluster",
                "ExpressionAttributeValues": {":cluster": cluster_name},
            }
            scan_kwargs.pop("TableName", None)
            assert "TableName" not in scan_kwargs, (
                "TableName must not be passed to DynamoDB Table.scan"
            )
            response = self.table.scan(**scan_kwargs)
            return [self._deserialize_item(item) for item in response.get("Items", [])]
        except ClientError as e:
            LOGGER.error("Failed to get worksets for cluster %s: %s", cluster_name, str(e))
            return []

    def get_concurrent_worksets_count(self) -> int:
        """Get count of worksets currently in progress.

        Returns:
            Number of worksets in IN_PROGRESS or LOCKED state
        """
        in_progress = len(self.list_worksets_by_state(WorksetState.IN_PROGRESS, limit=1000))
        locked = len(self.list_worksets_by_state(WorksetState.LOCKED, limit=1000))
        return in_progress + locked

    def can_start_new_workset(self, max_concurrent: int) -> bool:
        """Check if a new workset can be started based on concurrency limit.

        Args:
            max_concurrent: Maximum concurrent worksets allowed

        Returns:
            True if under the limit
        """
        current = self.get_concurrent_worksets_count()
        can_start = current < max_concurrent
        LOGGER.debug(
            "Concurrent worksets: %d/%d (can_start=%s)",
            current,
            max_concurrent,
            can_start,
        )
        return can_start

    def get_next_workset_with_affinity(
        self,
        cluster_name: str,
        priority: Optional[WorksetPriority] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get next workset with affinity to a specific cluster.

        Args:
            cluster_name: Cluster name
            priority: Optional priority filter

        Returns:
            Workset dict or None
        """
        # First try worksets with explicit affinity
        ready_worksets = self.list_worksets_by_state(WorksetState.READY, limit=100)

        for workset in ready_worksets:
            if workset.get("preferred_cluster") == cluster_name:
                if priority is None or workset.get("priority") == priority.value:
                    return workset

        # Fall back to any ready workset if no affinity match
        if ready_worksets:
            return ready_worksets[0]

        return None

    def archive_workset(
        self,
        workset_id: str,
        archived_by: str = "system",
        archive_reason: Optional[str] = None,
    ) -> bool:
        """Archive a workset.

        Updates state to ARCHIVED and records archival metadata.

        Args:
            workset_id: Workset identifier
            archived_by: User or system that archived the workset
            archive_reason: Optional reason for archiving

        Returns:
            True if successful
        """
        now = dt.datetime.utcnow().isoformat() + "Z"
        update_expr = "SET #state = :state, archived_at = :archived_at, archived_by = :archived_by"
        expr_values = {
            ":state": WorksetState.ARCHIVED.value,
            ":archived_at": now,
            ":archived_by": archived_by,
        }
        expr_names = {"#state": "state"}

        if archive_reason:
            update_expr += ", archive_reason = :reason"
            expr_values[":reason"] = archive_reason

        try:
            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
            LOGGER.info("Archived workset %s by %s", workset_id, archived_by)
            return True
        except ClientError as e:
            LOGGER.error("Failed to archive workset %s: %s", workset_id, str(e))
            return False

    def delete_workset(
        self,
        workset_id: str,
        deleted_by: str = "system",
        delete_reason: Optional[str] = None,
        hard_delete: bool = False,
    ) -> bool:
        """Delete a workset.

        Either marks as DELETED state or completely removes from DynamoDB.

        Args:
            workset_id: Workset identifier
            deleted_by: User or system that deleted the workset
            delete_reason: Optional reason for deletion
            hard_delete: If True, remove from DynamoDB entirely

        Returns:
            True if successful
        """
        try:
            if hard_delete:
                # Completely remove from DynamoDB
                self.table.delete_item(Key={"workset_id": workset_id})
                LOGGER.info("Hard deleted workset %s from DynamoDB by %s", workset_id, deleted_by)
            else:
                # Soft delete - mark as deleted
                now = dt.datetime.utcnow().isoformat() + "Z"
                update_expr = "SET #state = :state, deleted_at = :deleted_at, deleted_by = :deleted_by"
                expr_values = {
                    ":state": WorksetState.DELETED.value,
                    ":deleted_at": now,
                    ":deleted_by": deleted_by,
                }
                expr_names = {"#state": "state"}

                if delete_reason:
                    update_expr += ", delete_reason = :reason"
                    expr_values[":reason"] = delete_reason

                self.table.update_item(
                    Key={"workset_id": workset_id},
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames=expr_names,
                    ExpressionAttributeValues=expr_values,
                )
                LOGGER.info("Soft deleted workset %s by %s", workset_id, deleted_by)
            return True
        except ClientError as e:
            LOGGER.error("Failed to delete workset %s: %s", workset_id, str(e))
            return False

    def restore_workset(
        self,
        workset_id: str,
        restored_by: str = "system",
    ) -> bool:
        """Restore an archived workset back to ready state.

        Args:
            workset_id: Workset identifier
            restored_by: User or system restoring the workset

        Returns:
            True if successful
        """
        now = dt.datetime.utcnow().isoformat() + "Z"
        try:
            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression="SET #state = :state, restored_at = :restored_at, restored_by = :restored_by REMOVE archived_at, archived_by, archive_reason",
                ExpressionAttributeNames={"#state": "state"},
                ConditionExpression="attribute_exists(workset_id) AND #state = :archived",
                ExpressionAttributeValues={
                    ":state": WorksetState.READY.value,
                    ":restored_at": now,
                    ":restored_by": restored_by,
                    ":archived": WorksetState.ARCHIVED.value,
                },
            )
            LOGGER.info("Restored workset %s by %s", workset_id, restored_by)
            return True
        except ClientError as e:
            LOGGER.error("Failed to restore workset %s: %s", workset_id, str(e))
            return False

    def list_archived_worksets(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all archived worksets.

        Args:
            limit: Maximum number of results

        Returns:
            List of archived workset dicts
        """
        return self.list_worksets_by_state(WorksetState.ARCHIVED, limit=limit)

