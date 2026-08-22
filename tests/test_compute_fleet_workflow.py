from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from daylily_ec.headnode_control import (
    CONTROLLER_ENTRYPOINT_NAMES,
    build_controller_action_script,
    build_controller_inventory_script,
)
from daylily_ec.scripts import daylily_run_omics_analysis_headnode as launcher_module
from daylily_ec.workflow import compute_fleet as fleet_module
from daylily_ec.workflow.compute_fleet import (
    CLUSTER_QUEUE_MARKER,
    CLUSTER_QUEUE_SCHEMA,
    ClusterIdleProof,
    ComputeFleetOperationError,
    parse_cluster_queue_probe_output,
    run_compute_fleet_transition,
)


def _provider_result(body: dict[str, object], *, success: bool = True) -> SimpleNamespace:
    return SimpleNamespace(success=success, json_body=body)


def _idle(*, controllers: int = 0, jobs: int = 0) -> ClusterIdleProof:
    return ClusterIdleProof(
        authoritative=True,
        controller_count=controllers,
        slurm_job_count=jobs,
        observed_at="2026-08-20T18:00:00Z",
        instance_id="i-headnode",
        ssm_command_ids=("ssm-controller", "ssm-queue"),
    )


def test_queue_probe_parser_accepts_one_consistent_bounded_marker() -> None:
    payload = (
        '{"schema_version":"dyec.cluster_queue_idle_probe.v1","ok":true,'
        '"observed_at":"2026-08-20T18:00:00Z","job_count":2,'
        '"state_counts":{"PENDING":1,"RUNNING":1},"error":null}'
    )

    parsed = parse_cluster_queue_probe_output(f"prefix\n{CLUSTER_QUEUE_MARKER}{payload}\n")

    assert parsed["schema_version"] == CLUSTER_QUEUE_SCHEMA
    assert parsed["job_count"] == 2


def test_current_launcher_identity_matches_inventory_and_action_predicates() -> None:
    launcher_source = inspect.getsource(launcher_module.main)
    inventory_script = build_controller_inventory_script()
    action_script = build_controller_action_script(
        pid=4242,
        confirm_pid=4242,
        expected_analysis_root="/fsx/analysis_results/ubuntu/analysis-1",
        action="stop",
    )

    assert CONTROLLER_ENTRYPOINT_NAMES == ("dy-r", "dyec-controller-launch.sh")
    assert 'work_script="$run_dir/dyec-controller-launch.sh"' in launcher_source
    assert 'bash "$DAYLILY_WORK_SCRIPT"' in launcher_source
    assert "dyec-controller-launch.sh" in inventory_script
    assert "dyec-controller-launch.sh" in action_script
    assert "dayoa-controller-launch.sh" not in inventory_script
    assert "dayoa-controller-launch.sh" not in action_script


def test_stop_proves_idle_then_submits_and_waits(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        fleet_module,
        "describe_compute_fleet",
        lambda *_args, **_kwargs: _provider_result({"status": "RUNNING"}),
    )

    def idle_probe(**_kwargs) -> ClusterIdleProof:
        calls.append("idle")
        return _idle()

    def update(*_args, **_kwargs) -> SimpleNamespace:
        calls.append("update")
        return _provider_result({})

    def wait(*_args, **_kwargs) -> SimpleNamespace:
        calls.append("wait")
        return SimpleNamespace(success=True, final_status="STOPPED")

    monkeypatch.setattr(fleet_module, "update_compute_fleet", update)
    monkeypatch.setattr(fleet_module, "wait_for_compute_fleet", wait)

    result = run_compute_fleet_transition(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="lsmc",
        pcluster_executable="pcluster",
        request_status="STOP_REQUESTED",
        wait_for_status="STOPPED",
        drain=False,
        timeout_seconds=60,
        poll_interval_seconds=1,
        idle_probe_fn=idle_probe,
    )

    assert calls == ["idle", "update", "wait"]
    assert result.request_submitted is True
    assert result.resumed_existing_request is False
    assert result.final_status == "STOPPED"
    assert result.to_payload()["idle_proof"] == {
        "authoritative": True,
        "controller_count": 0,
        "slurm_job_count": 0,
        "observed_at": "2026-08-20T18:00:00Z",
        "instance_id": "i-headnode",
        "ssm_command_ids": ["ssm-controller", "ssm-queue"],
    }


def test_terminal_target_is_idempotent_without_probe_or_mutation(monkeypatch) -> None:
    monkeypatch.setattr(
        fleet_module,
        "describe_compute_fleet",
        lambda *_args, **_kwargs: _provider_result({"status": "STOPPED"}),
    )
    monkeypatch.setattr(
        fleet_module,
        "update_compute_fleet",
        lambda *_args, **_kwargs: pytest.fail("no mutation expected"),
    )

    result = run_compute_fleet_transition(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="lsmc",
        pcluster_executable="pcluster",
        request_status="STOP_REQUESTED",
        wait_for_status="STOPPED",
        drain=False,
        timeout_seconds=60,
        poll_interval_seconds=1,
        idle_probe_fn=lambda **_kwargs: pytest.fail("no idle probe expected"),
    )

    assert result.initial_status == "STOPPED"
    assert result.final_status == "STOPPED"
    assert result.request_submitted is False
    assert result.idle_proof is None


