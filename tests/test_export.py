"""Provider-neutral tests for immutable analysis-directory FSx exports."""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from daylily_ec.workflow.export_data import (
    ExportError,
    ExportOptions,
    analysis_dir_from_source_path,
    analysis_headnode_path,
    attach_export_dra,
    clone_status_evidence_s3_uri,
    cleanup_exported_analysis,
    normalize_export_source_path,
    resolve_launch_export_destination_s3_uri,
    run_export_task,
    run_export_workflow,
    validate_export_destination_s3_uri,
    validate_no_overlapping_export_dra,
    validate_s3_destination_prefix_empty,
    verify_exported_clone_status_v2_evidence,
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


class EmptyS3Client:
    def list_objects_v2(self, **_kwargs):
        return {"KeyCount": 0}


class FakeSession:
    def __init__(self, client: FakeFsxClient, s3_client: object | None = None) -> None:
        self.fsx_client = client
        self.s3_client = s3_client or EmptyS3Client()

    def client(self, service_name: str):
        if service_name == "fsx":
            return self.fsx_client
        assert service_name == "s3"
        return self.s3_client


def _exported_status_v2() -> dict[str, object]:
    timestamp = "2026-08-18T04:00:00Z"
    return {
        "schema_version": "daylily.analysis_status.v2",
        "analysis": {
            "analysis_root": "/fsx/analysis_results/user/run",
            "repo_path": "/fsx/analysis_results/user/run/daylily-omics-analysis",
            "created_at": timestamp,
        },
        "updated_at": timestamp,
        "attempts": [
            {
                "attempt_id": "00000000-0000-4000-8000-000000000001",
                "sequence": 1,
                "origin": "dyec_controller",
                "mode": "live",
                "requested_command": "dy-r target",
                "started_at": timestamp,
                "completed_at": timestamp,
                "state": "succeeded",
                "controller": {
                    "state": "succeeded",
                    "session_name": "controller-1",
                    "pid": 1234,
                    "command": "dy-r target",
                    "started_at": timestamp,
                    "completed_at": timestamp,
                    "exit_code": 0,
                },
                "day_run": {
                    "state": "succeeded",
                    "argv": ["bin/day_run", "target"],
                    "started_at": timestamp,
                    "completed_at": timestamp,
                    "exit_code": 0,
                },
                "snakemake": {
                    "state": "succeeded",
                    "argv": ["snakemake", "target"],
                    "started_at": timestamp,
                    "completed_at": timestamp,
                    "exit_code": 0,
                    "log_path": ".snakemake/log/one.snakemake.log",
                    "log_attribution": "exact invocation file-set difference",
                },
            }
        ],
    }


class FakeS3Client:
    def __init__(self, payload: dict[str, object], *, key_count: int = 0) -> None:
        self.payload = payload
        self.key_count = key_count
        self.get_requests: list[dict[str, str]] = []
        self.list_requests: list[dict[str, str | int]] = []

    def list_objects_v2(self, **kwargs):
        self.list_requests.append(kwargs)
        return {"KeyCount": self.key_count}

    def get_object(self, **kwargs):
        self.get_requests.append(kwargs)
        return {"Body": io.BytesIO(json.dumps(self.payload).encode("utf-8"))}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/fsx/analysis_results/user/run", "/analysis_results/user/run/"),
        ("/analysis_results/user/run/", "/analysis_results/user/run/"),
    ],
)
def test_normalize_export_source_accepts_analysis_dir(raw: str, expected: str) -> None:
    assert normalize_export_source_path(raw) == expected


def test_nested_export_source_preserves_full_path_and_analysis_ownership() -> None:
    source = "/fsx/analysis_results/prod-cand-1703/proof-batch/AU"

    assert normalize_export_source_path(source) == (
        "/analysis_results/prod-cand-1703/proof-batch/AU/"
    )
    assert analysis_dir_from_source_path(source) == "prod-cand-1703/proof-batch"
    assert analysis_headnode_path(source) == (
        "/fsx/analysis_results/prod-cand-1703/proof-batch/AU/"
    )


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


def test_validate_and_resolve_nested_export_destination_exactly() -> None:
    source = "/fsx/analysis_results/prod-cand-1703/proof-batch/AU/"
    destination = (
        "s3://lsmc-ssf-sequencing-data/derived/"
        "prod-cand-1703/proof-batch/AU/"
    )

    assert validate_export_destination_s3_uri(
        destination,
        source_path=source,
        cluster_name="prod-cand-1703",
    ) == destination
    assert resolve_launch_export_destination_s3_uri(
        "s3://lsmc-ssf-sequencing-data/derived/",
        source_path=source,
        cluster_name="prod-cand-1703",
    ) == destination
    with pytest.raises(ExportError, match="must end"):
        validate_export_destination_s3_uri(
            "s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/proof-batch/",
            source_path=source,
            cluster_name="prod-cand-1703",
        )


