from __future__ import annotations

import json
from pathlib import Path

import pytest

from daylily_ec.aws.ssm import HeadNodeTarget
from daylily_ec.scripts.common import CommandError
import daylily_ec.ssh_to_ssm_e2e_runner as runner_module


def test_write_runner_config_sets_cluster_name_triplet(tmp_path: Path) -> None:
    base_config = tmp_path / "daylily.yaml"
    base_config.write_text(
        "ephemeral_cluster:\n"
        "  config:\n"
        "    cluster_name: [PROMPTUSER, old-default, old-value]\n",
        encoding="utf-8",
    )

    runner_config = runner_module.write_runner_config(base_config, "e2e-cluster", tmp_path / "out")
    rendered = runner_config.read_text(encoding="utf-8")

    assert runner_config.is_file()
    assert "USESETVALUE" in rendered
    assert "e2e-cluster" in rendered


def test_parse_remote_stage_dir_extracts_path() -> None:
    stdout = (
        "Remote staging completed successfully.\n"
        "Remote FSx stage directory: /fsx/data/staged_sample_data/remote_stage_20260412T120000Z\n"
    )

    assert (
        runner_module.parse_remote_stage_dir(stdout)
        == "/fsx/data/staged_sample_data/remote_stage_20260412T120000Z"
    )


def test_parse_tmux_session_extracts_session_name() -> None:
    stdout = (
        "Tmux session 'daylily-omics-analysis' created on the head node.\n"
        "Reconnect with: daylily-ssh-into-headnode --profile dev --region us-west-2 --cluster cluster-a\n"
    )

    assert runner_module.parse_tmux_session(stdout) == "daylily-omics-analysis"


def test_validate_delete_flags_requires_allow_destroy() -> None:
    with pytest.raises(CommandError, match="requires --allow-destroy"):
        runner_module.validate_delete_flags(delete_cluster=True, allow_destroy=False)


def test_default_cluster_name_fits_supported_template_limit() -> None:
    cluster_name = runner_module.default_cluster_name()

    assert cluster_name.startswith(f"{runner_module.CLUSTER_NAME_PREFIX}-")
    assert len(cluster_name) <= runner_module.MAX_CLUSTER_NAME_LEN


def test_validate_cluster_name_rejects_too_long_values() -> None:
    with pytest.raises(CommandError, match="too long for the supported template"):
        runner_module.validate_cluster_name("daylily-ssm-e2e-20260412103248")


def test_build_interactive_smoke_command_targets_connect_helper(monkeypatch) -> None:
    monkeypatch.setattr(runner_module.sys, "platform", "darwin")

    command = runner_module._build_interactive_smoke_command("dev", "us-west-2", "cluster-a")

    assert command[:4] == ["script", "-q", "/dev/null", "/bin/sh"]
    assert "daylily-ssh-into-headnode" in command[-1]
    assert "--cluster cluster-a" in command[-1]


def test_record_step_writes_machine_readable_summary(tmp_path: Path) -> None:
    summary = runner_module.RunnerSummary(
        cluster_name="cluster-a",
        region="us-west-2",
        region_az="us-west-2d",
        profile="dev",
        config_path="/tmp/daylily.yaml",
        analysis_samples="/tmp/analysis_samples.tsv",
        output_json=str(tmp_path / "summary.json"),
        started_at="2026-04-12T00:00:00+00:00",
    )
    output_path = tmp_path / "summary.json"

    runner_module._record_step(summary, output_path, "preflight", "passed", command="daylily-ec preflight")

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["cluster_name"] == "cluster-a"
    assert payload["steps"] == [
        {
            "name": "preflight",
            "status": "passed",
            "details": {"command": "daylily-ec preflight"},
        }
    ]


