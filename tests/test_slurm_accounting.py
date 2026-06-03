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
    scan_slurm_accounting_ec2_candidates,
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


class FakeEc2Paginator:
    def __init__(self, ec2: "FakeEc2") -> None:
        self._ec2 = ec2

    def paginate(self, **kwargs):
        self._ec2.calls.append(("paginate", kwargs))
        yield {
            "Reservations": [
                {"Instances": self._ec2.instances},
            ]
        }


class FakeEc2:
    def __init__(
        self,
        *,
        instances: list[dict[str, object]] | None = None,
        security_groups: list[dict[str, object]] | None = None,
    ) -> None:
        self.instances = instances or []
        self.security_groups = {
            str(group["GroupId"]): group for group in security_groups or []
        }
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_paginator(self, name: str) -> FakeEc2Paginator:
        self.calls.append(("get_paginator", {"name": name}))
        assert name == "describe_instances"
        return FakeEc2Paginator(self)

    def describe_security_groups(self, **kwargs):
        self.calls.append(("describe_security_groups", kwargs))
        return {
            "SecurityGroups": [
                self.security_groups[group_id]
                for group_id in kwargs["GroupIds"]
                if group_id in self.security_groups
            ]
        }


class FakeAwsContext:
    def __init__(self, cfn: FakeCloudFormation, ec2: FakeEc2 | None = None) -> None:
        self._cfn = cfn
        self._ec2 = ec2

    def client(self, service: str):
        if service == "cloudformation":
            return self._cfn
        if service == "ec2" and self._ec2 is not None:
            return self._ec2
        raise AssertionError(service)


def _instance(
    instance_id: str,
    *,
    tags: list[dict[str, str]] | None = None,
    private_ip: str = "10.0.1.10",
    vpc_id: str = "vpc-123",
    security_groups: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "InstanceId": instance_id,
        "PrivateIpAddress": private_ip,
        "VpcId": vpc_id,
        "Placement": {"AvailabilityZone": "us-west-2b"},
        "Tags": tags or [{"Key": "Name", "Value": "acct-mariadb"}],
        "SecurityGroups": security_groups or [],
    }


def _security_group(
    group_id: str = "sg-mysql",
    *,
    allows_mysql: bool = True,
) -> dict[str, object]:
    return {
        "GroupId": group_id,
        "GroupName": "mysql-sg",
        "Description": "MariaDB server",
        "IpPermissions": (
            [{"IpProtocol": "tcp", "FromPort": 3306, "ToPort": 3306}]
            if allows_mysql
            else []
        ),
    }


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


def test_scan_returns_selectable_dayec_tagged_instance_with_stack_outputs() -> None:
    cfn = FakeCloudFormation([_stack("dayec-slurm-accounting-us-west-2b")])
    ec2 = FakeEc2(
        instances=[
            _instance(
                "i-0123456789abcdef0",
                tags=[
                    {"Key": "Name", "Value": "dayec-slurm-accounting-us-west-2b-mariadb"},
                    {"Key": ACCOUNTING_COMPONENT_TAG_KEY, "Value": ACCOUNTING_COMPONENT_TAG_VALUE},
                    {"Key": ACCOUNTING_VPC_TAG_KEY, "Value": "vpc-123"},
                ],
            )
        ],
    )

    candidates = scan_slurm_accounting_ec2_candidates(
        FakeAwsContext(cfn, ec2),
        region_az="us-west-2b",
        vpc_id="vpc-123",
    )

    assert len(candidates) == 1
    assert candidates[0].selectable is True
    assert candidates[0].db is not None
    assert candidates[0].db.uri == "10.0.1.10:3306"


def test_scan_rejects_wrong_vpc_stack_for_tagged_instance() -> None:
    cfn = FakeCloudFormation([_stack("wrong-vpc", tags=_tags(vpc_id="vpc-other"))])
    ec2 = FakeEc2(
        instances=[
            _instance(
                "i-0123456789abcdef0",
                tags=[
                    {"Key": "Name", "Value": "acct-mariadb"},
                    {"Key": ACCOUNTING_COMPONENT_TAG_KEY, "Value": ACCOUNTING_COMPONENT_TAG_VALUE},
                    {"Key": ACCOUNTING_VPC_TAG_KEY, "Value": "vpc-123"},
                ],
            )
        ],
    )

    candidates = scan_slurm_accounting_ec2_candidates(
        FakeAwsContext(cfn, ec2),
        region_az="us-west-2b",
        vpc_id="vpc-123",
    )

    assert len(candidates) == 1
    assert candidates[0].selectable is False
    assert candidates[0].db is None
    assert "no matching healthy stack outputs" in candidates[0].reason


def test_scan_rejects_missing_stack_outputs_for_tagged_instance() -> None:
    outputs = [
        item for item in _outputs() if item["OutputKey"] != "AccountingPasswordSecretArn"
    ]
    cfn = FakeCloudFormation([_stack("acct", outputs=outputs)])
    ec2 = FakeEc2(
        instances=[
            _instance(
                "i-0123456789abcdef0",
                tags=[
                    {"Key": "Name", "Value": "acct-mariadb"},
                    {"Key": ACCOUNTING_COMPONENT_TAG_KEY, "Value": ACCOUNTING_COMPONENT_TAG_VALUE},
                    {"Key": ACCOUNTING_VPC_TAG_KEY, "Value": "vpc-123"},
                ],
            )
        ],
    )

    candidates = scan_slurm_accounting_ec2_candidates(
        FakeAwsContext(cfn, ec2),
        region_az="us-west-2b",
        vpc_id="vpc-123",
    )

    assert len(candidates) == 1
    assert candidates[0].selectable is False
    assert "AccountingPasswordSecretArn" in candidates[0].reason


def test_scan_reports_broad_mysql_instance_as_non_selectable() -> None:
    ec2 = FakeEc2(
        instances=[
            _instance(
                "i-broad",
                security_groups=[{"GroupId": "sg-mysql", "GroupName": "mysql-sg"}],
            )
        ],
        security_groups=[_security_group()],
    )

    candidates = scan_slurm_accounting_ec2_candidates(
        FakeAwsContext(FakeCloudFormation([]), ec2),
        region_az="us-west-2b",
        vpc_id="vpc-123",
    )

    assert len(candidates) == 1
    assert candidates[0].source == "ec2-advisory"
    assert candidates[0].selectable is False
    assert candidates[0].db is None


def test_scan_empty_when_no_instances_match() -> None:
    candidates = scan_slurm_accounting_ec2_candidates(
        FakeAwsContext(FakeCloudFormation([]), FakeEc2(instances=[])),
        region_az="us-west-2b",
        vpc_id="vpc-123",
    )

    assert candidates == []
