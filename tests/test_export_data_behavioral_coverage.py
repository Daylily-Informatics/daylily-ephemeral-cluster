"""Behavioral validation and recovery coverage for export-data helpers."""

from __future__ import annotations

import base64
import hashlib
import io
import pytest
from botocore.exceptions import ClientError

import daylily_ec.workflow.export_data as e

SOURCE = "/analysis_results/entity/analysis/"
DEST = "s3://bucket/root/entity/analysis/"


def _client_error(code="Denied"):
    return ClientError({"Error": {"Code": code, "Message": code}}, "operation")


@pytest.mark.parametrize(
    "source",
    [
        "",
        "/fsx/data/a",
        "/fsx/run_dir_mounts/a",
        "/fsx/references/a",
        "/fsx/control_data/a",
        "/fsx/staging/a",
        "/fsx/exports/a",
        "/fsx/unknown/a",
        "/run_dir_mounts/a",
        "/data/a",
        "/references/a",
        "/control_data/a",
        "/staging/a",
        "/exports/a",
        "relative/a",
        "/analysis_results/entity/analysis/extra",
    ],
)
def test_export_source_validation_rejects_non_analysis_namespaces(source):
    with pytest.raises(e.ExportError):
        e.normalize_export_source_path(source)


def test_session_source_and_destination_resolution(monkeypatch):
    seen = []
    monkeypatch.setattr(e.boto3, "Session", lambda **kwargs: seen.append(kwargs) or kwargs)
    assert e._create_session("us-west-2", "lsmc")["profile_name"] == "lsmc"
    assert e._create_session("us-west-2", None) == {"region_name": "us-west-2"}
    assert e.normalize_export_source_path("/fsx/analysis_results/entity/analysis") == SOURCE
    assert e.analysis_headnode_path(SOURCE).endswith("entity/analysis/")
    assert e.analysis_dir_from_source_path(SOURCE) == "entity/analysis"
    with pytest.raises(e.ExportError, match="must end"):
        e.validate_export_destination_s3_uri("s3://bucket/wrong/", source_path=SOURCE)
    with pytest.raises(e.ExportError, match="--cluster is required"):
        e.resolve_launch_export_destination_s3_uri("s3://bucket/root/", source_path=SOURCE)
    assert e.resolve_launch_export_destination_s3_uri(
        "s3://bucket/root/", source_path=SOURCE, cluster_name="cluster"
    ).endswith("cluster/analysis/")


class _ListClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {}
        self.error = error

    def list_objects_v2(self, **_kwargs):
        if self.error:
            raise self.error
        return self.payload


def test_destination_empty_check_wraps_aws_and_rejects_existing_objects():
    with pytest.raises(e.ExportError, match="Unable to inspect"):
        e.validate_s3_destination_prefix_empty(
            _ListClient(error=_client_error()), DEST, source_path=SOURCE
        )
    with pytest.raises(e.ExportError, match="not empty"):
        e.validate_s3_destination_prefix_empty(
            _ListClient({"KeyCount": 1}), DEST, source_path=SOURCE
        )
    assert e.validate_s3_destination_prefix_empty(_ListClient(), DEST, source_path=SOURCE) == DEST


def test_fsx_resolution_and_overlap_inspection(monkeypatch):
    assert e.resolve_export_fsx_id(object(), cluster_name=None, fsx_file_system_id="fs-1") == "fs-1"
    with pytest.raises(e.ExportError, match="Provide --cluster"):
        e.resolve_export_fsx_id(object(), cluster_name=None, fsx_file_system_id=None)

    monkeypatch.setattr(
        e,
        "describe_data_repository_associations",
        lambda *a, **k: [
            {"Lifecycle": "FAILED", "FileSystemPath": SOURCE},
            {"Lifecycle": "AVAILABLE", "FileSystemPath": SOURCE, "AssociationId": "dra-1"},
        ],
    )
    with pytest.raises(e.ExportError, match="overlaps"):
        e.validate_no_overlapping_export_dra(
            object(), fsx_file_system_id="fs-1", source_path=SOURCE
        )
    monkeypatch.setattr(
        e,
        "describe_data_repository_associations",
        lambda *a, **k: (_ for _ in ()).throw(_client_error()),
    )
    with pytest.raises(e.ExportError, match="Unable to inspect existing"):
        e.validate_no_overlapping_export_dra(
            object(), fsx_file_system_id="fs-1", source_path=SOURCE
        )


