from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

import daylily_ec.cli as cli_module
from daylily_ec.cli import app
from daylily_ec import run_mounts


runner = CliRunner()


class FakeFsxClient:
    def __init__(
        self,
        associations: list[dict[str, Any]] | None = None,
        filesystem: dict[str, Any] | None = None,
    ) -> None:
        self.associations = list(associations or [])
        self.filesystem = filesystem or _filesystem()
        self.created_params: dict[str, Any] | None = None
        self.deleted_association_id: str | None = None

    def describe_file_systems(self, **params: Any) -> dict[str, Any]:
        wanted = set(params.get("FileSystemIds") or [])
        if wanted and self.filesystem.get("FileSystemId") not in wanted:
            return {"FileSystems": []}
        return {"FileSystems": [self.filesystem]}

    def describe_data_repository_associations(self, **params: Any) -> dict[str, Any]:
        associations = self.associations
        if "AssociationIds" in params:
            wanted = set(params["AssociationIds"])
            associations = [
                association
                for association in associations
                if association.get("AssociationId") in wanted
            ]
        for item in params.get("Filters", []) or []:
            if item.get("Name") == "file-system-id":
                wanted = set(item.get("Values") or [])
                associations = [
                    association
                    for association in associations
                    if association.get("FileSystemId") in wanted
                ]
        return {"Associations": associations}

    def create_data_repository_association(self, **params: Any) -> dict[str, Any]:
        self.created_params = params
        association = {
            "AssociationId": "dra-created",
            "FileSystemId": params["FileSystemId"],
            "FileSystemPath": params["FileSystemPath"],
            "DataRepositoryPath": params["DataRepositoryPath"],
            "Lifecycle": "CREATING",
            "S3": params.get("S3", {}),
        }
        self.associations.append(association)
        return {"Association": association}

    def delete_data_repository_association(self, **params: Any) -> dict[str, Any]:
        self.deleted_association_id = params["AssociationId"]
        assert params["DeleteDataInFileSystem"] is False
        for association in self.associations:
            if association["AssociationId"] == params["AssociationId"]:
                association = dict(association)
                association["Lifecycle"] = "DELETING"
                return {"Association": association}
        return {"Association": {"AssociationId": params["AssociationId"], "Lifecycle": "DELETING"}}


def _association(
    *,
    association_id: str = "dra-existing",
    file_system_path: str = "/run_dir_mounts/RUN124/",
    s3_uri: str = "s3://bucket/RUN124/",
    lifecycle: str = "AVAILABLE",
) -> dict[str, Any]:
    return {
        "AssociationId": association_id,
        "FileSystemId": "fs-123",
        "FileSystemPath": file_system_path,
        "DataRepositoryPath": s3_uri,
        "Lifecycle": lifecycle,
        "S3": {"AutoImportPolicy": {"Events": ["NEW", "CHANGED"]}},
    }


