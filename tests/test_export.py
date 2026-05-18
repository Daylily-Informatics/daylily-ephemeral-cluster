"""Tests for direct analysis-directory FSx DRA export workflow and CLI."""

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
    run_export_task,
    run_export_workflow,
    validate_export_destination_s3_uri,
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
    def __init__(
        self,
        *,
        task_lifecycle: str = "SUCCEEDED",
        detach_fails: bool = False,
        association_lifecycle: str = "AVAILABLE",
        existing_associations: list[dict[str, Any]] | None = None,
    ) -> None:
        self.task_lifecycle = task_lifecycle
        self.detach_fails = detach_fails
        self.association_lifecycle = association_lifecycle
        self.created_association: dict[str, Any] | None = None
        self.created_task: dict[str, Any] | None = None
        self.deleted_association_id: str | None = None
        self.existing_associations = existing_associations or []

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
        if params.get("Filters"):
            return {"Associations": list(self.existing_associations)}
        lifecycle = (
            "DELETED"
            if self.deleted_association_id == "dra-export"
            else self.association_lifecycle
        )
        return {
            "Associations": [
                {
                    "AssociationId": "dra-export",
                    "FileSystemId": "fs-123",
                    "FileSystemPath": "/analysis_results/ubuntu/illumina_run_qc/",
                    "DataRepositoryPath": (
                        "s3://bucket/analysis_results/ubuntu/illumina_run_qc/"
                    ),
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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/fsx/analysis_results/ubuntu/illumina_run_qc", "/analysis_results/ubuntu/illumina_run_qc/"),
        ("/analysis_results/ubuntu/illumina_run_qc/", "/analysis_results/ubuntu/illumina_run_qc/"),
    ],
)
def test_normalize_export_source_accepts_analysis_dir(raw: str, expected: str) -> None:
    assert normalize_export_source_path(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "/fsx/exports/export-1/",
        "/fsx/run_dir_mounts/RUN123/fastqs/",
        "/fsx/data/cached_envs/",
        "/analysis_results/ubuntu/illumina_run_qc/nested/",
        "/analysis_results/ubuntu/../illumina_run_qc/",
        "/analysis_results/ubuntu//illumina_run_qc/",
    ],
)
def test_normalize_export_source_rejects_non_analysis_dir(raw: str) -> None:
    with pytest.raises(RuntimeError):
        normalize_export_source_path(raw)


def test_validate_export_destination_requires_matching_suffix() -> None:
    assert (
        validate_export_destination_s3_uri(
            "s3://bucket/analysis_results/ubuntu/illumina_run_qc",
            source_path="/fsx/analysis_results/ubuntu/illumina_run_qc",
        )
        == "s3://bucket/analysis_results/ubuntu/illumina_run_qc/"
    )
    with pytest.raises(RuntimeError, match="destination_s3_uri must end with"):
        validate_export_destination_s3_uri(
            "s3://bucket/analysis_results/ubuntu/other/",
            source_path="/fsx/analysis_results/ubuntu/illumina_run_qc",
        )


def test_attach_export_dra_uses_analysis_dir_without_auto_export_policy() -> None:
    fake = FakeFsxClient()

    record = attach_export_dra(
        cluster_name="alpha",
        fsx_file_system_id="fs-123",
        source_path="/fsx/analysis_results/ubuntu/illumina_run_qc",
        destination_s3_uri="s3://bucket/analysis_results/ubuntu/illumina_run_qc",
        region="us-west-2",
        profile="prof",
        wait=True,
        timeout_seconds=1,
        fsx_client=fake,
    )

    assert record.association_id == "dra-export"
    assert record.analysis_dir == "illumina_run_qc"
    assert fake.created_association is not None
    assert fake.created_association["FileSystemPath"] == "/analysis_results/ubuntu/illumina_run_qc/"
    assert (
        fake.created_association["DataRepositoryPath"]
        == "s3://bucket/analysis_results/ubuntu/illumina_run_qc/"
    )
    assert fake.created_association["BatchImportMetaDataOnCreate"] is False
    assert "S3" not in fake.created_association


def test_attach_export_dra_rejects_overlapping_existing_dra() -> None:
    fake = FakeFsxClient(
        existing_associations=[
            {
                "AssociationId": "dra-existing",
                "FileSystemPath": "/analysis_results/ubuntu/illumina_run_qc/",
                "Lifecycle": "AVAILABLE",
            }
        ]
    )

    with pytest.raises(RuntimeError, match="overlaps existing"):
        attach_export_dra(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/ubuntu/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/ubuntu/illumina_run_qc",
            region="us-west-2",
            profile="prof",
            wait=True,
            timeout_seconds=1,
            fsx_client=fake,
        )