class _TaskClient:
    def __init__(self, create=None, descriptions=None):
        self.create = create
        self.descriptions = iter(descriptions or [])

    def create_data_repository_task(self, **_kwargs):
        if isinstance(self.create, Exception):
            raise self.create
        return self.create or {}

    def describe_data_repository_tasks(self, **_kwargs):
        result = next(self.descriptions)
        if isinstance(result, Exception):
            raise result
        return result


def test_export_task_creation_and_wait_recovery(monkeypatch):
    with pytest.raises(e.ExportError, match="Unable to start"):
        e.run_export_task(
            fsx_file_system_id="fs-1",
            source_path=SOURCE,
            destination_s3_uri=DEST,
            cluster_name=None,
            wait=False,
            timeout_seconds=1,
            fsx_client=_TaskClient(create=_client_error()),
        )
    with pytest.raises(e.ExportError, match="did not return a task id"):
        e.run_export_task(
            fsx_file_system_id="fs-1",
            source_path=SOURCE,
            destination_s3_uri=DEST,
            cluster_name=None,
            wait=False,
            timeout_seconds=1,
            fsx_client=_TaskClient(),
        )
    result = e.run_export_task(
        fsx_file_system_id="fs-1",
        source_path=SOURCE,
        destination_s3_uri=DEST,
        cluster_name=None,
        wait=False,
        timeout_seconds=1,
        fsx_client=_TaskClient(
            create={"DataRepositoryTask": {"TaskId": "task", "Lifecycle": "PENDING"}}
        ),
    )
    assert result["task_id"] == "task"

    with pytest.raises(e.ExportError, match="Unable to describe"):
        e.await_export_task(_TaskClient(descriptions=[_client_error()]), "task", timeout_seconds=1)
    with pytest.raises(e.ExportError, match="Unable to locate"):
        e.await_export_task(_TaskClient(descriptions=[{}]), "task", timeout_seconds=1)
    monkeypatch.setattr(e.time, "time", lambda: 10)
    with pytest.raises(e.ExportError, match="Timed out"):
        e.await_export_task(
            _TaskClient(descriptions=[{"DataRepositoryTasks": [{"Lifecycle": "PENDING"}]}]),
            "task",
            timeout_seconds=0,
        )
    assert (
        e.await_export_task(
            _TaskClient(descriptions=[{"DataRepositoryTasks": [{"Lifecycle": "SUCCEEDED"}]}]),
            "task",
            timeout_seconds=1,
        )["Lifecycle"]
        == "SUCCEEDED"
    )


class _DetachClient:
    def __init__(self, result):
        self.result = result

    def delete_data_repository_association(self, **_kwargs):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_detach_allows_absent_but_wraps_other_errors():
    absent = e.detach_export_dra(
        association_id="dra",
        region="us-west-2",
        profile=None,
        wait=False,
        timeout_seconds=1,
        fsx_client=_DetachClient(_client_error("DataRepositoryAssociationNotFound")),
        allow_absent=True,
    )
    assert absent["detach_absent"] is True
    with pytest.raises(e.ExportError, match="Unable to detach"):
        e.detach_export_dra(
            association_id="dra",
            region="us-west-2",
            profile=None,
            wait=False,
            timeout_seconds=1,
            fsx_client=_DetachClient(_client_error()),
            allow_absent=False,
        )


class _Body:
    def __init__(self, data: bytes):
        self._io = io.BytesIO(data)
        self.closed = False

    def read(self, size=-1):
        return self._io.read(size)

    def close(self):
        self.closed = True


