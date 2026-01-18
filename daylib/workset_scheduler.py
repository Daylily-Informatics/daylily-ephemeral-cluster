"""Intelligent workset scheduling with priority queue and resource awareness.

Implements cost-based and resource-aware scheduling for optimal cluster utilization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from daylib.workset_state_db import WorksetPriority, WorksetState, WorksetStateDB

LOGGER = logging.getLogger("daylily.workset_scheduler")


@dataclass
class WorksetRequirements:
    """Resource requirements for a workset."""
    estimated_vcpu_hours: Optional[float] = None
    estimated_memory_gb: Optional[float] = None
    estimated_storage_gb: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    estimated_duration_minutes: Optional[int] = None
    preferred_instance_types: Optional[List[str]] = None
    preferred_availability_zone: Optional[str] = None


@dataclass
class ClusterCapacity:
    """Current capacity and utilization of a cluster."""
    cluster_name: str
    availability_zone: str
    max_vcpus: int
    current_vcpus_used: int
    max_memory_gb: float
    current_memory_gb_used: float
    active_worksets: int
    max_concurrent_worksets: int
    cost_per_vcpu_hour: float


@dataclass
class SchedulingDecision:
    """Result of scheduling decision."""
    workset_id: str
    cluster_name: Optional[str]
    should_create_cluster: bool
    estimated_start_delay_minutes: int
    reason: str


class WorksetScheduler:
    """Intelligent scheduler for workset execution."""
    
    def __init__(
        self,
        state_db: WorksetStateDB,
        max_concurrent_worksets_per_cluster: int = 3,
        cost_optimization_enabled: bool = True,
    ):
        """Initialize the scheduler.
        
        Args:
            state_db: Workset state database
            max_concurrent_worksets_per_cluster: Max worksets per cluster
            cost_optimization_enabled: Enable cost-based scheduling
        """
        self.state_db = state_db
        self.max_concurrent_worksets_per_cluster = max_concurrent_worksets_per_cluster
        self.cost_optimization_enabled = cost_optimization_enabled
        self.cluster_capacities: Dict[str, ClusterCapacity] = {}
    
    def register_cluster(self, capacity: ClusterCapacity) -> None:
        """Register a cluster's capacity for scheduling.
        
        Args:
            capacity: Cluster capacity information
        """
        self.cluster_capacities[capacity.cluster_name] = capacity
        LOGGER.info(
            "Registered cluster %s in %s with %d vCPUs",
            capacity.cluster_name,
            capacity.availability_zone,
            capacity.max_vcpus,
        )
    
    def update_cluster_utilization(
        self,
        cluster_name: str,
        vcpus_used: int,
        memory_gb_used: float,
        active_worksets: int,
    ) -> None:
        """Update cluster utilization metrics.
        
        Args:
            cluster_name: Cluster name
            vcpus_used: Current vCPU usage
            memory_gb_used: Current memory usage in GB
            active_worksets: Number of active worksets
        """
        if cluster_name in self.cluster_capacities:
            capacity = self.cluster_capacities[cluster_name]
            capacity.current_vcpus_used = vcpus_used
            capacity.current_memory_gb_used = memory_gb_used
            capacity.active_worksets = active_worksets
    
    def get_next_workset(self) -> Optional[Dict]:
        """Get the next workset to execute based on priority and resources.
        
        Returns:
            Next workset to execute, or None if none available
        """
        # Get ready worksets ordered by priority
        ready_worksets = self.state_db.get_ready_worksets_prioritized(limit=100)
        
        if not ready_worksets:
            return None
        
        # If cost optimization is enabled, sort by estimated cost within priority groups
        if self.cost_optimization_enabled:
            ready_worksets = self._sort_by_cost_efficiency(ready_worksets)
        
        return ready_worksets[0] if ready_worksets else None
    
    def schedule_workset(
        self,
        workset_id: str,
        requirements: Optional[WorksetRequirements] = None,
    ) -> SchedulingDecision:
        """Make scheduling decision for a workset.
        
        Args:
            workset_id: Workset to schedule
            requirements: Resource requirements (optional)
            
        Returns:
            Scheduling decision
        """
        # Find best cluster for this workset
        best_cluster = self._find_best_cluster(requirements)
        
        if best_cluster:
            capacity = self.cluster_capacities[best_cluster]
            
            # Check if cluster has capacity
            if capacity.active_worksets < capacity.max_concurrent_worksets:
                return SchedulingDecision(
                    workset_id=workset_id,
                    cluster_name=best_cluster,
                    should_create_cluster=False,
                    estimated_start_delay_minutes=0,
                    reason=f"Scheduled on existing cluster {best_cluster}",
                )
            else:
                # Estimate wait time based on average workset duration
                avg_duration = 120  # Default 2 hours
                return SchedulingDecision(
                    workset_id=workset_id,
                    cluster_name=best_cluster,
                    should_create_cluster=False,
                    estimated_start_delay_minutes=avg_duration // capacity.active_worksets,
                    reason=f"Queued for cluster {best_cluster} (at capacity)",
                )
        
        # No suitable cluster found, need to create one
        return SchedulingDecision(
            workset_id=workset_id,
            cluster_name=None,
            should_create_cluster=True,
            estimated_start_delay_minutes=15,  # Cluster creation time
            reason="No suitable cluster available, will create new cluster",
        )

    def _find_best_cluster(
        self,
        requirements: Optional[WorksetRequirements] = None,
    ) -> Optional[str]:
        """Find the best cluster for a workset based on requirements and cost.

        Args:
            requirements: Workset resource requirements

        Returns:
            Best cluster name, or None if no suitable cluster
        """
        if not self.cluster_capacities:
            return None

        candidates = []

        for cluster_name, capacity in self.cluster_capacities.items():
            # Check if cluster has any capacity
            if capacity.active_worksets >= capacity.max_concurrent_worksets:
                continue

            # Check availability zone preference
            if requirements and requirements.preferred_availability_zone:
                if capacity.availability_zone != requirements.preferred_availability_zone:
                    continue

            # Calculate score based on cost and utilization
            utilization = capacity.current_vcpus_used / capacity.max_vcpus
            cost_score = capacity.cost_per_vcpu_hour

            # Prefer clusters with moderate utilization (better for spot stability)
            utilization_score = abs(0.6 - utilization)  # Optimal around 60%

            # Combined score (lower is better)
            score = cost_score * 10 + utilization_score

            candidates.append((cluster_name, score))

        if not candidates:
            return None

        # Sort by score and return best
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    def _sort_by_cost_efficiency(self, worksets: List[Dict]) -> List[Dict]:
        """Sort worksets by cost efficiency within priority groups.

        Args:
            worksets: List of workset records

        Returns:
            Sorted list of worksets
        """
        def cost_key(workset: Dict) -> Tuple[int, float]:
            priority = workset.get("priority", "normal")
            priority_order = {
                WorksetPriority.URGENT.value: 0,
                WorksetPriority.NORMAL.value: 1,
                WorksetPriority.LOW.value: 2,
            }

            # Get estimated cost from metadata
            metadata = workset.get("metadata", {})
            estimated_cost = metadata.get("estimated_cost_usd", 999999.0)

            return (priority_order.get(priority, 1), estimated_cost)

        return sorted(worksets, key=cost_key)

    def get_scheduling_stats(self) -> Dict[str, Any]:
        """Get scheduling statistics.

        Returns:
            Dictionary of scheduling metrics
        """
        total_capacity = sum(c.max_vcpus for c in self.cluster_capacities.values())
        total_used = sum(c.current_vcpus_used for c in self.cluster_capacities.values())
        total_worksets = sum(c.active_worksets for c in self.cluster_capacities.values())

        queue_depth = self.state_db.get_queue_depth()

        return {
            "total_clusters": len(self.cluster_capacities),
            "total_vcpu_capacity": total_capacity,
            "total_vcpus_used": total_used,
            "vcpu_utilization_percent": (total_used / total_capacity * 100) if total_capacity > 0 else 0,
            "total_active_worksets": total_worksets,
            "queue_depth": queue_depth,
        }

