"""IAM policy checks, ensurers, and scheduler role resolution.

Implements CP-007 from the refactor spec:

- Check ``DaylilyGlobalEClusterPolicy`` + ``DaylilyRegionalEClusterPolicy-<region>``
  attached via user or group (exact Bash parity with ``check_managed_policy_attached``).
- Ensure ``pcluster-omics-analysis`` managed policy exists (idempotent create).
- Resolve EventBridge Scheduler role ARN using env vars, existing roles, or creation.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional, Tuple

from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GLOBAL_POLICY_NAME = "DaylilyGlobalEClusterPolicy"
REGIONAL_POLICY_PREFIX = "DaylilyRegionalEClusterPolicy"

# NOTE (2026-08-19): this policy appears to be vestigial, and the check below is
# a gate on an object that has never done anything.
#
#   origin        legacy bash: "# Ensure 'pcluster-omics-analysis' policy exists
#                 (spot SL role)" — it granted iam:CreateServiceLinkedRole for
#                 spot.amazonaws.com so the EC2 Spot SLR could be created once.
#   ever attached NEVER. The legacy block ends at `create-policy`; no attach-*
#                 call exists anywhere in it. DYEC ported the omission faithfully.
#   purpose met   AWSServiceRoleForEC2Spot was created 2025-02-23, four days
#                 after this policy, by something else. SLRs are once-per-account.
#   attachments   0
#   cloudtrail    zero events naming it across a 90-day window
#   versions      v1 only, never edited since 2025-02-19
#
# The clean-slate case it nominally guarded is covered better by the
# DaylilyDeployer permission set, which grants iam:CreateServiceLinkedRole
# directly, conditioned on iam:AWSServiceName. A conditioned grant on the
# principal that needs it beats an unattached side-policy that never worked.
#
# Retained rather than removed pending confirmation from the original author
# that it was not meant to be attached somewhere. See
# docs/plans/ for the deprecation plan.
PCLUSTER_OMICS_POLICY_NAME = "pcluster-omics-analysis"
# Retained after the create path was removed: this is the reference for what
# the policy should contain if it ever genuinely needs recreating, and the
# Layer-0 Terraform should match it. No production code path uses it.
PCLUSTER_OMICS_POLICY_DOCUMENT: dict = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "iam:CreateServiceLinkedRole",
            "Resource": "*",
            "Condition": {
                "StringLike": {
                    "iam:AWSServiceName": "spot.amazonaws.com",
                }
            },
        }
    ],
}

HEARTBEAT_ROLE_ENV_VARS: List[str] = [
    "DAY_HEARTBEAT_SCHEDULER_ROLE_ARN",
    "DAYLILY_HEARTBEAT_SCHEDULER_ROLE_ARN",
    "DAY_HEARTBEAT_ROLE_ARN",
    "DAYLILY_SCHEDULER_ROLE_ARN",
]

HEARTBEAT_DEFAULT_ROLE_NAMES: List[str] = [
    "eventbridge-scheduler-to-sns",
    "daylily-eventbridge-scheduler",
]


# ---------------------------------------------------------------------------
# Policy attachment check (exact Bash parity)
# ---------------------------------------------------------------------------


def check_policy_attached(
    iam_client: Any,
    username: str,
    policy_name: str,
) -> bool:
    """Return *True* if *policy_name* is attached to *username* (user or group).

    Mirrors Bash ``check_managed_policy_attached`` exactly:
    1. Check user-attached policies.
    2. Check group-attached policies for each group the user belongs to.
    """
    # 1. Direct user attachment (legacy path)
    try:
        resp = iam_client.list_attached_user_policies(UserName=username)
        for pol in resp.get("AttachedPolicies", []):
            if pol.get("PolicyName") == policy_name:
                return True
    except Exception:
        logger.debug("Could not list user policies for %s", username)

    # 2. Group attachment (preferred path)
    try:
        groups_resp = iam_client.list_groups_for_user(UserName=username)
        for group in groups_resp.get("Groups", []):
            group_name = group.get("GroupName", "")
            if not group_name:
                continue
            try:
                gp_resp = iam_client.list_attached_group_policies(
                    GroupName=group_name,
                )
                for pol in gp_resp.get("AttachedPolicies", []):
                    if pol.get("PolicyName") == policy_name:
                        return True
            except Exception:
                logger.debug(
                    "Could not list group policies for %s",
                    group_name,
                )
    except Exception:
        logger.debug("Could not list groups for user %s", username)

    return False


# ---------------------------------------------------------------------------
# Daylily policy check (global + regional)
# ---------------------------------------------------------------------------


def _is_root_account(username: str) -> bool:
    """Return *True* if *username* represents the AWS root account."""
    return username == "root"


def check_daylily_policies(
    iam_client: Any,
    username: str,
    region: str,
    *,
    interactive: bool = False,
) -> List[CheckResult]:
    """Check both global and regional Daylily policies.

    Returns:
        List of :class:`CheckResult` — one per policy checked.
        Missing policies produce WARN in interactive mode, FAIL otherwise.
        Root accounts auto-PASS (implicit full access).
    """
    # Root accounts have implicit full access — policy attachment is N/A.
    if _is_root_account(username):
        return [
            CheckResult(
                id="iam.policy.global",
                status=CheckStatus.PASS,
                details={
                    "policy": GLOBAL_POLICY_NAME,
                    "user": username,
                    "note": "root account — implicit full access",
                },
            ),
            CheckResult(
                id="iam.policy.regional",
                status=CheckStatus.PASS,
                details={
                    "policy": f"{REGIONAL_POLICY_PREFIX}-{region}",
                    "user": username,
                    "note": "root account — implicit full access",
                },
            ),
        ]

    regional_policy = f"{REGIONAL_POLICY_PREFIX}-{region}"
    results: List[CheckResult] = []

    for policy_name, label in [
        (GLOBAL_POLICY_NAME, "global"),
        (regional_policy, f"regional ({region})"),
    ]:
        attached = check_policy_attached(iam_client, username, policy_name)
        if attached:
            results.append(
                CheckResult(
                    id=f"iam.policy.{label.split()[0]}",
                    status=CheckStatus.PASS,
                    details={"policy": policy_name, "user": username},
                )
            )
        else:
            status = CheckStatus.WARN if interactive else CheckStatus.FAIL
            remediation = (
                f"Policy '{policy_name}' not attached to user '{username}' (direct or via group). "
            )
            if label == "global":
                remediation += (
                    "An admin can attach it by running: "
                    "bin/admin/daylily_ephemeral_cluster_bootstrap_global.sh "
                    f"--profile <admin_profile> --user {username}"
                )
            else:
                remediation += (
                    "An admin can attach it by running: "
                    "bin/admin/daylily_ephemeral_cluster_bootstrap_region.sh "
                    f"--region {region} --profile <admin_profile> "
                    f"--user {username}"
                )
            results.append(
                CheckResult(
                    id=f"iam.policy.{label.split()[0]}",
                    status=status,
                    details={"policy": policy_name, "user": username},
                    remediation=remediation,
                )
            )

    return results


# ---------------------------------------------------------------------------
# pcluster-omics-analysis policy (idempotent ensure)
# ---------------------------------------------------------------------------


def ensure_pcluster_omics_policy(
    iam_client: Any,
) -> CheckResult:
    """Ensure ``pcluster-omics-analysis`` managed policy exists.

    If the policy already exists, return PASS.
    The policy is VERIFIED, never created. See the notes below on why it is
    also almost certainly dead.
    """
    try:
        paginator = iam_client.get_paginator("list_policies")
        for page in paginator.paginate(Scope="Local"):
            for pol in page.get("Policies", []):
                if pol.get("PolicyName") == PCLUSTER_OMICS_POLICY_NAME:
                    return CheckResult(
                        id="iam.pcluster_omics_policy",
                        status=CheckStatus.PASS,
                        details={
                            "policy": PCLUSTER_OMICS_POLICY_NAME,
                            "arn": pol.get("Arn", ""),
                            "action": "verified",
                        },
                    )
    except Exception as exc:
        return CheckResult(
            id="iam.pcluster_omics_policy",
            status=CheckStatus.FAIL,
            details={"policy": PCLUSTER_OMICS_POLICY_NAME, "error": str(exc)},
            remediation=(
                f"Could not list IAM policies to verify "
                f"{PCLUSTER_OMICS_POLICY_NAME!r}: {exc}. The deploying principal "
                "needs iam:ListPolicies."
            ),
        )

    return CheckResult(
        id="iam.pcluster_omics_policy",
        status=CheckStatus.FAIL,
        details={"policy": PCLUSTER_OMICS_POLICY_NAME, "action": "missing"},
        remediation=(
            f"IAM policy {PCLUSTER_OMICS_POLICY_NAME!r} does not exist. DYEC no "
            "longer creates it: a deploy path must not perform one-time IAM "
            "setup. Apply the Layer-0 Terraform in lsmc-infra "
            "(terraform/management/identity-center) and retry.\n\n"
            "Before creating it, check whether it is needed at all — see the "
            "note in this module. On the evidence it is dead."
        ),
    )


# ---------------------------------------------------------------------------
# Scheduler role resolution (exact Bash parity)
# ---------------------------------------------------------------------------


def resolve_scheduler_role(
    iam_client: Any,
    *,
    preconfigured: str = "",
    region: str = "",
    profile: str = "",
) -> Tuple[Optional[str], str]:
    """Resolve the EventBridge Scheduler role ARN.

    Precedence (exact Bash ``resolve_or_create_heartbeat_role`` parity):

    1. *preconfigured* value (from config ``heartbeat_scheduler_role_arn``).
    2. Environment variables (in order): ``DAY_HEARTBEAT_SCHEDULER_ROLE_ARN``,
       ``DAYLILY_HEARTBEAT_SCHEDULER_ROLE_ARN``, ``DAY_HEARTBEAT_ROLE_ARN``,
       ``DAYLILY_SCHEDULER_ROLE_ARN``.
    3. Existing role names: ``eventbridge-scheduler-to-sns``,
       ``daylily-eventbridge-scheduler``.

    There is deliberately no fourth step. This previously shelled out to
    ``bin/admin/create_scheduler_role_for_sns.sh``, which calls iam:CreateRole,
    **iam:UpdateAssumeRolePolicy**, iam:PutRolePolicy and iam:TagRole — one-time
    setup on the every-deploy path, and two of the more dangerous IAM verbs
    hiding in a branch that only fires on a clean-slate region.

    A miss is now a clean ``(None, "not_found")``. The caller reports it and the
    heartbeat is skipped; the role is created by the Layer-0 Terraform in
    lsmc-infra, once, under review.

    Args:
        region, profile: accepted and ignored. They fed only the removed
            create-via-script step; the signature is kept so the caller in
            create_cluster.py needs no change.

    Returns:
        Tuple of (role_arn_or_None, source_description).
    """
    # 1. Preconfigured
    if preconfigured:
        return preconfigured, "preconfigured"

    # 2. Environment variables
    for env_var in HEARTBEAT_ROLE_ENV_VARS:
        value = os.environ.get(env_var, "")
        if value:
            return value, f"env:{env_var}"

    # 3. Existing roles by name
    for role_name in HEARTBEAT_DEFAULT_ROLE_NAMES:
        try:
            resp = iam_client.get_role(RoleName=role_name)
            arn = resp.get("Role", {}).get("Arn", "")
            if arn and arn != "None":
                return arn, f"existing_role:{role_name}"
        except Exception:
            continue

    return None, "not_found"


# ---------------------------------------------------------------------------
# Preflight step factory
# ---------------------------------------------------------------------------


def make_iam_preflight_step(
    aws_ctx: Any,
    *,
    interactive: bool = False,
):
    """Return a :data:`PreflightStep` that runs all IAM checks.

    Checks performed (in order):
    1. DaylilyGlobalEClusterPolicy attached
    2. DaylilyRegionalEClusterPolicy-<region> attached
    3. pcluster-omics-analysis policy exists (idempotent create)
    """

    def step(report: PreflightReport) -> PreflightReport:
        iam = aws_ctx.client("iam")

        # 1-2. Daylily policy checks
        policy_results = check_daylily_policies(
            iam,
            aws_ctx.iam_username,
            report.region or aws_ctx.region,
            interactive=interactive,
        )
        report.checks.extend(policy_results)

        # 3. pcluster-omics-analysis ensure
        omics_result = ensure_pcluster_omics_policy(iam)
        report.checks.append(omics_result)

        return report

    return step
