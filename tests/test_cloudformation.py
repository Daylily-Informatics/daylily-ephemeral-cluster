"""Tests for daylily_ec.aws.cloudformation — CP-008."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from daylily_ec.aws.cloudformation import (
    COMPLETE_STATUSES,
    DEFAULT_TEMPLATE_PATH,
    DIGIT_WORD_MAP,
    IN_PROGRESS_STATUSES,
    PRIVATE_SUBNET_CIDR,
    PUBLIC_SUBNET_CIDR,
    TAGS_AND_BUDGET_POLICY_NAME,
    VPC_CIDR,
    StackOutputs,
    check_tags_budget_policy_exists,
    derive_resource_prefix,
    derive_stack_name,
    describe_stack_status,
    ensure_pcluster_env_stack,
    get_stack_outputs,
    make_cfn_preflight_step,
)
from daylily_ec.state.models import CheckStatus, PreflightReport


# ===================================================================
# derive_stack_name
# ===================================================================


class TestDeriveStackName:
    """Exact Bash parity: pcluster-vpc-stack-<3rd dash field>."""

    def test_us_west_2a(self):
        assert derive_stack_name("us-west-2a") == "pcluster-vpc-stack-2a"

    def test_us_east_1b(self):
        assert derive_stack_name("us-east-1b") == "pcluster-vpc-stack-1b"

    def test_eu_west_1c(self):
        assert derive_stack_name("eu-west-1c") == "pcluster-vpc-stack-1c"

    def test_ap_southeast_1a(self):
        # ap-southeast-1a has 4 segments: field3 = "1a"
        assert derive_stack_name("ap-southeast-1a") == "pcluster-vpc-stack-1a"

    def test_too_few_segments_raises(self):
        with pytest.raises(ValueError, match="at least 3"):
            derive_stack_name("us")

    def test_two_segments_raises(self):
        with pytest.raises(ValueError, match="at least 3"):
            derive_stack_name("us-west")


# ===================================================================
# derive_resource_prefix
# ===================================================================


class TestDeriveResourcePrefix:
    """Exact Bash parity: daylily-cs-<az> with digit-to-word."""

    def test_us_west_2a(self):
        assert derive_resource_prefix("us-west-2a") == "daylily-cs-us-west-twoa"

    def test_us_east_1a(self):
        assert derive_resource_prefix("us-east-1a") == "daylily-cs-us-east-onea"

    def test_eu_west_3b(self):
        assert derive_resource_prefix("eu-west-3b") == "daylily-cs-eu-west-threeb"

    def test_ap_southeast_4c(self):
        assert (
            derive_resource_prefix("ap-southeast-4c")
            == "daylily-cs-ap-southeast-fourc"
        )

    def test_digit_5_unchanged(self):
        # Only 1-4 are mapped; 5 stays as "5"
        assert derive_resource_prefix("us-west-5a") == "daylily-cs-us-west-5a"

    def test_no_digits(self):
        assert derive_resource_prefix("eu-west-ab") == "daylily-cs-eu-west-ab"

    def test_multiple_digits(self):
        # "us-east-12a": 1→one, 2→two
        assert derive_resource_prefix("us-east-12a") == "daylily-cs-us-east-onetwoa"


# ===================================================================
# check_tags_budget_policy_exists
# ===================================================================


class TestCheckTagsBudgetPolicyExists:
    def _mock_iam(self, policies):
        """Return a mock IAM client with a paginator returning *policies*."""
        page = {"Policies": [{"PolicyName": p} for p in policies]}
        paginator = MagicMock()
        paginator.paginate.return_value = [page]
        client = MagicMock()
        client.get_paginator.return_value = paginator
        return client

    def test_policy_found(self):
        iam = self._mock_iam(["other", TAGS_AND_BUDGET_POLICY_NAME])
        assert check_tags_budget_policy_exists(iam) is True

    def test_policy_not_found(self):
        iam = self._mock_iam(["other", "something-else"])
        assert check_tags_budget_policy_exists(iam) is False

    def test_empty_policies(self):
        iam = self._mock_iam([])
        assert check_tags_budget_policy_exists(iam) is False

    def test_exception_returns_false(self):
        client = MagicMock()
        client.get_paginator.side_effect = RuntimeError("boom")
        assert check_tags_budget_policy_exists(client) is False


# ===================================================================
# get_stack_outputs
# ===================================================================


class TestGetStackOutputs:
    def _mock_cfn(self, outputs):
        client = MagicMock()
        client.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": k, "OutputValue": v}
                        for k, v in outputs.items()
                    ],
                }
            ],
        }
        return client

    def test_partial_outputs(self):
        cfn = self._mock_cfn({"VPC": "vpc-123"})
        out = get_stack_outputs(cfn, "my-stack")
        assert out.vpc_id == "vpc-123"
        assert out.public_subnet_id == ""
        assert out.private_subnet_id == ""
        assert out.policy_arn == ""

    def test_no_stacks(self):
        client = MagicMock()
        client.describe_stacks.return_value = {"Stacks": []}
        out = get_stack_outputs(client, "missing")
        assert out.vpc_id == ""

    def test_exception_returns_empty(self):
        client = MagicMock()
        client.describe_stacks.side_effect = RuntimeError("not found")
        out = get_stack_outputs(client, "missing")
        assert out == StackOutputs()


# ===================================================================
# describe_stack_status
# ===================================================================


class TestDescribeStackStatus:
    def test_returns_status(self):
        client = MagicMock()
        client.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}],
        }
        assert describe_stack_status(client, "my-stack") == "CREATE_COMPLETE"

    def test_no_stacks_returns_none(self):
        client = MagicMock()
        client.describe_stacks.return_value = {"Stacks": []}
        assert describe_stack_status(client, "my-stack") is None

    def test_exception_returns_none(self):
        client = MagicMock()
        client.describe_stacks.side_effect = Exception("gone")
        assert describe_stack_status(client, "my-stack") is None


# ===================================================================
# ensure_pcluster_env_stack
# ===================================================================


def _make_aws_ctx(cfn_client, iam_client):
    """Build a fake AWSContext that returns pre-configured clients."""
    ctx = MagicMock()

    def _client(service, **kwargs):
        if service == "cloudformation":
            return cfn_client
        if service == "iam":
            return iam_client
        raise ValueError(f"unexpected service: {service}")

    ctx.client = _client
    return ctx


class TestEnsurePclusterEnvStack:
    def _cfn_with_status(self, status, outputs=None):
        """Return a mock CFN client reporting *status* on first describe."""
        cfn = MagicMock()
        stacks = [{"StackStatus": status}]
        if outputs:
            stacks[0]["Outputs"] = [
                {"OutputKey": k, "OutputValue": v} for k, v in outputs.items()
            ]
        cfn.describe_stacks.return_value = {"Stacks": stacks}
        return cfn

    def test_skip_if_create_complete(self):
        outputs = {
            "VPC": "vpc-1",
            "PublicSubnets": "sub-p",
            "PrivateSubnet": "sub-v",
            "PclusterPolicy": "arn:p",
        }
        cfn = self._cfn_with_status("CREATE_COMPLETE", outputs)
        iam = MagicMock()
        ctx = _make_aws_ctx(cfn, iam)

        result = ensure_pcluster_env_stack(ctx, "us-west-2a")
        assert result.vpc_id == "vpc-1"
        # create_stack should NOT be called
        cfn.create_stack.assert_not_called()

    def test_skip_if_update_complete(self):
        cfn = self._cfn_with_status("UPDATE_COMPLETE", {"VPC": "vpc-2"})
        iam = MagicMock()
        ctx = _make_aws_ctx(cfn, iam)
        result = ensure_pcluster_env_stack(ctx, "us-east-1a")
        assert result.vpc_id == "vpc-2"
        cfn.create_stack.assert_not_called()

    def test_waits_if_in_progress(self):
        cfn = self._cfn_with_status("CREATE_IN_PROGRESS", {"VPC": "vpc-w"})
        waiter = MagicMock()
        cfn.get_waiter.return_value = waiter
        iam = MagicMock()
        ctx = _make_aws_ctx(cfn, iam)

        result = ensure_pcluster_env_stack(ctx, "us-west-2a")
        waiter.wait.assert_called_once()
        assert result.vpc_id == "vpc-w"

    def test_creates_stack_when_none_exists(self, tmp_path):
        # describe returns no stack (exception → None status)
        cfn = MagicMock()
        cfn.describe_stacks.side_effect = [
            Exception("does not exist"),  # first call: status check
            Exception("does not exist"),  # second call: during wait
        ]

        # After create, describe returns CREATE_COMPLETE
        def _describe_after_create(**kwargs):
            return {
                "Stacks": [
                    {
                        "StackStatus": "CREATE_COMPLETE",
                        "Outputs": [
                            {"OutputKey": "VPC", "OutputValue": "vpc-new"},
                            {"OutputKey": "PublicSubnets", "OutputValue": "sub-new"},
                            {"OutputKey": "PrivateSubnet", "OutputValue": "priv-new"},
                            {"OutputKey": "PclusterPolicy", "OutputValue": "arn:new"},
                        ],
                    }
                ],
            }

        call_count = [0]

        def _describe_stacks(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise Exception("does not exist")
            return _describe_after_create(**kwargs)

        cfn.describe_stacks.side_effect = _describe_stacks

        waiter = MagicMock()
        cfn.get_waiter.return_value = waiter

        # IAM: policy does not exist
        iam_paginator = MagicMock()
        iam_paginator.paginate.return_value = [{"Policies": []}]
        iam = MagicMock()
        iam.get_paginator.return_value = iam_paginator

        ctx = _make_aws_ctx(cfn, iam)

        # Write a fake template
        tpl = tmp_path / "template.yml"
        tpl.write_text("AWSTemplateFormatVersion: '2010-09-09'\n")

        result = ensure_pcluster_env_stack(
            ctx, "us-west-2a", template_path=str(tpl),
        )
        cfn.create_stack.assert_called_once()
        call_args = cfn.create_stack.call_args
        params = {
            p["ParameterKey"]: p["ParameterValue"]
            for p in call_args.kwargs.get("Parameters", call_args[1].get("Parameters", []))
        }
        assert params["CreatePolicy"] == "true"
        assert params["AvailabilityZone"] == "us-west-2a"
        assert params["EnvironmentName"] == "daylily-cs-us-west-twoa"
        assert result.vpc_id == "vpc-new"

    def test_create_policy_false_when_exists(self, tmp_path):
        cfn = MagicMock()
        call_count = [0]

        def _describe(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise Exception("nope")
            return {
                "Stacks": [
                    {
                        "StackStatus": "CREATE_COMPLETE",
                        "Outputs": [{"OutputKey": "VPC", "OutputValue": "vpc-x"}],
                    }
                ],
            }

        cfn.describe_stacks.side_effect = _describe
        waiter = MagicMock()
        cfn.get_waiter.return_value = waiter

        # IAM: policy exists
        iam_paginator = MagicMock()
        iam_paginator.paginate.return_value = [
            {"Policies": [{"PolicyName": TAGS_AND_BUDGET_POLICY_NAME}]},
        ]
        iam = MagicMock()
        iam.get_paginator.return_value = iam_paginator

        ctx = _make_aws_ctx(cfn, iam)
        tpl = tmp_path / "t.yml"
        tpl.write_text("template\n")

        ensure_pcluster_env_stack(ctx, "us-east-1a", template_path=str(tpl))
        call_args = cfn.create_stack.call_args
        params = {
            p["ParameterKey"]: p["ParameterValue"]
            for p in call_args.kwargs.get("Parameters", call_args[1].get("Parameters", []))
        }
        assert params["CreatePolicy"] == "false"

    def test_template_not_found_raises(self):
        cfn = MagicMock()
        cfn.describe_stacks.side_effect = Exception("none")
        iam = MagicMock()
        ctx = _make_aws_ctx(cfn, iam)
        with pytest.raises(FileNotFoundError, match="CFN template not found"):
            ensure_pcluster_env_stack(
                ctx, "us-west-2a", template_path="/no/such/file.yml",
            )


# ===================================================================
# make_cfn_preflight_step
# ===================================================================


class TestMakeCfnPreflightStep:
    def test_pass_on_success(self):
        outputs = StackOutputs(
            vpc_id="vpc-ok",
            public_subnet_id="sub-pub",
            private_subnet_id="sub-priv",
            policy_arn="arn:pol",
        )
        with patch(
            "daylily_ec.aws.cloudformation.ensure_pcluster_env_stack",
            return_value=outputs,
        ):
            step = make_cfn_preflight_step(MagicMock(), "us-west-2a")
            report = PreflightReport()
            step(report)

        assert len(report.checks) == 1
        assert report.checks[0].id == "cfn.baseline_stack"
        assert report.checks[0].status == CheckStatus.PASS
        assert report.checks[0].details["vpc_id"] == "vpc-ok"

    def test_fail_on_error(self):
        with patch(
            "daylily_ec.aws.cloudformation.ensure_pcluster_env_stack",
            side_effect=RuntimeError("stack kaboom"),
        ):
            step = make_cfn_preflight_step(MagicMock(), "us-west-2a")
            report = PreflightReport()
            step(report)

        assert len(report.checks) == 1
        assert report.checks[0].status == CheckStatus.FAIL
        assert "kaboom" in report.checks[0].details["error"]


# ===================================================================
# Constants sanity checks
# ===================================================================


class TestConstants:
    def test_default_template_path(self):
        assert DEFAULT_TEMPLATE_PATH == "config/day_cluster/pcluster_env.yml"

    def test_cidrs(self):
        assert VPC_CIDR == "10.0.0.0/16"
        assert PUBLIC_SUBNET_CIDR == "10.0.0.0/24"
        assert PRIVATE_SUBNET_CIDR == "10.0.1.0/24"

    def test_digit_word_map_covers_1_to_4(self):
        assert set(DIGIT_WORD_MAP.keys()) == {"1", "2", "3", "4"}

    def test_complete_statuses(self):
        assert "CREATE_COMPLETE" in COMPLETE_STATUSES
        assert "UPDATE_COMPLETE" in COMPLETE_STATUSES

    def test_in_progress_statuses(self):
        assert "CREATE_IN_PROGRESS" in IN_PROGRESS_STATUSES

