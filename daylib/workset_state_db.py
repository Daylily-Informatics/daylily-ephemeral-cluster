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
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

LOGGER = logging.getLogger("daylily.workset_state_db")


class WorksetState(str, Enum):
    """Workset lifecycle states."""
    READY = "ready"
    LOCKED = "locked"  # Deprecated: lock ownership is tracked via lock_owner attributes.
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
    WorksetState.READY: 3,
    WorksetState.COMPLETE: 4,
    WorksetState.FAILED: 5,
    WorksetState.IGNORED: 6,
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
        now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        item: Dict[str, Any] = {
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

        IMPORTANT: This method only sets lock_owner, lock_acquired_at, and lock_expires_at
        attributes. It does NOT change the workset state. Locking is separate from state.

        Args:
            workset_id: Workset to lock
            owner_id: Identifier of the lock owner (e.g., monitor instance ID)
            force: If True, steal lock from current owner (for priority preemption)

        Returns:
            True if lock acquired, False otherwise
        """
        now = dt.datetime.now(dt.timezone.utc)
        now_iso = now.isoformat().replace("+00:00", "Z")
        expires_at = (now + dt.timedelta(seconds=self.lock_timeout_seconds)).isoformat().replace("+00:00", "Z")

        try:
            # First, check current state and lock metadata
            response = self.table.get_item(Key={"workset_id": workset_id})
            if "Item" not in response:
                LOGGER.warning("Workset %s not found", workset_id)
                return False

            item = response["Item"]
            current_state = item.get("state")

            # Allow locking READY worksets or RETRYING worksets (for retry logic)
            # Also allow force=True to lock any workset
            lockable_states = {WorksetState.READY.value, WorksetState.RETRYING.value}
            if not force and current_state not in lockable_states:
                LOGGER.info(
                    "Workset %s in state %s, cannot acquire lock (lockable states: %s)",
                    workset_id,
                    current_state,
                    ", ".join(lockable_states),
                )
                return False

            lock_owner = item.get("lock_owner")
            lock_acquired_at = item.get("lock_acquired_at")
            lock_expires_at = item.get("lock_expires_at")
            lock_is_stale = False

            if lock_owner:
                # Check if lock has expired using lock_expires_at (preferred) or lock_acquired_at
                if lock_expires_at:
                    try:
                        expires_time = dt.datetime.fromisoformat(lock_expires_at.rstrip("Z")).replace(tzinfo=dt.timezone.utc)
                        if now >= expires_time:
                            lock_is_stale = True
                            LOGGER.warning(
                                "Lock on %s expired at %s (held by %s)",
                                workset_id,
                                lock_expires_at,
                                lock_owner,
                            )
                        elif not force:
                            LOGGER.info(
                                "Workset %s locked by %s (expires at %s)",
                                workset_id,
                                lock_owner,
                                lock_expires_at,
                            )
                            return False
                    except ValueError:
                        lock_is_stale = True  # Invalid timestamp, treat as stale
                elif lock_acquired_at:
                    # Fallback to lock_acquired_at for backward compatibility
                    try:
                        lock_time = dt.datetime.fromisoformat(lock_acquired_at.rstrip("Z")).replace(tzinfo=dt.timezone.utc)
                        elapsed = (now - lock_time).total_seconds()
                        if elapsed >= self.lock_timeout_seconds:
                            lock_is_stale = True
                            LOGGER.warning(
                                "Releasing stale lock on %s (held by %s for %.0f seconds)",
                                workset_id,
                                lock_owner,
                                elapsed,
                            )
                        elif not force:
                            LOGGER.info(
                                "Workset %s locked by %s (%.0f seconds ago)",
                                workset_id,
                                lock_owner,
                                elapsed,
                            )
                            return False
                    except ValueError:
                        lock_is_stale = True  # Invalid timestamp, treat as stale
                elif not force:
                    LOGGER.info(
                        "Workset %s locked by %s (timestamp missing)",
                        workset_id,
                        lock_owner,
                    )
                    return False
                else:
                    lock_is_stale = True  # No timestamp + force, treat as stale

            # Attempt to acquire lock - only sets lock attributes, NOT state
            condition = "attribute_exists(workset_id) AND (attribute_not_exists(lock_owner) OR lock_owner = :owner"
            if lock_is_stale:
                condition += " OR lock_acquired_at = :stale_at"
            condition += ")"

            update_expr = (
                "SET lock_owner = :owner, "
                "lock_acquired_at = :now, "
                "lock_expires_at = :expires, "
                "updated_at = :now"
            )

            expression_values = {
                ":owner": owner_id,
                ":now": now_iso,
                ":expires": expires_at,
            }
            if lock_is_stale and lock_acquired_at:
                expression_values[":stale_at"] = lock_acquired_at

            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression=update_expr,
                ConditionExpression=condition,
                ExpressionAttributeValues=expression_values,
            )

            self._emit_metric("LockAcquired", 1.0)
            LOGGER.info(
                "Acquired lock on workset %s for %s (expires at %s)",
                workset_id,
                owner_id,
                expires_at,
            )
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.debug("Failed to acquire lock on %s (contention)", workset_id)
                return False
            raise

    def release_lock(self, workset_id: str, owner_id: str) -> bool:
        """Release a lock on a workset.

        IMPORTANT: This method only clears lock_owner, lock_acquired_at, and lock_expires_at
        attributes if the owner matches. It does NOT change the workset state.
        Locking is separate from state - call update_state() separately if needed.

        Args:
            workset_id: Workset to unlock
            owner_id: Lock owner identifier (must match current owner)

        Returns:
            True if released, False if not owned by this owner
        """
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

        try:
            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression=(
                    "SET updated_at = :now "
                    "REMOVE lock_owner, lock_acquired_at, lock_expires_at"
                ),
                ConditionExpression="lock_owner = :owner",
                ExpressionAttributeValues={
                    ":owner": owner_id,
                    ":now": now_iso,
                },
            )
            self._emit_metric("LockReleased", 1.0)
            LOGGER.info("Released lock on workset %s by owner %s", workset_id, owner_id)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning(
                    "Cannot release lock on %s (not owner: requested by %s)",
                    workset_id,
                    owner_id,
                )
                return False
            raise

    def refresh_lock(self, workset_id: str, owner_id: str) -> bool:
        """Extend the lock expiration time for a workset.

        This is useful for long-running worksets to prevent lock timeout.
        Only the current lock owner can refresh the lock.

        Args:
            workset_id: Workset identifier
            owner_id: Lock owner identifier (must match current owner)

        Returns:
            True if lock refreshed, False if not owned by this owner
        """
        now = dt.datetime.now(dt.timezone.utc)
        now_iso = now.isoformat().replace("+00:00", "Z")
        expires_at = (now + dt.timedelta(seconds=self.lock_timeout_seconds)).isoformat().replace("+00:00", "Z")

        try:
            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression=(
                    "SET lock_acquired_at = :now, "
                    "lock_expires_at = :expires, "
                    "updated_at = :now"
                ),
                ConditionExpression="lock_owner = :owner",
                ExpressionAttributeValues={
                    ":owner": owner_id,
                    ":now": now_iso,
                    ":expires": expires_at,
                },
            )
            LOGGER.debug(
                "Refreshed lock on workset %s for %s (expires at %s)",
                workset_id,
                owner_id,
                expires_at,
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                LOGGER.warning(
                    "Cannot refresh lock on %s (not owner: requested by %s)",
                    workset_id,
                    owner_id,
                )
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
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

        update_expr = (
            "SET #state = :state, "
            "updated_at = :now, "
            "state_history = list_append(state_history, :history)"
        )

        expr_values: Dict[str, Any] = {
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

    def update_progress(
        self,
        workset_id: str,
        current_step: Optional[str] = None,
        cluster_name: Optional[str] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update workset progress without changing state.

        This is used for incremental progress updates during processing,
        allowing the UI to show real-time status.

        Args:
            workset_id: Workset identifier
            current_step: Current processing step (e.g., 'staging', 'cloning', 'running')
            cluster_name: Associated cluster name
            started_at: ISO timestamp when processing started
            finished_at: ISO timestamp when processing finished
            metrics: Performance/cost metrics to merge
        """
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

        update_parts = ["updated_at = :now"]
        expr_values: Dict[str, Any] = {":now": now_iso}
        expr_names: Dict[str, str] = {}

        if current_step is not None:
            update_parts.append("current_step = :step")
            expr_values[":step"] = current_step

        if cluster_name is not None:
            update_parts.append("cluster_name = :cluster")
            expr_values[":cluster"] = cluster_name

        if started_at is not None:
            update_parts.append("started_at = :started")
            expr_values[":started"] = started_at

        if finished_at is not None:
            update_parts.append("finished_at = :finished")
            expr_values[":finished"] = finished_at

        if metrics is not None:
            update_parts.append("metrics = :metrics")
            expr_values[":metrics"] = self._serialize_metadata(metrics)

        update_expr = "SET " + ", ".join(update_parts)

        try:
            self.table.update_item(
                Key={"workset_id": workset_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=expr_names if expr_names else None,
            )
            LOGGER.debug(
                "Updated progress for workset %s: step=%s, cluster=%s",
                workset_id,
                current_step,
                cluster_name,
            )
        except ClientError as e:
            LOGGER.warning("Failed to update progress for %s: %s", workset_id, str(e))

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
        key_condition = "#state = :state"
        expr_names: Dict[str, str] = {"#state": "state"}
        expr_values: Dict[str, str] = {":state": state.value}

        if priority:
            key_condition += " AND priority = :priority"
            expr_values[":priority"] = priority.value

        query_kwargs: Dict[str, Any] = {
            "IndexName": "state-priority-index",
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeNames": expr_names,
            "ExpressionAttributeValues": expr_values,
            "Limit": limit,
        }

        try:
            response = self.table.query(**query_kwargs)
            return [self._deserialize_item(item) for item in response.get("Items", [])]
        except ClientError as e:
            LOGGER.error("Failed to list worksets: %s", str(e))
            return []

    def list_locked_worksets(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List worksets that currently have a lock owner.

        Args:
            limit: Maximum number of results

        Returns:
            List of workset records with lock_owner set
        """
        items: List[Dict[str, Any]] = []
        scan_kwargs = {
            "FilterExpression": Attr("lock_owner").exists(),
            "Limit": limit,
        }
        try:
            while True:
                response = self.table.scan(**scan_kwargs)
                items.extend(response.get("Items", []))
                if len(items) >= limit or "LastEvaluatedKey" not in response:
                    break
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                scan_kwargs["Limit"] = limit - len(items)
        except ClientError as e:
            LOGGER.error("Failed to list locked worksets: %s", str(e))
            return []

        return [self._deserialize_item(item) for item in items[:limit]]

    def get_ready_worksets_prioritized(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get ready worksets ordered by priority (urgent first).

        Args:
            limit: Maximum number of results

        Returns:
            List of ready worksets sorted by priority
        """
        worksets: List[Dict[str, Any]] = []
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
        counts: Dict[str, int] = {}
        for ws_state in WorksetState:
            worksets = self.list_worksets_by_state(ws_state, limit=1000)
            counts[ws_state.value] = len(worksets)

        # Emit metrics
        for state_name, count in counts.items():
            self._emit_metric(f"QueueDepth{state_name.title()}", float(count))

        return counts

    def _serialize_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Python types to DynamoDB-compatible types."""
        def convert(obj: Any) -> Any:
            if isinstance(obj, float):
                return Decimal(str(obj))
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            return obj

        result: Dict[str, Any] = convert(data)
        return result

    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB types to Python types."""
        def convert(obj: Any) -> Any:
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            return obj

        result: Dict[str, Any] = convert(item)
        return result

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
                        "Timestamp": dt.datetime.now(dt.timezone.utc),
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
                dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=backoff_seconds)
            ).isoformat().replace("+00:00", "Z")

            new_state = WorksetState.RETRYING
            reason = f"Retry {retry_count + 1}/{max_retries} after {error_category.value} error"
        else:
            new_state = WorksetState.FAILED
            reason = f"Permanent failure after {retry_count} retries: {error_category.value}"
            retry_after = None

        # Update workset state
        now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
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
        now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

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
        try:
            self.update_state(
                workset_id,
                WorksetState.READY,
                reason="Reset for retry attempt",
            )
            return True
        except Exception:
            return False

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
                    ":now": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
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
            response = self.table.scan(
                FilterExpression="cluster_name = :cluster",
                ExpressionAttributeValues={":cluster": cluster_name},
            )
            return [self._deserialize_item(item) for item in response.get("Items", [])]
        except ClientError as e:
            LOGGER.error("Failed to get worksets for cluster %s: %s", cluster_name, str(e))
            return []

    def get_concurrent_worksets_count(self) -> int:
        """Get count of worksets currently in progress.

        Returns:
            Number of worksets in IN_PROGRESS plus locked worksets
        """
        in_progress = len(self.list_worksets_by_state(WorksetState.IN_PROGRESS, limit=1000))
        locked = len(self.list_locked_worksets(limit=1000))
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
        now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
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
                now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
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
        now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
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
