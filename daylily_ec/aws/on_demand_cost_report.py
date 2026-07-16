"""On-demand, cache-first AWS cost, resource, lifecycle, and utilization data.

The report deliberately separates generic discovery from optional enrichment.
Cost Explorer, Resource Explorer, the Resource Groups Tagging API, and
CloudFormation define the generic record set.  Type-specific lifecycle and
CloudWatch metric adapters can add evidence, but an unknown resource type is a
valid record and never a fatal dispatch error.
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time as datetime_time, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional, Sequence

import boto3

from daylily_ec.aws.api_call_audit import (
    MAX_AUDIT_PAID_CALLS_AT_OBSERVED_RATE,
    MAX_AUDIT_PAID_COST_USD,
    OBSERVED_COST_EXPLORER_REQUEST_USD,
    ApiCallStats,
    AwsRequest,
    CachedAwsReader,
    ExactRequestCache,
    ServiceRateLimiter,
)


REPORT_SCHEMA_VERSION = 1
HISTORY_SCHEMA_VERSION = 1
DEFAULT_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
DEFAULT_CE_MIN_INTERVAL_SECONDS = 1.0
DEFAULT_OTHER_MIN_INTERVAL_SECONDS = 0.2
DEFAULT_PCLUSTER_MIN_INTERVAL_SECONDS = 0.5
DEFAULT_UTILIZATION_LIMIT = 50
DEFAULT_UTILIZATION_PERIOD_SECONDS = 3600
DEFAULT_BILLING_REGION = "us-east-1"

STACK_FAILURE_STATES = {
    "CREATE_FAILED",
    "DELETE_FAILED",
    "IMPORT_ROLLBACK_FAILED",
    "ROLLBACK_FAILED",
    "UPDATE_FAILED",
    "UPDATE_ROLLBACK_FAILED",
}
STACK_RECOVERED_FAILURE_STATES = {
    "ROLLBACK_COMPLETE",
    "UPDATE_ROLLBACK_COMPLETE",
}


class OnDemandCostReportError(RuntimeError):
    """The report could not satisfy its explicit safety or data contract."""


class HistoryContractError(OnDemandCostReportError):
    """The explicit cross-run history file is absent or invalid."""


@dataclass(frozen=True)
class OnDemandCostReportConfig:
    profile: str
    account_id: str
    start_date: date
    end_date: date
    resource_start_date: date
    control_region: str
    output_dir: Path
    cache_dir: Path
    history_path: Path
    initialize_history: bool = False
    cost_tag_keys: tuple[str, ...] = ()
    cluster_tag_keys: tuple[str, ...] = ()
    discover_cost_tag_keys: bool = True
    include_budgets: bool = True
    parallelcluster_executable: Optional[Path] = None
    parallelcluster_regions: tuple[str, ...] = ()
    utilization_limit: int = DEFAULT_UTILIZATION_LIMIT
    utilization_period_seconds: int = DEFAULT_UTILIZATION_PERIOD_SECONDS
    paid_call_budget: int = 50
    cache_max_age_seconds: float = DEFAULT_CACHE_MAX_AGE_SECONDS
    cache_only: bool = False
    refresh: bool = False
    ce_min_interval_seconds: float = DEFAULT_CE_MIN_INTERVAL_SECONDS
    other_min_interval_seconds: float = DEFAULT_OTHER_MIN_INTERVAL_SECONDS
    parallelcluster_min_interval_seconds: float = DEFAULT_PCLUSTER_MIN_INTERVAL_SECONDS

    def validate(self) -> None:
        if not self.profile.strip():
            raise ValueError("profile is required")
        if not re.fullmatch(r"\d{12}", self.account_id.strip()):
            raise ValueError("account_id must contain exactly 12 digits")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if not self.start_date <= self.resource_start_date < self.end_date:
            raise ValueError("resource_start_date must be inside the report window")
        if (self.end_date - self.resource_start_date).days > 14:
            raise ValueError("resource-level Cost Explorer window may not exceed 14 days")
        if not self.control_region.strip():
            raise ValueError("control_region is required")
        if self.paid_call_budget < 0:
            raise ValueError("paid_call_budget must be non-negative")
        if self.paid_call_budget > MAX_AUDIT_PAID_CALLS_AT_OBSERVED_RATE:
            raise ValueError(
                f"paid_call_budget may not exceed {MAX_AUDIT_PAID_CALLS_AT_OBSERVED_RATE}"
            )
        if self.cache_only and self.refresh:
            raise ValueError("cache_only and refresh are mutually exclusive")
        if self.cache_max_age_seconds < 0:
            raise ValueError("cache_max_age_seconds must be non-negative")
        if self.utilization_limit < 0:
            raise ValueError("utilization_limit must be non-negative")
        if self.utilization_period_seconds <= 0:
            raise ValueError("utilization_period_seconds must be positive")
        for label, value in (
            ("ce_min_interval_seconds", self.ce_min_interval_seconds),
            ("other_min_interval_seconds", self.other_min_interval_seconds),
            (
                "parallelcluster_min_interval_seconds",
                self.parallelcluster_min_interval_seconds,
            ),
        ):
            if value < 0:
                raise ValueError(f"{label} must be non-negative")
        for label, keys in (
            ("cost_tag_keys", self.cost_tag_keys),
            ("cluster_tag_keys", self.cluster_tag_keys),
        ):
            normalized_keys = tuple(key.strip() for key in keys)
            if any(not key for key in normalized_keys):
                raise ValueError(f"{label} may not contain blank values")
            if len(set(normalized_keys)) != len(normalized_keys):
                raise ValueError(f"{label} may not contain duplicates")
        normalized_regions = tuple(region.strip() for region in self.parallelcluster_regions)
        if any(not region for region in normalized_regions):
            raise ValueError("parallelcluster_regions may not contain blank values")
        if self.parallelcluster_executable is None and normalized_regions:
            raise ValueError(
                "parallelcluster_executable is required when parallelcluster_regions are set"
            )
        if self.parallelcluster_executable is not None and not normalized_regions:
            raise ValueError(
                "at least one parallelcluster_region is required with parallelcluster_executable"
            )


@dataclass(frozen=True)
class MetricSpec:
    namespace: str
    metric_name: str
    dimension_name: str
    statistic: str


UTILIZATION_SPECS: dict[str, tuple[MetricSpec, ...]] = {
    "AWS::EC2::Instance": (
        MetricSpec("AWS/EC2", "CPUUtilization", "InstanceId", "Average"),
    ),
    "AWS::EC2::Volume": (
        MetricSpec("AWS/EBS", "VolumeIdleTime", "VolumeId", "Sum"),
        MetricSpec("AWS/EBS", "VolumeReadOps", "VolumeId", "Sum"),
        MetricSpec("AWS/EBS", "VolumeWriteOps", "VolumeId", "Sum"),
    ),
    "AWS::EC2::NatGateway": tuple(
        MetricSpec("AWS/NATGateway", metric, "NatGatewayId", "Sum")
        for metric in (
            "BytesInFromDestination",
            "BytesInFromSource",
            "BytesOutToDestination",
            "BytesOutToSource",
        )
    ),
    "AWS::FSx::FileSystem": (
        MetricSpec("AWS/FSx", "DataReadBytes", "FileSystemId", "Sum"),
        MetricSpec("AWS/FSx", "DataWriteBytes", "FileSystemId", "Sum"),
        MetricSpec("AWS/FSx", "MetadataOperations", "FileSystemId", "Sum"),
        MetricSpec("AWS/FSx", "FreeDataStorageCapacity", "FileSystemId", "Average"),
    ),
    "AWS::RDS::DBInstance": (
        MetricSpec("AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", "Average"),
        MetricSpec("AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", "Average"),
        MetricSpec("AWS/RDS", "FreeableMemory", "DBInstanceIdentifier", "Average"),
    ),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _atomic_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field_name in row:
            if field_name not in fields:
                fields.append(field_name)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        if fields:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    os.replace(temporary, path)


def _paginate(
    reader: CachedAwsReader,
    *,
    service: str,
    region: str,
    operation: str,
    parameters: Mapping[str, Any],
    request_token: str,
    response_token: str,
    paid: bool = False,
) -> Iterable[dict[str, Any]]:
    token = ""
    seen_tokens: set[str] = set()
    while True:
        request_parameters = dict(parameters)
        if token:
            request_parameters[request_token] = token
        payload = reader.call(
            service=service,
            region=region,
            operation=operation,
            parameters=request_parameters,
            paid=paid,
        )
        yield payload
        next_token = str(payload.get(response_token) or "")
        if not next_token:
            return
        if next_token in seen_tokens:
            raise OnDemandCostReportError(
                f"pagination token cycle in {service}.{operation}"
            )
        seen_tokens.add(next_token)
        token = next_token


def _metric_amount(group: Mapping[str, Any], metric: str = "UnblendedCost") -> float:
    metrics = group.get("Metrics") or {}
    value = metrics.get(metric) or {}
    return float(value.get("Amount") or 0.0)


def _flatten_cost_pages(
    pages: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page_number, payload in enumerate(pages, 1):
        for period in payload.get("ResultsByTime", []):
            if not isinstance(period, Mapping):
                continue
            time_period = period.get("TimePeriod") or {}
            for group in period.get("Groups", []):
                if not isinstance(group, Mapping):
                    continue
                keys = list(group.get("Keys") or [])
                row: dict[str, Any] = {
                    "start": str(time_period.get("Start") or ""),
                    "end_exclusive": str(time_period.get("End") or ""),
                    "cost_usd": _metric_amount(group),
                    "estimated": bool(period.get("Estimated")),
                    "source_page": page_number,
                }
                for index, field_name in enumerate(fields):
                    row[field_name] = str(keys[index]) if index < len(keys) else ""
                rows.append(row)
    return rows


def _normalize_tag_group_value(raw: str, tag_key: str) -> str:
    prefix = f"{tag_key}$"
    return raw[len(prefix) :] if raw.startswith(prefix) else raw


def _arn_parts(arn: str) -> tuple[str, str, str, str]:
    parts = arn.split(":", 5)
    if len(parts) != 6 or parts[0] != "arn":
        return "", "", "", ""
    return parts[2], parts[3], parts[4], parts[5]


def _canonical_resource_id(value: str) -> str:
    text = str(value or "")
    if text.startswith("arn:"):
        resource = _arn_parts(text)[3]
        return re.split(r"[/ :]", resource)[-1]
    return re.split(r"[/ :]", text)[-1]


def _type_key(row: Mapping[str, Any]) -> str:
    return str(
        row.get("cfn_resource_type")
        or row.get("resource_type")
        or f"aws::{row.get('service') or 'unknown'}::unknown"
    )


def _stack_lifecycle(status: str) -> str:
    if status == "DELETE_COMPLETE":
        return "deleted"
    if status == "DELETE_IN_PROGRESS":
        return "deleting"
    if status in STACK_FAILURE_STATES or status.endswith("_FAILED"):
        return "exception"
    if status in STACK_RECOVERED_FAILURE_STATES:
        return "exception_recovered"
    if status.endswith("_IN_PROGRESS"):
        return "provisioning_or_updating"
    return "active"


def _provider_lifecycle(state: str, *, exists: bool = True) -> str:
    normalized = state.strip().lower().replace(" ", "_")
    if not exists:
        return "unresolved"
    if normalized in {"stopped", "stopping"}:
        return "stopped"
    if normalized in {"terminated", "deleted", "delete_complete"}:
        return "deleted"
    if normalized in {"shutting-down", "shutting_down", "deleting", "delete_in_progress"}:
        return "deleting"
    if normalized.endswith("_failed") or normalized == "failed":
        return "exception"
    if normalized.endswith("_in_progress") or normalized in {"pending", "creating", "updating"}:
        return "provisioning_or_updating"
    return "active"


def _tags_map(tags: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in tags or []:
        if not isinstance(item, Mapping):
            continue
        key = item.get("Key") if "Key" in item else item.get("key")
        value = item.get("Value") if "Value" in item else item.get("value")
        if key:
            result[str(key)] = str(value or "")
    return result


def _resource_explorer_tags(properties: Any) -> dict[str, str]:
    for item in properties or []:
        if not isinstance(item, Mapping) or str(item.get("Name") or "").lower() != "tags":
            continue
        data = item.get("Data")
        if isinstance(data, Mapping):
            if isinstance(data.get("Tags"), list):
                return _tags_map(data.get("Tags"))
            return {str(key): str(value or "") for key, value in data.items()}
        if isinstance(data, list):
            return _tags_map(data)
    return {}


def _resource_key(
    *,
    arn: str,
    region: str,
    type_key: str,
    resource_id: str,
) -> str:
    if arn:
        return arn
    return f"aws-resource://{region}/{type_key}/{resource_id}"


@dataclass
class ResourceSet:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    identity_index: dict[tuple[str, str, str], str] = field(default_factory=dict)

    def add(
        self,
        *,
        source: str,
        arn: str = "",
        region: str = "",
        service: str = "",
        resource_type: str = "",
        cfn_resource_type: str = "",
        resource_id: str = "",
        current: bool = True,
        tags: Optional[Mapping[str, str]] = None,
        provider_state: str = "",
        owner_stack: str = "",
        lifecycle_status: str = "",
        lifecycle_evidence: str = "",
        properties: Any = None,
    ) -> dict[str, Any]:
        rid = resource_id or _canonical_resource_id(arn)
        type_name = cfn_resource_type or resource_type or f"aws::{service or 'unknown'}::unknown"
        identity = (region, type_name, rid)
        key = self.identity_index.get(identity) if rid else None
        if not key:
            key = _resource_key(
                arn=arn,
                region=region or "global",
                type_key=type_name,
                resource_id=rid or "unknown",
            )
        row = self.records.setdefault(
            key,
            {
                "resource_key": key,
                "arn": arn,
                "region": region or "global",
                "service": service,
                "resource_type": resource_type,
                "cfn_resource_type": cfn_resource_type,
                "resource_id": rid,
                "current": bool(current),
                "sources": [],
                "tags": {},
                "tag_state": "unknown",
                "provider_state": provider_state,
                "owner_stack": owner_stack,
                "lifecycle_status": lifecycle_status or _provider_lifecycle(provider_state),
                "lifecycle_evidence": lifecycle_evidence or "resource exists in current discovery",
                "properties": properties or [],
                "cost_usd": 0.0,
                "presence": "current" if current else "historical",
                "utilization_status": "not_selected",
            },
        )
        if source not in row["sources"]:
            row["sources"].append(source)
        row["current"] = bool(row["current"] or current)
        for field_name, value in (
            ("arn", arn),
            ("region", region),
            ("service", service),
            ("resource_type", resource_type),
            ("cfn_resource_type", cfn_resource_type),
            ("resource_id", rid),
            ("provider_state", provider_state),
            ("owner_stack", owner_stack),
        ):
            if value and not row.get(field_name):
                row[field_name] = value
        if properties and not row.get("properties"):
            row["properties"] = properties
        if tags:
            row["tags"].update({str(k): str(v) for k, v in tags.items()})
            row["tag_state"] = "tagged"
        if lifecycle_status:
            row["lifecycle_status"] = lifecycle_status
            row["lifecycle_evidence"] = lifecycle_evidence
        if rid:
            self.identity_index[identity] = key
        return row


def _serializable_resource(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "sources": ";".join(sorted(str(item) for item in row.get("sources", []))),
        "tags": json.dumps(row.get("tags") or {}, sort_keys=True, separators=(",", ":")),
        "properties": json.dumps(row.get("properties") or [], sort_keys=True, default=str),
    }


CommandRunner = Callable[[Sequence[str], Mapping[str, str]], subprocess.CompletedProcess[str]]


def _run_json_command(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        env=dict(environment),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class CachedParallelClusterReader:
    """Exact-request cached reader for the read-only ParallelCluster CLI."""

    def __init__(
        self,
        *,
        executable: Path,
        profile: str,
        account_id: str,
        cache: ExactRequestCache,
        limiter: ServiceRateLimiter,
        cache_only: bool,
        refresh: bool,
        command_runner: CommandRunner = _run_json_command,
    ) -> None:
        self.executable = Path(executable).expanduser().resolve()
        if not self.executable.is_file():
            raise OnDemandCostReportError(
                f"ParallelCluster executable does not exist: {self.executable}"
            )
        self.profile = profile
        self.account_id = account_id
        self.cache = cache
        self.limiter = limiter
        self.cache_only = cache_only
        self.refresh = refresh
        self.command_runner = command_runner
        self.stats = ApiCallStats()

    def call(
        self,
        *,
        region: str,
        operation: str,
        parameters: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        normalized = dict(parameters or {})
        request = AwsRequest(
            profile=self.profile,
            account_id=self.account_id,
            service="parallelcluster-cli",
            region=region,
            operation=operation,
            parameters=normalized,
        )
        lookup = self.cache.lookup(request)
        self.stats.cache_paths.add(str(lookup.path))
        if not self.refresh and lookup.response is not None:
            self.stats.cache_hits += 1
            self.stats.cache_hits_by_service_operation[("parallelcluster-cli", operation)] += 1
            return dict(lookup.response)
        self.stats.cache_misses += 1
        if lookup.status == "stale":
            self.stats.cache_stale += 1
        if self.cache_only:
            raise OnDemandCostReportError(
                f"Cache-only ParallelCluster request is {lookup.status}: {lookup.path}"
            )
        command = [str(self.executable), operation.replace("_", "-")]
        if operation == "list_clusters":
            token = str(normalized.get("next_token") or "")
            if token:
                command.extend(["--next-token", token])
        elif operation == "describe_compute_fleet":
            cluster_name = str(normalized.get("cluster_name") or "")
            if not cluster_name:
                raise OnDemandCostReportError(
                    "describe_compute_fleet requires cluster_name"
                )
            command.extend(["--cluster-name", cluster_name])
        else:
            raise OnDemandCostReportError(
                f"unsupported read-only ParallelCluster operation: {operation}"
            )
        command.extend(["--region", region])
        self.limiter.wait("parallelcluster-cli")
        environment = os.environ.copy()
        environment["AWS_PROFILE"] = self.profile
        environment["AWS_DEFAULT_REGION"] = region
        completed = self.command_runner(command, environment)
        if completed.returncode != 0:
            raise OnDemandCostReportError(
                f"ParallelCluster {operation} failed in {region}: "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )
        try:
            response = json.loads(completed.stdout) if completed.stdout.strip() else {}
        except json.JSONDecodeError as exc:
            raise OnDemandCostReportError(
                f"ParallelCluster {operation} returned non-JSON output in {region}"
            ) from exc
        if not isinstance(response, MutableMapping):
            raise OnDemandCostReportError(
                f"ParallelCluster {operation} returned a non-object response"
            )
        self.stats.live_calls += 1
        self.stats.calls_by_service_operation[("parallelcluster-cli", operation)] += 1
        self.cache.store(request, response)
        return dict(response)


def _collect_parallelclusters(
    reader: CachedParallelClusterReader,
    regions: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for region in regions:
        token = ""
        seen_tokens: set[str] = set()
        while True:
            payload = reader.call(
                region=region,
                operation="list_clusters",
                parameters={"next_token": token} if token else {},
            )
            for cluster in payload.get("clusters", []):
                if not isinstance(cluster, Mapping):
                    continue
                item = dict(cluster)
                status = str(item.get("clusterStatus") or "")
                item.update(
                    {
                        "region": region,
                        "cluster": str(item.get("clusterName") or ""),
                        "provider_status": status,
                        "compute_fleet_status": "not_queried",
                        "lifecycle_status": _stack_lifecycle(status),
                        "classification_evidence": "ParallelCluster list-clusters",
                    }
                )
                if status in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}:
                    fleet = reader.call(
                        region=region,
                        operation="describe_compute_fleet",
                        parameters={"cluster_name": item["cluster"]},
                    )
                    fleet_status = str(fleet.get("status") or "")
                    item["compute_fleet_status"] = fleet_status
                    if fleet_status in {"STOPPED", "STOPPING"}:
                        item["lifecycle_status"] = "stopped"
                    item["classification_evidence"] = (
                        "ParallelCluster list-clusters and describe-compute-fleet"
                    )
                rows.append(item)
            next_token = str(payload.get("nextToken") or "")
            if not next_token:
                break
            if next_token in seen_tokens:
                raise OnDemandCostReportError(
                    f"ParallelCluster pagination token cycle in {region}"
                )
            seen_tokens.add(next_token)
            token = next_token
    return rows


def _spend_fields(value: Any, prefix: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {f"{prefix}_amount": None, f"{prefix}_unit": ""}
    return {
        f"{prefix}_amount": float(value.get("Amount") or 0.0),
        f"{prefix}_unit": str(value.get("Unit") or ""),
    }


def _budget_expression_associations(
    expression: Any,
    *,
    budget_name: str,
    path: str = "filter_expression",
) -> list[dict[str, Any]]:
    if not isinstance(expression, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for operator in ("And", "Or"):
        children = expression.get(operator)
        if isinstance(children, list):
            for index, child in enumerate(children):
                rows.extend(
                    _budget_expression_associations(
                        child,
                        budget_name=budget_name,
                        path=f"{path}.{operator.lower()}[{index}]",
                    )
                )
    if isinstance(expression.get("Not"), Mapping):
        rows.extend(
            _budget_expression_associations(
                expression["Not"],
                budget_name=budget_name,
                path=f"{path}.not",
            )
        )
    for kind in ("Dimensions", "Tags", "CostCategories"):
        node = expression.get(kind)
        if not isinstance(node, Mapping):
            continue
        key = str(node.get("Key") or "")
        values = node.get("Values") or []
        if not isinstance(values, list):
            values = [values]
        match_options = node.get("MatchOptions") or []
        rows.append(
            {
                "budget_name": budget_name,
                "association_source": "filter_expression",
                "association_type": kind.lower(),
                "key": key,
                "values": ";".join(str(value) for value in values),
                "match_options": ";".join(str(value) for value in match_options),
                "expression_path": path,
            }
        )
    return rows


def _legacy_budget_associations(
    filters: Any,
    *,
    budget_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(filters, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for key, raw_values in sorted(filters.items(), key=lambda item: str(item[0])):
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        rows.append(
            {
                "budget_name": budget_name,
                "association_source": "legacy_cost_filters",
                "association_type": "cost_filter",
                "key": str(key),
                "values": ";".join(str(value) for value in values),
                "match_options": "",
                "expression_path": "cost_filters",
            }
        )
    return rows


def _budget_cost_tag_keys(association_rows: Sequence[Mapping[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in association_rows:
        association_type = str(row.get("association_type") or "").lower()
        key = str(row.get("key") or "")
        if association_type == "tags" and key:
            keys.add(key)
        if association_type != "cost_filter" or key.lower() not in {
            "tagkeyvalue",
            "tag",
            "tags",
        }:
            continue
        for raw in str(row.get("values") or "").split(";"):
            normalized = raw.removeprefix("user:").removeprefix("aws:")
            if "$" in normalized:
                tag_key = normalized.split("$", 1)[0]
                if tag_key:
                    keys.add(tag_key)
    return keys


def _collect_budgets(
    reader: CachedAwsReader,
    *,
    account_id: str,
    region: str,
) -> dict[str, Any]:
    budget_objects: list[dict[str, Any]] = []
    for page in _paginate(
        reader,
        service="budgets",
        region=region,
        operation="describe_budgets",
        parameters={
            "AccountId": account_id,
            "ShowFilterExpression": True,
            "MaxResults": 1000,
        },
        request_token="NextToken",
        response_token="NextToken",
    ):
        budget_objects.extend(
            dict(item) for item in page.get("Budgets", []) if isinstance(item, Mapping)
        )

    budget_rows: list[dict[str, Any]] = []
    association_rows: list[dict[str, Any]] = []
    notification_rows: list[dict[str, Any]] = []
    subscriber_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    budget_tag_rows: list[dict[str, Any]] = []

    for budget in budget_objects:
        name = str(budget.get("BudgetName") or "")
        budget_arn = f"arn:aws:budgets::{account_id}:budget/{name}"
        calculated = budget.get("CalculatedSpend") or {}
        budget_limit = budget.get("BudgetLimit") or {}
        row = {
            "budget_name": name,
            "budget_arn": budget_arn,
            "budget_type": str(budget.get("BudgetType") or ""),
            "time_unit": str(budget.get("TimeUnit") or ""),
            "last_updated_at": str(budget.get("LastUpdatedTime") or ""),
            "metrics": ";".join(str(item) for item in budget.get("Metrics") or []),
            "billing_view_arn": str(budget.get("BillingViewArn") or ""),
            "health_status": str((budget.get("HealthStatus") or {}).get("Status") or ""),
            **_spend_fields(budget_limit, "limit"),
            **_spend_fields(calculated.get("ActualSpend"), "actual"),
            **_spend_fields(calculated.get("ForecastedSpend"), "forecast"),
            "cost_filters_json": json.dumps(
                _jsonable(budget.get("CostFilters") or {}),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "filter_expression_json": json.dumps(
                _jsonable(budget.get("FilterExpression") or {}),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "cost_types_json": json.dumps(
                _jsonable(budget.get("CostTypes") or {}),
                sort_keys=True,
                separators=(",", ":"),
            ),
        }
        budget_rows.append(row)
        association_rows.extend(
            _legacy_budget_associations(budget.get("CostFilters"), budget_name=name)
        )
        association_rows.extend(
            _budget_expression_associations(
                budget.get("FilterExpression"), budget_name=name
            )
        )

        notifications: list[dict[str, Any]] = []
        for page in _paginate(
            reader,
            service="budgets",
            region=region,
            operation="describe_notifications_for_budget",
            parameters={
                "AccountId": account_id,
                "BudgetName": name,
                "MaxResults": 100,
            },
            request_token="NextToken",
            response_token="NextToken",
        ):
            notifications.extend(
                dict(item)
                for item in page.get("Notifications", [])
                if isinstance(item, Mapping)
            )
        for index, notification in enumerate(notifications):
            notification_id = f"{name}:{index + 1}"
            notification_rows.append(
                {
                    "budget_name": name,
                    "notification_id": notification_id,
                    **{str(key): _jsonable(value) for key, value in notification.items()},
                }
            )
            for page in _paginate(
                reader,
                service="budgets",
                region=region,
                operation="describe_subscribers_for_notification",
                parameters={
                    "AccountId": account_id,
                    "BudgetName": name,
                    "Notification": notification,
                    "MaxResults": 100,
                },
                request_token="NextToken",
                response_token="NextToken",
            ):
                for subscriber in page.get("Subscribers", []):
                    if isinstance(subscriber, Mapping):
                        subscriber_rows.append(
                            {
                                "budget_name": name,
                                "notification_id": notification_id,
                                **{
                                    str(key): _jsonable(value)
                                    for key, value in subscriber.items()
                                },
                            }
                        )

        for page in _paginate(
            reader,
            service="budgets",
            region=region,
            operation="describe_budget_actions_for_budget",
            parameters={
                "AccountId": account_id,
                "BudgetName": name,
                "MaxResults": 100,
            },
            request_token="NextToken",
            response_token="NextToken",
        ):
            for action in page.get("Actions", []):
                if isinstance(action, Mapping):
                    action_rows.append(
                        {
                            "budget_name": name,
                            **{
                                str(key): json.dumps(_jsonable(value), sort_keys=True)
                                if isinstance(value, (Mapping, list))
                                else _jsonable(value)
                                for key, value in action.items()
                            },
                        }
                    )

        tag_payload = reader.call(
            service="budgets",
            region=region,
            operation="list_tags_for_resource",
            parameters={"ResourceARN": budget_arn},
        )
        for tag in tag_payload.get("ResourceTags", []):
            if not isinstance(tag, Mapping):
                continue
            budget_tag_rows.append(
                {
                    "budget_name": name,
                    "budget_arn": budget_arn,
                    "tag_key": str(tag.get("Key") or ""),
                    "tag_value": str(tag.get("Value") or ""),
                }
            )

    notification_counts = Counter(str(row["budget_name"]) for row in notification_rows)
    action_counts = Counter(str(row["budget_name"]) for row in action_rows)
    association_counts = Counter(str(row["budget_name"]) for row in association_rows)
    for row in budget_rows:
        name = str(row["budget_name"])
        row["association_count"] = association_counts[name]
        row["notification_count"] = notification_counts[name]
        row["action_count"] = action_counts[name]

    return {
        "budgets": budget_rows,
        "associations": association_rows,
        "notifications": notification_rows,
        "subscribers": subscriber_rows,
        "actions": action_rows,
        "budget_tags": budget_tag_rows,
        "cost_tag_keys": sorted(_budget_cost_tag_keys(association_rows)),
    }


def _enabled_regions(reader: CachedAwsReader, control_region: str) -> list[str]:
    payload = reader.call(
        service="ec2",
        region=control_region,
        operation="describe_regions",
        parameters={"AllRegions": True},
    )
    regions = sorted(
        str(item.get("RegionName") or "")
        for item in payload.get("Regions", [])
        if item.get("RegionName") and item.get("OptInStatus") != "not-opted-in"
    )
    if not regions:
        raise OnDemandCostReportError("EC2 describe_regions returned no enabled regions")
    return regions


def _discover_resource_explorer(
    reader: CachedAwsReader,
    *,
    account_id: str,
    control_region: str,
    regions: Sequence[str],
    resources: ResourceSet,
) -> dict[str, Any]:
    indexes: list[dict[str, Any]] = []
    for page in _paginate(
        reader,
        service="resource-explorer-2",
        region=control_region,
        operation="list_indexes",
        parameters={"Regions": list(regions), "MaxResults": 1000},
        request_token="NextToken",
        response_token="NextToken",
    ):
        indexes.extend(
            dict(item) for item in page.get("Indexes", []) if isinstance(item, Mapping)
        )
    index_regions = sorted(
        {str(item.get("Region") or "") for item in indexes if item.get("Region")}
    )
    untagged_arns: set[str] = set()
    discovered_arns: set[str] = set()
    for index_region in index_regions:
        for page in _paginate(
            reader,
            service="resource-explorer-2",
            region=index_region,
            operation="list_resources",
            parameters={"Filters": {"FilterString": ""}, "MaxResults": 1000},
            request_token="NextToken",
            response_token="NextToken",
        ):
            for item in page.get("Resources", []):
                if not isinstance(item, Mapping):
                    continue
                arn = str(item.get("Arn") or "")
                if not arn:
                    continue
                discovered_arns.add(arn)
                tags = _resource_explorer_tags(item.get("Properties"))
                row = resources.add(
                    source="resource_explorer",
                    arn=arn,
                    region=str(item.get("Region") or "global"),
                    service=str(item.get("Service") or ""),
                    resource_type=str(item.get("ResourceType") or ""),
                    cfn_resource_type=str(item.get("CfnResourceType") or ""),
                    tags=tags,
                    properties=item.get("Properties") or [],
                )
                if str(item.get("OwningAccountId") or account_id) != account_id:
                    row["lifecycle_evidence"] = "resource is visible but owned by another account"
        for page in _paginate(
            reader,
            service="resource-explorer-2",
            region=index_region,
            operation="list_resources",
            parameters={"Filters": {"FilterString": "tag:none"}, "MaxResults": 1000},
            request_token="NextToken",
            response_token="NextToken",
        ):
            for item in page.get("Resources", []):
                if isinstance(item, Mapping) and item.get("Arn"):
                    untagged_arns.add(str(item["Arn"]))
    for arn in untagged_arns:
        current_row = resources.records.get(arn)
        if current_row is not None and not current_row.get("tags"):
            current_row["tag_state"] = "untagged"
    return {
        "indexes": indexes,
        "index_regions": index_regions,
        "discovered_resource_count": len(discovered_arns),
        "untagged_resource_count": len(untagged_arns),
    }


def _discover_tagged_resources(
    reader: CachedAwsReader,
    *,
    regions: Sequence[str],
    resources: ResourceSet,
) -> list[dict[str, Any]]:
    tag_rows: list[dict[str, Any]] = []
    for region in regions:
        for page in _paginate(
            reader,
            service="resourcegroupstaggingapi",
            region=region,
            operation="get_resources",
            parameters={"ResourcesPerPage": 100},
            request_token="PaginationToken",
            response_token="PaginationToken",
        ):
            for item in page.get("ResourceTagMappingList", []):
                if not isinstance(item, Mapping):
                    continue
                arn = str(item.get("ResourceARN") or "")
                if not arn:
                    continue
                service, arn_region, _, resource = _arn_parts(arn)
                tags = _tags_map(item.get("Tags"))
                resource_type = resource.split("/", 1)[0].split(":", 1)[0]
                row = resources.add(
                    source="resource_groups_tagging_api",
                    arn=arn,
                    region=arn_region or region or "global",
                    service=service,
                    resource_type=f"{service}:{resource_type}",
                    tags=tags,
                )
                for key, value in sorted(tags.items()):
                    tag_rows.append(
                        {
                            "resource_key": row["resource_key"],
                            "arn": arn,
                            "region": row["region"],
                            "service": row["service"],
                            "resource_type": _type_key(row),
                            "resource_id": row["resource_id"],
                            "tag_key": key,
                            "tag_value": value,
                        }
                    )
    return tag_rows


def _discover_cloudformation(
    reader: CachedAwsReader,
    *,
    regions: Sequence[str],
    resources: ResourceSet,
) -> list[dict[str, Any]]:
    stacks: list[dict[str, Any]] = []
    for region in regions:
        summaries: list[dict[str, Any]] = []
        for page in _paginate(
            reader,
            service="cloudformation",
            region=region,
            operation="list_stacks",
            parameters={},
            request_token="NextToken",
            response_token="NextToken",
        ):
            summaries.extend(
                dict(item)
                for item in page.get("StackSummaries", [])
                if isinstance(item, Mapping)
            )
        for stack in summaries:
            name = str(stack.get("StackName") or "")
            stack_id = str(stack.get("StackId") or "")
            status = str(stack.get("StackStatus") or "")
            lifecycle = _stack_lifecycle(status)
            stack_row = {
                "region": region,
                "stack_name": name,
                "stack_id": stack_id,
                "stack_status": status,
                "lifecycle_status": lifecycle,
                "status_reason": str(stack.get("StackStatusReason") or ""),
                "creation_time": str(stack.get("CreationTime") or ""),
                "last_updated_time": str(stack.get("LastUpdatedTime") or ""),
                "deletion_time": str(stack.get("DeletionTime") or ""),
            }
            stacks.append(stack_row)
            resources.add(
                source="cloudformation",
                arn=stack_id,
                region=region,
                service="cloudformation",
                resource_type="cloudformation:stack",
                cfn_resource_type="AWS::CloudFormation::Stack",
                resource_id=name,
                current=lifecycle != "deleted",
                provider_state=status,
                lifecycle_status=lifecycle,
                lifecycle_evidence=f"CloudFormation stack status is {status}",
            )
            if lifecycle == "deleted":
                continue
            for page in _paginate(
                reader,
                service="cloudformation",
                region=region,
                operation="list_stack_resources",
                parameters={"StackName": stack_id or name},
                request_token="NextToken",
                response_token="NextToken",
            ):
                for item in page.get("StackResourceSummaries", []):
                    if not isinstance(item, Mapping):
                        continue
                    resource_status = str(item.get("ResourceStatus") or "")
                    resources.add(
                        source="cloudformation",
                        region=region,
                        service="cloudformation",
                        cfn_resource_type=str(item.get("ResourceType") or ""),
                        resource_id=str(
                            item.get("PhysicalResourceId")
                            or item.get("LogicalResourceId")
                            or ""
                        ),
                        current=True,
                        provider_state=resource_status,
                        owner_stack=name,
                        lifecycle_status=_provider_lifecycle(resource_status),
                        lifecycle_evidence=(
                            f"CloudFormation resource status is {resource_status}; "
                            f"owner stack {name} is {status}"
                        ),
                    )
    return stacks


def _direct_provider_inventory(
    reader: CachedAwsReader,
    *,
    account_id: str,
    regions: Sequence[str],
    control_region: str,
    resources: ResourceSet,
) -> None:
    def add_with_explicit_tags(*, tags: Mapping[str, str], **kwargs: Any) -> dict[str, Any]:
        row = resources.add(tags=tags, **kwargs)
        row["tag_state"] = "tagged" if tags else "untagged"
        return row

    for region in regions:
        for page in _paginate(
            reader,
            service="ec2",
            region=region,
            operation="describe_instances",
            parameters={},
            request_token="NextToken",
            response_token="NextToken",
        ):
            for reservation in page.get("Reservations", []):
                for item in reservation.get("Instances", []):
                    if not isinstance(item, Mapping) or not item.get("InstanceId"):
                        continue
                    instance_id = str(item["InstanceId"])
                    state = str((item.get("State") or {}).get("Name") or "")
                    add_with_explicit_tags(
                        source="ec2_provider",
                        arn=f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}",
                        region=region,
                        service="ec2",
                        resource_type="ec2:instance",
                        cfn_resource_type="AWS::EC2::Instance",
                        resource_id=instance_id,
                        tags=_tags_map(item.get("Tags")),
                        provider_state=state,
                        lifecycle_status=_provider_lifecycle(state),
                        lifecycle_evidence=f"EC2 instance state is {state}",
                        properties={
                            "InstanceType": item.get("InstanceType"),
                            "LaunchTime": item.get("LaunchTime"),
                            "InstanceLifecycle": item.get("InstanceLifecycle", "on-demand"),
                        },
                    )
        for page in _paginate(
            reader,
            service="ec2",
            region=region,
            operation="describe_volumes",
            parameters={},
            request_token="NextToken",
            response_token="NextToken",
        ):
            for item in page.get("Volumes", []):
                if not isinstance(item, Mapping) or not item.get("VolumeId"):
                    continue
                volume_id = str(item["VolumeId"])
                state = str(item.get("State") or "")
                add_with_explicit_tags(
                    source="ec2_provider",
                    arn=f"arn:aws:ec2:{region}:{account_id}:volume/{volume_id}",
                    region=region,
                    service="ec2",
                    resource_type="ec2:volume",
                    cfn_resource_type="AWS::EC2::Volume",
                    resource_id=volume_id,
                    tags=_tags_map(item.get("Tags")),
                    provider_state=state,
                    lifecycle_status=_provider_lifecycle(state),
                    lifecycle_evidence=f"EBS volume state is {state}",
                    properties={
                        "SizeGiB": item.get("Size"),
                        "VolumeType": item.get("VolumeType"),
                        "Attachments": item.get("Attachments") or [],
                    },
                )
        for page in _paginate(
            reader,
            service="ec2",
            region=region,
            operation="describe_snapshots",
            parameters={"OwnerIds": ["self"]},
            request_token="NextToken",
            response_token="NextToken",
        ):
            for item in page.get("Snapshots", []):
                if not isinstance(item, Mapping) or not item.get("SnapshotId"):
                    continue
                snapshot_id = str(item["SnapshotId"])
                state = str(item.get("State") or "")
                add_with_explicit_tags(
                    source="ec2_provider",
                    arn=f"arn:aws:ec2:{region}:{account_id}:snapshot/{snapshot_id}",
                    region=region,
                    service="ec2",
                    resource_type="ec2:snapshot",
                    cfn_resource_type="AWS::EC2::Snapshot",
                    resource_id=snapshot_id,
                    tags=_tags_map(item.get("Tags")),
                    provider_state=state,
                    lifecycle_status=_provider_lifecycle(state),
                    lifecycle_evidence=f"EBS snapshot state is {state}",
                    properties={"VolumeSizeGiB": item.get("VolumeSize")},
                )
        address_payload = reader.call(
            service="ec2",
            region=region,
            operation="describe_addresses",
        )
        for item in address_payload.get("Addresses", []):
            if not isinstance(item, Mapping):
                continue
            resource_id = str(item.get("AllocationId") or item.get("PublicIp") or "")
            if not resource_id:
                continue
            state = "associated" if item.get("AssociationId") else "unassociated"
            add_with_explicit_tags(
                source="ec2_provider",
                arn=f"arn:aws:ec2:{region}:{account_id}:elastic-ip/{resource_id}",
                region=region,
                service="ec2",
                resource_type="ec2:elastic-ip",
                cfn_resource_type="AWS::EC2::EIP",
                resource_id=resource_id,
                tags=_tags_map(item.get("Tags")),
                provider_state=state,
                lifecycle_status="active",
                lifecycle_evidence=f"Elastic IP is {state}",
            )
        for page in _paginate(
            reader,
            service="ec2",
            region=region,
            operation="describe_nat_gateways",
            parameters={},
            request_token="NextToken",
            response_token="NextToken",
        ):
            for item in page.get("NatGateways", []):
                if not isinstance(item, Mapping) or not item.get("NatGatewayId"):
                    continue
                resource_id = str(item["NatGatewayId"])
                state = str(item.get("State") or "")
                add_with_explicit_tags(
                    source="ec2_provider",
                    arn=f"arn:aws:ec2:{region}:{account_id}:natgateway/{resource_id}",
                    region=region,
                    service="ec2",
                    resource_type="ec2:natgateway",
                    cfn_resource_type="AWS::EC2::NatGateway",
                    resource_id=resource_id,
                    tags=_tags_map(item.get("Tags")),
                    provider_state=state,
                    lifecycle_status=_provider_lifecycle(state),
                    lifecycle_evidence=f"NAT gateway state is {state}",
                )
        for page in _paginate(
            reader,
            service="fsx",
            region=region,
            operation="describe_file_systems",
            parameters={},
            request_token="NextToken",
            response_token="NextToken",
        ):
            for item in page.get("FileSystems", []):
                if not isinstance(item, Mapping) or not item.get("FileSystemId"):
                    continue
                resource_id = str(item["FileSystemId"])
                state = str(item.get("Lifecycle") or "")
                add_with_explicit_tags(
                    source="fsx_provider",
                    arn=str(item.get("ResourceARN") or ""),
                    region=region,
                    service="fsx",
                    resource_type="fsx:file-system",
                    cfn_resource_type="AWS::FSx::FileSystem",
                    resource_id=resource_id,
                    tags=_tags_map(item.get("Tags")),
                    provider_state=state,
                    lifecycle_status=_provider_lifecycle(state),
                    lifecycle_evidence=f"FSx lifecycle is {state}",
                    properties={
                        "FileSystemType": item.get("FileSystemType"),
                        "StorageCapacityGiB": item.get("StorageCapacity"),
                        "StorageType": item.get("StorageType"),
                    },
                )
        for operation, result_key, cfn_type, id_key, arn_key, state_key in (
            (
                "describe_db_instances",
                "DBInstances",
                "AWS::RDS::DBInstance",
                "DBInstanceIdentifier",
                "DBInstanceArn",
                "DBInstanceStatus",
            ),
            (
                "describe_db_clusters",
                "DBClusters",
                "AWS::RDS::DBCluster",
                "DBClusterIdentifier",
                "DBClusterArn",
                "Status",
            ),
        ):
            for page in _paginate(
                reader,
                service="rds",
                region=region,
                operation=operation,
                parameters={},
                request_token="Marker",
                response_token="Marker",
            ):
                for item in page.get(result_key, []):
                    if not isinstance(item, Mapping) or not item.get(id_key):
                        continue
                    resource_id = str(item[id_key])
                    state = str(item.get(state_key) or "")
                    resources.add(
                        source="rds_provider",
                        arn=str(item.get(arn_key) or ""),
                        region=region,
                        service="rds",
                        resource_type=(
                            "rds:db" if cfn_type.endswith("DBInstance") else "rds:cluster"
                        ),
                        cfn_resource_type=cfn_type,
                        resource_id=resource_id,
                        provider_state=state,
                        lifecycle_status=_provider_lifecycle(state),
                        lifecycle_evidence=f"RDS provider state is {state}",
                        properties={
                            "Engine": item.get("Engine"),
                            "Class": item.get("DBInstanceClass"),
                            "AllocatedStorageGiB": item.get("AllocatedStorage"),
                        },
                    )
        for page in _paginate(
            reader,
            service="elbv2",
            region=region,
            operation="describe_load_balancers",
            parameters={},
            request_token="Marker",
            response_token="NextMarker",
        ):
            for item in page.get("LoadBalancers", []):
                if not isinstance(item, Mapping) or not item.get("LoadBalancerArn"):
                    continue
                arn = str(item["LoadBalancerArn"])
                state = str((item.get("State") or {}).get("Code") or "")
                resources.add(
                    source="elbv2_provider",
                    arn=arn,
                    region=region,
                    service="elasticloadbalancing",
                    resource_type="elasticloadbalancing:loadbalancer",
                    cfn_resource_type=(
                        "AWS::ElasticLoadBalancingV2::LoadBalancer"
                    ),
                    resource_id=str(item.get("LoadBalancerName") or _canonical_resource_id(arn)),
                    provider_state=state,
                    lifecycle_status=_provider_lifecycle(state),
                    lifecycle_evidence=f"ELBv2 provider state is {state}",
                    properties={"Type": item.get("Type"), "Scheme": item.get("Scheme")},
                )

    bucket_payload = reader.call(
        service="s3",
        region=control_region,
        operation="list_buckets",
    )
    for item in bucket_payload.get("Buckets", []):
        if not isinstance(item, Mapping) or not item.get("Name"):
            continue
        name = str(item["Name"])
        resources.add(
            source="s3_provider",
            arn=f"arn:aws:s3:::{name}",
            region="global",
            service="s3",
            resource_type="s3:bucket",
            cfn_resource_type="AWS::S3::Bucket",
            resource_id=name,
            provider_state="exists",
            lifecycle_status="active",
            lifecycle_evidence="S3 list_buckets returned the bucket",
            properties={"CreationDate": item.get("CreationDate")},
        )


def _collect_cost_data(
    reader: CachedAwsReader,
    config: OnDemandCostReportConfig,
    *,
    budget_cost_tag_keys: Sequence[str],
) -> dict[str, Any]:
    time_period = {
        "Start": config.start_date.isoformat(),
        "End": config.end_date.isoformat(),
    }
    service_pages = list(
        _paginate(
            reader,
            service="ce",
            region=DEFAULT_BILLING_REGION,
            operation="get_cost_and_usage",
            parameters={
                "TimePeriod": time_period,
                "Granularity": "DAILY",
                "Metrics": ["UnblendedCost"],
                "GroupBy": [
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                    {"Type": "DIMENSION", "Key": "REGION"},
                ],
            },
            request_token="NextPageToken",
            response_token="NextPageToken",
            paid=True,
        )
    )
    service_rows = _flatten_cost_pages(service_pages, ("service", "region"))
    services = sorted(
        {
            str(row["service"])
            for row in service_rows
            if row.get("service") and float(row.get("cost_usd") or 0.0) != 0.0
        }
    )

    usage_pages = list(
        _paginate(
            reader,
            service="ce",
            region=DEFAULT_BILLING_REGION,
            operation="get_cost_and_usage",
            parameters={
                "TimePeriod": time_period,
                "Granularity": "MONTHLY",
                "Metrics": ["UnblendedCost"],
                "GroupBy": [
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                    {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
                ],
            },
            request_token="NextPageToken",
            response_token="NextPageToken",
            paid=True,
        )
    )
    service_usage_rows = _flatten_cost_pages(
        usage_pages, ("service", "usage_type")
    )

    resource_rows: list[dict[str, Any]] = []
    if services:
        resource_pages = list(
            _paginate(
                reader,
                service="ce",
                region=DEFAULT_BILLING_REGION,
                operation="get_cost_and_usage_with_resources",
                parameters={
                    "TimePeriod": {
                        "Start": config.resource_start_date.isoformat(),
                        "End": config.end_date.isoformat(),
                    },
                    "Granularity": "DAILY",
                    "Metrics": ["UnblendedCost"],
                    "Filter": {
                        "Dimensions": {
                            "Key": "SERVICE",
                            "Values": services,
                        }
                    },
                    "GroupBy": [
                        {"Type": "DIMENSION", "Key": "SERVICE"},
                        {"Type": "DIMENSION", "Key": "RESOURCE_ID"},
                    ],
                },
                request_token="NextPageToken",
                response_token="NextPageToken",
                paid=True,
            )
        )
        resource_rows = _flatten_cost_pages(
            resource_pages, ("service", "resource_id")
        )

    discovered_cost_tag_rows: list[dict[str, Any]] = []
    discovered_tag_keys: list[str] = []
    if config.discover_cost_tag_keys:
        for page in _paginate(
            reader,
            service="ce",
            region=DEFAULT_BILLING_REGION,
            operation="get_tags",
            parameters={"TimePeriod": time_period, "MaxResults": 1000},
            request_token="NextPageToken",
            response_token="NextPageToken",
            paid=True,
        ):
            for value in page.get("Tags", []):
                tag_key = str(value)
                if tag_key:
                    discovered_cost_tag_rows.append(
                        {
                            "tag_key": tag_key,
                            "source_page_return_size": int(page.get("ReturnSize") or 0),
                            "source_total_size": int(page.get("TotalSize") or 0),
                        }
                    )
                    discovered_tag_keys.append(tag_key)

    selected_tag_keys = sorted(
        {
            *(key.strip() for key in config.cost_tag_keys if key.strip()),
            *(key.strip() for key in config.cluster_tag_keys if key.strip()),
            *(key.strip() for key in budget_cost_tag_keys if key.strip()),
        }
    )
    cost_by_tag_rows: list[dict[str, Any]] = []
    for tag_key in selected_tag_keys:
        tag_pages = list(
            _paginate(
                reader,
                service="ce",
                region=DEFAULT_BILLING_REGION,
                operation="get_cost_and_usage",
                parameters={
                    "TimePeriod": time_period,
                    "Granularity": "MONTHLY",
                    "Metrics": ["UnblendedCost"],
                    "GroupBy": [
                        {"Type": "TAG", "Key": tag_key},
                        {"Type": "DIMENSION", "Key": "SERVICE"},
                    ],
                },
                request_token="NextPageToken",
                response_token="NextPageToken",
                paid=True,
            )
        )
        rows = _flatten_cost_pages(tag_pages, ("tag_value", "service"))
        for row in rows:
            row["tag_key"] = tag_key
            row["tag_value"] = _normalize_tag_group_value(
                str(row["tag_value"]), tag_key
            )
        cost_by_tag_rows.extend(rows)

    return {
        "service_costs": service_rows,
        "service_usage_costs": service_usage_rows,
        "resource_costs": resource_rows,
        "cost_allocation_tag_keys": discovered_cost_tag_rows,
        "discovered_cost_tag_keys": sorted(set(discovered_tag_keys)),
        "selected_cost_tag_keys": selected_tag_keys,
        "cost_by_tag_value": cost_by_tag_rows,
    }


def _resource_aliases(row: Mapping[str, Any]) -> set[str]:
    aliases = {
        str(row.get("resource_key") or ""),
        str(row.get("arn") or ""),
        str(row.get("resource_id") or ""),
    }
    aliases.update(_canonical_resource_id(value) for value in tuple(aliases) if value)
    return {value for value in aliases if value}


def _attach_resource_costs(
    resources: ResourceSet,
    resource_cost_rows: Sequence[Mapping[str, Any]],
) -> None:
    alias_index: dict[str, set[str]] = defaultdict(set)
    for key, row in resources.records.items():
        for alias in _resource_aliases(row):
            alias_index[alias].add(key)
    amounts: dict[tuple[str, str], float] = defaultdict(float)
    for cost_row in resource_cost_rows:
        service = str(cost_row.get("service") or "")
        resource_id = str(cost_row.get("resource_id") or "")
        if not resource_id or resource_id == "NoResourceId":
            continue
        amounts[(service, resource_id)] += float(cost_row.get("cost_usd") or 0.0)
    for (service, raw_resource_id), amount in amounts.items():
        candidates: set[str] = set()
        for alias in {raw_resource_id, _canonical_resource_id(raw_resource_id)}:
            candidates.update(alias_index.get(alias, set()))
        if len(candidates) == 1:
            resources.records[next(iter(candidates))]["cost_usd"] += amount
            continue
        arn = raw_resource_id if raw_resource_id.startswith("arn:") else ""
        arn_service, region, _, _ = _arn_parts(arn)
        row = resources.add(
            source="cost_explorer",
            arn=arn,
            region=region or "unknown",
            service=arn_service or service,
            resource_type=f"billing::{service}",
            resource_id=_canonical_resource_id(raw_resource_id),
            current=False,
            lifecycle_status="unresolved",
            lifecycle_evidence=(
                "Cost Explorer reported spend, but dynamic current discovery did not "
                "produce one unambiguous matching resource"
            ),
        )
        row["cost_usd"] += amount
        row["presence"] = "cost_history_only"


def _current_tag_rows(resources: ResourceSet) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource in resources.records.values():
        for tag_key, tag_value in sorted((resource.get("tags") or {}).items()):
            rows.append(
                {
                    "resource_key": resource["resource_key"],
                    "arn": resource.get("arn", ""),
                    "region": resource.get("region", ""),
                    "service": resource.get("service", ""),
                    "resource_type": _type_key(resource),
                    "resource_id": resource.get("resource_id", ""),
                    "lifecycle_status": resource.get("lifecycle_status", ""),
                    "cost_usd": round(float(resource.get("cost_usd") or 0.0), 8),
                    "tag_key": str(tag_key),
                    "tag_value": str(tag_value),
                }
            )
    return rows


def _service_tag_summary(tag_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in tag_rows:
        key = (
            str(row.get("service") or ""),
            str(row.get("tag_key") or ""),
            str(row.get("tag_value") or ""),
        )
        total = totals.setdefault(
            key,
            {
                "service": key[0],
                "tag_key": key[1],
                "tag_value": key[2],
                "resource_count": 0,
                "resource_cost_usd": 0.0,
            },
        )
        total["resource_count"] += 1
        total["resource_cost_usd"] += float(row.get("cost_usd") or 0.0)
    rows = list(totals.values())
    for row in rows:
        row["resource_cost_usd"] = round(float(row["resource_cost_usd"]), 8)
    return sorted(
        rows,
        key=lambda row: (
            -float(row["resource_cost_usd"]),
            str(row["service"]),
            str(row["tag_key"]),
            str(row["tag_value"]),
        ),
    )


def _read_history(config: OnDemandCostReportConfig) -> Optional[dict[str, Any]]:
    path = Path(config.history_path).expanduser().resolve()
    if config.initialize_history:
        if path.exists():
            raise HistoryContractError(
                f"history already exists; refusing --initialize-history: {path}"
            )
        return None
    if not path.exists():
        raise HistoryContractError(
            f"history does not exist: {path}; use --initialize-history exactly once"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoryContractError(f"unable to read history {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HistoryContractError(f"history must be a JSON object: {path}")
    if payload.get("schema_version") != HISTORY_SCHEMA_VERSION:
        raise HistoryContractError(f"unsupported history schema: {path}")
    if payload.get("account_id") != config.account_id:
        raise HistoryContractError(
            f"history account {payload.get('account_id')!r} does not match "
            f"{config.account_id!r}"
        )
    if not isinstance(payload.get("resource_types"), dict) or not isinstance(
        payload.get("resources"), dict
    ):
        raise HistoryContractError(f"history catalogs are malformed: {path}")
    return payload


def _apply_history(
    resources: ResourceSet,
    *,
    prior: Optional[Mapping[str, Any]],
    generated_at: str,
    account_id: str,
    cost_services: Sequence[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    current_resource_keys = {
        key for key, row in resources.records.items() if bool(row.get("current"))
    }
    current_type_counts = Counter(
        _type_key(resources.records[key]) for key in current_resource_keys
    )
    for service in cost_services:
        current_type_counts[f"billing::{service}"] += 1

    prior_types = dict((prior or {}).get("resource_types") or {})
    type_names = sorted(set(prior_types) | set(current_type_counts))
    type_rows: list[dict[str, Any]] = []
    next_types: dict[str, dict[str, Any]] = {}
    baseline = prior is None
    for type_name in type_names:
        previous = prior_types.get(type_name) or {}
        count = int(current_type_counts.get(type_name, 0))
        previously_present = int(previous.get("last_count") or 0) > 0
        missing_runs = int(previous.get("missing_runs") or 0)
        if baseline:
            presence = "baseline"
        elif count and type_name not in prior_types:
            presence = "appeared"
        elif count and previously_present:
            presence = "persisting"
        elif count:
            presence = "reappeared"
        else:
            presence = "disappeared"
        first_seen = str(previous.get("first_seen") or generated_at)
        last_seen = generated_at if count else str(previous.get("last_seen") or "")
        next_missing_runs = 0 if count else missing_runs + 1
        row = {
            "resource_type": type_name,
            "presence": presence,
            "current_count": count,
            "previous_count": int(previous.get("last_count") or 0),
            "first_seen": first_seen,
            "last_seen": last_seen,
            "missing_runs": next_missing_runs,
        }
        type_rows.append(row)
        next_types[type_name] = {
            "first_seen": first_seen,
            "last_seen": last_seen,
            "last_count": count,
            "missing_runs": next_missing_runs,
        }

    prior_resources = dict((prior or {}).get("resources") or {})
    next_resources: dict[str, dict[str, Any]] = {}
    for key in sorted(current_resource_keys):
        row = resources.records[key]
        previous = prior_resources.get(key) or {}
        was_missing = int(previous.get("missing_runs") or 0) > 0
        row["presence"] = (
            "baseline"
            if baseline
            else "reappeared"
            if was_missing
            else "persisting"
            if key in prior_resources
            else "appeared"
        )
        next_resources[key] = {
            "resource_key": key,
            "arn": str(row.get("arn") or ""),
            "region": str(row.get("region") or ""),
            "service": str(row.get("service") or ""),
            "resource_type": _type_key(row),
            "resource_id": str(row.get("resource_id") or ""),
            "first_seen": str(previous.get("first_seen") or generated_at),
            "last_seen": generated_at,
            "missing_runs": 0,
            "last_lifecycle_status": str(row.get("lifecycle_status") or ""),
        }
    for key, previous in sorted(prior_resources.items()):
        if key in current_resource_keys:
            continue
        missing_runs = int(previous.get("missing_runs") or 0) + 1
        previous_lifecycle = str(previous.get("last_lifecycle_status") or "")
        lifecycle = "deleted" if previous_lifecycle == "deleted" else "unresolved"
        resources.records.setdefault(
            key,
            {
                "resource_key": key,
                "arn": str(previous.get("arn") or ""),
                "region": str(previous.get("region") or "unknown"),
                "service": str(previous.get("service") or ""),
                "resource_type": str(previous.get("resource_type") or ""),
                "cfn_resource_type": (
                    str(previous.get("resource_type") or "")
                    if str(previous.get("resource_type") or "").startswith("AWS::")
                    else ""
                ),
                "resource_id": str(previous.get("resource_id") or ""),
                "current": False,
                "sources": ["history"],
                "tags": {},
                "tag_state": "unknown",
                "provider_state": "not observed in current discovery",
                "owner_stack": "",
                "lifecycle_status": lifecycle,
                "lifecycle_evidence": (
                    "resource disappeared from dynamic discovery; absence alone is "
                    "not proof of deletion"
                ),
                "properties": [],
                "cost_usd": 0.0,
                "presence": "disappeared",
                "utilization_status": "not_current",
            },
        )
        next_resources[key] = {
            **previous,
            "missing_runs": missing_runs,
            "last_lifecycle_status": lifecycle,
        }

    history = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "account_id": account_id,
        "updated_at": generated_at,
        "resource_types": next_types,
        "resources": next_resources,
    }
    return type_rows, history


def _collect_utilization(
    reader: CachedAwsReader,
    config: OnDemandCostReportConfig,
    resources: ResourceSet,
) -> list[dict[str, Any]]:
    current_rows = [row for row in resources.records.values() if row.get("current")]
    ranked = sorted(
        current_rows,
        key=lambda row: (
            -float(row.get("cost_usd") or 0.0),
            str(row.get("resource_key") or ""),
        ),
    )
    selected = ranked[: config.utilization_limit]
    selected_keys = {str(row["resource_key"]) for row in selected}
    output: list[dict[str, Any]] = []
    queries_by_region: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    query_number = 0
    for row in current_rows:
        key = str(row["resource_key"])
        type_name = _type_key(row)
        if key not in selected_keys:
            row["utilization_status"] = "not_selected"
            continue
        specs = UTILIZATION_SPECS.get(type_name)
        if not specs:
            row["utilization_status"] = "not_supported"
            output.append(
                {
                    "resource_key": key,
                    "resource_type": type_name,
                    "region": row.get("region", ""),
                    "resource_id": row.get("resource_id", ""),
                    "cost_usd": round(float(row.get("cost_usd") or 0.0), 8),
                    "status": "not_supported",
                    "metric_name": "",
                    "namespace": "",
                    "statistic": "",
                    "datapoints": 0,
                }
            )
            continue
        region = str(row.get("region") or "")
        resource_id = str(row.get("resource_id") or "")
        if region in {"", "global", "unknown"} or not resource_id:
            row["utilization_status"] = "unresolved_identity"
            continue
        row["utilization_status"] = "selected"
        for spec in specs:
            query_number += 1
            query_id = f"q{query_number:06d}"
            query = {
                "Id": query_id,
                "MetricStat": {
                    "Metric": {
                        "Namespace": spec.namespace,
                        "MetricName": spec.metric_name,
                        "Dimensions": [
                            {"Name": spec.dimension_name, "Value": resource_id}
                        ],
                    },
                    "Period": config.utilization_period_seconds,
                    "Stat": spec.statistic,
                },
                "ReturnData": True,
            }
            metadata = {
                "query_id": query_id,
                "resource_key": key,
                "resource_type": type_name,
                "region": region,
                "resource_id": resource_id,
                "cost_usd": round(float(row.get("cost_usd") or 0.0), 8),
                "namespace": spec.namespace,
                "metric_name": spec.metric_name,
                "statistic": spec.statistic,
            }
            queries_by_region[region].append((query, metadata))

    start_time = datetime.combine(
        config.resource_start_date, datetime_time.min, tzinfo=timezone.utc
    )
    end_time = datetime.combine(config.end_date, datetime_time.min, tzinfo=timezone.utc)
    for region, query_pairs in sorted(queries_by_region.items()):
        for offset in range(0, len(query_pairs), 200):
            batch = query_pairs[offset : offset + 200]
            metadata_by_id = {item[1]["query_id"]: item[1] for item in batch}
            values_by_id: dict[str, list[float]] = defaultdict(list)
            statuses: dict[str, str] = {}
            for page in _paginate(
                reader,
                service="cloudwatch",
                region=region,
                operation="get_metric_data",
                parameters={
                    "MetricDataQueries": [item[0] for item in batch],
                    "StartTime": start_time,
                    "EndTime": end_time,
                    "ScanBy": "TimestampAscending",
                    "MaxDatapoints": 100800,
                },
                request_token="NextToken",
                response_token="NextToken",
            ):
                for result in page.get("MetricDataResults", []):
                    if not isinstance(result, Mapping):
                        continue
                    query_id = str(result.get("Id") or "")
                    values_by_id[query_id].extend(
                        float(value) for value in result.get("Values", [])
                    )
                    statuses[query_id] = str(result.get("StatusCode") or "")
            for query_id, metadata in metadata_by_id.items():
                values = values_by_id.get(query_id, [])
                status = "collected" if values else "no_datapoints"
                resource = resources.records[str(metadata["resource_key"])]
                if status == "collected":
                    resource["utilization_status"] = "collected"
                elif resource.get("utilization_status") != "collected":
                    resource["utilization_status"] = "no_datapoints"
                output.append(
                    {
                        **metadata,
                        "status": status,
                        "cloudwatch_status": statuses.get(query_id, ""),
                        "datapoints": len(values),
                        "average": round(sum(values) / len(values), 8) if values else None,
                        "sum": round(sum(values), 8) if values else None,
                        "minimum": round(min(values), 8) if values else None,
                        "maximum": round(max(values), 8) if values else None,
                    }
                )
    return sorted(
        output,
        key=lambda row: (
            -float(row.get("cost_usd") or 0.0),
            str(row.get("resource_key") or ""),
            str(row.get("metric_name") or ""),
        ),
    )


def _cluster_rows(
    *,
    resources: ResourceSet,
    stacks: Sequence[Mapping[str, Any]],
    parallelclusters: Sequence[Mapping[str, Any]],
    cost_by_tag_rows: Sequence[Mapping[str, Any]],
    cluster_tag_keys: Sequence[str],
) -> list[dict[str, Any]]:
    pcluster_by_name: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in parallelclusters:
        name = str(row.get("cluster") or row.get("clusterName") or "")
        if name:
            pcluster_by_name[name].append(row)
    stacks_by_name: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in stacks:
        name = str(row.get("stack_name") or "")
        if name:
            stacks_by_name[name].append(row)
    tagged_resources: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for resource in resources.records.values():
        if not resource.get("current"):
            continue
        tags = resource.get("tags") or {}
        for tag_key in cluster_tag_keys:
            name = str(tags.get(tag_key) or "")
            if name:
                tagged_resources[name].append(resource)
    cost_by_cluster_key: dict[tuple[str, str], float] = defaultdict(float)
    for row in cost_by_tag_rows:
        tag_key = str(row.get("tag_key") or "")
        if tag_key not in cluster_tag_keys:
            continue
        name = str(row.get("tag_value") or "")
        if not name or name in {"NoTagKey", "NoTagValue"}:
            continue
        cost_by_cluster_key[(name, tag_key)] += float(row.get("cost_usd") or 0.0)
    names = sorted(
        set(pcluster_by_name)
        | set(stacks_by_name)
        | set(tagged_resources)
        | {name for name, _ in cost_by_cluster_key}
    )
    rows: list[dict[str, Any]] = []
    primary_tag_key = str(cluster_tag_keys[0]) if cluster_tag_keys else ""
    for name in names:
        by_tag = {
            key: round(cost_by_cluster_key.get((name, key), 0.0), 8)
            for key in cluster_tag_keys
        }
        pcluster_matches = pcluster_by_name.get(name, [])
        current_resources = tagged_resources.get(name, [])
        stack_history = stacks_by_name.get(name, [])
        active_stacks = [row for row in stack_history if row.get("lifecycle_status") != "deleted"]
        deleted_stacks = [row for row in stack_history if row.get("lifecycle_status") == "deleted"]
        if pcluster_matches:
            for match in pcluster_matches:
                rows.append(
                    {
                        "cluster": name,
                        "region": str(match.get("region") or "unknown"),
                        "lifecycle_status": str(match.get("lifecycle_status") or "unresolved"),
                        "provider_status": str(match.get("provider_status") or ""),
                        "compute_fleet_status": str(
                            match.get("compute_fleet_status") or ""
                        ),
                        "cloudformation_status": str(
                            match.get("cloudformationStackStatus") or ""
                        ),
                        "current_tagged_resource_count": len(current_resources),
                        "cost_usd_primary_tag_key": by_tag.get(primary_tag_key, 0.0),
                        "primary_tag_key": primary_tag_key,
                        "cost_usd_by_tag_key_json": json.dumps(by_tag, sort_keys=True),
                        "classification_evidence": str(
                            match.get("classification_evidence") or "ParallelCluster API"
                        ),
                    }
                )
            continue
        if active_stacks:
            chosen = sorted(
                active_stacks,
                key=lambda row: str(
                    row.get("last_updated_time") or row.get("creation_time") or ""
                ),
                reverse=True,
            )[0]
            lifecycle = str(chosen.get("lifecycle_status") or "active")
            evidence = "same-name live CloudFormation stack; ParallelCluster API did not list it"
        elif current_resources:
            chosen = {"region": str(current_resources[0].get("region") or "unknown")}
            lifecycle = "orphaned"
            evidence = (
                "current resources retain an explicit cluster tag, but no live "
                "ParallelCluster or same-name CloudFormation owner exists"
            )
        elif deleted_stacks:
            chosen = sorted(
                deleted_stacks,
                key=lambda row: str(row.get("deletion_time") or ""),
                reverse=True,
            )[0]
            lifecycle = "deleted"
            evidence = "same-name CloudFormation stack is DELETE_COMPLETE"
        else:
            chosen = {"region": "unknown"}
            lifecycle = "unresolved"
            evidence = "cost tag history exists without current provider evidence"
        rows.append(
            {
                "cluster": name,
                "region": str(chosen.get("region") or "unknown"),
                "lifecycle_status": lifecycle,
                "provider_status": str(chosen.get("stack_status") or "not_listed"),
                "compute_fleet_status": "not_available",
                "cloudformation_status": str(chosen.get("stack_status") or ""),
                "current_tagged_resource_count": len(current_resources),
                "cost_usd_primary_tag_key": by_tag.get(primary_tag_key, 0.0),
                "primary_tag_key": primary_tag_key,
                "cost_usd_by_tag_key_json": json.dumps(by_tag, sort_keys=True),
                "classification_evidence": evidence,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -float(row.get("cost_usd_primary_tag_key") or 0.0),
            str(row.get("cluster") or ""),
            str(row.get("region") or ""),
        ),
    )


def _empty_budget_data() -> dict[str, Any]:
    return {
        "budgets": [],
        "associations": [],
        "notifications": [],
        "subscribers": [],
        "actions": [],
        "budget_tags": [],
        "cost_tag_keys": [],
    }


def run_on_demand_cost_report(
    config: OnDemandCostReportConfig,
    *,
    session_factory: Callable[..., Any] = boto3.Session,
    command_runner: CommandRunner = _run_json_command,
    now: Callable[[], datetime] = _utc_now,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Collect and write the on-demand machine-readable report datasets."""

    config.validate()
    prior_history = _read_history(config)
    output_dir = Path(config.output_dir).expanduser().resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise OnDemandCostReportError(
            f"output_dir must be absent or empty; refusing to overwrite {output_dir}"
        )

    cache = ExactRequestCache(
        config.cache_dir,
        max_age_seconds=config.cache_max_age_seconds,
        now=now,
    )
    limiter = ServiceRateLimiter(
        {
            "ce": config.ce_min_interval_seconds,
            "parallelcluster-cli": config.parallelcluster_min_interval_seconds,
            "*": config.other_min_interval_seconds,
        },
        monotonic=monotonic,
        sleep=sleep,
    )
    reader = CachedAwsReader(
        profile=config.profile,
        account_id=config.account_id,
        cache=cache,
        limiter=limiter,
        paid_call_budget=config.paid_call_budget,
        cache_only=config.cache_only,
        refresh=config.refresh,
        session_factory=session_factory,
    )

    identity = reader.call(
        service="sts",
        region=config.control_region,
        operation="get_caller_identity",
    )
    resolved_account = str(identity.get("Account") or "")
    if resolved_account != config.account_id:
        raise OnDemandCostReportError(
            f"AWS profile {config.profile!r} resolved to account {resolved_account!r}; "
            f"expected {config.account_id!r}"
        )

    budget_data = (
        _collect_budgets(
            reader,
            account_id=config.account_id,
            region=DEFAULT_BILLING_REGION,
        )
        if config.include_budgets
        else _empty_budget_data()
    )
    cost_data = _collect_cost_data(
        reader,
        config,
        budget_cost_tag_keys=budget_data["cost_tag_keys"],
    )
    regions = _enabled_regions(reader, config.control_region)

    resources = ResourceSet()
    resource_explorer = _discover_resource_explorer(
        reader,
        account_id=config.account_id,
        control_region=config.control_region,
        regions=regions,
        resources=resources,
    )
    _discover_tagged_resources(reader, regions=regions, resources=resources)
    stacks = _discover_cloudformation(reader, regions=regions, resources=resources)
    _direct_provider_inventory(
        reader,
        account_id=config.account_id,
        regions=regions,
        control_region=config.control_region,
        resources=resources,
    )
    _attach_resource_costs(resources, cost_data["resource_costs"])

    parallelclusters: list[dict[str, Any]] = []
    pcluster_stats: dict[str, Any] = {"enabled": False}
    if config.parallelcluster_executable is not None:
        pcluster_reader = CachedParallelClusterReader(
            executable=config.parallelcluster_executable,
            profile=config.profile,
            account_id=config.account_id,
            cache=cache,
            limiter=limiter,
            cache_only=config.cache_only,
            refresh=config.refresh,
            command_runner=command_runner,
        )
        parallelclusters = _collect_parallelclusters(
            pcluster_reader, config.parallelcluster_regions
        )
        pcluster_stats = {
            "enabled": True,
            **pcluster_reader.stats.to_dict(limiter.total_sleep_seconds),
        }

    clusters = _cluster_rows(
        resources=resources,
        stacks=stacks,
        parallelclusters=parallelclusters,
        cost_by_tag_rows=cost_data["cost_by_tag_value"],
        cluster_tag_keys=config.cluster_tag_keys,
    )
    utilization_rows = _collect_utilization(reader, config, resources)
    generated_at = now().isoformat().replace("+00:00", "Z")
    cost_services = sorted(
        {
            str(row.get("service") or "")
            for row in cost_data["service_costs"]
            if row.get("service") and float(row.get("cost_usd") or 0.0) != 0.0
        }
    )
    resource_type_rows, next_history = _apply_history(
        resources,
        prior=prior_history,
        generated_at=generated_at,
        account_id=config.account_id,
        cost_services=cost_services,
    )
    tag_rows = _current_tag_rows(resources)
    service_tag_rows = _service_tag_summary(tag_rows)

    resource_rows = sorted(
        (_serializable_resource(row) for row in resources.records.values()),
        key=lambda row: (
            not bool(row.get("current")),
            -float(row.get("cost_usd") or 0.0),
            str(row.get("resource_type") or row.get("cfn_resource_type") or ""),
            str(row.get("resource_key") or ""),
        ),
    )
    high_cost_rows = [
        row for row in resource_rows if float(row.get("cost_usd") or 0.0) != 0.0
    ]
    untagged_rows = [row for row in resource_rows if row.get("tag_state") == "untagged"]
    exception_rows = [
        row
        for row in resource_rows
        if row.get("lifecycle_status") in {"exception", "exception_recovered", "orphaned"}
    ]
    stack_exception_rows = [
        dict(row)
        for row in stacks
        if row.get("lifecycle_status") in {"exception", "exception_recovered"}
    ]

    output_files: dict[str, tuple[str, Sequence[Mapping[str, Any]]]] = {
        "service_costs": ("service_costs.csv", cost_data["service_costs"]),
        "service_usage_costs": (
            "service_usage_costs.csv",
            cost_data["service_usage_costs"],
        ),
        "resource_costs": ("resource_costs.csv", cost_data["resource_costs"]),
        "cost_allocation_tag_keys": (
            "cost_allocation_tag_keys.csv",
            cost_data["cost_allocation_tag_keys"],
        ),
        "cost_by_tag_value": (
            "cost_by_tag_value.csv",
            cost_data["cost_by_tag_value"],
        ),
        "resources": ("resources.csv", resource_rows),
        "high_cost_resources": ("high_cost_resources.csv", high_cost_rows),
        "untagged_resources": ("untagged_resources.csv", untagged_rows),
        "resource_types": ("resource_types.csv", resource_type_rows),
        "resource_tags": ("resource_tags.csv", tag_rows),
        "service_tag_summary": ("service_tag_summary.csv", service_tag_rows),
        "utilization": ("utilization.csv", utilization_rows),
        "clusters": ("clusters.csv", clusters),
        "cloudformation_stacks": ("cloudformation_stacks.csv", stacks),
        "lifecycle_exceptions": (
            "lifecycle_exceptions.csv",
            [*exception_rows, *stack_exception_rows],
        ),
        "budgets": ("budgets.csv", budget_data["budgets"]),
        "budget_associations": (
            "budget_associations.csv",
            budget_data["associations"],
        ),
        "budget_notifications": (
            "budget_notifications.csv",
            budget_data["notifications"],
        ),
        "budget_subscribers": (
            "budget_subscribers.csv",
            budget_data["subscribers"],
        ),
        "budget_actions": ("budget_actions.csv", budget_data["actions"]),
        "budget_tags": ("budget_tags.csv", budget_data["budget_tags"]),
    }
    for _, (filename, rows) in output_files.items():
        _atomic_csv(output_dir / filename, rows)

    request_stats = reader.stats.to_dict(limiter.total_sleep_seconds)
    lifecycle_counts = Counter(str(row.get("lifecycle_status") or "") for row in resource_rows)
    type_presence_counts = Counter(str(row.get("presence") or "") for row in resource_type_rows)
    summary = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "mode": "read_only",
        "profile": config.profile,
        "account_id": config.account_id,
        "caller_identity": {
            "account": resolved_account,
            "arn": str(identity.get("Arn") or ""),
            "user_id": str(identity.get("UserId") or ""),
        },
        "cost_window": {
            "start": config.start_date.isoformat(),
            "end_exclusive": config.end_date.isoformat(),
            "resource_start": config.resource_start_date.isoformat(),
        },
        "coverage": {
            "enabled_regions": regions,
            "resource_explorer_index_regions": resource_explorer["index_regions"],
            "parallelcluster_regions": list(config.parallelcluster_regions),
            "resource_explorer_limit": (
                "only resources visible through configured Resource Explorer views/indexes"
            ),
            "disappeared_resource_limit": (
                "absence from current discovery is unresolved unless provider history proves deletion"
            ),
        },
        "counts": {
            "resources": len(resource_rows),
            "current_resources": sum(1 for row in resource_rows if row.get("current")),
            "high_cost_resources": len(high_cost_rows),
            "untagged_resources": len(untagged_rows),
            "resource_tags": len(tag_rows),
            "resource_types": len(resource_type_rows),
            "clusters": len(clusters),
            "budgets": len(budget_data["budgets"]),
            "budget_associations": len(budget_data["associations"]),
        },
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "resource_type_presence_counts": dict(sorted(type_presence_counts.items())),
        "tag_analysis": {
            "discovered_cost_allocation_tag_keys": cost_data[
                "discovered_cost_tag_keys"
            ],
            "selected_cost_tag_keys": cost_data["selected_cost_tag_keys"],
            "budget_selected_cost_tag_keys": budget_data["cost_tag_keys"],
        },
        "budgets": {
            "included": config.include_budgets,
            "api_read_pricing": "budget monitoring and notifications are free; no budget mutation",
        },
        "request_reuse": request_stats,
        "parallelcluster_request_reuse": pcluster_stats,
        "paid_call_guard": {
            "hard_ceiling_usd_at_observed_rate": MAX_AUDIT_PAID_COST_USD,
            "observed_request_rate_usd": OBSERVED_COST_EXPLORER_REQUEST_USD,
            "configured_call_budget": config.paid_call_budget,
            "configured_budget_usd_at_observed_rate": round(
                config.paid_call_budget * OBSERVED_COST_EXPLORER_REQUEST_USD, 2
            ),
            "actual_paid_live_calls": request_stats["paid_live_calls"],
            "actual_estimated_cost_usd_at_observed_rate": request_stats[
                "estimated_paid_call_cost_usd_at_observed_rate"
            ],
            "sdk_total_max_attempts": 1,
        },
        "history": {
            "path": str(Path(config.history_path).expanduser().resolve()),
            "initialized": prior_history is None,
        },
        "output_files": {
            name: filename for name, (filename, _) in output_files.items()
        },
    }
    _atomic_json(output_dir / "summary.json", summary)
    _atomic_json(Path(config.history_path).expanduser().resolve(), next_history)
    return summary


__all__ = [
    "HISTORY_SCHEMA_VERSION",
    "REPORT_SCHEMA_VERSION",
    "HistoryContractError",
    "OnDemandCostReportConfig",
    "OnDemandCostReportError",
    "run_on_demand_cost_report",
]
