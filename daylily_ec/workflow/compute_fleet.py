"""Public DYEC compute-fleet lifecycle orchestration.

The public CLI owns every underlying ParallelCluster invocation.  A stop
request is guarded by an authoritative, read-only inventory of DayOA
controllers and all Slurm jobs.  ``drain`` means wait for that inventory to
become empty naturally; it never changes Slurm or controller state.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from daylily_ec.aws.ssm import run_shell, wait_for_ssm_online
from daylily_ec.headnode_control import (
    build_controller_inventory_script,
    parse_controller_inventory_output,
)
from daylily_ec.pcluster.monitor import wait_for_compute_fleet
from daylily_ec.pcluster.runner import (
    describe_cluster,
    describe_compute_fleet,
    update_compute_fleet,
)

COMPUTE_FLEET_SCHEMA = "dyec.cluster_compute_fleet.v1"
CLUSTER_QUEUE_SCHEMA = "dyec.cluster_queue_idle_probe.v1"
CLUSTER_QUEUE_MARKER = "__DYEC_CLUSTER_QUEUE_IDLE_PROBE__="

REQUEST_TO_TARGET = {
    "STOP_REQUESTED": "STOPPED",
    "START_REQUESTED": "RUNNING",
}
REQUEST_PROGRESS_STATES = {
    "STOP_REQUESTED": frozenset({"STOP_REQUESTED", "STOPPING"}),
    "START_REQUESTED": frozenset({"START_REQUESTED", "STARTING"}),
}
KNOWN_FLEET_STATES = frozenset(
    {
        "RUNNING",
        "STOPPED",
        "STOP_REQUESTED",
        "STOPPING",
        "START_REQUESTED",
        "STARTING",
    }
)


class ComputeFleetOperationError(RuntimeError):
    """Raised when a public compute-fleet operation cannot proceed safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _positive_number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ComputeFleetOperationError(f"{field} must be greater than zero.")
    return float(value)


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "")
    if not text or text != text.strip():
        raise ComputeFleetOperationError(f"{field} must be a non-empty trimmed string.")
    return text


def build_cluster_queue_probe_script() -> str:
    """Return a bounded script that counts all Slurm jobs without job details."""

    return f"""set +e +u
set +o pipefail 2>/dev/null || true
if [[ "$(id -un)" != "ubuntu" ]]; then
  printf "DYEC cluster queue probe requires ubuntu\\n" >&2
  exit 91
fi
python3 - <<'PY'
import datetime
import json
import subprocess

MARKER = {CLUSTER_QUEUE_MARKER!r}
SCHEMA = {CLUSTER_QUEUE_SCHEMA!r}
try:
    result = subprocess.run(
        ["/opt/slurm/bin/squeue", "-h", "-o", "%T"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
except (OSError, subprocess.SubprocessError):
    result = None

states = {{}}
if result is not None and result.returncode == 0:
    for raw in result.stdout.splitlines():
        state = raw.strip().upper()[:64]
        if state:
            states[state] = states.get(state, 0) + 1
payload = {{
    "schema_version": SCHEMA,
    "ok": result is not None and result.returncode == 0,
    "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    ),
    "job_count": sum(states.values()),
    "state_counts": states,
    "error": None if result is not None and result.returncode == 0 else "squeue_failed",
}}
print(MARKER + json.dumps(payload, sort_keys=True, separators=(",", ":")))
raise SystemExit(0 if payload["ok"] else 1)
PY
"""


