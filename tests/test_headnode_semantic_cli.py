from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from daylily_ec.aws.ssm import (
    HeadNodeTarget,
    SsmCommandFailedError,
    SsmCommandResult,
)
from daylily_ec.cli import app
from daylily_ec.headnode_control import (
    CONTROLLER_ACTION_MARKER,
    CONTROLLER_ACTION_SCHEMA,
    CONTROLLER_INVENTORY_MARKER,
    CONTROLLER_INVENTORY_SCHEMA,
    SLURM_JOB_ACTION_MARKER,
    SLURM_JOB_ACTION_SCHEMA,
    SLURM_NODE_STATE_MARKER,
    SLURM_NODE_STATE_SCHEMA,
)
from daylily_ec.headnode_observability import (
    ANALYSIS_DISCOVERY_MARKER,
    BENCHMARK_REPORT_MARKER,
    FSX_USAGE_MARKER,
    SYSTEM_INFO_MARKER,
)


runner = CliRunner()
OBSERVED_AT = "2026-07-22T12:00:00Z"
COMMON_ARGS = [
    "--profile",
    "dev",
    "--region",
    "us-west-2",
    "--cluster",
    "cluster-a",
]


def _marker(marker: str, payload: dict[str, object]) -> str:
    return marker + json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


SYSTEM_INFO_STDOUT = _marker(
    SYSTEM_INFO_MARKER,
    {
        "schema_version": 1,
        "operation": "headnode_system_info",
        "observed_at": OBSERVED_AT,
        "host": {
            "hostname": "ip-10-0-0-10",
            "os_release": {
                "id": "ubuntu",
                "version_id": "22.04",
                "pretty_name": "Ubuntu 22.04 LTS",
            },
            "kernel_release": "6.8.0",
            "architecture": "x86_64",
            "uptime_seconds": 3600,
            "cpu_count": 16,
            "memory_total_kib": 131072,
            "dyec_version": "13.0.8",
            "day_clone_available": True,
            "day_clone_version": None,
            "day_clone_default_ref": None,
        },
    },
)
FSX_USAGE_STDOUT = _marker(
    FSX_USAGE_MARKER,
    {
        "schema_version": 1,
        "operation": "headnode_fsx_usage",
        "observed_at": OBSERVED_AT,
        "filesystem": {
            "path": "/fsx",
            "filesystem": "fs-123.fsx.us-west-2.amazonaws.com@tcp:/abc",
            "size_kib": 1000,
            "used_kib": 250,
            "available_kib": 750,
            "use_percent": 25,
            "mountpoint": "/fsx",
        },
    },
)
ANALYSIS_ROOTS_STDOUT = _marker(
    ANALYSIS_DISCOVERY_MARKER,
    {
        "schema_version": 1,
        "operation": "analysis_discovery",
        "observed_at": OBSERVED_AT,
        "root": "/fsx/analysis_results",
        "mode": "direct",
        "max_results": 2,
        "max_depth": 3,
        "max_scanned_entries": 20,
        "scanned_entries": 2,
        "truncated": False,
        "analyses": [
            {
                "analysis_root": "/fsx/analysis_results/ursa/M-RGX-TEST",
                "dayoa_root": (
                    "/fsx/analysis_results/ursa/M-RGX-TEST/daylily-omics-analysis"
                ),
                "relative_path": "ursa/M-RGX-TEST",
            }
        ],
    },
)
CONTROLLERS_STDOUT = _marker(
    CONTROLLER_INVENTORY_MARKER,
    {
        "schema_version": CONTROLLER_INVENTORY_SCHEMA,
        "ok": True,
        "controllers": [],
        "tmux_panes": [],
        "tmux_sessions": [],
        "slurm_jobs": [],
        "errors": [],
        "slurm_state_counts": {},
        "controller_count": 0,
        "controller_process_identity_error_count": 0,
        "receipted_live_controller_count": 0,
        "unreceipted_live_controller_count": 0,
        "stale_controller_receipt_count": 0,
        "invalid_controller_receipt_count": 0,
        "controller_count_authoritative": True,
        "controllers_truncated": False,
        "controller_receipt_scan_truncated": False,
        "controller_receipt_enrichment_complete": True,
        "controller_process_scan_truncated": False,
    },
)
CONTROLLER_ACTION_STDOUT = _marker(
    CONTROLLER_ACTION_MARKER,
    {
        "schema_version": CONTROLLER_ACTION_SCHEMA,
        "ok": True,
        "signal_sent": True,
        "pid": 123,
        "action": "stop",
    },
)
SLURM_JOB_ACTION_STDOUT = _marker(
    SLURM_JOB_ACTION_MARKER,
    {
        "schema_version": SLURM_JOB_ACTION_SCHEMA,
        "ok": True,
        "job_ids": ["123", "124_1"],
        "job_count": 2,
        "action": "suspend",
        "return_code": 0,
    },
)
SLURM_DRAIN_STDOUT = _marker(
    SLURM_NODE_STATE_MARKER,
    {
        "schema_version": SLURM_NODE_STATE_SCHEMA,
        "ok": True,
        "jobs_cancelled": False,
        "action": "drain",
        "state": "DRAIN",
        "cluster": "cluster-a",
        "return_code": 0,
    },
)
BENCHMARK_STDOUT = _marker(
    BENCHMARK_REPORT_MARKER,
    {
        "schema_version": 1,
        "operation": "benchmark_report",
        "observed_at": OBSERVED_AT,
        "analysis_root": "/fsx/analysis_results/ursa/M-RGX-TEST",
        "genome_build": "hg38",
        "summary_tsv": (
            "/fsx/analysis_results/ursa/M-RGX-TEST/daylily-omics-analysis/"
            "results/day/hg38/reports/benchmarks_summary.tsv"
        ),
        "source": {
            "bytes": 42,
            "columns": ["rule", "s", "task_cost"],
            "row_count": 1,
        },
        "group_by": "rule",
        "numeric_columns": ["s", "task_cost"],
        "group_count": 1,
        "max_rows": 2,
        "max_bytes": 1024,
        "max_groups": 32,
        "truncated": False,
        "groups": [
            {
                "rule": "multiqc",
                "row_count": 1,
                "metrics": {
                    "s": {"value_count": 1, "total": 1.5, "mean": 1.5, "median": 1.5},
                    "task_cost": {
                        "value_count": 1,
                        "total": 0.1,
                        "mean": 0.1,
                        "median": 0.1,
                    },
                },
            }
        ],
    },
)


