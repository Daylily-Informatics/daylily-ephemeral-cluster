from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess
import sys
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import daylily_ec.cli as cli_module
from daylily_ec import versioning
from daylily_ec.aws.ssm import (
    HeadNodeTarget,
    SsmCommandFailedError,
    SsmCommandResult,
)
from daylily_ec.cli import app, spec
from daylily_ec.headnode import SQUEUE_FORMAT
from daylily_ec.state.models import StateRecord

runner = CliRunner()


DAYOA_BLESSED_TAG = "10.0.72"

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
    ("cluster", "tags"),
    ("export",),
    ("exports", "attach"),
    ("exports", "run"),
    ("exports", "detach"),
    ("exports", "register-dewey"),
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
    ("pricing", "spot-logs"),
    ("aws", "validate", "permissions"),
    ("aws", "validate", "quotas"),
    ("aws", "validate", "all"),
    ("slurm-accounting", "ensure"),
    ("cost-centers", "ensure-registry"),
    ("cost-centers", "create"),
    ("cost-centers", "edit"),
    ("cost-centers", "disable"),
    ("cost-centers", "show"),
    ("cost-centers", "list"),
    ("cost-centers", "usage"),
    ("cost-centers", "put-usage"),
    ("cost-centers", "ensure-cur-export"),
    ("headnode", "init"),
    ("headnode", "connect"),
    ("headnode", "info"),
    ("headnode", "jobs"),
    ("headnode", "configure"),
    ("headnode", "configure-dragen"),
    ("samples", "stage"),
    ("samples", "run"),
    ("workflow", "launch"),
    ("workflow", "status"),
    ("workflow", "logs"),
    ("workflow", "collect-benchmarks"),
    ("workflow", "stop"),
    ("repositories", "commands"),
    ("tests", "pytest"),
    ("tests", "command-catalog"),
    ("tests", "command-catalog-performance"),
    ("mounts", "list"),
    ("mounts", "create"),
    ("mounts", "describe"),
    ("mounts", "delete"),
    ("mounts", "verify"),
    ("mount", "rundir"),
    ("state", "list"),
    ("state", "show"),
    ("analysis", "visit"),
    ("analysis", "guard"),
    ("analysis", "lock", "status"),
    ("analysis", "lock", "acquire"),
    ("analysis", "lock", "release"),
    ("analysis", "lock", "heartbeat"),
    ("analysis", "lock", "takeover"),
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


