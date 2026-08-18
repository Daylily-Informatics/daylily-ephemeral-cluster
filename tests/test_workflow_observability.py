from __future__ import annotations

import json
import shlex
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from daylily_ec import workflow_observability
from daylily_ec.workflow_observability import (
    WorkflowObservabilityError,
    build_remote_probe_command,
    collect_workflow_observability,
    decode_snakemake_tail,
    derive_state,
    normalize_snakemake_log,
    parse_snakemake_lines,
)

REPO = "/fsx/analysis_results/cluster-a/analysis-1/daylily-omics-analysis"
LOG = f"{REPO}/.snakemake/log/2026-08-10T072121.snakemake.log"


def test_remote_probe_is_self_contained_and_does_not_require_headnode_module() -> None:
    command = build_remote_probe_command(
        ["--mode", "manual", "--repo-path", REPO, "--controller-pid", "0"]
    )
    argv = shlex.split(command)

    assert argv[:2] == ["python3", "-c"]
    assert "daylily_ec.workflow_observability" not in command
    assert len(command.encode("utf-8")) < 18_000
    result = workflow_observability.subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "--controller-pid must be a positive integer" in result.stderr


def test_exact_tail_round_trips_through_compressed_probe_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_path = tmp_path / "current.snakemake.log"
    log_path.write_bytes(
        b"stale line\n"
        b"Submitted job 21 with external jobid '82'.\n"
        b"12 of 195 steps (6%) done\n"
    )
    encode_tail = workflow_observability._encoded_snakemake_tail
    monkeypatch.setattr(workflow_observability, "_process_snapshot", lambda: {4242: 4000})
    monkeypatch.setattr(
        workflow_observability,
        "_observed_process",
        lambda _pid: {"pid_exists": True, "cwd": REPO, "command": "python snakemake"},
    )
    monkeypatch.setattr(workflow_observability, "_tmux_correlates", lambda *args: True)
    monkeypatch.setattr(
        workflow_observability,
        "_open_snakemake_logs",
        lambda *args, **kwargs: [LOG],
    )
    monkeypatch.setattr(
        workflow_observability,
        "_log_evidence",
        lambda _path: {
            **parse_snakemake_lines([]),
            "last_progress_at": None,
        },
    )
    monkeypatch.setattr(workflow_observability, "_slurm_states", lambda _ids: {})
    monkeypatch.setattr(
        workflow_observability,
        "_encoded_snakemake_tail",
        lambda _path, tail_lines: encode_tail(str(log_path), tail_lines=tail_lines),
    )

    payload = collect_workflow_observability(
        mode="manual",
        session="recovery-session",
        repo_path=REPO,
        controller_pid=4242,
        tail_lines=2,
    )
    transported = json.loads(json.dumps(payload["snakemake_log"]["tail"]))

    assert decode_snakemake_tail(transported) == (
        "Submitted job 21 with external jobid '82'.\n12 of 195 steps (6%) done\n"
    )


def _launched_receipts(
    tmp_path: Path,
    *,
    controller_exit_code: int | None = None,
    day_run_exit_code: int | None = None,
    snakemake_exit_code: int | None = None,
    log_path: str | None = None,
    log_attribution: str | None = None,
) -> tuple[Path, dict[str, object]]:
    run_dir = tmp_path / "daylily-runs" / "session-1"
    run_dir.mkdir(parents=True)
    attempt_id = "00000000-0000-4000-8000-000000000001"
    (run_dir / "controller_target.json").write_text(
        json.dumps(
            {
                "schema_version": "dyec.controller_target.v2",
                "controller_id": "session-1",
                "pid": 4242,
                "cwd": REPO,
                "log_path": f"{REPO}/.dyec/controller.log",
                "dag_path": f"{REPO}/.dyec/controller-dag.png",
                "analysis_root": str(Path(REPO).parent),
                "status_attempt_id": attempt_id,
            }
        ),
        encoding="utf-8",
    )
    started_at = "2026-08-10T07:21:21Z"
    completed_at = "2026-08-10T07:40:00Z" if controller_exit_code is not None else None

    def child(code: int | None, argv: list[str], *, include_log: bool = False) -> dict[str, object]:
        state = (
            "running"
            if code is None
            else ("succeeded" if code == 0 else "failed")
        )
        result: dict[str, object] = {
            "state": state,
            "argv": argv,
            "started_at": started_at,
            "completed_at": completed_at if code is not None else None,
            "exit_code": code,
        }
        if include_log:
            result["log_path"] = log_path
            result["log_attribution"] = log_attribution
        return result

    controller_state = (
        "running"
        if controller_exit_code is None
        else ("succeeded" if controller_exit_code == 0 else "failed")
    )
    attempt: dict[str, object] = {
        "attempt_id": attempt_id,
        "sequence": 1,
        "origin": "dyec_controller",
        "mode": "dry_run",
        "requested_command": "dy-r target -j 333 -p -k",
        "started_at": started_at,
        "completed_at": completed_at,
        "state": controller_state,
        "controller": {
            "state": controller_state,
            "session_name": "session-1",
            "pid": 4242,
            "command": "dy-r target -j 333 -p -k",
            "started_at": started_at,
            "completed_at": completed_at,
            "exit_code": controller_exit_code,
        },
        "day_run": child(
            day_run_exit_code,
            ["bin/day_run", "target", "-j", "333", "-p", "-k"],
        ),
        "snakemake": child(
            snakemake_exit_code,
            ["snakemake", "target", "-j", "333", "-p", "-k"],
            include_log=True,
        ),
    }
    return run_dir, {
        "schema_version": "daylily.analysis_status.v2",
        "analysis": {
            "analysis_root": str(Path(REPO).parent),
            "repo_path": REPO,
            "created_at": started_at,
        },
        "updated_at": completed_at or started_at,
        "attempts": [attempt],
    }


