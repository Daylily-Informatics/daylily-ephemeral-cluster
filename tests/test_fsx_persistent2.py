from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import yaml

from daylily_ec.aws.fsx_persistent2 import (
    Persistent2Resources,
    Persistent2Spec,
    ensure_file_system,
    ensure_reference_association,
    ensure_security_group,
    render_external_mount,
    validate_external_mount,
)


def _spec(**overrides) -> Persistent2Spec:
    values = {
        "cluster_name": "ifx-p2-250-0714",
        "region": "us-west-2",
        "region_az": "us-west-2d",
        "subnet_id": "subnet-private",
        "storage_capacity_gib": 4800,
        "throughput_mbps_per_tib": 250,
        "reference_s3_uri": "s3://references/",
        "username_tag": "jmajor-root",
        "account_profile_tag": "aws_profile-lsmc",
        "enforce_budget_tag": "true",
        "cost_center_region": "us-west-2",
        "cost_center_table": "dayec-cost-centers",
        "cost_center_usage_table": "dayec-cost-center-usage",
    }
    values.update(overrides)
    return Persistent2Spec(**values)


def _filesystem() -> dict:
    return {
        "FileSystemId": "fs-p2",
        "Lifecycle": "AVAILABLE",
        "FileSystemType": "LUSTRE",
        "FileSystemTypeVersion": "2.15",
        "StorageType": "SSD",
        "StorageCapacity": 4800,
        "SubnetIds": ["subnet-private"],
        "LustreConfiguration": {
            "DeploymentType": "PERSISTENT_2",
            "PerUnitStorageThroughput": 250,
            "MetadataConfiguration": {"Mode": "AUTOMATIC"},
        },
        "Tags": [
            {"Key": "dyec:cluster-name", "Value": "ifx-p2-250-0714"},
            {"Key": "dyec:resource-role", "Value": "fsx"},
            {"Key": "dyec:fsx-owner", "Value": "DYEC"},
            {"Key": "dyec:fsx-lifecycle", "Value": "CLUSTER_BOUND"},
            {"Key": "ursa-preserve", "Value": "true"},
        ],
    }


def test_persistent2_spec_rejects_any_tier_substitution() -> None:
    with pytest.raises(ValueError, match="exactly 250"):
        _spec(throughput_mbps_per_tib=125).validate()


def test_ensure_security_group_creates_self_referenced_lustre_rules() -> None:
    ec2 = MagicMock()
    ec2.describe_subnets.return_value = {
        "Subnets": [
            {
                "SubnetId": "subnet-private",
                "AvailabilityZone": "us-west-2d",
                "VpcId": "vpc-1",
            }
        ]
    }
    ec2.describe_security_groups.return_value = {"SecurityGroups": []}
    ec2.create_security_group.return_value = {"GroupId": "sg-p2"}

    security_group_id, vpc_id = ensure_security_group(ec2, _spec())

    assert (security_group_id, vpc_id) == ("sg-p2", "vpc-1")
    assert ec2.authorize_security_group_ingress.call_count == 2
    permissions = [
        call.kwargs["IpPermissions"][0]
        for call in ec2.authorize_security_group_ingress.call_args_list
    ]
    assert [(item["FromPort"], item["ToPort"]) for item in permissions] == [
        (988, 988),
        (1021, 1023),
    ]
    assert all(item["UserIdGroupPairs"] == [{"GroupId": "sg-p2"}] for item in permissions)