def test_main_propagates_command_return_code(monkeypatch, tmp_path) -> None:
    import daylily_ec.cli as cli

    _activate_dayec_runtime(monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dyec",
            "export",
            "--cluster-name",
            "alpha",
            "--source-path",
            "/fsx/analysis_results/johnm/a",
            "--destination-s3-uri",
            "s3://bucket/johnm/a/",
            "--region",
            "us-west-2",
            "--output-dir",
            str(tmp_path),
        ],
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data.configure_logging",
        lambda _verbose: None,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data.run_export_workflow",
        lambda _options: 1,
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1


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
    exports_attach_cmd = registry.get_command(("exports", "attach"))
    exports_run_cmd = registry.get_command(("exports", "run"))
    exports_detach_cmd = registry.get_command(("exports", "detach"))
    resources_dir_cmd = registry.get_command(("resources-dir",))
    cluster_info_cmd = registry.get_command(("cluster-info",))
    cluster_list_cmd = registry.get_command(("cluster", "list"))
    cluster_describe_cmd = registry.get_command(("cluster", "describe"))
    cluster_wait_cmd = registry.get_command(("cluster", "wait"))
    cluster_tags_cmd = registry.get_command(("cluster", "tags"))
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
    headnode_configure_dragen_cmd = registry.get_command(("headnode", "configure-dragen"))
    samples_stage_cmd = registry.get_command(("samples", "stage"))
    workflow_launch_cmd = registry.get_command(("workflow", "launch"))
    workflow_status_cmd = registry.get_command(("workflow", "status"))
    workflow_logs_cmd = registry.get_command(("workflow", "logs"))
    workflow_collect_benchmarks_cmd = registry.get_command(("workflow", "collect-benchmarks"))
    workflow_stop_cmd = registry.get_command(("workflow", "stop"))
    repositories_commands_cmd = registry.get_command(("repositories", "commands"))
    tests_pytest_cmd = registry.get_command(("tests", "pytest"))
    tests_command_catalog_cmd = registry.get_command(("tests", "command-catalog"))
    tests_command_catalog_performance_cmd = registry.get_command(
        ("tests", "command-catalog-performance")
    )
    mounts_list_cmd = registry.get_command(("mounts", "list"))
    mounts_create_cmd = registry.get_command(("mounts", "create"))
    mounts_describe_cmd = registry.get_command(("mounts", "describe"))
    mounts_delete_cmd = registry.get_command(("mounts", "delete"))
    mounts_verify_cmd = registry.get_command(("mounts", "verify"))
    mount_rundir_cmd = registry.get_command(("mount", "rundir"))
    state_list_cmd = registry.get_command(("state", "list"))
    state_show_cmd = registry.get_command(("state", "show"))
    analysis_visit_cmd = registry.get_command(("analysis", "visit"))
    analysis_guard_cmd = registry.get_command(("analysis", "guard"))
    analysis_lock_status_cmd = registry.get_command(("analysis", "lock", "status"))
    analysis_lock_acquire_cmd = registry.get_command(("analysis", "lock", "acquire"))
    analysis_lock_release_cmd = registry.get_command(("analysis", "lock", "release"))
    analysis_lock_heartbeat_cmd = registry.get_command(("analysis", "lock", "heartbeat"))
    analysis_lock_takeover_cmd = registry.get_command(("analysis", "lock", "takeover"))
    pricing_snapshot_cmd = registry.get_command(("pricing", "snapshot"))
    pricing_spot_logs_cmd = registry.get_command(("pricing", "spot-logs"))
    aws_validate_permissions_cmd = registry.get_command(("aws", "validate", "permissions"))
    aws_validate_quotas_cmd = registry.get_command(("aws", "validate", "quotas"))
    aws_validate_all_cmd = registry.get_command(("aws", "validate", "all"))
    slurm_accounting_ensure_cmd = registry.get_command(("slurm-accounting", "ensure"))
    cost_centers_put_usage_cmd = registry.get_command(("cost-centers", "put-usage"))
    cost_centers_ensure_cur_export_cmd = registry.get_command(("cost-centers", "ensure-cur-export"))

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

    for exports_cmd in (exports_attach_cmd, exports_run_cmd, exports_detach_cmd):
        assert exports_cmd is not None
        assert exports_cmd.policy.supports_json is True
        assert exports_cmd.policy.mutates_state is True
        assert exports_cmd.policy.long_running is True

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

    assert cluster_tags_cmd is not None
    assert cluster_tags_cmd.policy.supports_json is True
    assert cluster_tags_cmd.policy.mutates_state is True
    assert cluster_tags_cmd.policy.long_running is True

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
    assert headnode_configure_dragen_cmd is not None
    assert headnode_configure_dragen_cmd.policy.mutates_state is True
    assert headnode_configure_dragen_cmd.policy.long_running is True

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

    assert workflow_collect_benchmarks_cmd is not None
    assert workflow_collect_benchmarks_cmd.policy.supports_json is True
    assert workflow_collect_benchmarks_cmd.policy.mutates_state is True
    assert workflow_collect_benchmarks_cmd.policy.long_running is True

    assert workflow_stop_cmd is not None
    assert workflow_stop_cmd.policy.supports_json is True
    assert workflow_stop_cmd.policy.mutates_state is True

    assert repositories_commands_cmd is not None
    assert repositories_commands_cmd.policy.supports_json is True
    assert repositories_commands_cmd.policy.runtime_guard == "exempt"

    assert tests_pytest_cmd is not None
    assert tests_pytest_cmd.policy.long_running is True
    assert tests_pytest_cmd.policy.mutates_state is False

    assert tests_command_catalog_cmd is not None
    assert tests_command_catalog_cmd.policy.supports_json is True
    assert tests_command_catalog_cmd.policy.mutates_state is True
    assert tests_command_catalog_cmd.policy.long_running is True

    assert tests_command_catalog_performance_cmd is not None
    assert tests_command_catalog_performance_cmd.policy.supports_json is True
    assert tests_command_catalog_performance_cmd.policy.runtime_guard == "exempt"
    assert tests_command_catalog_performance_cmd.policy.mutates_state is False

    assert mounts_list_cmd is not None
    assert mounts_list_cmd.policy.supports_json is True

    assert mounts_create_cmd is not None
    assert mounts_create_cmd.policy.supports_json is True
    assert mounts_create_cmd.policy.mutates_state is True
    assert mounts_create_cmd.policy.long_running is True

    assert mounts_describe_cmd is not None
    assert mounts_describe_cmd.policy.supports_json is True

    assert mounts_delete_cmd is not None
    assert mounts_delete_cmd.policy.supports_json is True
    assert mounts_delete_cmd.policy.mutates_state is True
    assert mounts_delete_cmd.policy.long_running is True

    assert mounts_verify_cmd is not None
    assert mounts_verify_cmd.policy.supports_json is True
    assert mounts_verify_cmd.policy.long_running is True

    assert mount_rundir_cmd is not None
    assert mount_rundir_cmd.policy.supports_json is True
    assert mount_rundir_cmd.policy.mutates_state is True
    assert mount_rundir_cmd.policy.long_running is True

    assert state_list_cmd is not None
    assert state_list_cmd.policy.supports_json is True
    assert state_list_cmd.policy.runtime_guard == "exempt"

    assert state_show_cmd is not None
    assert state_show_cmd.policy.supports_json is True
    assert state_show_cmd.policy.runtime_guard == "exempt"

    assert analysis_visit_cmd is not None
    assert analysis_visit_cmd.policy.supports_json is True
    assert analysis_visit_cmd.policy.mutates_state is True

    assert analysis_guard_cmd is not None
    assert analysis_guard_cmd.policy.mutates_state is True

    assert analysis_lock_status_cmd is not None
    assert analysis_lock_status_cmd.policy.supports_json is True
    assert analysis_lock_status_cmd.policy.mutates_state is False

    for analysis_lock_cmd in (
        analysis_lock_acquire_cmd,
        analysis_lock_release_cmd,
        analysis_lock_heartbeat_cmd,
        analysis_lock_takeover_cmd,
    ):
        assert analysis_lock_cmd is not None
        assert analysis_lock_cmd.policy.supports_json is True
        assert analysis_lock_cmd.policy.mutates_state is True

    assert pricing_snapshot_cmd is not None
    assert pricing_snapshot_cmd.policy.supports_json is True
    assert pricing_spot_logs_cmd is not None
    assert pricing_spot_logs_cmd.policy.supports_json is True

    for aws_validate_cmd in (
        aws_validate_permissions_cmd,
        aws_validate_quotas_cmd,
        aws_validate_all_cmd,
    ):
        assert aws_validate_cmd is not None
        assert aws_validate_cmd.policy.supports_json is True
        assert aws_validate_cmd.policy.mutates_state is False

    assert slurm_accounting_ensure_cmd is not None
    assert slurm_accounting_ensure_cmd.policy.supports_json is True
    assert slurm_accounting_ensure_cmd.policy.mutates_state is True
    assert slurm_accounting_ensure_cmd.policy.long_running is True

    assert cost_centers_put_usage_cmd is not None
    assert cost_centers_put_usage_cmd.policy.supports_json is True
    assert cost_centers_put_usage_cmd.policy.mutates_state is True
    assert cost_centers_put_usage_cmd.policy.long_running is False

    assert cost_centers_ensure_cur_export_cmd is not None
    assert cost_centers_ensure_cur_export_cmd.policy.supports_json is True
    assert cost_centers_ensure_cur_export_cmd.policy.mutates_state is True
    assert cost_centers_ensure_cur_export_cmd.policy.long_running is True


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
    versioning.get_version.cache_clear()
    result = runner.invoke(app, ["--json", "version"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["app"] == "Daylily Ephemeral Cluster"
    assert payload["version"] == versioning.get_version()


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
            "--cluster-type",
            "rhel",
            "--profile",
            "dev",
            "--config",
            str(config_path),
            "--pass-on-warn",
            "--debug",
            "--non-interactive",
            "--disable-budget-enforcement",
            "--create-slurm-accounting-db",
            "--slurm-accounting-stack-name",
            "dayec-costacct-20260705T000000Z",
        ],
    )

    assert result.exit_code == 17
    assert calls["region_az"] == "us-west-2d"
    assert calls["kwargs"] == {
        "profile": "dev",
        "config_path": str(config_path),
        "cluster_type": "rhel",
        "pass_on_warn": True,
        "debug": True,
        "non_interactive": True,
        "disable_budget_enforcement": True,
        "budget_project": None,
        "create_slurm_accounting_db": True,
        "scan_slurm_accounting_db": False,
        "slurm_accounting_stack_name": "dayec-costacct-20260705T000000Z",
        "global_spot_max_cost": 7.5,
        "spot_cost_limit_pct": 1.2,
        "write_spot_pricing_warn_threshold": 6.0,
    }


def test_create_command_defaults_region_az_to_us_west_2d(monkeypatch, tmp_path) -> None:
    import daylily_ec.workflow.create_cluster as create_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    config_path = tmp_path / "daylily.yaml"
    config_path.write_text("cluster_name: cluster-a\n", encoding="utf-8")

    def fake_run_create_workflow(region_az: str, **kwargs) -> int:
        calls["region_az"] = region_az
        calls["kwargs"] = kwargs
        return 0

    monkeypatch.setattr(create_module, "run_create_workflow", fake_run_create_workflow)

    result = runner.invoke(
        app,
        [
            "create",
            "--profile",
            "dev",
            "--config",
            str(config_path),
            "--non-interactive",
        ],
    )

    assert result.exit_code == 0
    assert calls["region_az"] == cli_module.DEFAULT_CREATE_REGION_AZ == "us-west-2d"
    assert calls["kwargs"]["profile"] == "dev"
    assert calls["kwargs"]["config_path"] == str(config_path)
    assert calls["kwargs"]["cluster_type"] == "intel"
    assert calls["kwargs"]["non_interactive"] is True
    assert calls["kwargs"]["global_spot_max_cost"] == 7.5
    assert calls["kwargs"]["spot_cost_limit_pct"] == 1.2
    assert calls["kwargs"]["write_spot_pricing_warn_threshold"] == 6.0