def _patch_transport(monkeypatch, *, stdout: str, failure: bool = False):
    import daylily_ec.aws.ssm as ssm_module
    import daylily_ec.scripts.common as common_module

    calls: dict[str, object] = {}
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    monkeypatch.setattr(common_module, "need_cmd", lambda _name: None)
    monkeypatch.setattr(common_module, "resolve_region", lambda _profile, _region=None: "us-west-2")
    monkeypatch.setattr(
        common_module,
        "resolve_cluster",
        lambda _profile, _region, _cluster=None: "cluster-a",
    )
    monkeypatch.setattr(
        ssm_module,
        "resolve_headnode_instance_id",
        lambda cluster, region, profile=None: HeadNodeTarget(cluster, region, "i-semantic"),
    )

    def fake_wait(instance_id: str, region: str, **kwargs):
        calls["wait"] = (instance_id, region, kwargs)

    def fake_run(instance_id: str, region: str, script: str, **kwargs):
        calls["run"] = (instance_id, region, script, kwargs)
        result = SsmCommandResult(
            "cmd-semantic",
            instance_id,
            "Failed" if failure else "Success",
            2 if failure else 0,
            stdout,
            "typed command failed" if failure else "",
        )
        if failure:
            raise SsmCommandFailedError("typed command failed", result)
        return result

    monkeypatch.setattr(ssm_module, "wait_for_ssm_online", fake_wait)
    monkeypatch.setattr(ssm_module, "run_shell", fake_run)
    return calls


