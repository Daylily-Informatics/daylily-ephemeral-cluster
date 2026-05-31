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
from daylily_ec.workflow.dewey_registration import (
    build_registration_requests,
    register_exported_analysis_directory_links,
)
from daylily_ec.workflow.export_data import (
    ExportOptions,
    RegisterExistingExportOptions,
    attach_export_dra,
    detach_export_dra,
    normalize_export_source_path,
    run_dewey_registration_for_existing_export,
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
    def __init__(
        self,
        *,
        key_count: int = 0,
        objects: dict[str, str] | None = None,
        listed_objects: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.key_count = key_count
        self.objects = objects or {}
        self.listed_objects = listed_objects
        self.list_calls: list[dict[str, Any]] = []

    def list_objects_v2(self, **params: Any) -> dict[str, Any]:
        self.list_calls.append(params)
        if self.listed_objects is not None:
            prefix = params.get("Prefix", "")
            contents = [
                {"Key": uri.split("/", 3)[3], "Size": head.get("ContentLength", 0)}
                for uri, head in self.listed_objects.items()
                if uri.split("/", 3)[3].startswith(prefix)
            ]
            return {"KeyCount": len(contents), "Contents": contents, "IsTruncated": False}
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

    def head_object(self, **params: Any) -> dict[str, Any]:
        key = f"s3://{params['Bucket']}/{params['Key']}"
        if self.listed_objects is None or key not in self.listed_objects:
            raise RuntimeError(f"missing fake s3 head: {key}")
        return self.listed_objects[key]


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
            {
                "relative_path": "config/samples.tsv",
                "size_bytes": 21,
                "sha256": digest,
                "classification": "samples_manifest",
                "parser_relevant": True,
                "required": True,
                "metadata": {
                    "sample_names": ["HG002", "HG003"],
                    "experiment_ids": ["EXP1", "EXP2"],
                },
                "tags": ["manifest:samples", "sample:HG002", "sample:HG003"],
            },
            {
                "relative_path": "config/units.tsv",
                "size_bytes": 22,
                "sha256": digest,
                "classification": "units_manifest",
                "parser_relevant": True,
                "required": True,
                "metadata": {
                    "sample_names": ["HG002", "HG003"],
                    "experiment_ids": ["EXP1", "EXP2"],
                    "run_ids": ["RUN42"],
                },
                "tags": [
                    "experiment:EXP1",
                    "experiment:EXP2",
                    "manifest:units",
                    "sample:HG002",
                    "sample:HG003",
                ],
            },
            {
                "relative_path": "results/day/hg38_broad/crams/HG002.dmd.cram",
                "size_bytes": 17,
                "sha256": digest,
                "classification": "alignment_cram",
                "parser_relevant": False,
                "required": True,
            },
            {
                "relative_path": "results/day/hg38_broad/crams/HG002.dmd.cram.crai",
                "size_bytes": 18,
                "sha256": digest,
                "classification": "alignment_cram_index",
                "parser_relevant": False,
                "required": True,
            },
            {
                "relative_path": "results/day/hg38_broad/vcfs/HG002.sentd.vcf.gz",
                "size_bytes": 19,
                "sha256": digest,
                "classification": "variant_vcf",
                "parser_relevant": False,
                "required": True,
            },
            {
                "relative_path": "results/day/hg38_broad/vcfs/HG002.sentd.vcf.gz.tbi",
                "size_bytes": 20,
                "sha256": digest,
                "classification": "variant_vcf_index",
                "parser_relevant": False,
                "required": True,
            },
        ],
    }
    return json.dumps(payload)


