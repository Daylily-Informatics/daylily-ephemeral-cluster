from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import daylily_ec.cli as cli_module
from daylily_ec.aws.ssm import HeadNodeTarget
from daylily_ec.cli import app
from daylily_ec.repositories import AnalysisCommand, load_repository_catalog
from daylily_ec.scripts import daylily_run_omics_analysis_headnode as launch_module
from daylily_ec.scripts.common import CommandError

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = ROOT / "config" / "daylily_pipeline_command_catalog.yaml"
COMMAND_ID = "inflection-bjuice-product-v0.9"
SIX_MANIFEST_NAMES = (
    "specimens.tsv",
    "samples.tsv",
    "libraries.tsv",
    "sequencing_inputs.tsv",
    "analysis_units.tsv",
    "analysis_unit_inputs.tsv",
)
runner = CliRunner()


def _declared_command() -> AnalysisCommand:
    """Return a validated declaration for the new unreleased catalog capability."""

    base = load_repository_catalog(SOURCE_CATALOG).get_command_for_dyec_build(COMMAND_ID, "19.0.54")
    payload = base.model_dump()
    payload.update(
        {
            "runtime_config_target": "config/dyec_runtime_config.yaml",
            "contributing_data_receipt_required": True,
            "dy_command": base.dy_command.replace(
                "config/hg002_bjuice_5x5x_hiomr2.yaml",
                "config/dyec_runtime_config.yaml",
            ),
            "dryrun_dy_command": base.dryrun_dy_command.replace(
                "config/hg002_bjuice_5x5x_hiomr2.yaml",
                "config/dyec_runtime_config.yaml",
            ),
        }
    )
    return AnalysisCommand.model_validate(payload)


def _write_receipt(path: Path, *, schema: str = "dayoa.contributing_data.v1") -> Path:
    path.write_text(json.dumps({"schema_version": schema}) + "\n", encoding="utf-8")
    return path


def _controller_marker(session_name: str, repo_path: str) -> str:
    payload = {
        "schema_version": "dyec.controller_target.v2",
        "controller_id": session_name,
        "pid": 4242,
        "cwd": repo_path,
        "log_path": f"{repo_path}/.dyec/controller.log",
        "dag_path": f"{repo_path}/.dyec/controller-dag.png",
        "analysis_root": str(Path(repo_path).parent),
        "status_attempt_id": "00000000-0000-4000-8000-000000000001",
    }
    return "\n".join(
        (
            f"__DAYLILY_TMUX_SESSION__={session_name}",
            "__DYEC_CONTROLLER_TARGET__=" + json.dumps(payload, separators=(",", ":")),
        )
    )


def test_analysis_command_requires_and_forwards_only_declared_contributing_receipt() -> None:
    command = _declared_command()
    common = {
        "analysis_id": "receipt-contract",
        "executing_entity": "bjuiceval-19024",
        "manifest_dir": "/tmp/manifests",
        "runtime_config_file": "/tmp/runtime.yaml",
        "cost_center": "bjuiceval-19024-ccenter",
    }

    with pytest.raises(ValueError, match="requires contributing_data_receipt_file"):
        command.launch_argv(**common)

    argv = command.launch_argv(
        **common,
        contributing_data_receipt_file="/tmp/contributing.json",
        dry_run=True,
    )
    assert argv[argv.index("--contributing-data-receipt-file") + 1] == "/tmp/contributing.json"

    undeclared = command.model_copy(update={"contributing_data_receipt_required": False})
    with pytest.raises(ValueError, match="does not declare a contributing-data receipt"):
        undeclared.launch_argv(**common, contributing_data_receipt_file="/tmp/contributing.json")


def test_analysis_command_rejects_an_unstaged_receipt_declaration() -> None:
    command = _declared_command()
    invalid = command.model_dump()
    invalid["runtime_config_target"] = ""
    with pytest.raises(ValidationError, match="requires an explicit in-clone runtime config"):
        AnalysisCommand.model_validate(invalid)


class _CatalogStub:
    command_catalog_version = 6
    result_export = None

    @staticmethod
    def resolve_dyec_build_key(dyec_version: str | None = None) -> str:
        return dyec_version or "19.0.55"


