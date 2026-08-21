from __future__ import annotations

from types import SimpleNamespace

import pytest

from daylily_ec.aws.slurm_accounting_privatelink import (
    SlurmAccountingPrivateLinkError,
)
from daylily_ec.workflow import inspect_slurm_accounting as inspection_module
from daylily_ec.workflow.inspect_slurm_accounting import (
    SLURM_ACCOUNTING_INSPECTION_SCHEMA,
    SlurmAccountingInspectionError,
    inspect_slurm_accounting,
)

PROVIDER_NAME = "dayec-slurm-accounting-us-west-2c"
BRIDGE_NAME = "dayec-sacct-pl-vpc-06b01782f2abece1c"
PROVIDER_VPC = "vpc-0f41176d568ae7b1e"
CONSUMER_VPC = "vpc-06b01782f2abece1c"


class _AwsContext:
    account_id = "123456789012"

    def client(self, service: str):
        assert service == "ec2"
        return self

    def describe_instances(self, *, InstanceIds):
        return {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": instance_id,
                            "InstanceType": "t4g.micro",
                        }
                        for instance_id in InstanceIds
                    ]
                }
            ]
        }


def _provider_stack() -> dict:
    return {
        "StackName": PROVIDER_NAME,
        "StackStatus": "CREATE_COMPLETE",
        "Tags": [
            {"Key": "daylily-ec:component", "Value": "slurm-accounting-mysql"},
            {"Key": "daylily-ec:managed-by", "Value": "daylily-ephemeral-cluster"},
            {"Key": "daylily-ec:region", "Value": "us-west-2"},
            {"Key": "daylily-ec:region-az", "Value": "us-west-2c"},
            {"Key": "daylily-ec:vpc-id", "Value": PROVIDER_VPC},
        ],
        "Outputs": [
            {"OutputKey": "AccountingDbUri", "OutputValue": "10.0.1.7:3306"},
            {"OutputKey": "AccountingDbPrivateIp", "OutputValue": "10.0.1.7"},
            {"OutputKey": "AccountingDatabaseName", "OutputValue": "dayec_slurm_acct"},
            {"OutputKey": "AccountingUserName", "OutputValue": "slurm_acct"},
            {
                "OutputKey": "AccountingPasswordSecretArn",
                "OutputValue": "arn:aws:secretsmanager:us-west-2:123456789012:secret:SENSITIVE",
            },
            {
                "OutputKey": "AccountingClientSecurityGroupId",
                "OutputValue": "sg-provider",
            },
            {
                "OutputKey": "AccountingClientSecretReadPolicyArn",
                "OutputValue": "arn:aws:iam::123456789012:policy/SENSITIVE",
            },
            {"OutputKey": "AccountingInstanceId", "OutputValue": "i-accounting"},
        ],
    }


def _bridge() -> SimpleNamespace:
    return SimpleNamespace(
        stack_name=BRIDGE_NAME,
        status="UPDATE_COMPLETE",
        provider_accounting_stack_name=PROVIDER_NAME,
        provider_vpc_id=PROVIDER_VPC,
        consumer_vpc_id=CONSUMER_VPC,
        database_name="dayec_slurm_acct",
        username="slurm_acct",
        accounting_instance_id="i-accounting",
        password_secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:SENSITIVE",
        uri="vpce-sensitive.internal:3306",
    )


def _patch_context(monkeypatch) -> None:
    monkeypatch.setattr(
        inspection_module.AWSContext,
        "build_region",
        classmethod(lambda _cls, region, profile=None: _AwsContext()),
    )