@pytest.mark.parametrize(
    ("flag", "value", "message"),
    [
        ("--global-spot-max-cost", "10.01", "--global-spot-max-cost"),
        ("--spot-cost-limit-pct", "0.99", "--spot-cost-limit-pct"),
        ("--spot-cost-limit-pct", "1.41", "--spot-cost-limit-pct"),
        (
            "--write-spot-pricing-warn-threshold",
            "0",
            "--write-spot-pricing-warn-threshold",
        ),
    ],
)
def test_create_command_rejects_invalid_spot_pricing_options(
    monkeypatch,
    flag: str,
    value: str,
    message: str,
) -> None:
    _activate_dayec_runtime(monkeypatch)

    result = runner.invoke(
        app,
        [
            "create",
            "--region-az",
            "us-west-2d",
            flag,
            value,
        ],
    )

    assert result.exit_code == 2
    assert message in result.output


def test_create_command_rejects_invalid_cluster_type(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)

    result = runner.invoke(
        app,
        [
            "create",
            "--region-az",
            "us-west-2d",
            "--cluster-type",
            "dragen",
        ],
    )

    assert result.exit_code == 2
    assert "--cluster-type must be one of" in result.output


def test_create_command_rejects_retired_budget_project(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)

    result = runner.invoke(
        app,
        [
            "create",
            "--region-az",
            "us-west-2d",
            "--budget-project",
            "rna-seq-prod",
        ],
    )

    assert result.exit_code == 2
    assert "--budget-project is retired" in result.output


def test_create_command_passes_scan_slurm_accounting_option(monkeypatch, tmp_path) -> None:
    import daylily_ec.workflow.create_cluster as create_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    config_path = tmp_path / "daylily.yaml"
    config_path.write_text("cluster_name: cluster-a\n", encoding="utf-8")

    def fake_run_create_workflow(region_az: str, **kwargs) -> int:
        calls["region_az"] = region_az
        calls["kwargs"] = kwargs
        return 0

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
            "--scan-slurm-accounting-db",
        ],
    )

    assert result.exit_code == 0
    assert calls["region_az"] == "us-west-2d"
    assert calls["kwargs"]["scan_slurm_accounting_db"] is True
    assert calls["kwargs"]["create_slurm_accounting_db"] is False
    assert calls["kwargs"]["disable_budget_enforcement"] is False
    assert calls["kwargs"]["budget_project"] is None


def test_create_command_rejects_scan_and_create_slurm_accounting_flags(
    monkeypatch,
) -> None:
    _activate_dayec_runtime(monkeypatch)

    result = runner.invoke(
        app,
        [
            "create",
            "--region-az",
            "us-west-2d",
            "--scan-slurm-accounting-db",
            "--create-slurm-accounting-db",
        ],
    )

    assert result.exit_code == 2
    assert "--scan-slurm-accounting-db cannot be combined" in result.stderr


def test_slurm_accounting_ensure_reports_resolved_db(monkeypatch) -> None:
    import daylily_ec.aws.cloudformation as cloudformation_module
    import daylily_ec.aws.context as context_module
    import daylily_ec.aws.slurm_accounting as accounting_module

    _activate_dayec_runtime(monkeypatch)
    calls: dict[str, object] = {}

    class FakeContext:
        profile = "lsmc"
        region = "us-west-2"
        region_az = "us-west-2b"

        def client(self, service: str) -> object:
            calls.setdefault("clients", []).append(service)
            return object()

    def fake_build(cls, region_az: str, profile: str | None = None) -> FakeContext:
        calls["build"] = (region_az, profile)
        return FakeContext()

    def fake_ensure_pcluster_env_stack(_aws_ctx, region_az: str):
        calls["baseline_region_az"] = region_az
        return SimpleNamespace(vpc_id="vpc-123", private_subnet_id="subnet-private")

    def fake_ensure_slurm_accounting_db(_aws_ctx, **kwargs):
        calls["ensure_kwargs"] = kwargs
        return accounting_module.SlurmAccountingDb(
            stack_name="dayec-slurm-accounting-us-west-2b",
            status="CREATE_COMPLETE",
            uri="10.0.1.10:3306",
            private_ip="10.0.1.10",
            database_name="dayec_slurm_acct",
            username="slurm_acct",
            password_secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:acct",
            client_security_group_id="sg-0123456789abcdef0",
            instance_id="i-0123456789abcdef0",
        )

    monkeypatch.setattr(context_module.AWSContext, "build", classmethod(fake_build))
    monkeypatch.setattr(
        cloudformation_module,
        "ensure_pcluster_env_stack",
        fake_ensure_pcluster_env_stack,
    )
    monkeypatch.setattr(
        accounting_module,
        "ensure_slurm_accounting_db",
        fake_ensure_slurm_accounting_db,
    )

    result = runner.invoke(
        app,
        [
            "slurm-accounting",
            "ensure",
            "--profile",
            "lsmc",
            "--region-az",
            "us-west-2b",
        ],
    )

    assert result.exit_code == 0
    assert "URI:       10.0.1.10:3306" in result.stdout
    assert calls["build"] == ("us-west-2b", "lsmc")
    assert calls["baseline_region_az"] == "us-west-2b"
    assert calls["ensure_kwargs"] == {
        "region_az": "us-west-2b",
        "vpc_id": "vpc-123",
        "private_subnet_id": "subnet-private",
        "create_if_missing": True,
        "stack_name": "",
        "database_name": "dayec_slurm_acct",
        "username": "slurm_acct",
        "instance_type": "t4g.micro",
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
            "--source-path",
            "/fsx/analysis_results/johnm/illumina_run_qc",
            "--destination-s3-uri",
            "s3://bucket/analysis_results/johnm/illumina_run_qc/",
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
    assert not hasattr(options, "export_id")
    assert options.source_path == "/fsx/analysis_results/johnm/illumina_run_qc"
    assert options.destination_s3_uri == "s3://bucket/analysis_results/johnm/illumina_run_qc/"
    assert options.region == "us-west-2"
    assert options.profile == "dev"
    assert options.output_dir == tmp_path.resolve()


def test_export_command_rejects_dewey_options_without_policy(monkeypatch, tmp_path) -> None:
    _activate_dayec_runtime(monkeypatch)

    result = runner.invoke(
        app,
        [
            "export",
            "--cluster-name",
            "cluster-a",
            "--source-path",
            "/fsx/analysis_results/johnm/illumina_run_qc",
            "--destination-s3-uri",
            "s3://bucket/analysis_results/johnm/illumina_run_qc/",
            "--region",
            "us-west-2",
            "--output-dir",
            str(tmp_path),
            "--dewey-url",
            "https://dewey.example",
            "--dewey-token-env",
            "DEWEY_TOKEN",
        ],
    )

    assert result.exit_code != 0
    assert "artifact-registration-command-id" in result.output


def test_export_command_passes_dewey_external_link_options(monkeypatch, tmp_path) -> None:
    import daylily_ec.workflow.export_data as export_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)

    def fake_run_export_workflow(options) -> int:
        calls["options"] = options
        return 0

    monkeypatch.setattr(export_module, "run_export_workflow", fake_run_export_workflow)

    result = runner.invoke(
        app,
        [
            "export",
            "--cluster-name",
            "cluster-a",
            "--source-path",
            "/fsx/analysis_results/johnm/illumina_run_qc",
            "--destination-s3-uri",
            "s3://bucket/analysis_results/johnm/illumina_run_qc/",
            "--region",
            "us-west-2",
            "--output-dir",
            str(tmp_path),
            "--artifact-registration-command-id",
            "illumina_snv_alignstats_relatedness_vep_multiqc",
            "--dewey-url",
            "https://dewey.example",
            "--dewey-token-env",
            "DEWEY_TOKEN",
            "--dewey-analysis-dir-external-object-id",
            "M-RGX-9S3G",
            "--dewey-run-artifact-euid",
            "M-DGX-9SD7",
            "--dewey-ursa-analysis-euid",
            "M-RGX-9S3G",
        ],
    )

    assert result.exit_code == 0
    options = calls["options"]
    assert options.dewey_analysis_dir_external_object_id == "M-RGX-9S3G"
    assert options.dewey_run_artifact_euid == "M-DGX-9SD7"
    assert options.dewey_ursa_analysis_euid == "M-RGX-9S3G"


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