def _patch_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    live: bool,
    open_logs: list[str],
    log_lines: list[str] | None = None,
    slurm: dict[str, object] | None = None,
    status_payload: dict[str, object] | None = None,
) -> None:
    if status_payload is not None:
        monkeypatch.setattr(
            workflow_observability,
            "read_execution_status",
            lambda *_args, **_kwargs: status_payload,
        )
    monkeypatch.setattr(workflow_observability, "_process_snapshot", lambda: {4242: 4000})
    monkeypatch.setattr(
        workflow_observability,
        "_observed_process",
        lambda _pid: {
            "pid_exists": live,
            "cwd": REPO if live else None,
            "command": "bash dyec-controller-launch.sh; python snakemake" if live else None,
        },
    )
    monkeypatch.setattr(workflow_observability, "_tmux_correlates", lambda *args: True)
    monkeypatch.setattr(
        workflow_observability,
        "_open_snakemake_logs",
        lambda *args, **kwargs: list(open_logs),
    )
    monkeypatch.setattr(
        workflow_observability,
        "_log_evidence",
        lambda _path: {
            **parse_snakemake_lines(log_lines or []),
            "last_progress_at": "2026-08-10T07:28:00Z" if log_lines else None,
        },
    )
    monkeypatch.setattr(
        workflow_observability,
        "_slurm_states",
        lambda _ids: (
            slurm
            or {
                "available": True,
                "states": [],
                "state_counts": {},
            }
        ),
    )


def test_launched_running_reports_exact_log_progress_jobs_and_slurm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir, status_payload = _launched_receipts(tmp_path)
    _patch_runtime(
        monkeypatch,
        live=True,
        open_logs=[LOG],
        log_lines=[
            "Submitted job 21 with external jobid '82'.",
            "Submitted job 282 with external jobid '83'.",
            "Finished job 21.",
            "92 of 288 steps (31%) done",
        ],
        slurm={
            "available": True,
            "states": [
                {"job_id": "82", "state": "CONFIGURING", "name": "rule-a", "reason": "node-a"},
                {"job_id": "83", "state": "RUNNING", "name": "rule-b", "reason": "node-b"},
            ],
            "state_counts": {"CONFIGURING": 1, "RUNNING": 1},
        },
        status_payload=status_payload,
    )

    payload = collect_workflow_observability(
        mode="launched", session="session-1", run_dir=str(run_dir)
    )

    assert payload["state"] == "RUNNING"
    assert payload["controller"]["pid"] == 4242
    assert payload["controller"]["pid_exists"] is True
    assert payload["controller"]["live"] is True
    assert payload["snakemake_log"] == {
        "path": LOG,
        "source": "controller process-tree open file descriptor",
        "problem": None,
        "open_candidates": [LOG],
    }
    assert payload["jobs"]["submitted_count"] == 2
    assert payload["jobs"]["finished_count"] == 1
    assert payload["slurm"]["state_counts"] == {"CONFIGURING": 1, "RUNNING": 1}
    assert payload["terminal"]["controller_exit_code"] is None
    assert payload["terminal"]["day_run_exit_code"] is None
    assert payload["terminal"]["snakemake_exit_code"] is None
    assert payload["terminal"]["controller_exit_code_attributed"] is False


