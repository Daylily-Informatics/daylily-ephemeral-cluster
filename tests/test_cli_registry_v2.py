from __future__ import annotations

from importlib.metadata import version as dist_version
import json
from subprocess import CompletedProcess
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import daylily_ec.cli as cli_module
from daylily_ec.aws.ssm import (
    HeadNodeTarget,
    SsmCommandFailedError,
    SsmCommandResult,
)
from daylily_ec.cli import app, spec
from daylily_ec.headnode import SQUEUE_FORMAT
from daylily_ec.state.models import StateRecord

runner = CliRunner()


EXPECTED_COMMANDS = {
    ("version",),
    ("info",),
    ("create",),
    ("preflight",),
    ("drift",),
    ("cluster-info",),
    ("cluster", "list"),
    ("cluster", "describe"),
    ("cluster", "wait"),
    ("export",),
    ("delete",),
    ("resources-dir",),
    ("env", "status"),
    ("env", "activate"),
    ("env", "deactivate"),
    ("env", "reset"),
    ("runtime", "status"),
    ("runtime", "check"),
    ("runtime", "explain"),
    ("pricing", "snapshot"),
    ("headnode", "init"),
    ("headnode", "connect"),
    ("headnode", "info"),
    ("headnode", "jobs"),
    ("headnode", "configure"),
    ("samples", "stage"),
    ("workflow", "launch"),
    ("workflow", "status"),
    ("workflow", "logs"),
    ("repositories", "commands"),
    ("state", "list"),
    ("state", "show"),
}


def _activate_dayec_runtime(monkeypatch) -> None:
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")


def _patch_headnode_selection(
    monkeypatch,
    *,
    region: str = "us-west-2",
    cluster: str = "cluster-a",
) -> None:
    import daylily_ec.scripts.common as common_module

    monkeypatch.setattr(common_module, "need_cmd", lambda _name: None)
    monkeypatch.setattr(common_module, "resolve_region", lambda _profile, _explicit=None: region)
    monkeypatch.setattr(
        common_module,
        "resolve_cluster",
        lambda _profile, _region, _explicit=None: cluster,
    )


def test_cli_spec_uses_platform_v2_runtime() -> None:
    assert spec.policy.profile == "platform-v2"
    assert spec.runtime is not None
    assert spec.runtime.guard_mode == "advisory"
    assert spec.runtime.allow_skip_check is False
    assert spec.runtime.supported_backends
    assert spec.runtime.prereqs
    assert {prereq.key: prereq.severity for prereq in spec.runtime.prereqs} == {
        "day-ec-conda-active-env": "warn",
        "day-ec-conda-env-name": "warn",
    }


