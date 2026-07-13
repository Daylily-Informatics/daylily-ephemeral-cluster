from __future__ import annotations

from copy import deepcopy

import pytest

from daylily_ec.aws.sentieon_license_network import (
    EXPECTED_SECURITY_GROUP_ID,
    EXPECTED_SERVER_INSTANCE_ID,
    validate_license_ingress,
    validate_license_network,
)


PERMISSIONS = [
    {
        "IpProtocol": "tcp",
        "FromPort": 8990,
        "ToPort": 8990,
        "IpRanges": [{"CidrIp": "10.0.0.0/16"}],
        "Ipv6Ranges": [],
        "UserIdGroupPairs": [],
        "PrefixListIds": [],
    }
]


class FakeEc2:
    def __init__(self) -> None:
        self.instances = {
            EXPECTED_SERVER_INSTANCE_ID: {
                "InstanceId": EXPECTED_SERVER_INSTANCE_ID,
                "State": {"Name": "running"},
                "PrivateIpAddress": "10.0.0.205",
                "VpcId": "vpc-fixed",
                "SecurityGroups": [{"GroupId": EXPECTED_SECURITY_GROUP_ID}],
            },
            "i-client": {
                "InstanceId": "i-client",
                "State": {"Name": "running"},
                "PrivateIpAddress": "10.0.0.184",
                "VpcId": "vpc-fixed",
                "SecurityGroups": [],
            },
        }
        self.permissions = deepcopy(PERMISSIONS)

    def describe_instances(self, *, InstanceIds: list[str]) -> dict[str, object]:
        return {
            "Reservations": [
                {"Instances": [self.instances[instance_id] for instance_id in InstanceIds]}
            ]
        }

    def describe_security_groups(self, *, GroupIds: list[str]) -> dict[str, object]:
        assert GroupIds == [EXPECTED_SECURITY_GROUP_ID]
        return {"SecurityGroups": [{"IpPermissions": self.permissions}]}


def test_same_vpc_client_is_covered_by_explicit_allowlist() -> None:
    evidence = validate_license_network(
        ec2_client=FakeEc2(),
        client_instance_id="i-client",
    )
    assert evidence.server_vpc_id == "vpc-fixed"
    assert evidence.client_vpc_id == "vpc-fixed"
    assert evidence.allowed_cidrs == ("10.0.0.0/16",)


@pytest.mark.parametrize(
    "mutation",
    (
        {"IpProtocol": "-1"},
        {"FromPort": 22},
        {"ToPort": 9000},
        {"Ipv6Ranges": [{"CidrIpv6": "::/0"}]},
        {"UserIdGroupPairs": [{"GroupId": "sg-client"}]},
        {"PrefixListIds": [{"PrefixListId": "pl-client"}]},
        {"IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
        {"IpRanges": [{"CidrIp": "52.40.208.0/24"}]},
    ),
)
def test_unsafe_ingress_is_rejected(mutation: dict[str, object]) -> None:
    permissions = deepcopy(PERMISSIONS)
    permissions[0].update(mutation)
    with pytest.raises(ValueError):
        validate_license_ingress(permissions)


def test_public_nat_client_must_be_exact_32() -> None:
    permissions = deepcopy(PERMISSIONS)
    permissions[0]["IpRanges"] = [{"CidrIp": "52.40.208.196/32"}]
    assert validate_license_ingress(permissions) == ("52.40.208.196/32",)


def test_same_vpc_client_outside_allowlist_fails() -> None:
    ec2 = FakeEc2()
    ec2.instances["i-client"]["PrivateIpAddress"] = "10.1.0.184"
    with pytest.raises(ValueError, match="outside"):
        validate_license_network(ec2_client=ec2, client_instance_id="i-client")


def test_server_identity_drift_fails() -> None:
    ec2 = FakeEc2()
    ec2.instances[EXPECTED_SERVER_INSTANCE_ID]["PrivateIpAddress"] = "10.0.0.206"
    with pytest.raises(ValueError, match="private IP"):
        validate_license_network(ec2_client=ec2, client_instance_id="i-client")
