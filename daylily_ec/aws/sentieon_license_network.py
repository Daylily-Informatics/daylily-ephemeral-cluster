"""Fail-closed network validation for the Sentieon license service."""

from __future__ import annotations

import argparse
import ipaddress
import sys
from dataclasses import dataclass
from typing import Any, Sequence

import boto3

EXPECTED_SERVER_INSTANCE_ID = "i-03c42907b08018d1a"
EXPECTED_SERVER_PRIVATE_IP = "10.0.0.205"
EXPECTED_SECURITY_GROUP_ID = "sg-004e7647782ff1cf9"
EXPECTED_PORT = 8990


@dataclass(frozen=True)
class NetworkEvidence:
    """Non-secret evidence for one validated client path."""

    server_vpc_id: str
    client_vpc_id: str
    allowed_cidrs: tuple[str, ...]


def validate_license_network(
    *,
    ec2_client: Any,
    client_instance_id: str,
) -> NetworkEvidence:
    """Require the fixed server identity and explicit TCP/8990 allowlist."""

    response = ec2_client.describe_instances(
        InstanceIds=[EXPECTED_SERVER_INSTANCE_ID, client_instance_id]
    )
    instances = {
        str(instance["InstanceId"]): instance
        for reservation in response.get("Reservations", [])
        for instance in reservation.get("Instances", [])
    }
    if set(instances) != {EXPECTED_SERVER_INSTANCE_ID, client_instance_id}:
        raise ValueError("Unable to resolve the exact server and client instance identities.")

    server = instances[EXPECTED_SERVER_INSTANCE_ID]
    client = instances[client_instance_id]
    if server.get("State", {}).get("Name") != "running":
        raise ValueError("Sentieon license-server instance must be running.")
    if server.get("PrivateIpAddress") != EXPECTED_SERVER_PRIVATE_IP:
        raise ValueError("Sentieon license-server private IP does not match the fixed contract.")
    server_groups = {group["GroupId"] for group in server.get("SecurityGroups", [])}
    if EXPECTED_SECURITY_GROUP_ID not in server_groups:
        raise ValueError("Sentieon license-server security group is not attached.")

    groups = ec2_client.describe_security_groups(
        GroupIds=[EXPECTED_SECURITY_GROUP_ID]
    ).get("SecurityGroups", [])
    if len(groups) != 1:
        raise ValueError("Unable to resolve the exact Sentieon security group.")
    allowed_cidrs = validate_license_ingress(groups[0].get("IpPermissions", []))

    server_vpc = str(server.get("VpcId") or "")
    client_vpc = str(client.get("VpcId") or "")
    if not server_vpc or not client_vpc:
        raise ValueError("Server and client VPC identities are required.")
    if server_vpc == client_vpc:
        client_ip = ipaddress.ip_address(str(client.get("PrivateIpAddress") or ""))
        if not any(client_ip in ipaddress.ip_network(cidr) for cidr in allowed_cidrs):
            raise ValueError("Same-VPC client private IP is outside the TCP/8990 allowlist.")

    return NetworkEvidence(
        server_vpc_id=server_vpc,
        client_vpc_id=client_vpc,
        allowed_cidrs=allowed_cidrs,
    )


def validate_license_ingress(permissions: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    """Validate that every ingress rule is an explicit IPv4 TCP/8990 CIDR."""

    if not permissions:
        raise ValueError("Sentieon license-server ingress allowlist is empty.")
    cidrs: list[str] = []
    for permission in permissions:
        if (
            permission.get("IpProtocol") != "tcp"
            or permission.get("FromPort") != EXPECTED_PORT
            or permission.get("ToPort") != EXPECTED_PORT
        ):
            raise ValueError("Every Sentieon ingress rule must be TCP/8990 only.")
        if permission.get("Ipv6Ranges"):
            raise ValueError("IPv6 Sentieon license ingress is not approved.")
        if permission.get("UserIdGroupPairs") or permission.get("PrefixListIds"):
            raise ValueError("Sentieon ingress must use explicit observed IPv4 CIDRs.")
        ranges = permission.get("IpRanges") or []
        if not ranges:
            raise ValueError("Sentieon ingress rule has no explicit IPv4 CIDR.")
        for item in ranges:
            network = ipaddress.ip_network(str(item.get("CidrIp") or ""), strict=True)
            if network.version != 4 or network.prefixlen == 0:
                raise ValueError("Publicly open Sentieon license ingress is forbidden.")
            if not network.is_private and network.prefixlen != 32:
                raise ValueError("Public Sentieon client ingress must be an observed /32 NAT IP.")
            cidrs.append(str(network))
    return tuple(sorted(set(cidrs)))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-instance-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        evidence = validate_license_network(
            ec2_client=session.client("ec2"),
            client_instance_id=args.client_instance_id,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "Sentieon license network validated: "
        f"server_vpc={evidence.server_vpc_id} "
        f"client_vpc={evidence.client_vpc_id} "
        f"allowed_cidrs={','.join(evidence.allowed_cidrs)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