def test_catalog_render_requires_and_forwards_only_declared_contributing_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = _declared_command()
    receipt = _write_receipt(tmp_path / "contributing.json")
    runtime = tmp_path / "runtime.yaml"
    runtime.write_text("multiqc_qc: {}\n", encoding="utf-8")
    monkeypatch.setattr(
        cli_module,
        "_catalog_load_command",
        lambda *_args, **_kwargs: (_CatalogStub(), command),
    )
    common = {
        "command_id": COMMAND_ID,
        "dyec_version": "19.0.55",
        "analysis_id": "render-contract",
        "executing_entity": "bjuiceval-19024",
        "profile": "lsmc",
        "region": "us-west-2",
        "cluster": "bjuiceval-19024",
        "git_tag": None,
        "stage_dir": None,
        "manifest_dir": tmp_path / "manifests",
        "runtime_config_file": runtime,
        "artifact_recovery_manifest": None,
        "payload_staging_s3_uri": None,
        "remote_user": "ubuntu",
        "run_context_file": None,
        "specimens_file": None,
        "samples_file": None,
        "libraries_file": None,
        "units_file": None,
        "session_name": None,
        "project": None,
        "cost_center": "bjuiceval-19024-ccenter",
        "dry_run": True,
        "skip_project_check": True,
        "allow_stage_discovery": False,
        "max_runtime_minutes": 100,
        "export_destination_s3_uri": None,
        "export_trigger": "none",
        "delete_on_export_success": False,
        "replace_existing_analysis_dir": False,
    }

    with pytest.raises(ValueError, match="requires --contributing-data-receipt-file"):
        cli_module._catalog_render_payload(
            **common,
            contributing_data_receipt_file=None,
        )

    rendered = cli_module._catalog_render_payload(
        **common,
        contributing_data_receipt_file=receipt,
    )
    argv = rendered["workflow_argv"]
    assert argv[argv.index("--contributing-data-receipt-file") + 1] == str(receipt)

    undeclared = command.model_copy(update={"contributing_data_receipt_required": False})
    monkeypatch.setattr(
        cli_module,
        "_catalog_load_command",
        lambda *_args, **_kwargs: (_CatalogStub(), undeclared),
    )
    with pytest.raises(ValueError, match="does not declare a contributing-data receipt"):
        cli_module._catalog_render_payload(
            **common,
            contributing_data_receipt_file=receipt,
        )


