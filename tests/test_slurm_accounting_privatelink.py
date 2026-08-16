from __future__ import annotations

from pathlib import Path

import pytest

from daylily_ec.aws import slurm_accounting_privatelink as privatelink
from daylily_ec.aws.slurm_accounting_privatelink import (
    SlurmAccountingPrivateLinkError,
    derive_privatelink_stack_name,
    ensure_slurm_accounting_privatelink_bridge,
    resolve_slurm_accounting_privatelink_bridge,
    resolve_slurm_accounting_privatelink_bridge_for_consumer,
)


def _bridge_stack() -> dict:
    values = {
        "AccountingClientSecurityGroupId": "sg-client",
        "AccountingClientSecretReadPolicyArn": "arn:aws:iam::123:policy/accounting-client-read",
        "AccountingDatabaseName": "dayec_slurm_acct",
        "AccountingEndpointId": "vpce-123",
        "AccountingEndpointServiceId": "vpce-svc-123",
        "AccountingInstanceId": "i-accounting",
        "AccountingPasswordSecretArn": "arn:aws:secretsmanager:us-west-2:123:secret:acct",
        "AccountingTargetGroupArn": "arn:aws:elasticloadbalancing:targetgroup/accounting",
        "AccountingUserName": "slurm_acct",
        "ConsumerEndpointSubnetId": "subnet-endpoint",
        "ConsumerVpcId": "vpc-consumer",
        "ProviderAccountingStackName": "dayec-slurm-accounting-us-west-2c",
        "ProviderVpcId": "vpc-provider",
    }
    return {
        "StackName": "dayec-sacct-pl-vpc-consumer",
        "StackStatus": "CREATE_COMPLETE",
        "Outputs": [{"OutputKey": key, "OutputValue": value} for key, value in values.items()],
    }


class _Cfn:
    def describe_stacks(self, *, StackName):
        assert StackName == "dayec-sacct-pl-vpc-consumer"
        return {"Stacks": [_bridge_stack()]}


class _Ec2:
    def describe_vpc_endpoints(self, *, VpcEndpointIds):
        assert VpcEndpointIds == ["vpce-123"]
        return {
            "VpcEndpoints": [
                {
                    "State": "available",
                    "DnsEntries": [
                        {"DnsName": "vpce-123.vpce-svc-123.us-west-2.vpce.amazonaws.com"}
                    ],
                    "NetworkInterfaceIds": ["eni-endpoint"],
                }
            ]
        }

    def describe_network_interfaces(self, *, NetworkInterfaceIds):
        assert NetworkInterfaceIds == ["eni-endpoint"]
        return {"NetworkInterfaces": [{"PrivateIpAddress": "10.0.2.4"}]}


class _Elbv2:
    def describe_target_health(self, *, TargetGroupArn):
        assert TargetGroupArn.endswith("targetgroup/accounting")
        return {"TargetHealthDescriptions": [{"TargetHealth": {"State": "healthy"}}]}


class _Context:
    def client(self, service: str):
        return {"cloudformation": _Cfn(), "ec2": _Ec2(), "elbv2": _Elbv2()}[service]


def test_bridge_resolves_to_redacted_accounting_db() -> None:
    bridge = resolve_slurm_accounting_privatelink_bridge(
        _Context(),
        stack_name="dayec-sacct-pl-vpc-consumer",
    )
    db = bridge.as_accounting_db()

    assert db.uri.endswith(":3306")
    assert db.client_security_group_id == "sg-client"
    assert db.client_secret_read_policy_arn.endswith("accounting-client-read")
    assert bridge.password_secret_arn not in repr(bridge)
    assert bridge.uri not in repr(bridge)
    assert db.password_secret_arn not in repr(db)


def test_derive_bridge_name_requires_real_vpc_id() -> None:
    assert derive_privatelink_stack_name("vpc-0123456789abcdef0") == (
        "dayec-sacct-pl-vpc-0123456789abcdef0"
    )
    with pytest.raises(SlurmAccountingPrivateLinkError, match="valid consumer VPC"):
        derive_privatelink_stack_name("consumer-vpc")


def test_consumer_bridge_resolution_uses_exact_deterministic_stack(monkeypatch) -> None:
    consumer_vpc_id = "vpc-0123456789abcdef0"
    calls = []

    class Bridge:
        consumer_vpc_id = "vpc-0123456789abcdef0"
        provider_accounting_stack_name = "dayec-slurm-accounting-us-west-2c"

    bridge = Bridge()

    def resolve(*_args, **kwargs):
        calls.append(kwargs)
        return bridge

    monkeypatch.setattr(
        privatelink,
        "resolve_slurm_accounting_privatelink_bridge",
        resolve,
    )

    result = resolve_slurm_accounting_privatelink_bridge_for_consumer(
        object(),
        consumer_vpc_id=consumer_vpc_id,
        provider_accounting_stack_name="dayec-slurm-accounting-us-west-2c",
    )

    assert result is bridge
    assert calls == [
        {
            "stack_name": "dayec-sacct-pl-vpc-0123456789abcdef0",
            "require_healthy_target": True,
        }
    ]


