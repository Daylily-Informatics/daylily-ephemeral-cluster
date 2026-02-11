"""Tests for daylily_ec.aws.iam — CP-007 IAM Policy Checks and Ensurers."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from daylily_ec.aws.iam import (
    CREATE_SCHEDULER_SCRIPT,
    GLOBAL_POLICY_NAME,
    HEARTBEAT_DEFAULT_ROLE_NAMES,
    HEARTBEAT_ROLE_ENV_VARS,
    PCLUSTER_OMICS_POLICY_DOCUMENT,
    PCLUSTER_OMICS_POLICY_NAME,
    REGIONAL_POLICY_PREFIX,
    check_daylily_policies,
    check_policy_attached,
    ensure_pcluster_omics_policy,
    make_iam_preflight_step,
    resolve_scheduler_role,
)
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iam_client(
    *,
    user_policies=None,
    groups=None,
    group_policies=None,
    list_policies_pages=None,
    create_policy_resp=None,
    create_policy_error=None,
    get_role_responses=None,
):
    """Build a mock IAM client with configurable responses."""
    client = MagicMock()

    # list_attached_user_policies
    client.list_attached_user_policies.return_value = {
        "AttachedPolicies": user_policies or [],
    }

    # list_groups_for_user
    client.list_groups_for_user.return_value = {
        "Groups": [{"GroupName": g} for g in (groups or [])],
    }

    # list_attached_group_policies — keyed by group name
    gp = group_policies or {}

    def _group_policies_side_effect(GroupName=""):
        return {"AttachedPolicies": gp.get(GroupName, [])}

    client.list_attached_group_policies.side_effect = _group_policies_side_effect

    # Paginator for list_policies
    if list_policies_pages is not None:
        paginator = MagicMock()
        paginator.paginate.return_value = list_policies_pages
        client.get_paginator.return_value = paginator
    else:
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Policies": []}]
        client.get_paginator.return_value = paginator

    # create_policy
    if create_policy_error:
        client.create_policy.side_effect = create_policy_error
    elif create_policy_resp:
        client.create_policy.return_value = create_policy_resp
    else:
        client.create_policy.return_value = {
            "Policy": {"Arn": "arn:aws:iam::123456789012:policy/test", "PolicyName": "test"},
        }

    # get_role — keyed by role name
    if get_role_responses is not None:

        def _get_role_side_effect(RoleName=""):
            if RoleName in get_role_responses:
                return get_role_responses[RoleName]
            raise Exception(f"NoSuchEntity: {RoleName}")

        client.get_role.side_effect = _get_role_side_effect
    else:
        client.get_role.side_effect = Exception("NoSuchEntity")

    return client


def _aws_ctx(*, region="us-west-2", iam_username="testuser", iam_client=None):
    """Build a mock AWSContext."""
    ctx = MagicMock()
    ctx.region = region
    ctx.iam_username = iam_username
    ctx.profile = "test-profile"
    if iam_client:
        ctx.client.return_value = iam_client
    else:
        ctx.client.return_value = _iam_client()
    return ctx


# ===========================================================================
# check_policy_attached
# ===========================================================================


class TestCheckPolicyAttached:
    def test_user_attached(self):
        """Policy attached directly to user → True."""
        iam = _iam_client(user_policies=[{"PolicyName": "MyPolicy"}])
        assert check_policy_attached(iam, "alice", "MyPolicy") is True

    def test_group_attached(self):
        """Policy attached via group → True."""
        iam = _iam_client(
            groups=["devs"],
            group_policies={"devs": [{"PolicyName": "MyPolicy"}]},
        )
        assert check_policy_attached(iam, "alice", "MyPolicy") is True

    def test_not_attached(self):
        """Policy not attached at all → False."""
        iam = _iam_client()
        assert check_policy_attached(iam, "alice", "MyPolicy") is False

    def test_different_policy_name(self):
        """Different policy name → False."""
        iam = _iam_client(user_policies=[{"PolicyName": "OtherPolicy"}])
        assert check_policy_attached(iam, "alice", "MyPolicy") is False

    def test_multiple_groups_second_has_policy(self):
        """Policy found in second group → True."""
        iam = _iam_client(
            groups=["group1", "group2"],
            group_policies={
                "group1": [{"PolicyName": "Unrelated"}],
                "group2": [{"PolicyName": "TargetPolicy"}],
            },
        )
        assert check_policy_attached(iam, "bob", "TargetPolicy") is True

    def test_user_api_error_falls_through_to_groups(self):
        """Error on user policies → still checks groups."""
        iam = _iam_client(
            groups=["devs"],
            group_policies={"devs": [{"PolicyName": "MyPolicy"}]},
        )
        iam.list_attached_user_policies.side_effect = Exception("AccessDenied")
        assert check_policy_attached(iam, "alice", "MyPolicy") is True

    def test_group_api_error_returns_false(self):
        """Error on both user and group queries → False."""
        iam = _iam_client()
        iam.list_attached_user_policies.side_effect = Exception("err")
        iam.list_groups_for_user.side_effect = Exception("err")
        assert check_policy_attached(iam, "alice", "MyPolicy") is False


# ===========================================================================
# check_daylily_policies
# ===========================================================================


class TestCheckDaylilyPolicies:
    def test_both_attached(self):
        """Both global and regional policies found → two PASS."""
        iam = _iam_client(
            user_policies=[
                {"PolicyName": GLOBAL_POLICY_NAME},
                {"PolicyName": f"{REGIONAL_POLICY_PREFIX}-us-west-2"},
            ],
        )
        results = check_daylily_policies(iam, "alice", "us-west-2")
        assert len(results) == 2
        assert all(r.status == CheckStatus.PASS for r in results)

    def test_both_missing_non_interactive(self):
        """Both missing, non-interactive → two FAIL."""
        iam = _iam_client()
        results = check_daylily_policies(iam, "alice", "us-west-2", interactive=False)
        assert len(results) == 2
        assert all(r.status == CheckStatus.FAIL for r in results)

    def test_both_missing_interactive(self):
        """Both missing, interactive → two WARN."""
        iam = _iam_client()
        results = check_daylily_policies(iam, "alice", "us-west-2", interactive=True)
        assert len(results) == 2
        assert all(r.status == CheckStatus.WARN for r in results)

    def test_global_missing_regional_present(self):
        """Global missing, regional present → FAIL + PASS."""
        iam = _iam_client(
            user_policies=[
                {"PolicyName": f"{REGIONAL_POLICY_PREFIX}-eu-west-1"},
            ],
        )
        results = check_daylily_policies(iam, "alice", "eu-west-1")
        assert results[0].status == CheckStatus.FAIL  # global
        assert results[1].status == CheckStatus.PASS  # regional

    def test_check_ids(self):
        """Check IDs are iam.policy.global and iam.policy.regional."""
        iam = _iam_client(
            user_policies=[
                {"PolicyName": GLOBAL_POLICY_NAME},
                {"PolicyName": f"{REGIONAL_POLICY_PREFIX}-us-east-1"},
            ],
        )
        results = check_daylily_policies(iam, "alice", "us-east-1")
        assert results[0].id == "iam.policy.global"
        assert results[1].id == "iam.policy.regional"

    def test_remediation_includes_bootstrap_commands(self):
        """Remediation mentions the correct bootstrap scripts."""
        iam = _iam_client()
        results = check_daylily_policies(iam, "bob", "us-west-2")
        assert "bootstrap_global" in results[0].remediation
        assert "bootstrap_region" in results[1].remediation
        assert "--user bob" in results[0].remediation
        assert "--region us-west-2" in results[1].remediation

    def test_group_attached_policy_detected(self):
        """Policy attached via group is detected."""
        iam = _iam_client(
            groups=["daylily-users"],
            group_policies={
                "daylily-users": [
                    {"PolicyName": GLOBAL_POLICY_NAME},
                    {"PolicyName": f"{REGIONAL_POLICY_PREFIX}-us-west-2"},
                ],
            },
        )
        results = check_daylily_policies(iam, "alice", "us-west-2")
        assert all(r.status == CheckStatus.PASS for r in results)


# ===========================================================================
# ensure_pcluster_omics_policy
# ===========================================================================


class TestEnsurePclusterOmicsPolicy:
    def test_already_exists(self):
        """Policy exists → PASS with action=already_exists."""
        iam = _iam_client(
            list_policies_pages=[
                {
                    "Policies": [
                        {
                            "PolicyName": PCLUSTER_OMICS_POLICY_NAME,
                            "Arn": "arn:aws:iam::123:policy/pcluster-omics-analysis",
                        }
                    ],
                }
            ],
        )
        result = ensure_pcluster_omics_policy(iam)
        assert result.status == CheckStatus.PASS
        assert result.details["action"] == "already_exists"
        assert result.id == "iam.pcluster_omics_policy"
        # create_policy should NOT be called
        iam.create_policy.assert_not_called()

    def test_not_exists_creates(self):
        """Policy missing → create → PASS with action=created."""
        iam = _iam_client(
            create_policy_resp={
                "Policy": {
                    "Arn": "arn:aws:iam::123:policy/pcluster-omics-analysis",
                    "PolicyName": PCLUSTER_OMICS_POLICY_NAME,
                },
            },
        )
        result = ensure_pcluster_omics_policy(iam)
        assert result.status == CheckStatus.PASS
        assert result.details["action"] == "created"
        iam.create_policy.assert_called_once()

    def test_create_failure(self):
        """Policy missing and create fails → FAIL."""
        iam = _iam_client(
            create_policy_error=Exception("AccessDenied"),
        )
        result = ensure_pcluster_omics_policy(iam)
        assert result.status == CheckStatus.FAIL
        assert "AccessDenied" in result.remediation

    def test_policy_document_matches_bash(self):
        """Verify policy document matches the exact Bash implementation."""
        assert PCLUSTER_OMICS_POLICY_DOCUMENT["Version"] == "2012-10-17"
        stmts = PCLUSTER_OMICS_POLICY_DOCUMENT["Statement"]
        assert len(stmts) == 1
        assert stmts[0]["Action"] == "iam:CreateServiceLinkedRole"
        assert stmts[0]["Resource"] == "*"
        assert stmts[0]["Condition"]["StringLike"]["iam:AWSServiceName"] == "spot.amazonaws.com"

    def test_idempotent_second_call(self):
        """Calling twice with existing policy → both return PASS."""
        iam = _iam_client(
            list_policies_pages=[
                {"Policies": [{"PolicyName": PCLUSTER_OMICS_POLICY_NAME, "Arn": "arn:test"}]},
            ],
        )
        r1 = ensure_pcluster_omics_policy(iam)
        r2 = ensure_pcluster_omics_policy(iam)
        assert r1.status == CheckStatus.PASS
        assert r2.status == CheckStatus.PASS



# ===========================================================================
# resolve_scheduler_role
# ===========================================================================


class TestResolveSchedulerRole:
    def test_preconfigured_wins(self):
        """Preconfigured value takes precedence over everything."""
        iam = _iam_client()
        arn, source = resolve_scheduler_role(
            iam, preconfigured="arn:aws:iam::123:role/my-role",
        )
        assert arn == "arn:aws:iam::123:role/my-role"
        assert source == "preconfigured"

    def test_env_var_first(self):
        """First env var in list takes precedence."""
        iam = _iam_client()
        with patch.dict(
            os.environ,
            {"DAY_HEARTBEAT_SCHEDULER_ROLE_ARN": "arn:from:env1"},
            clear=False,
        ):
            arn, source = resolve_scheduler_role(iam)
        assert arn == "arn:from:env1"
        assert source == "env:DAY_HEARTBEAT_SCHEDULER_ROLE_ARN"

    def test_env_var_second(self):
        """Second env var used when first is empty."""
        iam = _iam_client()
        env_patch = {
            "DAYLILY_HEARTBEAT_SCHEDULER_ROLE_ARN": "arn:from:env2",
        }
        # Ensure first var is not set
        env_clean = {v: "" for v in HEARTBEAT_ROLE_ENV_VARS}
        env_clean.update(env_patch)
        # Remove empties
        with patch.dict(os.environ, env_clean, clear=False):
            # Clear the first one explicitly
            os.environ.pop("DAY_HEARTBEAT_SCHEDULER_ROLE_ARN", None)
            arn, source = resolve_scheduler_role(iam)
        assert arn == "arn:from:env2"
        assert source == "env:DAYLILY_HEARTBEAT_SCHEDULER_ROLE_ARN"

    def test_env_var_order_matches_bash(self):
        """Env var order matches Bash HEARTBEAT_ROLE_ENV_VARS."""
        assert HEARTBEAT_ROLE_ENV_VARS == [
            "DAY_HEARTBEAT_SCHEDULER_ROLE_ARN",
            "DAYLILY_HEARTBEAT_SCHEDULER_ROLE_ARN",
            "DAY_HEARTBEAT_ROLE_ARN",
            "DAYLILY_SCHEDULER_ROLE_ARN",
        ]

    def test_existing_role_first_name(self):
        """First role name found → returns its ARN."""
        iam = _iam_client(
            get_role_responses={
                "eventbridge-scheduler-to-sns": {
                    "Role": {"Arn": "arn:aws:iam::123:role/eventbridge-scheduler-to-sns"},
                },
            },
        )
        # Clear env vars
        env_clean = {v: "" for v in HEARTBEAT_ROLE_ENV_VARS}
        with patch.dict(os.environ, env_clean, clear=False):
            for v in HEARTBEAT_ROLE_ENV_VARS:
                os.environ.pop(v, None)
            arn, source = resolve_scheduler_role(iam)
        assert arn == "arn:aws:iam::123:role/eventbridge-scheduler-to-sns"
        assert source == "existing_role:eventbridge-scheduler-to-sns"

    def test_existing_role_second_name(self):
        """Second role name found when first missing → returns its ARN."""
        iam = _iam_client(
            get_role_responses={
                "daylily-eventbridge-scheduler": {
                    "Role": {"Arn": "arn:aws:iam::123:role/daylily-eventbridge-scheduler"},
                },
            },
        )
        env_clean = {v: "" for v in HEARTBEAT_ROLE_ENV_VARS}
        with patch.dict(os.environ, env_clean, clear=False):
            for v in HEARTBEAT_ROLE_ENV_VARS:
                os.environ.pop(v, None)
            arn, source = resolve_scheduler_role(iam)
        assert arn == "arn:aws:iam::123:role/daylily-eventbridge-scheduler"
        assert source == "existing_role:daylily-eventbridge-scheduler"

    def test_role_names_match_bash(self):
        """Role name list matches Bash HEARTBEAT_DEFAULT_ROLE_NAMES."""
        assert HEARTBEAT_DEFAULT_ROLE_NAMES == [
            "eventbridge-scheduler-to-sns",
            "daylily-eventbridge-scheduler",
        ]

    @patch("daylily_ec.aws.iam.subprocess.run")
    @patch("daylily_ec.aws.iam.os.path.isfile", return_value=True)
    @patch("daylily_ec.aws.iam.shutil.which", return_value=None)
    def test_create_via_script(self, mock_which, mock_isfile, mock_run):
        """When no role found, create via script → parse ARN from output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Creating role...\nROLE ARN: arn:aws:iam::123:role/created-role\nDone.",
            stderr="",
        )
        iam = _iam_client()
        env_clean = {v: "" for v in HEARTBEAT_ROLE_ENV_VARS}
        with patch.dict(os.environ, env_clean, clear=False):
            for v in HEARTBEAT_ROLE_ENV_VARS:
                os.environ.pop(v, None)
            arn, source = resolve_scheduler_role(
                iam, region="us-west-2", profile="myprof",
            )
        assert arn == "arn:aws:iam::123:role/created-role"
        assert source == "created_by_script"

    @patch("daylily_ec.aws.iam.os.path.isfile", return_value=False)
    @patch("daylily_ec.aws.iam.shutil.which", return_value=None)
    def test_not_found(self, mock_which, mock_isfile):
        """Nothing found → returns (None, 'not_found')."""
        iam = _iam_client()
        env_clean = {v: "" for v in HEARTBEAT_ROLE_ENV_VARS}
        with patch.dict(os.environ, env_clean, clear=False):
            for v in HEARTBEAT_ROLE_ENV_VARS:
                os.environ.pop(v, None)
            arn, source = resolve_scheduler_role(iam)
        assert arn is None
        assert source == "not_found"

    def test_preconfigured_over_env(self):
        """Preconfigured beats env var."""
        iam = _iam_client()
        with patch.dict(
            os.environ,
            {"DAY_HEARTBEAT_SCHEDULER_ROLE_ARN": "arn:from:env"},
            clear=False,
        ):
            arn, source = resolve_scheduler_role(
                iam, preconfigured="arn:preconfigured",
            )
        assert arn == "arn:preconfigured"
        assert source == "preconfigured"


