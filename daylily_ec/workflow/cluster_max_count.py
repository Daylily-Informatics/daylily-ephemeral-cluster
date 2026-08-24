"""Guarded public update of every ParallelCluster compute-resource MaxCount."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml

from daylily_ec.pcluster.runner import describe_cluster, update_cluster
from daylily_ec.workflow.compute_fleet import ClusterIdleProof, probe_cluster_idle

CLUSTER_MAX_COUNT_SCHEMA = "dyec.cluster_max_count.v1"
MAX_CONFIGURATION_BYTES = 4 * 1024 * 1024
STABLE_SOURCE_STATES = frozenset({"CREATE_COMPLETE", "UPDATE_COMPLETE"})
UPDATE_PROGRESS_STATES = frozenset(
    {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_IN_PROGRESS",
        "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
    }
)
UPDATE_FAILURE_STATES = frozenset(
    {
        "UPDATE_FAILED",
        "UPDATE_ROLLBACK_IN_PROGRESS",
        "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
        "UPDATE_ROLLBACK_COMPLETE",
        "UPDATE_ROLLBACK_FAILED",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ClusterMaxCountError(RuntimeError):
    """Raised when an exact all-resource MaxCount update cannot proceed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "")
    if not text or text != text.strip():
        raise ClusterMaxCountError(f"{field} must be a non-empty trimmed string.")
    return text


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ClusterMaxCountError(f"{field} must be a positive integer.")
    return value


def _configuration_url(details: Mapping[str, Any]) -> str:
    reference = details.get("clusterConfiguration")
    raw_url = str(reference.get("url") or "") if isinstance(reference, Mapping) else ""
    parsed = urlparse(raw_url)
    hostname = str(parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname.endswith(".amazonaws.com"):
        raise ClusterMaxCountError("The cluster configuration reference is unavailable or invalid.")
    return raw_url


def download_cluster_configuration(
    details: Mapping[str, Any],
    *,
    request_get: Callable[..., Any] = requests.get,
) -> tuple[dict[str, Any], bytes, str]:
    """Download and parse the exact live ParallelCluster configuration."""

    try:
        response = request_get(
            _configuration_url(details),
            timeout=30,
            allow_redirects=False,
        )
        response.raise_for_status()
    except requests.RequestException:
        raise ClusterMaxCountError("The cluster configuration download failed.") from None
    content = bytes(response.content)
    if not content or len(content) > MAX_CONFIGURATION_BYTES:
        raise ClusterMaxCountError("The cluster configuration size is invalid.")
    try:
        decoded = yaml.safe_load(content)
    except yaml.YAMLError:
        raise ClusterMaxCountError("The cluster configuration YAML is invalid.") from None
    if not isinstance(decoded, dict):
        raise ClusterMaxCountError("The cluster configuration must be a mapping.")
    return decoded, content, hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class ComputeResourceMaxCount:
    queue: str
    resource: str
    before: int
    after: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "queue": self.queue,
            "resource": self.resource,
            "before": self.before,
            "after": self.after,
        }


