from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace

from botocore.exceptions import ClientError
import pytest

import daylily_ec.workflow.export_data as export


def _client_error(code: str = "Denied") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "operation")


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/fsx/data/run",
        "/fsx/control_data/x",
        "/fsx/staging/x",
        "/fsx/other/x",
        "/run_dir_mounts/run",
        "/data/run",
        "/references/x",
        "/control_data/x",
        "/staging/x",
        "/exports/x",
        "relative/path",
        "/other/path",
    ],
)
def test_export_source_rejected_namespaces(path: str) -> None:
    with pytest.raises(export.ExportError):
        export.normalize_export_source_path(path)


def test_export_logging_session_and_record(monkeypatch: pytest.MonkeyPatch) -> None:
    configured: list[dict] = []
    monkeypatch.setattr(export.logging, "basicConfig", lambda **kwargs: configured.append(kwargs))
    export.configure_logging(True)
    export.configure_logging(False)
    assert configured[0]["level"] == export.logging.DEBUG
    calls: list[dict] = []
    monkeypatch.setattr(export.boto3, "Session", lambda **kwargs: calls.append(kwargs) or kwargs)
    export._create_session("r", "profile")
    export._create_session("r", None)
    assert calls == [
        {"region_name": "r", "profile_name": "profile"},
        {"region_name": "r"},
    ]
    record = export.ExportDraRecord("a", None, "r", "fs", "/p", "/h", "s3://b/k", "dra", "A")
    assert record.to_payload()["association_id"] == "dra"


def test_launch_destination_existing_and_missing_cluster() -> None:
    source = "/analysis_results/alice/analysis/"
    assert (
        export.resolve_launch_export_destination_s3_uri(
            "s3://bucket/alice/analysis/", source_path=source
        )
        == "s3://bucket/alice/analysis/"
    )
    with pytest.raises(export.ExportError, match="--cluster is required"):
        export.resolve_launch_export_destination_s3_uri("s3://bucket/root/", source_path=source)


def test_destination_and_fsx_resolution_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    source = "/analysis_results/alice/analysis/"
    client = SimpleNamespace(
        list_objects_v2=lambda **kwargs: (_ for _ in ()).throw(_client_error())
    )
    with pytest.raises(export.ExportError, match="Unable to inspect"):
        export.validate_s3_destination_prefix_empty(
            client, "s3://bucket/alice/analysis/", source_path=source
        )
    with pytest.raises(export.ExportError, match="Provide --cluster"):
        export.resolve_export_fsx_id(object(), cluster_name=None, fsx_file_system_id=None)
    monkeypatch.setattr(export, "resolve_fsx_file_system_id", lambda client, cluster: "fs-resolved")
    assert (
        export.resolve_export_fsx_id(object(), cluster_name="cluster", fsx_file_system_id=None)
        == "fs-resolved"
    )

    monkeypatch.setattr(
        export,
        "describe_data_repository_associations",
        lambda *args, **kwargs: (_ for _ in ()).throw(export.RunMountError("bad")),
    )
    with pytest.raises(export.ExportError, match="Unable to inspect existing"):
        export.validate_no_overlapping_export_dra(
            object(), fsx_file_system_id="fs", source_path=source
        )


def test_empty_destination_and_inactive_association_are_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = "/analysis_results/alice/analysis/"
    client = SimpleNamespace(list_objects_v2=lambda **kwargs: {"KeyCount": 0})
    assert (
        export.validate_s3_destination_prefix_empty(
            client, "s3://bucket/alice/analysis/", source_path=source
        )
        == "s3://bucket/alice/analysis/"
    )
    monkeypatch.setattr(
        export,
        "describe_data_repository_associations",
        lambda *args, **kwargs: [{"Lifecycle": "FAILED", "FileSystemPath": source}],
    )
    export.validate_no_overlapping_export_dra(object(), fsx_file_system_id="fs", source_path=source)