def test_pricing_spot_logs_exports_csv_via_ssm(monkeypatch, tmp_path) -> None:
    import daylily_ec.aws.ssm as ssm_module
    from daylily_ec.spot_price_logs import (
        SPOT_PRICE_LOG_JSON_BEGIN,
        SPOT_PRICE_LOG_JSON_END,
    )

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
        payload = {
            "rows": [
                {
                    "source_path": "/fsx/scratch/ip-10-0-0-1_spot_price.log",
                    "line_number": "4",
                    "recorded_at": "2026-07-03 12:01:02",
                    "region": "us-west-2",
                    "availability_zone": "us-west-2c",
                    "instance_type": "f2.6xlarge",
                    "spot_price_usd_per_hour": "1.234",
                    "node_type": "ComputeFleet",
                    "slurm_partition": "dragen",
                    "compute_resource": "f26xlarge",
                    "hostname": "ip-10-0-0-1",
                    "instance_id": "i-node",
                    "raw_line": "spot row",
                },
                {
                    "source_path": "/fsx/scratch/ip-10-0-0-1_spot_price.log",
                    "line_number": "5",
                    "recorded_at": "2026-07-03 12:31:02",
                    "recorded_at_epoch": "1783081862",
                    "region": "us-west-2",
                    "availability_zone": "us-west-2c",
                    "instance_type": "f2.6xlarge",
                    "spot_price_usd_per_hour": "1.234",
                    "node_type": "ComputeFleet",
                    "slurm_partition": "dragen",
                    "compute_resource": "f26xlarge",
                    "hostname": "ip-10-0-0-1",
                    "instance_id": "i-node",
                    "event": "shutdown",
                    "shutdown_reason": "systemd-stop",
                    "raw_line": "shutdown row",
                },
            ],
            "paths": ["/fsx/logs", "/fsx/scratch"],
            "name_globs": ["*.log"],
            "visited_files": 2,
        }
        stdout = "\n".join(
            [
                "noise before payload",
                SPOT_PRICE_LOG_JSON_BEGIN,
                json.dumps(payload),
                SPOT_PRICE_LOG_JSON_END,
                "",
            ]
        )
        return SsmCommandResult("cmd-1", instance_id, "Success", 0, stdout, "")

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)

    result = runner.invoke(
        app,
        [
            "pricing",
            "spot-logs",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--path",
            "/fsx/logs",
            "--path",
            "/fsx/scratch",
            "--output",
            str(tmp_path / "spot.csv"),
            "--cost-output",
            str(tmp_path / "cost.csv"),
            "--cost-price-source",
            "logged",
        ],
    )

    assert result.exit_code == 0
    output_path = tmp_path / "spot.csv"
    cost_path = tmp_path / "cost.csv"
    assert result.stdout.strip().splitlines() == [str(output_path), str(cost_path)]
    text = output_path.read_text(encoding="utf-8")
    assert "cluster,headnode_instance_id,source_path" in text
    assert "cluster-a,i-abc123,/fsx/scratch/ip-10-0-0-1_spot_price.log" in text
    assert ",dragen,f26xlarge," in text
    cost_text = cost_path.read_text(encoding="utf-8")
    assert "instance_id,hostname,node_type" in cost_text
    assert "i-node,ip-10-0-0-1,ComputeFleet" in cost_text
    assert "0.61700000" in cost_text
    instance_id, region, script, kwargs = calls["run_shell"]
    assert instance_id == "i-abc123"
    assert region == "us-west-2"
    assert 'roots = ["/fsx/logs", "/fsx/scratch"]' in script
    assert 'name_globs = ["*.log"]' in script
    assert kwargs["profile"] == "dev"
    assert kwargs["as_user"] == "auto"
    assert kwargs["timeout"] == 300
    assert kwargs["comment"] == "Daylily spot price log export"