def test_build_registration_requests_handles_multiple_multiqc_reports() -> None:
    digest = "c" * 64
    manifest = {
        "schema_version": "dyec.s3_export_inventory_manifest.v1",
        "manifest_checksum": "d" * 64,
        "generated_at": "2026-05-31T00:00:00Z",
        "analysis": {"genome_build": "hg38_broad"},
        "workflow": {
            "pipeline_name": "daylily-omics-analysis",
            "pipeline_version": "2.0.26",
            "git_sha": "abc123",
            "snakemake_version": "7.32.4",
            "workflow_config_hash": digest,
            "workflow_profile": "exported-s3-inventory",
        },
        "files": [
            {
                "relative_path": "config/samples.tsv",
                "size_bytes": 8,
                "sha256": digest,
                "classification": "samples_manifest",
                "parser_relevant": True,
                "required": True,
                "metadata": {
                    "sample_names": ["HG002"],
                    "experiment_ids": ["EXP1"],
                },
                "tags": ["manifest:samples", "sample:HG002"],
            },
            {
                "relative_path": "config/units.tsv",
                "size_bytes": 9,
                "sha256": digest,
                "classification": "units_manifest",
                "parser_relevant": True,
                "required": True,
                "metadata": {
                    "sample_names": ["HG002"],
                    "experiment_ids": ["EXP1"],
                    "run_ids": ["RUN1"],
                },
                "tags": ["experiment:EXP1", "manifest:units", "sample:HG002"],
            },
            {
                "relative_path": "results/runs/RUN1/run_qc/illumina/multiqc_report.html",
                "size_bytes": 10,
                "sha256": digest,
                "classification": "multiqc_html",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": (
                    "results/runs/RUN1/run_qc/illumina/multiqc_report_data/multiqc_data.json"
                ),
                "size_bytes": 11,
                "sha256": digest,
                "classification": "multiqc_data_json",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": (
                    "results/runs/RUN1/run_qc/illumina/multiqc_report_data/multiqc_general_stats.txt"
                ),
                "size_bytes": 12,
                "sha256": digest,
                "classification": "multiqc_general_stats",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": "results/runs/RUN1/bclconvert/multiqc_report.html",
                "size_bytes": 13,
                "sha256": digest,
                "classification": "multiqc_html",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": (
                    "results/runs/RUN1/bclconvert/multiqc_report_data/multiqc_data.json"
                ),
                "size_bytes": 14,
                "sha256": digest,
                "classification": "multiqc_data_json",
                "parser_relevant": True,
                "required": True,
            },
            {
                "relative_path": (
                    "results/runs/RUN1/bclconvert/multiqc_report_data/multiqc_bclconvert_demux.tsv"
                ),
                "size_bytes": 15,
                "sha256": digest,
                "classification": "multiqc_data_file",
                "parser_relevant": True,
                "required": True,
            },
        ],
    }
    command = load_repository_catalog().get_command("illumina_run_qc_bclconvert")

    requests = build_registration_requests(
        manifest=manifest,
        export_receipt={
            "status": "success",
            "analysis_dir": "ubuntu/ccv20260530r57_illumina_run_qc_bclconvert",
            "dayoa_s3_root": (
                "s3://bucket/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert/"
                "daylily-omics-analysis/"
            ),
        },
        policy=command.artifact_registration,
    )

    assert requests["analysis"]["analysis_euid"] == "ccv20260530r57_illumina_run_qc_bclconvert"
    assert requests["analysis"]["metadata"]["analysis_id"] == (
        "ccv20260530r57_illumina_run_qc_bclconvert"
    )
    assert len(requests["multiqc"]) == 2
    assert {request["report_kind"] for request in requests["multiqc"]} == {
        "bclconvert",
        "run_qc_illumina",
    }
    assert {
        request["metadata"]["data_dir_relative_path"] for request in requests["multiqc"]
    } == {
        "results/runs/RUN1/bclconvert/multiqc_report_data/",
        "results/runs/RUN1/run_qc/illumina/multiqc_report_data/",
    }
    assert len(requests["analysis"]["artifacts"]) == 8
    artifacts_by_path = {
        artifact["relative_path"]: artifact for artifact in requests["analysis"]["artifacts"]
    }
    assert artifacts_by_path["config/samples.tsv"]["metadata"]["tags"] == [
        "manifest:samples",
        "sample:HG002",
    ]


def test_registration_only_s3_inventory_requires_sha256_metadata(tmp_path, monkeypatch) -> None:
    fake = FakeFsxClient()
    prefix = "s3://bucket/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert/"
    dayoa_prefix = prefix + "daylily-omics-analysis/"
    fake_s3 = FakeS3Client(
        listed_objects={
            dayoa_prefix + ".test_data/data/ultima_run_qc/ultima_demux_summary_mqc.tsv": {
                "ContentLength": 9,
                "Metadata": {"user-agent": "aws-fsx-lustre"},
                "ETag": '"testdata"',
            },
            dayoa_prefix + "results/runs/RUN1/run_qc/illumina/multiqc_report.html": {
                "ContentLength": 10,
                "Metadata": {"user-agent": "aws-fsx-lustre"},
                "ETag": '"abc"',
            }
        }
    )
    monkeypatch.setenv("DEWEY_TOKEN", "token-1")
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(fake, s3_client=fake_s3),
    )
    command = load_repository_catalog().get_command("illumina_run_qc_bclconvert")

    rc = run_dewey_registration_for_existing_export(
        RegisterExistingExportOptions(
            source_path="/fsx/analysis_results/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert",
            destination_s3_uri=prefix,
            region="us-west-2",
            profile="prof",
            output_dir=tmp_path,
            artifact_registration_policy=command.artifact_registration,
            artifact_registration_genome=command.genome,
            artifact_registration_manifest_source="s3_inventory",
            artifact_registration_command_id=command.command_id,
            dewey_url="https://dewey.example",
            dewey_token_env="DEWEY_TOKEN",
        )
    )

    assert rc == 1
    receipt = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))[
        "fsx_export"
    ]
    assert receipt["status"] == "error"
    assert receipt["registration_only"] is True
    assert "missing SHA-256 metadata" in receipt["failure_details"]["message"]
    assert ".test_data" not in receipt["failure_details"]["message"]
    assert not (tmp_path / "dewey_registration_receipt.json").exists()


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
            "multiqc_responses": [{"artifact_set_euid": "Z-MQC-1"}],
            "analysis_request_manifest_sha256": requests["analysis"]["manifest_sha256"],
            "multiqc_request_manifest_sha256s": [
                request["manifest_sha256"] for request in requests["multiqc"]
            ],
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
    assert receipt["dewey_selected_artifact_count"] == 13
    assert receipt["dewey_multiqc_artifact_set_count"] == 1
    assert (tmp_path / "dewey_registration_receipt.json").is_file()
    assert captured["dewey_url"] == "https://dewey.example"
    assert captured["token"] == "token-1"
    assert captured["requests"]["analysis"]["analysis_euid"] == "illumina_run_qc"
    assert captured["requests"]["analysis"]["artifacts"][0]["storage_uri"].startswith(
        "s3://bucket/analysis_results/johnm/illumina_run_qc/daylily-omics-analysis/"
    )
    artifacts_by_path = {
        artifact["relative_path"]: artifact
        for artifact in captured["requests"]["analysis"]["artifacts"]
    }
    assert artifacts_by_path["config/units.tsv"]["metadata"]["tags"] == [
        "experiment:EXP1",
        "experiment:EXP2",
        "manifest:units",
        "sample:HG002",
        "sample:HG003",
    ]