def test_attach_export_dra_creation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    common = dict(
        cluster_name="cluster",
        fsx_file_system_id="fs",
        source_path="/analysis_results/alice/analysis/",
        destination_s3_uri="s3://bucket/alice/analysis/",
        region="r",
        profile=None,
        wait=False,
        timeout_seconds=1,
    )
    monkeypatch.setattr(export, "describe_fsx_file_system", lambda *args: {})
    monkeypatch.setattr(export, "validate_dra_compatible_file_system", lambda fs: None)
    monkeypatch.setattr(export, "validate_no_overlapping_export_dra", lambda *args, **kwargs: None)
    failing = SimpleNamespace(
        create_data_repository_association=lambda **kwargs: (_ for _ in ()).throw(_client_error())
    )
    with pytest.raises(export.ExportError, match="Unable to create"):
        export.attach_export_dra(**common, fsx_client=failing)
    missing = SimpleNamespace(create_data_repository_association=lambda **kwargs: {})
    with pytest.raises(export.ExportError, match="did not return"):
        export.attach_export_dra(**common, fsx_client=missing)


def test_run_and_wait_export_task_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    common = dict(
        fsx_file_system_id="fs",
        source_path="/analysis_results/alice/analysis/",
        destination_s3_uri="s3://bucket/alice/analysis/",
        cluster_name=None,
        wait=False,
        timeout_seconds=1,
    )
    failing = SimpleNamespace(
        create_data_repository_task=lambda **kwargs: (_ for _ in ()).throw(_client_error())
    )
    with pytest.raises(export.ExportError, match="Unable to start"):
        export.run_export_task(**common, fsx_client=failing)
    missing = SimpleNamespace(create_data_repository_task=lambda **kwargs: {})
    with pytest.raises(export.ExportError, match="did not return a task id"):
        export.run_export_task(**common, fsx_client=missing)

    describe_error = SimpleNamespace(
        describe_data_repository_tasks=lambda **kwargs: (_ for _ in ()).throw(_client_error())
    )
    with pytest.raises(export.ExportError, match="Unable to describe"):
        export.await_export_task(describe_error, "task", timeout_seconds=1)
    absent = SimpleNamespace(describe_data_repository_tasks=lambda **kwargs: {})
    with pytest.raises(export.ExportError, match="Unable to locate"):
        export.await_export_task(absent, "task", timeout_seconds=1)
    monotonic = iter([0, 2])
    monkeypatch.setattr(export.time, "time", lambda: next(monotonic))
    pending = SimpleNamespace(
        describe_data_repository_tasks=lambda **kwargs: {
            "DataRepositoryTasks": [{"Lifecycle": "PENDING"}]
        }
    )
    with pytest.raises(export.ExportError, match="Timed out"):
        export.await_export_task(pending, "task", timeout_seconds=1)


def test_detach_errors_absent_and_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    absent_client = SimpleNamespace(
        delete_data_repository_association=lambda **kwargs: (_ for _ in ()).throw(
            _client_error("DataRepositoryAssociationNotFound")
        )
    )
    result = export.detach_export_dra(
        association_id="dra",
        region="r",
        profile=None,
        wait=False,
        timeout_seconds=1,
        fsx_client=absent_client,
        allow_absent=True,
    )
    assert result["detach_absent"] is True
    with pytest.raises(export.ExportError, match="Unable to detach"):
        export.detach_export_dra(
            association_id="dra",
            region="r",
            profile=None,
            wait=False,
            timeout_seconds=1,
            fsx_client=absent_client,
            allow_absent=False,
        )

    client = SimpleNamespace(
        delete_data_repository_association=lambda **kwargs: {
            "Association": {"Lifecycle": "DELETING"}
        }
    )
    monkeypatch.setattr(
        export, "wait_for_deleted_association", lambda *args, **kwargs: {"Lifecycle": "DELETED"}
    )
    result = export.detach_export_dra(
        association_id="dra",
        region="r",
        profile=None,
        wait=True,
        timeout_seconds=1,
        fsx_client=client,
    )
    assert result["detach_lifecycle"] == "DELETED"