def test_nested_package_destination_uses_explicit_batch_and_source_leaf() -> None:
    source = (
        "/fsx/analysis_results/prod-cand-1703/original-analysis/"
        "daylily-omics-analysis/results/day/hg38/deliveries/inflection/"
        "proof-batch/HG002-Z-HG002-ANALYSIS-UNIT-5X5X/"
    )
    destination = (
        "s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/"
        "proof-batch/HG002-Z-HG002-ANALYSIS-UNIT-5X5X/"
    )

    assert validate_export_destination_s3_uri(
        destination,
        source_path=source,
        cluster_name="prod-cand-1703",
        destination_analysis_id="proof-batch",
    ) == destination


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


def test_attach_nested_export_dra_uses_full_source_but_root_ownership_tag() -> None:
    client = FakeFsxClient()
    source = "/fsx/analysis_results/prod-cand-1703/proof-batch/AU/"
    destination = (
        "s3://lsmc-ssf-sequencing-data/derived/"
        "prod-cand-1703/proof-batch/AU/"
    )

    record = attach_export_dra(
        cluster_name="prod-cand-1703",
        fsx_file_system_id="fs-123",
        source_path=source,
        destination_s3_uri=destination,
        region="us-west-2",
        profile="profile",
        wait=False,
        timeout_seconds=1,
        fsx_client=client,
    )

    assert record.analysis_dir == "prod-cand-1703/proof-batch"
    assert record.file_system_path == (
        "/analysis_results/prod-cand-1703/proof-batch/AU/"
    )
    assert record.headnode_path == source
    assert client.created_association is not None
    assert client.created_association["FileSystemPath"] == record.file_system_path
    assert {"Key": "Name", "Value": record.analysis_dir} in client.created_association[
        "Tags"
    ]


def test_export_rejects_overlapping_s3_repository_path() -> None:
    class ExistingAssociationClient:
        def describe_data_repository_associations(self, **_kwargs):
            return {
                "Associations": [
                    {
                        "AssociationId": "dra-reference",
                        "Lifecycle": "AVAILABLE",
                        "FileSystemPath": "/references/",
                        "DataRepositoryPath": "s3://reference-bucket/",
                    }
                ]
            }

    with pytest.raises(ExportError, match="destination_s3_uri overlaps"):
        validate_no_overlapping_export_dra(
            ExistingAssociationClient(),
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/cluster-a/cache-export-a",
            destination_s3_uri=(
                "s3://reference-bucket/runtime_assets/cached_envs/"
                "cluster-a/cache-export-a/"
            ),
        )


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


def test_run_export_task_uses_exact_nested_path() -> None:
    client = FakeFsxClient()
    receipt = run_export_task(
        fsx_file_system_id="fs-123",
        source_path="/fsx/analysis_results/prod-cand-1703/proof-batch/AU/",
        destination_s3_uri=(
            "s3://lsmc-ssf-sequencing-data/derived/"
            "prod-cand-1703/proof-batch/AU/"
        ),
        cluster_name="prod-cand-1703",
        wait=True,
        timeout_seconds=1,
        fsx_client=client,
    )

    assert receipt["source_path"] == (
        "/analysis_results/prod-cand-1703/proof-batch/AU/"
    )
    assert client.created_task is not None
    assert client.created_task["Paths"] == [receipt["source_path"]]


def test_exported_clone_status_v2_evidence_requires_full_analysis_export() -> None:
    assert clone_status_evidence_s3_uri(
        source_path="/fsx/analysis_results/user/run/",
        destination_s3_uri="s3://bucket/root/user/run/",
    ) == "s3://bucket/root/user/run/daylily-omics-analysis/status.json"
    with pytest.raises(ExportError, match="complete analysis directory"):
        clone_status_evidence_s3_uri(
            source_path="/fsx/analysis_results/user/run/daylily-omics-analysis/",
            destination_s3_uri="s3://bucket/root/user/run/daylily-omics-analysis/",
        )


def test_analysis_export_rejects_nested_source_before_attaching_dra(tmp_path, monkeypatch) -> None:
    client = FakeFsxClient()
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(client, FakeS3Client(_exported_status_v2())),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="cluster-a",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/user/run/AU/",
            destination_s3_uri="s3://bucket/root/user/run/AU/",
            region="us-west-2",
            profile="profile",
            output_dir=tmp_path,
            wait=False,
        )
    )

    assert rc == 1
    assert client.created_association is None
    receipt = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))["fsx_export"]
    assert receipt["phase"] == "validate"
    assert "complete analysis directory" in receipt["failure_details"]["message"]


