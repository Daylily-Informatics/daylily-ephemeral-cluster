"""Provider-neutral tests for immutable analysis-directory FSx exports."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from daylily_ec.workflow.export_data import (
    RUNTIME_ASSET_EXPORT_KIND,
    SHARED_REFERENCE_EXPORT_KIND,
    ExportError,
    ExportOptions,
    analysis_dir_from_source_path,
    analysis_headnode_path,
    attach_export_dra,
    cleanup_exported_analysis,
    clone_status_evidence_s3_uri,
    inspect_completed_export,
    normalize_export_source_path,
    preflight_export,
    resolve_launch_export_destination_s3_uri,
    run_export_task,
    run_export_workflow,
    validate_export_destination_s3_uri,
    validate_no_overlapping_export_dra,
    validate_runtime_asset_export_source,
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


class FakeReferenceFsxClient(FakeFsxClient):
    def describe_data_repository_associations(self, **_kwargs):
        return {
            "Associations": [
                {
                    "AssociationId": "dra-reference",
                    "FileSystemId": "fs-123",
                    "FileSystemPath": "/references/",
                    "DataRepositoryPath": "s3://references/",
                    "Lifecycle": "AVAILABLE",
                }
            ]
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
        if kwargs.get("MaxKeys") == 1:
            return {"KeyCount": self.key_count}
        return {
            "Contents": [{"Key": f"{kwargs['Prefix']}result.txt", "Size": 1}],
            "IsTruncated": False,
        }

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


def test_export_preflight_is_read_only_and_exact() -> None:
    fsx = FakeFsxClient()
    s3 = EmptyS3Client()
    payload = preflight_export(
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        source_path="/fsx/analysis_results/cluster-a/run-a",
        destination_s3_uri="s3://bucket/derived/cluster-a/run-a/",
        region="us-west-2",
        profile="lsmc",
        fsx_client=fsx,
        s3_client=s3,
    )

    assert payload == {
        "schema_version": "dyec.exports.preflight.v1",
        "ok": True,
        "operation": "preflight",
        "read_only": True,
        "mutation_attempted": False,
        "cluster_name": "cluster-a",
        "region": "us-west-2",
        "fsx_file_system_id": "fs-123",
        "source_path": "/analysis_results/cluster-a/run-a/",
        "headnode_path": "/fsx/analysis_results/cluster-a/run-a/",
        "destination_s3_uri": "s3://bucket/derived/cluster-a/run-a/",
        "destination_analysis_id": None,
        "destination_empty": True,
        "overlapping_dra": False,
        "fsx_dra_compatible": True,
    }
    assert fsx.created_association is None
    assert fsx.created_task is None
    assert fsx.deleted_association is None


def test_shared_reference_preflight_is_read_only_and_exact() -> None:
    fsx = FakeReferenceFsxClient()
    s3 = EmptyS3Client()
    payload = preflight_export(
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        source_path="/fsx/analysis_results/team/ganon2_ref",
        destination_s3_uri="s3://references/genomic_annotations/ganon2/ganon2_ref/",
        region="us-west-2",
        profile="lsmc",
        export_kind=SHARED_REFERENCE_EXPORT_KIND,
        fsx_client=fsx,
        s3_client=s3,
    )

    assert payload["export_kind"] == SHARED_REFERENCE_EXPORT_KIND
    assert payload["source_path"] == "/analysis_results/team/ganon2_ref/"
    assert payload["destination_s3_uri"] == (
        "s3://references/genomic_annotations/ganon2/ganon2_ref/"
    )
    assert payload["destination_empty"] is True
    assert payload["mutation_attempted"] is False
    assert payload["existing_reference_dra"] == {
        "association_id": "dra-reference",
        "association_lifecycle": "AVAILABLE",
        "association_file_system_path": "/references/",
        "association_data_repository_path": "s3://references/",
        "target_file_system_path": "/references/genomic_annotations/ganon2/ganon2_ref/",
        "target_headnode_path": "/fsx/references/genomic_annotations/ganon2/ganon2_ref/",
    }
    assert fsx.created_association is None
    assert fsx.created_task is None
    assert fsx.deleted_association is None


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


def test_runtime_asset_export_requires_exact_aligned_source() -> None:
    assert validate_runtime_asset_export_source(
        "/fsx/analysis_results/runtime_assets/cached_envs/"
        "sentieon-genomics-202503.04"
    ) == (
        "/analysis_results/runtime_assets/cached_envs/"
        "sentieon-genomics-202503.04/"
    )
    with pytest.raises(ExportError, match="require exactly"):
        validate_runtime_asset_export_source(
            "/fsx/analysis_results/user/run/sentieon-genomics-202503.04"
        )


def test_runtime_asset_export_requires_standalone_bucket_layout() -> None:
    source = (
        "/fsx/analysis_results/runtime_assets/cached_envs/"
        "sentieon-genomics-202503.04"
    )
    assert validate_export_destination_s3_uri(
        "s3://bucket/cached_envs/sentieon-genomics-202503.04/",
        source_path=source,
        cluster_name="cluster-a",
    ) == "s3://bucket/cached_envs/sentieon-genomics-202503.04/"
    with pytest.raises(ExportError, match="must end with"):
        validate_export_destination_s3_uri(
            "s3://bucket/runtime_assets/cached_envs/"
            "sentieon-genomics-202503.04/",
            source_path=source,
            cluster_name="cluster-a",
        )


def test_runtime_asset_export_uses_dra_without_clone_evidence(
    tmp_path, monkeypatch
) -> None:
    client = FakeFsxClient()
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(client),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="cluster-a",
            fsx_file_system_id="fs-123",
            source_path=(
                "/fsx/analysis_results/runtime_assets/cached_envs/"
                "sentieon-genomics-202503.04"
            ),
            destination_s3_uri=(
                "s3://bucket/cached_envs/"
                "sentieon-genomics-202503.04/"
            ),
            region="us-west-2",
            profile="profile",
            output_dir=tmp_path,
            wait=False,
            export_kind=RUNTIME_ASSET_EXPORT_KIND,
        )
    )

    assert rc == 0
    receipt = yaml.safe_load(
        (tmp_path / "fsx_export.yaml").read_text(encoding="utf-8")
    )["fsx_export"]
    assert receipt["export_kind"] == "runtime_asset"
    assert "clone_status_v2_evidence" not in receipt
    assert "dayoa_analysis_root" not in receipt
    assert client.created_association is not None


def test_runtime_asset_export_forbids_fsx_deletion(tmp_path) -> None:
    rc = run_export_workflow(
        ExportOptions(
            cluster_name="cluster-a",
            fsx_file_system_id="fs-123",
            source_path=(
                "/fsx/analysis_results/runtime_assets/cached_envs/"
                "sentieon-genomics-202503.04"
            ),
            destination_s3_uri=(
                "s3://bucket/cached_envs/"
                "sentieon-genomics-202503.04/"
            ),
            region="us-west-2",
            profile="profile",
            output_dir=tmp_path,
            delete_data_in_file_system=True,
            export_kind=RUNTIME_ASSET_EXPORT_KIND,
        )
    )
    assert rc == 1
    receipt = yaml.safe_load(
        (tmp_path / "fsx_export.yaml").read_text(encoding="utf-8")
    )["fsx_export"]
    assert receipt["phase"] == "validate"
    assert "must retain staged FSx data" in receipt["failure_details"]["message"]


def test_shared_reference_destination_binds_exact_source_leaf() -> None:
    source = "/fsx/analysis_results/team/ganon2_blood_oral_ref_v1"
    destination = (
        "s3://references/genomic_annotations/ganon2/"
        "ganon2_blood_oral_ref_v1/"
    )

    assert validate_export_destination_s3_uri(
        destination,
        source_path=source,
        export_kind=SHARED_REFERENCE_EXPORT_KIND,
    ) == destination
    with pytest.raises(ExportError, match="leaf must exactly match"):
        validate_export_destination_s3_uri(
            "s3://references/genomic_annotations/ganon2/wrong/",
            source_path=source,
            export_kind=SHARED_REFERENCE_EXPORT_KIND,
        )
    with pytest.raises(ExportError, match="complete top-level"):
        validate_export_destination_s3_uri(
            destination,
            source_path=f"{source}/nested",
            export_kind=SHARED_REFERENCE_EXPORT_KIND,
        )


def test_shared_reference_export_uses_dra_and_verifies_objects(
    tmp_path, monkeypatch
) -> None:
    client = FakeReferenceFsxClient()
    s3 = FakeS3Client(_exported_status_v2())
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data._create_session",
        lambda _region, _profile: FakeSession(client, s3),
    )
    monkeypatch.setattr(
        "daylily_ec.aws.ssm.resolve_headnode_instance_id",
        lambda *_args, **_kwargs: SimpleNamespace(instance_id="i-head"),
    )
    monkeypatch.setattr(
        "daylily_ec.aws.ssm.wait_for_ssm_online",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "daylily_ec.aws.ssm.run_shell",
        lambda *_args, **_kwargs: SimpleNamespace(
            command_id="cmd-stage",
            stdout=(
                "DYEC_SHARED_REFERENCE_STAGE\t"
                "/fsx/references/genomic_annotations/ganon2/ganon2_blood_oral_ref_v1"
                "\t100\t10\n"
            ),
        ),
    )

    rc = run_export_workflow(
        ExportOptions(
            cluster_name="cluster-a",
            fsx_file_system_id="fs-123",
            source_path="/fsx/analysis_results/team/ganon2_blood_oral_ref_v1",
            destination_s3_uri=(
                "s3://references/genomic_annotations/ganon2/"
                "ganon2_blood_oral_ref_v1/"
            ),
            region="us-west-2",
            profile="profile",
            output_dir=tmp_path,
            wait=False,
            export_kind=SHARED_REFERENCE_EXPORT_KIND,
        )
    )

    assert rc == 0
    receipt = yaml.safe_load(
        (tmp_path / "fsx_export.yaml").read_text(encoding="utf-8")
    )["fsx_export"]
    assert receipt["export_kind"] == SHARED_REFERENCE_EXPORT_KIND
    assert receipt["destination_s3_evidence"]["verified"] is True
    assert "clone_status_v2_evidence" not in receipt
    assert receipt["existing_dra_preserved"] is True
    assert receipt["source_fsx_preserved"] is True
    assert receipt["reference_fsx_present"] is True
    assert client.created_association is None
    assert client.deleted_association is None
    assert client.created_task is not None
    assert client.created_task["Paths"] == [
        "/references/genomic_annotations/ganon2/ganon2_blood_oral_ref_v1/"
    ]


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


def test_inspect_completed_export_proves_task_detach_and_s3_without_mutation(
    monkeypatch,
) -> None:
    source = "/analysis_results/ursa-M-RGX-JJG9/M-RGX-JK33/"
    destination = (
        "s3://bucket/derived/ursa-clusters/ursa-m-rgx-j2gs/"
        "analysis_results/M-RGX-JK33/"
    )
    report_path = (
        f"{destination}_daylily_monitor/fsx-export/"
        "20260822T011000Z/export-report/"
    )

    class InspectionFsxClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def describe_data_repository_tasks(self, **kwargs):
            self.calls.append(("describe_data_repository_tasks", kwargs))
            return {
                "DataRepositoryTasks": [
                    {
                        "TaskId": "task-1",
                        "Lifecycle": "SUCCEEDED",
                        "Type": "EXPORT_TO_REPOSITORY",
                        "CreationTime": datetime(2026, 8, 22, 1, 10, tzinfo=timezone.utc),
                        "EndTime": datetime(2026, 8, 22, 1, 20, tzinfo=timezone.utc),
                        "FileSystemId": "fs-123",
                        "Paths": [source],
                        "Report": {
                            "Enabled": True,
                            "Path": report_path,
                            "Format": "REPORT_CSV_20191124",
                            "Scope": "FAILED_FILES_ONLY",
                        },
                    }
                ]
            }

        def describe_data_repository_associations(self, **kwargs):
            self.calls.append(("describe_data_repository_associations", kwargs))
            return {"Associations": []}

    def event(
        *,
        name: str,
        event_time: str,
        request: dict[str, object],
        response: dict[str, object],
    ) -> dict[str, object]:
        event_id = f"event-{name}"
        return {
            "EventId": event_id,
            "CloudTrailEvent": json.dumps(
                {
                    "eventSource": "fsx.amazonaws.com",
                    "eventName": name,
                    "eventTime": event_time,
                    "eventID": event_id,
                    "requestID": f"request-{name}",
                    "recipientAccountId": "108782052779",
                    "userIdentity": {"principalId": "role:ursa"},
                    "requestParameters": request,
                    "responseElements": response,
                }
            ),
        }

    events = {
        "CreateDataRepositoryAssociation": event(
            name="CreateDataRepositoryAssociation",
            event_time="2026-08-22T01:05:00Z",
            request={
                "fileSystemId": "fs-123",
                "fileSystemPath": source,
                "dataRepositoryPath": destination,
                "batchImportMetaDataOnCreate": False,
                "tags": [
                    {"key": "lsmc:purpose", "value": "output-export"},
                    {"key": "Name", "value": "ursa-M-RGX-JJG9/M-RGX-JK33"},
                ],
            },
            response={"association": {"associationId": "dra-export"}},
        ),
        "CreateDataRepositoryTask": event(
            name="CreateDataRepositoryTask",
            event_time="2026-08-22T01:10:00Z",
            request={
                "fileSystemId": "fs-123",
                "type": "EXPORT_TO_REPOSITORY",
                "paths": [source],
                "report": {"path": report_path},
            },
            response={"dataRepositoryTask": {"taskId": "task-1"}},
        ),
        "DeleteDataRepositoryAssociation": event(
            name="DeleteDataRepositoryAssociation",
            event_time="2026-08-22T01:21:00Z",
            request={
                "associationId": "dra-export",
                "deleteDataInFileSystem": False,
            },
            response={"association": {"associationId": "dra-export"}},
        ),
    }

    class InspectionCloudTrailClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def lookup_events(self, **kwargs):
            self.calls.append(kwargs)
            event_name = kwargs["LookupAttributes"][0]["AttributeValue"]
            return {"Events": [events[event_name]]}

    fsx = InspectionFsxClient()
    cloudtrail = InspectionCloudTrailClient()
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data.verify_exported_clone_status_v2_evidence",
        lambda *_args, **_kwargs: {
            "required": True,
            "verified": True,
            "schema_version": "daylily.analysis_status.v2",
            "s3_uri": f"{destination}daylily-omics-analysis/status.json",
            "attempt_count": 1,
            "latest_attempt_id": "attempt-1",
        },
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data.verify_exported_destination_evidence",
        lambda *_args, **_kwargs: {
            "required": True,
            "verified": True,
            "schema_version": "dyec.export.destination_evidence.v1",
            "s3_uri": destination,
            "object_count": 1,
            "total_bytes": 1,
            "list_request_count": 1,
        },
    )

    payload = inspect_completed_export(
        cluster_name="ursa-m-rgx-j2gs",
        fsx_file_system_id="fs-123",
        source_path=f"/fsx{source}",
        destination_s3_uri=destination,
        destination_analysis_id="M-RGX-JK33",
        started_after="2026-08-22T01:00:00Z",
        started_before="2026-08-22T01:30:00Z",
        region="us-west-2",
        profile="lsmc",
        fsx_client=fsx,
        cloudtrail_client=cloudtrail,
        s3_client=object(),
    )

    assert payload["schema_version"] == "dyec.exports.inspect.v1"
    assert payload["read_only"] is True
    assert payload["task_id"] == "task-1"
    assert payload["association_id"] == "dra-export"
    assert payload["detached"] is True
    assert payload["delete_data_in_file_system"] is False
    assert [name for name, _kwargs in fsx.calls] == [
        "describe_data_repository_tasks",
        "describe_data_repository_associations",
    ]
    assert len(cloudtrail.calls) == 3


def test_exports_inspect_emits_current_read_only_receipt(monkeypatch) -> None:
    from daylily_ec.cli import app

    observed: dict[str, object] = {}

    def fake_inspect(**kwargs):
        observed.update(kwargs)
        return {
            "schema_version": "dyec.exports.inspect.v1",
            "ok": True,
            "operation": "inspect",
            "read_only": True,
            "task_id": "task-1",
            "destination_s3_uri": "s3://bucket/derived/cluster/analysis_results/run/",
        }

    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data.inspect_completed_export",
        fake_inspect,
    )
    result = runner.invoke(
        app,
        [
            "--json",
            "exports",
            "inspect",
            "--cluster",
            "cluster-a",
            "--fsx-file-system-id",
            "fs-123",
            "--source-path",
            "/fsx/analysis_results/ursa-run/execution",
            "--destination-s3-uri",
            "s3://bucket/derived/cluster/analysis_results/run/",
            "--destination-analysis-id",
            "run",
            "--started-after",
            "2026-08-22T01:00:00Z",
            "--started-before",
            "2026-08-22T01:30:00Z",
            "--region",
            "us-west-2",
            "--profile",
            "lsmc",
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = yaml.safe_load(result.stdout)
    assert payload["schema_version"] == "dyec.exports.inspect.v1"
    assert payload["read_only"] is True
    assert observed["fsx_file_system_id"] == "fs-123"


def test_exports_preflight_emits_read_only_receipt(monkeypatch) -> None:
    from daylily_ec.cli import app

    observed: dict[str, object] = {}

    def fake_preflight(**kwargs):
        observed.update(kwargs)
        return {
            "schema_version": "dyec.exports.preflight.v1",
            "ok": True,
            "operation": "preflight",
            "read_only": True,
            "mutation_attempted": False,
            "headnode_path": "/fsx/analysis_results/cluster-a/run-a/",
            "destination_s3_uri": "s3://bucket/derived/cluster-a/run-a/",
            "destination_empty": True,
            "overlapping_dra": False,
        }

    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data.preflight_export",
        fake_preflight,
    )
    result = runner.invoke(
        app,
        [
            "--json",
            "exports",
            "preflight",
            "--cluster",
            "cluster-a",
            "--fsx-file-system-id",
            "fs-123",
            "--source-path",
            "/fsx/analysis_results/cluster-a/run-a",
            "--destination-s3-uri",
            "s3://bucket/derived/cluster-a/run-a/",
            "--region",
            "us-west-2",
            "--profile",
            "lsmc",
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = yaml.safe_load(result.stdout)
    assert payload["schema_version"] == "dyec.exports.preflight.v1"
    assert payload["read_only"] is True
    assert payload["mutation_attempted"] is False
    assert observed["fsx_file_system_id"] == "fs-123"
    assert observed["export_kind"] == "analysis"


def test_exports_preflight_accepts_shared_reference_contract(monkeypatch) -> None:
    from daylily_ec.cli import app

    observed: dict[str, object] = {}

    def fake_preflight(**kwargs):
        observed.update(kwargs)
        return {
            "schema_version": "dyec.exports.preflight.v1",
            "ok": True,
            "operation": "preflight",
            "read_only": True,
            "mutation_attempted": False,
            "headnode_path": "/fsx/analysis_results/team/ganon2_ref/",
            "destination_s3_uri": "s3://references/genomic_annotations/ganon2/ganon2_ref/",
            "destination_empty": True,
            "overlapping_dra": False,
            "export_kind": "shared_reference",
        }

    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    monkeypatch.setattr(
        "daylily_ec.workflow.export_data.preflight_export",
        fake_preflight,
    )
    result = runner.invoke(
        app,
        [
            "--json",
            "exports",
            "preflight",
            "--export-kind",
            "shared-reference",
            "--cluster",
            "cluster-a",
            "--fsx-file-system-id",
            "fs-123",
            "--source-path",
            "/fsx/analysis_results/team/ganon2_ref",
            "--destination-s3-uri",
            "s3://references/genomic_annotations/ganon2/ganon2_ref/",
            "--region",
            "us-west-2",
            "--profile",
            "lsmc",
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = yaml.safe_load(result.stdout)
    assert payload["export_kind"] == "shared_reference"
    assert observed["export_kind"] == "shared_reference"


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


def test_cli_export_accepts_runtime_asset_contract(tmp_path, monkeypatch) -> None:
    from daylily_ec.cli import app

    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    with (
        patch("daylily_ec.workflow.export_data.configure_logging"),
        patch(
            "daylily_ec.workflow.export_data.run_export_workflow", return_value=0
        ) as run,
    ):
        result = runner.invoke(
            app,
            [
                "export",
                "--cluster-name",
                "cluster-a",
                "--source-path",
                "/fsx/analysis_results/runtime_assets/cached_envs/runtime-1",
                "--destination-s3-uri",
                "s3://bucket/cached_envs/runtime-1/",
                "--region",
                "us-west-2",
                "--output-dir",
                str(tmp_path),
                "--export-kind",
                "runtime-asset",
            ],
        )
    assert result.exit_code == 0, result.output
    assert run.call_args.args[0].export_kind == RUNTIME_ASSET_EXPORT_KIND


def test_cli_export_accepts_shared_reference_contract(tmp_path, monkeypatch) -> None:
    from daylily_ec.cli import app

    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    with (
        patch("daylily_ec.workflow.export_data.configure_logging"),
        patch(
            "daylily_ec.workflow.export_data.run_export_workflow", return_value=0
        ) as run,
    ):
        result = runner.invoke(
            app,
            [
                "export",
                "--cluster-name",
                "cluster-a",
                "--source-path",
                "/fsx/analysis_results/team/ganon2_blood_oral_ref_v1",
                "--destination-s3-uri",
                "s3://references/genomic_annotations/ganon2/ganon2_blood_oral_ref_v1/",
                "--region",
                "us-west-2",
                "--output-dir",
                str(tmp_path),
                "--export-kind",
                "shared-reference",
            ],
        )
    assert result.exit_code == 0, result.output
    assert run.call_args.args[0].export_kind == SHARED_REFERENCE_EXPORT_KIND


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
