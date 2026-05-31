from __future__ import annotations

import pytest

from daylily_ec.aws.slurm_accounting import (
    ACCOUNTING_COMPONENT_TAG_KEY,
    ACCOUNTING_COMPONENT_TAG_VALUE,
    ACCOUNTING_REGION_AZ_TAG_KEY,
    ACCOUNTING_VPC_TAG_KEY,
    SlurmAccountingError,
    derive_slurm_accounting_stack_name,
    discover_slurm_accounting_dbs,
    ensure_slurm_accounting_db,
)


def _tags(region_az: str = "us-west-2b", vpc_id: str = "vpc-123") -> list[dict[str, str]]:
    return [
        {"Key": ACCOUNTING_COMPONENT_TAG_KEY, "Value": ACCOUNTING_COMPONENT_TAG_VALUE},
        {"Key": ACCOUNTING_REGION_AZ_TAG_KEY, "Value": region_az},
        {"Key": ACCOUNTING_VPC_TAG_KEY, "Value": vpc_id},
    ]


def _outputs(
    *,
    uri: str = "10.0.1.10:3306",
    database_name: str = "dayec_slurm_acct",
    username: str = "slurm_acct",
) -> list[dict[str, str]]:
    return [
        {"OutputKey": "AccountingDbUri", "OutputValue": uri},
        {"OutputKey": "AccountingDbPrivateIp", "OutputValue": "10.0.1.10"},
        {"OutputKey": "AccountingDatabaseName", "OutputValue": database_name},
        {"OutputKey": "AccountingUserName", "OutputValue": username},
        {
            "OutputKey": "AccountingPasswordSecretArn",
            "OutputValue": "arn:aws:secretsmanager:us-west-2:123456789012:secret:acct",
        },
        {"OutputKey": "AccountingClientSecurityGroupId", "OutputValue": "sg-0123456789abcdef0"},
        {"OutputKey": "AccountingInstanceId", "OutputValue": "i-0123456789abcdef0"},
    ]


def _stack(
    name: str,
    *,
    tags: list[dict[str, str]] | None = None,
    status: str = "CREATE_COMPLETE",
    outputs: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "StackName": name,
        "StackStatus": status,
        "Tags": tags if tags is not None else _tags(),
        "Outputs": outputs if outputs is not None else _outputs(),
    }


class FakePaginator:
    def __init__(self, cfn: "FakeCloudFormation") -> None:
        self._cfn = cfn

    def paginate(self, **kwargs):
        self._cfn.calls.append(("paginate", kwargs))
        yield {
            "StackSummaries": [
                {"StackName": name, "StackStatus": stack["StackStatus"]}
                for name, stack in self._cfn.stacks.items()
            ]
        }


class FakeWaiter:
    def __init__(self, cfn: "FakeCloudFormation") -> None:
        self._cfn = cfn

    def wait(self, **kwargs) -> None:
        self._cfn.calls.append(("wait", kwargs))


class FakeCloudFormation:
    def __init__(self, stacks: list[dict[str, object]] | None = None) -> None:
        self.stacks = {str(stack["StackName"]): stack for stack in stacks or []}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_paginator(self, name: str) -> FakePaginator:
        self.calls.append(("get_paginator", {"name": name}))
        assert name == "list_stacks"
        return FakePaginator(self)

    def describe_stacks(self, StackName: str):
        self.calls.append(("describe_stacks", {"StackName": StackName}))
        stack = self.stacks.get(StackName)
        return {"Stacks": [stack] if stack else []}

    def create_stack(self, **kwargs) -> None:
        self.calls.append(("create_stack", kwargs))
        stack_name = str(kwargs["StackName"])
        tags = kwargs.get("Tags", [])
        params = {
            item["ParameterKey"]: item["ParameterValue"]
            for item in kwargs.get("Parameters", [])
        }
        self.stacks[stack_name] = _stack(
            stack_name,
            tags=tags,
            outputs=_outputs(
                database_name=str(params["DatabaseName"]),
                username=str(params["DatabaseUserName"]),
            ),
        )

    def get_waiter(self, name: str) -> FakeWaiter:
        self.calls.append(("get_waiter", {"name": name}))
        assert name == "stack_create_complete"
        return FakeWaiter(self)


class FakeAwsContext:
    def __init__(self, cfn: FakeCloudFormation) -> None:
        self._cfn = cfn

    def client(self, service: str):
        assert service == "cloudformation"
        return self._cfn


def test_derive_slurm_accounting_stack_name() -> None:
    assert (
        derive_slurm_accounting_stack_name("us-west-2b")
        == "dayec-slurm-accounting-us-west-2b"
    )


