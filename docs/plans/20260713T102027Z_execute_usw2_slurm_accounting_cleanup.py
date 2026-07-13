#!/usr/bin/env python3
"""Execute the explicitly approved us-west-2 Slurm accounting cleanup."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError


REGION = "us-west-2"
PROFILE = "lsmc"

KEEP = {
    "stack": "dayec-slurm-accounting-us-west-2c",
    "instance": "i-088957ddbc7fcf3d1",
    "volume": "vol-0b481de207f5b19f1",
    "client_sg": "sg-0e1a8da66cbee0a47",
    "db_sg": "sg-09151c49d1b2edeaf",
    "cluster": "sent-hg003-5x-0712",
}

DELETE_STACKS = {
    "dayec-slurm-accounting-us-west-2d": "CREATE_COMPLETE",
    "dayec-costacct-20260705T005955Z": "CREATE_COMPLETE",
    "dayec-slurm-accounting-cmdcat-103c": "CREATE_COMPLETE",
    "dayec-slurm-accounting-cmdcat-103b": "ROLLBACK_COMPLETE",
    "dayec-slurm-accounting-cmdcat-103": "ROLLBACK_COMPLETE",
}

DELETE_INSTANCES = {
    "i-0fec5d1a28b6d27aa": "vol-02caa6b741e86c280",
    "i-089b87fc6d966ec03": "vol-0958a841ed26fc81a",
    "i-052339da98d06719b": "vol-00445793f93ce7a51",
    "i-06940617dae9625d9": "vol-0bbe7df9fbac2b7c2",
}

DELETE_SECURITY_GROUPS = (
    "sg-0c8f3047dfc85b1c0",
    "sg-0619812d6a455c694",
    "sg-058f0a3b836320398",
    "sg-0472b75bd26b1c897",
    "sg-03f4d4b7fc608b7ea",
    "sg-042443cee20a43b8c",
    "sg-0dd41519e39d1cb85",
    "sg-00ff459cfcd910733",
)

DELETE_SECRETS = (
    "arn:aws:secretsmanager:us-west-2:108782052779:secret:AccountingPasswordSecret-LIXjs4Jyv7oh-b82PTx",
    "arn:aws:secretsmanager:us-west-2:108782052779:secret:AccountingPasswordSecret-2RA5iP6oOrnR-4nkGWC",
    "arn:aws:secretsmanager:us-west-2:108782052779:secret:AccountingPasswordSecret-92BEr4g2XZHh-nTwoQn",
    "arn:aws:secretsmanager:us-west-2:108782052779:secret:AccountingPasswordSecret-LbNa3JfFnch7-6dzKdQ",
)

DELETE_IAM = {
    "dayec-slurm-accounting-us-west-2d-AccountingDbInstanceProfile-efusfYBdIjfG": "dayec-slurm-accounting-us-west-2d-AccountingDbRole-86WYht22G5zK",
    "dayec-costacct-20260705T005955Z-AccountingDbInstanceProfile-X2TN4RONptFa": "dayec-costacct-20260705T005955Z-AccountingDbRole-Liyb6DNu1JOZ",
    "dayec-slurm-accounting-cmdcat-103c-AccountingDbInstanceProfile-twBW3Ek5hXkW": "dayec-slurm-accounting-cmdcat-103c-AccountingDbRole-xtsRVEZoDAIT",
    "dayec-slurm-accounting-cmdcat-103b-AccountingDbInstanceProfile-hR5uBTEm4oib": "dayec-slurm-accounting-cmdcat-103b-AccountingDbRole-9YSkisEDD8W3",
}

SENTLIC_ENI = "eni-037fd783d392c41cb"
SENTLIC_CLIENT_SG = "sg-0c8f3047dfc85b1c0"
SENTLIC_REMAINING_SG = "sg-05d44b1844e7651b0"


def tags_by_key(items: list[dict[str, str]]) -> dict[str, str]:
    return {item["Key"]: item["Value"] for item in items}


def emit(action: str, **details: Any) -> None:
    print(json.dumps({"action": action, **details}, sort_keys=True), flush=True)


def expect_client_error_code(exc: ClientError, code: str) -> None:
    actual = str(exc.response.get("Error", {}).get("Code", ""))
    if actual != code:
        raise exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("Refusing mutation without --execute")

    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    cfn = session.client("cloudformation")
    ec2 = session.client("ec2")
    secrets = session.client("secretsmanager")
    iam = session.client("iam")

    # Preflight the keeper and its live Ursa attachment before any mutation.
    keeper_stack = cfn.describe_stacks(StackName=KEEP["stack"])["Stacks"][0]
    assert keeper_stack["StackStatus"] == "CREATE_COMPLETE", keeper_stack["StackStatus"]
    keeper_instance = ec2.describe_instances(InstanceIds=[KEEP["instance"]])["Reservations"][0][
        "Instances"
    ][0]
    assert keeper_instance["State"]["Name"] == "running", keeper_instance["State"]
    keeper_volumes = {
        mapping["Ebs"]["VolumeId"]
        for mapping in keeper_instance.get("BlockDeviceMappings", [])
        if mapping.get("Ebs", {}).get("VolumeId")
    }
    assert keeper_volumes == {KEEP["volume"]}, keeper_volumes
    keeper_enis = ec2.describe_network_interfaces(
        Filters=[{"Name": "group-id", "Values": [KEEP["client_sg"]]}]
    )["NetworkInterfaces"]
    assert len(keeper_enis) == 1, keeper_enis
    keeper_headnode_id = keeper_enis[0]["Attachment"]["InstanceId"]
    keeper_headnode = ec2.describe_instances(InstanceIds=[keeper_headnode_id])["Reservations"][0][
        "Instances"
    ][0]
    keeper_tags = tags_by_key(keeper_headnode.get("Tags", []))
    assert keeper_tags.get("parallelcluster:cluster-name") == KEEP["cluster"], keeper_tags
    assert keeper_tags.get("ursa-preserve") == "true", keeper_tags

    # Freeze exact delete identities and states before mutation.
    for stack_name, expected_status in DELETE_STACKS.items():
        stack = cfn.describe_stacks(StackName=stack_name)["Stacks"][0]
        assert stack["StackStatus"] == expected_status, (stack_name, stack["StackStatus"])
        assert stack.get("EnableTerminationProtection") is True, stack_name

    described_instances: dict[str, dict[str, Any]] = {}
    response = ec2.describe_instances(InstanceIds=list(DELETE_INSTANCES))
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            described_instances[instance["InstanceId"]] = instance
    assert set(described_instances) == set(DELETE_INSTANCES), described_instances.keys()
    for instance_id, volume_id in DELETE_INSTANCES.items():
        instance = described_instances[instance_id]
        assert instance["State"]["Name"] == "running", (instance_id, instance["State"])
        assert tags_by_key(instance.get("Tags", [])).get("daylily-ec:component") == (
            "slurm-accounting-mysql"
        )
        actual_volumes = {
            mapping["Ebs"]["VolumeId"]
            for mapping in instance.get("BlockDeviceMappings", [])
            if mapping.get("Ebs", {}).get("VolumeId")
        }
        assert actual_volumes == {volume_id}, (instance_id, actual_volumes)
        protected = ec2.describe_instance_attribute(
            InstanceId=instance_id, Attribute="disableApiTermination"
        )["DisableApiTermination"]["Value"]
        assert protected is True, instance_id

    sentlic_eni = ec2.describe_network_interfaces(NetworkInterfaceIds=[SENTLIC_ENI])[
        "NetworkInterfaces"
    ][0]
    assert sentlic_eni["Attachment"]["InstanceId"] == "i-048ff099d73057e09", sentlic_eni
    assert {group["GroupId"] for group in sentlic_eni["Groups"]} == {
        SENTLIC_CLIENT_SG,
        SENTLIC_REMAINING_SG,
    }, sentlic_eni["Groups"]
    emit("preflight_complete", keeper=KEEP["stack"], delete_stacks=list(DELETE_STACKS))

    # Delete stack records; template retention policies preserve resources for explicit cleanup below.
    for stack_name in DELETE_STACKS:
        cfn.update_termination_protection(StackName=stack_name, EnableTerminationProtection=False)
        emit("stack_termination_protection_disabled", stack=stack_name)
        cfn.delete_stack(StackName=stack_name)
        emit("stack_delete_requested", stack=stack_name)
    waiter = cfn.get_waiter("stack_delete_complete")
    for stack_name in DELETE_STACKS:
        waiter.wait(StackName=stack_name, WaiterConfig={"Delay": 5, "MaxAttempts": 180})
        emit("stack_deleted", stack=stack_name)

    # Remove the obsolete accounting client SG from sentlic-e before deleting that SG.
    ec2.modify_network_interface_attribute(
        NetworkInterfaceId=SENTLIC_ENI,
        Groups=[SENTLIC_REMAINING_SG],
    )
    emit(
        "sentlic_accounting_sg_detached",
        eni=SENTLIC_ENI,
        removed=SENTLIC_CLIENT_SG,
        remaining=SENTLIC_REMAINING_SG,
    )

    # Terminate the four approved database hosts and wait for full detachment.
    for instance_id in DELETE_INSTANCES:
        ec2.modify_instance_attribute(
            InstanceId=instance_id,
            DisableApiTermination={"Value": False},
        )
        emit("instance_termination_protection_disabled", instance=instance_id)
    ec2.terminate_instances(InstanceIds=list(DELETE_INSTANCES))
    emit("instances_termination_requested", instances=list(DELETE_INSTANCES))
    ec2.get_waiter("instance_terminated").wait(
        InstanceIds=list(DELETE_INSTANCES),
        WaiterConfig={"Delay": 10, "MaxAttempts": 120},
    )
    emit("instances_terminated", instances=list(DELETE_INSTANCES))

    # Delete the explicitly retained EBS volumes.
    for volume_id in DELETE_INSTANCES.values():
        ec2.get_waiter("volume_available").wait(
            VolumeIds=[volume_id], WaiterConfig={"Delay": 5, "MaxAttempts": 120}
        )
        ec2.delete_volume(VolumeId=volume_id)
        emit("volume_delete_requested", volume=volume_id)
    for volume_id in DELETE_INSTANCES.values():
        ec2.get_waiter("volume_deleted").wait(
            VolumeIds=[volume_id], WaiterConfig={"Delay": 5, "MaxAttempts": 120}
        )
        emit("volume_deleted", volume=volume_id)

    # Revoke all retained rules before deleting the paired client/database SGs.
    for group_id in DELETE_SECURITY_GROUPS:
        rules = ec2.describe_security_group_rules(
            Filters=[{"Name": "group-id", "Values": [group_id]}]
        )["SecurityGroupRules"]
        ingress = [rule["SecurityGroupRuleId"] for rule in rules if not rule["IsEgress"]]
        egress = [rule["SecurityGroupRuleId"] for rule in rules if rule["IsEgress"]]
        if ingress:
            ec2.revoke_security_group_ingress(GroupId=group_id, SecurityGroupRuleIds=ingress)
        if egress:
            ec2.revoke_security_group_egress(GroupId=group_id, SecurityGroupRuleIds=egress)
        emit("security_group_rules_revoked", group=group_id, ingress=ingress, egress=egress)
    for group_id in DELETE_SECURITY_GROUPS:
        ec2.delete_security_group(GroupId=group_id)
        emit("security_group_deleted", group=group_id)

    # Delete the retained secrets without a recovery window, as explicitly approved.
    for secret_id in DELETE_SECRETS:
        response = secrets.delete_secret(SecretId=secret_id, ForceDeleteWithoutRecovery=True)
        emit("secret_force_delete_requested", secret=response["ARN"])

    # Remove retained instance-profile bindings, role policies, profiles, and roles.
    for profile_name, role_name in DELETE_IAM.items():
        profile = iam.get_instance_profile(InstanceProfileName=profile_name)["InstanceProfile"]
        actual_roles = {role["RoleName"] for role in profile.get("Roles", [])}
        assert actual_roles == {role_name}, (profile_name, actual_roles)
        iam.remove_role_from_instance_profile(
            InstanceProfileName=profile_name,
            RoleName=role_name,
        )
        for policy in iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
            iam.delete_role_policy(RoleName=role_name, PolicyName=policy)
        for policy in iam.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
        iam.delete_instance_profile(InstanceProfileName=profile_name)
        iam.delete_role(RoleName=role_name)
        emit("iam_profile_and_role_deleted", profile=profile_name, role=role_name)

    # Final regional singleton verification.
    active_instances = []
    response = ec2.describe_instances(
        Filters=[
            {"Name": "tag:daylily-ec:component", "Values": ["slurm-accounting-mysql"]},
            {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
        ]
    )
    for reservation in response["Reservations"]:
        active_instances.extend(instance["InstanceId"] for instance in reservation["Instances"])
    assert active_instances == [KEEP["instance"]], active_instances

    remaining_groups = ec2.describe_security_groups(
        Filters=[
            {"Name": "tag:daylily-ec:component", "Values": ["slurm-accounting-mysql"]}
        ]
    )["SecurityGroups"]
    remaining_group_ids = {group["GroupId"] for group in remaining_groups}
    assert remaining_group_ids == {KEEP["client_sg"], KEEP["db_sg"]}, remaining_group_ids

    for stack_name in DELETE_STACKS:
        try:
            cfn.describe_stacks(StackName=stack_name)
        except ClientError as exc:
            expect_client_error_code(exc, "ValidationError")
        else:
            raise AssertionError(f"Deleted stack still exists: {stack_name}")

    emit(
        "cleanup_complete",
        keeper_stack=KEEP["stack"],
        keeper_instance=KEEP["instance"],
        active_accounting_instances=active_instances,
        accounting_security_groups=sorted(remaining_group_ids),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
