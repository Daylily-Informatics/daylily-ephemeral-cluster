"""Multi-region support for workset state management.

Provides DynamoDB Global Tables integration for cross-region replication
and latency-based routing for optimal performance.
"""

from __future__ import annotations

import datetime as dt
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

from daylib.workset_state_db import WorksetStateDB, WorksetState, WorksetPriority

LOGGER = logging.getLogger("daylily.workset_multi_region")


class RegionStatus(str, Enum):
    """Region health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class RegionHealth:
    """Health metrics for a region."""
    region: str
    status: RegionStatus = RegionStatus.UNKNOWN
    latency_ms: float = 0.0
    last_check: Optional[dt.datetime] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    
    def is_available(self) -> bool:
        """Check if region is available for routing."""
        return self.status in [RegionStatus.HEALTHY, RegionStatus.DEGRADED]


@dataclass
class MultiRegionConfig:
    """Configuration for multi-region setup."""
    primary_region: str
    replica_regions: List[str] = field(default_factory=list)
    table_name: str = "daylily-worksets"
    health_check_interval_seconds: int = 30
    failover_threshold: int = 3  # Consecutive failures before failover
    latency_threshold_ms: float = 500.0  # Mark degraded if above this
    enable_global_tables: bool = True
    profile: Optional[str] = None


class WorksetMultiRegionDB:
    """Multi-region workset state database with automatic failover."""

    def __init__(self, config: MultiRegionConfig):
        """Initialize multi-region database.
        
        Args:
            config: Multi-region configuration
        """
        self.config = config
        self.all_regions = [config.primary_region] + config.replica_regions
        
        # Initialize per-region connections
        self._connections: Dict[str, WorksetStateDB] = {}
        self._region_health: Dict[str, RegionHealth] = {}
        
        for region in self.all_regions:
            self._region_health[region] = RegionHealth(region=region)
            try:
                self._connections[region] = WorksetStateDB(
                    table_name=config.table_name,
                    region=region,
                    profile=config.profile,
                )
                LOGGER.info("Initialized connection to region %s", region)
            except Exception as e:
                LOGGER.error("Failed to initialize region %s: %s", region, str(e))
                self._region_health[region].status = RegionStatus.UNHEALTHY
                self._region_health[region].last_error = str(e)
        
        # Active region for writes (always primary for Global Tables)
        self._active_region = config.primary_region
        
        # Health check thread
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_health_check = threading.Event()
        
        # Metrics
        self._request_count: Dict[str, int] = {r: 0 for r in self.all_regions}
        self._error_count: Dict[str, int] = {r: 0 for r in self.all_regions}
        
    def start_health_monitoring(self) -> None:
        """Start background health monitoring thread."""
        if self._health_check_thread and self._health_check_thread.is_alive():
            LOGGER.warning("Health monitoring already running")
            return
            
        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="multi-region-health-monitor",
        )
        self._health_check_thread.start()
        LOGGER.info("Started health monitoring thread")
        
    def stop_health_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._stop_health_check.set()
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5.0)
            LOGGER.info("Stopped health monitoring thread")

    def _health_check_loop(self) -> None:
        """Background health check loop."""
        while not self._stop_health_check.is_set():
            for region in self.all_regions:
                try:
                    self._check_region_health(region)
                except Exception as e:
                    LOGGER.error("Health check failed for %s: %s", region, str(e))

            # Update active region based on health
            self._update_active_region()

            self._stop_health_check.wait(self.config.health_check_interval_seconds)

    def _check_region_health(self, region: str) -> None:
        """Check health of a specific region."""
        health = self._region_health[region]
        conn = self._connections.get(region)

        if not conn:
            health.status = RegionStatus.UNHEALTHY
            health.last_error = "No connection available"
            return

        start_time = time.monotonic()
        try:
            # Perform lightweight health check (describe table)
            conn.table.load()
            latency = (time.monotonic() - start_time) * 1000

            health.latency_ms = latency
            health.last_check = dt.datetime.now(dt.timezone.utc)
            health.consecutive_failures = 0
            health.last_error = None

            if latency > self.config.latency_threshold_ms:
                health.status = RegionStatus.DEGRADED
                LOGGER.warning("Region %s degraded (latency: %.1fms)", region, latency)
            else:
                health.status = RegionStatus.HEALTHY

        except (ClientError, EndpointConnectionError) as e:
            health.consecutive_failures += 1
            health.last_error = str(e)
            health.last_check = dt.datetime.now(dt.timezone.utc)

            if health.consecutive_failures >= self.config.failover_threshold:
                health.status = RegionStatus.UNHEALTHY
                LOGGER.error(
                    "Region %s marked unhealthy after %d failures: %s",
                    region, health.consecutive_failures, e
                )
            else:
                health.status = RegionStatus.DEGRADED
                LOGGER.warning(
                    "Region %s health check failed (%d/%d): %s",
                    region, health.consecutive_failures,
                    self.config.failover_threshold, e
                )

    def _update_active_region(self) -> None:
        """Update active region based on health status."""
        primary_health = self._region_health.get(self.config.primary_region)

        # Prefer primary if healthy
        if primary_health and primary_health.is_available():
            if self._active_region != self.config.primary_region:
                LOGGER.info("Restoring primary region %s", self.config.primary_region)
                self._active_region = self.config.primary_region
            return

        # Find best available replica
        for region in self.config.replica_regions:
            health = self._region_health.get(region)
            if health and health.is_available():
                if self._active_region != region:
                    LOGGER.warning("Failing over to region %s", region)
                    self._active_region = region
                return

        LOGGER.critical("No healthy regions available!")

    def get_best_read_region(self) -> str:
        """Get best region for read operations based on latency.

        Returns:
            Region with lowest latency that is healthy
        """
        available_regions = [
            (r, h) for r, h in self._region_health.items()
            if h.is_available()
        ]

        if not available_regions:
            LOGGER.warning("No healthy regions, falling back to primary")
            return self.config.primary_region

        # Sort by latency
        available_regions.sort(key=lambda x: x[1].latency_ms)
        return available_regions[0][0]

    def _get_connection(self, region: str) -> Optional[WorksetStateDB]:
        """Get connection for a region with fallback."""
        conn = self._connections.get(region)
        if conn:
            return conn

        # Try to establish connection
        try:
            conn = WorksetStateDB(
                table_name=self.config.table_name,
                region=region,
                profile=self.config.profile,
            )
            self._connections[region] = conn
            return conn
        except Exception as e:
            LOGGER.error("Failed to connect to region %s: %s", region, str(e))
            return None

    def _with_retry(
        self,
        operation: Callable,
        read_only: bool = False,
    ) -> Any:
        """Execute operation with automatic region failover.

        Args:
            operation: Callable that takes a WorksetStateDB connection
            read_only: If True, can use any healthy region

        Returns:
            Result of operation
        """
        if read_only:
            regions_to_try = sorted(
                self.all_regions,
                key=lambda r: self._region_health.get(r, RegionHealth(region=r)).latency_ms
            )
        else:
            # Writes always go to active region first
            regions_to_try = [self._active_region] + [
                r for r in self.all_regions if r != self._active_region
            ]

        last_error = None
        for region in regions_to_try:
            health = self._region_health.get(region)
            if health and not health.is_available() and not read_only:
                continue

            conn = self._get_connection(region)
            if not conn:
                continue

            try:
                self._request_count[region] = self._request_count.get(region, 0) + 1
                result = operation(conn)
                return result
            except (ClientError, EndpointConnectionError) as e:
                self._error_count[region] = self._error_count.get(region, 0) + 1
                last_error = e
                LOGGER.warning("Operation failed in region %s: %s", region, str(e))
                continue

        raise last_error or RuntimeError("No regions available")

    # ========== Proxied State DB Methods ==========

    def register_workset(
        self,
        workset_id: str,
        bucket: str,
        prefix: str,
        priority: WorksetPriority = WorksetPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Register workset (writes to active region)."""
        result: bool = bool(self._with_retry(
            lambda conn: conn.register_workset(
                workset_id, bucket, prefix, priority, metadata
            ),
            read_only=False,
        ))
        return result

    def get_workset(self, workset_id: str) -> Optional[Dict[str, Any]]:
        """Get workset (reads from best region)."""
        result: Optional[Dict[str, Any]] = self._with_retry(
            lambda conn: conn.get_workset(workset_id),
            read_only=True,
        )
        return result

    def update_state(
        self,
        workset_id: str,
        new_state: WorksetState,
        reason: str,
        error_details: Optional[str] = None,
        cluster_name: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update workset state (writes to active region)."""
        self._with_retry(
            lambda conn: conn.update_state(
                workset_id, new_state, reason, error_details, cluster_name, metrics
            ),
            read_only=False,
        )

    def acquire_lock(
        self,
        workset_id: str,
        owner_id: str,
        force: bool = False,
    ) -> bool:
        """Acquire lock (writes to active region)."""
        result: bool = bool(self._with_retry(
            lambda conn: conn.acquire_lock(workset_id, owner_id, force),
            read_only=False,
        ))
        return result

    def release_lock(self, workset_id: str, owner_id: str) -> bool:
        """Release lock (writes to active region)."""
        result: bool = bool(self._with_retry(
            lambda conn: conn.release_lock(workset_id, owner_id),
            read_only=False,
        ))
        return result

    def list_worksets_by_state(
        self,
        state: WorksetState,
        priority: Optional[WorksetPriority] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List worksets (reads from best region)."""
        result: List[Dict[str, Any]] = list(self._with_retry(
            lambda conn: conn.list_worksets_by_state(state, priority, limit),
            read_only=True,
        ))
        return result

    def get_ready_worksets_prioritized(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get ready worksets (reads from best region)."""
        result: List[Dict[str, Any]] = list(self._with_retry(
            lambda conn: conn.get_ready_worksets_prioritized(limit),
            read_only=True,
        ))
        return result

    def get_queue_depth(self) -> Dict[str, int]:
        """Get queue depth (reads from best region)."""
        result: Dict[str, int] = dict(self._with_retry(
            lambda conn: conn.get_queue_depth(),
            read_only=True,
        ))
        return result

    # ========== Global Tables Management ==========

    def create_global_table(self) -> bool:
        """Create DynamoDB Global Table across configured regions.

        Creates the table in the primary region first, then adds replicas.

        Returns:
            True if successful
        """
        if not self.config.enable_global_tables:
            LOGGER.warning("Global Tables disabled in config")
            return False

        # First, ensure table exists in primary region
        primary_conn = self._connections.get(self.config.primary_region)
        if not primary_conn:
            LOGGER.error("No connection to primary region")
            return False

        try:
            primary_conn.create_table_if_not_exists()
            LOGGER.info("Ensured table exists in primary region %s",
                       self.config.primary_region)
        except Exception as e:
            LOGGER.error("Failed to create table in primary: %s", str(e))
            return False

        # Create Global Table with replicas
        if not self.config.replica_regions:
            LOGGER.info("No replica regions configured")
            return True

        try:
            session = boto3.Session(
                region_name=self.config.primary_region,
                profile_name=self.config.profile,
            )
            dynamodb = session.client("dynamodb")

            # Check if already a Global Table
            response = dynamodb.describe_table(TableName=self.config.table_name)
            table_info = response.get("Table", {})

            existing_replicas = {
                r["RegionName"]
                for r in table_info.get("Replicas", [])
            }

            # Add missing replicas
            replicas_to_add = [
                r for r in self.config.replica_regions
                if r not in existing_replicas
            ]

            if not replicas_to_add:
                LOGGER.info("All replicas already configured")
                return True

            # Create replicas
            replica_updates = [
                {"Create": {"RegionName": region}}
                for region in replicas_to_add
            ]

            dynamodb.update_table(
                TableName=self.config.table_name,
                ReplicaUpdates=replica_updates,
            )

            LOGGER.info("Added Global Table replicas: %s", replicas_to_add)

            # Wait for replicas to become active
            self._wait_for_replicas(dynamodb, replicas_to_add)

            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "GlobalTableAlreadyExistsException":
                LOGGER.info("Global Table already exists")
                return True
            LOGGER.error("Failed to create Global Table: %s", str(e))
            return False

    def _wait_for_replicas(
        self,
        dynamodb,
        regions: List[str],
        timeout_seconds: int = 600,
    ) -> None:
        """Wait for replica regions to become active."""
        start = time.monotonic()

        while time.monotonic() - start < timeout_seconds:
            response = dynamodb.describe_table(TableName=self.config.table_name)
            replicas = response.get("Table", {}).get("Replicas", [])

            pending = []
            for replica in replicas:
                if replica["RegionName"] in regions:
                    status = replica.get("ReplicaStatus", "UNKNOWN")
                    if status != "ACTIVE":
                        pending.append(f"{replica['RegionName']}:{status}")

            if not pending:
                LOGGER.info("All replicas active")
                return

            LOGGER.info("Waiting for replicas: %s", pending)
            time.sleep(10)

        LOGGER.warning("Timeout waiting for replicas to become active")

    def remove_replica(self, region: str) -> bool:
        """Remove a replica region from Global Table.

        Args:
            region: Region to remove

        Returns:
            True if successful
        """
        if region == self.config.primary_region:
            LOGGER.error("Cannot remove primary region")
            return False

        try:
            session = boto3.Session(
                region_name=self.config.primary_region,
                profile_name=self.config.profile,
            )
            dynamodb = session.client("dynamodb")

            dynamodb.update_table(
                TableName=self.config.table_name,
                ReplicaUpdates=[
                    {"Delete": {"RegionName": region}}
                ],
            )

            LOGGER.info("Removed replica region %s", region)

            # Update local state
            if region in self.config.replica_regions:
                self.config.replica_regions.remove(region)
            if region in self._connections:
                del self._connections[region]
            if region in self._region_health:
                del self._region_health[region]

            return True

        except ClientError as e:
            LOGGER.error("Failed to remove replica %s: %s", region, str(e))
            return False

    # ========== Status & Metrics ==========

    def get_region_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all regions.

        Returns:
            Dict mapping region to health info
        """
        status = {}
        for region, health in self._region_health.items():
            status[region] = {
                "status": health.status.value,
                "latency_ms": health.latency_ms,
                "last_check": health.last_check.isoformat() if health.last_check else None,
                "consecutive_failures": health.consecutive_failures,
                "last_error": health.last_error,
                "is_active": region == self._active_region,
                "is_primary": region == self.config.primary_region,
                "request_count": self._request_count.get(region, 0),
                "error_count": self._error_count.get(region, 0),
            }
        return status

    def get_active_region(self) -> str:
        """Get currently active region for writes."""
        return self._active_region

    def force_failover(self, target_region: str) -> bool:
        """Force failover to a specific region.

        Args:
            target_region: Region to failover to

        Returns:
            True if successful
        """
        if target_region not in self.all_regions:
            LOGGER.error("Unknown region: %s", target_region)
            return False

        health = self._region_health.get(target_region)
        if not health or not health.is_available():
            LOGGER.warning("Target region %s is not healthy", target_region)

        LOGGER.warning("Forcing failover to region %s", target_region)
        self._active_region = target_region
        return True

    def get_replication_status(self) -> Dict[str, Any]:
        """Get Global Table replication status.

        Returns:
            Dict with replication info
        """
        try:
            session = boto3.Session(
                region_name=self.config.primary_region,
                profile_name=self.config.profile,
            )
            dynamodb = session.client("dynamodb")

            response = dynamodb.describe_table(TableName=self.config.table_name)
            table_info = response.get("Table", {})

            replicas = []
            for replica in table_info.get("Replicas", []):
                replicas.append({
                    "region": replica["RegionName"],
                    "status": replica.get("ReplicaStatus", "UNKNOWN"),
                    "status_description": replica.get("ReplicaStatusDescription"),
                })

            return {
                "table_name": self.config.table_name,
                "is_global_table": len(replicas) > 0,
                "primary_region": self.config.primary_region,
                "replicas": replicas,
                "table_status": table_info.get("TableStatus"),
            }

        except ClientError as e:
            LOGGER.error("Failed to get replication status: %s", str(e))
            return {"error": str(e)}