def test_export_rejects_nonempty_s3_prefix_before_creating_dra(tmp_path, monkeypatch) -> None:
    client = FakeFsxClient()
    s3 = FakeS3Client(_exported_status_v2(), key_count=1)
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(client, s3),
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

    assert rc == 1
    assert client.created_association is None
    assert s3.list_requests == [
        {"Bucket": "bucket", "Prefix": "root/user/run/", "MaxKeys": 1}
    ]
    receipt = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))["fsx_export"]
    assert receipt["phase"] == "preflight"
    assert "destination prefix is not empty" in receipt["failure_details"]["message"]


def test_verify_exported_clone_status_v2_evidence_reads_retained_attempts() -> None:
    s3 = FakeS3Client(_exported_status_v2())

    evidence = verify_exported_clone_status_v2_evidence(
        s3,
        source_path="/fsx/analysis_results/user/run/",
        destination_s3_uri="s3://bucket/root/user/run/",
    )

    assert evidence == {
        "required": True,
        "verified": True,
        "s3_uri": "s3://bucket/root/user/run/daylily-omics-analysis/status.json",
        "schema_version": "daylily.analysis_status.v2",
        "attempt_count": 1,
        "latest_attempt_id": "00000000-0000-4000-8000-000000000001",
    }
    assert s3.get_requests == [
        {
            "Bucket": "bucket",
            "Key": "root/user/run/daylily-omics-analysis/status.json",
        }
    ]


def test_analysis_export_rejects_legacy_evidence_by_default(tmp_path, monkeypatch) -> None:
    client = FakeFsxClient()
    s3 = FakeS3Client({"schema_version": "retired.home.status.v1"})
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(client, s3),
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
            delete_data_in_file_system=True,
        )
    )

    assert rc == 1
    assert client.deleted_association == {
        "AssociationId": "dra-export",
        "DeleteDataInFileSystem": False,
    }


def test_export_workflow_records_validated_clone_status_evidence(tmp_path, monkeypatch) -> None:
    client = FakeFsxClient()
    s3 = FakeS3Client(_exported_status_v2())
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(client, s3),
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
    receipt = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))["fsx_export"]
    assert receipt["clone_status_v2_evidence"]["verified"] is True
    assert receipt["clone_status_v2_evidence"]["attempt_count"] == 1


def test_run_export_workflow_writes_provider_neutral_receipt(tmp_path, monkeypatch) -> None:
    client = FakeFsxClient()
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(client, FakeS3Client(_exported_status_v2())),
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
    assert receipt["clone_status_v2_evidence"]["verified"] is True
    text = (tmp_path / "fsx_export.yaml").read_text(encoding="utf-8").lower()
    for forbidden in ("dayhoff", "ursa", "bloom", "tapdb", "dewey"):
        assert forbidden not in text


def test_run_export_workflow_never_deletes_fsx_after_failed_task(
    tmp_path, monkeypatch
) -> None:
    client = FakeFsxClient(task_lifecycle="FAILED")
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
            delete_data_in_file_system=True,
        )
    )

    assert rc == 1
    assert client.deleted_association == {
        "AssociationId": "dra-export",
        "DeleteDataInFileSystem": False,
    }
    receipt = yaml.safe_load(
        (tmp_path / "fsx_export.yaml").read_text(encoding="utf-8")
    )["fsx_export"]
    assert receipt["status"] == "error"
    assert receipt["task_lifecycle"] == "FAILED"
    assert receipt["detached"] is True
    assert receipt["delete_data_in_file_system"] is False


def test_exports_transfer_emits_json_receipt_and_preserves_fsx(monkeypatch) -> None:
    from daylily_ec.cli import app

    observed: dict[str, object] = {}

    def fake_workflow(options: ExportOptions) -> int:
        observed["options"] = options
        receipt = {
            "fsx_export": {
                "schema_version": 6,
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
    payload = yaml.safe_load(result.stdout)
    assert payload["schema_version"] == "dyec.exports.transfer.v1"
    assert payload["ok"] is True
    assert payload["operation"] == "transfer"
    assert payload["task_lifecycle"] == "SUCCEEDED"
    options = observed["options"]
    assert isinstance(options, ExportOptions)
    assert options.destination_analysis_id == "M-RGX-FSAP"
    assert options.delete_data_in_file_system is False
    assert not hasattr(options, "require_clone_status_v2_evidence")
    assert options.timeout_seconds == 5400


def test_analysis_export_cli_has_no_legacy_evidence_opt_in() -> None:
    from daylily_ec.cli import app

    for argv in (["export", "--help"], ["exports", "transfer", "--help"]):
        result = runner.invoke(app, argv)
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--require-clone-status-v2-evidence" not in result.output


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