def test_pricing_spot_logs_supports_json(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module
    from daylily_ec.spot_price_logs import (
        SPOT_PRICE_LOG_JSON_BEGIN,
        SPOT_PRICE_LOG_JSON_END,
    )

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
    stdout = "\n".join(
        [
            SPOT_PRICE_LOG_JSON_BEGIN,
            '{"rows": [], "paths": ["/fsx/tmp"], "name_globs": ["*.log"], "visited_files": 0}',
            SPOT_PRICE_LOG_JSON_END,
        ]
    )
    monkeypatch.setattr(
        ssm_module,
        "run_shell",
        lambda instance_id, region, script, **kwargs: SsmCommandResult(
            "cmd-1",
            instance_id,
            "Success",
            0,
            stdout,
            "",
        ),
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "pricing",
            "spot-logs",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--path",
            "/fsx/tmp",
            "--allow-empty",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["cluster"] == "cluster-a"
    assert payload["headnode_instance_id"] == "i-abc123"
    assert payload["paths"] == ["/fsx/tmp"]
    assert payload["row_count"] == 0
    assert payload["cost_interval_count"] == 0
    assert payload["cost_intervals"] == []


def test_aws_validate_all_passes_options_and_json(monkeypatch, tmp_path) -> None:
    import daylily_ec.aws.validation as validation_module
    from daylily_ec.aws.validation import AwsValidationReport
    from daylily_ec.state.models import CheckResult, CheckStatus

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    config_path = tmp_path / "daylily.yaml"
    gap_path = tmp_path / "gap.md"
    config_path.write_text("ephemeral_cluster: {}\n", encoding="utf-8")

    def fake_run_aws_validation(options):
        calls["options"] = options
        report = AwsValidationReport(
            mode=options.mode,
            region="us-west-2",
            region_az=options.region_az,
            aws_profile=options.profile,
            account_id="123456789012",
            caller_arn="arn:aws:iam::123456789012:user/alice",
            config_path=str(config_path),
            checks=[
                CheckResult(
                    id="aws.identity",
                    status=CheckStatus.PASS,
                    details={"ok": True},
                )
            ],
            summary={"PASS": 1, "WARN": 0, "FAIL": 0},
        )
        return 0, report

    monkeypatch.setattr(validation_module, "run_aws_validation", fake_run_aws_validation)

    result = runner.invoke(
        app,
        [
            "--json",
            "aws",
            "validate",
            "all",
            "--profile",
            "dev",
            "--region-az",
            "us-west-2b",
            "--config",
            str(config_path),
            "--gap-analysis",
            str(gap_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "all"
    assert payload["summary"] == {"PASS": 1, "WARN": 0, "FAIL": 0}
    options = calls["options"]
    assert options.mode == "all"
    assert options.profile == "dev"
    assert options.region_az == "us-west-2b"
    assert options.config_path == str(config_path)
    assert options.gap_analysis_path == gap_path


def test_aws_validate_requires_profile() -> None:
    result = runner.invoke(
        app,
        ["aws", "validate", "permissions", "--region-az", "us-west-2b"],
    )

    assert result.exit_code == 2


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
    assert kwargs["as_user"] == "auto"
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
        "remote_user": "ubuntu",
    }


def test_headnode_configure_dragen_uses_ec2_user(monkeypatch, tmp_path) -> None:
    import daylily_ec.aws.ssm as ssm_module
    import daylily_ec.workflow.create_cluster as workflow_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch, cluster="dragen-cluster")
    override_file = tmp_path / "repos.txt"
    override_file.write_text("daylily-omics-analysis:release-1\n", encoding="utf-8")
    monkeypatch.setattr(
        ssm_module,
        "resolve_headnode_instance_id",
        lambda _cluster, _region, *, profile=None: HeadNodeTarget(
            "dragen-cluster",
            "us-west-2",
            "i-drg123",
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
            "configure-dragen",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "dragen-cluster",
            "--repo-overrides",
            str(override_file),
        ],
    )

    assert result.exit_code == 0
    assert calls["configure"] == {
        "cluster_name": "dragen-cluster",
        "head_node_instance_id": "i-drg123",
        "region": "us-west-2",
        "profile": "dev",
        "repo_overrides": {"daylily-omics-analysis": "release-1"},
        "remote_user": "ec2-user",
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
            "--reference-s3-uri",
            "s3://reference-bucket",
            "--control-data-s3-uri",
            "s3://control-data-bucket",
            "--stage-s3-uri",
            "s3://stage-bucket",
            "--config-dir",
            str(tmp_path / "cfg"),
            "--stage-target",
            "/fsx/staging/staged_external_sequencing_data",
            "--run-metric-staging",
            "RUN1:ILMN:/tmp/run1.fofn",
            "--run-metric-staging",
            "RUN2:ONT:/tmp/run2.fofn",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--debug",
            "--precheck-only",
        ],
    )

    assert result.exit_code == 0
    assert calls["argv"] == [
        str(samples),
        "--reference-s3-uri",
        "s3://reference-bucket",
        "--control-data-s3-uri",
        "s3://control-data-bucket",
        "--stage-s3-uri",
        "s3://stage-bucket",
        "--stage-target",
        "/fsx/staging/staged_external_sequencing_data",
        "--run-metric-staging",
        "RUN1:ILMN:/tmp/run1.fofn",
        "--run-metric-staging",
        "RUN2:ONT:/tmp/run2.fofn",
        "--config-dir",
        str(tmp_path / "cfg"),
        "--profile",
        "dev",
        "--region",
        "us-west-2",
        "--debug",
        "--precheck-only",
    ]


def test_samples_stage_help_does_not_advertise_generated_cram_index_flags() -> None:
    result = runner.invoke(app, ["samples", "stage", "--help"])

    assert result.exit_code == 0
    assert "--generate-missing-cram-indexes" not in result.stdout
    assert "--index-threads" not in result.stdout


def _write_complete_genomics_manifest(path) -> None:
    path.write_text(
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "CG_R1_FQ",
                "CG_R2_FQ",
            ]
        )
        + "\n"
        + "\t".join(
            [
                "CGT7P",
                "HG003",
                "T7PLUS",
                "blood",
                "PCR-FREE",
                "CG",
                "DNBSEQ",
                "0",
                "D0",
                "s3://bucket/HG003_R1.fastq.gz",
                "s3://bucket/HG003_R2.fastq.gz",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_samples_run_stages_then_launches_catalog_command(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    manifest = tmp_path / "analysis_samples.tsv"
    config_dir = tmp_path / "cfg"
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        (
            Path(__file__).resolve().parents[1] / "config" / "daylily_pipeline_command_catalog.yaml"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_complete_genomics_manifest(manifest)

    def fake_stage(argv: list[str]) -> int:
        calls["stage_argv"] = argv
        print("Remote staging completed successfully.")
        print(
            "Remote FSx stage directory: /fsx/staging/staged_external_sequencing_data/remote_stage_20260425T000000Z"
        )
        return 0

    def fake_launch(argv: list[str]) -> int:
        calls["launch_argv"] = argv
        print("__DAYLILY_SESSION__=cg-session")
        print("__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/cg-session")
        print("__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/cg-run/daylily-omics-analysis")
        return 0

    monkeypatch.setattr(cli_module, "_invoke_stage_samples", fake_stage)
    monkeypatch.setattr(cli_module, "_invoke_workflow_launch", fake_launch)

    result = runner.invoke(
        app,
        [
            "samples",
            "run",
            str(manifest),
            "--catalog-config",
            str(catalog),
            "--command-id",
            "complete_genomics_mgi_snv_concordance",
            "--analysis-id",
            "cg-run",
            "--executing-entity",
            "johnm",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--reference-s3-uri",
            "s3://reference-bucket",
            "--control-data-s3-uri",
            "s3://control-data-bucket",
            "--stage-s3-uri",
            "s3://stage-bucket",
            "--config-dir",
            str(config_dir),
            "--run-metric-staging",
            "CGT7P:CG:/tmp/cgt7p.fofn",
            "--project",
            "project-alpha",
            "--session-name",
            "cg-session",
            "--max-runtime-minutes",
            "240",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert calls["stage_argv"] == [
        str(manifest.resolve()),
        "--reference-s3-uri",
        "s3://reference-bucket",
        "--control-data-s3-uri",
        "s3://control-data-bucket",
        "--stage-s3-uri",
        "s3://stage-bucket",
        "--stage-target",
        "/fsx/staging/staged_external_sequencing_data",
        "--run-metric-staging",
        "CGT7P:CG:/tmp/cgt7p.fofn",
        "--config-dir",
        str(config_dir),
        "--profile",
        "dev",
        "--region",
        "us-west-2",
        "--cluster",
        "cluster-a",
    ]
    launch_argv = calls["launch_argv"]
    assert "--analysis-id" in launch_argv
    assert "cg-run" in launch_argv
    assert "--executing-entity" in launch_argv
    assert "johnm" in launch_argv
    assert "--git-tag" in launch_argv
    assert DAYOA_BLESSED_TAG in launch_argv
    assert "--project" in launch_argv
    assert "project-alpha" in launch_argv
    assert "--max-runtime-minutes" in launch_argv
    assert launch_argv[launch_argv.index("--max-runtime-minutes") + 1] == "240"
    assert "--dy-command" in launch_argv
    dy_command = launch_argv[launch_argv.index("--dy-command") + 1]
    assert "produce_cgt7p_snv_vcf" in dy_command
    assert "produce_sentcg_align" in dy_command
    assert "produce_dmd_dedup_cram" in dy_command
    assert "produce_smd_dedup_cram" not in dy_command
    assert dy_command.endswith(" -n")
    assert "--stage-dir" in launch_argv
    assert (
        "/fsx/staging/staged_external_sequencing_data/remote_stage_20260425T000000Z" in launch_argv
    )
    receipt = config_dir / "20260425T000000Z_samples_run_receipt.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["detected_data_modes"] == ["complete_genomics_solo"]
    assert payload["compatible_cluster_types"] == ["daywgs"]
    assert payload["max_runtime_minutes"] == 240
    assert payload["workflow_launch"]["session_name"] == "cg-session"


def test_samples_run_requires_analysis_identity(monkeypatch, tmp_path) -> None:
    _activate_dayec_runtime(monkeypatch)
    manifest = tmp_path / "analysis_samples.tsv"
    _write_complete_genomics_manifest(manifest)

    result = runner.invoke(
        app,
        [
            "samples",
            "run",
            str(manifest),
            "--command-id",
            "complete_genomics_mgi_snv_concordance",
            "--profile",
            "dev",
            "--reference-s3-uri",
            "s3://reference-bucket",
            "--control-data-s3-uri",
            "s3://control-data-bucket",
            "--stage-s3-uri",
            "s3://stage-bucket",
        ],
    )

    assert result.exit_code != 0
    assert "analysis-id" in result.output


def test_samples_run_defaults_executing_entity_to_cluster(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    manifest = tmp_path / "analysis_samples.tsv"
    config_dir = tmp_path / "cfg"
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        (
            Path(__file__).resolve().parents[1] / "config" / "daylily_pipeline_command_catalog.yaml"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_complete_genomics_manifest(manifest)

    def fake_stage(argv: list[str]) -> int:
        calls["stage_argv"] = argv
        print("Remote staging completed successfully.")
        print(
            "Remote FSx stage directory: /fsx/staging/staged_external_sequencing_data/remote_stage_20260425T000000Z"
        )
        return 0

    def fake_launch(argv: list[str]) -> int:
        calls["launch_argv"] = argv
        print("__DAYLILY_SESSION__=cg-session")
        return 0

    monkeypatch.setattr(cli_module, "_invoke_stage_samples", fake_stage)
    monkeypatch.setattr(cli_module, "_invoke_workflow_launch", fake_launch)

    result = runner.invoke(
        app,
        [
            "samples",
            "run",
            str(manifest),
            "--catalog-config",
            str(catalog),
            "--command-id",
            "complete_genomics_mgi_snv_concordance",
            "--analysis-id",
            "cg-run",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--reference-s3-uri",
            "s3://reference-bucket",
            "--control-data-s3-uri",
            "s3://control-data-bucket",
            "--stage-s3-uri",
            "s3://stage-bucket",
            "--config-dir",
            str(config_dir),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    launch_argv = calls["launch_argv"]
    assert launch_argv[launch_argv.index("--executing-entity") + 1] == "cluster-a"
    receipt = config_dir / "20260425T000000Z_samples_run_receipt.json"
    assert json.loads(receipt.read_text(encoding="utf-8"))["executing_entity"] == "cluster-a"


def test_samples_run_rejects_export_policy_before_staging(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    manifest = tmp_path / "analysis_samples.tsv"
    _write_complete_genomics_manifest(manifest)

    def fake_stage(argv: list[str]) -> int:
        calls["stage_argv"] = argv
        return 0

    monkeypatch.setattr(cli_module, "_invoke_stage_samples", fake_stage)

    result = runner.invoke(
        app,
        [
            "samples",
            "run",
            str(manifest),
            "--command-id",
            "complete_genomics_mgi_snv_concordance",
            "--analysis-id",
            "cg-run",
            "--executing-entity",
            "johnm",
            "--profile",
            "dev",
            "--reference-s3-uri",
            "s3://reference-bucket",
            "--control-data-s3-uri",
            "s3://control-data-bucket",
            "--stage-s3-uri",
            "s3://stage-bucket",
            "--export-destination-s3-uri",
            "s3://bucket/derived/johnm/cg-run/",
        ],
    )

    assert result.exit_code != 0
    assert "export-trigger" in result.output
    assert "stage_argv" not in calls


def test_samples_run_expands_export_root_to_cluster_analysis(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    manifest = tmp_path / "analysis_samples.tsv"
    config_dir = tmp_path / "cfg"
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        (
            Path(__file__).resolve().parents[1] / "config" / "daylily_pipeline_command_catalog.yaml"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_complete_genomics_manifest(manifest)

    def fake_stage(argv: list[str]) -> int:
        calls["stage_argv"] = argv
        print("Remote staging completed successfully.")
        print(
            "Remote FSx stage directory: /fsx/staging/staged_external_sequencing_data/remote_stage_20260425T000000Z"
        )
        return 0

    def fake_launch(argv: list[str]) -> int:
        calls["launch_argv"] = argv
        print("__DAYLILY_SESSION__=cg-session")
        return 0

    monkeypatch.setattr(cli_module, "_invoke_stage_samples", fake_stage)
    monkeypatch.setattr(cli_module, "_invoke_workflow_launch", fake_launch)

    result = runner.invoke(
        app,
        [
            "samples",
            "run",
            str(manifest),
            "--catalog-config",
            str(catalog),
            "--command-id",
            "complete_genomics_mgi_snv_concordance",
            "--analysis-id",
            "cg-run",
            "--executing-entity",
            "johnm",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--reference-s3-uri",
            "s3://reference-bucket",
            "--control-data-s3-uri",
            "s3://control-data-bucket",
            "--stage-s3-uri",
            "s3://stage-bucket",
            "--config-dir",
            str(config_dir),
            "--export-destination-s3-uri",
            "s3://bucket/derived/",
            "--export-trigger",
            "on-success",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    launch_argv = calls["launch_argv"]
    assert launch_argv[launch_argv.index("--export-destination-s3-uri") + 1] == (
        "s3://bucket/derived/cluster-a/cg-run/"
    )
    receipt = config_dir / "20260425T000000Z_samples_run_receipt.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["export_destination_s3_uri"] == "s3://bucket/derived/cluster-a/cg-run/"


def test_samples_run_rejects_unknown_command(monkeypatch, tmp_path) -> None:
    _activate_dayec_runtime(monkeypatch)
    manifest = tmp_path / "analysis_samples.tsv"
    _write_complete_genomics_manifest(manifest)

    result = runner.invoke(
        app,
        [
            "samples",
            "run",
            str(manifest),
            "--command-id",
            "missing",
            "--analysis-id",
            "cg-run",
            "--executing-entity",
            "johnm",
            "--profile",
            "dev",
            "--reference-s3-uri",
            "s3://reference-bucket",
            "--control-data-s3-uri",
            "s3://control-data-bucket",
            "--stage-s3-uri",
            "s3://stage-bucket",
        ],
    )

    assert result.exit_code != 0
    assert "Unknown analysis command: missing" in result.output


def test_samples_run_rejects_incompatible_catalog_command(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    manifest = tmp_path / "analysis_samples.tsv"
    _write_complete_genomics_manifest(manifest)

    def fake_stage(argv: list[str]) -> int:
        calls["stage_argv"] = argv
        return 0

    monkeypatch.setattr(cli_module, "_invoke_stage_samples", fake_stage)

    result = runner.invoke(
        app,
        [
            "samples",
            "run",
            str(manifest),
            "--command-id",
            "illumina_snv_alignstats",
            "--analysis-id",
            "cg-run",
            "--executing-entity",
            "johnm",
            "--profile",
            "dev",
            "--reference-s3-uri",
            "s3://reference-bucket",
            "--control-data-s3-uri",
            "s3://control-data-bucket",
            "--stage-s3-uri",
            "s3://stage-bucket",
        ],
    )

    assert result.exit_code != 0
    assert "not compatible" in result.output
    assert "stage_argv" not in calls


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
            "--analysis-id",
            "run-1",
            "--executing-entity",
            "johnm",
            "--git-tag",
            "release-1",
            "--project",
            "project-alpha",
            "--session-name",
            "sess-1",
            "--export-destination-s3-uri",
            "s3://bucket/derived/johnm/run-1/",
            "--export-trigger",
            "on-success",
            "--delete-on-export-success",
            "--replace-existing-analysis-dir",
            "--artifact-registration-command-id",
            "illumina_snv_alignstats_relatedness_vep_multiqc",
            "--dewey-url",
            "https://dewey.example",
            "--dewey-token-env",
            "DEWEY_TOKEN",
            "--dewey-analysis-dir-external-object-id",
            "M-RGX-9S3G",
            "--dewey-run-artifact-euid",
            "M-DGX-9SD7",
            "--dewey-ursa-analysis-euid",
            "M-RGX-9S3G",
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
    assert "--analysis-id" in argv
    assert "run-1" in argv
    assert "--executing-entity" in argv
    assert "johnm" in argv
    assert "--git-tag" in argv
    assert "release-1" in argv
    assert "--project" in argv
    assert "project-alpha" in argv
    assert "--session-name" in argv
    assert "sess-1" in argv
    assert "--export-destination-s3-uri" in argv
    assert "s3://bucket/derived/johnm/run-1/" in argv
    assert "--export-trigger" in argv
    assert "on-success" in argv
    assert "--delete-on-export-success" in argv
    assert "--replace-existing-analysis-dir" in argv
    assert "--dewey-analysis-dir-external-object-id" in argv
    assert "M-RGX-9S3G" in argv
    assert "--dewey-run-artifact-euid" in argv
    assert "M-DGX-9SD7" in argv
    assert "--sv-callers" in argv
    assert "tiddit" in argv
    assert "--max-runtime-minutes" in argv
    assert "100" in argv
    assert "--strict-project-check" in argv
    assert "--dry-run" in argv


def test_workflow_launch_expands_export_root_to_cluster_analysis(monkeypatch) -> None:
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
            "--analysis-id",
            "run-1",
            "--executing-entity",
            "johnm",
            "--export-destination-s3-uri",
            "s3://bucket/derived/",
            "--export-trigger",
            "on-success",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    argv = calls["argv"]
    assert argv[argv.index("--export-destination-s3-uri") + 1] == (
        "s3://bucket/derived/cluster-a/run-1/"
    )


def test_workflow_launch_rejects_dewey_options_without_policy(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)

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
            "--analysis-id",
            "run-1",
            "--executing-entity",
            "johnm",
            "--export-destination-s3-uri",
            "s3://bucket/derived/johnm/run-1/",
            "--export-trigger",
            "on-success",
            "--dewey-url",
            "https://dewey.example",
            "--dewey-token-env",
            "DEWEY_TOKEN",
        ],
    )

    assert result.exit_code != 0
    assert "artifact-registration-command-id" in result.output


def test_workflow_launch_defaults_executing_entity_to_cluster(monkeypatch) -> None:
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
            "--analysis-id",
            "run-1",
        ],
    )

    assert result.exit_code == 0
    argv = calls["argv"]
    assert argv[argv.index("--executing-entity") + 1] == "cluster-a"


def test_workflow_launch_forwards_run_context_file(monkeypatch, tmp_path) -> None:
    import daylily_ec.scripts.daylily_run_omics_analysis_headnode as launch_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    run_context = tmp_path / "runs.tsv"
    run_context.write_text("RUNID\tPLATFORM\nRUN-1\tILMN\n", encoding="utf-8")

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
            "--run-context-file",
            str(run_context),
            "--analysis-id",
            "run-1",
            "--executing-entity",
            "johnm",
        ],
    )

    assert result.exit_code == 0
    argv = calls["argv"]
    assert "--run-context-file" in argv
    assert str(run_context) in argv
    assert "--stage-dir" not in argv


def test_workflow_launch_forwards_no_input_utility_flags(monkeypatch) -> None:
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
            "--analysis-id",
            "simple-test",
            "--executing-entity",
            "johnm",
            "--dy-command",
            "source dyoainit; dy-a local hg38; dy-r -p -k -j 1 help",
            "--no-input-staging",
            "--no-default-activation",
            "--bootstrap-test-config",
        ],
    )

    assert result.exit_code == 0
    argv = calls["argv"]
    assert "--no-input-staging" in argv
    assert "--no-default-activation" in argv
    assert "--bootstrap-test-config" in argv
    assert "--stage-dir" not in argv
    assert "--run-context-file" not in argv


def test_workflow_launch_requires_analysis_identity(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)

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
        ],
    )

    assert result.exit_code != 0
    assert "analysis-id" in result.output


def test_workflow_launch_rejects_unsafe_analysis_id_before_entrypoint(monkeypatch) -> None:
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
            "--analysis-id",
            "../bad",
            "--executing-entity",
            "johnm",
        ],
    )

    assert result.exit_code != 0
    assert "analysis_id" in result.output
    assert "argv" not in calls


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


def test_workflow_collect_benchmarks_runs_remote_dayoa_collector(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module

    calls: dict[str, object] = {}
    _activate_dayec_runtime(monkeypatch)
    _patch_headnode_selection(monkeypatch)
    monkeypatch.setenv("USER", "jmajor")
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
        payload = {
            "analysis_root": "/fsx/analysis_results/ubuntu/run-1",
            "dayoa_root": "/fsx/analysis_results/ubuntu/run-1/daylily-omics-analysis",
            "genome_build": "hg38_broad",
            "report_dir": (
                "/fsx/analysis_results/ubuntu/run-1/daylily-omics-analysis/"
                "results/day/hg38_broad/reports"
            ),
            "summary_tsv": (
                "/fsx/analysis_results/ubuntu/run-1/daylily-omics-analysis/"
                "results/day/hg38_broad/reports/benchmarks_summary.tsv"
            ),
            "row_count": 42,
            "bytes": 2048,
        }
        return SsmCommandResult(
            "cmd-1",
            instance_id,
            "Success",
            0,
            "__DAYLILY_BENCHMARK_COLLECTION__=" + json.dumps(payload, sort_keys=True) + "\n",
            "",
        )

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)

    result = runner.invoke(
        app,
        [
            "--json",
            "workflow",
            "collect-benchmarks",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--analysis-root",
            "/fsx/analysis_results/ubuntu/run-1",
            "--genome-build",
            "hg38_broad",
            "--timeout",
            "900",
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary_tsv"].endswith("results/day/hg38_broad/reports/benchmarks_summary.tsv")
    instance_id, region, script, kwargs = calls["run_shell"]
    assert instance_id == "i-abc123"
    assert region == "us-west-2"
    assert "ANALYSIS_ROOT=/fsx/analysis_results/ubuntu/run-1" in script
    assert 'DAYOA_ROOT="${ANALYSIS_ROOT}/daylily-omics-analysis"' in script
    assert "source dyoainit" in script
    assert 'dy-a local "$GENOME_BUILD"' in script
    assert 'bash "$COLLECTOR" "$GENOME_BUILD"' in script
    assert "dyec analysis lock acquire" in script
    assert "dyec analysis lock release" in script
    assert "collect_day_benchmark_data.sh" in script
    assert kwargs["profile"] == "dev"
    assert kwargs["timeout"] == 900
    assert kwargs["comment"] == ("Collect DayOA benchmarks for /fsx/analysis_results/ubuntu/run-1")


def test_workflow_collect_benchmarks_rejects_invalid_genome_build(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module

    _activate_dayec_runtime(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(ssm_module, "run_shell", lambda *args, **kwargs: calls.append("run"))

    result = runner.invoke(
        app,
        [
            "workflow",
            "collect-benchmarks",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--analysis-root",
            "/fsx/analysis_results/ubuntu/run-1",
            "--genome-build",
            "GRCh38",
        ],
    )

    assert result.exit_code != 0
    assert "--genome-build must be one of" in (result.stdout + result.stderr)
    assert calls == []


def test_workflow_collect_benchmarks_rejects_dayoa_root_as_analysis_root(monkeypatch) -> None:
    import daylily_ec.aws.ssm as ssm_module

    _activate_dayec_runtime(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(ssm_module, "run_shell", lambda *args, **kwargs: calls.append("run"))

    result = runner.invoke(
        app,
        [
            "workflow",
            "collect-benchmarks",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--analysis-root",
            "/fsx/analysis_results/ubuntu/run-1/daylily-omics-analysis",
            "--genome-build",
            "hg38",
        ],
    )

    assert result.exit_code != 0
    assert "parent analysis directory" in (result.stdout + result.stderr)
    assert calls == []


def test_workflow_collect_benchmarks_surfaces_remote_failures(monkeypatch) -> None:
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
    failed_result = SsmCommandResult(
        "cmd-1",
        "i-abc123",
        "Failed",
        66,
        "",
        "DayOA benchmark collector missing",
    )

    def fake_run_shell(*args, **kwargs):
        raise SsmCommandFailedError("SSM command 'cmd-1' failed", failed_result)

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)

    result = runner.invoke(
        app,
        [
            "workflow",
            "collect-benchmarks",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--analysis-root",
            "/fsx/analysis_results/ubuntu/run-1",
            "--genome-build",
            "hg38",
        ],
    )

    assert result.exit_code == 1
    assert "DayOA benchmark collector missing" in result.stderr
    assert "SSM command 'cmd-1' failed" in result.stderr


def test_workflow_stop_kills_controller_via_ssm(monkeypatch) -> None:
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
        payload = {
            "session_name": "sess-1",
            "run_dir": "/home/ubuntu/daylily-runs/sess-1",
            "tmux_session_name": "sess-1",
            "tmux_session_before": True,
            "tmux_session_after": False,
            "killed_tmux_session": True,
            "cancel_slurm_jobs": False,
            "job_name_pattern": "",
            "slurm_jobs_before": [],
            "scancelled_job_ids": [],
            "slurm_jobs_after": [],
            "status_path": "/home/ubuntu/daylily-runs/sess-1/status.json",
            "status_updated": True,
        }
        return SsmCommandResult(
            "cmd-1",
            instance_id,
            "Success",
            0,
            "DAY-EC activated.\n__DAYLILY_WORKFLOW_STOP__="
            + json.dumps(payload, sort_keys=True)
            + "\n",
            "",
        )

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)

    result = runner.invoke(
        app,
        [
            "--json",
            "workflow",
            "stop",
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
    payload = json.loads(result.stdout)
    assert payload["killed_tmux_session"] is True
    assert payload["cancel_slurm_jobs"] is False
    _instance_id, _region, script, kwargs = calls["run_shell"]
    assert "DAYLILY_WORKFLOW_SESSION=sess-1" in script
    assert "DAYLILY_CANCEL_SLURM_JOBS=false" in script
    assert 'run(["tmux", "kill-session"' in script
    assert 'status["exit_code"] = 130' in script
    assert "scancel" in script
    assert kwargs["profile"] == "dev"


def test_workflow_stop_can_cancel_slurm_jobs_with_explicit_pattern(monkeypatch) -> None:
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
        payload = {
            "session_name": "sess-1",
            "run_dir": "/home/ubuntu/daylily-runs/sess-1",
            "tmux_session_name": "sess-1",
            "tmux_session_before": True,
            "tmux_session_after": False,
            "killed_tmux_session": True,
            "cancel_slurm_jobs": True,
            "job_name_pattern": "ONT-4Coriells|sentmm2ont",
            "slurm_jobs_before": [{"job_id": "101", "name": "sentmm2ont-ONT-4Coriells"}],
            "scancelled_job_ids": ["101"],
            "slurm_jobs_after": [],
            "status_path": "/home/ubuntu/daylily-runs/sess-1/status.json",
            "status_updated": True,
        }
        return SsmCommandResult(
            "cmd-1",
            instance_id,
            "Success",
            0,
            "__DAYLILY_WORKFLOW_STOP__=" + json.dumps(payload, sort_keys=True) + "\n",
            "",
        )

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)

    result = runner.invoke(
        app,
        [
            "--json",
            "workflow",
            "stop",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--session",
            "sess-1",
            "--cancel-slurm-jobs",
            "--job-name-pattern",
            "ONT-4Coriells|sentmm2ont",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["scancelled_job_ids"] == ["101"]
    assert "DAYLILY_CANCEL_SLURM_JOBS=true" in calls["script"]
    assert "DAYLILY_JOB_NAME_PATTERN='ONT-4Coriells|sentmm2ont'" in calls["script"]


def test_workflow_stop_requires_job_pattern_for_slurm_cancellation(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)
    result = runner.invoke(
        app,
        [
            "workflow",
            "stop",
            "--profile",
            "dev",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--session",
            "sess-1",
            "--cancel-slurm-jobs",
        ],
    )

    assert result.exit_code != 0
    assert "--job-name-pattern is required with --cancel-slurm-jobs" in (
        result.stdout + result.stderr
    )


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