@pytest.mark.parametrize(
    ("body", "pattern"),
    [("not json", "malformed"), ("[]", "must be an object")],
)
def test_read_s3_json_validation(body: str, pattern: str) -> None:
    client = SimpleNamespace(
        get_object=lambda **kwargs: {"Body": SimpleNamespace(read=lambda: body.encode())}
    )
    with pytest.raises(export.ExportError, match=pattern):
        export._read_s3_json(client, "s3://bucket/key")
    with pytest.raises(export.ExportError, match="must use s3"):
        export._read_s3_json(client, "https://bucket/key")
    assert export._s3_parts("s3://bucket/key") == ("bucket", "key")
    with pytest.raises(export.ExportError, match="must use s3"):
        export._s3_parts("bad")


def test_iter_s3_objects_pagination_and_errors() -> None:
    pages = iter(
        [
            {"Contents": [{"Key": "a"}], "IsTruncated": True, "NextContinuationToken": "next"},
            {"Contents": [{"Key": "b"}], "IsTruncated": False},
        ]
    )
    client = SimpleNamespace(list_objects_v2=lambda **kwargs: next(pages))
    assert [item["Key"] for item in export._iter_s3_objects(client, bucket="b", prefix="p")] == [
        "a",
        "b",
    ]
    truncated = SimpleNamespace(
        list_objects_v2=lambda **kwargs: {"Contents": [{}], "IsTruncated": True}
    )
    with pytest.raises(export.ExportError, match="truncated without a token"):
        export._iter_s3_objects(truncated, bucket="b", prefix="p")
    empty = SimpleNamespace(list_objects_v2=lambda **kwargs: {})
    with pytest.raises(export.ExportError, match="has no objects"):
        export._iter_s3_objects(empty, bucket="b", prefix="p")
    failing = SimpleNamespace(
        list_objects_v2=lambda **kwargs: (_ for _ in ()).throw(_client_error())
    )
    with pytest.raises(export.ExportError, match="Unable to list"):
        export._iter_s3_objects(failing, bucket="b", prefix="p")


def test_sha_and_s3_text_edge_cases() -> None:
    digest = "a" * 64
    assert (
        export._sha256_from_head_object(
            {"ChecksumSHA256": base64.b64encode(bytes.fromhex(digest)).decode()}, uri="s3://b/k"
        )
        == digest
    )
    with pytest.raises(export.ExportError, match="missing SHA-256"):
        export._sha256_from_head_object({}, uri="s3://b/k")
    too_large = SimpleNamespace()
    with pytest.raises(export.ExportError, match="s3_body_sha256_max_bytes"):
        export._sha256_from_s3_object_body(
            too_large, bucket="b", key="k", uri="s3://b/k", size_bytes=11, max_bytes=10
        )
    body = io.BytesIO(b"content")
    client = SimpleNamespace(get_object=lambda **kwargs: {"Body": body})
    assert (
        export._sha256_from_s3_object_body(
            client, bucket="b", key="k", uri="s3://b/k", size_bytes=7, max_bytes=10
        )
        == hashlib.sha256(b"content").hexdigest()
    )

    missing = SimpleNamespace(head_object=lambda **kwargs: (_ for _ in ()).throw(RuntimeError()))
    assert export._read_s3_text_if_present(missing, bucket="b", key="k") == ""
    large = SimpleNamespace(head_object=lambda **kwargs: {"ContentLength": 11})
    with pytest.raises(export.ExportError, match="too large"):
        export._read_s3_text_if_present(large, bucket="b", key="k", max_bytes=10)


def test_git_tag_and_workflow_metadata_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    assert export._tag_for_git_sha("malformed\nabc refs/heads/main", "a" * 40) == ""
    assert (
        export._tag_for_git_sha(
            f"{'a' * 40} refs/tags/10.0.1\n{'a' * 40} refs/tags/10.2.0", "a" * 40
        )
        == "10.2.0"
    )
    monkeypatch.setattr(export, "_read_s3_text_if_present", lambda *args, **kwargs: "bad")
    with pytest.raises(export.ExportError, match="40-character SHA"):
        export._s3_inventory_workflow_metadata(object(), bucket="b", prefix="p/")