def parse_cluster_queue_probe_output(stdout: object) -> dict[str, Any]:
    """Parse exactly one bounded cluster-queue marker."""

    if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > 16 * 1024:
        raise ComputeFleetOperationError("Cluster queue probe output is invalid or oversized.")
    lines = [line for line in stdout.splitlines() if line.startswith(CLUSTER_QUEUE_MARKER)]
    if len(lines) != 1:
        raise ComputeFleetOperationError("Expected exactly one cluster queue probe marker.")
    try:
        payload = json.loads(lines[0][len(CLUSTER_QUEUE_MARKER) :])
    except json.JSONDecodeError:
        raise ComputeFleetOperationError("Cluster queue probe returned invalid JSON.") from None
    if not isinstance(payload, dict) or payload.get("schema_version") != CLUSTER_QUEUE_SCHEMA:
        raise ComputeFleetOperationError("Cluster queue probe returned the wrong schema.")
    if not isinstance(payload.get("ok"), bool):
        raise ComputeFleetOperationError("Cluster queue probe is missing its status.")
    job_count = payload.get("job_count")
    state_counts = payload.get("state_counts")
    if isinstance(job_count, bool) or not isinstance(job_count, int) or job_count < 0:
        raise ComputeFleetOperationError("Cluster queue probe returned an invalid job count.")
    if not isinstance(state_counts, dict) or not all(
        isinstance(key, str)
        and isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
        for key, value in state_counts.items()
    ):
        raise ComputeFleetOperationError("Cluster queue probe returned invalid state counts.")
    if sum(state_counts.values()) != job_count:
        raise ComputeFleetOperationError("Cluster queue probe counts are inconsistent.")
    return payload


@dataclass(frozen=True)
class ClusterIdleProof:
    """Bounded read-only proof used before a fleet stop."""

    authoritative: bool
    controller_count: int
    slurm_job_count: int
    observed_at: str
    instance_id: str
    ssm_command_ids: tuple[str, ...]

    @property
    def idle(self) -> bool:
        return self.authoritative and self.controller_count == 0 and self.slurm_job_count == 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "authoritative": self.authoritative,
            "controller_count": self.controller_count,
            "slurm_job_count": self.slurm_job_count,
            "observed_at": self.observed_at,
            "instance_id": self.instance_id,
            "ssm_command_ids": list(self.ssm_command_ids),
        }


def probe_cluster_idle(
    *,
    cluster_name: str,
    region: str,
    profile: str | None,
    pcluster_executable: str,
    timeout: int = 180,
) -> ClusterIdleProof:
    """Prove no live DayOA controller or Slurm job exists on a cluster."""

    try:
        described = describe_cluster(
            cluster_name,
            region,
            profile=profile,
            executable=_required_text(
                pcluster_executable,
                field="pcluster_executable",
            ),
        )
    except Exception:  # noqa: BLE001 - provider exceptions are normalized at this boundary
        raise ComputeFleetOperationError("Could not describe the cluster for idle proof.") from None
    if not described.success:
        raise ComputeFleetOperationError("Could not describe the cluster for idle proof.")
    head_node = described.json_body.get("headNode")
    instance_id = head_node.get("instanceId") if isinstance(head_node, dict) else None
    if not isinstance(instance_id, str) or not instance_id:
        raise ComputeFleetOperationError("The cluster description has no headnode identity.")

    try:
        wait_for_ssm_online(instance_id, region, profile=profile, timeout=min(timeout, 120))
        controller_result = run_shell(
            instance_id,
            region,
            build_controller_inventory_script(
                max_controllers=1,
                max_tmux_panes=1,
                max_slurm_jobs=1,
            ),
            profile=profile,
            as_user="ubuntu",
            timeout=timeout,
            comment="DYEC fleet-stop controller idle proof",
        )
        controller_payload = parse_controller_inventory_output(controller_result.stdout)
        queue_result = run_shell(
            instance_id,
            region,
            build_cluster_queue_probe_script(),
            profile=profile,
            as_user="ubuntu",
            timeout=timeout,
            comment="DYEC fleet-stop all-job idle proof",
        )
        queue_payload = parse_cluster_queue_probe_output(queue_result.stdout)
    except Exception:  # noqa: BLE001 - SSM/probe exceptions are normalized here
        raise ComputeFleetOperationError(
            "The headnode controller/job idle proof did not complete authoritatively."
        ) from None

    authoritative = bool(
        controller_payload.get("ok")
        and controller_payload.get("controller_count_authoritative")
        and not controller_payload.get("controllers_truncated")
        and queue_payload.get("ok")
    )
    if not authoritative:
        raise ComputeFleetOperationError(
            "The headnode controller/job idle proof did not complete authoritatively."
        )
    controller_count = controller_payload.get("controller_count")
    slurm_job_count = queue_payload.get("job_count")
    if (
        isinstance(controller_count, bool)
        or not isinstance(controller_count, int)
        or isinstance(slurm_job_count, bool)
        or not isinstance(slurm_job_count, int)
    ):
        raise ComputeFleetOperationError("The idle proof returned invalid counts.")
    observed_at = str(queue_payload.get("observed_at") or "")
    if not observed_at:
        raise ComputeFleetOperationError("The idle proof is missing its observation time.")
    return ClusterIdleProof(
        authoritative=True,
        controller_count=controller_count,
        slurm_job_count=slurm_job_count,
        observed_at=observed_at,
        instance_id=instance_id,
        ssm_command_ids=(controller_result.command_id, queue_result.command_id),
    )