# ===========================================================================
# make_iam_preflight_step
# ===========================================================================


class TestMakeIamPreflightStep:
    def test_all_pass(self):
        """All policies attached + omics policy exists → 3 PASS checks."""
        iam = _iam_client(
            user_policies=[
                {"PolicyName": GLOBAL_POLICY_NAME},
                {"PolicyName": f"{REGIONAL_POLICY_PREFIX}-us-west-2"},
            ],
            list_policies_pages=[
                {"Policies": [{"PolicyName": PCLUSTER_OMICS_POLICY_NAME, "Arn": "arn:test"}]},
            ],
        )
        ctx = _aws_ctx(iam_client=iam)
        step = make_iam_preflight_step(ctx)
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert len(report.checks) == 3
        assert all(c.status == CheckStatus.PASS for c in report.checks)
        assert report.passed

    def test_missing_policy_non_interactive_fails(self):
        """Missing policy in non-interactive mode → FAIL."""
        iam = _iam_client(
            list_policies_pages=[
                {"Policies": [{"PolicyName": PCLUSTER_OMICS_POLICY_NAME, "Arn": "arn:test"}]},
            ],
        )
        ctx = _aws_ctx(iam_client=iam)
        step = make_iam_preflight_step(ctx, interactive=False)
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert not report.passed
        fail_ids = [c.id for c in report.checks if c.status == CheckStatus.FAIL]
        assert "iam.policy.global" in fail_ids

    def test_missing_policy_interactive_warns(self):
        """Missing policy in interactive mode → WARN (not FAIL)."""
        iam = _iam_client(
            list_policies_pages=[
                {"Policies": [{"PolicyName": PCLUSTER_OMICS_POLICY_NAME, "Arn": "arn:test"}]},
            ],
        )
        ctx = _aws_ctx(iam_client=iam)
        step = make_iam_preflight_step(ctx, interactive=True)
        report = PreflightReport(region="us-west-2")
        report = step(report)

        # No FAIL — should still be "passed" (only WARNs)
        assert report.passed
        assert report.has_warnings
        warn_ids = [c.id for c in report.checks if c.status == CheckStatus.WARN]
        assert "iam.policy.global" in warn_ids

    def test_preserves_existing_checks(self):
        """Step preserves checks already in the report."""
        iam = _iam_client(
            user_policies=[
                {"PolicyName": GLOBAL_POLICY_NAME},
                {"PolicyName": f"{REGIONAL_POLICY_PREFIX}-us-west-2"},
            ],
            list_policies_pages=[
                {"Policies": [{"PolicyName": PCLUSTER_OMICS_POLICY_NAME, "Arn": "arn:test"}]},
            ],
        )
        ctx = _aws_ctx(iam_client=iam)
        step = make_iam_preflight_step(ctx)
        report = PreflightReport(region="us-west-2")
        report.checks.append(
            CheckResult(id="prior.check", status=CheckStatus.PASS),
        )
        report = step(report)

        assert len(report.checks) == 4
        assert report.checks[0].id == "prior.check"

    def test_uses_report_region(self):
        """Step uses report.region for regional policy name."""
        iam = _iam_client(
            user_policies=[
                {"PolicyName": GLOBAL_POLICY_NAME},
                {"PolicyName": f"{REGIONAL_POLICY_PREFIX}-eu-west-1"},
            ],
            list_policies_pages=[
                {"Policies": [{"PolicyName": PCLUSTER_OMICS_POLICY_NAME, "Arn": "arn:test"}]},
            ],
        )
        ctx = _aws_ctx(region="us-west-2", iam_client=iam)
        step = make_iam_preflight_step(ctx)
        # Report region differs from ctx region
        report = PreflightReport(region="eu-west-1")
        report = step(report)

        assert report.checks[1].status == CheckStatus.PASS  # regional found

    def test_returns_callable(self):
        """Factory returns a callable."""
        ctx = _aws_ctx()
        step = make_iam_preflight_step(ctx)
        assert callable(step)

    def test_constants_correct(self):
        """Verify constant values match Bash."""
        assert GLOBAL_POLICY_NAME == "DaylilyGlobalEClusterPolicy"
        assert REGIONAL_POLICY_PREFIX == "DaylilyRegionalEClusterPolicy"
        assert PCLUSTER_OMICS_POLICY_NAME == "pcluster-omics-analysis"
        assert CREATE_SCHEDULER_SCRIPT == "bin/admin/create_scheduler_role_for_sns.sh"