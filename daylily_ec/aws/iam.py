"""IAM policy checks, ensurers, and scheduler role resolution.

Implements CP-007 from the refactor spec:

- Check ``DaylilyGlobalEClusterPolicy`` + ``DaylilyRegionalEClusterPolicy-<region>``
  attached via user or group (exact Bash parity with ``check_managed_policy_attached``).
- Ensure ``pcluster-omics-analysis`` managed policy exists (idempotent create).
- Resolve EventBridge Scheduler role ARN using env vars, existing roles, or creation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Any, List, Optional, Tuple

from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport
from daylily_ec.resources import resource_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GLOBAL_POLICY_NAME = "DaylilyGlobalEClusterPolicy"
REGIONAL_POLICY_PREFIX = "DaylilyRegionalEClusterPolicy"

PCLUSTER_OMICS_POLICY_NAME = "pcluster-omics-analysis"
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

HEADNODE_TAILSCALE_AUTHKEY_SSM_PARAMETER = "/daylily/dayec/tailscale/headnode-authkey"
HEADNODE_TAILSCALE_POLICY_NAME = "dayec-headnode-tailscale-authkey-read"

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

CREATE_SCHEDULER_SCRIPT = "bin/admin/create_scheduler_role_for_sns.sh"


def headnode_tailscale_authkey_policy_arn(account_id: str) -> str:
    """Return the deterministic managed-policy ARN for headnode Tailscale access."""
    if not account_id:
        raise ValueError("account_id must not be empty")
    return f"arn:aws:iam::{account_id}:policy/{HEADNODE_TAILSCALE_POLICY_NAME}"


def headnode_tailscale_authkey_policy_document(
    *,
    account_id: str,
    region: str,
    parameter_name: str = HEADNODE_TAILSCALE_AUTHKEY_SSM_PARAMETER,
) -> dict:
    """Build the least-privilege policy for reading the headnode authkey."""
    if not account_id:
        raise ValueError("account_id must not be empty")
    if not region:
        raise ValueError("region must not be empty")
    parameter_resource = parameter_name.lstrip("/")
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "ssm:GetParameter",
                "Resource": (
                    f"arn:aws:ssm:{region}:{account_id}:parameter/{parameter_resource}"
                ),
            }
        ],
    }


def _canonical_policy_document(document: dict) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


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
                    "Could not list group policies for %s", group_name,
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
                f"Policy '{policy_name}' not attached to user '{username}' "
                f"(direct or via group). "
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
    If missing, create it with the exact policy document from Bash.
    On error, return FAIL.
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
                            "action": "already_exists",
                        },
                    )
    except Exception as exc:
        logger.debug("Error listing policies: %s", exc)

    # Policy not found — create it
    try:
        resp = iam_client.create_policy(
            PolicyName=PCLUSTER_OMICS_POLICY_NAME,
            PolicyDocument=json.dumps(PCLUSTER_OMICS_POLICY_DOCUMENT),
        )
        arn = resp.get("Policy", {}).get("Arn", "")
        logger.info("Created IAM policy %s: %s", PCLUSTER_OMICS_POLICY_NAME, arn)
        return CheckResult(
            id="iam.pcluster_omics_policy",
            status=CheckStatus.PASS,
            details={
                "policy": PCLUSTER_OMICS_POLICY_NAME,
                "arn": arn,
                "action": "created",
            },
        )
    except Exception as exc:
        return CheckResult(
            id="iam.pcluster_omics_policy",
            status=CheckStatus.FAIL,
            details={"policy": PCLUSTER_OMICS_POLICY_NAME, "error": str(exc)},
            remediation=(
                f"Failed to create IAM policy '{PCLUSTER_OMICS_POLICY_NAME}': "
                f"{exc}. Create it manually or ensure IAM permissions."
            ),
        )


# ---------------------------------------------------------------------------
# Headnode Tailscale authkey read policy (idempotent ensure)
# ---------------------------------------------------------------------------


def ensure_headnode_tailscale_authkey_policy(
    iam_client: Any,
    *,
    account_id: str,
    region: str,
) -> CheckResult:
    """Ensure the headnode managed policy can read the Tailscale authkey."""
    try:
        desired_doc = headnode_tailscale_authkey_policy_document(
            account_id=account_id,
            region=region,
        )
        desired_canon = _canonical_policy_document(desired_doc)
    except ValueError as exc:
        return CheckResult(
            id="iam.headnode_tailscale_authkey_policy",
            status=CheckStatus.FAIL,
            details={
                "policy": HEADNODE_TAILSCALE_POLICY_NAME,
                "error": str(exc),
            },
            remediation=str(exc),
        )

    policy_arn = ""
    try:
        paginator = iam_client.get_paginator("list_policies")
        for page in paginator.paginate(Scope="Local"):
            for pol in page.get("Policies", []):
                if pol.get("PolicyName") == HEADNODE_TAILSCALE_POLICY_NAME:
                    policy_arn = pol.get("Arn", "")
                    break
            if policy_arn:
                break
    except Exception as exc:
        logger.debug("Error listing policies: %s", exc)

    if not policy_arn:
        try:
            resp = iam_client.create_policy(
                PolicyName=HEADNODE_TAILSCALE_POLICY_NAME,
                PolicyDocument=json.dumps(desired_doc),
            )
            arn = resp.get("Policy", {}).get("Arn", "")
            return CheckResult(
                id="iam.headnode_tailscale_authkey_policy",
                status=CheckStatus.PASS,
                details={
                    "policy": HEADNODE_TAILSCALE_POLICY_NAME,
                    "arn": arn,
                    "action": "created",
                },
            )
        except Exception as exc:
            return CheckResult(
                id="iam.headnode_tailscale_authkey_policy",
                status=CheckStatus.FAIL,
                details={
                    "policy": HEADNODE_TAILSCALE_POLICY_NAME,
                    "error": str(exc),
                },
                remediation=(
                    f"Failed to create IAM policy '{HEADNODE_TAILSCALE_POLICY_NAME}': "
                    f"{exc}. Create it manually or ensure IAM permissions."
                ),
            )

    try:
        policy = iam_client.get_policy(PolicyArn=policy_arn).get("Policy", {})
        default_version_id = policy.get("DefaultVersionId", "")
        version = iam_client.get_policy_version(
            PolicyArn=policy_arn,
            VersionId=default_version_id,
        )
        current_doc = version.get("PolicyVersion", {}).get("Document", {})
        if _canonical_policy_document(current_doc) == desired_canon:
            return CheckResult(
                id="iam.headnode_tailscale_authkey_policy",
                status=CheckStatus.PASS,
                details={
                    "policy": HEADNODE_TAILSCALE_POLICY_NAME,
                    "arn": policy_arn,
                    "action": "already_exists",
                },
            )

        versions = iam_client.list_policy_versions(PolicyArn=policy_arn).get(
            "Versions",
            [],
        )
        if len(versions) >= 5:
            non_default = [v for v in versions if not v.get("IsDefaultVersion")]
            if not non_default:
                raise RuntimeError(
                    f"Policy {HEADNODE_TAILSCALE_POLICY_NAME} has no non-default "
                    "versions available to delete before updating"
                )
            oldest = sorted(
                non_default,
                key=lambda v: str(v.get("CreateDate", "")),
            )[0]
            iam_client.delete_policy_version(
                PolicyArn=policy_arn,
                VersionId=oldest.get("VersionId", ""),
            )

        iam_client.create_policy_version(
            PolicyArn=policy_arn,
            PolicyDocument=json.dumps(desired_doc),
            SetAsDefault=True,
        )
        return CheckResult(
            id="iam.headnode_tailscale_authkey_policy",
            status=CheckStatus.PASS,
            details={
                "policy": HEADNODE_TAILSCALE_POLICY_NAME,
                "arn": policy_arn,
                "action": "updated_default_version",
            },
        )
    except Exception as exc:
        return CheckResult(
            id="iam.headnode_tailscale_authkey_policy",
            status=CheckStatus.FAIL,
            details={
                "policy": HEADNODE_TAILSCALE_POLICY_NAME,
                "arn": policy_arn,
                "error": str(exc),
            },
            remediation=(
                f"Failed to verify or update IAM policy "
                f"'{HEADNODE_TAILSCALE_POLICY_NAME}': {exc}."
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
    4. Create via ``bin/admin/create_scheduler_role_for_sns.sh`` if available.

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

    # 4. Create via script
    script_path = shutil.which(CREATE_SCHEDULER_SCRIPT) or ""
    if not script_path and os.path.isfile(CREATE_SCHEDULER_SCRIPT):
        script_path = CREATE_SCHEDULER_SCRIPT
    elif not script_path:
        # When installed via pip, use the packaged script.
        try:
            script_path = str(resource_path(CREATE_SCHEDULER_SCRIPT))
        except FileNotFoundError:
            script_path = ""

    if script_path:
        cmd: List[str] = [script_path, "--region", region]
        if profile:
            cmd.extend(["--profile", profile])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                # Parse "ROLE ARN: arn:aws:iam::..." from output
                for line in result.stdout.splitlines():
                    if "ROLE ARN:" in line:
                        parts = line.split("ROLE ARN:")
                        if len(parts) >= 2:
                            arn = parts[1].strip()
                            if arn:
                                return arn, "created_by_script"
        except Exception as exc:
            logger.error("Scheduler role creation script failed: %s", exc)

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
    4. headnode Tailscale authkey read policy exists (idempotent create/update)
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

        # 4. Headnode Tailscale authkey read policy ensure
        headnode_policy_result = ensure_headnode_tailscale_authkey_policy(
            iam,
            account_id=aws_ctx.account_id,
            region=report.region or aws_ctx.region,
        )
        report.checks.append(headnode_policy_result)

        return report

    return step
