"""Tests for direct analysis-directory FSx DRA export workflow and CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from botocore.exceptions import ClientError
import pytest
import yaml
from typer.testing import CliRunner

from daylily_ec.repositories import load_repository_catalog
from daylily_ec.workflow.export_data import (
    ExportOptions,
    attach_export_dra,
    detach_export_dra,
    normalize_export_source_path,
    run_export_task,
    run_export_workflow,
    validate_export_destination_s3_uri,
    validate_s3_destination_prefix_empty,
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
        detach_not_found: bool = False,
        association_lifecycle: str = "AVAILABLE",
        existing_associations: list[dict[str, Any]] | None = None,
    ) -> None:
        self.task_lifecycle = task_lifecycle
        self.detach_fails = detach_fails
        self.detach_not_found = detach_not_found
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
                    "FileSystemPath": "/analysis_results/johnm/illumina_run_qc/",
                    "DataRepositoryPath": (
                        "s3://bucket/analysis_results/johnm/illumina_run_qc/"
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
        if self.detach_not_found:
            raise ClientError(
                {
                    "Error": {
                        "Code": "DataRepositoryAssociationNotFound",
                        "Message": "Data repository association does not exist.",
                    }
                },
                "DeleteDataRepositoryAssociation",
            )
        self.deleted_association_id = params["AssociationId"]
        assert params["DeleteDataInFileSystem"] is False
        return {"Association": {"AssociationId": params["AssociationId"], "Lifecycle": "DELETED"}}


class FakeSession:
    def __init__(self, client: FakeFsxClient, *, s3_client: "FakeS3Client | None" = None) -> None:
        self._client = client
        self._s3_client = s3_client or FakeS3Client()

    def client(self, service: str) -> Any:
        if service == "s3":
            return self._s3_client
        assert service == "fsx"
        return self._client


class FakeS3Client:
    def __init__(self, *, key_count: int = 0, objects: dict[str, str] | None = None) -> None:
        self.key_count = key_count
        self.objects = objects or {}
        self.list_calls: list[dict[str, Any]] = []

    def list_objects_v2(self, **params: Any) -> dict[str, Any]:
        self.list_calls.append(params)
        return {"KeyCount": self.key_count}

    def get_object(self, **params: Any) -> dict[str, Any]:
        key = f"s3://{params['Bucket']}/{params['Key']}"
        if key not in self.objects:
            raise RuntimeError(f"missing fake s3 object: {key}")

        class Body:
            def __init__(self, text: str) -> None:
                self.text = text

            def read(self) -> bytes:
                return self.text.encode("utf-8")

        return {"Body": Body(self.objects[key])}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/fsx/analysis_results/johnm/illumina_run_qc", "/analysis_results/johnm/illumina_run_qc/"),
        ("/analysis_results/johnm/illumina_run_qc/", "/analysis_results/johnm/illumina_run_qc/"),
    ],
)
def test_normalize_export_source_accepts_analysis_dir(raw: str, expected: str) -> None:
    assert normalize_export_source_path(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "/fsx/exports/export-1/",
        "/fsx/run_dir_mounts/RUN123/fastqs/",
        "/fsx/references/runtime_assets/cached_envs/",
        "/analysis_results/johnm/illumina_run_qc/nested/",
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
            "s3://bucket/derived/lsmc/ssf-hq/johnm/illumina_run_qc",
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
        )
        == "s3://bucket/derived/lsmc/ssf-hq/johnm/illumina_run_qc/"
    )
    with pytest.raises(RuntimeError, match="destination_s3_uri must end with"):
        validate_export_destination_s3_uri(
            "s3://bucket/analysis_results/ubuntu/other/",
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
        )


def test_validate_s3_destination_prefix_rejects_existing_objects() -> None:
    fake_s3 = FakeS3Client(key_count=1)

    with pytest.raises(RuntimeError, match="not empty"):
        validate_s3_destination_prefix_empty(
            fake_s3,
            "s3://bucket/derived/lsmc/ssf-hq/johnm/illumina_run_qc/",
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
        )

    assert fake_s3.list_calls == [
        {
            "Bucket": "bucket",
            "Prefix": "derived/lsmc/ssf-hq/johnm/illumina_run_qc/",
            "MaxKeys": 1,
        }
    ]


def test_attach_export_dra_uses_analysis_dir_without_auto_export_policy() -> None:
    fake = FakeFsxClient()

    record = attach_export_dra(
        cluster_name="alpha",
        fsx_file_system_id="fs-123",
        source_path="/fsx/analysis_results/johnm/illumina_run_qc",
        destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc",
        region="us-west-2",
        profile="prof",
        wait=True,
        timeout_seconds=1,
        fsx_client=fake,
    )

    assert record.association_id == "dra-export"
    assert record.analysis_dir == "johnm/illumina_run_qc"
    assert fake.created_association is not None
    assert fake.created_association["FileSystemPath"] == "/analysis_results/johnm/illumina_run_qc/"
    assert (
        fake.created_association["DataRepositoryPath"]
        == "s3://bucket/analysis_results/johnm/illumina_run_qc/"
    )
    assert fake.created_association["BatchImportMetaDataOnCreate"] is False
    assert "S3" not in fake.created_association


def test_attach_export_dra_rejects_overlapping_existing_dra() -> None:
    fake = FakeFsxClient(
        existing_associations=[
            {
                "AssociationId": "dra-existing",
                "FileSystemPath": "/analysis_results/johnm/illumina_run_qc/",
                "Lifecycle": "AVAILABLE",
            }
        ]
    )

    with pytest.raises(RuntimeError, match="overlaps existing"):
        attach_export_dra(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc",
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
        source_path="/analysis_results/johnm/illumina_run_qc/",
        destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc/",
        wait=True,
        timeout_seconds=1,
        fsx_client=fake,
    )

    assert payload["task_id"] == "task-123"
    assert payload["task_lifecycle"] == "SUCCEEDED"
    assert fake.created_task is not None
    assert fake.created_task["Type"] == "EXPORT_TO_REPOSITORY"
    assert fake.created_task["Paths"] == ["/analysis_results/johnm/illumina_run_qc/"]
    assert fake.created_task["Report"]["Path"].startswith(
        "s3://bucket/analysis_results/johnm/illumina_run_qc/_daylily_monitor/fsx-export/"
    )


def test_run_export_workflow_success_writes_v4_receipt(tmp_path, monkeypatch) -> None:
    fake = FakeFsxClient()
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
        )
    )

    assert rc == 0
    payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
    receipt = payload["fsx_export"]
    assert receipt["schema_version"] == 4
    assert receipt["status"] == "success"
    assert receipt["analysis_dir"] == "johnm/illumina_run_qc"
    assert receipt["source_path"] == "/analysis_results/johnm/illumina_run_qc/"
    assert receipt["headnode_path"] == "/fsx/analysis_results/johnm/illumina_run_qc/"
    assert receipt["destination_s3_uri"] == "s3://bucket/analysis_results/johnm/illumina_run_qc/"
    assert receipt["fsx_root"] == "/fsx/analysis_results/johnm/illumina_run_qc/"
    assert receipt["s3_root"] == "s3://bucket/analysis_results/johnm/illumina_run_qc/"
    assert (
        receipt["dayoa_analysis_root"]
        == "/fsx/analysis_results/johnm/illumina_run_qc/daylily-omics-analysis/"
    )
    assert (
        receipt["dayoa_s3_root"]
        == "s3://bucket/analysis_results/johnm/illumina_run_qc/daylily-omics-analysis/"
    )
    assert receipt["fsx_file_system_id"] == "fs-123"
    assert receipt["association_id"] == "dra-export"
    assert receipt["task_id"] == "task-123"
    assert receipt["task_lifecycle"] == "SUCCEEDED"
    assert receipt["detached"] is True
    assert receipt["delete_data_in_file_system"] is False
    assert fake.deleted_association_id == "dra-export"


def _dayoa_evidence_manifest() -> str:
    digest = "a" * 64
    payload = {
        "schema_version": "dayoa.evidence_manifest.v1",
        "manifest_checksum": "b" * 64,
        "generated_at": "2026-05-28T00:00:00Z",
        "analysis": {"genome_build": "hg38_broad"},
        "workflow": {
            "pipeline_name": "daylily-omics-analysis",
            "pipeline_version": "2.0.12",
            "git_sha": "abc123",
            "snakemake_version": "7.32.4",
            "workflow_config_hash": digest,
            "workflow_profile": "slurm",
        },
        "files": [
            {
                "relative_path": "results/day/hg38_broad/reports/DAY_final_multiqc.html",
                "size_bytes": 10,
                "sha256": digest,
                "classification": "multiqc_html",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": "results/day/hg38_broad/reports/DAY_final_multiqc_data/multiqc_data.json",
                "size_bytes": 11,
                "sha256": digest,
                "classification": "multiqc_data_json",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": "results/day/hg38_broad/reports/DAY_final_multiqc_data/multiqc_general_stats.txt",
                "size_bytes": 12,
                "sha256": digest,
                "classification": "multiqc_general_stats",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": "results/day/hg38_broad/reports/DAY_final_multiqc_data/multiqc_sources.txt",
                "size_bytes": 13,
                "sha256": digest,
                "classification": "multiqc_sources",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": "results/day/hg38_broad/reports/DAY_final_multiqc_data/multiqc.log",
                "size_bytes": 14,
                "sha256": digest,
                "classification": "multiqc_log",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": "results/day/hg38_broad/reports/multiqc_inputs/final/manifest.tsv",
                "size_bytes": 15,
                "sha256": digest,
                "classification": "staging_manifest",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": "results/day/hg38_broad/reports/benchmarks_summary.tsv",
                "size_bytes": 16,
                "sha256": digest,
                "classification": "benchmark",
                "parser_relevant": False,
                "required": False,
            },
        ],
    }
    return json.dumps(payload)


def test_run_export_workflow_registers_dewey_after_success(tmp_path, monkeypatch) -> None:
    fake = FakeFsxClient()
    manifest_uri = (
        "s3://bucket/analysis_results/johnm/illumina_run_qc/daylily-omics-analysis/"
        "results/day/hg38_broad/reports/dayoa_evidence_manifest.json"
    )
    fake_s3 = FakeS3Client(objects={manifest_uri: _dayoa_evidence_manifest()})
    monkeypatch.setenv("DEWEY_TOKEN", "token-1")
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake, s3_client=fake_s3),
    )
    captured: dict[str, Any] = {}

    def fake_register_with_dewey(*, dewey_url: str, token: str, requests: dict[str, Any]):
        captured["dewey_url"] = dewey_url
        captured["token"] = token
        captured["requests"] = requests
        return {
            "analysis_response": {"artifact_set_euid": "Z-ASET-1"},
            "multiqc_response": {"artifact_set_euid": "Z-MQC-1"},
            "analysis_request_manifest_sha256": requests["analysis"]["manifest_sha256"],
            "multiqc_request_manifest_sha256": requests["multiqc"]["manifest_sha256"],
        }

    monkeypatch.setattr(
        "daylily_ec.workflow.dewey_registration.register_with_dewey",
        fake_register_with_dewey,
    )
    command = load_repository_catalog().get_command(
        "illumina_snv_alignstats_relatedness_vep_multiqc"
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
            artifact_registration_policy=command.artifact_registration,
            artifact_registration_genome=command.genome,
            dewey_url="https://dewey.example",
            dewey_token_env="DEWEY_TOKEN",
        )
    )

    assert rc == 0
    payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
    receipt = payload["fsx_export"]
    assert receipt["dewey_registration_status"] == "success"
    assert receipt["dewey_selected_artifact_count"] == 7
    assert (tmp_path / "dewey_registration_receipt.json").is_file()
    assert captured["dewey_url"] == "https://dewey.example"
    assert captured["token"] == "token-1"
    assert captured["requests"]["analysis"]["analysis_euid"] == "illumina_run_qc"
    assert captured["requests"]["analysis"]["artifacts"][0]["storage_uri"].startswith(
        "s3://bucket/analysis_results/johnm/illumina_run_qc/daylily-omics-analysis/"
    )


def test_run_export_workflow_rejects_malformed_exported_manifest(tmp_path, monkeypatch) -> None:
    fake = FakeFsxClient()
    manifest_uri = (
        "s3://bucket/analysis_results/johnm/illumina_run_qc/daylily-omics-analysis/"
        "results/day/hg38_broad/reports/dayoa_evidence_manifest.json"
    )
    fake_s3 = FakeS3Client(objects={manifest_uri: "{not json"})
    monkeypatch.setenv("DEWEY_TOKEN", "token-1")
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake, s3_client=fake_s3),
    )
    command = load_repository_catalog().get_command(
        "illumina_snv_alignstats_relatedness_vep_multiqc"
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
            artifact_registration_policy=command.artifact_registration,
            artifact_registration_genome=command.genome,
            dewey_url="https://dewey.example",
            dewey_token_env="DEWEY_TOKEN",
        )
    )

    assert rc == 1
    payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
    receipt = payload["fsx_export"]
    assert receipt["status"] == "error"
    assert receipt["dewey_registration_status"] == "error"
    assert "malformed" in receipt["failure_details"]["message"]
    assert not (tmp_path / "dewey_registration_receipt.json").exists()


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
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc/",
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
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc/",
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
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc/",
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


def test_run_export_workflow_treats_created_dra_not_found_as_detached(
    tmp_path, monkeypatch
) -> None:
    fake = FakeFsxClient(detach_not_found=True)
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="alpha",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/johnm/illumina_run_qc",
            destination_s3_uri="s3://bucket/analysis_results/johnm/illumina_run_qc/",
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
        )
    )

    assert rc == 0
    receipt = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))[
        "fsx_export"
    ]
    assert receipt["status"] == "success"
    assert receipt["detached"] is True
    assert receipt["detach_lifecycle"] == "NOT_FOUND"
    assert receipt["detach_absent"] is True
    assert fake.deleted_association_id is None


def test_direct_detach_still_fails_when_requested_association_is_missing() -> None:
    fake = FakeFsxClient(detach_not_found=True)

    with pytest.raises(RuntimeError, match="Unable to detach export data repository association"):
        detach_export_dra(
            association_id="dra-missing",
            region="us-west-2",
            profile="prof",
            wait=True,
            timeout_seconds=1,
            fsx_client=fake,
        )


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
                "/fsx/analysis_results/johnm/illumina_run_qc",
                "--destination-s3-uri",
                "s3://bucket/analysis_results/johnm/illumina_run_qc/",
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
    assert options.source_path == "/fsx/analysis_results/johnm/illumina_run_qc"
    assert options.destination_s3_uri == "s3://bucket/analysis_results/johnm/illumina_run_qc/"
    assert options.region == "us-west-2"
    assert options.profile == "prof"
    assert options.output_dir == Path(tmp_path).resolve()