def test_register_exported_analysis_directory_links_posts_external_object_and_relations(
    monkeypatch,
) -> None:
    import daylily_ec.workflow.dewey_registration as dewey_registration

    calls: list[dict[str, Any]] = []

    def fake_post_json(
        url: str,
        token: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        calls.append(
            {
                "url": url,
                "token": token,
                "payload": payload,
                "idempotency_key": idempotency_key,
            }
        )
        if url.endswith("/api/v1/external-objects"):
            object_count = sum(
                1 for call in calls if call["url"].endswith("/api/v1/external-objects")
            )
            return {"external_object_euid": f"Z-EXT-{object_count}"}
        return {"external_object_relation_euid": f"Z-REL-{len(calls)}"}

    monkeypatch.setattr(dewey_registration, "post_json", fake_post_json)

    receipt = register_exported_analysis_directory_links(
        dewey_url="https://dewey.example",
        token="token-1",
        export_receipt={
            "status": "success",
            "cluster_name": "cluster-a",
            "region": "us-west-2",
            "analysis_dir": "ubuntu/M-RGX-9S3G",
            "source_path": "/fsx/analysis_results/ubuntu/M-RGX-9S3G",
            "destination_s3_uri": "s3://seq/derived/analysis_results/cluster-a/M-RGX-9S3G/",
            "dayoa_s3_root": (
                "s3://seq/derived/analysis_results/cluster-a/M-RGX-9S3G/"
                "daylily-omics-analysis/"
            ),
        },
        dewey_receipt={"analysis_response": {"artifact_set_euid": "Z-ASET-1"}},
        external_object_id="M-RGX-9S3G",
        run_artifact_euid="M-DGX-9SD7",
        ursa_analysis_euid="M-RGX-9S3G",
    )

    assert receipt["external_object_response"]["external_object_euid"] == "Z-EXT-1"
    assert len(calls) == 5
    external_call = calls[0]
    assert external_call["url"] == "https://dewey.example/api/v1/external-objects"
    assert external_call["token"] == "token-1"
    assert external_call["idempotency_key"].startswith(
        "dyec-analysis-directory-external-object-"
    )
    assert external_call["payload"] == {
        "external_system": "dyec",
        "external_object_type": "dayoa_analysis_directory",
        "external_object_id": "M-RGX-9S3G",
        "external_uri": (
            "s3://seq/derived/analysis_results/cluster-a/M-RGX-9S3G/"
            "daylily-omics-analysis/"
        ),
        "metadata": {
            "source": "dyec export",
            "cluster_name": "cluster-a",
            "region": "us-west-2",
            "analysis_dir": "ubuntu/M-RGX-9S3G",
            "source_path": "/fsx/analysis_results/ubuntu/M-RGX-9S3G",
            "destination_s3_uri": "s3://seq/derived/analysis_results/cluster-a/M-RGX-9S3G/",
            "dayoa_s3_root": (
                "s3://seq/derived/analysis_results/cluster-a/M-RGX-9S3G/"
                "daylily-omics-analysis/"
            ),
            "dewey_analysis_artifact_set_euid": "Z-ASET-1",
            "run_artifact_euid": "M-DGX-9SD7",
            "ursa_analysis_euid": "M-RGX-9S3G",
        },
    }
    ursa_external_call = calls[1]
    assert ursa_external_call["payload"] == {
        "external_system": "ursa",
        "external_object_type": "analysis_job",
        "external_object_id": "M-RGX-9S3G",
        "external_uri": None,
        "metadata": external_call["payload"]["metadata"],
    }
    relation_targets = [call["payload"] for call in calls[2:]]
    assert relation_targets == [
        {
            "target_type": "artifact_set",
            "target_euid": "Z-ASET-1",
            "external_object_euid": "Z-EXT-1",
            "relation_type": "dyec_exported_analysis_directory",
            "metadata": {**external_call["payload"]["metadata"], "target_label": "analysis_artifact_set"},
        },
        {
            "target_type": "artifact",
            "target_euid": "M-DGX-9SD7",
            "external_object_euid": "Z-EXT-1",
            "relation_type": "dyec_analysis_directory_for_run",
            "metadata": {**external_call["payload"]["metadata"], "target_label": "run_artifact"},
        },
        {
            "target_type": "artifact_set",
            "target_euid": "Z-ASET-1",
            "external_object_euid": "Z-EXT-2",
            "relation_type": "ursa_analysis_job",
            "metadata": {**external_call["payload"]["metadata"], "target_label": "ursa_analysis"},
        },
    ]
    assert all(
        call["idempotency_key"].startswith("dyec-analysis-directory-external-relation-")
        or call["idempotency_key"].startswith("dyec-ursa-analysis-external-")
        for call in calls[1:]
    )


def test_run_export_workflow_links_dewey_analysis_directory_after_registration(
    tmp_path, monkeypatch
) -> None:
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
        _ = dewey_url, token, requests
        return {
            "analysis_response": {"artifact_set_euid": "Z-ASET-1"},
            "multiqc_responses": [{"artifact_set_euid": "Z-MQC-1"}],
        }

    def fake_links(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"external_object_response": {"external_object_euid": "Z-EXT-1"}, "relations": []}

    monkeypatch.setattr(
        "daylily_ec.workflow.dewey_registration.register_with_dewey",
        fake_register_with_dewey,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.dewey_registration.register_exported_analysis_directory_links",
        fake_links,
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
            dewey_analysis_dir_external_object_id="M-RGX-9S3G",
            dewey_run_artifact_euid="M-DGX-9SD7",
            dewey_ursa_analysis_euid="M-RGX-9S3G",
        )
    )

    assert rc == 0
    assert captured["dewey_url"] == "https://dewey.example"
    assert captured["token"] == "token-1"
    assert captured["external_object_id"] == "M-RGX-9S3G"
    assert captured["run_artifact_euid"] == "M-DGX-9SD7"
    assert captured["ursa_analysis_euid"] == "M-RGX-9S3G"
    payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
    receipt = payload["fsx_export"]
    assert receipt["dewey_registration_status"] == "success"
    assert receipt["dewey_analysis_directory_link_status"] == "success"
    dewey_receipt = json.loads(
        (tmp_path / "dewey_registration_receipt.json").read_text(encoding="utf-8")
    )
    assert dewey_receipt["analysis_directory_links"]["external_object_response"] == {
        "external_object_euid": "Z-EXT-1"
    }


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


