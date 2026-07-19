"""Behavioral edges for the immutable provider-neutral export workflow."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from daylily_ec.workflow import export_data as export


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "operation")


def test_overlap_inspection_ignores_inactive_and_blocks_active(monkeypatch) -> None:
    monkeypatch.setattr(
        export,
        "describe_data_repository_associations",
        lambda *_args, **_kwargs: [
            {
                "AssociationId": "inactive",
                "Lifecycle": "DELETED",
                "FileSystemPath": "/analysis_results/alice/run/",
            }
        ],
    )
    export.validate_no_overlapping_export_dra(
        object(), fsx_file_system_id="fs-1", source_path="/analysis_results/alice/run/"
    )
    monkeypatch.setattr(
        export,
        "describe_data_repository_associations",
        lambda *_args, **_kwargs: [
            {
                "AssociationId": "active",
                "Lifecycle": "AVAILABLE",
                "FileSystemPath": "/analysis_results/alice/run/",
            }
        ],
    )
    with pytest.raises(export.ExportError, match="overlaps"):
        export.validate_no_overlapping_export_dra(
            object(),
            fsx_file_system_id="fs-1",
            source_path="/analysis_results/alice/run/",
        )


def test_detach_allows_only_explicit_not_found() -> None:
    absent = SimpleNamespace(
        delete_data_repository_association=lambda **_kwargs: (_ for _ in ()).throw(
            _client_error("DataRepositoryAssociationNotFound")
        )
    )
    receipt = export.detach_export_dra(
        association_id="dra-1",
        region="us-west-2",
        profile=None,
        wait=False,
        timeout_seconds=1,
        fsx_client=absent,
        allow_absent=True,
    )
    assert receipt["detach_absent"] is True
    assert receipt["delete_data_in_file_system"] is False

    denied = SimpleNamespace(
        delete_data_repository_association=lambda **_kwargs: (_ for _ in ()).throw(
            _client_error("AccessDenied")
        )
    )
    with pytest.raises(export.ExportError, match="Unable to detach"):
        export.detach_export_dra(
            association_id="dra-1",
            region="us-west-2",
            profile=None,
            wait=False,
            timeout_seconds=1,
            fsx_client=denied,
            allow_absent=True,
        )


def test_analysis_paths_remain_exact() -> None:
    assert export.analysis_dir_from_source_path("/fsx/analysis_results/alice/run") == "alice/run"
    assert (
        export.analysis_headnode_path("/analysis_results/alice/run/")
        == "/fsx/analysis_results/alice/run/"
    )