def _filesystem(
    *,
    file_system_id: str = "fs-123",
    file_system_type: str = "LUSTRE",
    deployment_type: str = "SCRATCH_2",
    legacy_repository_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lustre: dict[str, Any] = {"DeploymentType": deployment_type}
    if legacy_repository_config is not None:
        lustre["DataRepositoryConfiguration"] = legacy_repository_config
    return {
        "FileSystemId": file_system_id,
        "FileSystemType": file_system_type,
        "Lifecycle": "AVAILABLE",
        "LustreConfiguration": lustre,
    }


def test_mount_id_s3_and_path_normalization() -> None:
    assert run_mounts.validate_mount_id("RUN_123.4-5") == "RUN_123.4-5"
    with pytest.raises(run_mounts.RunMountError, match="must not be"):
        run_mounts.validate_mount_id("..")
    assert run_mounts.normalize_s3_uri("s3://bucket/runs/RUN123") == "s3://bucket/runs/RUN123/"
    assert (
        run_mounts.normalize_file_system_path(None, mount_id="RUN123")
        == "/run_dir_mounts/RUN123/"
    )
    assert (
        run_mounts.headnode_path_from_file_system_path("/run_dir_mounts/RUN123/")
        == "/fsx/run_dir_mounts/RUN123/"
    )
    with pytest.raises(run_mounts.RunMountError, match="/fsx/run_dir_mounts"):
        run_mounts.normalize_file_system_path("/fsx/run_dir_mounts/RUN123/", mount_id="RUN123")


def test_overlap_detection_rejects_active_fsx_and_s3_prefixes() -> None:
    assert run_mounts.paths_overlap("/run_dir_mounts/RUN123/", "/run_dir_mounts/RUN123/sub/")
    assert run_mounts.paths_overlap("s3://bucket/runs/", "s3://bucket/runs/RUN123/")
    with pytest.raises(run_mounts.RunMountError, match="overlaps active DRA"):
        run_mounts.validate_no_overlaps(
            [_association()],
            file_system_path="/run_dir_mounts/RUN124/sub/",
            source_s3_uri="s3://bucket/other/",
        )
    with pytest.raises(run_mounts.RunMountError, match="overlaps active DRA"):
        run_mounts.validate_no_overlaps(
            [_association()],
            file_system_path="/run_dir_mounts/other/",
            source_s3_uri="s3://bucket/RUN124/sub/",
        )


def test_auto_export_rejected_without_admin_override() -> None:
    with pytest.raises(run_mounts.RunMountError, match="forbidden"):
        run_mounts.parse_auto_export_events(
            "NEW",
            allow_writeback_admin=False,
            read_only=False,
        )
    with pytest.raises(run_mounts.RunMountError, match="requires --no-read-only"):
        run_mounts.parse_auto_export_events(
            "NEW",
            allow_writeback_admin=True,
            read_only=True,
        )
    assert run_mounts.parse_auto_export_events(
        "NEW",
        allow_writeback_admin=True,
        read_only=False,
    ) == ["NEW"]


def test_verification_script_avoids_heredoc() -> None:
    script = run_mounts._verification_script("/fsx/run_dir_mounts/RUN123/", "ILMN")

    assert "<<" not in script
    assert "DAYLILY_VERIFY_ROOT" in script
    assert "python3 -c" in script
    assert "Verify path is not under /fsx" in script
    assert "ls -A . >/dev/null" in script
    assert "RunInfo.xml" not in script
    assert "find " not in script


def test_create_describe_list_delete_run_mount_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    fake = FakeFsxClient()

    record = run_mounts.create_run_mount(
        run_mounts.CreateRunMountRequest(
            cluster_name="cluster-a",
            fsx_file_system_id="fs-123",
            region="us-west-2",
            profile="lsmc",
            source_s3_uri="s3://bucket/runs/RUN123",
            mount_id="RUN123",
            run_id="RUN123",
            platform="ILMN",
            wait=False,
            tags={"Name": "RUN123"},
        ),
        fsx_client=fake,
    )

    assert fake.created_params is not None
    assert fake.created_params["FileSystemPath"] == "/run_dir_mounts/RUN123/"
    assert fake.created_params["DataRepositoryPath"] == "s3://bucket/runs/RUN123/"
    assert "AutoExportPolicy" not in fake.created_params["S3"]
    assert record.to_output_payload()["headnode_path"] == "/fsx/run_dir_mounts/RUN123/"
    assert record.to_output_payload()["read_only"] is True

    listed = run_mounts.list_run_mounts(
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        region="us-west-2",
        profile="lsmc",
        fsx_client=fake,
    )
    assert [item.mount_id for item in listed] == ["RUN123"]

    described = run_mounts.describe_run_mount(
        mount_id="RUN123",
        association_id=None,
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        region="us-west-2",
        profile="lsmc",
        fsx_client=fake,
    )
    assert described.association_id == "dra-created"

    deleted = run_mounts.delete_run_mount(
        mount_id="RUN123",
        association_id=None,
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        region="us-west-2",
        profile="lsmc",
        wait=False,
        timeout_seconds=1,
        fsx_client=fake,
    )
    assert fake.deleted_association_id == "dra-created"
    assert deleted.lifecycle == "DELETING"


def test_create_run_mount_rejects_legacy_fsx_before_create() -> None:
    fake = FakeFsxClient(
        filesystem=_filesystem(
            legacy_repository_config={"ImportPath": "s3://bucket/data/"}
        )
    )

    with pytest.raises(run_mounts.RunMountError, match="legacy LustreConfiguration"):
        run_mounts.create_run_mount(
            run_mounts.CreateRunMountRequest(
                cluster_name="cluster-a",
                fsx_file_system_id="fs-123",
                region="us-west-2",
                profile="lsmc",
                source_s3_uri="s3://bucket/runs/RUN123",
                mount_id="RUN123",
                wait=False,
            ),
            fsx_client=fake,
        )

    assert fake.created_params is None


@pytest.mark.parametrize(
    ("filesystem", "message"),
    [
        (_filesystem(file_system_type="WINDOWS"), "DRA mounts require Lustre"),
        (_filesystem(deployment_type="SCRATCH_1"), "SCRATCH_1"),
    ],
)
def test_create_run_mount_rejects_dra_incompatible_filesystems(
    filesystem: dict[str, Any],
    message: str,
) -> None:
    fake = FakeFsxClient(filesystem=filesystem)

    with pytest.raises(run_mounts.RunMountError, match=message):
        run_mounts.create_run_mount(
            run_mounts.CreateRunMountRequest(
                cluster_name="cluster-a",
                fsx_file_system_id="fs-123",
                region="us-west-2",
                profile="lsmc",
                source_s3_uri="s3://bucket/runs/RUN123",
                mount_id="RUN123",
                wait=False,
            ),
            fsx_client=fake,
        )

    assert fake.created_params is None


def test_describe_mount_id_is_aws_authoritative(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    stale = run_mounts.RunMountRecord(
        mount_id="RUN123",
        run_id="RUN123",
        platform="ILMN",
        cluster_name="cluster-a",
        region="us-west-2",
        source_s3_uri="s3://bucket/RUN123/",
        fsx_file_system_id="fs-123",
        file_system_path="/run_dir_mounts/RUN123/",
        headnode_path="/fsx/run_dir_mounts/RUN123/",
        association_id="dra-stale",
        lifecycle="AVAILABLE",
        read_only=True,
    )
    run_mounts.write_mount_record(stale)
    fake = FakeFsxClient()

    listed = run_mounts.list_run_mounts(
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        region="us-west-2",
        profile="lsmc",
        fsx_client=fake,
    )
    assert listed == []

    with pytest.raises(run_mounts.RunMountError, match="Run mount not found"):
        run_mounts.describe_run_mount(
            mount_id="RUN123",
            association_id=None,
            cluster_name="cluster-a",
            fsx_file_system_id="fs-123",
            region="us-west-2",
            profile="lsmc",
            fsx_client=fake,
        )


def test_list_run_mounts_reports_missing_local_projection(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    fake = FakeFsxClient(associations=[_association(association_id="dra-aws")])

    listed = run_mounts.list_run_mounts(
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        region="us-west-2",
        profile="lsmc",
        fsx_client=fake,
    )

    assert len(listed) == 1
    assert listed[0].association_id == "dra-aws"
    assert listed[0].to_output_payload()["local_projection_status"] == "missing"


def test_verify_run_mount_accepts_association_id(monkeypatch) -> None:
    fake = FakeFsxClient(associations=[_association(association_id="dra-123")])
    calls: dict[str, Any] = {}

    def resolver(cluster_name: str, region: str, *, profile: str | None):
        return type("Target", (), {"instance_id": "i-123"})()

    def runner(instance_id: str, region: str, script: str, **kwargs: Any):
        calls["script"] = script
        return type(
            "Result",
            (),
            {
                "command_id": "cmd-1",
                "stdout": '{"path": "/fsx/run_dir_mounts/RUN124/", "usable": true}',
                "stderr": "",
            },
        )()

    payload = run_mounts.verify_run_mount(
        association_id="dra-123",
        cluster_name="cluster-a",
        fsx_file_system_id="fs-123",
        region="us-west-2",
        profile="lsmc",
        fsx_client=fake,
        headnode_resolver=resolver,
        shell_runner=runner,
    )

    assert payload["association_id"] == "dra-123"
    assert payload["verified"] is True
    assert payload["verification"]["usable"] is True
    assert "/fsx/run_dir_mounts/RUN124/" in calls["script"]


def test_verify_run_mount_rejects_non_headnode_scope() -> None:
    fake = FakeFsxClient(associations=[_association()])

    with pytest.raises(run_mounts.RunMountError, match="headnode-only"):
        run_mounts.verify_run_mount(
            mount_id="RUN124",
            cluster_name="cluster-a",
            fsx_file_system_id="fs-123",
            region="us-west-2",
            profile="lsmc",
            fsx_client=fake,
            scope="compute",
        )


def test_verify_run_mount_requires_exactly_one_identifier() -> None:
    with pytest.raises(run_mounts.RunMountError, match="exactly one"):
        run_mounts.verify_run_mount(
            mount_id="RUN123",
            association_id="dra-123",
            cluster_name="cluster-a",
            fsx_file_system_id="fs-123",
            region="us-west-2",
            profile="lsmc",
        )


def test_mounts_create_cli_emits_stable_json(monkeypatch) -> None:
    record = run_mounts.RunMountRecord(
        mount_id="RUN123",
        run_id="RUN123",
        platform="ILMN",
        cluster_name="cluster-a",
        region="us-west-2",
        source_s3_uri="s3://bucket/RUN123/",
        fsx_file_system_id="fs-123",
        file_system_path="/run_dir_mounts/RUN123/",
        headnode_path="/fsx/run_dir_mounts/RUN123/",
        association_id="dra-created",
        lifecycle="AVAILABLE",
        read_only=True,
    )

    monkeypatch.setattr(cli_module, "_create_mount_payload", lambda **_kwargs: record)

    result = runner.invoke(
        app,
        [
            "--json",
            "mounts",
            "create",
            "--s3-uri",
            "s3://bucket/RUN123/",
            "--cluster",
            "cluster-a",
            "--region",
            "us-west-2",
            "--profile",
            "lsmc",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["mount_id"] == "RUN123"
    assert payload["headnode_path"] == "/fsx/run_dir_mounts/RUN123/"
    assert payload["read_only"] is True


def test_mounts_verify_cli_accepts_association_id_json(monkeypatch) -> None:
    monkeypatch.setattr(
        run_mounts,
        "verify_run_mount",
        lambda **_kwargs: {
            "association_id": "dra-123",
            "headnode_path": "/fsx/run_dir_mounts/RUN123/",
            "lifecycle": "AVAILABLE",
            "mount_id": "RUN123",
            "verified": True,
        },
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "mounts",
            "verify",
            "--association-id",
            "dra-123",
            "--cluster",
            "cluster-a",
            "--region",
            "us-west-2",
            "--profile",
            "lsmc",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["association_id"] == "dra-123"
    assert payload["headnode_path"] == "/fsx/run_dir_mounts/RUN123/"
    assert payload["verified"] is True