def test_inspection_reports_exact_bounded_provider_and_bridge_without_secrets(
    monkeypatch,
) -> None:
    _patch_context(monkeypatch)
    bridge_calls: list[dict] = []
    monkeypatch.setattr(
        inspection_module,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [_provider_stack()],
    )

    def resolve_bridge(*_args, **kwargs):
        bridge_calls.append(kwargs)
        return _bridge()

    monkeypatch.setattr(
        inspection_module,
        "resolve_slurm_accounting_privatelink_bridge",
        resolve_bridge,
    )

    result = inspect_slurm_accounting(
        profile="lsmc",
        region_az="us-west-2d",
        expected_accounting_stack_name=PROVIDER_NAME,
        expected_privatelink_stack_name=BRIDGE_NAME,
    )
    payload = result.to_payload()

    assert payload["schema_version"] == SLURM_ACCOUNTING_INSPECTION_SCHEMA
    assert payload["read_only"] is True
    assert payload["aws_profile"] == "lsmc"
    assert payload["aws_account_id"] == "123456789012"
    assert payload["regional_provider_count"] == 1
    assert payload["regional_singleton"] is True
    assert payload["regional_provider_matches_expected"] is True
    assert payload["exact_bridge_resolved"] is True
    assert payload["bridge_provider_matches_expected"] is True
    assert payload["bridge_provider_binding_matches_regional_provider"] is True
    assert payload["exact_bridge"] == {
        "stack_name": BRIDGE_NAME,
        "status": "UPDATE_COMPLETE",
        "provider_accounting_stack_name": PROVIDER_NAME,
        "provider_vpc_id": PROVIDER_VPC,
        "consumer_vpc_id": CONSUMER_VPC,
        "database_name": "dayec_slurm_acct",
        "db_username": "slurm_acct",
        "accounting_instance_id": "i-accounting",
        "accounting_instance_type": "t4g.micro",
        "contract_healthy": True,
    }
    assert payload["regional_providers"][0]["instance_type"] == "t4g.micro"
    assert bridge_calls == [
        {"stack_name": BRIDGE_NAME, "require_healthy_target": False},
        {"stack_name": BRIDGE_NAME, "require_healthy_target": True},
    ]
    rendered = repr(payload)
    assert "SENSITIVE" not in rendered
    assert "vpce-sensitive" not in rendered
    assert "10.0.1.7" not in rendered


def test_inspection_exact_bridge_failure_is_safe_read_only_evidence(monkeypatch) -> None:
    _patch_context(monkeypatch)
    monkeypatch.setattr(
        inspection_module,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [_provider_stack()],
    )
    monkeypatch.setattr(
        inspection_module,
        "resolve_slurm_accounting_privatelink_bridge",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            SlurmAccountingPrivateLinkError("SENSITIVE provider detail")
        ),
    )

    payload = inspect_slurm_accounting(
        profile="lsmc",
        region_az="us-west-2d",
        expected_accounting_stack_name=PROVIDER_NAME,
        expected_privatelink_stack_name=BRIDGE_NAME,
    ).to_payload()

    assert payload["ok"] is True
    assert payload["exact_bridge"] is None
    assert payload["exact_bridge_resolved"] is False
    assert payload["exact_bridge_error_code"] == ("exact_bridge_unavailable_or_incompatible")
    assert payload["bridge_provider_binding_matches_regional_provider"] is None
    assert "SENSITIVE" not in repr(payload)


def test_inspection_reports_exact_bridge_identity_when_target_is_unhealthy(
    monkeypatch,
) -> None:
    _patch_context(monkeypatch)
    monkeypatch.setattr(
        inspection_module,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [_provider_stack()],
    )

    def resolve_bridge(*_args, require_healthy_target, **_kwargs):
        if require_healthy_target:
            raise SlurmAccountingPrivateLinkError("SENSITIVE target detail")
        return _bridge()

    monkeypatch.setattr(
        inspection_module,
        "resolve_slurm_accounting_privatelink_bridge",
        resolve_bridge,
    )

    payload = inspect_slurm_accounting(
        profile="lsmc",
        region_az="us-west-2d",
        expected_accounting_stack_name=PROVIDER_NAME,
        expected_privatelink_stack_name=BRIDGE_NAME,
    ).to_payload()

    assert payload["exact_bridge_resolved"] is True
    assert payload["exact_bridge"]["stack_name"] == BRIDGE_NAME
    assert payload["exact_bridge"]["contract_healthy"] is False
    assert payload["exact_bridge_error_code"] == ("exact_bridge_target_unhealthy_or_unverified")
    assert payload["bridge_provider_binding_matches_regional_provider"] is True
    assert "SENSITIVE" not in repr(payload)


