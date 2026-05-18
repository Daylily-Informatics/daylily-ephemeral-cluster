"""Tests for explicit FSx DRA export workflow and CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from daylily_ec.workflow.export_data import (
    ExportOptions,
    attach_export_dra,
    normalize_export_source_path,
    run_export_workflow,
    run_export_task,
)

runner = CliRunner()


def _activate_dayec_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")


def _filesystem() -> dict[str, object]:
    return {
        "FileSystemId": "fs-123",
        "FileSystemType": "LUSTRE",
        "Lifecycle": "AVAILABLE",
        "LustreConfiguration": {"DeploymentType": "SCRATCH_2"},
    }


class FakeFsxClient:
    def __init__(self, *, task_lifecycle: str = "SUCCEEDED", detach_fails: bool = False) -> None:
        self.task_lifecycle = task_lifecycle
        self.detach_fails = detach_fails
        self.created_association: dict[str, Any] | None = None
        self.created_task: dict[str, Any] | None = None
        self.deleted_association_id: str | None = None

    def describe_file_systems(self, **params: Any) -> dict[str, Any]:
        wanted = set(params.get("FileSystemIds") or [])
        if wanted and "fs-123" not in wanted:
            return {"FileSystems": []}
        return {"FileSystems": [_filesystem()]}

    def create_data_repository_association(self, **params: Any) -> dict[str, Any]:
        self.created_association = params
        return {
            "Association": {
                "AssociationId": "dra-export",
                "FileSystemId": params["FileSystemId"],
                "FileSystemPath": params["FileSystemPath"],
                "DataRepositoryPath": params["DataRepositoryPath"],
                "Lifecycle": "AVAILABLE",
            }
        }

    def describe_data_repository_associations(self, **params: Any) -> dict[str, Any]:
        lifecycle = "DELETED" if self.deleted_association_id == "dra-export" else "AVAILABLE"
        return {
            "Associations": [
                {
                    "AssociationId": "dra-export",
                    "FileSystemId": "fs-123",
                    "FileSystemPath": "/exports/export-1/",
                    "DataRepositoryPath": "s3://bucket/exports/export-1/",
                    "Lifecycle": lifecycle,
                }
            ]
        }

    def create_data_repository_task(self, **params: Any) -> dict[str, Any]:
        self.created_task = params
        return {
            "DataRepositoryTask": {
                "TaskId": "task-123",
                "Lifecycle": self.task_lifecycle,
            }
        }

    def describe_data_repository_tasks(self, **params: Any) -> dict[str, Any]:
        return {
            "DataRepositoryTasks": [
                {
                    "TaskId": "task-123",
                    "Lifecycle": self.task_lifecycle,
                    "FailureDetails": {"Message": "boom"} if self.task_lifecycle == "FAILED" else {},
                }
            ]
        }

    def delete_data_repository_association(self, **params: Any) -> dict[str, Any]:
        if self.detach_fails:
            raise RuntimeError("detach failed")
        self.deleted_association_id = params["AssociationId"]
        assert params["DeleteDataInFileSystem"] is False
        return {"Association": {"AssociationId": params["AssociationId"], "Lifecycle": "DELETED"}}


class FakeSession:
    def __init__(self, client: FakeFsxClient) -> None:
        self._client = client

    def client(self, service: str) -> FakeFsxClient:
        assert service == "fsx"
        return self._client


def test_normalize_export_source_rejects_run_mounts() -> None:
    with pytest.raises(RuntimeError, match="Run-directory mounts"):
        normalize_export_source_path(
            "/fsx/run_dir_mounts/RUN123/fastqs/",
            export_id="export-1",
        )


def test_attach_export_dra_uses_no_auto_export_policy() -> None:
    fake = FakeFsxClient()

    record = attach_export_dra(
        cluster_name="alpha",
        fsx_file_system_id="fs-123",
        export_id="export-1",
        destination_s3_uri="s3://bucket/exports/export-1",
        region="us-west-2",
        profile="prof",
        wait=True,
        timeout_seconds=1,
        fsx_client=fake,
    )

    assert record.association_id == "dra-export"
    assert fake.created_association is not None
    assert fake.created_association["FileSystemPath"] == "/exports/export-1/"
    assert fake.created_association["DataRepositoryPath"] == "s3://bucket/exports/export-1/"
    assert fake.created_association["BatchImportMetaDataOnCreate"] is False
    assert "S3" not in fake.created_association


def test_run_export_task_starts_explicit_path_and_report() -> None:
    fake = FakeFsxClient()

    payload = run_export_task(
        fsx_file_system_id="fs-123",
        export_id="export-1",
        source_path="/exports/export-1/analysis_results/",
        destination_s3_uri="s3://bucket/exports/export-1/",
        wait=True,
        timeout_seconds=1,
        fsx_client=fake,
    )

    assert payload["task_id"] == "task-123"
    assert payload["task_lifecycle"] == "SUCCEEDED"
    assert fake.created_task is not None
    assert fake.created_task["Type"] == "EXPORT_TO_REPOSITORY"
    assert fake.created_task["Paths"] == ["/exports/export-1/analysis_results/"]
    assert fake.created_task["Report"]["Path"].startswith("s3://bucket/exports/export-1/")


def test_run_export_workflow_success_writes_full_receipt(tmp_path, monkeypatch) -> None:
    fake = FakeFsxClient()
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            export_id="export-1",
            source_path="/exports/export-1/analysis_results/",
            destination_s3_uri="s3://bucket/exports/export-1/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
        )
    )

    assert rc == 0
    payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
    receipt = payload["fsx_export"]
    assert receipt["schema_version"] == 2
    assert receipt["status"] == "success"
    assert receipt["fsx_file_system_id"] == "fs-123"
    assert receipt["association_id"] == "dra-export"
    assert receipt["task_id"] == "task-123"
    assert receipt["task_lifecycle"] == "SUCCEEDED"
    assert receipt["detached"] is True
    assert fake.deleted_association_id == "dra-export"


def test_run_export_workflow_task_failure_still_detaches(tmp_path, monkeypatch) -> None:
    fake = FakeFsxClient(task_lifecycle="FAILED")
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            export_id="export-1",
            source_path="/exports/export-1/analysis_results/",
            destination_s3_uri="s3://bucket/exports/export-1/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
        )
    )

    assert rc == 1
    payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
    assert payload["fsx_export"]["status"] == "error"
    assert payload["fsx_export"]["detached"] is True
    assert fake.deleted_association_id == "dra-export"


def test_cli_export_passes_explicit_dra_options(tmp_path, monkeypatch):
    from daylily_ec.cli import app

    _activate_dayec_runtime(monkeypatch)
    with (
        patch("daylily_ec.workflow.export_data.configure_logging") as mock_logging,
        patch("daylily_ec.workflow.export_data.run_export_workflow", return_value=0) as mock_run,
    ):
        result = runner.invoke(
            app,
            [
                "export",
                "--cluster-name",
                "alpha",
                "--export-id",
                "export-1",
                "--source-path",
                "/exports/export-1/analysis_results/",
                "--destination-s3-uri",
                "s3://bucket/exports/export-1/",
                "--region",
                "us-west-2",
                "--output-dir",
                str(tmp_path),
                "--profile",
                "prof",
                "--verbose",
            ],
        )

    assert result.exit_code == 0
    mock_logging.assert_called_once_with(True)
    options = mock_run.call_args.args[0]
    assert options.cluster_name == "alpha"
    assert options.export_id == "export-1"
    assert options.source_path == "/exports/export-1/analysis_results/"
    assert options.destination_s3_uri == "s3://bucket/exports/export-1/"
    assert options.region == "us-west-2"
    assert options.profile == "prof"
    assert options.output_dir == Path(tmp_path).resolve()