@pytest.mark.parametrize(
    ("exit_code", "expected_state"),
    [(0, "SUCCEEDED"), (1, "FAILED")],
)
def test_launched_terminal_state_uses_only_matching_status_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
    expected_state: str,
) -> None:
    run_dir, status_payload = _launched_receipts(
        tmp_path,
        controller_exit_code=exit_code,
        day_run_exit_code=exit_code,
        snakemake_exit_code=exit_code,
    )
    _patch_runtime(monkeypatch, live=False, open_logs=[], status_payload=status_payload)

    payload = collect_workflow_observability(
        mode="launched", session="session-1", run_dir=str(run_dir)
    )

    assert payload["state"] == expected_state
    assert payload["terminal"]["controller_exit_code"] == exit_code
    assert payload["terminal"]["day_run_exit_code"] == exit_code
    assert payload["terminal"]["snakemake_exit_code"] == exit_code
    assert payload["terminal"]["controller_exit_code_attributed"] is True
    assert payload["terminal"]["controller_exit_code_source"].endswith(
        "/status.json#attempts/00000000-0000-4000-8000-000000000001/controller/exit_code"
    )


def test_launched_snakemake_rc_is_not_terminal_before_controller_postprocessing_finishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir, status_payload = _launched_receipts(
        tmp_path,
        snakemake_exit_code=0,
    )
    _patch_runtime(monkeypatch, live=True, open_logs=[LOG], status_payload=status_payload)

    payload = collect_workflow_observability(
        mode="launched", session="session-1", run_dir=str(run_dir)
    )

    assert payload["state"] == "RUNNING"
    assert payload["controller"]["live"] is True
    assert payload["terminal"]["controller_exit_code"] is None
    assert payload["terminal"]["snakemake_exit_code"] == 0


def test_launched_status_preserves_divergent_day_run_and_snakemake_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir, status_payload = _launched_receipts(
        tmp_path,
        controller_exit_code=24,
        day_run_exit_code=7,
        snakemake_exit_code=0,
    )
    _patch_runtime(monkeypatch, live=False, open_logs=[], status_payload=status_payload)

    payload = collect_workflow_observability(
        mode="launched", session="session-1", run_dir=str(run_dir)
    )

    assert payload["state"] == "FAILED"
    assert payload["terminal"]["controller_exit_code"] == 24
    assert payload["terminal"]["day_run_exit_code"] == 7
    assert payload["terminal"]["snakemake_exit_code"] == 0


def test_launched_terminal_receipt_preserves_exact_invocation_log_and_job_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir, status_payload = _launched_receipts(
        tmp_path,
        controller_exit_code=0,
        day_run_exit_code=0,
        snakemake_exit_code=0,
        log_path=LOG,
        log_attribution="exact invocation file-set difference",
    )
    _patch_runtime(
        monkeypatch,
        live=False,
        open_logs=[],
        log_lines=[
            "Submitted job 21 with external jobid '82'.",
            "Finished job 21.",
            "1 of 1 steps (100%) done",
        ],
        status_payload=status_payload,
    )

    payload = collect_workflow_observability(
        mode="launched", session="session-1", run_dir=str(run_dir)
    )

    assert payload["state"] == "SUCCEEDED"
    assert payload["snakemake_log"]["path"] == LOG
    assert payload["snakemake_log"]["source"].endswith("/status.json")
    assert payload["jobs"]["submitted_count"] == 1
    assert payload["jobs"]["finished_count"] == 1


def test_stale_or_mismatched_status_receipt_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir, status_payload = _launched_receipts(
        tmp_path,
        controller_exit_code=0,
        day_run_exit_code=0,
        snakemake_exit_code=0,
    )
    target_path = run_dir / "controller_target.json"
    target = json.loads(target_path.read_text(encoding="utf-8"))
    target["controller_id"] = "prior-invocation"
    target_path.write_text(json.dumps(target), encoding="utf-8")
    _patch_runtime(monkeypatch, live=False, open_logs=[], status_payload=status_payload)

    with pytest.raises(WorkflowObservabilityError, match="does not match requested session"):
        collect_workflow_observability(mode="launched", session="session-1", run_dir=str(run_dir))


def test_manual_running_requires_explicit_repo_and_pid_and_never_infers_rc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime(
        monkeypatch,
        live=True,
        open_logs=[LOG],
        log_lines=[
            "echo 'RETURN CODE: 1'",
            "ERROR transient license retry",
            "1 of 5 steps (20%) done",
        ],
    )

    payload = collect_workflow_observability(
        mode="manual",
        session="recovery-session",
        repo_path=REPO,
        controller_pid=4242,
    )

    assert payload["state"] == "RUNNING"
    assert payload["terminal"]["controller_exit_code"] is None
    assert payload["terminal"]["failure_markers"] == []
    assert payload["semantics"]["generic_error_text_is_terminal_failure"] is False


