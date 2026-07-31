"""Collect per-AZ Spot pricing points, summaries, and placement scores."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import harmonic_mean, median
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import yaml
from tabulate import tabulate

from daylily_ec.resources import resource_path

DEFAULT_MONITORED_REGIONS: tuple[str, ...] = ("us-west-2", "us-east-1", "eu-central-1")
DEFAULT_PRODUCTION_PARTITIONS: tuple[str, ...] = (
    "i8",
    "i128",
    "i128shm",
    "i128nvme",
    "i192",
    "i192shm",
    "i192nvme",
    "i384shm",
    "i384nvme",
    "i192hugenvme",
)
_INSTANCE_TYPE_BATCH_SIZE = 100
DEFAULT_CLUSTER_CONFIG_RELPATH = (
    "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_cluster_config_path() -> Path:
    return resource_path(DEFAULT_CLUSTER_CONFIG_RELPATH)


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


def _get_available_zone_metadata(ec2_client: Any) -> tuple[List[str], Dict[str, str]]:
    response = ec2_client.describe_availability_zones(
        Filters=[{"Name": "state", "Values": ["available"]}],
    )
    zone_names: List[str] = []
    zone_id_to_name: Dict[str, str] = {}
    for zone in response.get("AvailabilityZones", []):
        zone_name = str(zone.get("ZoneName") or "").strip()
        if not zone_name:
            continue
        zone_names.append(zone_name)
        zone_id = str(zone.get("ZoneId") or "").strip()
        if zone_id:
            zone_id_to_name[zone_id] = zone_name
    return sorted(zone_names), zone_id_to_name


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


def _get_spot_placement_scores(
    ec2_client: Any,
    *,
    region: str,
    partition_instance_types: Dict[str, List[str]],
    target_capacity_vcpus: int,
    zone_id_to_name: Dict[str, str],
) -> Dict[tuple[str, str, str], int]:
    """Return EC2 Spot Placement Scores keyed by region, partition, and AZ name."""

    scores: Dict[tuple[str, str, str], int] = {}
    for partition, instance_types in partition_instance_types.items():
        next_token: Optional[str] = None
        while True:
            request: Dict[str, Any] = {
                "InstanceTypes": list(instance_types),
                "TargetCapacity": target_capacity_vcpus,
                "TargetCapacityUnitType": "vcpu",
                "SingleAvailabilityZone": True,
                "RegionNames": [region],
                "MaxResults": 1000,
            }
            if next_token:
                request["NextToken"] = next_token
            response = ec2_client.get_spot_placement_scores(**request)
            for item in response.get("SpotPlacementScores", []):
                item_region = str(item.get("Region") or "").strip()
                if item_region != region:
                    raise ValueError(
                        "Spot Placement Score response region does not match request: "
                        f"expected {region}, received {item_region or '<missing>'}"
                    )
                zone_id = str(item.get("AvailabilityZoneId") or "").strip()
                if zone_id not in zone_id_to_name:
                    raise ValueError(
                        "Spot Placement Score response returned an unknown availability-zone ID: "
                        f"{zone_id or '<missing>'}"
                    )
                raw_score = item.get("Score")
                if not isinstance(raw_score, int) or not 1 <= raw_score <= 10:
                    raise ValueError(
                        "Spot Placement Score must be an integer from 1 through 10: "
                        f"{raw_score!r}"
                    )
                key = (region, partition, zone_id_to_name[zone_id])
                previous = scores.get(key)
                if previous is not None and previous != raw_score:
                    raise ValueError(
                        "Spot Placement Score response returned conflicting scores for "
                        f"{region}/{partition}/{zone_id_to_name[zone_id]}: "
                        f"{previous} and {raw_score}"
                    )
                scores[key] = raw_score
            next_token = str(response.get("NextToken") or "").strip() or None
            if next_token is None:
                break
    return scores


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
class PartitionZonePricingSummary:
    region: str
    availability_zone: str
    partition: str
    priced_instance_count: int
    configured_instance_count: int
    price_coverage_percent: float
    min_hourly_spot_price: Optional[float]
    median_hourly_spot_price: Optional[float]
    harmonic_mean_hourly_spot_price: Optional[float]
    max_hourly_spot_price: Optional[float]
    spread_hourly_spot_price: Optional[float]
    spot_placement_target_capacity_vcpus: Optional[int]
    spot_placement_score: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PricingSnapshot:
    captured_at: str
    cluster_config_path: str
    regions: List[str]
    partitions: List[str]
    target_capacity_vcpus: Optional[int]
    summaries: List[PartitionZonePricingSummary]
    points: List[PricingPoint]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "captured_at": self.captured_at,
            "cluster_config_path": self.cluster_config_path,
            "regions": self.regions,
            "partitions": self.partitions,
            "target_capacity_vcpus": self.target_capacity_vcpus,
            "summaries": [summary.to_dict() for summary in self.summaries],
            "points": [point.to_dict() for point in self.points],
        }


PRICING_SNAPSHOT_TABLE_HEADERS: tuple[str, ...] = (
    "Partition",
    "AZ",
    "Priced/Configured",
    "Coverage %",
    "Min USD/hr",
    "Median USD/hr",
    "Harmonic USD/hr",
    "Max USD/hr",
    "Spread USD/hr",
    "Spot Placement Score",
)


def _format_optional_price(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value:.5f}"


def format_pricing_snapshot_table(payload: Dict[str, Any]) -> str:
    """Render per-partition/AZ pricing statistics and Spot Placement Scores."""

    target_capacity_vcpus = payload["target_capacity_vcpus"]
    if not isinstance(target_capacity_vcpus, int) or target_capacity_vcpus < 1:
        raise ValueError(
            "A positive target_capacity_vcpus is required to render the pricing summary table"
        )

    rows = [
        (
            str(summary["partition"]),
            str(summary["availability_zone"]),
            f'{summary["priced_instance_count"]}/{summary["configured_instance_count"]}',
            f'{float(summary["price_coverage_percent"]):.2f}%',
            _format_optional_price(summary["min_hourly_spot_price"]),
            _format_optional_price(summary["median_hourly_spot_price"]),
            _format_optional_price(summary["harmonic_mean_hourly_spot_price"]),
            _format_optional_price(summary["max_hourly_spot_price"]),
            _format_optional_price(summary["spread_hourly_spot_price"]),
            (
                "N/A"
                if summary["spot_placement_score"] is None
                else str(summary["spot_placement_score"])
            ),
        )
        for summary in payload["summaries"]
    ]
    table = tabulate(
        rows,
        headers=PRICING_SNAPSHOT_TABLE_HEADERS,
        tablefmt="grid",
        colalign=("left", "left", "right", "right", "right", "right", "right", "right", "right", "right"),
        disable_numparse=True,
    )
    metadata = (
        f'Captured at: {payload["captured_at"]}\n'
        f'Cluster config: {payload["cluster_config_path"]}\n'
        f'Regions: {", ".join(str(value) for value in payload["regions"])}\n'
        f'Partitions: {", ".join(str(value) for value in payload["partitions"])}\n'
        f"Spot Placement Score target: {target_capacity_vcpus} vCPUs\n"
        "Spot Placement Score scale: 1 (lowest capacity likelihood) to 10 (highest)"
    )
    return f"{metadata}\n\n{table}"


def _build_partition_zone_summaries(
    *,
    regions: Sequence[str],
    region_zones: Dict[str, List[str]],
    partitions: Sequence[str],
    partition_instance_types: Dict[str, List[str]],
    points: Sequence[PricingPoint],
    target_capacity_vcpus: Optional[int],
    placement_scores: Dict[tuple[str, str, str], int],
) -> List[PartitionZonePricingSummary]:
    prices_by_key: Dict[tuple[str, str, str], List[float]] = {}
    for point in points:
        prices_by_key.setdefault(
            (point.region, point.partition, point.availability_zone), []
        ).append(point.hourly_spot_price)

    summaries: List[PartitionZonePricingSummary] = []
    for region in regions:
        for partition in partitions:
            configured_count = len(partition_instance_types[partition])
            for availability_zone in region_zones[region]:
                key = (region, partition, availability_zone)
                prices = prices_by_key.get(key, [])
                priced_count = len(prices)
                coverage = round((priced_count / configured_count) * 100.0, 2)
                summaries.append(
                    PartitionZonePricingSummary(
                        region=region,
                        availability_zone=availability_zone,
                        partition=partition,
                        priced_instance_count=priced_count,
                        configured_instance_count=configured_count,
                        price_coverage_percent=coverage,
                        min_hourly_spot_price=min(prices) if prices else None,
                        median_hourly_spot_price=(round(median(prices), 8) if prices else None),
                        harmonic_mean_hourly_spot_price=(
                            round(harmonic_mean(prices), 8) if prices else None
                        ),
                        max_hourly_spot_price=max(prices) if prices else None,
                        spread_hourly_spot_price=(
                            round(max(prices) - min(prices), 8) if prices else None
                        ),
                        spot_placement_target_capacity_vcpus=target_capacity_vcpus,
                        spot_placement_score=placement_scores.get(key),
                    )
                )
    return summaries


def collect_pricing_snapshot(
    *,
    regions: Optional[Sequence[str]] = None,
    partitions: Optional[Sequence[str]] = None,
    cluster_config_path: Optional[str] = None,
    profile: Optional[str] = None,
    target_capacity_vcpus: Optional[int] = None,
    captured_at: Optional[str] = None,
    session_factory: Optional[Callable[[Optional[str]], Any]] = None,
) -> PricingSnapshot:
    """Collect current per-AZ Spot prices for all requested partition instance types."""
    if target_capacity_vcpus is not None and target_capacity_vcpus < 1:
        raise ValueError("target_capacity_vcpus must be at least 1")
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
    placement_scores: Dict[tuple[str, str, str], int] = {}
    region_zones: Dict[str, List[str]] = {}
    timestamp = captured_at or _now_iso()

    for region in selected_regions:
        ec2_client = session.client("ec2", region_name=region)
        zones, zone_id_to_name = _get_available_zone_metadata(ec2_client)
        region_zones[region] = zones
        vcpu_counts = _get_vcpu_counts(ec2_client, all_instance_types)

        if target_capacity_vcpus is not None:
            placement_scores.update(
                _get_spot_placement_scores(
                    ec2_client,
                    region=region,
                    partition_instance_types=partition_instances,
                    target_capacity_vcpus=target_capacity_vcpus,
                    zone_id_to_name=zone_id_to_name,
                )
            )

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
    summaries = _build_partition_zone_summaries(
        regions=selected_regions,
        region_zones=region_zones,
        partitions=selected_partitions,
        partition_instance_types=partition_instances,
        points=snapshot_points,
        target_capacity_vcpus=target_capacity_vcpus,
        placement_scores=placement_scores,
    )
    return PricingSnapshot(
        captured_at=timestamp,
        cluster_config_path=str(resolved_config_path),
        regions=selected_regions,
        partitions=selected_partitions,
        target_capacity_vcpus=target_capacity_vcpus,
        summaries=summaries,
        points=snapshot_points,
    )
