"""Cached, throttled, read-only AWS API call attribution audit.

The audit intentionally treats request-rate control and request-count control as
different concerns.  Throttling spaces live calls; exact-request disk caching,
cache-only mode, and a paid-call budget prevent repeated Cost Explorer charges.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping, Optional, Sequence

import boto3
from botocore.config import Config as BotocoreConfig


CACHE_SCHEMA_VERSION = 1
AUDIT_SCHEMA_VERSION = 1
OBSERVED_COST_EXPLORER_REQUEST_USD = 0.01
MAX_AUDIT_PAID_COST_USD = 3.00
MAX_AUDIT_PAID_CALLS_AT_OBSERVED_RATE = int(
    MAX_AUDIT_PAID_COST_USD / OBSERVED_COST_EXPLORER_REQUEST_USD
)
DEFAULT_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
DEFAULT_CE_MIN_INTERVAL_SECONDS = 1.0
DEFAULT_CLOUDTRAIL_MIN_INTERVAL_SECONDS = 0.5
DEFAULT_OTHER_MIN_INTERVAL_SECONDS = 0.2
DEFAULT_BILLING_REGION = "us-east-1"
DEFAULT_EVENT_SOURCE = "ce.amazonaws.com"
DEFAULT_BILLING_SERVICE = "AWS Cost Explorer"


class ApiCallAuditError(RuntimeError):
    """Base error for the API call audit."""


class CacheEntryError(ApiCallAuditError):
    """A cache entry exists but is malformed or does not match its request."""


class CacheMissError(ApiCallAuditError):
    """Cache-only mode could not satisfy an exact request."""


class PaidCallBudgetExceeded(ApiCallAuditError):
    """A paid API call would exceed the explicit per-run budget."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported cache value type: {type(value).__name__}")


def _canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CacheEntryError(f"Cache timestamp is not timezone-aware: {value!r}")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class AwsRequest:
    profile: str
    account_id: str
    service: str
    region: str
    operation: str
    parameters: Mapping[str, Any]

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": CACHE_SCHEMA_VERSION,
            "profile": self.profile,
            "account_id": self.account_id,
            "service": self.service,
            "region": self.region,
            "operation": self.operation,
            "parameters": _jsonable(self.parameters),
        }

    @property
    def fingerprint(self) -> str:
        return _sha256(self.payload())


@dataclass(frozen=True)
class CacheLookup:
    response: Optional[dict[str, Any]]
    status: str
    path: Path
    stored_at: Optional[str] = None
    age_seconds: Optional[float] = None


