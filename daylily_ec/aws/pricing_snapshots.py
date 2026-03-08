"""Collect raw per-AZ Spot pricing snapshots for production partitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import yaml

from daylily_ec.resources import resource_path

DEFAULT_MONITORED_REGIONS: tuple[str, ...] = ("us-west-2", "us-east-1", "eu-central-1")
DEFAULT_PRODUCTION_PARTITIONS: tuple[str, ...] = (
    "i8",
    "i128",
    "i192",
    "i192mem",
    "i192bigmem",
)
_INSTANCE_TYPE_BATCH_SIZE = 100


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_cluster_config_path() -> Path:
    return resource_path("config/day_cluster/prod_cluster.yaml")


def resolve_cluster_config_path(cluster_config_path: Optional[str] = None) -> Path:
    """Resolve the cluster config used as the partition source of truth."""
    if not cluster_config_path:
        return _default_cluster_config_path()

    path = Path(cluster_config_path).expanduser()
    if path.is_file():
        return path
    return resource_path(cluster_config_path)


def _load_cluster_config(cluster_config_path: Optional[str] = None) -> Dict[str, Any]:
    path = resolve_cluster_config_path(cluster_config_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Cluster config must be a mapping: {path}")
    return data


def _partition_name(queue: Dict[str, Any]) -> str:
    name = queue.get("Name") or queue.get("QueueName")
    if not name:
        raise ValueError("Slurm queue is missing Name/QueueName")
    return str(name)


def load_partition_instance_types(
    *,
    cluster_config_path: Optional[str] = None,
    partitions: Optional[Sequence[str]] = None,
) -> Dict[str, List[str]]:
    """Return partition -> unique instance types from the cluster template."""
    requested = {
        partition.strip()
        for partition in (partitions or DEFAULT_PRODUCTION_PARTITIONS)
        if partition and partition.strip()
    }
    config = _load_cluster_config(cluster_config_path)
    queues = config.get("Scheduling", {}).get("SlurmQueues", [])
    result: Dict[str, List[str]] = {}

    for queue in queues:
        if not isinstance(queue, dict):
            continue
        partition = _partition_name(queue)
        if partition not in requested:
            continue

        instance_types: set[str] = set()
        for resource in queue.get("ComputeResources", []):
            if not isinstance(resource, dict):
                continue
            for instance in resource.get("Instances", []):
                if not isinstance(instance, dict):
                    continue
                instance_type = str(instance.get("InstanceType") or "").strip()
                if instance_type:
                    instance_types.add(instance_type)

        result[partition] = sorted(instance_types)

    missing = sorted(requested.difference(result))
    if missing:
        raise ValueError(f"Requested partitions not found in cluster config: {', '.join(missing)}")
    return result


def _chunked(values: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _get_available_zones(ec2_client: Any) -> List[str]:
    response = ec2_client.describe_availability_zones(
        Filters=[{"Name": "state", "Values": ["available"]}],
    )
    zones = [
        str(zone.get("ZoneName") or "").strip()
        for zone in response.get("AvailabilityZones", [])
        if str(zone.get("ZoneName") or "").strip()
    ]
    return sorted(zones)


def _get_vcpu_counts(ec2_client: Any, instance_types: Sequence[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for chunk in _chunked(list(instance_types), _INSTANCE_TYPE_BATCH_SIZE):
        response = ec2_client.describe_instance_types(InstanceTypes=list(chunk))
        for instance in response.get("InstanceTypes", []):
            instance_type = str(instance.get("InstanceType") or "").strip()
            vcpus = instance.get("VCpuInfo", {}).get("DefaultVCpus")
            if instance_type and isinstance(vcpus, int) and vcpus > 0:
                counts[instance_type] = vcpus
    return counts


def _get_current_spot_price(
    ec2_client: Any,
    *,
    instance_type: str,
    availability_zone: str,
) -> Optional[float]:
    response = ec2_client.describe_spot_price_history(
        InstanceTypes=[instance_type],
        AvailabilityZone=availability_zone,
        ProductDescriptions=["Linux/UNIX"],
        MaxResults=1,
    )
    history = response.get("SpotPriceHistory", [])
    if not history:
        return None

    raw_price = history[0].get("SpotPrice")
    try:
        return float(raw_price)
    except (TypeError, ValueError):
        return None


def _build_session(profile: Optional[str]) -> Any:
    import boto3

    if profile:
        return boto3.Session(profile_name=profile)
    return boto3.Session()


@dataclass(frozen=True)
class PricingPoint:
    captured_at: str
    region: str
    availability_zone: str
    partition: str
    instance_type: str
    vcpu_count: int
    hourly_spot_price: float
    vcpu_cost_per_hour: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PricingSnapshot:
    captured_at: str
    cluster_config_path: str
    regions: List[str]
    partitions: List[str]
    points: List[PricingPoint]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "captured_at": self.captured_at,
            "cluster_config_path": self.cluster_config_path,
            "regions": self.regions,
            "partitions": self.partitions,
            "points": [point.to_dict() for point in self.points],
        }


def collect_pricing_snapshot(
    *,
    regions: Optional[Sequence[str]] = None,
    partitions: Optional[Sequence[str]] = None,
    cluster_config_path: Optional[str] = None,
    profile: Optional[str] = None,
    captured_at: Optional[str] = None,
    session_factory: Optional[Callable[[Optional[str]], Any]] = None,
) -> PricingSnapshot:
    """Collect current per-AZ Spot prices for all requested partition instance types."""
    selected_regions = [region.strip() for region in (regions or DEFAULT_MONITORED_REGIONS) if region]
    selected_partitions = [
        partition.strip()
        for partition in (partitions or DEFAULT_PRODUCTION_PARTITIONS)
        if partition and partition.strip()
    ]
    resolved_config_path = resolve_cluster_config_path(cluster_config_path)
    partition_instances = load_partition_instance_types(
        cluster_config_path=str(resolved_config_path),
        partitions=selected_partitions,
    )
    all_instance_types = sorted({itype for values in partition_instances.values() for itype in values})
    if not all_instance_types:
        raise ValueError("No instance types found for the requested partitions")

    session_builder = session_factory or _build_session
    session = session_builder(profile)
    snapshot_points: List[PricingPoint] = []
    timestamp = captured_at or _now_iso()

    for region in selected_regions:
        ec2_client = session.client("ec2", region_name=region)
        zones = _get_available_zones(ec2_client)
        vcpu_counts = _get_vcpu_counts(ec2_client, all_instance_types)

        for partition in selected_partitions:
            for availability_zone in zones:
                for instance_type in partition_instances[partition]:
                    vcpu_count = vcpu_counts.get(instance_type)
                    if not vcpu_count:
                        continue
                    spot_price = _get_current_spot_price(
                        ec2_client,
                        instance_type=instance_type,
                        availability_zone=availability_zone,
                    )
                    if spot_price is None:
                        continue
                    snapshot_points.append(
                        PricingPoint(
                            captured_at=timestamp,
                            region=region,
                            availability_zone=availability_zone,
                            partition=partition,
                            instance_type=instance_type,
                            vcpu_count=vcpu_count,
                            hourly_spot_price=spot_price,
                            vcpu_cost_per_hour=round(spot_price / vcpu_count, 8),
                        )
                    )

    snapshot_points.sort(
        key=lambda point: (
            point.region,
            point.partition,
            point.availability_zone,
            point.instance_type,
        )
    )
    return PricingSnapshot(
        captured_at=timestamp,
        cluster_config_path=str(resolved_config_path),
        regions=selected_regions,
        partitions=selected_partitions,
        points=snapshot_points,
    )
