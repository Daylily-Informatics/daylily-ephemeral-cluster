"""One bounded, non-secret public cluster-inspection receipt."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping
from urllib.parse import urlparse

import requests
import yaml

from daylily_ec import versioning


CLUSTER_INSPECTION_SCHEMA = "dyec.cluster.inspect.v1"
_MAX_TAGS = 64
_MAX_ASSOCIATIONS = 64
_MAX_TASKS = 64
_MAX_CONFIGURATION_BYTES = 4 * 1024 * 1024


class ClusterInspectionError(RuntimeError):
    """Raised when the exact primary cluster identity cannot be inspected."""


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_string(value: Any, *, maximum: int = 256) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > maximum or any(character in text for character in "\r\n\x00"):
        return None
    return text


def _safe_tags(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value[:_MAX_TAGS]:
        if not isinstance(item, Mapping):
            continue
        key = _safe_string(item.get("key") or item.get("Key"), maximum=128)
        tag_value = _safe_string(item.get("value") or item.get("Value"), maximum=256)
        if key is None or tag_value is None:
            continue
        lowered = key.lower()
        if any(token in lowered for token in ("secret", "token", "password", "credential")):
            continue
        rows.append({"key": key, "value": tag_value})
    return sorted(rows, key=lambda item: (item["key"], item["value"]))


def _sanitized_config(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = _safe_string(raw_key, maximum=128)
            if key is None:
                continue
            lowered = key.lower()
            if any(token in lowered for token in ("secret", "token", "password", "endpoint", "presigned", "url")):
                continue
            result[key] = _sanitized_config(raw_value)
        return result
    if isinstance(value, list):
        return [_sanitized_config(item) for item in value[:64]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return None


def _configuration_section(details: Mapping[str, Any]) -> dict[str, Any]:
    configuration = details.get("clusterConfiguration")
    if not isinstance(configuration, Mapping):
        return {"complete": False, "error_code": "cluster_configuration_reference_unavailable"}
    raw_url = str(configuration.get("url") or "").strip()
    parsed_url = urlparse(raw_url)
    hostname = str(parsed_url.hostname or "").lower()
    if parsed_url.scheme != "https" or not hostname.endswith(".amazonaws.com"):
        return {"complete": False, "error_code": "cluster_configuration_reference_invalid"}
    try:
        response = requests.get(raw_url, timeout=30, allow_redirects=False)
        response.raise_for_status()
    except requests.RequestException:
        return {"complete": False, "error_code": "cluster_configuration_download_failed"}
    content = bytes(response.content)
    if not content or len(content) > _MAX_CONFIGURATION_BYTES:
        return {"complete": False, "error_code": "cluster_configuration_size_invalid"}
    try:
        decoded = yaml.safe_load(content)
    except yaml.YAMLError:
        return {"complete": False, "error_code": "cluster_configuration_yaml_invalid"}
    if not isinstance(decoded, Mapping):
        return {"complete": False, "error_code": "cluster_configuration_shape_invalid"}
    sanitized = _sanitized_config(decoded)
    sanitized_yaml = yaml.safe_dump(
        sanitized,
        sort_keys=False,
        default_flow_style=False,
    )
    return {
        "complete": True,
        "data": {
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "configuration": sanitized,
            "sanitized_yaml": sanitized_yaml,
        },
    }


def _provider_section(func) -> dict[str, Any]:
    try:
        payload = func()
    except Exception:  # noqa: BLE001 - raw provider text is intentionally excluded
        return {"complete": False, "error_code": "provider_data_unavailable"}
    return {"complete": True, "data": payload}


def _headnode_section(details: Mapping[str, Any], ec2_client: Any) -> dict[str, Any]:
    head_node = details.get("headNode") if isinstance(details.get("headNode"), Mapping) else {}
    instance_id = _safe_string(head_node.get("instanceId"))
    if instance_id is None:
        return {"complete": False, "error_code": "headnode_instance_id_unavailable"}

    def fetch() -> dict[str, Any]:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        reservations = response.get("Reservations", [])
        instances = [
            instance
            for reservation in reservations if isinstance(reservation, Mapping)
            for instance in reservation.get("Instances", [])
            if isinstance(instance, Mapping)
        ]
        if len(instances) != 1:
            raise ClusterInspectionError("headnode inventory is ambiguous")
        instance = instances[0]
        placement = instance.get("Placement") if isinstance(instance.get("Placement"), Mapping) else {}
        return {
            "instance_id": instance_id,
            "instance_type": _safe_string(instance.get("InstanceType")),
            "state": _safe_string((instance.get("State") or {}).get("Name")) if isinstance(instance.get("State"), Mapping) else None,
            "vpc_id": _safe_string(instance.get("VpcId")),
            "subnet_id": _safe_string(instance.get("SubnetId")),
            "availability_zone": _safe_string(placement.get("AvailabilityZone")),
            "tags": _safe_tags(instance.get("Tags")),
        }

    return _provider_section(fetch)


def _fsx_section(cluster_name: str, cloudformation_client: Any, fsx_client: Any) -> dict[str, Any]:
    def fetch() -> dict[str, Any]:
        resources = cloudformation_client.describe_stack_resources(StackName=cluster_name).get(
            "StackResources", []
        )
        ids = [
            _safe_string(item.get("PhysicalResourceId"))
            for item in resources
            if isinstance(item, Mapping) and item.get("ResourceType") == "AWS::FSx::FileSystem"
        ]
        ids = [item for item in ids if item]
        if len(ids) != 1:
            raise ClusterInspectionError("cluster FSx identity is unavailable or ambiguous")
        rows = fsx_client.describe_file_systems(FileSystemIds=ids).get("FileSystems", [])
        if len(rows) != 1 or not isinstance(rows[0], Mapping):
            raise ClusterInspectionError("cluster FSx lifecycle is unavailable")
        filesystem = rows[0]
        lustre = (
            filesystem.get("LustreConfiguration")
            if isinstance(filesystem.get("LustreConfiguration"), Mapping)
            else {}
        )
        return {
            "file_system_id": ids[0],
            "lifecycle": _safe_string(filesystem.get("Lifecycle")),
            "storage_capacity": filesystem.get("StorageCapacity"),
            "vpc_id": _safe_string(filesystem.get("VpcId")),
            "subnet_ids": [
                value
                for value in (_safe_string(item) for item in filesystem.get("SubnetIds", []))
                if value is not None
            ],
            "storage_type": _safe_string(filesystem.get("StorageType")),
            "deployment_type": _safe_string(lustre.get("DeploymentType")),
            "mount_name": _safe_string(lustre.get("MountName")),
            "per_unit_storage_throughput": lustre.get("PerUnitStorageThroughput"),
        }

    return _provider_section(fetch)


def _dra_section(fsx_section: Mapping[str, Any], fsx_client: Any) -> dict[str, Any]:
    if fsx_section.get("complete") is not True:
        return {"complete": False, "error_code": "fsx_identity_unavailable"}
    fsx_data = fsx_section.get("data")
    if not isinstance(fsx_data, Mapping) or not isinstance(fsx_data.get("file_system_id"), str):
        return {"complete": False, "error_code": "fsx_identity_unavailable"}
    fsx_id = fsx_data["file_system_id"]

    def fetch() -> dict[str, Any]:
        associations = fsx_client.describe_data_repository_associations(
            Filters=[{"Name": "file-system-id", "Values": [fsx_id]}],
            MaxResults=_MAX_ASSOCIATIONS,
        )
        task_response = fsx_client.describe_data_repository_tasks(
            Filters=[{"Name": "file-system-id", "Values": [fsx_id]}],
            MaxResults=_MAX_TASKS,
        )
        association_rows = associations.get("Associations", [])
        task_rows = task_response.get("DataRepositoryTasks", [])
        return {
            "associations": [
                {
                    "association_id": _safe_string(row.get("AssociationId")),
                    "lifecycle": _safe_string(row.get("Lifecycle")),
                    "file_system_path": _safe_string(row.get("FileSystemPath")),
                    "repository_path": _safe_string(row.get("DataRepositoryPath")),
                }
                for row in association_rows[:_MAX_ASSOCIATIONS]
                if isinstance(row, Mapping)
            ],
            "tasks": [
                {
                    "task_id": _safe_string(row.get("TaskId")),
                    "lifecycle": _safe_string(row.get("Lifecycle")),
                    "type": _safe_string(row.get("Type")),
                }
                for row in task_rows[:_MAX_TASKS]
                if isinstance(row, Mapping)
            ],
            "associations_truncated": bool(associations.get("NextToken")),
            "tasks_truncated": bool(task_response.get("NextToken")),
        }

    return _provider_section(fetch)


def _fsx_io_section(fsx_section: Mapping[str, Any], cloudwatch_client: Any) -> dict[str, Any]:
    if fsx_section.get("complete") is not True:
        return {"complete": False, "error_code": "fsx_identity_unavailable"}
    fsx_data = fsx_section.get("data")
    if not isinstance(fsx_data, Mapping) or not isinstance(fsx_data.get("file_system_id"), str):
        return {"complete": False, "error_code": "fsx_identity_unavailable"}
    fsx_id = fsx_data["file_system_id"]

    def fetch() -> dict[str, Any]:
        end = datetime.now(UTC)
        start = end - timedelta(minutes=15)
        metrics: dict[str, float | None] = {}
        for metric_name in ("DataReadBytes", "DataWriteBytes"):
            response = cloudwatch_client.get_metric_statistics(
                Namespace="AWS/FSx",
                MetricName=metric_name,
                Dimensions=[{"Name": "FileSystemId", "Value": fsx_id}],
                StartTime=start,
                EndTime=end,
                Period=300,
                Statistics=["Sum"],
            )
            points = response.get("Datapoints", [])
            latest = max(points, key=lambda item: item.get("Timestamp", start), default=None)
            metrics[metric_name] = float(latest["Sum"]) if isinstance(latest, Mapping) and "Sum" in latest else None
        missing_metrics = sorted(name for name, value in metrics.items() if value is None)
        return {
            "window_minutes": 15,
            "metrics": metrics,
            "health_status": "HEALTHY" if not missing_metrics else "UNKNOWN",
            "reason_codes": (
                [] if not missing_metrics else ["required_metric_datapoint_missing"]
            ),
            "missing_metrics": missing_metrics,
        }

    return _provider_section(fetch)


def _cost_section(
    cluster_name: str,
    cost_explorer_client: Any,
    ec2_client: Any,
    headnode_section: Mapping[str, Any],
    fsx_section: Mapping[str, Any],
) -> dict[str, Any]:
    def fetch() -> dict[str, Any]:
        end = datetime.now(UTC).date()
        start = end - timedelta(days=1)
        response = cost_explorer_client.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            Filter={"Tags": {"Key": "parallelcluster:cluster-name", "Values": [cluster_name]}},
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        service_totals: list[dict[str, str]] = []
        for result in response.get("ResultsByTime", []):
            for group in result.get("Groups", []) if isinstance(result, Mapping) else []:
                keys = group.get("Keys", []) if isinstance(group, Mapping) else []
                amount = ((group.get("Metrics") or {}).get("UnblendedCost") or {}).get("Amount") if isinstance(group, Mapping) else None
                if not keys or amount is None:
                    continue
                service = _safe_string(keys[0])
                unit = ((group.get("Metrics") or {}).get("UnblendedCost") or {}).get("Unit")
                if service is not None:
                    service_totals.append(
                        {"service": service, "amount": str(amount), "unit": str(unit or "USD")}
                    )
        service_totals.sort(key=lambda row: row["service"])
        headnode_data = (
            headnode_section.get("data")
            if headnode_section.get("complete") is True
            and isinstance(headnode_section.get("data"), Mapping)
            else {}
        )
        headnode_instance_id = _safe_string(headnode_data.get("instance_id"))
        volumes: list[dict[str, Any]] = []
        if headnode_instance_id is not None:
            response = ec2_client.describe_volumes(
                Filters=[
                    {"Name": "attachment.instance-id", "Values": [headnode_instance_id]}
                ]
            )
            for row in response.get("Volumes", [])[:64]:
                if not isinstance(row, Mapping):
                    continue
                volumes.append(
                    {
                        "volume_id": _safe_string(row.get("VolumeId")),
                        "volume_type": _safe_string(row.get("VolumeType")),
                        "size_gib": row.get("Size"),
                    }
                )
        fsx_data = (
            fsx_section.get("data")
            if fsx_section.get("complete") is True
            and isinstance(fsx_section.get("data"), Mapping)
            else {}
        )
        return {
            "currency": "USD",
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "allocation_status": "service_totals_only",
            "allocation_note": (
                "Cost Explorer cannot separate headnode, compute, and EBS from this tag receipt; "
                "use dyec pricing spot-logs for versioned all-node intervals."
            ),
            "components": {
                "headnode": {
                    "instance_id": headnode_instance_id,
                    "instance_type": _safe_string(headnode_data.get("instance_type")),
                    "cost_usd": None,
                    "status": "requires_dyec_spot_log_interval",
                },
                "compute": {
                    "cost_usd": None,
                    "status": "requires_dyec_spot_log_intervals",
                },
                "ebs": {
                    "volumes": volumes,
                    "total_gib": sum(
                        int(row["size_gib"])
                        for row in volumes
                        if isinstance(row.get("size_gib"), int)
                    ),
                    "cost_usd": None,
                    "status": "cost_explorer_not_resource_allocated",
                },
                "fsx": {
                    "file_system_id": _safe_string(fsx_data.get("file_system_id")),
                    "storage_capacity_gib": fsx_data.get("storage_capacity"),
                    "deployment_type": _safe_string(fsx_data.get("deployment_type")),
                    "cost_usd": None,
                    "status": "cost_explorer_not_resource_allocated",
                },
            },
            "service_totals": service_totals,
        }

    try:
        data = fetch()
    except Exception:  # noqa: BLE001 - raw provider text is intentionally excluded
        return {"complete": False, "error_code": "provider_data_unavailable"}
    # Cost Explorer's cluster tag view is useful inventory evidence, but it cannot
    # truthfully allocate EBS and FSx charges to exact resources. Keep the known
    # service totals and explicit component inventories while marking the section
    # incomplete rather than turning unavailable values into zeroes.
    return {
        "complete": False,
        "error_code": "resource_cost_allocation_unavailable",
        "data": data,
    }


def build_cluster_inspection(
    *,
    cluster_name: str,
    region: str,
    profile: str,
    details: Mapping[str, Any],
    ec2_client: Any,
    cloudformation_client: Any,
    fsx_client: Any,
    cloudwatch_client: Any,
    cost_explorer_client: Any,
    accounting: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect typed bounded sections without emitting provider URLs or raw errors."""

    safe_cluster = _safe_string(cluster_name)
    safe_region = _safe_string(region)
    safe_profile = _safe_string(profile)
    if safe_cluster is None or safe_region is None or safe_profile is None:
        raise ClusterInspectionError("cluster identity requires exact non-empty cluster, region, and profile")
    described_cluster = _safe_string(details.get("clusterName"))
    if described_cluster is not None and described_cluster != safe_cluster:
        raise ClusterInspectionError("provider returned a different cluster identity")
    described_region = _safe_string(details.get("region"))
    if described_region is not None and described_region != safe_region:
        raise ClusterInspectionError("provider returned a different cluster region")
    configuration = _configuration_section(details)
    identity = {
        "cluster_name": safe_cluster,
        "cluster_state": _safe_string(details.get("clusterStatus")),
        "created_at": _safe_string(details.get("creationTime")),
        "updated_at": _safe_string(details.get("lastUpdatedTime")),
        "compute_fleet_state": _safe_string(details.get("computeFleetStatus")),
        "scheduler_type": _safe_string(
            (details.get("scheduler") or {}).get("type")
            if isinstance(details.get("scheduler"), Mapping)
            else None
        ),
        "parallelcluster_version": _safe_string(details.get("version")),
        "tags": _safe_tags(details.get("tags")),
    }
    headnode = _headnode_section(details, ec2_client)
    fsx = _fsx_section(safe_cluster, cloudformation_client, fsx_client)
    dra = _dra_section(fsx, fsx_client)
    fsx_io = _fsx_io_section(fsx, cloudwatch_client)
    costs = _cost_section(
        safe_cluster,
        cost_explorer_client,
        ec2_client,
        headnode,
        fsx,
    )
    accounting_complete = bool(
        accounting is not None and accounting.get("sacct_verified") is True
    )
    sections = {
        "identity": {"complete": True, "data": identity},
        "configuration": configuration,
        "headnode": headnode,
        "fsx": fsx,
        "data_repository": dra,
        "fsx_io": fsx_io,
        "cost": costs,
        "slurm_accounting": (
            {
                "complete": accounting_complete,
                "data": dict(accounting),
                **(
                    {}
                    if accounting_complete
                    else {"error_code": "bounded_sacct_verification_failed"}
                ),
            }
            if accounting is not None
            else {"complete": False, "error_code": "exact_accounting_topology_not_supplied"}
        ),
    }
    return {
        "schema_version": CLUSTER_INSPECTION_SCHEMA,
        "ok": True,
        "generated_at": _timestamp(),
        "dyec_version": versioning.get_version(),
        "profile": safe_profile,
        "region": safe_region,
        "cluster": safe_cluster,
        "sections": sections,
        "complete": all(section.get("complete") is True for section in sections.values()),
    }


__all__ = ["CLUSTER_INSPECTION_SCHEMA", "ClusterInspectionError", "build_cluster_inspection"]