def test_main_runs_supported_lifecycle_and_writes_summary(monkeypatch, tmp_path: Path) -> None:
    base_config = tmp_path / "daylily.yaml"
    analysis_samples = tmp_path / "analysis_samples.tsv"
    export_dir = tmp_path / "export"
    output_json = tmp_path / "summary.json"
    base_config.write_text(
        "ephemeral_cluster:\n  config:\n    cluster_name: [PROMPTUSER, base, old]\n",
        encoding="utf-8",
    )
    analysis_samples.write_text("RUN_ID\tSAMPLE_ID\n", encoding="utf-8")

    calls: list[str] = []
    commands_by_name: dict[str, list[str]] = {}

    monkeypatch.setattr(runner_module, "need_cmd", lambda name: calls.append(f"need:{name}"))
    monkeypatch.setattr(
        runner_module,
        "write_runner_config",
        lambda base, cluster, dest: dest / f"{cluster}.yaml",
    )
    monkeypatch.setattr(
        runner_module,
        "resolve_headnode_instance_id",
        lambda cluster, region, profile=None: HeadNodeTarget(cluster, region, "i-abc123"),
    )
    monkeypatch.setattr(
        runner_module,
        "wait_for_ssm_online",
        lambda instance_id, region, profile=None, timeout=300: calls.append("wait-for-ssm"),
    )
    monkeypatch.setattr(
        runner_module,
        "ensure_ubuntu_session_preferences",
        lambda region, profile=None: calls.append("validate-session-manager-shell"),
    )
    monkeypatch.setattr(
        runner_module,
        "_validate_headnode_bootstrap",
        lambda *args, **kwargs: calls.append("validate-headnode-bootstrap"),
    )
    monkeypatch.setattr(
        runner_module,
        "_inspect_runtime_state",
        lambda *args, **kwargs: calls.append("inspect-runtime-state"),
    )
    monkeypatch.setattr(
        runner_module,
        "_smoke_interactive_session",
        lambda *args, **kwargs: calls.append("smoke-interactive-session"),
    )

    def fake_run_local(summary, output_path, name, command, env):
        calls.append(name)
        commands_by_name[name] = list(command)
        if name == "stage-from-laptop":
            stdout = "Remote FSx stage directory: /fsx/data/staged_sample_data/remote_stage_1\n"
            runner_module._record_step(summary, output_path, name, "passed", command=" ".join(command))
            return stdout
        if name == "launch-workflow":
            stdout = "Tmux session 'sess-1' created on the head node.\n"
            runner_module._record_step(summary, output_path, name, "passed", command=" ".join(command))
            return stdout
        if name == "export-results":
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "fsx_export.yaml").write_text("ok\n", encoding="utf-8")
        runner_module._record_step(summary, output_path, name, "passed", command=" ".join(command))
        return ""

    monkeypatch.setattr(runner_module, "_run_local_command", fake_run_local)

    rc = runner_module.main(
        [
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--region-az",
            "us-west-2d",
            "--config",
            str(base_config),
            "--cluster-name",
            "cluster-a",
            "--reference-bucket",
            "s3://bucket",
            "--analysis-samples",
            str(analysis_samples),
            "--export-output-dir",
            str(export_dir),
            "--output-json",
            str(output_json),
            "--workflow-live",
            "--interactive-session-smoke",
            "--delete-cluster",
            "--allow-destroy",
        ]
    )

    assert rc == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    step_names = [step["name"] for step in payload["steps"]]
    assert "prepare-config" in step_names
    assert "validate-session-manager-shell" in step_names
    assert "parse-stage-output" in step_names
    assert "parse-workflow-output" in step_names
    assert "delete-cluster" in step_names
    assert "--non-interactive" in commands_by_name["preflight"]
    assert "--non-interactive" in commands_by_name["create-cluster"]
    assert "--stage-dir" in commands_by_name["launch-workflow"]
    assert "/fsx/data/staged_sample_data/remote_stage_1" in commands_by_name["launch-workflow"]
    assert "--stage-base" not in commands_by_name["launch-workflow"]
    assert calls.count("smoke-interactive-session") == 1
    assert "create-cluster" in calls
    assert "export-results" in calls