def test_cli_registry_exposes_v2_command_tree_and_policies() -> None:
    registry = app._cli_core_yo_registry

    assert set(registry._commands) == EXPECTED_COMMANDS
    for argv in EXPECTED_COMMANDS:
        assert registry.resolve_command_args(list(argv)) is not None

    version_cmd = registry.get_command(("version",))
    info_cmd = registry.get_command(("info",))
    create_cmd = registry.get_command(("create",))
    preflight_cmd = registry.get_command(("preflight",))
    drift_cmd = registry.get_command(("drift",))
    delete_cmd = registry.get_command(("delete",))
    export_cmd = registry.get_command(("export",))
    resources_dir_cmd = registry.get_command(("resources-dir",))
    cluster_info_cmd = registry.get_command(("cluster-info",))
    cluster_list_cmd = registry.get_command(("cluster", "list"))
    cluster_describe_cmd = registry.get_command(("cluster", "describe"))
    cluster_wait_cmd = registry.get_command(("cluster", "wait"))
    env_status_cmd = registry.get_command(("env", "status"))
    env_activate_cmd = registry.get_command(("env", "activate"))
    env_deactivate_cmd = registry.get_command(("env", "deactivate"))
    env_reset_cmd = registry.get_command(("env", "reset"))
    runtime_status_cmd = registry.get_command(("runtime", "status"))
    runtime_check_cmd = registry.get_command(("runtime", "check"))
    runtime_explain_cmd = registry.get_command(("runtime", "explain"))
    headnode_init_cmd = registry.get_command(("headnode", "init"))
    headnode_connect_cmd = registry.get_command(("headnode", "connect"))
    headnode_info_cmd = registry.get_command(("headnode", "info"))
    headnode_jobs_cmd = registry.get_command(("headnode", "jobs"))
    headnode_configure_cmd = registry.get_command(("headnode", "configure"))
    samples_stage_cmd = registry.get_command(("samples", "stage"))
    workflow_launch_cmd = registry.get_command(("workflow", "launch"))
    workflow_status_cmd = registry.get_command(("workflow", "status"))
    workflow_logs_cmd = registry.get_command(("workflow", "logs"))
    repositories_commands_cmd = registry.get_command(("repositories", "commands"))
    state_list_cmd = registry.get_command(("state", "list"))
    state_show_cmd = registry.get_command(("state", "show"))
    pricing_snapshot_cmd = registry.get_command(("pricing", "snapshot"))

    assert version_cmd is not None
    assert version_cmd.policy.runtime_guard == "exempt"

    assert info_cmd is not None
    assert info_cmd.policy.runtime_guard == "exempt"
    assert info_cmd.policy.supports_json is True

    assert create_cmd is not None
    assert create_cmd.policy.mutates_state is True

    assert preflight_cmd is not None
    assert preflight_cmd.policy.long_running is True
    assert preflight_cmd.policy.mutates_state is False

    assert drift_cmd is not None
    assert drift_cmd.policy.supports_json is True

    assert delete_cmd is not None
    assert delete_cmd.policy.mutates_state is True

    assert export_cmd is not None
    assert export_cmd.policy.mutates_state is True

    assert resources_dir_cmd is not None
    assert resources_dir_cmd.policy.runtime_guard == "exempt"

    assert cluster_info_cmd is not None
    assert cluster_info_cmd.policy.supports_json is True

    assert cluster_list_cmd is not None
    assert cluster_list_cmd.policy.supports_json is True
    assert cluster_list_cmd.policy.mutates_state is False

    assert cluster_describe_cmd is not None
    assert cluster_describe_cmd.policy.supports_json is True

    assert cluster_wait_cmd is not None
    assert cluster_wait_cmd.policy.long_running is True
    assert cluster_wait_cmd.policy.mutates_state is False

    assert env_status_cmd is not None
    assert env_status_cmd.policy.supports_json is True
    assert env_status_cmd.policy.runtime_guard == "exempt"

    assert env_activate_cmd is not None
    assert env_activate_cmd.policy.runtime_guard == "exempt"

    assert env_deactivate_cmd is not None
    assert env_deactivate_cmd.policy.runtime_guard == "exempt"

    assert env_reset_cmd is not None
    assert env_reset_cmd.policy.runtime_guard == "exempt"

    for runtime_cmd in (runtime_status_cmd, runtime_check_cmd, runtime_explain_cmd):
        assert runtime_cmd is not None
        assert runtime_cmd.policy.supports_json is True
        assert runtime_cmd.policy.runtime_guard == "exempt"

    assert headnode_init_cmd is not None
    assert headnode_init_cmd.policy.mutates_state is True
    assert headnode_init_cmd.policy.interactive is True

    assert headnode_connect_cmd is not None
    assert headnode_connect_cmd.policy.interactive is True
    assert headnode_connect_cmd.policy.mutates_state is False

    assert headnode_info_cmd is not None
    assert headnode_info_cmd.policy.supports_json is True

    assert headnode_jobs_cmd is not None
    assert headnode_jobs_cmd.policy.runtime_guard == "required"
    assert headnode_jobs_cmd.policy.mutates_state is False

    assert headnode_configure_cmd is not None
    assert headnode_configure_cmd.policy.mutates_state is True
    assert headnode_configure_cmd.policy.long_running is True

    assert samples_stage_cmd is not None
    assert samples_stage_cmd.policy.mutates_state is True
    assert samples_stage_cmd.policy.long_running is True

    assert workflow_launch_cmd is not None
    assert workflow_launch_cmd.policy.mutates_state is True
    assert workflow_launch_cmd.policy.long_running is True

    assert workflow_status_cmd is not None
    assert workflow_status_cmd.policy.supports_json is True

    assert workflow_logs_cmd is not None
    assert workflow_logs_cmd.policy.mutates_state is False

    assert repositories_commands_cmd is not None
    assert repositories_commands_cmd.policy.supports_json is True
    assert repositories_commands_cmd.policy.runtime_guard == "exempt"

    assert state_list_cmd is not None
    assert state_list_cmd.policy.supports_json is True
    assert state_list_cmd.policy.runtime_guard == "exempt"

    assert state_show_cmd is not None
    assert state_show_cmd.policy.supports_json is True
    assert state_show_cmd.policy.runtime_guard == "exempt"

    assert pricing_snapshot_cmd is not None
    assert pricing_snapshot_cmd.policy.supports_json is True