def _compute_resources(
    configuration: Mapping[str, Any],
) -> list[tuple[str, str, Mapping[str, Any]]]:
    scheduling = configuration.get("Scheduling")
    queues = scheduling.get("SlurmQueues") if isinstance(scheduling, Mapping) else None
    if not isinstance(queues, list) or not queues:
        raise ClusterMaxCountError("Scheduling.SlurmQueues must be a non-empty list.")
    rows: list[tuple[str, str, Mapping[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for queue in queues:
        if not isinstance(queue, Mapping):
            raise ClusterMaxCountError("Every SlurmQueues entry must be a mapping.")
        queue_name = _required_text(queue.get("Name"), field="SlurmQueues[].Name")
        resources = queue.get("ComputeResources")
        if not isinstance(resources, list) or not resources:
            raise ClusterMaxCountError(
                f"Slurm queue {queue_name!r} must have a non-empty ComputeResources list."
            )
        for resource in resources:
            if not isinstance(resource, Mapping):
                raise ClusterMaxCountError("Every ComputeResources entry must be a mapping.")
            resource_name = _required_text(resource.get("Name"), field="ComputeResources[].Name")
            identity = (queue_name, resource_name)
            if identity in seen:
                raise ClusterMaxCountError(
                    f"Duplicate compute-resource identity {queue_name}/{resource_name}."
                )
            seen.add(identity)
            rows.append((queue_name, resource_name, resource))
    return rows


def build_max_count_configuration(
    source: Mapping[str, Any],
    *,
    max_count: int,
    expected_resource_count: int,
) -> tuple[dict[str, Any], tuple[ComputeResourceMaxCount, ...]]:
    """Return a deep copy whose only semantic changes are resource MaxCount values."""

    target = _positive_int(max_count, field="max_count")
    expected = _positive_int(expected_resource_count, field="expected_resource_count")
    updated = copy.deepcopy(dict(source))
    resources = _compute_resources(updated)
    if len(resources) != expected:
        raise ClusterMaxCountError(
            f"Expected exactly {expected} compute resources, found {len(resources)}."
        )
    changes: list[ComputeResourceMaxCount] = []
    for queue_name, resource_name, resource in resources:
        before = resource.get("MaxCount")
        minimum = resource.get("MinCount", 0)
        if isinstance(before, bool) or not isinstance(before, int) or before < 0:
            raise ClusterMaxCountError(f"{queue_name}/{resource_name} has an invalid MaxCount.")
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
            raise ClusterMaxCountError(f"{queue_name}/{resource_name} has an invalid MinCount.")
        if minimum > target:
            raise ClusterMaxCountError(
                f"{queue_name}/{resource_name} MinCount {minimum} exceeds requested MaxCount {target}."
            )
        if before == target:
            raise ClusterMaxCountError(
                f"{queue_name}/{resource_name} already has MaxCount {target}; "
                "the exact source baseline has drifted from this requested change set."
            )
        resource["MaxCount"] = target
        changes.append(
            ComputeResourceMaxCount(
                queue=queue_name,
                resource=resource_name,
                before=before,
                after=target,
            )
        )
    return updated, tuple(changes)


def _verify_target_configuration(
    configuration: Mapping[str, Any],
    *,
    expected_configuration: Mapping[str, Any],
    max_count: int,
    expected_resource_count: int,
) -> bool:
    if configuration != expected_configuration:
        return False
    resources = _compute_resources(configuration)
    return len(resources) == expected_resource_count and all(
        resource.get("MaxCount") == max_count for _queue, _name, resource in resources
    )


def _describe(
    *,
    cluster_name: str,
    region: str,
    profile: str,
    pcluster_executable: str,
) -> dict[str, Any]:
    try:
        result = describe_cluster(
            cluster_name,
            region,
            profile=profile,
            executable=pcluster_executable,
        )
    except Exception:  # noqa: BLE001 - provider failures are normalized at this boundary
        raise ClusterMaxCountError("Could not describe the exact cluster.") from None
    if not result.success or not isinstance(result.json_body, dict):
        raise ClusterMaxCountError("Could not describe the exact cluster.")
    if result.json_body.get("clusterName") != cluster_name:
        raise ClusterMaxCountError("The provider response returned a different cluster identity.")
    return result.json_body


def _wait_for_update(
    *,
    cluster_name: str,
    region: str,
    profile: str,
    pcluster_executable: str,
    expected_configuration: Mapping[str, Any],
    max_count: int,
    expected_resource_count: int,
    timeout_seconds: float,
    poll_interval_seconds: float,
    describe_fn: Callable[..., dict[str, Any]] = _describe,
    download_fn: Callable[..., tuple[dict[str, Any], bytes, str]] = download_cluster_configuration,
    monotonic_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[str, float, str]:
    start = monotonic_fn()
    while True:
        details = describe_fn(
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
        )
        status = str(details.get("clusterStatus") or "")
        if status in UPDATE_FAILURE_STATES:
            raise ClusterMaxCountError(f"Cluster update entered terminal state {status}.")
        if status not in UPDATE_PROGRESS_STATES:
            raise ClusterMaxCountError(
                f"Cluster entered unexpected state {status or 'UNKNOWN'} during update."
            )
        configuration, _content, source_sha256 = download_fn(details)
        if status == "UPDATE_COMPLETE" and _verify_target_configuration(
            configuration,
            expected_configuration=expected_configuration,
            max_count=max_count,
            expected_resource_count=expected_resource_count,
        ):
            return status, max(0.0, monotonic_fn() - start), source_sha256
        elapsed = max(0.0, monotonic_fn() - start)
        if elapsed >= timeout_seconds:
            raise ClusterMaxCountError(
                "Timed out waiting for UPDATE_COMPLETE with the exact requested configuration."
            )
        sleep_fn(min(poll_interval_seconds, max(0.0, timeout_seconds - elapsed)))


@dataclass(frozen=True)
class ClusterMaxCountResult:
    cluster: str
    region: str
    max_count: int
    expected_resource_count: int
    dry_run_only: bool
    source_configuration_sha256: str
    update_configuration_sha256: str
    final_configuration_sha256: str | None
    initial_cluster_status: str
    final_cluster_status: str
    provider_dry_run_validated: bool
    update_submitted: bool
    idle_proof: ClusterIdleProof | None
    changes: tuple[ComputeResourceMaxCount, ...]
    update_config_path: str
    started_at: str
    completed_at: str
    elapsed_seconds: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": CLUSTER_MAX_COUNT_SCHEMA,
            "ok": True,
            "cluster": self.cluster,
            "region": self.region,
            "max_count": self.max_count,
            "expected_resource_count": self.expected_resource_count,
            "dry_run_only": self.dry_run_only,
            "source_configuration_sha256": self.source_configuration_sha256,
            "update_configuration_sha256": self.update_configuration_sha256,
            "final_configuration_sha256": self.final_configuration_sha256,
            "initial_cluster_status": self.initial_cluster_status,
            "final_cluster_status": self.final_cluster_status,
            "provider_dry_run_validated": self.provider_dry_run_validated,
            "update_submitted": self.update_submitted,
            "idle_proof": self.idle_proof.to_payload() if self.idle_proof else None,
            "changes": [change.to_payload() for change in self.changes],
            "update_config_path": self.update_config_path,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


def _prepare_output_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists() and any(resolved.iterdir()):
        raise ClusterMaxCountError("output_dir must be absent or empty.")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def run_cluster_max_count_update(
    *,
    cluster_name: str,
    region: str,
    profile: str,
    max_count: int,
    expected_resource_count: int,
    expected_source_sha256: str,
    expected_cluster_status: str,
    output_dir: Path,
    apply: bool,
    timeout_seconds: float,
    poll_interval_seconds: float,
    pcluster_executable: str = "pcluster",
    describe_fn: Callable[..., dict[str, Any]] = _describe,
    download_fn: Callable[..., tuple[dict[str, Any], bytes, str]] = download_cluster_configuration,
    update_fn: Callable[..., Any] = update_cluster,
    idle_probe_fn: Callable[..., ClusterIdleProof] = probe_cluster_idle,
    wait_fn: Callable[..., tuple[str, float, str]] = _wait_for_update,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> ClusterMaxCountResult:
    """Dry-run, optionally submit, and verify an exact all-resource update."""

    cluster_name = _required_text(cluster_name, field="cluster")
    region = _required_text(region, field="region")
    profile = _required_text(profile, field="profile")
    pcluster_executable = _required_text(pcluster_executable, field="pcluster_executable")
    max_count = _positive_int(max_count, field="max_count")
    expected_resource_count = _positive_int(
        expected_resource_count, field="expected_resource_count"
    )
    expected_cluster_status = _required_text(
        expected_cluster_status, field="expected_cluster_status"
    )
    if expected_cluster_status not in STABLE_SOURCE_STATES:
        raise ClusterMaxCountError(
            "expected_cluster_status must be exactly CREATE_COMPLETE or UPDATE_COMPLETE."
        )
    expected_source_sha256 = str(expected_source_sha256 or "").strip().lower()
    if not _SHA256_RE.fullmatch(expected_source_sha256):
        raise ClusterMaxCountError("expected_source_sha256 must be 64 lowercase hex characters.")
    if timeout_seconds <= 0 or poll_interval_seconds <= 0:
        raise ClusterMaxCountError("Timeout and poll interval must both be greater than zero.")

    started_at = _utc_now()
    started = monotonic_fn()
    destination = _prepare_output_dir(output_dir)
    details = describe_fn(
        cluster_name=cluster_name,
        region=region,
        profile=profile,
        pcluster_executable=pcluster_executable,
    )
    initial_status = str(details.get("clusterStatus") or "")
    if initial_status != expected_cluster_status:
        raise ClusterMaxCountError(
            f"Expected cluster state {expected_cluster_status}, found {initial_status or 'UNKNOWN'}."
        )
    source, _source_bytes, source_sha256 = download_fn(details)
    if source_sha256 != expected_source_sha256:
        raise ClusterMaxCountError(
            "The live cluster configuration SHA-256 does not match the approved source baseline."
        )
    updated, changes = build_max_count_configuration(
        source,
        max_count=max_count,
        expected_resource_count=expected_resource_count,
    )
    update_bytes = yaml.safe_dump(updated, sort_keys=False, default_flow_style=False).encode(
        "utf-8"
    )
    update_sha256 = hashlib.sha256(update_bytes).hexdigest()
    update_path = destination / "cluster_max_count_update.yaml"
    update_path.write_bytes(update_bytes)
    os.chmod(update_path, 0o600)

    dry_run = update_fn(
        cluster_name,
        str(update_path),
        region,
        profile=profile,
        dry_run=True,
        executable=pcluster_executable,
    )
    if not dry_run.success:
        raise ClusterMaxCountError("ParallelCluster rejected the exact MaxCount update dry run.")

    idle_proof: ClusterIdleProof | None = None
    final_status = initial_status
    final_sha256: str | None = None
    wait_elapsed = 0.0
    if apply:
        idle_proof = idle_probe_fn(
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
            timeout=max(1, min(int(timeout_seconds), 180)),
        )
        if not idle_proof.idle:
            raise ClusterMaxCountError(
                "Cluster update refused because active controllers or Slurm jobs remain "
                f"(controllers={idle_proof.controller_count}, jobs={idle_proof.slurm_job_count})."
            )
        recheck_details = describe_fn(
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
        )
        if str(recheck_details.get("clusterStatus") or "") != expected_cluster_status:
            raise ClusterMaxCountError("Cluster state changed after the idle proof.")
        recheck_source, _recheck_bytes, recheck_sha256 = download_fn(recheck_details)
        if recheck_sha256 != expected_source_sha256 or recheck_source != source:
            raise ClusterMaxCountError("Cluster configuration changed after the dry run.")
        submitted = update_fn(
            cluster_name,
            str(update_path),
            region,
            profile=profile,
            dry_run=False,
            executable=pcluster_executable,
        )
        if not submitted.success:
            raise ClusterMaxCountError("ParallelCluster did not accept the MaxCount update.")
        final_status, wait_elapsed, final_sha256 = wait_fn(
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
            expected_configuration=updated,
            max_count=max_count,
            expected_resource_count=expected_resource_count,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    result = ClusterMaxCountResult(
        cluster=cluster_name,
        region=region,
        max_count=max_count,
        expected_resource_count=expected_resource_count,
        dry_run_only=not apply,
        source_configuration_sha256=source_sha256,
        update_configuration_sha256=update_sha256,
        final_configuration_sha256=final_sha256,
        initial_cluster_status=initial_status,
        final_cluster_status=final_status,
        provider_dry_run_validated=True,
        update_submitted=apply,
        idle_proof=idle_proof,
        changes=changes,
        update_config_path=str(update_path),
        started_at=started_at,
        completed_at=_utc_now(),
        elapsed_seconds=max(wait_elapsed, max(0.0, monotonic_fn() - started)),
    )
    receipt_path = destination / "cluster_max_count_receipt.json"
    receipt_path.write_text(
        json.dumps(result.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