def test_consumer_bridge_resolution_rejects_provider_mismatch(monkeypatch) -> None:
    class Bridge:
        consumer_vpc_id = "vpc-0123456789abcdef0"
        provider_accounting_stack_name = "different-provider"

    monkeypatch.setattr(
        privatelink,
        "resolve_slurm_accounting_privatelink_bridge",
        lambda *_args, **_kwargs: Bridge(),
    )

    with pytest.raises(SlurmAccountingPrivateLinkError, match="provider"):
        resolve_slurm_accounting_privatelink_bridge_for_consumer(
            object(),
            consumer_vpc_id="vpc-0123456789abcdef0",
            provider_accounting_stack_name="dayec-slurm-accounting-us-west-2c",
        )


def test_ensure_updates_existing_stack_and_allows_its_owned_subnet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = _bridge_stack()
    existing["Tags"] = [
        {"Key": "daylily-ec:component", "Value": "slurm-accounting-privatelink"},
        {"Key": "daylily-ec:managed-by", "Value": "daylily-ephemeral-cluster"},
        {
            "Key": "daylily-ec:provider-accounting-stack",
            "Value": "dayec-slurm-accounting-us-west-2c",
        },
        {"Key": "daylily-ec:consumer-vpc-id", "Value": "vpc-consumer"},
    ]

    class _Waiter:
        def wait(self, **kwargs):
            assert kwargs == {"StackName": "dayec-sacct-pl-vpc-consumer"}

    class _UpdateCfn:
        def __init__(self):
            self.update_calls = []

        def describe_stacks(self, *, StackName):
            assert StackName == "dayec-sacct-pl-vpc-consumer"
            return {"Stacks": [existing]}

        def update_stack(self, **kwargs):
            self.update_calls.append(kwargs)

        def get_waiter(self, name):
            assert name == "stack_update_complete"
            return _Waiter()

    cfn = _UpdateCfn()

    class _EnsureContext:
        region = "us-west-2"

        def client(self, service):
            return {"cloudformation": cfn, "ec2": object()}[service]

    provider = privatelink._Provider(
        stack_name="dayec-slurm-accounting-us-west-2c",
        vpc_id="vpc-provider",
        subnet_id="subnet-provider",
        availability_zone="us-west-2c",
        database_private_ip="10.0.1.237",
        database_security_group_id="sg-database",
        database_name="dayec_slurm_acct",
        username="slurm_acct",
        password_secret_arn="arn:aws:secretsmanager:us-west-2:123:secret:acct",
        instance_id="i-accounting",
    )
    validation = {}
    sentinel = object()
    monkeypatch.setattr(privatelink, "_resolve_provider", lambda *args: provider)
    monkeypatch.setattr(
        privatelink,
        "_validate_consumer_network",
        lambda _ec2, **kwargs: validation.update(kwargs),
    )
    monkeypatch.setattr(privatelink, "_read_template", lambda _path: "Resources: {}")
    monkeypatch.setattr(
        privatelink,
        "_wait_for_healthy_bridge",
        lambda *_args, **_kwargs: sentinel,
    )

    result = ensure_slurm_accounting_privatelink_bridge(
        _EnsureContext(),
        provider_accounting_stack_name="dayec-slurm-accounting-us-west-2c",
        consumer_vpc_id="vpc-consumer",
        consumer_endpoint_subnet_cidr="10.0.2.0/28",
        stack_name="dayec-sacct-pl-vpc-consumer",
    )

    assert result is sentinel
    assert validation["allowed_existing_subnet_id"] == "subnet-endpoint"
    assert cfn.update_calls[0]["TemplateBody"] == "Resources: {}"
    assert cfn.update_calls[0]["Capabilities"] == ["CAPABILITY_IAM"]


def test_packaged_and_repo_templates_match() -> None:
    root = Path(__file__).resolve().parents[1]
    repo = root / "config/day_cluster/slurm_accounting_privatelink.yml"
    packaged = (
        root / "daylily_ec/resources/payload/config/day_cluster/slurm_accounting_privatelink.yml"
    )
    assert repo.read_bytes() == packaged.read_bytes()
    text = repo.read_text(encoding="utf-8")
    assert 'EnforceSecurityGroupInboundRulesOnPrivateLinkTraffic: "off"' in text
    assert "ConsumerEndpointToClientEgress:" in text
    assert "DestinationSecurityGroupId: !Ref ConsumerClientSecurityGroup" in text
    assert "Port: 3306" in text
    assert "AcceptanceRequired: false" in text
    assert "arn:${AWS::Partition}:iam::${AWS::AccountId}:root" in text
    assert "AccountingClientSecretReadPolicyArn:" in text
    assert "secretsmanager:GetSecretValue" in text