@dataclass(frozen=True)
class ComputeFleetOperationResult:
    """Stable, non-secret result for one public fleet transition."""

    cluster: str
    region: str
    request_status: str
    wait_for_status: str
    drain_requested: bool
    initial_status: str
    final_status: str
    request_submitted: bool
    resumed_existing_request: bool
    idle_proof: ClusterIdleProof | None
    started_at: str
    completed_at: str
    elapsed_seconds: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": COMPUTE_FLEET_SCHEMA,
            "ok": True,
            "cluster": self.cluster,
            "region": self.region,
            "request_status": self.request_status,
            "wait_for_status": self.wait_for_status,
            "drain_requested": self.drain_requested,
            "initial_status": self.initial_status,
            "final_status": self.final_status,
            "request_submitted": self.request_submitted,
            "resumed_existing_request": self.resumed_existing_request,
            "idle_proof": self.idle_proof.to_payload() if self.idle_proof else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


def _idle_before_stop(
    *,
    cluster_name: str,
    region: str,
    profile: str | None,
    pcluster_executable: str,
    drain: bool,
    deadline: float,
    poll_interval: float,
    idle_probe_fn: Callable[..., ClusterIdleProof],
    monotonic_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
) -> ClusterIdleProof:
    while True:
        remaining = deadline - monotonic_fn()
        if remaining <= 0:
            raise ComputeFleetOperationError(
                "Timed out waiting for controllers and Slurm jobs to drain naturally."
            )
        proof = idle_probe_fn(
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
            timeout=max(1, int(remaining)),
        )
        if proof.idle:
            return proof
        if not drain:
            raise ComputeFleetOperationError(
                "Fleet stop refused: active DayOA controllers or Slurm jobs remain "
                f"(controllers={proof.controller_count}, jobs={proof.slurm_job_count})."
            )
        remaining = deadline - monotonic_fn()
        if remaining <= 0:
            raise ComputeFleetOperationError(
                "Timed out waiting for controllers and Slurm jobs to drain naturally."
            )
        sleep_fn(min(poll_interval, remaining))