def test_dewey_registration_required_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = export.ExportOptions(
        cluster_name=None,
        fsx_file_system_id=None,
        source_path="/analysis_results/alice/analysis/",
        destination_s3_uri="s3://bucket/alice/analysis/",
        region="r",
        profile=None,
        output_dir=tmp_path,
        wait=False,
        timeout_seconds=1,
    )
    receipt = {"fsx_export": {"analysis_dir": "alice/analysis"}}
    with pytest.raises(export.ExportError, match="policy is required"):
        export._run_dewey_registration(options=base, receipt=receipt, s3_client=object())
    policy = SimpleNamespace(manifest_source="bad")
    base.artifact_registration_policy = policy
    base.artifact_registration_genome = "hg38"
    base.dewey_url = "https://dewey"
    base.dewey_token_env = "TOKEN"
    monkeypatch.setenv("TOKEN", "secret")
    with pytest.raises(export.ExportError, match="manifest source"):
        export._run_dewey_registration(options=base, receipt=receipt, s3_client=object())


@pytest.mark.parametrize(
    ("field", "value", "pattern"),
    [
        ("artifact_registration_genome", "", "genome is required"),
        ("dewey_url", "", "dewey_url is required"),
        ("dewey_token_env", "", "token_env is required"),
    ],
)
def test_dewey_registration_missing_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
    pattern: str,
) -> None:
    policy = SimpleNamespace(manifest_source="dayoa_manifest")
    options = export.ExportOptions(
        cluster_name=None,
        fsx_file_system_id=None,
        source_path="/analysis_results/alice/analysis/",
        destination_s3_uri="s3://bucket/alice/analysis/",
        region="r",
        profile=None,
        output_dir=tmp_path,
        artifact_registration_policy=policy,
        artifact_registration_genome="hg38",
        dewey_url="https://dewey",
        dewey_token_env="TOKEN",
    )
    setattr(options, field, value)
    monkeypatch.setenv("TOKEN", "secret")
    with pytest.raises(export.ExportError, match=pattern):
        export._run_dewey_registration(
            options=options,
            receipt={"fsx_export": {"analysis_dir": "alice/analysis"}},
            s3_client=object(),
        )


def test_dewey_registration_missing_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = SimpleNamespace(manifest_source="dayoa_manifest")
    options = export.ExportOptions(
        cluster_name=None,
        fsx_file_system_id=None,
        source_path="/analysis_results/alice/analysis/",
        destination_s3_uri="s3://bucket/alice/analysis/",
        region="r",
        profile=None,
        output_dir=tmp_path,
        artifact_registration_policy=policy,
        artifact_registration_genome="hg38",
        dewey_url="https://dewey",
        dewey_token_env="TOKEN",
    )
    monkeypatch.delenv("TOKEN", raising=False)
    with pytest.raises(export.ExportError, match="environment variable is not set"):
        export._run_dewey_registration(
            options=options,
            receipt={"fsx_export": {"analysis_dir": "alice/analysis"}},
            s3_client=object(),
        )


def test_registration_only_and_export_validation_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = SimpleNamespace(manifest_source="dayoa_manifest")
    register = export.RegisterExistingExportOptions(
        source_path="bad",
        destination_s3_uri="bad",
        region="r",
        profile=None,
        output_dir=tmp_path,
        artifact_registration_policy=policy,
        artifact_registration_genome="hg38",
        artifact_registration_manifest_source="dayoa_manifest",
        artifact_registration_command_id="cmd",
        dewey_url="url",
        dewey_token_env="TOKEN",
    )
    monkeypatch.setattr(export.ui, "phase", lambda *args: None)
    monkeypatch.setattr(export.ui, "step", lambda *args: None)
    monkeypatch.setattr(export.ui, "error_panel", lambda *args: None)
    assert export.run_dewey_registration_for_existing_export(register) == 1
    status = (tmp_path / export.STATUS_FILENAME).read_text(encoding="utf-8")
    assert "phase: validate" in status

    options = export.ExportOptions(
        cluster_name=None,
        fsx_file_system_id=None,
        source_path="bad",
        destination_s3_uri="bad",
        region="r",
        profile=None,
        output_dir=tmp_path,
    )
    assert export.run_export_workflow(options) == 1
    assert "phase: validate" in (tmp_path / export.STATUS_FILENAME).read_text(encoding="utf-8")