def test_inspection_reports_provider_bridge_binding_mismatch(monkeypatch) -> None:
    _patch_context(monkeypatch)
    provider = _provider_stack()
    for output in provider["Outputs"]:
        if output["OutputKey"] == "AccountingInstanceId":
            output["OutputValue"] = "i-different"
    monkeypatch.setattr(
        inspection_module,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [provider],
    )
    monkeypatch.setattr(
        inspection_module,
        "resolve_slurm_accounting_privatelink_bridge",
        lambda *_args, **_kwargs: _bridge(),
    )

    payload = inspect_slurm_accounting(
        profile="lsmc",
        region_az="us-west-2d",
        expected_accounting_stack_name=PROVIDER_NAME,
        expected_privatelink_stack_name=BRIDGE_NAME,
    ).to_payload()

    assert payload["exact_bridge_resolved"] is True
    assert payload["bridge_provider_matches_expected"] is True
    assert payload["bridge_provider_binding_matches_regional_provider"] is False


@pytest.mark.parametrize(
    "unsafe_name",
    ("x" * 257, "provider-\N{SNOWMAN}"),
)
def test_inspection_rejects_unbounded_or_non_ascii_provider_identity(
    monkeypatch,
    unsafe_name,
) -> None:
    _patch_context(monkeypatch)
    provider = _provider_stack()
    provider["StackName"] = unsafe_name
    monkeypatch.setattr(
        inspection_module,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [provider],
    )

    with pytest.raises(SlurmAccountingInspectionError, match="bounded identity"):
        inspect_slurm_accounting(profile="lsmc", region_az="us-west-2d")


def test_inspection_fails_closed_when_provider_instance_type_is_unavailable(
    monkeypatch,
) -> None:
    class _MissingInstanceContext(_AwsContext):
        def describe_instances(self, *, InstanceIds):
            _ = InstanceIds
            return {"Reservations": []}

    monkeypatch.setattr(
        inspection_module.AWSContext,
        "build_region",
        classmethod(lambda _cls, region, profile=None: _MissingInstanceContext()),
    )
    monkeypatch.setattr(
        inspection_module,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [_provider_stack()],
    )

    with pytest.raises(SlurmAccountingInspectionError, match="incomplete"):
        inspect_slurm_accounting(profile="lsmc", region_az="us-west-2d")


def test_inspection_does_not_resolve_any_bridge_without_exact_name(monkeypatch) -> None:
    _patch_context(monkeypatch)
    monkeypatch.setattr(
        inspection_module,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [_provider_stack()],
    )
    monkeypatch.setattr(
        inspection_module,
        "resolve_slurm_accounting_privatelink_bridge",
        lambda *_args, **_kwargs: pytest.fail("no bridge discovery without exact name"),
    )

    payload = inspect_slurm_accounting(
        profile="lsmc",
        region_az="us-west-2d",
        expected_accounting_stack_name=PROVIDER_NAME,
    ).to_payload()

    assert payload["exact_bridge"] is None
    assert payload["exact_bridge_resolved"] is None
    assert payload["expected_privatelink_stack_name"] is None
    assert payload["bridge_provider_binding_matches_regional_provider"] is None


def test_inspection_exposes_duplicate_provider_conflict_without_selecting(monkeypatch) -> None:
    _patch_context(monkeypatch)
    second = _provider_stack()
    second["StackName"] = "dayec-slurm-accounting-us-west-2"
    monkeypatch.setattr(
        inspection_module,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [_provider_stack(), second],
    )
    monkeypatch.setattr(
        inspection_module,
        "resolve_slurm_accounting_privatelink_bridge",
        lambda *_args, **_kwargs: pytest.fail("provider conflict must not select a bridge"),
    )

    payload = inspect_slurm_accounting(
        profile="lsmc",
        region_az="us-west-2d",
        expected_accounting_stack_name=PROVIDER_NAME,
    ).to_payload()

    assert payload["regional_provider_count"] == 2
    assert payload["regional_singleton"] is False
    assert payload["regional_provider_matches_expected"] is False
    assert [item["stack_name"] for item in payload["regional_providers"]] == [
        PROVIDER_NAME,
        "dayec-slurm-accounting-us-west-2",
    ]