def run_compute_fleet_transition(
    *,
    cluster_name: str,
    region: str,
    profile: str | None,
    pcluster_executable: str,
    request_status: str,
    wait_for_status: str,
    drain: bool,
    timeout_seconds: float,
    poll_interval_seconds: float,
    idle_probe_fn: Callable[..., ClusterIdleProof] = probe_cluster_idle,
    monotonic_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> ComputeFleetOperationResult:
    """Request, reclaim, or no-op one exact compute-fleet transition."""

    cluster_name = _required_text(cluster_name, field="cluster")
    region = _required_text(region, field="region")
    pcluster_executable = _required_text(
        pcluster_executable,
        field="pcluster_executable",
    )
    timeout = _positive_number(timeout_seconds, field="timeout_seconds")
    poll_interval = _positive_number(poll_interval_seconds, field="poll_interval_seconds")
    expected_target = REQUEST_TO_TARGET.get(request_status)
    if expected_target is None:
        raise ComputeFleetOperationError(
            "status must be exactly STOP_REQUESTED or START_REQUESTED."
        )
    if wait_for_status != expected_target:
        raise ComputeFleetOperationError(
            f"{request_status} must pair with wait target {expected_target}."
        )
    if drain and request_status != "STOP_REQUESTED":
        raise ComputeFleetOperationError("--drain is supported only with STOP_REQUESTED.")

    started_at = _utc_now()
    start = monotonic_fn()
    deadline = start + timeout
    try:
        described = describe_compute_fleet(
            cluster_name,
            region,
            profile=profile,
            executable=pcluster_executable,
        )
    except Exception:  # noqa: BLE001 - provider exceptions are normalized at this boundary
        raise ComputeFleetOperationError("Could not describe the compute fleet.") from None
    if not described.success:
        raise ComputeFleetOperationError("Could not describe the compute fleet.")
    initial_status = described.json_body.get("status")
    if initial_status not in KNOWN_FLEET_STATES:
        raise ComputeFleetOperationError("The compute fleet returned an unsupported state.")

    idle_proof: ClusterIdleProof | None = None
    request_submitted = False
    resumed_existing_request = initial_status in REQUEST_PROGRESS_STATES[request_status]
    if initial_status == wait_for_status:
        final_status = initial_status
    else:
        if request_status == "STOP_REQUESTED":
            idle_proof = _idle_before_stop(
                cluster_name=cluster_name,
                region=region,
                profile=profile,
                pcluster_executable=pcluster_executable,
                drain=drain,
                deadline=deadline,
                poll_interval=poll_interval,
                idle_probe_fn=idle_probe_fn,
                monotonic_fn=monotonic_fn,
                sleep_fn=sleep_fn,
            )

        if not resumed_existing_request:
            opposite_progress = REQUEST_PROGRESS_STATES[
                "START_REQUESTED" if request_status == "STOP_REQUESTED" else "STOP_REQUESTED"
            ]
            if initial_status in opposite_progress:
                raise ComputeFleetOperationError(
                    "The compute fleet is already moving in the opposite direction."
                )
            try:
                requested = update_compute_fleet(
                    cluster_name,
                    request_status,
                    region,
                    profile=profile,
                    executable=pcluster_executable,
                )
            except Exception:  # noqa: BLE001 - re-describe resolves ambiguous submission
                requested = None
            if requested is None or not requested.success:
                try:
                    observed = describe_compute_fleet(
                        cluster_name,
                        region,
                        profile=profile,
                        executable=pcluster_executable,
                    )
                except Exception:  # noqa: BLE001 - failed re-describe remains indeterminate
                    observed = None
                observed_status = (
                    observed.json_body.get("status")
                    if observed is not None and observed.success
                    else None
                )
                if (
                    observed_status == wait_for_status
                    or observed_status in REQUEST_PROGRESS_STATES[request_status]
                ):
                    resumed_existing_request = True
                else:
                    raise ComputeFleetOperationError(
                        "The compute-fleet request was not accepted and state is unchanged."
                    )
            else:
                request_submitted = True

        remaining = deadline - monotonic_fn()
        if remaining <= 0:
            raise ComputeFleetOperationError("The compute-fleet operation timed out.")
        try:
            waited = wait_for_compute_fleet(
                cluster_name,
                region,
                wait_for_status,
                profile=profile,
                executable=pcluster_executable,
                timeout=remaining,
                poll_interval=poll_interval,
            )
        except Exception:  # noqa: BLE001 - provider exceptions are normalized at this boundary
            raise ComputeFleetOperationError("The compute-fleet wait failed.") from None
        if not waited.success or waited.final_status != wait_for_status:
            raise ComputeFleetOperationError(
                "The compute fleet did not reach the requested terminal state."
            )
        final_status = wait_for_status

    completed = monotonic_fn()
    return ComputeFleetOperationResult(
        cluster=cluster_name,
        region=region,
        request_status=request_status,
        wait_for_status=wait_for_status,
        drain_requested=drain,
        initial_status=initial_status,
        final_status=final_status,
        request_submitted=request_submitted,
        resumed_existing_request=resumed_existing_request,
        idle_proof=idle_proof,
        started_at=started_at,
        completed_at=_utc_now(),
        elapsed_seconds=max(0.0, completed - start),
    )