class ExactRequestCache:
    """Persistent exact-request cache with digest validation and atomic writes."""

    def __init__(
        self,
        root: Path,
        *,
        max_age_seconds: float,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        if max_age_seconds < 0:
            raise ValueError("cache max age must be non-negative")
        self.root = Path(root).expanduser().resolve()
        self.max_age_seconds = float(max_age_seconds)
        self.now = now

    def path_for(self, request: AwsRequest) -> Path:
        return (
            self.root
            / request.service
            / request.region
            / request.operation
            / f"{request.fingerprint}.json"
        )

    def lookup(self, request: AwsRequest) -> CacheLookup:
        path = self.path_for(request)
        if not path.exists():
            return CacheLookup(response=None, status="missing", path=path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CacheEntryError(f"Unable to read cache entry {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise CacheEntryError(f"Cache entry must be a JSON object: {path}")
        if payload.get("schema_version") != CACHE_SCHEMA_VERSION:
            raise CacheEntryError(f"Unsupported cache schema in {path}")
        if payload.get("request_fingerprint") != request.fingerprint:
            raise CacheEntryError(f"Cache fingerprint mismatch in {path}")
        if payload.get("request") != request.payload():
            raise CacheEntryError(f"Cache request payload mismatch in {path}")
        response = payload.get("response")
        if not isinstance(response, dict):
            raise CacheEntryError(f"Cache response must be a JSON object: {path}")
        if payload.get("response_sha256") != _sha256(response):
            raise CacheEntryError(f"Cache response digest mismatch in {path}")
        stored_at = str(payload.get("stored_at") or "")
        if not stored_at:
            raise CacheEntryError(f"Cache stored_at is missing in {path}")
        age_seconds = (self.now() - _parse_utc_timestamp(stored_at)).total_seconds()
        if age_seconds < -60:
            raise CacheEntryError(f"Cache entry timestamp is in the future: {path}")
        effective_age = max(age_seconds, 0.0)
        if effective_age > self.max_age_seconds:
            return CacheLookup(
                response=None,
                status="stale",
                path=path,
                stored_at=stored_at,
                age_seconds=effective_age,
            )
        return CacheLookup(
            response=response,
            status="hit",
            path=path,
            stored_at=stored_at,
            age_seconds=effective_age,
        )

    def store(self, request: AwsRequest, response: Mapping[str, Any]) -> Path:
        path = self.path_for(request)
        normalized_response = _jsonable(response)
        if not isinstance(normalized_response, dict):
            raise TypeError("AWS response must normalize to a JSON object")
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "request_fingerprint": request.fingerprint,
            "request": request.payload(),
            "stored_at": self.now().isoformat().replace("+00:00", "Z"),
            "response_sha256": _sha256(normalized_response),
            "response": normalized_response,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return path


class ServiceRateLimiter:
    """Minimum-interval limiter applied only immediately before live calls."""

    def __init__(
        self,
        intervals: Mapping[str, float],
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        normalized: dict[str, float] = {}
        for service, interval in intervals.items():
            value = float(interval)
            if value < 0:
                raise ValueError(f"minimum interval for {service} must be non-negative")
            normalized[str(service)] = value
        self.intervals = normalized
        self.monotonic = monotonic
        self.sleep = sleep
        self.last_call_at: dict[str, float] = {}
        self.total_sleep_seconds = 0.0

    def wait(self, service: str) -> float:
        interval = self.intervals.get(service, self.intervals.get("*", 0.0))
        now = self.monotonic()
        previous = self.last_call_at.get(service)
        slept = 0.0
        if previous is not None and interval > 0:
            remaining = interval - (now - previous)
            if remaining > 0:
                self.sleep(remaining)
                slept = remaining
                self.total_sleep_seconds += remaining
                now = self.monotonic()
        self.last_call_at[service] = now
        return slept


@dataclass
class ApiCallStats:
    cache_hits: int = 0
    cache_misses: int = 0
    cache_stale: int = 0
    live_calls: int = 0
    paid_live_calls: int = 0
    calls_by_service_operation: Counter[tuple[str, str]] = field(default_factory=Counter)
    cache_hits_by_service_operation: Counter[tuple[str, str]] = field(default_factory=Counter)
    cache_paths: set[str] = field(default_factory=set)

    def to_dict(self, throttle_sleep_seconds: float) -> dict[str, Any]:
        attempted = self.cache_hits + self.cache_misses
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_stale": self.cache_stale,
            "cache_hit_ratio": round(self.cache_hits / attempted, 6) if attempted else None,
            "live_calls": self.live_calls,
            "paid_live_calls": self.paid_live_calls,
            "estimated_paid_call_cost_usd_at_observed_rate": round(
                self.paid_live_calls * OBSERVED_COST_EXPLORER_REQUEST_USD,
                2,
            ),
            "observed_cost_explorer_request_rate_usd": OBSERVED_COST_EXPLORER_REQUEST_USD,
            "throttle_sleep_seconds": round(throttle_sleep_seconds, 6),
            "live_calls_by_service_operation": [
                {"service": key[0], "operation": key[1], "calls": count}
                for key, count in sorted(self.calls_by_service_operation.items())
            ],
            "cache_hits_by_service_operation": [
                {"service": key[0], "operation": key[1], "hits": count}
                for key, count in sorted(self.cache_hits_by_service_operation.items())
            ],
            "cache_entry_count": len(self.cache_paths),
        }


class CachedAwsReader:
    """Read-only AWS SDK caller with exact caching, throttling, and paid-call budget."""

    def __init__(
        self,
        *,
        profile: str,
        account_id: str,
        cache: ExactRequestCache,
        limiter: ServiceRateLimiter,
        paid_call_budget: int,
        cache_only: bool = False,
        refresh: bool = False,
        session_factory: Callable[..., Any] = boto3.Session,
    ) -> None:
        if not profile.strip():
            raise ValueError("AWS profile is required")
        if not re.fullmatch(r"\d{12}", account_id.strip()):
            raise ValueError("AWS account id must contain exactly 12 digits")
        if paid_call_budget < 0:
            raise ValueError("paid call budget must be non-negative")
        if paid_call_budget > MAX_AUDIT_PAID_CALLS_AT_OBSERVED_RATE:
            raise ValueError(
                f"paid call budget may not exceed {MAX_AUDIT_PAID_CALLS_AT_OBSERVED_RATE}; "
                f"the audit hard ceiling is ${MAX_AUDIT_PAID_COST_USD:.2f} at the observed "
                f"${OBSERVED_COST_EXPLORER_REQUEST_USD:.2f} request rate"
            )
        if cache_only and refresh:
            raise ValueError("cache-only and refresh are mutually exclusive")
        self.profile = profile.strip()
        self.account_id = account_id.strip()
        self.cache = cache
        self.limiter = limiter
        self.paid_call_budget = int(paid_call_budget)
        self.cache_only = bool(cache_only)
        self.refresh = bool(refresh)
        self.session = session_factory(profile_name=self.profile)
        self.clients: dict[tuple[str, str], Any] = {}
        self.stats = ApiCallStats()
        self.client_config = BotocoreConfig(
            retries={"mode": "standard", "total_max_attempts": 1},
            user_agent_extra="dyec-api-call-audit/1",
        )

    def _client(self, service: str, region: str) -> Any:
        key = (service, region)
        if key not in self.clients:
            self.clients[key] = self.session.client(
                service,
                region_name=region,
                config=self.client_config,
            )
        return self.clients[key]

    def call(
        self,
        *,
        service: str,
        region: str,
        operation: str,
        parameters: Optional[Mapping[str, Any]] = None,
        paid: bool = False,
    ) -> dict[str, Any]:
        request = AwsRequest(
            profile=self.profile,
            account_id=self.account_id,
            service=service,
            region=region,
            operation=operation,
            parameters=dict(parameters or {}),
        )
        lookup = self.cache.lookup(request)
        self.stats.cache_paths.add(str(lookup.path))
        if not self.refresh and lookup.response is not None:
            self.stats.cache_hits += 1
            self.stats.cache_hits_by_service_operation[(service, operation)] += 1
            return lookup.response
        self.stats.cache_misses += 1
        if lookup.status == "stale":
            self.stats.cache_stale += 1
        if self.cache_only:
            raise CacheMissError(
                f"Cache-only request is {lookup.status}: {service}.{operation} {lookup.path}"
            )
        if paid and self.stats.paid_live_calls >= self.paid_call_budget:
            raise PaidCallBudgetExceeded(
                f"Paid call budget {self.paid_call_budget} would be exceeded by "
                f"{service}.{operation}"
            )
        self.limiter.wait(service)
        client = self._client(service, region)
        method = getattr(client, operation, None)
        if method is None or not callable(method):
            raise ApiCallAuditError(f"AWS client has no callable {service}.{operation}")
        response = method(**dict(parameters or {}))
        if not isinstance(response, MutableMapping):
            raise ApiCallAuditError(f"AWS {service}.{operation} returned non-mapping response")
        self.stats.live_calls += 1
        self.stats.calls_by_service_operation[(service, operation)] += 1
        if paid:
            self.stats.paid_live_calls += 1
        self.cache.store(request, response)
        normalized_response = _jsonable(response)
        if not isinstance(normalized_response, dict):
            raise ApiCallAuditError(
                f"AWS {service}.{operation} response did not normalize to a JSON object"
            )
        return normalized_response


@dataclass(frozen=True)
class ApiCallAuditConfig:
    profile: str
    account_id: str
    start_date: date
    end_date: date
    trail_region: str
    resource_regions: tuple[str, ...]
    output_dir: Path
    cache_dir: Path
    cache_max_age_seconds: float = DEFAULT_CACHE_MAX_AGE_SECONDS
    cloudtrail_slices_per_day: int = 4
    cloudtrail_events_per_slice: int = 25
    top_source_ips: int = 5
    top_principals: int = 3
    paid_call_budget: int = 1
    cache_only: bool = False
    refresh: bool = False
    ce_min_interval_seconds: float = DEFAULT_CE_MIN_INTERVAL_SECONDS
    cloudtrail_min_interval_seconds: float = DEFAULT_CLOUDTRAIL_MIN_INTERVAL_SECONDS
    other_min_interval_seconds: float = DEFAULT_OTHER_MIN_INTERVAL_SECONDS

    def validate(self) -> None:
        if not self.profile.strip():
            raise ValueError("profile is required")
        if not re.fullmatch(r"\d{12}", self.account_id.strip()):
            raise ValueError("account_id must contain exactly 12 digits")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if not self.trail_region.strip():
            raise ValueError("trail_region is required")
        if not self.resource_regions:
            raise ValueError("at least one resource region is required")
        if self.cloudtrail_slices_per_day <= 0 or 24 % self.cloudtrail_slices_per_day != 0:
            raise ValueError("cloudtrail_slices_per_day must be a positive divisor of 24")
        if not 1 <= self.cloudtrail_events_per_slice <= 50:
            raise ValueError("cloudtrail_events_per_slice must be between 1 and 50")
        if self.top_source_ips < 0 or self.top_principals < 0:
            raise ValueError("top source/principal counts must be non-negative")
        if self.cache_max_age_seconds < 0:
            raise ValueError("cache_max_age_seconds must be non-negative")
        if self.paid_call_budget < 0:
            raise ValueError("paid_call_budget must be non-negative")
        if self.paid_call_budget > MAX_AUDIT_PAID_CALLS_AT_OBSERVED_RATE:
            raise ValueError(
                f"paid_call_budget may not exceed {MAX_AUDIT_PAID_CALLS_AT_OBSERVED_RATE}"
            )
        if self.cache_only and self.refresh:
            raise ValueError("cache_only and refresh are mutually exclusive")
        for label, value in (
            ("ce_min_interval_seconds", self.ce_min_interval_seconds),
            ("cloudtrail_min_interval_seconds", self.cloudtrail_min_interval_seconds),
            ("other_min_interval_seconds", self.other_min_interval_seconds),
        ):
            if value < 0:
                raise ValueError(f"{label} must be non-negative")


def _mapping_value(payload: Any, *names: str) -> Any:
    if not isinstance(payload, Mapping):
        return None
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _event_request_parameters(detail: Mapping[str, Any]) -> dict[str, Any]:
    raw = _mapping_value(detail, "requestParameters")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _user_agent_family(user_agent: str) -> str:
    text = str(user_agent or "").strip()
    if not text:
        return "unknown"
    match = re.match(r"^([^\s]+)", text)
    return match.group(1) if match else text


def _parse_cloudtrail_event(event: Mapping[str, Any], slice_start: datetime) -> dict[str, Any]:
    raw_detail = event.get("CloudTrailEvent") or "{}"
    try:
        detail = json.loads(raw_detail) if isinstance(raw_detail, str) else dict(raw_detail)
    except (json.JSONDecodeError, TypeError, ValueError):
        detail = {}
    identity = _mapping_value(detail, "userIdentity") or {}
    request = _event_request_parameters(detail)
    time_period = _mapping_value(request, "timePeriod") or {}
    group_by = _mapping_value(request, "groupBy") or []
    group_one = group_by[0] if isinstance(group_by, list) and len(group_by) > 0 else {}
    group_two = group_by[1] if isinstance(group_by, list) and len(group_by) > 1 else {}
    metrics = _mapping_value(request, "metrics") or []
    access_key = str(_mapping_value(identity, "accessKeyId") or "")
    user_agent = str(_mapping_value(detail, "userAgent") or "")
    return {
        "sample_slice_start": slice_start.isoformat().replace("+00:00", "Z"),
        "event_time": str(_mapping_value(detail, "eventTime") or event.get("EventTime") or ""),
        "event_name": str(_mapping_value(detail, "eventName") or event.get("EventName") or ""),
        "principal_arn": str(_mapping_value(identity, "arn") or ""),
        "user_name": str(event.get("Username") or _mapping_value(identity, "userName") or ""),
        "access_key_suffix": access_key[-4:] if access_key else "",
        "source_ip": str(_mapping_value(detail, "sourceIPAddress") or ""),
        "user_agent": user_agent,
        "user_agent_family": _user_agent_family(user_agent),
        "start_date": str(_mapping_value(time_period, "start") or ""),
        "end_date": str(_mapping_value(time_period, "end") or ""),
        "granularity": str(_mapping_value(request, "granularity") or ""),
        "metric": ",".join(str(item) for item in metrics) if isinstance(metrics, list) else "",
        "group_one_type": str(_mapping_value(group_one, "type") or ""),
        "group_one_key": str(_mapping_value(group_one, "key") or ""),
        "group_two_type": str(_mapping_value(group_two, "type") or ""),
        "group_two_key": str(_mapping_value(group_two, "key") or ""),
    }


def _cost_operation_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in payload.get("ResultsByTime", []):
        if not isinstance(period, Mapping):
            continue
        for group in period.get("Groups", []):
            if not isinstance(group, Mapping):
                continue
            metrics = group.get("Metrics") or {}
            cost = metrics.get("UnblendedCost") or {}
            usage = metrics.get("UsageQuantity") or {}
            operation = str((group.get("Keys") or [""])[0])
            quantity = float(usage.get("Amount") or 0)
            rows.append(
                {
                    "date": str((period.get("TimePeriod") or {}).get("Start") or ""),
                    "operation": operation,
                    "usage_quantity": quantity,
                    "request_count": int(round(quantity)) if operation.startswith(("Get", "List")) else 0,
                    "cost_usd": float(cost.get("Amount") or 0),
                    "estimated": bool(period.get("Estimated")),
                }
            )
    return rows


def _summary_rows(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> list[dict[str, Any]]:
    counts = Counter(tuple(str(row.get(field) or "") for field in fields) for row in rows)
    total = len(rows)
    output: list[dict[str, Any]] = []
    for key, count in counts.most_common():
        item: dict[str, Any] = {field: key[index] for index, field in enumerate(fields)}
        item["sample_events"] = count
        item["sample_share_pct"] = round(count / total * 100, 2) if total else 0.0
        output.append(item)
    return output


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
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


def _instance_from_response(payload: Mapping[str, Any]) -> dict[str, Any]:
    reservations = payload.get("Reservations") or []
    if not reservations or not isinstance(reservations[0], Mapping):
        return {}
    instances = reservations[0].get("Instances") or []
    return dict(instances[0]) if instances and isinstance(instances[0], Mapping) else {}


def _tags_map(tags: Any) -> dict[str, str]:
    return {
        str(item.get("Key")): str(item.get("Value") or "")
        for item in tags or []
        if isinstance(item, Mapping) and item.get("Key")
    }


def _map_source_ips(
    reader: CachedAwsReader,
    source_rows: Sequence[Mapping[str, Any]],
    resource_regions: Sequence[str],
    limit: int,
) -> list[dict[str, Any]]:
    origins: list[dict[str, Any]] = []
    for source_row in source_rows[:limit]:
        source_ip = str(source_row.get("source_ip") or "")
        if not source_ip or not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", source_ip):
            continue
        matches = 0
        for region in resource_regions:
            address_payload = reader.call(
                service="ec2",
                region=region,
                operation="describe_addresses",
                parameters={"PublicIps": [source_ip]},
            )
            for address in address_payload.get("Addresses", []):
                if not isinstance(address, Mapping):
                    continue
                matches += 1
                instance_id = str(address.get("InstanceId") or "")
                instance: dict[str, Any] = {}
                if instance_id:
                    instance = _instance_from_response(
                        reader.call(
                            service="ec2",
                            region=region,
                            operation="describe_instances",
                            parameters={"InstanceIds": [instance_id]},
                        )
                    )
                tags = _tags_map(instance.get("Tags"))
                origins.append(
                    {
                        "source_ip": source_ip,
                        "sample_events": int(source_row.get("sample_events") or 0),
                        "sample_share_pct": float(source_row.get("sample_share_pct") or 0),
                        "region": region,
                        "allocation_id": str(address.get("AllocationId") or ""),
                        "network_interface_id": str(address.get("NetworkInterfaceId") or ""),
                        "private_ip": str(address.get("PrivateIpAddress") or ""),
                        "instance_id": instance_id,
                        "instance_state": str((instance.get("State") or {}).get("Name") or ""),
                        "instance_type": str(instance.get("InstanceType") or ""),
                        "instance_name": tags.get("Name", ""),
                        "stack": tags.get("aws:cloudformation:stack-name", ""),
                        "environment": tags.get("Environment", ""),
                        "project": tags.get("Project", tags.get("project", "")),
                        "roles": tags.get("Roles", ""),
                    }
                )
        if matches == 0:
            origins.append(
                {
                    "source_ip": source_ip,
                    "sample_events": int(source_row.get("sample_events") or 0),
                    "sample_share_pct": float(source_row.get("sample_share_pct") or 0),
                    "region": "",
                    "allocation_id": "",
                    "network_interface_id": "",
                    "private_ip": "",
                    "instance_id": "",
                    "instance_state": "not_mapped_in_requested_regions",
                    "instance_type": "",
                    "instance_name": "",
                    "stack": "",
                    "environment": "",
                    "project": "",
                    "roles": "",
                }
            )
    return origins


def _map_iam_principals(
    reader: CachedAwsReader,
    principal_rows: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for principal_row in principal_rows[:limit]:
        arn = str(principal_row.get("principal_arn") or "")
        match = re.fullmatch(r"arn:aws:iam::\d{12}:user/(.+)", arn)
        if not match:
            continue
        user_name = match.group(1).rsplit("/", 1)[-1]
        user_payload = reader.call(
            service="iam",
            region=DEFAULT_BILLING_REGION,
            operation="get_user",
            parameters={"UserName": user_name},
        )
        keys_payload = reader.call(
            service="iam",
            region=DEFAULT_BILLING_REGION,
            operation="list_access_keys",
            parameters={"UserName": user_name},
        )
        observed_suffixes = {
            str(event.get("access_key_suffix") or "")
            for event in events
            if event.get("principal_arn") == arn and event.get("access_key_suffix")
        }
        user = user_payload.get("User") or {}
        for key in keys_payload.get("AccessKeyMetadata", []):
            if not isinstance(key, Mapping):
                continue
            key_id = str(key.get("AccessKeyId") or "")
            suffix = key_id[-4:] if key_id else ""
            if suffix not in observed_suffixes:
                continue
            last_used = reader.call(
                service="iam",
                region=DEFAULT_BILLING_REGION,
                operation="get_access_key_last_used",
                parameters={"AccessKeyId": key_id},
            ).get("AccessKeyLastUsed") or {}
            output.append(
                {
                    "principal_arn": arn,
                    "user_name": user_name,
                    "sample_events": int(principal_row.get("sample_events") or 0),
                    "sample_share_pct": float(principal_row.get("sample_share_pct") or 0),
                    "user_created_at": str(user.get("CreateDate") or ""),
                    "access_key_suffix": suffix,
                    "access_key_status": str(key.get("Status") or ""),
                    "access_key_created_at": str(key.get("CreateDate") or ""),
                    "last_used_at": str(last_used.get("LastUsedDate") or ""),
                    "last_used_service": str(last_used.get("ServiceName") or ""),
                    "last_used_region": str(last_used.get("Region") or ""),
                }
            )
    return output


def run_api_call_audit(
    config: ApiCallAuditConfig,
    *,
    session_factory: Callable[..., Any] = boto3.Session,
    now: Callable[[], datetime] = _utc_now,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run the bounded read-only attribution audit and write reproducible outputs."""

    config.validate()
    cache = ExactRequestCache(
        config.cache_dir,
        max_age_seconds=config.cache_max_age_seconds,
        now=now,
    )
    limiter = ServiceRateLimiter(
        {
            "ce": config.ce_min_interval_seconds,
            "cloudtrail": config.cloudtrail_min_interval_seconds,
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
        region=config.trail_region,
        operation="get_caller_identity",
    )
    resolved_account = str(identity.get("Account") or "")
    if resolved_account != config.account_id:
        raise ApiCallAuditError(
            f"AWS profile {config.profile!r} resolved to account {resolved_account!r}; "
            f"expected {config.account_id!r}"
        )
    cost_payload = reader.call(
        service="ce",
        region=DEFAULT_BILLING_REGION,
        operation="get_cost_and_usage",
        paid=True,
        parameters={
            "TimePeriod": {
                "Start": config.start_date.isoformat(),
                "End": config.end_date.isoformat(),
            },
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost", "UsageQuantity"],
            "Filter": {
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": [DEFAULT_BILLING_SERVICE],
                }
            },
            "GroupBy": [{"Type": "DIMENSION", "Key": "OPERATION"}],
        },
    )
    operation_rows = _cost_operation_rows(cost_payload)

    event_rows: list[dict[str, Any]] = []
    slice_hours = 24 // config.cloudtrail_slices_per_day
    day = config.start_date
    while day < config.end_date:
        for slice_index in range(config.cloudtrail_slices_per_day):
            slice_start = datetime.combine(
                day,
                datetime_time(slice_index * slice_hours),
                tzinfo=timezone.utc,
            )
            slice_end = slice_start + timedelta(hours=slice_hours)
            payload = reader.call(
                service="cloudtrail",
                region=config.trail_region,
                operation="lookup_events",
                parameters={
                    "LookupAttributes": [
                        {"AttributeKey": "EventSource", "AttributeValue": DEFAULT_EVENT_SOURCE}
                    ],
                    "StartTime": slice_start,
                    "EndTime": slice_end,
                    "MaxResults": config.cloudtrail_events_per_slice,
                },
            )
            for event in payload.get("Events", []):
                if isinstance(event, Mapping):
                    event_rows.append(_parse_cloudtrail_event(event, slice_start))
        day += timedelta(days=1)

    principal_rows = _summary_rows(event_rows, ("principal_arn", "user_name"))
    source_ip_rows = _summary_rows(event_rows, ("source_ip",))
    caller_rows = _summary_rows(
        event_rows,
        ("principal_arn", "user_name", "source_ip", "user_agent_family", "event_name"),
    )
    request_shape_rows = _summary_rows(
        event_rows,
        (
            "event_name",
            "granularity",
            "metric",
            "group_one_type",
            "group_one_key",
            "group_two_type",
            "group_two_key",
        ),
    )
    origin_rows = _map_source_ips(
        reader,
        source_ip_rows,
        config.resource_regions,
        config.top_source_ips,
    )
    iam_rows = _map_iam_principals(
        reader,
        principal_rows,
        event_rows,
        config.top_principals,
    )

    operation_totals: dict[str, dict[str, Any]] = {}
    for row in operation_rows:
        operation = str(row["operation"])
        total = operation_totals.setdefault(
            operation,
            {"operation": operation, "request_count": 0, "usage_quantity": 0.0, "cost_usd": 0.0},
        )
        total["request_count"] += int(row["request_count"])
        total["usage_quantity"] += float(row["usage_quantity"])
        total["cost_usd"] += float(row["cost_usd"])
    operation_total_rows = sorted(
        operation_totals.values(),
        key=lambda row: (-float(row["cost_usd"]), str(row["operation"])),
    )
    for row in operation_total_rows:
        row["cost_usd"] = round(float(row["cost_usd"]), 6)
        row["usage_quantity"] = round(float(row["usage_quantity"]), 6)

    generated_at = now().isoformat().replace("+00:00", "Z")
    cache_stats = reader.stats.to_dict(limiter.total_sleep_seconds)
    summary = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "mode": "read_only",
        "profile": config.profile,
        "account_id": config.account_id,
        "caller_identity": {
            "account": str(identity.get("Account") or ""),
            "arn": str(identity.get("Arn") or ""),
            "user_id": str(identity.get("UserId") or ""),
        },
        "window": {
            "start": config.start_date.isoformat(),
            "end_exclusive": config.end_date.isoformat(),
        },
        "cloudtrail_sample": {
            "event_source": DEFAULT_EVENT_SOURCE,
            "trail_region": config.trail_region,
            "slices_per_day": config.cloudtrail_slices_per_day,
            "events_per_slice_limit": config.cloudtrail_events_per_slice,
            "sample_events": len(event_rows),
            "sample_slices": (config.end_date - config.start_date).days
            * config.cloudtrail_slices_per_day,
        },
        "cost_explorer_operation_totals": operation_total_rows,
        "billed_api_requests": sum(int(row["request_count"]) for row in operation_total_rows),
        "billed_api_cost_usd": round(
            sum(float(row["cost_usd"]) for row in operation_total_rows if int(row["request_count"])),
            6,
        ),
        "top_principals": principal_rows[: config.top_principals],
        "top_source_ips": source_ip_rows[: config.top_source_ips],
        "mapped_origins": origin_rows,
        "iam_principals": iam_rows,
        "request_reuse": cache_stats,
        "paid_call_guard": {
            "hard_ceiling_usd_at_observed_rate": MAX_AUDIT_PAID_COST_USD,
            "observed_request_rate_usd": OBSERVED_COST_EXPLORER_REQUEST_USD,
            "configured_call_budget": config.paid_call_budget,
            "configured_budget_usd_at_observed_rate": round(
                config.paid_call_budget * OBSERVED_COST_EXPLORER_REQUEST_USD,
                2,
            ),
            "sdk_total_max_attempts": 1,
        },
        "output_files": {
            "summary": "summary.json",
            "operation_daily": "cost_explorer_operation_daily.csv",
            "cloudtrail_sample": "cloudtrail_sample.csv",
            "principal_summary": "principal_summary.csv",
            "source_ip_summary": "source_ip_summary.csv",
            "caller_summary": "caller_summary.csv",
            "request_shapes": "request_shapes.csv",
            "mapped_origins": "mapped_origins.csv",
            "iam_principals": "iam_principals.csv",
        },
    }

    output_dir = Path(config.output_dir).expanduser().resolve()
    _write_csv(output_dir / "cost_explorer_operation_daily.csv", operation_rows)
    _write_csv(output_dir / "cloudtrail_sample.csv", event_rows)
    _write_csv(output_dir / "principal_summary.csv", principal_rows)
    _write_csv(output_dir / "source_ip_summary.csv", source_ip_rows)
    _write_csv(output_dir / "caller_summary.csv", caller_rows)
    _write_csv(output_dir / "request_shapes.csv", request_shape_rows)
    _write_csv(output_dir / "mapped_origins.csv", origin_rows)
    _write_csv(output_dir / "iam_principals.csv", iam_rows)
    _write_json(output_dir / "summary.json", summary)
    return summary


__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "CACHE_SCHEMA_VERSION",
    "MAX_AUDIT_PAID_CALLS_AT_OBSERVED_RATE",
    "MAX_AUDIT_PAID_COST_USD",
    "ApiCallAuditConfig",
    "ApiCallAuditError",
    "CacheEntryError",
    "CacheMissError",
    "CachedAwsReader",
    "ExactRequestCache",
    "PaidCallBudgetExceeded",
    "ServiceRateLimiter",
    "run_api_call_audit",
]
