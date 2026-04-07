from __future__ import annotations

from importlib.metadata import version as dist_version
import json

from typer.testing import CliRunner

from daylily_ec.cli import app, spec

runner = CliRunner()


def test_cli_spec_uses_platform_v2_runtime() -> None:
    assert spec.policy.profile == "platform-v2"
    assert spec.runtime is not None
    assert spec.runtime.guard_mode == "enforced"
    assert spec.runtime.allow_skip_check is False
    assert spec.runtime.supported_backends
    assert spec.runtime.prereqs


def test_cli_registry_exposes_v2_command_tree_and_policies() -> None:
    registry = app._cli_core_yo_registry

    for argv in (
        ["version"],
        ["info"],
        ["create"],
        ["preflight"],
        ["drift"],
        ["delete"],
        ["export"],
        ["resources-dir"],
        ["cluster-info"],
        ["headnode", "init"],
        ["pricing", "snapshot"],
    ):
        assert registry.resolve_command_args(argv) is not None

    version_cmd = registry.get_command(("version",))
    info_cmd = registry.get_command(("info",))
    create_cmd = registry.get_command(("create",))
    delete_cmd = registry.get_command(("delete",))
    export_cmd = registry.get_command(("export",))
    cluster_info_cmd = registry.get_command(("cluster-info",))
    headnode_init_cmd = registry.get_command(("headnode", "init"))
    pricing_snapshot_cmd = registry.get_command(("pricing", "snapshot"))

    assert version_cmd is not None
    assert version_cmd.policy.runtime_guard == "exempt"

    assert info_cmd is not None
    assert info_cmd.policy.runtime_guard == "exempt"
    assert info_cmd.policy.supports_json is True

    assert create_cmd is not None
    assert create_cmd.policy.mutates_state is True

    assert delete_cmd is not None
    assert delete_cmd.policy.mutates_state is True

    assert export_cmd is not None
    assert export_cmd.policy.mutates_state is True

    assert cluster_info_cmd is not None
    assert cluster_info_cmd.policy.supports_json is True

    assert headnode_init_cmd is not None
    assert headnode_init_cmd.policy.mutates_state is True
    assert headnode_init_cmd.policy.interactive is True

    assert pricing_snapshot_cmd is not None
    assert pricing_snapshot_cmd.policy.supports_json is True


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


def test_runtime_exempt_command_bypasses_runtime_guard(monkeypatch) -> None:
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)

    result = runner.invoke(app, ["--json", "version"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["app"] == "Daylily Ephemeral Cluster"


def test_runtime_required_command_fails_without_active_env(monkeypatch) -> None:
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)

    result = runner.invoke(app, ["--json", "cluster-info", "--region", "us-west-2"])

    assert result.exit_code == 3
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "runtime_validation_failed"
    assert payload["error"]["details"]["summary"]["blocking_failures"] >= 1