@pytest.mark.parametrize("argv", sorted(EXPECTED_COMMANDS))
def test_registered_cli_commands_render_help(argv: tuple[str, ...]) -> None:
    result = runner.invoke(app, [*argv, "--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout


def test_env_commands_emit_guidance_and_status(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DAYLILY_EC_ACTIVE", "1")
    monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    activate_result = runner.invoke(app, ["env", "activate"])
    deactivate_result = runner.invoke(app, ["env", "deactivate"])
    reset_result = runner.invoke(app, ["env", "reset"])
    status_result = runner.invoke(app, ["--json", "env", "status"])

    assert activate_result.exit_code == 0
    assert "./activate" in activate_result.stdout
    assert deactivate_result.exit_code == 0
    assert "conda deactivate" in deactivate_result.stdout
    assert reset_result.exit_code == 0
    assert "./activate" in reset_result.stdout
    assert "conda deactivate" in reset_result.stdout
    assert status_result.exit_code == 0
    payload = json.loads(status_result.stdout)
    assert payload["active"] is True
    assert payload["project_root"] == str(tmp_path)


@pytest.mark.parametrize("subcommand", ["status", "check", "explain"])
def test_runtime_commands_emit_json(monkeypatch, subcommand: str) -> None:
    _activate_dayec_runtime(monkeypatch)

    result = runner.invoke(app, ["--json", "runtime", subcommand])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["backend_name"] == "day-ec-conda"
    if subcommand == "status":
        assert "prereq_summary" in payload
    elif subcommand == "check":
        assert "results" in payload
    else:
        assert payload["entry_guidance"] == "source ./activate"


def test_root_json_is_global_for_version() -> None:
    result = runner.invoke(app, ["--json", "version"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["app"] == "Daylily Ephemeral Cluster"
    assert payload["version"] == dist_version("daylily-ephemeral-cluster")


def test_root_json_is_global_for_info(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    from cli_core_yo.app import create_app

    fresh_app = create_app(spec)
    result = runner.invoke(fresh_app, ["--json", "info"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["Version"]
    assert payload["CLI Core"]
    assert payload["Config Dir"] == str((tmp_path / "config" / "daylily").resolve())


def test_json_rejected_for_non_json_command() -> None:
    result = runner.invoke(app, ["--json", "create", "--region-az", "us-west-2b"])

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "contract_violation"
    assert payload["error"]["details"]["command"] == "create"


def test_create_command_passes_workflow_options(monkeypatch, tmp_path) -> None:
    import daylily_ec.workflow.create_cluster as create_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    config_path = tmp_path / "daylily.yaml"
    config_path.write_text("cluster_name: cluster-a\n", encoding="utf-8")

    def fake_run_create_workflow(region_az: str, **kwargs) -> int:
        calls["region_az"] = region_az
        calls["kwargs"] = kwargs
        return 17

    monkeypatch.setattr(create_module, "run_create_workflow", fake_run_create_workflow)

    result = runner.invoke(
        app,
        [
            "create",
            "--region-az",
            "us-west-2d",
            "--profile",
            "dev",
            "--config",
            str(config_path),
            "--pass-on-warn",
            "--debug",
            "--non-interactive",
        ],
    )

    assert result.exit_code == 17
    assert calls["region_az"] == "us-west-2d"
    assert calls["kwargs"] == {
        "profile": "dev",
        "config_path": str(config_path),
        "pass_on_warn": True,
        "debug": True,
        "non_interactive": True,
    }


def test_preflight_command_passes_workflow_options(monkeypatch, tmp_path) -> None:
    import daylily_ec.workflow.create_cluster as create_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    config_path = tmp_path / "daylily.yaml"
    config_path.write_text("cluster_name: cluster-a\n", encoding="utf-8")

    def fake_run_preflight_only(region_az: str, **kwargs) -> int:
        calls["region_az"] = region_az
        calls["kwargs"] = kwargs
        return 19

    monkeypatch.setattr(create_module, "run_preflight_only", fake_run_preflight_only)

    result = runner.invoke(
        app,
        [
            "preflight",
            "--region-az",
            "us-west-2d",
            "--profile",
            "dev",
            "--config",
            str(config_path),
            "--pass-on-warn",
            "--debug",
            "--non-interactive",
        ],
    )

    assert result.exit_code == 19
    assert calls["region_az"] == "us-west-2d"
    assert calls["kwargs"] == {
        "profile": "dev",
        "config_path": str(config_path),
        "pass_on_warn": True,
        "debug": True,
        "non_interactive": True,
    }


def test_drift_command_loads_state_and_runs_drift_check(monkeypatch, tmp_path) -> None:
    import daylily_ec.aws.context as context_module
    import daylily_ec.state.drift as drift_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    state_path = tmp_path / "state.json"
    state_path.write_text(
        StateRecord(
            cluster_name="cluster-a",
            region="us-west-2",
            region_az="us-west-2d",
            aws_profile="dev",
            account_id="123456789012",
        ).to_sorted_json(),
        encoding="utf-8",
    )

    class FakeAwsContext:
        account_id = "123456789012"

        def client(self, service_name: str) -> str:
            return f"{service_name}-client"

    def fake_build(region_az: str, *, profile: str | None = None) -> FakeAwsContext:
        calls["build"] = (region_az, profile)
        return FakeAwsContext()

    def fake_run_drift_check(state: StateRecord, **kwargs):
        calls["state"] = state
        calls["drift_kwargs"] = kwargs
        return SimpleNamespace(has_drift=False, errors=[])

    monkeypatch.setattr(context_module.AWSContext, "build", fake_build)
    monkeypatch.setattr(drift_module, "run_drift_check", fake_run_drift_check)

    result = runner.invoke(
        app,
        ["drift", "--state-file", str(state_path), "--profile", "dev"],
    )

    assert result.exit_code == 0
    assert calls["build"] == ("us-west-2d", "dev")
    assert calls["state"].cluster_name == "cluster-a"
    assert calls["drift_kwargs"]["account_id"] == "123456789012"
    assert calls["drift_kwargs"]["cfn_client"] == "cloudformation-client"


def test_export_command_passes_workflow_options(monkeypatch, tmp_path) -> None:
    import daylily_ec.workflow.export_data as export_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)

    def fake_configure_logging(verbose: bool) -> None:
        calls["verbose"] = verbose

    def fake_run_export_workflow(options) -> int:
        calls["options"] = options
        return 23

    monkeypatch.setattr(export_module, "configure_logging", fake_configure_logging)
    monkeypatch.setattr(export_module, "run_export_workflow", fake_run_export_workflow)

    result = runner.invoke(
        app,
        [
            "export",
            "--cluster-name",
            "cluster-a",
            "--target-uri",
            "analysis_results/ubuntu",
            "--region",
            "us-west-2",
            "--output-dir",
            str(tmp_path),
            "--profile",
            "dev",
            "--verbose",
        ],
    )

    assert result.exit_code == 23
    assert calls["verbose"] is True
    options = calls["options"]
    assert options.cluster_name == "cluster-a"
    assert options.target_uri == "analysis_results/ubuntu"
    assert options.region == "us-west-2"
    assert options.profile == "dev"
    assert options.output_dir == tmp_path.resolve()


def test_delete_command_passes_workflow_options(monkeypatch, tmp_path) -> None:
    import daylily_ec.workflow.delete_cluster as delete_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")

    def fake_delete(options) -> int:
        calls["options"] = options
        return 29

    def fake_dry_run(_options):
        raise AssertionError("dry-run workflow should not run")

    monkeypatch.setattr(delete_module, "run_delete_workflow", fake_delete)
    monkeypatch.setattr(delete_module, "run_delete_dry_run", fake_dry_run)

    result = runner.invoke(
        app,
        [
            "delete",
            "--cluster-name",
            "cluster-a",
            "--region",
            "us-west-2",
            "--profile",
            "dev",
            "--state-file",
            str(state_file),
            "--yes",
        ],
    )

    assert result.exit_code == 29
    options = calls["options"]
    assert options.cluster_name == "cluster-a"
    assert options.region == "us-west-2"
    assert options.profile == "dev"
    assert options.state_file == state_file
    assert options.yes is True


def test_resources_dir_command_prints_extracted_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli_module, "ensure_extracted", lambda: tmp_path)

    result = runner.invoke(app, ["resources-dir"])

    assert result.exit_code == 0
    assert result.stdout.strip() == str(tmp_path)


def test_pricing_snapshot_command_passes_collection_options(monkeypatch, tmp_path) -> None:
    import daylily_ec.aws.pricing_snapshots as pricing_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    config_path = tmp_path / "cluster.yaml"
    config_path.write_text("Scheduling: {}\n", encoding="utf-8")

    def fake_collect_pricing_snapshot(**kwargs):
        calls["kwargs"] = kwargs
        return SimpleNamespace(to_dict=lambda: {"ok": True, **kwargs})

    monkeypatch.setattr(
        pricing_module,
        "collect_pricing_snapshot",
        fake_collect_pricing_snapshot,
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "pricing",
            "snapshot",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--region",
            "us-east-1",
            "--partition",
            "i192",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert calls["kwargs"] == {
        "regions": ["us-west-2", "us-east-1"],
        "partitions": ["i192"],
        "cluster_config_path": str(config_path),
        "profile": "dev",
    }


def test_headnode_init_command_passes_runtime_options(monkeypatch) -> None:
    import daylily_ec.headnode as headnode_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)

    def fake_run_headnode_init(**kwargs) -> int:
        calls["kwargs"] = kwargs
        return 31

    monkeypatch.setattr(headnode_module, "run_headnode_init", fake_run_headnode_init)

    result = runner.invoke(
        app,
        [
            "headnode",
            "init",
            "--project",
            "dayoa",
            "--profile",
            "dev",
            "--skip-project-check",
            "--non-interactive",
            "--emit-shell",
        ],
    )

    assert result.exit_code == 31
    assert calls["kwargs"] == {
        "project": "dayoa",
        "profile": "dev",
        "skip_project_check": True,
        "non_interactive": True,
        "emit_shell": True,
    }


def test_runtime_exempt_command_bypasses_runtime_guard(monkeypatch) -> None:
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)

    result = runner.invoke(app, ["--json", "version"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["app"] == "Daylily Ephemeral Cluster"


def test_runtime_required_command_warns_without_active_env(monkeypatch) -> None:
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])

    assert result.exit_code == 1
    assert "DAY-EC conda environment is not active." in result.stderr
    assert "AWS_PROFILE is not set." in result.stderr


def test_headnode_connect_dry_run_prints_session_command(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module

    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)
    monkeypatch.setattr(
        ssm_module,
        "resolve_headnode_instance_id",
        lambda _cluster, _region, *, profile=None: HeadNodeTarget(
            "cluster-a",
            "us-west-2",
            "i-abc123",
        ),
    )
    monkeypatch.setattr(ssm_module, "wait_for_ssm_online", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ssm_module,
        "start_session",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected session")),
    )

    result = runner.invoke(
        app,
        [
            "headnode",
            "connect",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Opening Session Manager session as ubuntu to i-abc123" in result.stdout
    assert "SSM-SessionManagerRunShell" in result.stdout


def test_headnode_connect_starts_session(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)
    monkeypatch.setattr(
        ssm_module,
        "resolve_headnode_instance_id",
        lambda _cluster, _region, *, profile=None: HeadNodeTarget(
            "cluster-a",
            "us-west-2",
            "i-abc123",
        ),
    )
    monkeypatch.setattr(ssm_module, "wait_for_ssm_online", lambda *args, **kwargs: None)

    def fake_start_session(
        instance_id: str,
        region: str,
        *,
        profile: str | None = None,
        replace_process: bool = False,
    ) -> int:
        calls["start_session"] = (instance_id, region, profile, replace_process)
        return 17

    monkeypatch.setattr(ssm_module, "start_session", fake_start_session)

    result = runner.invoke(
        app,
        [
            "headnode",
            "connect",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster-name",
            "cluster-a",
        ],
    )

    assert result.exit_code == 17
    assert calls["start_session"] == ("i-abc123", "us-west-2", "dev", True)


def test_headnode_info_returns_describe_cluster_json(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)
    payload = {
        "clusterName": "cluster-a",
        "clusterStatus": "CREATE_COMPLETE",
        "headNode": {"instanceId": "i-abc123"},
    }

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "-c" in cmd:
            return CompletedProcess(cmd, 0, "", "")
        assert cmd == [
            "pcluster",
            "describe-cluster",
            "--cluster-name",
            "cluster-a",
            "--region",
            "us-west-2",
        ]
        assert kwargs["env"]["AWS_PROFILE"] == "dev"
        return CompletedProcess(cmd, 0, json.dumps(payload), "")

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "--json",
            "headnode",
            "info",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["headNode"]["instanceId"] == "i-abc123"


def test_headnode_info_reports_pcluster_errors(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "-c" in cmd:
            return CompletedProcess(cmd, 0, "", "")
        return CompletedProcess(cmd, 1, "", "access denied")

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "headnode",
            "info",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
        ],
    )

    assert result.exit_code == 1
    assert "pcluster describe-cluster failed: access denied" in result.stderr


def test_headnode_info_reports_missing_pcluster(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "-c" in cmd:
            return CompletedProcess(cmd, 0, "", "")
        raise FileNotFoundError("pcluster")

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "headnode",
            "info",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
        ],
    )

    assert result.exit_code == 1
    assert "pcluster CLI not found on PATH." in result.stderr


def test_headnode_info_reports_invalid_json(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "-c" in cmd:
            return CompletedProcess(cmd, 0, "", "")
        return CompletedProcess(cmd, 0, "not-json", "")

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "headnode",
            "info",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
        ],
    )

    assert result.exit_code == 1
    assert "Failed to parse pcluster describe-cluster output." in result.stderr


def test_headnode_jobs_runs_squeue_with_sq_format(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)
    monkeypatch.setattr(
        ssm_module,
        "resolve_headnode_instance_id",
        lambda _cluster, _region, *, profile=None: HeadNodeTarget(
            "cluster-a",
            "us-west-2",
            "i-abc123",
        ),
    )
    monkeypatch.setattr(ssm_module, "wait_for_ssm_online", lambda *args, **kwargs: None)

    def fake_run_shell(instance_id: str, region: str, script: str, **kwargs):
        calls["run_shell"] = (instance_id, region, script, kwargs)
        return SsmCommandResult("cmd-1", instance_id, "Success", 0, "JOBID PARTITION\n", "")

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)

    result = runner.invoke(
        app,
        [
            "headnode",
            "jobs",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
        ],
    )

    assert result.exit_code == 0
    assert "JOBID PARTITION" in result.stdout
    instance_id, region, script, kwargs = calls["run_shell"]
    assert instance_id == "i-abc123"
    assert region == "us-west-2"
    assert "squeue -o" in script
    assert SQUEUE_FORMAT in script
    assert kwargs["profile"] == "dev"
    assert kwargs["timeout"] == 120


def test_headnode_jobs_surfaces_ssm_failures(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module

    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)
    monkeypatch.setattr(
        ssm_module,
        "resolve_headnode_instance_id",
        lambda _cluster, _region, *, profile=None: HeadNodeTarget(
            "cluster-a",
            "us-west-2",
            "i-abc123",
        ),
    )
    monkeypatch.setattr(ssm_module, "wait_for_ssm_online", lambda *args, **kwargs: None)

    failed_result = SsmCommandResult("cmd-1", "i-abc123", "Failed", 127, "", "squeue missing")

    def fake_run_shell(*args, **kwargs):
        raise SsmCommandFailedError("SSM command 'cmd-1' failed", failed_result)

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)

    result = runner.invoke(
        app,
        [
            "headnode",
            "jobs",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
        ],
    )

    assert result.exit_code == 1
    assert "squeue missing" in result.stderr
    assert "SSM command 'cmd-1' failed" in result.stderr


def test_headnode_configure_uses_workflow_configure(monkeypatch, tmp_path) -> None:
    import daylily_ec.aws.ssm as ssm_module
    import daylily_ec.workflow.create_cluster as workflow_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)
    override_file = tmp_path / "repos.txt"
    override_file.write_text("daylily-omics-analysis:release-1\n", encoding="utf-8")
    monkeypatch.setattr(
        ssm_module,
        "resolve_headnode_instance_id",
        lambda _cluster, _region, *, profile=None: HeadNodeTarget(
            "cluster-a",
            "us-west-2",
            "i-abc123",
        ),
    )
    monkeypatch.setattr(ssm_module, "wait_for_ssm_online", lambda *args, **kwargs: None)

    def fake_configure_headnode(**kwargs):
        calls["configure"] = kwargs
        return True

    monkeypatch.setattr(workflow_module, "configure_headnode", fake_configure_headnode)

    result = runner.invoke(
        app,
        [
            "headnode",
            "configure",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--repo-overrides",
            str(override_file),
        ],
    )

    assert result.exit_code == 0
    assert calls["configure"] == {
        "cluster_name": "cluster-a",
        "head_node_instance_id": "i-abc123",
        "region": "us-west-2",
        "profile": "dev",
        "repo_overrides": {"daylily-omics-analysis": "release-1"},
    }


def test_samples_stage_calls_python_staging_entrypoint(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    samples = tmp_path / "analysis_samples.tsv"
    samples.write_text("SAMPLE_ID\ns1\n", encoding="utf-8")

    def fake_stage(argv: list[str]) -> int:
        calls["argv"] = argv
        return 0

    monkeypatch.setattr(cli_module, "_invoke_stage_samples", fake_stage)

    result = runner.invoke(
        app,
        [
            "samples",
            "stage",
            str(samples),
            "--reference-bucket",
            "s3://bucket",
            "--config-dir",
            str(tmp_path / "cfg"),
            "--stage-target",
            "/data/staged_sample_data",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--debug",
        ],
    )

    assert result.exit_code == 0
    assert calls["argv"] == [
        str(samples),
        "--reference-bucket",
        "s3://bucket",
        "--stage-target",
        "/data/staged_sample_data",
        "--config-dir",
        str(tmp_path / "cfg"),
        "--profile",
        "dev",
        "--region",
        "us-west-2",
        "--debug",
    ]


def test_workflow_launch_calls_python_launch_entrypoint(monkeypatch) -> None:
    import daylily_ec.scripts.daylily_run_omics_analysis_headnode as launch_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)

    def fake_launch(argv: list[str]) -> int:
        calls["argv"] = argv
        return 0

    monkeypatch.setattr(launch_module, "main", fake_launch)

    result = runner.invoke(
        app,
        [
            "workflow",
            "launch",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--stage-dir",
            "/fsx/stage/run-1",
            "--session-name",
            "sess-1",
            "--sv-callers",
            "tiddit",
            "--strict-project-check",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    argv = calls["argv"]
    assert "--profile" in argv
    assert "dev" in argv
    assert "--cluster" in argv
    assert "cluster-a" in argv
    assert "--stage-dir" in argv
    assert "/fsx/stage/run-1" in argv
    assert "--session-name" in argv
    assert "sess-1" in argv
    assert "--sv-callers" in argv
    assert "tiddit" in argv
    assert "--strict-project-check" in argv
    assert "--dry-run" in argv


def test_workflow_status_reads_status_json_via_ssm(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)
    monkeypatch.setattr(
        ssm_module,
        "resolve_headnode_instance_id",
        lambda _cluster, _region, *, profile=None: HeadNodeTarget(
            "cluster-a",
            "us-west-2",
            "i-abc123",
        ),
    )
    monkeypatch.setattr(ssm_module, "wait_for_ssm_online", lambda *args, **kwargs: None)

    def fake_run_shell(instance_id: str, region: str, script: str, **kwargs):
        calls["run_shell"] = (instance_id, region, script, kwargs)
        return SsmCommandResult(
            "cmd-1",
            instance_id,
            "Success",
            0,
            'DAY-EC activated.\n{"session_name":"sess-1","exit_code":0}\n',
            "",
        )

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)

    result = runner.invoke(
        app,
        [
            "--json",
            "workflow",
            "status",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--session",
            "sess-1",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["session_name"] == "sess-1"
    _instance_id, _region, script, kwargs = calls["run_shell"]
    assert "/home/ubuntu/daylily-runs/sess-1/status.json" in script
    assert kwargs["profile"] == "dev"


def test_workflow_logs_tails_tmux_log_via_ssm(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)
    monkeypatch.setattr(
        ssm_module,
        "resolve_headnode_instance_id",
        lambda _cluster, _region, *, profile=None: HeadNodeTarget(
            "cluster-a",
            "us-west-2",
            "i-abc123",
        ),
    )
    monkeypatch.setattr(ssm_module, "wait_for_ssm_online", lambda *args, **kwargs: None)

    def fake_run_shell(instance_id: str, region: str, script: str, **kwargs):
        calls["script"] = script
        return SsmCommandResult("cmd-1", instance_id, "Success", 0, "line 1\n", "")

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)

    result = runner.invoke(
        app,
        [
            "workflow",
            "logs",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--run-dir",
            "/home/ubuntu/daylily-runs/sess-1",
            "--lines",
            "50",
        ],
    )

    assert result.exit_code == 0
    assert "line 1" in result.stdout
    assert "tmux.log" in calls["script"]
    assert "tail -n 50" in calls["script"]


def test_delete_dry_run_never_calls_delete_workflow(monkeypatch) -> None:
    import daylily_ec.workflow.delete_cluster as delete_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)

    def fake_dry_run(options):
        calls["dry_run"] = options
        return 0

    def fake_delete(_options):
        raise AssertionError("delete workflow should not run")

    monkeypatch.setattr(delete_module, "run_delete_dry_run", fake_dry_run)
    monkeypatch.setattr(delete_module, "run_delete_workflow", fake_delete)

    result = runner.invoke(
        app,
        [
            "delete",
            "--dry-run",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster-name",
            "cluster-a",
        ],
    )

    assert result.exit_code == 0
    assert calls["dry_run"].cluster_name == "cluster-a"


def test_state_list_and_show_are_json_capable(monkeypatch, tmp_path) -> None:
    _activate_dayec_runtime(monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    state_dir = tmp_path / "daylily"
    state_dir.mkdir()
    first = StateRecord(
        run_id="20260101010101",
        cluster_name="cluster-a",
        region="us-west-2",
        aws_profile="dev",
    )
    second = StateRecord(
        run_id="20260102020202",
        cluster_name="cluster-a",
        region="us-west-2",
        aws_profile="dev",
    )
    (state_dir / "state_cluster-a_20260101010101.json").write_text(
        first.to_sorted_json() + "\n",
        encoding="utf-8",
    )
    (state_dir / "state_cluster-a_20260102020202.json").write_text(
        second.to_sorted_json() + "\n",
        encoding="utf-8",
    )

    list_result = runner.invoke(app, ["--json", "state", "list"])
    assert list_result.exit_code == 0
    list_payload = json.loads(list_result.stdout)
    assert len(list_payload["states"]) == 2

    show_result = runner.invoke(app, ["--json", "state", "show", "--cluster-name", "cluster-a"])
    assert show_result.exit_code == 0
    show_payload = json.loads(show_result.stdout)
    assert show_payload["run_id"] == "20260102020202"
