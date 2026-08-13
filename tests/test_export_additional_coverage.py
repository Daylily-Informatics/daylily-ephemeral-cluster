"""Additional failure coverage for provider-neutral FSx exports."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from daylily_ec.workflow import export_data as export


def _client_error(code: str = "Denied") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "denied"}}, "operation")


@pytest.mark.parametrize(
    "path",
    ["", "/", "/fsx/data/run", "/analysis_results/one", "/analysis_results/a/../b"],
)
def test_export_source_rejected_namespaces(path: str) -> None:
    with pytest.raises(export.ExportError):
        export.normalize_export_source_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "/analysis_results/alice/run/nested/../escape",
        "/analysis_results/alice/run/nested/./child",
        "/analysis_results/alice/run/nested//child",
        "/analysis_results/alice/run/nested/%2E%2E/child",
        "/fsx/staging/alice/run/nested/child",
        "analysis_results/alice/run/nested/child",
    ],
)
def test_nested_export_source_rejects_unsafe_or_alternate_paths(path: str) -> None:
    with pytest.raises((export.ExportError, ValueError)):
        export.normalize_export_source_path(path)


def test_nested_export_source_validation_does_not_discover_symlinks(monkeypatch) -> None:
    def unexpected_file_system_access(*_args, **_kwargs):
        raise AssertionError("source validation must remain lexical")

    monkeypatch.setattr(Path, "resolve", unexpected_file_system_access)
    monkeypatch.setattr(Path, "exists", unexpected_file_system_access)
    monkeypatch.setattr(Path, "is_symlink", unexpected_file_system_access)

    assert export.normalize_export_source_path(
        "/analysis_results/alice/run/symlink-shaped/child"
    ) == "/analysis_results/alice/run/symlink-shaped/child/"


@pytest.mark.parametrize(
    "existing_path",
    [
        "/analysis_results/alice/run/",
        "/analysis_results/alice/run/proof-batch/AU/child/",
    ],
)
def test_nested_export_overlap_uses_full_source_path(
    monkeypatch, existing_path: str
) -> None:
    monkeypatch.setattr(
        export,
        "describe_data_repository_associations",
        lambda *_args, **_kwargs: [
            {
                "AssociationId": "dra-overlap",
                "Lifecycle": "AVAILABLE",
                "FileSystemPath": existing_path,
            }
        ],
    )

    with pytest.raises(export.ExportError, match="dra-overlap"):
        export.validate_no_overlapping_export_dra(
            object(),
            fsx_file_system_id="fs-123",
            source_path="/analysis_results/alice/run/proof-batch/AU/",
        )


def test_nested_export_overlap_allows_sibling_path(monkeypatch) -> None:
    monkeypatch.setattr(
        export,
        "describe_data_repository_associations",
        lambda *_args, **_kwargs: [
            {
                "AssociationId": "dra-sibling",
                "Lifecycle": "AVAILABLE",
                "FileSystemPath": "/analysis_results/alice/run/proof-batch/AU-2/",
            }
        ],
    )

    export.validate_no_overlapping_export_dra(
        object(),
        fsx_file_system_id="fs-123",
        source_path="/analysis_results/alice/run/proof-batch/AU/",
    )


def test_launch_destination_requires_cluster_for_root() -> None:
    with pytest.raises(export.ExportError, match="--cluster is required"):
        export.resolve_launch_export_destination_s3_uri(
            "s3://bucket/root/",
            source_path="/analysis_results/alice/run/",
        )


def test_destination_prefix_wraps_client_error() -> None:
    client = SimpleNamespace(
        list_objects_v2=lambda **_kwargs: (_ for _ in ()).throw(_client_error())
    )
    with pytest.raises(export.ExportError, match="Unable to inspect"):
        export.validate_s3_destination_prefix_empty(
            client,
            "s3://bucket/alice/run/",
            source_path="/analysis_results/alice/run/",
        )


def test_resolve_export_fsx_requires_one_locator() -> None:
    with pytest.raises(export.ExportError, match="Provide --cluster"):
        export.resolve_export_fsx_id(
            object(), cluster_name=None, fsx_file_system_id=None
        )
    assert (
        export.resolve_export_fsx_id(
            object(), cluster_name=None, fsx_file_system_id=" fs-123 "
        )
        == "fs-123"
    )


def test_export_task_rejects_missing_task_id() -> None:
    client = SimpleNamespace(create_data_repository_task=lambda **_kwargs: {})
    with pytest.raises(export.ExportError, match="did not return a task id"):
        export.run_export_task(
            fsx_file_system_id="fs-123",
            source_path="/analysis_results/alice/run/",
            destination_s3_uri="s3://bucket/alice/run/",
            cluster_name=None,
            wait=False,
            timeout_seconds=1,
            fsx_client=client,
        )


def test_export_wait_rejects_missing_task() -> None:
    client = SimpleNamespace(
        describe_data_repository_tasks=lambda **_kwargs: {"DataRepositoryTasks": []}
    )
    with pytest.raises(export.ExportError, match="Unable to locate"):
        export.await_export_task(client, "task-1", timeout_seconds=1)


def test_status_write_creates_provider_neutral_receipt(tmp_path: Path) -> None:
    options = export.ExportOptions(
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        source_path="/analysis_results/alice/run/",
        destination_s3_uri="s3://bucket/alice/run/",
        region="us-west-2",
        profile=None,
        output_dir=tmp_path,
    )
    export._write_status(options, {"fsx_export": {"status": "success"}})
    text = (tmp_path / export.STATUS_FILENAME).read_text(encoding="utf-8")
    assert "status: success" in text
    assert "http" not in text


def test_shell_copy_hint_is_explicit_and_non_destructive() -> None:
    record = export.ExportDraRecord(
        analysis_dir="alice/run",
        cluster_name="cluster-a",
        region="us-west-2",
        fsx_file_system_id="fs-123",
        file_system_path="/analysis_results/alice/run/",
        headnode_path="/fsx/analysis_results/alice/run/",
        destination_s3_uri="s3://bucket/alice/run/",
        association_id="dra-123",
        lifecycle="AVAILABLE",
    )
    hint = export.shell_copy_hint(record)
    assert hint == "/fsx/analysis_results/alice/run/"
    assert "rm " not in hint