def test_manual_dead_controller_with_only_stale_rc_or_generic_error_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime(
        monkeypatch,
        live=False,
        open_logs=[],
        log_lines=["RETURN CODE: 0", "ERROR: this appeared in a printed shell body"],
    )

    payload = collect_workflow_observability(
        mode="manual",
        repo_path=REPO,
        controller_pid=4242,
        snakemake_log=LOG,
    )

    assert payload["state"] == "UNKNOWN"
    assert payload["terminal"]["controller_exit_code"] is None
    assert payload["terminal"]["controller_exit_code_attributed"] is False


def test_manual_persistent_tmux_shell_is_not_a_live_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime(
        monkeypatch,
        live=True,
        open_logs=[],
        log_lines=["Error in rule stale_prior_invocation:"],
    )
    monkeypatch.setattr(
        workflow_observability,
        "_observed_process",
        lambda _pid: {
            "pid_exists": True,
            "cwd": REPO,
            "command": "bash --login --interactive",
        },
    )

    payload = collect_workflow_observability(
        mode="manual",
        session="recovery-session",
        repo_path=REPO,
        controller_pid=4242,
        snakemake_log=LOG,
    )

    assert payload["controller"]["pid_exists"] is True
    assert payload["controller"]["live"] is False
    assert payload["controller"]["command_matches"] is False
    assert payload["controller"]["attributed"] is False
    assert payload["snakemake_log"]["path"] is None
    assert payload["state"] == "UNKNOWN"


def test_manual_dead_controller_high_signal_failure_is_failed_without_invented_rc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime(
        monkeypatch,
        live=False,
        open_logs=[],
        log_lines=["Error in rule align:", "Exiting because a job execution failed."],
    )

    payload = collect_workflow_observability(
        mode="manual",
        repo_path=REPO,
        controller_pid=4242,
        snakemake_log=LOG,
    )

    assert payload["state"] == "FAILED"
    assert payload["terminal"]["controller_exit_code"] is None
    assert [item["marker"] for item in payload["terminal"]["failure_markers"]] == [
        "rule_error",
        "job_execution_failed",
    ]


def test_multiple_open_logs_are_reported_as_ambiguous_without_newest_guess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir, status_payload = _launched_receipts(tmp_path)
    second = f"{REPO}/.snakemake/log/2026-08-10T072122.snakemake.log"
    _patch_runtime(
        monkeypatch,
        live=True,
        open_logs=[LOG, second],
        status_payload=status_payload,
    )

    payload = collect_workflow_observability(
        mode="launched", session="session-1", run_dir=str(run_dir)
    )

    assert payload["state"] == "RUNNING"
    assert payload["snakemake_log"]["path"] is None
    assert payload["snakemake_log"]["open_candidates"] == [LOG, second]
    assert "multiple" in payload["snakemake_log"]["problem"]


def test_explicit_manual_log_must_be_inside_exact_repo() -> None:
    with pytest.raises(WorkflowObservabilityError, match="exact <repo-path>"):
        normalize_snakemake_log(
            "/fsx/analysis_results/other/run/daylily-omics-analysis/.snakemake/log/x.snakemake.log",
            repo_path=REPO,
        )


def test_slurm_state_collection_preserves_configuring_and_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs):
        calls.append(argv)
        return CompletedProcess(
            argv,
            0,
            "82|CONFIGURING|rule-a|node-a\n83|RUNNING|rule-b|node-b\n",
            "",
        )

    monkeypatch.setattr(workflow_observability.subprocess, "run", fake_run)

    payload = workflow_observability._slurm_states(["83", "82", "82"])

    assert calls == [["squeue", "--noheader", "--jobs", "82,83", "--format", "%i|%T|%j|%R"]]
    assert payload["state_counts"] == {"CONFIGURING": 1, "RUNNING": 1}
    assert [item["job_id"] for item in payload["states"]] == ["82", "83"]


def test_state_derivation_never_uses_queue_emptiness_or_inspection_rc() -> None:
    assert (
        derive_state(
            controller_live=False,
            controller_attributed=False,
            terminal_rc=None,
            terminal_rc_attributed=False,
            high_signal_failure=False,
        )
        == "UNKNOWN"
    )