def test_cli_exports_register_dewey_passes_existing_export_options(tmp_path, monkeypatch):
    from daylily_ec.cli import app

    _activate_dayec_runtime(monkeypatch)
    monkeypatch.setenv("DEWEY_TOKEN", "token-1")
    with (
        patch("daylily_ec.workflow.export_data.configure_logging") as mock_logging,
        patch(
            "daylily_ec.workflow.export_data.run_dewey_registration_for_existing_export",
            return_value=0,
        ) as mock_run,
    ):
        result = runner.invoke(
            app,
            [
                "exports",
                "register-dewey",
                "--source-path",
                "/fsx/analysis_results/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert",
                "--destination-s3-uri",
                "s3://bucket/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert/",
                "--region",
                "us-west-2",
                "--output-dir",
                str(tmp_path),
                "--artifact-registration-command-id",
                "illumina_run_qc_bclconvert",
                "--manifest-source",
                "s3-inventory",
                "--dewey-url",
                "https://dewey.example",
                "--dewey-token-env",
                "DEWEY_TOKEN",
                "--profile",
                "prof",
                "--verbose",
            ],
        )

    assert result.exit_code == 0
    mock_logging.assert_called_once_with(True)
    options = mock_run.call_args.args[0]
    assert options.source_path == (
        "/fsx/analysis_results/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert"
    )
    assert (
        options.destination_s3_uri
        == "s3://bucket/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert/"
    )
    assert options.artifact_registration_command_id == "illumina_run_qc_bclconvert"
    assert options.artifact_registration_manifest_source == "s3_inventory"
    assert options.dewey_url == "https://dewey.example"