def test_s3_json_listing_hash_and_text_failure_contracts():
    with pytest.raises(e.ExportError, match="must use s3"):
        e._read_s3_json(object(), "https://bucket/key")
    with pytest.raises(e.ExportError, match="must use s3"):
        e._s3_parts("https://bucket/key")

    class JsonClient:
        def get_object(self, **_kwargs):
            return {"Body": _Body(b"[]")}

    with pytest.raises(e.ExportError, match="must be an object"):
        e._read_s3_json(JsonClient(), "s3://bucket/key")

    responses = iter(
        [
            {"Contents": [{"Key": "a"}], "IsTruncated": True, "NextContinuationToken": "n"},
            {"Contents": [{"Key": "b"}]},
        ]
    )

    class PagingClient:
        def list_objects_v2(self, **_kwargs):
            return next(responses)

    assert len(e._iter_s3_objects(PagingClient(), bucket="b", prefix="p")) == 2
    with pytest.raises(e.ExportError, match="has no objects"):
        e._iter_s3_objects(_ListClient(), bucket="b", prefix="p")
    with pytest.raises(e.ExportError, match="truncated without a token"):
        e._iter_s3_objects(
            _ListClient({"Contents": [{"Key": "a"}], "IsTruncated": True}),
            bucket="b",
            prefix="p",
        )

    digest = hashlib.sha256(b"payload").hexdigest()
    assert e._sha256_from_head_object({"Metadata": {"sha256": digest}}, uri="s3://b/k") == digest
    encoded = base64.b64encode(bytes.fromhex(digest)).decode()
    assert e._sha256_from_head_object({"ChecksumSHA256": encoded}, uri="s3://b/k") == digest
    with pytest.raises(e.ExportError, match="missing SHA-256"):
        e._sha256_from_head_object({}, uri="s3://b/k")

    body = _Body(b"payload")

    class BodyClient:
        def get_object(self, **_kwargs):
            return {"Body": body}

    assert (
        e._sha256_from_s3_object_body(
            BodyClient(), bucket="b", key="k", uri="s3://b/k", size_bytes=7, max_bytes=7
        )
        == digest
    )
    assert body.closed
    with pytest.raises(e.ExportError, match="exceeds"):
        e._sha256_from_s3_object_body(
            BodyClient(), bucket="b", key="k", uri="s3://b/k", size_bytes=8, max_bytes=7
        )


def test_git_tag_and_artifact_classification_edges():
    sha = "a" * 40
    packed = f"{sha} refs/tags/1.0.0\ninvalid\n{sha} refs/heads/main\n"
    assert e._tag_for_git_sha(packed, sha) == "1.0.0"
    assert e._tag_for_git_sha("", sha) == ""
    assert e._classify_exported_artifact("other/file") == ""
    assert e._classify_exported_artifact("results/sample.cram") == "alignment_cram"
    assert e._classify_exported_artifact("results/sample.vcf.gz.tbi") == "variant_vcf_index"
    assert e._parser_relevant("multiqc_data_file", "x/data.json") is True


def test_optional_s3_provenance_reads_cover_absent_errors_limits_and_success():
    class HeadClient:
        def __init__(self, *, head=None, head_error=None, body=None, body_error=None):
            self.head = head or {}
            self.head_error = head_error
            self.body = body
            self.body_error = body_error

        def head_object(self, **_kwargs):
            if self.head_error:
                raise self.head_error
            return self.head

        def get_object(self, **_kwargs):
            if self.body_error:
                raise self.body_error
            return {"Body": self.body}

    assert (
        e._read_s3_text_if_present(
            HeadClient(head_error=_client_error("NoSuchKey")), bucket="b", key="k"
        )
        == ""
    )
    with pytest.raises(e.ExportError, match="Unable to inspect"):
        e._read_s3_text_if_present(
            HeadClient(head_error=_client_error("Denied")), bucket="b", key="k"
        )
    assert (
        e._read_s3_text_if_present(
            HeadClient(head_error=RuntimeError("offline")), bucket="b", key="k"
        )
        == ""
    )
    with pytest.raises(e.ExportError, match="too large"):
        e._read_s3_text_if_present(
            HeadClient(head={"ContentLength": 11}), bucket="b", key="k", max_bytes=10
        )
    assert (
        e._read_s3_text_if_present(
            HeadClient(
                head={"ContentLength": 1},
                body_error=_client_error("NotFound"),
            ),
            bucket="b",
            key="k",
        )
        == ""
    )
    with pytest.raises(e.ExportError, match="Unable to read"):
        e._read_s3_text_if_present(
            HeadClient(
                head={"ContentLength": 1},
                body_error=_client_error("Denied"),
            ),
            bucket="b",
            key="k",
        )
    assert (
        e._read_s3_text_if_present(
            HeadClient(head={"ContentLength": 1}, body_error=RuntimeError("offline")),
            bucket="b",
            key="k",
        )
        == ""
    )
    body = _Body(b"hello")
    assert (
        e._read_s3_text_if_present(
            HeadClient(head={"ContentLength": 5}, body=body), bucket="b", key="k", max_bytes=5
        )
        == "hello"
    )
    assert body.closed
    with pytest.raises(e.ExportError, match="exceeds read limit"):
        e._read_s3_text_if_present(
            HeadClient(head={"ContentLength": 1}, body=_Body(b"too long")),
            bucket="b",
            key="k",
            max_bytes=2,
        )
