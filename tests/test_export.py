"""Provider-neutral tests for immutable analysis-directory FSx exports."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from daylily_ec.workflow.export_data import (
    ExportError,
    ExportOptions,
    attach_export_dra,
    cleanup_exported_analysis,
    normalize_export_source_path,
    resolve_launch_export_destination_s3_uri,
    run_export_task,
    run_export_workflow,
    validate_export_destination_s3_uri,
    validate_s3_destination_prefix_empty,
)

runner = CliRunner()


class FakeFsxClient:
    def __init__(self, *, task_lifecycle: str = "SUCCEEDED") -> None:
        self.task_lifecycle = task_lifecycle
        self.created_association: dict[str, object] | None = None
        self.deleted_association: dict[str, object] | None = None
        self.created_task: dict[str, object] | None = None
        self.association_active = False

    def describe_file_systems(self, **_kwargs):
        return {
            "FileSystems": [
                {
                    "FileSystemId": "fs-123",
                    "FileSystemType": "LUSTRE",
                    "Lifecycle": "AVAILABLE",
                    "LustreConfiguration": {"DeploymentType": "SCRATCH_2"},
                }
            ]
        }

    def describe_data_repository_associations(self, **_kwargs):
        if self.association_active and self.created_association is not None:
            return {
                "Associations": [
                    {
                        "AssociationId": "dra-export",
                        "FileSystemId": self.created_association["FileSystemId"],
                        "FileSystemPath": self.created_association["FileSystemPath"],
                        "DataRepositoryPath": self.created_association[
                            "DataRepositoryPath"
                        ],
                        "Lifecycle": "AVAILABLE",
                    }
                ]
            }
        return {"Associations": []}

    def create_data_repository_association(self, **kwargs):
        self.created_association = kwargs
        self.association_active = True
        return {
            "Association": {
                "AssociationId": "dra-export",
                "FileSystemPath": kwargs["FileSystemPath"],
                "Lifecycle": "AVAILABLE",
            }
        }

    def create_data_repository_task(self, **kwargs):
        self.created_task = kwargs
        return {
            "DataRepositoryTask": {
                "TaskId": "task-1",
                "Lifecycle": self.task_lifecycle,
            }
        }

    def describe_data_repository_tasks(self, **_kwargs):
        return {
            "DataRepositoryTasks": [
                {"TaskId": "task-1", "Lifecycle": self.task_lifecycle}
            ]
        }

    def delete_data_repository_association(self, **kwargs):
        self.deleted_association = kwargs
        self.association_active = False
        return {
            "AssociationId": kwargs["AssociationId"],
            "Lifecycle": "DELETING",
            "DeleteDataInFileSystem": kwargs["DeleteDataInFileSystem"],
        }


class FakeSession:
    def __init__(self, client: FakeFsxClient) -> None:
        self.fsx_client = client

    def client(self, service_name: str):
        assert service_name == "fsx"
        return self.fsx_client


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/fsx/analysis_results/user/run", "/analysis_results/user/run/"),
        ("/analysis_results/user/run/", "/analysis_results/user/run/"),
    ],
)
def test_normalize_export_source_accepts_analysis_dir(raw: str, expected: str) -> None:
    assert normalize_export_source_path(raw) == expected


@pytest.mark.parametrize("raw", ["/fsx", "/tmp/run", "/fsx/analysis_results/user"])
def test_normalize_export_source_rejects_non_analysis_dir(raw: str) -> None:
    with pytest.raises(ExportError):
        normalize_export_source_path(raw)


def test_validate_and_resolve_export_destination() -> None:
    source = "/fsx/analysis_results/user/run"
    assert validate_export_destination_s3_uri(
        "s3://bucket/root/user/run/", source_path=source
    ) == "s3://bucket/root/user/run/"
    assert resolve_launch_export_destination_s3_uri(
        "s3://bucket/root/", source_path=source, cluster_name="cluster-a"
    ) == "s3://bucket/root/cluster-a/run/"
    with pytest.raises(ExportError, match="must end"):
        validate_export_destination_s3_uri("s3://bucket/wrong/", source_path=source)
    assert validate_export_destination_s3_uri(
        "s3://bucket/derived/cluster-a/analysis_results/M-RGX-FSAP/",
        source_path=source,
        cluster_name="cluster-a",
        destination_analysis_id="M-RGX-FSAP",
    ) == "s3://bucket/derived/cluster-a/analysis_results/M-RGX-FSAP/"


def test_validate_s3_destination_prefix_is_immutable() -> None:
    class Existing:
        def list_objects_v2(self, **_kwargs):
            return {"KeyCount": 1}

    with pytest.raises(ExportError, match="not empty"):
        validate_s3_destination_prefix_empty(
            Existing(),
            "s3://bucket/root/user/run/",
            source_path="/fsx/analysis_results/user/run",
        )


def test_attach_export_dra_has_no_autoexport_or_delete() -> None:
    client = FakeFsxClient()
    record = attach_export_dra(
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        source_path="/fsx/analysis_results/user/run",
        destination_s3_uri="s3://bucket/root/user/run/",
        region="us-west-2",
        profile="profile",
        wait=False,
        timeout_seconds=1,
        fsx_client=client,
    )
    assert record.association_id == "dra-export"
    assert client.created_association is not None
    assert client.created_association["BatchImportMetaDataOnCreate"] is False
    assert "S3" not in client.created_association


def test_run_export_task_uses_exact_analysis_path() -> None:
    client = FakeFsxClient()
    receipt = run_export_task(
        fsx_file_system_id="fs-123",
        source_path="/fsx/analysis_results/user/run",
        destination_s3_uri="s3://bucket/root/user/run/",
        cluster_name="cluster-a",
        wait=True,
        timeout_seconds=1,
        fsx_client=client,
    )
    assert receipt["task_lifecycle"] == "SUCCEEDED"
    assert client.created_task is not None
    assert client.created_task["Paths"] == ["/analysis_results/user/run/"]
    assert client.created_task["Report"]["Scope"] == "FAILED_FILES_ONLY"


def test_run_export_workflow_writes_provider_neutral_receipt(tmp_path, monkeypatch) -> None:
    client = FakeFsxClient()
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(client),
    )
    rc = run_export_workflow(
        ExportOptions(
            cluster_name="cluster-a",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/user/run",
            destination_s3_uri="s3://bucket/root/user/run/",
            region="us-west-2",
            profile="profile",
            output_dir=tmp_path,
            wait=False,
        )
    )
    assert rc == 0
    receipt = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))[
        "fsx_export"
    ]
    assert receipt["status"] == "success"
    assert receipt["detached"] is True
    assert receipt["delete_data_in_file_system"] is False
    text = (tmp_path / "fsx_export.yaml").read_text(encoding="utf-8").lower()
    for forbidden in ("dayhoff", "ursa", "bloom", "tapdb", "dewey"):
        assert forbidden not in text


def test_exports_transfer_emits_json_receipt_and_preserves_fsx(monkeypatch) -> None:
    from daylily_ec.cli import app

    observed: dict[str, object] = {}

    def fake_workflow(options: ExportOptions) -> int:
        observed["options"] = options
        receipt = {
            "fsx_export": {
                "status": "success",
                "task_id": "task-1",
                "task_lifecycle": "SUCCEEDED",
                "destination_s3_uri": options.destination_s3_uri,
                "association_id": "dra-1",
                "detached": True,
                "delete_data_in_file_system": False,
            }
        }
        (options.output_dir / "fsx_export.yaml").write_text(
            yaml.safe_dump(receipt),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data.run_export_workflow",
        fake_workflow,
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "exports",
            "transfer",
            "--cluster",
            "cluster-a",
            "--fsx-file-system-id",
            "fs-123",
            "--source-path",
            "/fsx/analysis_results/ursa-M-RGX-FSAP/M-RGX-FSDG",
            "--destination-s3-uri",
            "s3://bucket/derived/cluster-a/analysis_results/M-RGX-FSAP/",
            "--destination-analysis-id",
            "M-RGX-FSAP",
            "--region",
            "us-west-2",
            "--profile",
            "lsmc",
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert yaml.safe_load(result.stdout)["task_lifecycle"] == "SUCCEEDED"
    options = observed["options"]
    assert isinstance(options, ExportOptions)
    assert options.destination_analysis_id == "M-RGX-FSAP"
    assert options.delete_data_in_file_system is False
    assert options.timeout_seconds == 5400


def test_cleanup_exported_analysis_deletes_only_exact_fsx_path() -> None:
    client = FakeFsxClient()
    payload = cleanup_exported_analysis(
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        source_path="/fsx/analysis_results/ursa/M-RGX-FSDG",
        destination_s3_uri=(
            "s3://bucket/derived/cluster-a/analysis_results/M-RGX-FSAP/"
        ),
        destination_analysis_id="M-RGX-FSAP",
        region="us-west-2",
        profile="lsmc",
        timeout_seconds=1,
        fsx_client=client,
    )

    assert payload["status"] == "success"
    assert payload["source_path"] == "/analysis_results/ursa/M-RGX-FSDG/"
    assert payload["destination_s3_uri"] == (
        "s3://bucket/derived/cluster-a/analysis_results/M-RGX-FSAP/"
    )
    assert payload["delete_data_in_file_system"] is True
    assert payload["s3_delete_requested"] is False
    assert client.created_association is not None
    assert "S3" not in client.created_association
    assert "AutoExportPolicy" not in client.created_association
    assert client.deleted_association == {
        "AssociationId": "dra-export",
        "DeleteDataInFileSystem": True,
    }


def test_exports_cleanup_requires_confirmation_and_emits_receipt(monkeypatch) -> None:
    from daylily_ec.cli import app

    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    argv = [
        "--json",
        "exports",
        "cleanup",
        "--cluster",
        "cluster-a",
        "--fsx-file-system-id",
        "fs-123",
        "--source-path",
        "/fsx/analysis_results/ursa/M-RGX-FSDG",
        "--destination-s3-uri",
        "s3://bucket/derived/cluster-a/analysis_results/M-RGX-FSAP/",
        "--destination-analysis-id",
        "M-RGX-FSAP",
        "--region",
        "us-west-2",
        "--profile",
        "lsmc",
    ]
    denied = runner.invoke(app, argv)
    assert denied.exit_code != 0
    assert "--confirm-fsx-delete is required" in denied.output

    with patch(
        "daylily_ec.workflow.export_data.cleanup_exported_analysis",
        return_value={
            "status": "success",
            "headnode_path": "/fsx/analysis_results/ursa/M-RGX-FSDG/",
            "association_id": "dra-export",
        },
    ) as cleanup:
        accepted = runner.invoke(app, [*argv, "--confirm-fsx-delete"])

    assert accepted.exit_code == 0, accepted.stdout + accepted.stderr
    assert yaml.safe_load(accepted.stdout)["status"] == "success"
    assert cleanup.call_args.kwargs["source_path"] == (
        "/fsx/analysis_results/ursa/M-RGX-FSDG"
    )


def test_cli_export_passes_only_provider_neutral_options(tmp_path, monkeypatch) -> None:
    from daylily_ec.cli import app

    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    with (
        patch("daylily_ec.workflow.export_data.configure_logging"),
        patch("daylily_ec.workflow.export_data.run_export_workflow", return_value=0) as run,
    ):
        result = runner.invoke(
            app,
            [
                "export",
                "--cluster-name",
                "cluster-a",
                "--source-path",
                "/fsx/analysis_results/user/run",
                "--destination-s3-uri",
                "s3://bucket/root/user/run/",
                "--region",
                "us-west-2",
                "--output-dir",
                str(tmp_path),
            ],
        )
    assert result.exit_code == 0
    options = run.call_args.args[0]
    assert not hasattr(options, "dewey_url")
    assert not hasattr(options, "artifact_registration_policy")


def test_removed_provider_export_options_fail_closed(tmp_path, monkeypatch) -> None:
    from daylily_ec.cli import app

    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    result = runner.invoke(
        app,
        [
            "export",
            "--source-path",
            "/fsx/analysis_results/user/run",
            "--destination-s3-uri",
            "s3://bucket/root/user/run/",
            "--region",
            "us-west-2",
            "--output-dir",
            str(tmp_path),
            "--dewey-url",
            "https://example.invalid",
        ],
    )
    assert result.exit_code != 0
    assert "No such option" in result.output
