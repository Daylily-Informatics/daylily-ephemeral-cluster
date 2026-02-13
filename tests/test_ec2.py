"""Tests for daylily_ec.aws.ec2 — CP-009 subnet and policy selection."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from daylily_ec.aws.ec2 import (
    PCLUSTER_TAGS_POLICY_NAME,
    PRIVATE_SUBNET_TAG_FILTER,
    PUBLIC_SUBNET_TAG_FILTER,
    SubnetInfo,
    inspect_baseline_subnets,
    list_pcluster_tags_budget_policies,
    list_private_subnets,
    list_public_subnets,
    list_subnets,
    make_subnet_policy_preflight_step,
    select_policy_arn,
    select_subnet,
)
from daylily_ec.state.models import CheckStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ec2_client(subnets=None):
    """Return a mock EC2 client with paginated describe_subnets."""
    client = MagicMock()
    paginator = MagicMock()
    client.get_paginator.return_value = paginator
    paginator.paginate.return_value = [{"Subnets": subnets or []}]
    return client


def _make_subnet(subnet_id, name, az="us-west-2a", vpc_id="vpc-abc"):
    return {
        "SubnetId": subnet_id,
        "AvailabilityZone": az,
        "VpcId": vpc_id,
        "Tags": [{"Key": "Name", "Value": name}],
    }


def _make_iam_client(policy_names=None):
    """Return a mock IAM client with paginated list_policies."""
    client = MagicMock()
    paginator = MagicMock()
    client.get_paginator.return_value = paginator
    policies = []
    for name in (policy_names or []):
        policies.append({"PolicyName": name, "Arn": f"arn:aws:iam::123456789012:policy/{name}"})
    paginator.paginate.return_value = [{"Policies": policies}]
    return client


# ===================================================================
# TestListSubnets
# ===================================================================


class TestListSubnets:
    def test_filters_by_tag_and_az(self):
        ec2 = _make_ec2_client([
            _make_subnet("subnet-1", "My Public Subnet A", "us-west-2a"),
            _make_subnet("subnet-2", "My Private Subnet A", "us-west-2a"),
            _make_subnet("subnet-3", "Something Else", "us-west-2a"),
        ])
        result = list_subnets(ec2, "us-west-2a", tag_filter="Public Subnet")
        assert len(result) == 1
        assert result[0].subnet_id == "subnet-1"
        assert result[0].name == "My Public Subnet A"

    def test_no_matching_subnets(self):
        ec2 = _make_ec2_client([
            _make_subnet("subnet-1", "Something Else", "us-west-2a"),
        ])
        result = list_subnets(ec2, "us-west-2a", tag_filter="Public Subnet")
        assert result == []

    def test_empty_response(self):
        ec2 = _make_ec2_client([])
        result = list_subnets(ec2, "us-west-2a", tag_filter="Public Subnet")
        assert result == []

    def test_exception_returns_empty(self):
        ec2 = MagicMock()
        ec2.get_paginator.side_effect = Exception("boom")
        result = list_subnets(ec2, "us-west-2a", tag_filter="Public Subnet")
        assert result == []

    def test_multiple_matches(self):
        ec2 = _make_ec2_client([
            _make_subnet("subnet-1", "Public Subnet A", "us-west-2a"),
            _make_subnet("subnet-2", "Public Subnet B", "us-west-2a"),
        ])
        result = list_subnets(ec2, "us-west-2a", tag_filter="Public Subnet")
        assert len(result) == 2

    def test_no_tags(self):
        """Subnet with no tags should be skipped."""
        ec2 = _make_ec2_client([
            {"SubnetId": "subnet-1", "AvailabilityZone": "us-west-2a", "VpcId": "vpc-1"},
        ])
        result = list_subnets(ec2, "us-west-2a", tag_filter="Public Subnet")
        assert result == []


class TestConvenienceFunctions:
    def test_list_public_subnets(self):
        ec2 = _make_ec2_client([
            _make_subnet("subnet-1", "Public Subnet A", "us-west-2a"),
        ])
        result = list_public_subnets(ec2, "us-west-2a")
        assert len(result) == 1

    def test_list_private_subnets(self):
        ec2 = _make_ec2_client([
            _make_subnet("subnet-1", "Private Subnet A", "us-west-2a"),
        ])
        result = list_private_subnets(ec2, "us-west-2a")
        assert len(result) == 1


# ===================================================================
# TestInspectBaselineSubnets
# ===================================================================


class TestInspectBaselineSubnets:
    def test_both_present(self):
        ec2 = _make_ec2_client([
            _make_subnet("subnet-pub", "Public Subnet A", "us-west-2a"),
            _make_subnet("subnet-priv", "Private Subnet A", "us-west-2a"),
        ])
        pub, priv = inspect_baseline_subnets(ec2, "us-west-2a")
        assert len(pub) == 1
        assert len(priv) == 1

    def test_both_missing(self):
        ec2 = _make_ec2_client([])
        pub, priv = inspect_baseline_subnets(ec2, "us-west-2a")
        assert len(pub) == 0
        assert len(priv) == 0

    def test_public_only(self):
        ec2 = _make_ec2_client([
            _make_subnet("subnet-pub", "Public Subnet A", "us-west-2a"),
        ])
        pub, priv = inspect_baseline_subnets(ec2, "us-west-2a")
        assert len(pub) == 1
        assert len(priv) == 0

    def test_private_only(self):
        ec2 = _make_ec2_client([
            _make_subnet("subnet-priv", "Private Subnet A", "us-west-2a"),
        ])
        pub, priv = inspect_baseline_subnets(ec2, "us-west-2a")
        assert len(pub) == 0
        assert len(priv) == 1


# ===================================================================
# TestSelectSubnet
# ===================================================================


class TestSelectSubnet:
    def _candidates(self):
        return [
            SubnetInfo(subnet_id="subnet-aaa", name="Public Subnet A"),
            SubnetInfo(subnet_id="subnet-bbb", name="Public Subnet B"),
        ]

    def test_triplet_set_value_match(self):
        """Triplet USESETVALUE selects matching candidate."""
        result = select_subnet(
            self._candidates(),
            cfg_action="USESETVALUE",
            cfg_set_value="subnet-bbb",
        )
        assert result == "subnet-bbb"

    def test_triplet_set_value_no_match(self):
        """Triplet USESETVALUE with non-matching value falls through."""
        result = select_subnet(
            self._candidates(),
            cfg_action="USESETVALUE",
            cfg_set_value="subnet-zzz",
        )
        # Falls through to no auto-select (2 candidates), returns None
        assert result is None

    def test_single_candidate_auto_select(self):
        result = select_subnet(
            [SubnetInfo(subnet_id="subnet-only", name="Public Subnet A")],
        )
        assert result == "subnet-only"

    def test_single_candidate_auto_select_disabled(self):
        with patch.dict(os.environ, {"DAY_DISABLE_AUTO_SELECT": "1"}):
            result = select_subnet(
                [SubnetInfo(subnet_id="subnet-only", name="Public Subnet A")],
            )
        assert result is None

    def test_cfg_fallback(self):
        result = select_subnet(
            self._candidates(),
            cfg_fallback="subnet-aaa",
        )
        assert result == "subnet-aaa"

    def test_cfg_fallback_no_match(self):
        result = select_subnet(
            self._candidates(),
            cfg_fallback="subnet-zzz",
        )
        assert result is None

    def test_empty_candidates(self):
        result = select_subnet([])
        assert result is None

    def test_precedence_triplet_over_single(self):
        """Triplet set_value takes precedence over single auto-select."""
        result = select_subnet(
            [SubnetInfo(subnet_id="subnet-only", name="X")],
            cfg_action="USESETVALUE",
            cfg_set_value="subnet-only",
        )
        assert result == "subnet-only"

    def test_precedence_single_over_fallback(self):
        """Single auto-select takes precedence over config fallback."""
        cands = [SubnetInfo(subnet_id="subnet-only", name="X")]
        result = select_subnet(cands, cfg_fallback="subnet-only")
        # Single auto-select fires first
        assert result == "subnet-only"

    def test_day_disable_auto_select_triplet_still_disabled(self):
        """When DAY_DISABLE_AUTO_SELECT=1, triplet should_auto_apply returns False."""
        with patch.dict(os.environ, {"DAY_DISABLE_AUTO_SELECT": "1"}):
            result = select_subnet(
                self._candidates(),
                cfg_action="USESETVALUE",
                cfg_set_value="subnet-aaa",
            )
        # Falls through to cfg_fallback (empty), returns None
        assert result is None


# ===================================================================
# TestListPclusterTagsBudgetPolicies
# ===================================================================


class TestListPclusterTagsBudgetPolicies:
    def test_finds_matching_policies(self):
        iam = _make_iam_client([PCLUSTER_TAGS_POLICY_NAME])
        result = list_pcluster_tags_budget_policies(iam)
        assert len(result) == 1
        assert PCLUSTER_TAGS_POLICY_NAME in result[0]

    def test_no_matching_policies(self):
        iam = _make_iam_client(["SomeOtherPolicy"])
        result = list_pcluster_tags_budget_policies(iam)
        assert result == []

    def test_multiple_matching_policies(self):
        iam = _make_iam_client([
            PCLUSTER_TAGS_POLICY_NAME,
            PCLUSTER_TAGS_POLICY_NAME,
        ])
        result = list_pcluster_tags_budget_policies(iam)
        assert len(result) == 2

    def test_exception_returns_empty(self):
        iam = MagicMock()
        iam.get_paginator.side_effect = Exception("access denied")
        result = list_pcluster_tags_budget_policies(iam)
        assert result == []


# ===================================================================
# TestSelectPolicyArn
# ===================================================================


class TestSelectPolicyArn:
    def _candidates(self):
        return [
            "arn:aws:iam::123456789012:policy/pclusterTagsAndBudget",
            "arn:aws:iam::123456789012:policy/pclusterTagsAndBudget2",
        ]

    def test_triplet_set_value_match(self):
        arns = self._candidates()
        result = select_policy_arn(arns, cfg_action="USESETVALUE", cfg_set_value=arns[1])
        assert result == arns[1]

    def test_triplet_set_value_no_match(self):
        result = select_policy_arn(
            self._candidates(),
            cfg_action="USESETVALUE",
            cfg_set_value="arn:aws:iam::999:policy/nope",
        )
        assert result is None

    def test_single_candidate_auto_select(self):
        arn = "arn:aws:iam::123456789012:policy/pclusterTagsAndBudget"
        result = select_policy_arn([arn])
        assert result == arn

    def test_single_candidate_auto_select_disabled(self):
        arn = "arn:aws:iam::123456789012:policy/pclusterTagsAndBudget"
        with patch.dict(os.environ, {"DAY_DISABLE_AUTO_SELECT": "1"}):
            result = select_policy_arn([arn])
        assert result is None

    def test_cfg_fallback(self):
        arns = self._candidates()
        result = select_policy_arn(arns, cfg_fallback=arns[0])
        assert result == arns[0]

    def test_cfg_fallback_no_match(self):
        result = select_policy_arn(self._candidates(), cfg_fallback="arn:nope")
        assert result is None

    def test_empty_candidates(self):
        result = select_policy_arn([])
        assert result is None


# ===================================================================
# TestMakeSubnetPolicyPreflightStep
# ===================================================================


class TestMakeSubnetPolicyPreflightStep:
    def _ec2_with_both(self):
        return _make_ec2_client([
            _make_subnet("subnet-pub", "Public Subnet A", "us-west-2a"),
            _make_subnet("subnet-priv", "Private Subnet A", "us-west-2a"),
        ])

    def _iam_with_policy(self):
        return _make_iam_client([PCLUSTER_TAGS_POLICY_NAME])

    def test_all_auto_selected_pass(self):
        """Single pub, single priv, single policy → PASS."""
        ec2 = _make_ec2_client([
            _make_subnet("subnet-pub", "Public Subnet A", "us-west-2a"),
            _make_subnet("subnet-priv", "Private Subnet A", "us-west-2a"),
        ])
        iam = self._iam_with_policy()
        result = make_subnet_policy_preflight_step(ec2, iam, "us-west-2a")
        assert result.id == "ec2.subnet_policy_selection"
        assert result.status == CheckStatus.PASS
        assert result.details["public_subnet_selected"] == "subnet-pub"
        assert result.details["private_subnet_selected"] == "subnet-priv"
        assert result.details["policy_arn_selected"] != ""

    def test_both_missing_warn(self):
        """No subnets at all → WARN (caller should create stack)."""
        ec2 = _make_ec2_client([])
        iam = self._iam_with_policy()
        result = make_subnet_policy_preflight_step(ec2, iam, "us-west-2a")
        assert result.status == CheckStatus.WARN
        assert result.details["baseline_status"] == "both_missing"

    def test_partial_missing_fail(self):
        """Only public subnet → FAIL."""
        ec2 = _make_ec2_client([
            _make_subnet("subnet-pub", "Public Subnet A", "us-west-2a"),
        ])
        iam = self._iam_with_policy()
        result = make_subnet_policy_preflight_step(ec2, iam, "us-west-2a")
        assert result.status == CheckStatus.FAIL
        assert "private_missing" in result.details["baseline_status"]

    def test_no_policy_warn(self):
        """Subnets exist but no policy → WARN."""
        ec2 = self._ec2_with_both()
        iam = _make_iam_client([])  # no matching policy
        result = make_subnet_policy_preflight_step(ec2, iam, "us-west-2a")
        assert result.status == CheckStatus.WARN
        assert "policy_arn_selected" in result.details
        assert result.details["policy_arn_selected"] == ""

    def test_triplet_override(self):
        """Triplet config overrides auto-select for subnets and policy."""
        ec2 = _make_ec2_client([
            _make_subnet("subnet-pub1", "Public Subnet A", "us-west-2a"),
            _make_subnet("subnet-pub2", "Public Subnet B", "us-west-2a"),
            _make_subnet("subnet-priv1", "Private Subnet A", "us-west-2a"),
            _make_subnet("subnet-priv2", "Private Subnet B", "us-west-2a"),
        ])
        # Two policies
        iam = MagicMock()
        pag = MagicMock()
        iam.get_paginator.return_value = pag
        pag.paginate.return_value = [{"Policies": [
            {"PolicyName": PCLUSTER_TAGS_POLICY_NAME, "Arn": "arn:policy1"},
            {"PolicyName": PCLUSTER_TAGS_POLICY_NAME, "Arn": "arn:policy2"},
        ]}]
        result = make_subnet_policy_preflight_step(
            ec2, iam, "us-west-2a",
            pub_cfg_action="USESETVALUE",
            pub_cfg_set_value="subnet-pub2",
            priv_cfg_action="USESETVALUE",
            priv_cfg_set_value="subnet-priv2",
            iam_cfg_action="USESETVALUE",
            iam_cfg_set_value="arn:policy2",
        )
        assert result.status == CheckStatus.PASS
        assert result.details["public_subnet_selected"] == "subnet-pub2"
        assert result.details["private_subnet_selected"] == "subnet-priv2"
        assert result.details["policy_arn_selected"] == "arn:policy2"

    def test_multiple_candidates_no_config_warn(self):
        """Multiple candidates + no config → WARN (prompt needed)."""
        ec2 = _make_ec2_client([
            _make_subnet("subnet-pub1", "Public Subnet A", "us-west-2a"),
            _make_subnet("subnet-pub2", "Public Subnet B", "us-west-2a"),
            _make_subnet("subnet-priv1", "Private Subnet A", "us-west-2a"),
        ])
        iam = self._iam_with_policy()
        result = make_subnet_policy_preflight_step(ec2, iam, "us-west-2a")
        # pub has 2 candidates → can't auto-select → WARN
        assert result.status == CheckStatus.WARN
        assert result.details["public_subnet_selected"] == ""

    def test_constants_values(self):
        assert PUBLIC_SUBNET_TAG_FILTER == "Public Subnet"
        assert PRIVATE_SUBNET_TAG_FILTER == "Private Subnet"
        assert PCLUSTER_TAGS_POLICY_NAME == "pclusterTagsAndBudget"