def test_public_workflow_launch_forwards_only_a_valid_explicit_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import daylily_ec.manifest_set as manifest_set_module

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    runtime = tmp_path / "runtime.yaml"
    runtime.write_text("multiqc_qc: {}\n", encoding="utf-8")
    receipt = _write_receipt(tmp_path / "contributing.json")
    calls: dict[str, list[str]] = {}

    monkeypatch.setattr(manifest_set_module, "load_manifest_set", lambda _path: object())
    monkeypatch.setattr(cli_module, "_warn_if_dayec_env_inactive", lambda: None)
    monkeypatch.setattr(
        launch_module,
        "main",
        lambda argv: calls.setdefault("argv", list(argv)) and 0,
    )

    result = runner.invoke(
        app,
        [
            "workflow",
            "launch",
            "--profile",
            "lsmc",
            "--region",
            "us-west-2",
            "--cluster",
            "bjuiceval-19024",
            "--analysis-id",
            "receipt-contract",
            "--executing-entity",
            "bjuiceval-19024",
            "--git-tag",
            "16.0.37",
            "--manifest-dir",
            str(manifest_dir),
            "--runtime-config-file",
            str(runtime),
            "--contributing-data-receipt-file",
            str(receipt),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    argv = calls["argv"]
    assert argv[argv.index("--contributing-data-receipt-file") + 1] == str(receipt)

    result = runner.invoke(
        app,
        [
            "workflow",
            "launch",
            "--profile",
            "lsmc",
            "--region",
            "us-west-2",
            "--cluster",
            "bjuiceval-19024",
            "--analysis-id",
            "receipt-contract",
            "--git-tag",
            "16.0.37",
            "--manifest-dir",
            str(manifest_dir),
            "--contributing-data-receipt-file",
            str(receipt),
        ],
    )
    assert result.exit_code != 0
    assert "--contributing-data-receipt-file requires staged" in result.output
    assert "--runtime-config-file" in result.output


def test_low_level_launch_rejects_missing_or_wrong_receipt_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime.yaml"
    runtime.write_text("multiqc_qc: {}\n", encoding="utf-8")
    bad_receipt = _write_receipt(tmp_path / "bad.json", schema="wrong.schema")
    _mock_low_level_prerequisites(monkeypatch)

    with pytest.raises(CommandError, match="must use schema_version dayoa.contributing_data.v1"):
        launch_module.main(
            [
                "--profile",
                "lsmc",
                "--cluster",
                "bjuiceval-19024",
                "--analysis-id",
                "low-level-contract",
                "--git-tag",
                "16.0.37",
                "--manifest-dir",
                str(tmp_path / "manifests"),
                "--runtime-config-file",
                str(runtime),
                "--contributing-data-receipt-file",
                str(bad_receipt),
            ]
        )


def _mock_low_level_prerequisites(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    captured: dict[str, str] = {}

    monkeypatch.setattr(launch_module, "need_cmd", lambda _name: None)
    monkeypatch.setattr(launch_module, "resolve_region", lambda *_args: "us-west-2")
    monkeypatch.setattr(launch_module, "resolve_cluster", lambda *_args: "bjuiceval-19024")
    monkeypatch.setattr(
        launch_module,
        "resolve_headnode_instance_id",
        lambda *_args, **_kwargs: HeadNodeTarget("bjuiceval-19024", "us-west-2", "i-test"),
    )
    monkeypatch.setattr(launch_module, "wait_for_ssm_online", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(launch_module, "resolve_remote_user", lambda *_args, **_kwargs: "ubuntu")
    monkeypatch.setattr(
        launch_module, "validate_headnode_readiness", lambda *_args, **_kwargs: None
    )

    def fake_run_shell(*args, **_kwargs):
        captured["script"] = args[2]
        repo_path = (
            "/fsx/analysis_results/bjuiceval-19024/low-level-contract/daylily-omics-analysis"
        )
        return SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=low-level-contract\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/low-level-contract\n"
                f"__DAYLILY_REPO_PATH__={repo_path}\n"
                "__DAYLILY_DY_COMMAND__=dy-r help -n\n"
                + _controller_marker("low-level-contract", repo_path)
                + "\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(launch_module, "run_shell", fake_run_shell)
    return captured


def test_low_level_launch_stages_receipt_at_fixed_target_with_sha256_verification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import daylily_ec.manifest_set as manifest_set_module

    runtime = tmp_path / "runtime.yaml"
    runtime.write_text("multiqc_qc: {}\n", encoding="utf-8")
    receipt = _write_receipt(tmp_path / "contributing.json")
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    paths: dict[str, Path] = {}
    for name in SIX_MANIFEST_NAMES:
        path = manifest_dir / name
        path.write_text(f"{name}\n", encoding="utf-8")
        paths[name] = path
    monkeypatch.setattr(
        manifest_set_module,
        "load_manifest_set",
        lambda _path: SimpleNamespace(paths=paths),
    )
    monkeypatch.setattr(manifest_set_module, "validation_receipt", lambda _value: {})
    captured = _mock_low_level_prerequisites(monkeypatch)

    assert (
        launch_module.main(
            [
                "--profile",
                "lsmc",
                "--cluster",
                "bjuiceval-19024",
                "--analysis-id",
                "low-level-contract",
                "--git-tag",
                "16.0.37",
                "--manifest-dir",
                str(manifest_dir),
                "--runtime-config-file",
                str(runtime),
                "--contributing-data-receipt-file",
                str(receipt),
                "--dry-run",
            ]
        )
        == 0
    )
    script = captured["script"]
    expected_sha256 = hashlib.sha256(receipt.read_bytes()).hexdigest()
    assert "config/contributing_data_receipt.v1.json" in script
    assert "staged contributing-data receipt SHA-256 mismatch" in script
    assert expected_sha256 in script
    assert "printf '%s' \"$CONTRIBUTING_DATA_RECEIPT_PAYLOAD\"" in script


def test_payload_staging_binds_receipt_content_and_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(argv, **_kwargs):
        tar_path = Path(argv[3])
        with tarfile.open(tar_path, "r:gz") as archive:
            manifest_member = archive.extractfile("./payload_manifest.json")
            receipt_member = archive.extractfile("./inputs/contributing_data_receipt.v1.json")
            assert manifest_member is not None and receipt_member is not None
            captured["manifest"] = json.loads(manifest_member.read().decode("utf-8"))
            captured["receipt"] = receipt_member.read().decode("utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(launch_module, "run_command", fake_run_command)
    content = json.dumps({"schema_version": "dayoa.contributing_data.v1"}) + "\n"
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    args = SimpleNamespace(
        payload_staging_s3_uri="s3://bucket/prefix",
        repository="daylily-omics-analysis",
        git_tag="16.0.37",
        input_contract="six_manifest",
        dy_command="dy-r help -n",
        profile="lsmc",
        region="us-west-2",
    )

    uri = launch_module.stage_workflow_launch_payload(
        pipeline_script="#!/usr/bin/env bash\n",
        args=args,
        cluster_name="bjuiceval-19024",
        analysis_id="payload-contract",
        run_context_content=None,
        specimens_content=None,
        samples_content=None,
        libraries_content=None,
        units_content=None,
        six_manifest_contents={},
        six_manifest_receipt=None,
        runtime_config_content="multiqc_qc: {}\n",
        runtime_config_sha256=hashlib.sha256(b"multiqc_qc: {}\n").hexdigest(),
        contributing_data_receipt_content=content,
        contributing_data_receipt_sha256=sha256,
        artifact_recovery_content=None,
        artifact_recovery_sha256=None,
    )

    assert uri.startswith("s3://bucket/prefix/dyec-workflow-launch-payload/")
    assert captured["receipt"] == content
    manifest = captured["manifest"]
    assert manifest["contributing_data_receipt"] == {
        "target": "config/contributing_data_receipt.v1.json",
        "sha256": sha256,
    }
    assert "inputs/contributing_data_receipt.v1.json" in manifest["files"]