def test_registration_only_invalid_manifest_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = SimpleNamespace(manifest_source="dayoa_manifest")
    options = export.RegisterExistingExportOptions(
        source_path="/analysis_results/alice/analysis/",
        destination_s3_uri="s3://bucket/alice/analysis/",
        region="r",
        profile=None,
        output_dir=tmp_path,
        artifact_registration_policy=policy,
        artifact_registration_genome="hg38",
        artifact_registration_manifest_source="bad",
        artifact_registration_command_id="cmd",
        dewey_url="url",
        dewey_token_env="TOKEN",
    )
    for name in ("phase", "step", "error_panel"):
        monkeypatch.setattr(export.ui, name, lambda *args: None)
    assert export.run_dewey_registration_for_existing_export(options) == 1
    assert "dewey_registration_status: error" in (tmp_path / export.STATUS_FILENAME).read_text(
        encoding="utf-8"
    )


def test_workflow_metadata_symbolic_head_and_missing_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    sha = "a" * 40
    values = iter(["ref: refs/heads/main", sha, ""])
    monkeypatch.setattr(export, "_read_s3_text_if_present", lambda *args, **kwargs: next(values))
    with pytest.raises(export.ExportError, match="packed-refs with a tag"):
        export._s3_inventory_workflow_metadata(object(), bucket="b", prefix="p/")


def test_remaining_s3_read_error_branches() -> None:
    failing_body = SimpleNamespace(
        get_object=lambda **kwargs: (_ for _ in ()).throw(_client_error())
    )
    with pytest.raises(export.ExportError, match="SHA-256 computation"):
        export._sha256_from_s3_object_body(
            failing_body, bucket="b", key="k", uri="s3://b/k", size_bytes=1, max_bytes=2
        )

    missing_head = SimpleNamespace(
        head_object=lambda **kwargs: (_ for _ in ()).throw(_client_error("NoSuchKey"))
    )
    assert export._read_s3_text_if_present(missing_head, bucket="b", key="k") == ""
    denied_head = SimpleNamespace(
        head_object=lambda **kwargs: (_ for _ in ()).throw(_client_error("Denied"))
    )
    with pytest.raises(export.ExportError, match="Unable to inspect"):
        export._read_s3_text_if_present(denied_head, bucket="b", key="k")

    missing_body = SimpleNamespace(
        head_object=lambda **kwargs: {"ContentLength": 1},
        get_object=lambda **kwargs: (_ for _ in ()).throw(_client_error("404")),
    )
    assert export._read_s3_text_if_present(missing_body, bucket="b", key="k") == ""
    denied_body = SimpleNamespace(
        head_object=lambda **kwargs: {"ContentLength": 1},
        get_object=lambda **kwargs: (_ for _ in ()).throw(_client_error("Denied")),
    )
    with pytest.raises(export.ExportError, match="Unable to read"):
        export._read_s3_text_if_present(denied_body, bucket="b", key="k")
    oversized = SimpleNamespace(
        head_object=lambda **kwargs: {"ContentLength": 1},
        get_object=lambda **kwargs: {"Body": io.BytesIO(b"too long")},
    )
    with pytest.raises(export.ExportError, match="exceeds read limit"):
        export._read_s3_text_if_present(oversized, bucket="b", key="k", max_bytes=2)


def test_shell_copy_hint() -> None:
    record = export.ExportDraRecord("a", None, "r", "fs", "/p", "/head/path", "s3://b/k", "d", "A")
    assert export.shell_copy_hint(record) == "/head/path"
