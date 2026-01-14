"""Integration layer bridging DynamoDB state management with S3 sentinel system.

This module provides unified state synchronization between the new UI/API layer
(DynamoDB-based) and the original processing engine (S3 sentinel-based).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError
import yaml

if TYPE_CHECKING:
    from daylib.workset_state_db import WorksetStateDB, WorksetState, WorksetPriority
    from daylib.workset_notifications import NotificationManager, NotificationEvent
    from daylib.workset_scheduler import WorksetScheduler

LOGGER = logging.getLogger("daylily.workset_integration")

# Sentinel file names (must match workset_monitor.py)
SENTINEL_FILES = {
    "ready": "daylily.ready",
    "lock": "daylily.lock",
    "in_progress": "daylily.in_progress",
    "error": "daylily.error",
    "complete": "daylily.complete",
    "ignore": "daylily.ignore",
}

WORK_YAML_NAME = "daylily_work.yaml"
INFO_YAML_NAME = "daylily_info.yaml"
STAGE_SAMPLES_NAME = "stage_samples.tsv"


class WorksetIntegration:
    """Bridge between DynamoDB state management and S3 sentinel-based system.
    
    Provides unified operations that keep both systems in sync:
    - Workset registration writes to both DynamoDB and S3
    - State updates propagate to both systems
    - Discovery can pull from either source
    - Notifications are triggered on state changes
    """

    def __init__(
        self,
        state_db: Optional["WorksetStateDB"] = None,
        s3_client: Optional[Any] = None,
        bucket: Optional[str] = None,
        prefix: str = "",
        notification_manager: Optional["NotificationManager"] = None,
        scheduler: Optional["WorksetScheduler"] = None,
        region: str = "us-west-2",
        profile: Optional[str] = None,
    ):
        """Initialize the integration layer.
        
        Args:
            state_db: DynamoDB state database (optional for S3-only mode)
            s3_client: Boto3 S3 client (created if not provided)
            bucket: S3 bucket for worksets
            prefix: S3 prefix for workset directories
            notification_manager: Optional notification manager
            scheduler: Optional workset scheduler
            region: AWS region
            profile: AWS profile name
        """
        self.state_db = state_db
        self.bucket = bucket
        self.prefix = prefix.strip("/") + "/" if prefix else ""
        self.notification_manager = notification_manager
        self.scheduler = scheduler
        
        if s3_client:
            self._s3 = s3_client
        else:
            session_kwargs = {"region_name": region}
            if profile:
                session_kwargs["profile_name"] = profile
            session = boto3.Session(**session_kwargs)
            self._s3 = session.client("s3")

    def register_workset(
        self,
        workset_id: str,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None,
        *,
        write_s3: bool = True,
        write_dynamodb: bool = True,
    ) -> bool:
        """Register a new workset in both DynamoDB and S3.
        
        Args:
            workset_id: Unique workset identifier
            bucket: S3 bucket (uses default if not provided)
            prefix: S3 prefix for this workset
            priority: Execution priority (urgent, normal, low)
            metadata: Additional workset metadata
            write_s3: Whether to write S3 sentinel files
            write_dynamodb: Whether to write DynamoDB record
            
        Returns:
            True if registration successful
        """
        target_bucket = bucket or self.bucket
        if not target_bucket:
            raise ValueError("Bucket must be specified")
        
        workset_prefix = prefix or f"{self.prefix}{workset_id}/"
        if not workset_prefix.endswith("/"):
            workset_prefix += "/"
        
        now = dt.datetime.utcnow().isoformat() + "Z"
        success = True
        
        # Write to DynamoDB first (if enabled and available)
        if write_dynamodb and self.state_db:
            from daylib.workset_state_db import WorksetPriority
            try:
                ws_priority = WorksetPriority(priority)
            except ValueError:
                ws_priority = WorksetPriority.NORMAL
            
            db_success = self.state_db.register_workset(
                workset_id=workset_id,
                bucket=target_bucket,
                prefix=workset_prefix,
                priority=ws_priority,
                metadata=metadata,
            )
            if not db_success:
                LOGGER.warning("DynamoDB registration failed for %s", workset_id)
                success = False
        
        # Write S3 sentinel files (if enabled)
        if write_s3:
            try:
                self._write_s3_workset_files(
                    bucket=target_bucket,
                    prefix=workset_prefix,
                    workset_id=workset_id,
                    metadata=metadata or {},
                    timestamp=now,
                )
            except Exception as e:
                LOGGER.error("S3 sentinel write failed for %s: %s", workset_id, e)
                success = False
        
        if success:
            LOGGER.info("Registered workset %s in bucket %s", workset_id, target_bucket)
            self._notify_state_change(workset_id, "ready", "Workset registered")

        return success

    def update_state(
        self,
        workset_id: str,
        new_state: str,
        reason: str,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
        error_details: Optional[str] = None,
        cluster_name: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        *,
        write_s3: bool = True,
        write_dynamodb: bool = True,
    ) -> bool:
        """Update workset state in both systems.

        Args:
            workset_id: Workset identifier
            new_state: New state (ready, locked, in_progress, error, complete, ignore)
            reason: Reason for state change
            bucket: S3 bucket
            prefix: S3 prefix for this workset
            error_details: Error message if state is error
            cluster_name: Associated cluster name
            metrics: Performance/cost metrics
            write_s3: Whether to update S3 sentinels
            write_dynamodb: Whether to update DynamoDB

        Returns:
            True if update successful
        """
        target_bucket = bucket or self.bucket
        workset_prefix = prefix or f"{self.prefix}{workset_id}/"

        now = dt.datetime.utcnow().isoformat() + "Z"
        success = True

        # Update DynamoDB
        if write_dynamodb and self.state_db:
            from daylib.workset_state_db import WorksetState
            try:
                ws_state = WorksetState(new_state)
                self.state_db.update_state(
                    workset_id=workset_id,
                    new_state=ws_state,
                    reason=reason,
                    error_details=error_details,
                    cluster_name=cluster_name,
                    metrics=metrics,
                )
            except Exception as e:
                LOGGER.error("DynamoDB state update failed for %s: %s", workset_id, e)
                success = False

        # Update S3 sentinel
        if write_s3 and target_bucket:
            try:
                self._write_sentinel(
                    bucket=target_bucket,
                    prefix=workset_prefix,
                    state=new_state,
                    timestamp=now,
                    content=reason,
                )
            except Exception as e:
                LOGGER.error("S3 sentinel update failed for %s: %s", workset_id, e)
                success = False

        if success:
            self._notify_state_change(workset_id, new_state, reason, error_details)

        return success

    def sync_s3_to_dynamodb(self, workset_prefix: str) -> Optional[str]:
        """Register an S3 workset in DynamoDB.

        Reads workset state from S3 sentinels and creates/updates DynamoDB record.

        Args:
            workset_prefix: S3 prefix for the workset

        Returns:
            Workset ID if sync successful, None otherwise
        """
        if not self.state_db or not self.bucket:
            LOGGER.warning("DynamoDB or bucket not configured for sync")
            return None

        # Determine workset ID from prefix
        workset_id = workset_prefix.rstrip("/").split("/")[-1]

        # Read current state from S3
        state = self._determine_s3_state(workset_prefix)
        metadata = self._read_work_yaml(workset_prefix)

        from daylib.workset_state_db import WorksetPriority, WorksetState

        # Check if workset already exists in DynamoDB
        existing = self.state_db.get_workset(workset_id)

        if existing:
            # Update state if changed
            try:
                ws_state = WorksetState(state)
                self.state_db.update_state(
                    workset_id=workset_id,
                    new_state=ws_state,
                    reason="Synced from S3 sentinel",
                )
            except ValueError:
                pass
        else:
            # Register new workset
            priority_str = metadata.get("priority", "normal") if metadata else "normal"
            try:
                ws_priority = WorksetPriority(priority_str)
            except ValueError:
                ws_priority = WorksetPriority.NORMAL

            self.state_db.register_workset(
                workset_id=workset_id,
                bucket=self.bucket,
                prefix=workset_prefix,
                priority=ws_priority,
                metadata=metadata,
            )

        LOGGER.info("Synced S3 workset %s to DynamoDB", workset_id)
        return workset_id

    def sync_dynamodb_to_s3(self, workset_id: str) -> bool:
        """Write S3 sentinel files for a DynamoDB workset.

        Args:
            workset_id: Workset identifier

        Returns:
            True if sync successful
        """
        if not self.state_db:
            LOGGER.warning("DynamoDB not configured for sync")
            return False

        workset = self.state_db.get_workset(workset_id)
        if not workset:
            LOGGER.error("Workset %s not found in DynamoDB", workset_id)
            return False

        bucket = workset.get("bucket", self.bucket)
        prefix = workset.get("prefix", f"{self.prefix}{workset_id}/")
        state = workset.get("state", "ready")
        metadata = workset.get("metadata", {})

        now = dt.datetime.utcnow().isoformat() + "Z"

        try:
            # Write work yaml if metadata present
            if metadata:
                self._write_s3_workset_files(
                    bucket=bucket,
                    prefix=prefix,
                    workset_id=workset_id,
                    metadata=metadata,
                    timestamp=now,
                )

            # Write current state sentinel
            self._write_sentinel(
                bucket=bucket,
                prefix=prefix,
                state=state,
                timestamp=now,
            )

            LOGGER.info("Synced DynamoDB workset %s to S3", workset_id)
            return True

        except Exception as e:
            LOGGER.error("Failed to sync workset %s to S3: %s", workset_id, e)
            return False

    def get_ready_worksets(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get worksets ready for processing from DynamoDB.

        Args:
            limit: Maximum number of results

        Returns:
            List of ready worksets prioritized by urgency
        """
        if not self.state_db:
            return []

        return self.state_db.get_ready_worksets_prioritized(limit=limit)

    def acquire_lock(
        self,
        workset_id: str,
        owner_id: str,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
    ) -> bool:
        """Acquire distributed lock on a workset.

        Uses DynamoDB for authoritative locking with S3 sentinel as backup.

        Args:
            workset_id: Workset identifier
            owner_id: Lock owner identifier
            bucket: S3 bucket
            prefix: S3 prefix

        Returns:
            True if lock acquired
        """
        target_bucket = bucket or self.bucket
        workset_prefix = prefix or f"{self.prefix}{workset_id}/"

        # Try DynamoDB lock first (authoritative)
        if self.state_db:
            if not self.state_db.acquire_lock(workset_id, owner_id):
                return False

        # Also write S3 lock sentinel for compatibility
        if target_bucket:
            now = dt.datetime.utcnow().isoformat() + "Z"
            try:
                self._write_sentinel(
                    bucket=target_bucket,
                    prefix=workset_prefix,
                    state="lock",
                    timestamp=now,
                    content=f"Locked by {owner_id}",
                )
            except Exception as e:
                LOGGER.warning("Failed to write S3 lock sentinel: %s", e)

        return True

    def release_lock(
        self,
        workset_id: str,
        owner_id: str,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
    ) -> bool:
        """Release lock on a workset.

        Args:
            workset_id: Workset identifier
            owner_id: Lock owner identifier
            bucket: S3 bucket
            prefix: S3 prefix

        Returns:
            True if lock released
        """
        target_bucket = bucket or self.bucket
        workset_prefix = prefix or f"{self.prefix}{workset_id}/"

        # Release DynamoDB lock
        if self.state_db:
            if not self.state_db.release_lock(workset_id, owner_id):
                return False

        # Remove S3 lock sentinel
        if target_bucket:
            try:
                lock_key = f"{workset_prefix}{SENTINEL_FILES['lock']}"
                self._s3.delete_object(Bucket=target_bucket, Key=lock_key)
            except Exception as e:
                LOGGER.warning("Failed to delete S3 lock sentinel: %s", e)

        return True

    # ========== Helper Methods ==========

    def _write_s3_workset_files(
        self,
        bucket: str,
        prefix: str,
        workset_id: str,
        metadata: Dict[str, Any],
        timestamp: str,
    ) -> None:
        """Write S3 files required for workset processing.

        Creates daylily_work.yaml, daylily_info.yaml, and daylily.ready sentinel.
        """
        if not prefix.endswith("/"):
            prefix += "/"

        # Build daylily_work.yaml from metadata
        work_yaml = self._build_work_yaml(workset_id, metadata)
        work_key = f"{prefix}{WORK_YAML_NAME}"
        self._s3.put_object(
            Bucket=bucket,
            Key=work_key,
            Body=yaml.dump(work_yaml, default_flow_style=False).encode("utf-8"),
            ContentType="text/yaml",
        )
        LOGGER.debug("Wrote %s to s3://%s/%s", WORK_YAML_NAME, bucket, work_key)

        # Build daylily_info.yaml
        info_yaml = {
            "workset_id": workset_id,
            "created_at": timestamp,
            "submitted_by": metadata.get("submitted_by", "unknown"),
            "pipeline_type": metadata.get("pipeline_type", "germline"),
            "reference_genome": metadata.get("reference_genome", "GRCh38"),
        }
        info_key = f"{prefix}{INFO_YAML_NAME}"
        self._s3.put_object(
            Bucket=bucket,
            Key=info_key,
            Body=yaml.dump(info_yaml, default_flow_style=False).encode("utf-8"),
            ContentType="text/yaml",
        )
        LOGGER.debug("Wrote %s to s3://%s/%s", INFO_YAML_NAME, bucket, info_key)

        # Write ready sentinel
        self._write_sentinel(bucket, prefix, "ready", timestamp)

    def _build_work_yaml(
        self, workset_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build daylily_work.yaml content from metadata."""
        pipeline_type = metadata.get("pipeline_type", "germline")
        reference = metadata.get("reference_genome", "GRCh38")

        # Map pipeline type to run command suffix
        run_suffix_map = {
            "germline": "dy-r GERMLINE",
            "somatic": "dy-r SOMATIC",
            "rnaseq": "dy-r RNASEQ",
            "wgs": "dy-r WGS",
            "wes": "dy-r WES",
        }
        run_suffix = run_suffix_map.get(pipeline_type, "dy-r GERMLINE")

        work_yaml = {
            "workset_name": metadata.get("workset_name", workset_id),
            "workdir_name": workset_id,
            "reference_genome": reference,
            "pipeline_type": pipeline_type,
            "dy-r": run_suffix,
            "enable_qc": metadata.get("enable_qc", True),
            "archive_results": metadata.get("archive_results", True),
            "priority": metadata.get("priority", "normal"),
        }

        # Add notification email if provided
        if metadata.get("notification_email"):
            work_yaml["notification_email"] = metadata["notification_email"]

        # Add export URI if configured
        if metadata.get("export_uri"):
            work_yaml["target_export_uri"] = metadata["export_uri"]

        return work_yaml

    def _write_sentinel(
        self,
        bucket: str,
        prefix: str,
        state: str,
        timestamp: str,
        content: Optional[str] = None,
    ) -> None:
        """Write a sentinel file to S3.

        Args:
            bucket: S3 bucket
            prefix: Workset prefix
            state: Sentinel state (ready, lock, in_progress, error, complete, ignore)
            timestamp: ISO timestamp
            content: Optional content for the sentinel file
        """
        if not prefix.endswith("/"):
            prefix += "/"

        sentinel_name = SENTINEL_FILES.get(state)
        if not sentinel_name:
            # Handle state variations
            state_map = {
                "in-progress": "in_progress",
                "ignored": "ignore",
                "locked": "lock",
            }
            sentinel_name = SENTINEL_FILES.get(state_map.get(state, state))

        if not sentinel_name:
            raise ValueError(f"Unknown sentinel state: {state}")

        key = f"{prefix}{sentinel_name}"
        body = content if content else timestamp

        self._s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="text/plain",
        )
        LOGGER.debug("Wrote sentinel %s to s3://%s/%s", sentinel_name, bucket, key)

    def _determine_s3_state(self, prefix: str) -> str:
        """Determine workset state from S3 sentinels.

        Args:
            prefix: Workset S3 prefix

        Returns:
            State string (ready, locked, in_progress, error, complete, ignored)
        """
        if not self.bucket:
            return "unknown"

        if not prefix.endswith("/"):
            prefix += "/"

        # Check sentinels in priority order
        state_priority = [
            ("ignore", "ignored"),
            ("complete", "complete"),
            ("error", "error"),
            ("in_progress", "in-progress"),
            ("lock", "locked"),
            ("ready", "ready"),
        ]

        for sentinel_key, state_value in state_priority:
            sentinel_name = SENTINEL_FILES.get(sentinel_key)
            if sentinel_name:
                key = f"{prefix}{sentinel_name}"
                try:
                    self._s3.head_object(Bucket=self.bucket, Key=key)
                    return state_value
                except ClientError:
                    continue

        return "unknown"

    def _read_work_yaml(self, prefix: str) -> Optional[Dict[str, Any]]:
        """Read daylily_work.yaml from S3.

        Args:
            prefix: Workset S3 prefix

        Returns:
            Parsed YAML content or None
        """
        if not self.bucket:
            return None

        if not prefix.endswith("/"):
            prefix += "/"

        key = f"{prefix}{WORK_YAML_NAME}"

        try:
            response = self._s3.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            return yaml.safe_load(content)
        except ClientError:
            return None
        except yaml.YAMLError as e:
            LOGGER.warning("Failed to parse %s: %s", key, e)
            return None

    def _notify_state_change(
        self,
        workset_id: str,
        state: str,
        message: str,
        error_details: Optional[str] = None,
    ) -> None:
        """Send notification for state change.

        Args:
            workset_id: Workset identifier
            state: New state
            message: State change message
            error_details: Error details if applicable
        """
        if not self.notification_manager:
            return

        from daylib.workset_notifications import NotificationEvent

        event = NotificationEvent(
            workset_id=workset_id,
            event_type="state_change",
            state=state,
            message=message,
            error_details=error_details,
        )

        try:
            self.notification_manager.notify(event)
        except Exception as e:
            LOGGER.warning("Failed to send notification for %s: %s", workset_id, e)

