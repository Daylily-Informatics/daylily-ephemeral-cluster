"""Contract tests for DRA-only runtime-cache preservation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from typer.testing import CliRunner

from daylily_ec.runtime_cache_export import (
    RUNTIME_CACHE_STAGE_MARKER,
    RuntimeCacheExportError,
    RuntimeCacheExportOptions,
    build_runtime_cache_stage_script,
    parse_runtime_cache_stage_result,
    run_runtime_cache_export,
)

runner = CliRunner()


def _options(tmp_path: Path, *, dry_run: bool = False) -> RuntimeCacheExportOptions:
    return RuntimeCacheExportOptions(
        cluster_name="cluster-a",
        executing_entity="cluster-a",
        cache_export_id="cache-20260813",
        destination_s3_uri=("s3://cache-bucket/runtime-cache/cluster-a/cache-20260813/"),
        region="us-west-2",
        profile="lsmc",
        output_dir=tmp_path / "receipt",
        human_requestor="jmajor",
        dry_run=dry_run,
    )


def test_stage_script_uses_cp_archive_and_never_an_s3_object_copy(tmp_path: Path) -> None:
    script = build_runtime_cache_stage_script(_options(tmp_path))

    subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    assert "cp -a --" in script
    assert "dyec analysis lock acquire" in script
    assert "dyec analysis lock release" in script
    assert "dyec analysis visit" in script
    assert "--mode export" in script
    assert "conda-meta/history" in script
    assert "symlink manifest differs" in script
    assert "source inventory changed during staging" in script
    assert "snakemake|nextflow" in script
    assert "EXPORT_TO_REPOSITORY" not in script
    lowered = script.lower()
    for forbidden in ("aws s3 cp", "aws s3 sync", "aws s3 mv", "copy_object"):
        assert forbidden not in lowered


def test_parse_stage_result_requires_one_nonempty_terminal_marker() -> None:
    marker = (
        f"{RUNTIME_CACHE_STAGE_MARKER}\tnamespace-a\t27\t1\t450\t3\t"
        "/fsx/analysis_results/cluster-a/cache-20260813/runtime_cache_manifest.tsv"
    )
    payload = parse_runtime_cache_stage_result(f"setup\n{marker}\n")

    assert payload == {
        "cluster_cache_namespace": "namespace-a",
        "conda_environment_count": 27,
        "container_image_count": 1,
        "preserved_conda_symlink_count": 450,
        "skipped_seeded_container_link_count": 3,
        "manifest_path": (
            "/fsx/analysis_results/cluster-a/cache-20260813/runtime_cache_manifest.tsv"
        ),
    }

    with pytest.raises(RuntimeCacheExportError, match="exactly one"):
        parse_runtime_cache_stage_result("no terminal marker")
    with pytest.raises(RuntimeCacheExportError, match="no copied entries"):
        parse_runtime_cache_stage_result(
            f"{RUNTIME_CACHE_STAGE_MARKER}\tnamespace-a\t0\t0\t0\t0\t/path"
        )


def test_runtime_cache_export_dry_run_is_local_and_immutable(tmp_path: Path) -> None:
    options = _options(tmp_path, dry_run=True)
    payload = run_runtime_cache_export(options)

    assert payload["status"] == "planned"
    assert payload["transport"] == "fsx_dra"
    assert payload["s3_object_copy_transport"] == "forbidden"
    assert payload["staging_copy_command"] == "cp -a"
    assert payload["stage_root"] == ("/fsx/analysis_results/cluster-a/cache-20260813")
    assert not options.output_dir.exists()


def test_runtime_cache_cli_exposes_json_dry_run_without_aws(tmp_path: Path) -> None:
    from daylily_ec.cli import app

    result = runner.invoke(
        app,
        [
            "--json",
            "runtime-cache",
            "export",
            "--cluster",
            "cluster-a",
            "--executing-entity",
            "cluster-a",
            "--cache-export-id",
            "cache-20260813",
            "--destination-s3-uri",
            "s3://cache-bucket/runtime-cache/cluster-a/cache-20260813/",
            "--region",
            "us-west-2",
            "--output-dir",
            str(tmp_path / "receipt"),
            "--human-requestor",
            "jmajor",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "planned"
    assert payload["transport"] == "fsx_dra"
    assert payload["destination_s3_uri"].endswith("cluster-a/cache-20260813/")


def test_runtime_cache_export_rejects_wrong_destination_suffix(tmp_path: Path) -> None:
    options = _options(tmp_path, dry_run=True)
    options = RuntimeCacheExportOptions(
        **{
            **options.__dict__,
            "destination_s3_uri": "s3://cache-bucket/wrong/",
        }
    )
    with pytest.raises(RuntimeCacheExportError, match="must end"):
        run_runtime_cache_export(options)


def test_runtime_cache_export_stages_then_calls_dra_workflow_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import daylily_ec.runtime_cache_export as cache_export
    from daylily_ec.aws import ssm
    from daylily_ec.workflow import export_data

    options = _options(tmp_path)
    preflight_calls: list[str] = []
    stage_calls: list[tuple[object, ...]] = []

    def fake_preflight(received: RuntimeCacheExportOptions) -> str:
        assert received is options
        preflight_calls.append(received.destination_s3_uri)
        return "fs-123"

    monkeypatch.setattr(cache_export, "_preflight_dra_export", fake_preflight)
    monkeypatch.setattr(
        ssm,
        "resolve_headnode_instance_id",
        lambda *_args, **_kwargs: SimpleNamespace(instance_id="i-headnode"),
    )
    monkeypatch.setattr(ssm, "wait_for_ssm_online", lambda *_args, **_kwargs: None)

    marker = (
        f"{RUNTIME_CACHE_STAGE_MARKER}\tnamespace-a\t27\t1\t450\t3\t"
        f"{options.stage_root}/runtime_cache_manifest.tsv\n"
    )

    def fake_run_shell(*args, **kwargs):
        stage_calls.append((*args, kwargs))
        return SimpleNamespace(command_id="ssm-stage", stdout=marker, stderr="")

    monkeypatch.setattr(ssm, "run_shell", fake_run_shell)

    def fake_export_workflow(export_options) -> int:
        assert export_options.source_path == options.stage_root
        assert export_options.destination_s3_uri == options.destination_s3_uri
        assert export_options.fsx_file_system_id == "fs-123"
        assert export_options.delete_data_in_file_system is False
        export_options.output_dir.mkdir(parents=True)
        (export_options.output_dir / export_data.STATUS_FILENAME).write_text(
            yaml.safe_dump(
                {
                    "fsx_export": {
                        "status": "success",
                        "task_id": "task-1",
                        "task_lifecycle": "SUCCEEDED",
                        "detached": True,
                        "delete_data_in_file_system": False,
                    }
                }
            ),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(export_data, "run_export_workflow", fake_export_workflow)

    payload = run_runtime_cache_export(options)

    assert payload["status"] == "success"
    assert payload["fsx_export"]["task_lifecycle"] == "SUCCEEDED"
    assert payload["staged_fsx_data_deleted"] is False
    assert len(preflight_calls) == 2
    assert len(stage_calls) == 1
    _instance_id, _region, script, kwargs = stage_calls[0]
    assert kwargs["as_user"] == "ubuntu"
    assert kwargs["timeout"] == 7200
    assert "cp -a --" in script
    for forbidden in ("aws s3 cp", "aws s3 sync", "aws s3 mv"):
        assert forbidden not in script.lower()
    receipt = yaml.safe_load(
        (options.output_dir / "runtime_cache_export.yaml").read_text(encoding="utf-8")
    )["runtime_cache_export"]
    assert receipt["status"] == "success"
    assert receipt["transport"] == "fsx_dra"