def test_ensure_file_system_creates_exact_p2_metadata_contract() -> None:
    fsx = MagicMock()
    fsx.get_paginator.return_value.paginate.return_value = [{"FileSystems": []}]
    fsx.create_file_system.return_value = {"FileSystem": {"FileSystemId": "fs-p2"}}
    fsx.describe_file_systems.return_value = {"FileSystems": [_filesystem()]}

    filesystem = ensure_file_system(
        fsx,
        _spec(),
        "sg-p2",
        poll_interval_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    assert filesystem["FileSystemId"] == "fs-p2"
    kwargs = fsx.create_file_system.call_args.kwargs
    assert kwargs["FileSystemType"] == "LUSTRE"
    assert kwargs["FileSystemTypeVersion"] == "2.15"
    assert kwargs["StorageCapacity"] == 4800
    assert kwargs["StorageType"] == "SSD"
    assert kwargs["SubnetIds"] == ["subnet-private"]
    assert kwargs["SecurityGroupIds"] == ["sg-p2"]
    assert kwargs["LustreConfiguration"] == {
        "DeploymentType": "PERSISTENT_2",
        "PerUnitStorageThroughput": 250,
        "MetadataConfiguration": {"Mode": "AUTOMATIC"},
        "DataCompressionType": "NONE",
        "AutomaticBackupRetentionDays": 0,
        "CopyTagsToBackups": True,
    }
    assert {item["Key"]: item["Value"] for item in kwargs["Tags"]}["ursa-preserve"] == "true"


def test_reference_dra_is_explicit_and_import_only() -> None:
    fsx = MagicMock()
    fsx.describe_data_repository_associations.side_effect = [
        {"Associations": []},
        {
            "Associations": [
                {
                    "AssociationId": "dra-p2",
                    "Lifecycle": "AVAILABLE",
                    "FileSystemPath": "/references/",
                    "DataRepositoryPath": "s3://references",
                    "S3": {"AutoImportPolicy": {"Events": ["NEW", "CHANGED", "DELETED"]}},
                }
            ]
        },
    ]
    fsx.create_data_repository_association.return_value = {
        "Association": {"AssociationId": "dra-p2"}
    }

    association = ensure_reference_association(
        fsx,
        _spec(),
        "fs-p2",
        poll_interval_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    assert association["AssociationId"] == "dra-p2"
    kwargs = fsx.create_data_repository_association.call_args.kwargs
    assert kwargs["FileSystemPath"] == "/references/"
    assert kwargs["DataRepositoryPath"] == "s3://references"
    assert kwargs["BatchImportMetaDataOnCreate"] is True
    assert kwargs["S3"] == {"AutoImportPolicy": {"Events": ["NEW", "CHANGED", "DELETED"]}}
    assert "AutoExportPolicy" not in kwargs["S3"]


def test_render_external_mount_adds_all_clients_and_sweeper_tag(tmp_path) -> None:
    path = tmp_path / "cluster.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "HeadNode": {"Networking": {"SubnetId": "subnet-public"}},
                "Scheduling": {
                    "SlurmQueues": [
                        {"Name": "i8", "Networking": {"SubnetIds": ["subnet-private"]}},
                        {"Name": "i96", "Networking": {"SubnetIds": ["subnet-private"]}},
                    ]
                },
                "SharedStorage": [
                    {
                        "MountDir": "/fsx",
                        "Name": "managed",
                        "StorageType": "FsxLustre",
                        "FsxLustreSettings": {
                            "StorageCapacity": 4800,
                            "DeploymentType": "SCRATCH_2",
                        },
                    }
                ],
                "Tags": [{"Key": "project", "Value": "ifx-p2-250-0714"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    resources = Persistent2Resources(
        file_system_id="fs-p2",
        security_group_id="sg-p2",
        data_repository_association_id="dra-p2",
        subnet_id="subnet-private",
        vpc_id="vpc-1",
    )

    render_external_mount(path, resources)
    validate_external_mount(path, resources)

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload["SharedStorage"][0]["FsxLustreSettings"] == {"FileSystemId": "fs-p2"}
    assert payload["HeadNode"]["Networking"]["AdditionalSecurityGroups"] == ["sg-p2"]
    assert all(
        queue["Networking"]["AdditionalSecurityGroups"] == ["sg-p2"]
        for queue in payload["Scheduling"]["SlurmQueues"]
    )
    assert {item["Key"]: item["Value"] for item in payload["Tags"]}["ursa-preserve"] == "true"