def test_discovery_filters_to_dayec_tags_for_vpc_and_az() -> None:
    cfn = FakeCloudFormation(
        [
            _stack("untagged", tags=[]),
            _stack("wrong-vpc", tags=_tags(vpc_id="vpc-other")),
            _stack("right-one", tags=_tags()),
        ]
    )

    matches = discover_slurm_accounting_dbs(
        FakeAwsContext(cfn),
        region_az="us-west-2b",
        vpc_id="vpc-123",
    )

    assert [match.stack_name for match in matches] == ["right-one"]


def test_ensure_auto_selects_exactly_one_healthy_stack() -> None:
    cfn = FakeCloudFormation([_stack("dayec-slurm-accounting-us-west-2b")])

    db = ensure_slurm_accounting_db(
        FakeAwsContext(cfn),
        region_az="us-west-2b",
        vpc_id="vpc-123",
        private_subnet_id="subnet-private",
        create_if_missing=False,
    )

    assert db.stack_name == "dayec-slurm-accounting-us-west-2b"
    assert db.uri == "10.0.1.10:3306"


def test_ensure_fails_when_none_exists_without_create() -> None:
    cfn = FakeCloudFormation([])

    with pytest.raises(SlurmAccountingError, match="No DayEC Slurm accounting stack"):
        ensure_slurm_accounting_db(
            FakeAwsContext(cfn),
            region_az="us-west-2b",
            vpc_id="vpc-123",
            private_subnet_id="subnet-private",
            create_if_missing=False,
        )


def test_ensure_fails_on_multiple_matching_stacks() -> None:
    cfn = FakeCloudFormation([_stack("acct-a"), _stack("acct-b")])

    with pytest.raises(SlurmAccountingError, match="Multiple DayEC Slurm accounting stacks"):
        ensure_slurm_accounting_db(
            FakeAwsContext(cfn),
            region_az="us-west-2b",
            vpc_id="vpc-123",
            private_subnet_id="subnet-private",
            create_if_missing=True,
        )


def test_ensure_fails_on_unhealthy_matching_stack() -> None:
    cfn = FakeCloudFormation([_stack("acct", status="ROLLBACK_COMPLETE")])

    with pytest.raises(SlurmAccountingError, match="not healthy"):
        ensure_slurm_accounting_db(
            FakeAwsContext(cfn),
            region_az="us-west-2b",
            vpc_id="vpc-123",
            private_subnet_id="subnet-private",
            create_if_missing=True,
        )


def test_output_validation_requires_all_required_outputs() -> None:
    outputs = [item for item in _outputs() if item["OutputKey"] != "AccountingPasswordSecretArn"]
    cfn = FakeCloudFormation([_stack("acct", outputs=outputs)])

    with pytest.raises(SlurmAccountingError, match="AccountingPasswordSecretArn"):
        ensure_slurm_accounting_db(
            FakeAwsContext(cfn),
            region_az="us-west-2b",
            vpc_id="vpc-123",
            private_subnet_id="subnet-private",
            create_if_missing=False,
        )


def test_create_when_missing_uses_expected_parameters_and_no_destructive_calls() -> None:
    cfn = FakeCloudFormation([])

    db = ensure_slurm_accounting_db(
        FakeAwsContext(cfn),
        region_az="us-west-2b",
        vpc_id="vpc-123",
        private_subnet_id="subnet-private",
        create_if_missing=True,
        database_name="dayec_slurm_acct",
        username="slurm_acct",
        instance_type="t4g.micro",
    )

    create_calls = [kwargs for name, kwargs in cfn.calls if name == "create_stack"]
    assert len(create_calls) == 1
    create_call = create_calls[0]
    assert create_call["StackName"] == "dayec-slurm-accounting-us-west-2b"
    assert create_call["EnableTerminationProtection"] is True
    assert {"Key": ACCOUNTING_VPC_TAG_KEY, "Value": "vpc-123"} in create_call["Tags"]
    assert {"Key": ACCOUNTING_REGION_AZ_TAG_KEY, "Value": "us-west-2b"} in create_call["Tags"]
    assert db.stack_name == "dayec-slurm-accounting-us-west-2b"
    destructive = [
        name
        for name, _kwargs in cfn.calls
        if name.startswith(("delete", "drop", "reset"))
    ]
    assert destructive == []


def test_explicit_stack_name_rejects_untagged_stack() -> None:
    cfn = FakeCloudFormation([_stack("not-dayec", tags=[])])

    with pytest.raises(SlurmAccountingError, match="is not tagged"):
        discover_slurm_accounting_dbs(
            FakeAwsContext(cfn),
            region_az="us-west-2b",
            vpc_id="vpc-123",
            stack_name="not-dayec",
        )