def test_run_export_task_starts_exact_analysis_path_and_report() -> None:
    fake = FakeFsxClient()

    payload = run_export_task(
        fsx_file_system_id="fs-123",
        source_path="/analysis_results/ubuntu/illumina_run_qc/",
        destination_s3_uri="s3://bucket/analysis_results/ubuntu/illumina_run_qc/",
        wait=True,
        timeout_seconds=1,
        fsx_client=fake,
    )

    assert payload["task_id"] == "task-123"
    assert payload["task_lifecycle"] == "SUCCEEDED"
    assert fake.created_task is not None
    assert fake.created_task["Type"] == "EXPORT_TO_REPOSITORY"
    assert fake.created_task["Paths"] == ["/analysis_results/ubuntu/illumina_run_qc/"]
    assert fake.created_task["Report"]["Path"].startswith(
        "s3://bucket/analysis_results/ubuntu/illumina_run_qc/_daylily_monitor/fsx-export/"
    )


def test_run_export_workflow_success_writes_v3_receipt(tmp_path, monkeypatch) -> None:
    fake = FakeFsxClient()
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/ubuntu/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/ubuntu/illumina_run_qc/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
        )
    )

    assert rc == 0
    payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
    receipt = payload["fsx_export"]
    assert receipt["schema_version"] == 3
    assert receipt["status"] == "success"
    assert receipt["analysis_dir"] == "illumina_run_qc"
    assert receipt["source_path"] == "/analysis_results/ubuntu/illumina_run_qc/"
    assert receipt["headnode_path"] == "/fsx/analysis_results/ubuntu/illumina_run_qc/"
    assert receipt["destination_s3_uri"] == "s3://bucket/analysis_results/ubuntu/illumina_run_qc/"
    assert receipt["fsx_file_system_id"] == "fs-123"
    assert receipt["association_id"] == "dra-export"
    assert receipt["task_id"] == "task-123"
    assert receipt["task_lifecycle"] == "SUCCEEDED"
    assert receipt["detached"] is True
    assert receipt["delete_data_in_file_system"] is False
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
            source_path="/fsx/analysis_results/ubuntu/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/ubuntu/illumina_run_qc/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
        )
    )

    assert rc == 1
    payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
    assert payload["fsx_export"]["status"] == "error"
    assert payload["fsx_export"]["detached"] is True
    assert payload["fsx_export"]["failure_details"]["task_failure_details"] == {
        "Message": "boom"
    }
    assert fake.deleted_association_id == "dra-export"


def test_run_export_workflow_attach_timeout_still_detaches(tmp_path, monkeypatch) -> None:
    fake = FakeFsxClient(association_lifecycle="CREATING")
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/ubuntu/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/ubuntu/illumina_run_qc/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
            timeout_seconds=0,
        )
    )

    assert rc == 1
    receipt = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))[
        "fsx_export"
    ]
    assert receipt["status"] == "error"
    assert receipt["association_id"] == "dra-export"
    assert receipt["detached"] is True
    assert receipt["failure_details"]["message"].startswith(
        "Timed out waiting for FSx data repository association dra-export"
    )
    assert fake.created_task is None
    assert fake.deleted_association_id == "dra-export"


def test_run_export_workflow_detach_failure_surfaces_association(tmp_path, monkeypatch) -> None:
    fake = FakeFsxClient(detach_fails=True)
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/ubuntu/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/ubuntu/illumina_run_qc/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
        )
    )

    assert rc == 1
    receipt = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))[
        "fsx_export"
    ]
    assert receipt["association_id"] == "dra-export"
    assert receipt["status"] == "error"
    assert receipt["detached"] is False
    assert receipt["failure_details"]["message"] == "detach failed"


def test_cli_export_passes_direct_analysis_options(tmp_path, monkeypatch):
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
                "--source-path",
                "/fsx/analysis_results/ubuntu/illumina_run_qc",
                "--destination-s3-uri",
                "s3://bucket/analysis_results/ubuntu/illumina_run_qc/",
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
    assert not hasattr(options, "export_id")
    assert options.source_path == "/fsx/analysis_results/ubuntu/illumina_run_qc"
    assert options.destination_s3_uri == "s3://bucket/analysis_results/ubuntu/illumina_run_qc/"
    assert options.region == "us-west-2"
    assert options.profile == "prof"
    assert options.output_dir == Path(tmp_path).resolve()