@pytest.mark.parametrize(
    ("command", "stdout", "script_fragment"),
    [
        (["headnode", "system-info"], SYSTEM_INFO_STDOUT, "/proc/meminfo"),
        (["headnode", "fsx-usage"], FSX_USAGE_STDOUT, "FSx-usage JSON"),
        (
            [
                "headnode",
                "analysis-roots",
                "--mode",
                "direct",
                "--max-results",
                "2",
                "--max-depth",
                "3",
                "--max-scanned-entries",
                "20",
            ],
            ANALYSIS_ROOTS_STDOUT,
            "Analysis discovery violates the scanned-entry limit",
        ),
        (
            [
                "headnode",
                "dayoa-controllers",
                "--max-controllers",
                "2",
                "--max-tmux-panes",
                "3",
                "--max-slurm-jobs",
                "4",
            ],
            CONTROLLERS_STDOUT,
            "MAX_CONTROLLERS = 2",
        ),
        (
            [
                "headnode",
                "dayoa-controller-action",
                "--pid",
                "123",
                "--confirm-pid",
                "123",
                "--analysis-root",
                "/fsx/analysis_results/ursa/M-RGX-TEST",
                "--action",
                "stop",
                "--operation-id",
                "op-123",
            ],
            CONTROLLER_ACTION_STDOUT,
            "process_not_recognized_dayoa_controller",
        ),
        (
            [
                "headnode",
                "slurm-job-action",
                "--action",
                "suspend",
                "--job-id",
                "123",
                "--job-id",
                "124_1",
            ],
            SLURM_JOB_ACTION_STDOUT,
            "scontrol",
        ),
        (
            [
                "headnode",
                "slurm-drain",
                "--confirm-cluster",
                "cluster-a",
                "--reason",
                "maintenance window",
                "--operation-id",
                "op-drain-1",
            ],
            SLURM_DRAIN_STDOUT,
            "NodeName=ALL",
        ),
        (
            [
                "workflow",
                "benchmark-report",
                "--analysis-root",
                "/fsx/analysis_results/ursa/M-RGX-TEST",
                "--genome-build",
                "hg38",
                "--max-bytes",
                "1024",
                "--max-rows",
                "2",
            ],
            BENCHMARK_STDOUT,
            "benchmarks_summary.tsv",
        ),
    ],
)
def test_semantic_commands_use_typed_ubuntu_ssm_transport(
    monkeypatch,
    command: list[str],
    stdout: str,
    script_fragment: str,
) -> None:
    calls = _patch_transport(monkeypatch, stdout=stdout)

    result = runner.invoke(app, ["--json", *command, *COMMON_ARGS])

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["cluster"] == "cluster-a"
    assert payload["region"] == "us-west-2"
    assert payload["instance_id"] == "i-semantic"
    assert payload["ssm_command_id"] == "cmd-semantic"
    assert calls["wait"] == (
        "i-semantic",
        "us-west-2",
        {"profile": "dev", "timeout": 120},
    )
    instance_id, region, script, kwargs = calls["run"]
    assert (instance_id, region) == ("i-semantic", "us-west-2")
    assert script_fragment in script
    assert kwargs["profile"] == "dev"
    assert kwargs["as_user"] == "ubuntu"
    assert "remote_user" not in payload


def test_semantic_command_fails_closed_on_duplicate_markers(monkeypatch) -> None:
    calls = _patch_transport(monkeypatch, stdout=SYSTEM_INFO_STDOUT + SYSTEM_INFO_STDOUT)

    result = runner.invoke(app, ["--json", "headnode", "system-info", *COMMON_ARGS])

    assert result.exit_code == 1
    assert "exactly one marker" in result.stdout + result.stderr
    assert "run" in calls


def test_semantic_command_validates_failure_marker_before_reporting(monkeypatch) -> None:
    failure_stdout = _marker(
        CONTROLLER_ACTION_MARKER,
        {
            "schema_version": CONTROLLER_ACTION_SCHEMA,
            "ok": False,
            "error": "process_not_live",
            "signal_sent": False,
        },
    )
    _patch_transport(monkeypatch, stdout=failure_stdout, failure=True)

    result = runner.invoke(
        app,
        [
            "--json",
            "headnode",
            "dayoa-controller-action",
            "--pid",
            "123",
            "--confirm-pid",
            "123",
            "--analysis-root",
            "/fsx/analysis_results/ursa/M-RGX-TEST",
            "--action",
            "stop",
            "--operation-id",
            "op-123",
            *COMMON_ARGS,
        ],
    )

    assert result.exit_code == 1
    assert "process_not_live" in result.stdout + result.stderr


def test_slurm_drain_exposes_no_undrain_or_action_selector() -> None:
    result = runner.invoke(app, ["headnode", "slurm-drain", "--help"])

    assert result.exit_code == 0
    assert "--confirm-cluster" in result.stdout
    assert "--reason" in result.stdout
    assert "--operation-id" in result.stdout
    assert "--action" not in result.stdout
    assert "undrain" not in result.stdout.lower()


def test_semantic_commands_expose_no_remote_user_option() -> None:
    result = runner.invoke(app, ["headnode", "system-info", "--help"])

    assert result.exit_code == 0
    assert "--remote-user" not in result.stdout
