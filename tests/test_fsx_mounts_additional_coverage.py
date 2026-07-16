"""Additional behavioral coverage for P2 FSx and run-mount contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from botocore.exceptions import ClientError, EndpointConnectionError
import pytest
import yaml

import daylily_ec.aws.fsx_persistent2 as p2
from daylily_ec.aws.fsx_persistent2 import Persistent2Resources, Persistent2Spec
import daylily_ec.run_mounts as mounts


def _spec(**overrides: object) -> Persistent2Spec:
    values: dict[str, object] = {
        "cluster_name": "coverage-p2",
        "region": "us-west-2",
        "region_az": "us-west-2d",
        "subnet_id": "subnet-private",
        "storage_capacity_gib": 4800,
        "throughput_mbps_per_tib": 250,
        "reference_s3_uri": "s3://references/",
        "username_tag": "coverage",
        "account_profile_tag": "aws_profile-coverage",
        "enforce_budget_tag": "true",
        "cost_center_region": "us-west-2",
        "cost_center_table": "dayec-cost-centers",
        "cost_center_usage_table": "dayec-cost-center-usage",
    }
    values.update(overrides)
    return Persistent2Spec(**values)


def _filesystem(**overrides: object) -> dict:
    payload = {
        "FileSystemId": "fs-p2",
        "Lifecycle": "AVAILABLE",
        "FileSystemType": "LUSTRE",
        "FileSystemTypeVersion": "2.15",
        "StorageType": "SSD",
        "StorageCapacity": 4800,
        "SubnetIds": ["subnet-private"],
        "SecurityGroupIds": ["sg-p2"],
        "LustreConfiguration": {
            "DeploymentType": "PERSISTENT_2",
            "PerUnitStorageThroughput": 250,
            "MetadataConfiguration": {"Mode": "AUTOMATIC"},
        },
        "Tags": [
            {"Key": "dyec:cluster-name", "Value": "coverage-p2"},
            {"Key": "dyec:resource-role", "Value": "fsx"},
            {"Key": "dyec:fsx-owner", "Value": "DYEC"},
            {"Key": "dyec:fsx-lifecycle", "Value": "CLUSTER_BOUND"},
            {"Key": "ursa-preserve", "Value": "true"},
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"cluster_name": ""}, "cluster_name is required"),
        ({"region": ""}, "region, region_az, and subnet_id"),
        ({"lustre_version": "2.12"}, "must use Lustre"),
        ({"metadata_mode": "USER_PROVISIONED"}, "metadata mode"),
        ({"encryption_mode": "KMS"}, "encryption mode"),
        ({"owner": "OTHER"}, "ownership"),
        ({"sweep_preserve": False}, "ursa-preserve"),
        ({"reference_s3_uri": "https://example.org"}, "explicit s3:// URI"),
    ],
)
def test_persistent2_spec_rejects_unsafe_contract_variants(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _spec(**overrides).validate()


@pytest.mark.parametrize(
    ("subnets", "message"),
    [
        ([], "exactly one subnet"),
        ([{"AvailabilityZone": "us-west-2c", "VpcId": "vpc-1"}], "expected us-west-2d"),
        ([{"AvailabilityZone": "us-west-2d"}], "has no VPC id"),
    ],
)
def test_target_subnet_contract_rejects_missing_mismatched_or_unscoped_records(
    subnets: list[dict], message: str
) -> None:
    ec2 = SimpleNamespace(describe_subnets=lambda **_kwargs: {"Subnets": subnets})
    with pytest.raises(RuntimeError, match=message):
        p2._describe_target_subnet(ec2, _spec())


def test_security_group_reuses_one_group_and_ignores_duplicate_ingress() -> None:
    duplicate = ClientError(
        {"Error": {"Code": "InvalidPermission.Duplicate", "Message": "exists"}},
        "AuthorizeSecurityGroupIngress",
    )
    calls: list[dict] = []
    ec2 = SimpleNamespace(
        describe_subnets=lambda **_kwargs: {
            "Subnets": [{"AvailabilityZone": "us-west-2d", "VpcId": "vpc-1"}]
        },
        describe_security_groups=lambda **_kwargs: {"SecurityGroups": [{"GroupId": "sg-existing"}]},
        authorize_security_group_ingress=lambda **kwargs: calls.append(kwargs)
        or (_ for _ in ()).throw(duplicate),
    )
    assert p2.ensure_security_group(ec2, _spec()) == ("sg-existing", "vpc-1")
    assert len(calls) == 2


def test_security_group_rejects_duplicates_missing_id_and_nonduplicate_api_error() -> None:
    base = {
        "describe_subnets": lambda **_kwargs: {
            "Subnets": [{"AvailabilityZone": "us-west-2d", "VpcId": "vpc-1"}]
        }
    }
    duplicate_groups = SimpleNamespace(
        **base,
        describe_security_groups=lambda **_kwargs: {
            "SecurityGroups": [{"GroupId": "sg-a"}, {"GroupId": "sg-b"}]
        },
    )
    with pytest.raises(RuntimeError, match="Multiple DYEC P2 security groups"):
        p2.ensure_security_group(duplicate_groups, _spec())

    missing_id = SimpleNamespace(
        **base,
        describe_security_groups=lambda **_kwargs: {"SecurityGroups": []},
        create_security_group=lambda **_kwargs: {},
    )
    with pytest.raises(RuntimeError, match="did not return a security group id"):
        p2.ensure_security_group(missing_id, _spec())

    denied = ClientError(
        {"Error": {"Code": "UnauthorizedOperation", "Message": "denied"}},
        "AuthorizeSecurityGroupIngress",
    )
    client = SimpleNamespace(
        authorize_security_group_ingress=lambda **_kwargs: (_ for _ in ()).throw(denied)
    )
    with pytest.raises(ClientError):
        p2._ensure_self_ingress(client, "sg-p2")


def test_file_system_matching_validation_and_wait_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paginator = SimpleNamespace(
        paginate=lambda: [{"FileSystems": [_filesystem(), {"FileSystemId": "other"}]}]
    )
    assert [
        item["FileSystemId"]
        for item in p2._matching_file_systems(
            SimpleNamespace(get_paginator=lambda _op: paginator), _spec()
        )
    ] == ["fs-p2"]

    with pytest.raises(RuntimeError, match="does not match"):
        p2._validate_file_system(_filesystem(StorageCapacity=2400), _spec(), "sg-p2")
    with pytest.raises(RuntimeError, match="missing tag"):
        p2._validate_file_system(_filesystem(Tags=[]), _spec(), "sg-p2")
    with pytest.raises(RuntimeError, match="does not use security group"):
        p2._validate_file_system(_filesystem(SecurityGroupIds=["sg-other"]), _spec(), "sg-p2")

    missing = SimpleNamespace(describe_file_systems=lambda **_kwargs: {"FileSystems": []})
    with pytest.raises(RuntimeError, match="exactly one record"):
        p2._wait_for_file_system(
            missing,
            "fs-p2",
            timeout_seconds=1,
            poll_interval_seconds=0,
            sleep_fn=lambda _seconds: None,
        )
    failed = SimpleNamespace(
        describe_file_systems=lambda **_kwargs: {
            "FileSystems": [
                {
                    "FileSystemId": "fs-p2",
                    "Lifecycle": "FAILED",
                    "FailureDetails": {"Message": "capacity"},
                }
            ]
        }
    )
    with pytest.raises(RuntimeError, match="capacity"):
        p2._wait_for_file_system(
            failed,
            "fs-p2",
            timeout_seconds=1,
            poll_interval_seconds=0,
            sleep_fn=lambda _seconds: None,
        )
    monkeypatch.setattr(p2.time, "monotonic", lambda: 10)
    pending = SimpleNamespace(
        describe_file_systems=lambda **_kwargs: {
            "FileSystems": [{"FileSystemId": "fs-p2", "Lifecycle": "CREATING"}]
        }
    )
    with pytest.raises(TimeoutError, match="last lifecycle=CREATING"):
        p2._wait_for_file_system(
            pending,
            "fs-p2",
            timeout_seconds=0,
            poll_interval_seconds=0,
            sleep_fn=lambda _seconds: None,
        )


def test_ensure_file_system_rejects_duplicate_or_missing_identity() -> None:
    duplicate = SimpleNamespace(
        get_paginator=lambda _op: SimpleNamespace(
            paginate=lambda: [
                {"FileSystems": [_filesystem(), _filesystem(FileSystemId="fs-other")]}
            ]
        )
    )
    with pytest.raises(RuntimeError, match="Multiple DYEC P2 filesystems"):
        p2.ensure_file_system(duplicate, _spec(), "sg-p2")

    missing = SimpleNamespace(
        get_paginator=lambda _op: SimpleNamespace(paginate=lambda: [{"FileSystems": []}]),
        create_file_system=lambda **_kwargs: {},
    )
    with pytest.raises(RuntimeError, match="did not return a file system id"):
        p2.ensure_file_system(missing, _spec(), "sg-p2")


def _association(**overrides: object) -> dict:
    payload = {
        "AssociationId": "dra-p2",
        "Lifecycle": "AVAILABLE",
        "FileSystemPath": "/references/",
        "DataRepositoryPath": "s3://references",
        "S3": {"AutoImportPolicy": {"Events": ["NEW", "CHANGED", "DELETED"]}},
    }
    payload.update(overrides)
    return payload


def test_reference_association_validation_wait_and_identity_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for association, message in [
        (_association(FileSystemPath="/wrong/"), "map exactly"),
        (_association(DataRepositoryPath="s3://other"), "repository mismatch"),
        (_association(S3={}), "must auto-import"),
    ]:
        with pytest.raises(RuntimeError, match=message):
            p2._validate_reference_association(association, _spec())

    missing = SimpleNamespace(
        describe_data_repository_associations=lambda **_kwargs: {"Associations": []}
    )
    with pytest.raises(RuntimeError, match="exactly one DRA"):
        p2._wait_for_association(
            missing,
            "dra-p2",
            timeout_seconds=1,
            poll_interval_seconds=0,
            sleep_fn=lambda _seconds: None,
        )
    failed = SimpleNamespace(
        describe_data_repository_associations=lambda **_kwargs: {
            "Associations": [
                _association(
                    Lifecycle="MISCONFIGURED",
                    FailureDetails={"Message": "bad repository"},
                )
            ]
        }
    )
    with pytest.raises(RuntimeError, match="bad repository"):
        p2._wait_for_association(
            failed,
            "dra-p2",
            timeout_seconds=1,
            poll_interval_seconds=0,
            sleep_fn=lambda _seconds: None,
        )
    monkeypatch.setattr(p2.time, "monotonic", lambda: 10)
    pending = SimpleNamespace(
        describe_data_repository_associations=lambda **_kwargs: {
            "Associations": [_association(Lifecycle="CREATING")]
        }
    )
    with pytest.raises(TimeoutError, match="last lifecycle=CREATING"):
        p2._wait_for_association(
            pending,
            "dra-p2",
            timeout_seconds=0,
            poll_interval_seconds=0,
            sleep_fn=lambda _seconds: None,
        )

    duplicate = SimpleNamespace(
        describe_data_repository_associations=lambda **_kwargs: {
            "Associations": [_association(), _association(AssociationId="dra-other")]
        }
    )
    with pytest.raises(RuntimeError, match="multiple data repository associations"):
        p2.ensure_reference_association(duplicate, _spec(), "fs-p2")

    no_id = SimpleNamespace(
        describe_data_repository_associations=lambda **_kwargs: {"Associations": []},
        create_data_repository_association=lambda **_kwargs: {},
    )
    with pytest.raises(RuntimeError, match="did not return an association id"):
        p2.ensure_reference_association(no_id, _spec(), "fs-p2")


def test_persistent2_orchestrator_returns_nonsecret_resource_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(p2, "ensure_security_group", lambda *_args: ("sg-p2", "vpc-1"))
    monkeypatch.setattr(
        p2,
        "ensure_file_system",
        lambda *_args, **_kwargs: {"FileSystemId": "fs-p2"},
    )
    monkeypatch.setattr(
        p2,
        "ensure_reference_association",
        lambda *_args, **_kwargs: {"AssociationId": "dra-p2"},
    )
    messages: list[str] = []
    resources = p2.ensure_persistent2_resources(
        object(),
        object(),
        _spec(),
        status_callback=messages.append,
    )
    assert resources == Persistent2Resources(
        file_system_id="fs-p2",
        security_group_id="sg-p2",
        data_repository_association_id="dra-p2",
        subnet_id="subnet-private",
        vpc_id="vpc-1",
    )
    assert messages == ["P2 client security group sg-p2: ready."]


def _resources() -> Persistent2Resources:
    return Persistent2Resources(
        file_system_id="fs-p2",
        security_group_id="sg-p2",
        data_repository_association_id="dra-p2",
        subnet_id="subnet-private",
        vpc_id="vpc-1",
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"SharedStorage": []}, "exactly one FsxLustre"),
        (
            {"SharedStorage": [{"StorageType": "FsxLustre", "MountDir": "/wrong"}]},
            "mount exactly at /fsx",
        ),
        (
            {
                "SharedStorage": [{"StorageType": "FsxLustre", "MountDir": "/fsx"}],
                "Scheduling": {"SlurmQueues": []},
            },
            "at least one Slurm queue",
        ),
        (
            {
                "SharedStorage": [{"StorageType": "FsxLustre", "MountDir": "/fsx"}],
                "Scheduling": {"SlurmQueues": [{"Name": "q"}]},
                "Tags": [{"Key": "ursa-preserve", "Value": "false"}],
            },
            "conflicting ursa-preserve",
        ),
    ],
)
def test_render_external_mount_rejects_invalid_cluster_templates(
    tmp_path: Path, payload: dict, message: str
) -> None:
    path = tmp_path / "cluster.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        p2.render_external_mount(path, _resources())


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"SharedStorage": []}, "exactly one FsxLustre"),
        (
            {
                "SharedStorage": [
                    {
                        "StorageType": "FsxLustre",
                        "FsxLustreSettings": {"StorageCapacity": 4800},
                    }
                ]
            },
            "only the external FileSystemId",
        ),
        (
            {
                "SharedStorage": [
                    {
                        "StorageType": "FsxLustre",
                        "FsxLustreSettings": {"FileSystemId": "fs-p2"},
                    }
                ],
                "HeadNode": {"Networking": {}},
            },
            "headnode is missing",
        ),
        (
            {
                "SharedStorage": [
                    {
                        "StorageType": "FsxLustre",
                        "FsxLustreSettings": {"FileSystemId": "fs-p2"},
                    }
                ],
                "HeadNode": {"Networking": {"AdditionalSecurityGroups": ["sg-p2"]}},
                "Scheduling": {"SlurmQueues": [{"Name": "q", "Networking": {}}]},
            },
            "queue q is missing",
        ),
    ],
)
def test_validate_external_mount_rejects_partial_rendered_contracts(
    tmp_path: Path, payload: dict, message: str
) -> None:
    path = tmp_path / "cluster.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        p2.validate_external_mount(path, _resources())


def test_cluster_bound_inventory_and_delete_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    filesystems = [
        _filesystem(),
        _filesystem(
            FileSystemId="fs-other",
            Tags=[
                {"Key": "dyec:cluster-name", "Value": "other"},
                {"Key": "dyec:resource-role", "Value": "fsx"},
            ],
        ),
    ]
    fsx = SimpleNamespace(
        describe_file_systems=lambda **_kwargs: {"FileSystems": filesystems},
        delete_file_system=lambda **_kwargs: None,
    )
    assert (
        p2.find_cluster_bound_file_systems(fsx, cluster_name="coverage-p2", file_system_ids=[])
        == []
    )
    assert p2.find_cluster_bound_file_systems(
        fsx,
        cluster_name="coverage-p2",
        file_system_ids=["fs-p2", "fs-other"],
    ) == ["fs-p2"]

    monkeypatch.setattr(
        p2,
        "find_cluster_bound_file_systems",
        lambda *_args, **_kwargs: ["fs-p2"],
    )
    monkeypatch.setattr(p2, "_wait_for_file_system_absent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(p2, "_delete_security_groups", lambda *_args, **_kwargs: ["sg-p2"])
    deleted = p2.delete_cluster_bound_resources(
        object(), fsx, cluster_name="coverage-p2", file_system_ids=["fs-p2"]
    )
    assert deleted == {"file_system_ids": ["fs-p2"], "security_group_ids": ["sg-p2"]}


def test_file_system_absence_waiter_handles_not_found_empty_timeout_and_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    not_found = ClientError(
        {"Error": {"Code": "FileSystemNotFound", "Message": "gone"}},
        "DescribeFileSystems",
    )
    p2._wait_for_file_system_absent(
        SimpleNamespace(describe_file_systems=lambda **_kwargs: (_ for _ in ()).throw(not_found)),
        "fs-p2",
        timeout_seconds=1,
        poll_interval_seconds=0,
        sleep_fn=lambda _seconds: None,
    )
    p2._wait_for_file_system_absent(
        SimpleNamespace(describe_file_systems=lambda **_kwargs: {"FileSystems": []}),
        "fs-p2",
        timeout_seconds=1,
        poll_interval_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    denied = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}},
        "DescribeFileSystems",
    )
    with pytest.raises(ClientError):
        p2._wait_for_file_system_absent(
            SimpleNamespace(describe_file_systems=lambda **_kwargs: (_ for _ in ()).throw(denied)),
            "fs-p2",
            timeout_seconds=1,
            poll_interval_seconds=0,
            sleep_fn=lambda _seconds: None,
        )

    monkeypatch.setattr(p2.time, "monotonic", lambda: 10)
    with pytest.raises(TimeoutError, match="last lifecycle=DELETING"):
        p2._wait_for_file_system_absent(
            SimpleNamespace(
                describe_file_systems=lambda **_kwargs: {"FileSystems": [{"Lifecycle": "DELETING"}]}
            ),
            "fs-p2",
            timeout_seconds=0,
            poll_interval_seconds=0,
            sleep_fn=lambda _seconds: None,
        )


def test_delete_security_groups_skips_empty_retries_dependency_and_accepts_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = ClientError(
        {"Error": {"Code": "DependencyViolation", "Message": "busy"}},
        "DeleteSecurityGroup",
    )
    missing = ClientError(
        {"Error": {"Code": "InvalidGroup.NotFound", "Message": "gone"}},
        "DeleteSecurityGroup",
    )
    calls: dict[str, int] = {}

    def delete(*, GroupId: str) -> None:
        calls[GroupId] = calls.get(GroupId, 0) + 1
        if GroupId == "sg-retry" and calls[GroupId] == 1:
            raise dependency
        if GroupId == "sg-missing":
            raise missing

    times = iter([0, 0, 0, 0, 0, 0])
    monkeypatch.setattr(p2.time, "monotonic", lambda: next(times))
    ec2 = SimpleNamespace(
        describe_security_groups=lambda **_kwargs: {
            "SecurityGroups": [
                {},
                {"GroupId": "sg-retry"},
                {"GroupId": "sg-missing"},
            ]
        },
        delete_security_group=delete,
    )
    assert p2._delete_security_groups(
        ec2,
        cluster_name="coverage-p2",
        timeout_seconds=10,
        poll_interval_seconds=0,
        sleep_fn=lambda _seconds: None,
    ) == ["sg-retry", "sg-missing"]


@pytest.mark.parametrize(
    "mount_id",
    ["", "a" * 129, "bad..id", "bad%20id", "bad/id"],
)
def test_run_mount_id_rejects_empty_long_traversal_encoding_and_separators(
    mount_id: str,
) -> None:
    with pytest.raises(mounts.RunMountError):
        mounts.validate_mount_id(mount_id)


def test_run_mount_source_id_purpose_and_path_contracts() -> None:
    with pytest.raises(mounts.RunMountError, match="Expected an s3:// URI"):
        mounts.normalize_s3_uri("https://bucket/key")
    with pytest.raises(mounts.RunMountError, match="query"):
        mounts.normalize_s3_uri("s3://bucket/key?version=1")
    assert (
        mounts.mount_id_from_request(mount_id=None, run_id="RUN1", source_s3_uri="s3://bucket/key/")
        == "RUN1"
    )
    assert (
        mounts.mount_id_from_request(
            mount_id=None, run_id=None, source_s3_uri="s3://bucket/runs/RUN2/"
        )
        == "RUN2"
    )
    with pytest.raises(mounts.RunMountError, match="bucket-root"):
        mounts.mount_id_from_request(mount_id=None, run_id=None, source_s3_uri="s3://bucket/")
    with pytest.raises(mounts.RunMountError, match="purpose"):
        mounts.normalize_mount_purpose("unknown")
    with pytest.raises(mounts.RunMountError, match="required when --purpose custom"):
        mounts.normalize_file_system_path(None, mount_id="RUN", purpose="custom")
    with pytest.raises(mounts.RunMountError, match="must be under"):
        mounts.normalize_file_system_path("/other/RUN/", mount_id="RUN", purpose="reference")
    with pytest.raises(mounts.RunMountError, match="concrete --purpose"):
        mounts.normalize_file_system_path("/references/RUN/", mount_id="RUN", purpose="custom")


@pytest.mark.parametrize("path", ["relative", "/", "/double//slash/"])
def test_run_mount_api_path_rejects_nonabsolute_root_and_duplicate_slashes(
    path: str,
) -> None:
    with pytest.raises(mounts.RunMountError):
        mounts._normalize_absolute_fsx_api_path(path)


def test_marker_and_tag_error_paths_are_bounded() -> None:
    with pytest.raises(mounts.RunMountError, match="bucket-root"):
        mounts.verify_atlas_rw_marker(object(), "s3://bucket/")

    access_denied = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "HeadObject"
    )
    with pytest.raises(mounts.RunMountError, match="Unable to verify"):
        mounts.verify_atlas_rw_marker(
            SimpleNamespace(head_object=lambda **_kwargs: (_ for _ in ()).throw(access_denied)),
            "s3://bucket/path/",
        )
    with pytest.raises(mounts.RunMountError, match="Unable to verify"):
        mounts.verify_atlas_rw_marker(
            SimpleNamespace(
                head_object=lambda **_kwargs: (_ for _ in ()).throw(
                    EndpointConnectionError(endpoint_url="https://s3.invalid")
                )
            ),
            "s3://bucket/path/",
        )
    with pytest.raises(mounts.RunMountError, match="KEY=VALUE"):
        mounts.parse_tags(["missing-equals"])
    with pytest.raises(mounts.RunMountError, match="key must not be empty"):
        mounts.parse_tags(["=value"])
    assert mounts.parse_tags(["owner=coverage"], purpose="reference") == {
        "lsmc:purpose": "reference",
        "owner": "coverage",
    }


def test_run_mount_waiters_cover_missing_failure_timeout_and_deleted_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mounts,
        "describe_data_repository_associations",
        lambda *_args, **_kwargs: [],
    )
    with pytest.raises(mounts.RunMountError, match="not found"):
        mounts.wait_for_association(
            object(), "dra", target_lifecycles=["AVAILABLE"], timeout_seconds=1
        )

    monkeypatch.setattr(
        mounts,
        "describe_data_repository_associations",
        lambda *_args, **_kwargs: [{"Lifecycle": "FAILED"}],
    )
    with pytest.raises(mounts.RunMountError, match="entered FAILED"):
        mounts.wait_for_association(
            object(), "dra", target_lifecycles=["AVAILABLE"], timeout_seconds=1
        )

    monkeypatch.setattr(mounts.time, "time", lambda: 10)
    monkeypatch.setattr(
        mounts,
        "describe_data_repository_associations",
        lambda *_args, **_kwargs: [{"Lifecycle": "CREATING"}],
    )
    with pytest.raises(mounts.RunMountError, match="Timed out"):
        mounts.wait_for_association(
            object(), "dra", target_lifecycles=["AVAILABLE"], timeout_seconds=0
        )

    fallback = {"AssociationId": "dra", "Lifecycle": "DELETING"}
    monkeypatch.setattr(
        mounts,
        "describe_data_repository_associations",
        lambda *_args, **_kwargs: [],
    )
    deleted = mounts.wait_for_deleted_association(
        object(), "dra", fallback_association=fallback, timeout_seconds=1
    )
    assert deleted["Lifecycle"] == "DELETED"

    monkeypatch.setattr(
        mounts,
        "describe_data_repository_associations",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            mounts.RunMountError("association not found")
        ),
    )
    assert (
        mounts.wait_for_deleted_association(
            object(), "dra", fallback_association=fallback, timeout_seconds=1
        )["Lifecycle"]
        == "DELETED"
    )


def test_run_mount_state_format_and_parser_helpers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(mounts.RunMountError, match="cluster_name or fsx"):
        mounts.mount_record_path(
            region="us-west-2",
            cluster_name=None,
            fsx_file_system_id=None,
            mount_id="RUN",
        )
    assert mounts.purpose_from_file_system_path("relative") is None
    assert mounts.purpose_from_file_system_path("/custom/RUN/") == "custom"
    assert mounts._is_static_role_root_path("relative") is False
    assert mounts.extract_mount_id("/control_data/") == "control_data"
    assert mounts.extract_mount_id("/staging/") == "staging"
    assert mounts.extract_mount_id("/staging/staged_external_sequencing_data/RUN1/") == "RUN1"
    assert mounts.format_mount_list([]) == "No mounts found."
    assert mounts._parse_event_tokens("none", default=["NEW"]) == []
    assert mounts._parse_event_tokens("all", default=[]) == ["NEW", "CHANGED", "DELETED"]
    assert mounts._parse_event_tokens("new,changed,new", default=[]) == ["NEW", "CHANGED"]
    with pytest.raises(mounts.RunMountError, match="Unsupported"):
        mounts._parse_event_tokens("renamed", default=[])
    with pytest.raises(mounts.RunMountError, match="Path must not be empty"):
        mounts._with_trailing_slash("")
    with pytest.raises(mounts.RunMountError, match="Unsupported platform"):
        mounts._normalize_platform("unknown")
    with pytest.raises(mounts.RunMountError, match="region is required"):
        mounts._require_region("")
    with pytest.raises(mounts.RunMountError, match="Unsafe state path"):
        mounts._state_component("../unsafe")
    assert mounts._format_timestamp(datetime(2026, 7, 16, 3, 0, 0)) == "2026-07-16T03:00:00Z"
    assert (
        mounts._format_timestamp(datetime(2026, 7, 16, 3, 0, 0, tzinfo=timezone.utc))
        == "2026-07-16T03:00:00Z"
    )
    assert mounts._format_timestamp("literal") == "literal"
    assert mounts._looks_not_found(RuntimeError("NotFound"))
    assert mounts._parse_verification_stdout("noise\n{bad json\n") == {
        "path": "",
        "usable": False,
    }
    assert mounts._parse_verification_stdout('noise\n{"path": "/fsx/run", "usable": true}\n') == {
        "path": "/fsx/run",
        "usable": True,
    }