def test_active_work_blocks_stop_without_drain(monkeypatch) -> None:
    monkeypatch.setattr(
        fleet_module,
        "describe_compute_fleet",
        lambda *_args, **_kwargs: _provider_result({"status": "RUNNING"}),
    )
    monkeypatch.setattr(
        fleet_module,
        "update_compute_fleet",
        lambda *_args, **_kwargs: pytest.fail("active work must block mutation"),
    )

    with pytest.raises(ComputeFleetOperationError, match="active DayOA controllers"):
        run_compute_fleet_transition(
            cluster_name="cluster-a",
            region="us-west-2",
            profile="lsmc",
            pcluster_executable="pcluster",
            request_status="STOP_REQUESTED",
            wait_for_status="STOPPED",
            drain=False,
            timeout_seconds=60,
            poll_interval_seconds=1,
            idle_probe_fn=lambda **_kwargs: _idle(controllers=1, jobs=2),
        )


def test_current_launcher_controller_blocks_stop_when_slurm_is_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        fleet_module,
        "describe_compute_fleet",
        lambda *_args, **_kwargs: _provider_result({"status": "RUNNING"}),
    )
    monkeypatch.setattr(
        fleet_module,
        "update_compute_fleet",
        lambda *_args, **_kwargs: pytest.fail("recognized controller must block mutation"),
    )

    with pytest.raises(
        ComputeFleetOperationError,
        match=r"controllers=1, jobs=0",
    ):
        run_compute_fleet_transition(
            cluster_name="cluster-a",
            region="us-west-2",
            profile="lsmc",
            pcluster_executable="pcluster",
            request_status="STOP_REQUESTED",
            wait_for_status="STOPPED",
            drain=False,
            timeout_seconds=60,
            poll_interval_seconds=1,
            idle_probe_fn=lambda **_kwargs: _idle(controllers=1, jobs=0),
        )


def test_drain_only_waits_for_work_to_finish_naturally(monkeypatch) -> None:
    proofs = iter((_idle(jobs=1), _idle()))
    sleeps: list[float] = []
    monkeypatch.setattr(
        fleet_module,
        "describe_compute_fleet",
        lambda *_args, **_kwargs: _provider_result({"status": "RUNNING"}),
    )
    monkeypatch.setattr(
        fleet_module,
        "update_compute_fleet",
        lambda *_args, **_kwargs: _provider_result({}),
    )
    monkeypatch.setattr(
        fleet_module,
        "wait_for_compute_fleet",
        lambda *_args, **_kwargs: SimpleNamespace(success=True, final_status="STOPPED"),
    )

    result = run_compute_fleet_transition(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="lsmc",
        pcluster_executable="pcluster",
        request_status="STOP_REQUESTED",
        wait_for_status="STOPPED",
        drain=True,
        timeout_seconds=60,
        poll_interval_seconds=3,
        idle_probe_fn=lambda **_kwargs: next(proofs),
        sleep_fn=sleeps.append,
    )

    assert sleeps == [3]
    assert result.drain_requested is True
    assert result.idle_proof is not None and result.idle_proof.idle


def test_existing_same_direction_request_is_reclaimed_without_duplicate(monkeypatch) -> None:
    monkeypatch.setattr(
        fleet_module,
        "describe_compute_fleet",
        lambda *_args, **_kwargs: _provider_result({"status": "STARTING"}),
    )
    monkeypatch.setattr(
        fleet_module,
        "update_compute_fleet",
        lambda *_args, **_kwargs: pytest.fail("duplicate request must not be submitted"),
    )
    monkeypatch.setattr(
        fleet_module,
        "wait_for_compute_fleet",
        lambda *_args, **_kwargs: SimpleNamespace(success=True, final_status="RUNNING"),
    )

    result = run_compute_fleet_transition(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="lsmc",
        pcluster_executable="pcluster",
        request_status="START_REQUESTED",
        wait_for_status="RUNNING",
        drain=False,
        timeout_seconds=60,
        poll_interval_seconds=1,
    )

    assert result.resumed_existing_request is True
    assert result.request_submitted is False
    assert result.final_status == "RUNNING"


@pytest.mark.parametrize(
    ("request_status", "wait_for_status", "drain"),
    [
        ("STOP_REQUESTED", "RUNNING", False),
        ("START_REQUESTED", "STOPPED", False),
        ("START_REQUESTED", "RUNNING", True),
    ],
)
def test_invalid_pairing_fails_before_provider_calls(
    monkeypatch,
    request_status: str,
    wait_for_status: str,
    drain: bool,
) -> None:
    monkeypatch.setattr(
        fleet_module,
        "describe_compute_fleet",
        lambda *_args, **_kwargs: pytest.fail("validation must precede provider calls"),
    )

    with pytest.raises(ComputeFleetOperationError):
        run_compute_fleet_transition(
            cluster_name="cluster-a",
            region="us-west-2",
            profile="lsmc",
            pcluster_executable="pcluster",
            request_status=request_status,
            wait_for_status=wait_for_status,
            drain=drain,
            timeout_seconds=60,
            poll_interval_seconds=1,
        )
