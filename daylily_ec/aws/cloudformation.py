"""Baseline CloudFormation stack ensure — CP-008.

Wraps the VPC/subnet/NAT/IGW stack creation that was previously handled by
``bin/init_cloudstackformation.sh``.  Uses the **same** CFN template
(``config/day_cluster/pcluster_env.yml``) and the same parameter semantics.

Stack name derivation (exact Bash parity)::

    STACK_NAME = "pcluster-vpc-stack-" + <3rd dash-delimited field of AZ>
    # e.g. us-west-2a → pcluster-vpc-stack-2a

Resource prefix (EnvironmentName)::

    daylily-cs-<region_az> with digit-to-word substitution (1→one, 2→two, 3→three, 4→four)
    # e.g. us-west-2a → daylily-cs-us-west-twoa
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TEMPLATE_PATH = "config/day_cluster/pcluster_env.yml"

VPC_CIDR = "10.0.0.0/16"
PUBLIC_SUBNET_CIDR = "10.0.0.0/24"
PRIVATE_SUBNET_CIDR = "10.0.1.0/24"

TAGS_AND_BUDGET_POLICY_NAME = "pclusterTagsAndBudget"

#: Digit-to-word substitution map (only 1-4 per Bash ``sed`` commands).
DIGIT_WORD_MAP: Dict[str, str] = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
}

#: Stack statuses that mean "done, no action needed".
COMPLETE_STATUSES = frozenset({
    "CREATE_COMPLETE",
    "UPDATE_COMPLETE",
    "UPDATE_ROLLBACK_COMPLETE",
})

#: Stack statuses that are actively in progress.
IN_PROGRESS_STATUSES = frozenset({
    "CREATE_IN_PROGRESS",
    "UPDATE_IN_PROGRESS",
    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
})


# ---------------------------------------------------------------------------
# Stack outputs dataclass
# ---------------------------------------------------------------------------


@dataclass
class StackOutputs:
    """Outputs extracted from the baseline CFN stack."""

    vpc_id: str = ""
    public_subnet_id: str = ""
    private_subnet_id: str = ""
    policy_arn: str = ""


# ---------------------------------------------------------------------------
# Name derivation helpers
# ---------------------------------------------------------------------------


def derive_stack_name(region_az: str) -> str:
    """Derive CFN stack name from AZ.

    Exact Bash parity with ``init_cloudstackformation.sh`` line 39::

        STACK_NAME="pcluster-vpc-stack-"$(echo $3 | cut -d '-' -f 3)

    Examples:
        >>> derive_stack_name("us-west-2a")
        'pcluster-vpc-stack-2a'
        >>> derive_stack_name("eu-west-1b")
        'pcluster-vpc-stack-1b'
    """
    parts = region_az.split("-")
    if len(parts) < 3:
        raise ValueError(
            f"Cannot derive stack name from AZ '{region_az}': "
            "expected at least 3 dash-delimited segments"
        )
    field3 = parts[2]
    return f"pcluster-vpc-stack-{field3}"


def derive_resource_prefix(region_az: str) -> str:
    """Derive the EnvironmentName (resource prefix) from AZ.

    Exact Bash parity::

        res_prefix=$(echo "daylily-cs-$region_az" \\
            | sed -e 's/1/one/g' -e 's/2/two/g' \\
                  -e 's/3/three/g' -e 's/4/four/g')

    Only digits 1-4 are substituted. Other digits pass through unchanged.

    Examples:
        >>> derive_resource_prefix("us-west-2a")
        'daylily-cs-us-west-twoa'
        >>> derive_resource_prefix("us-east-1a")
        'daylily-cs-us-east-onea'
    """
    raw = f"daylily-cs-{region_az}"
    result: List[str] = []
    for ch in raw:
        result.append(DIGIT_WORD_MAP.get(ch, ch))
    return "".join(result)


# ---------------------------------------------------------------------------
# Policy check helper
# ---------------------------------------------------------------------------


def check_tags_budget_policy_exists(iam_client: Any) -> bool:
    """Return True if the ``pclusterTagsAndBudget`` IAM policy already exists.

    Matches Bash ``init_cloudstackformation.sh`` line 66::

        POLICY_EXISTS=$(aws iam list-policies \\
            --query "Policies[?PolicyName=='pclusterTagsAndBudget'] | length(@)" ...)
    """
    try:
        paginator = iam_client.get_paginator("list_policies")
        for page in paginator.paginate(Scope="Local"):
            for pol in page.get("Policies", []):
                if pol.get("PolicyName") == TAGS_AND_BUDGET_POLICY_NAME:
                    return True
    except Exception as exc:
        logger.debug("Error checking %s policy: %s", TAGS_AND_BUDGET_POLICY_NAME, exc)
    return False


# ---------------------------------------------------------------------------
# Stack outputs extraction
# ---------------------------------------------------------------------------


def get_stack_outputs(cfn_client: Any, stack_name: str) -> StackOutputs:
    """Extract outputs from a CFN stack.

    Output keys (from ``pcluster_env.yml``)::

        VPC          → vpc_id
        PublicSubnets → public_subnet_id
        PrivateSubnet → private_subnet_id
        PclusterPolicy → policy_arn
    """
    try:
        resp = cfn_client.describe_stacks(StackName=stack_name)
        stacks = resp.get("Stacks", [])
        if not stacks:
            return StackOutputs()
        outputs = {
            o["OutputKey"]: o["OutputValue"]
            for o in stacks[0].get("Outputs", [])
        }
        return StackOutputs(
            vpc_id=outputs.get("VPC", ""),
            public_subnet_id=outputs.get("PublicSubnets", ""),
            private_subnet_id=outputs.get("PrivateSubnet", ""),
            policy_arn=outputs.get("PclusterPolicy", ""),
        )
    except Exception as exc:
        logger.debug("Error getting stack outputs for %s: %s", stack_name, exc)
        return StackOutputs()


# ---------------------------------------------------------------------------
# describe / status helpers
# ---------------------------------------------------------------------------


def describe_stack_status(cfn_client: Any, stack_name: str) -> Optional[str]:
    """Return the StackStatus string, or None if the stack doesn't exist."""
    try:
        resp = cfn_client.describe_stacks(StackName=stack_name)
        stacks = resp.get("Stacks", [])
        if stacks:
            return stacks[0].get("StackStatus")
    except Exception:
        # Stack doesn't exist or other error
        pass
    return None


# ---------------------------------------------------------------------------
# Core ensure logic
# ---------------------------------------------------------------------------


def ensure_pcluster_env_stack(
    aws_ctx: Any,
    region_az: str,
    *,
    template_path: str = DEFAULT_TEMPLATE_PATH,
) -> StackOutputs:
    """Ensure the baseline VPC/subnet CFN stack exists.

    Behaviour (exact Bash parity):

    1. Derive stack name and resource prefix from *region_az*.
    2. If stack already in ``CREATE_COMPLETE`` / ``UPDATE_COMPLETE``, skip.
    3. Check if ``pclusterTagsAndBudget`` policy exists → set ``CreatePolicy``.
    4. Read template file, call ``create_stack``, wait for completion.
    5. Return :class:`StackOutputs`.

    Raises:
        FileNotFoundError: If template file not found.
        RuntimeError: If stack creation fails.
    """
    stack_name = derive_stack_name(region_az)
    resource_prefix = derive_resource_prefix(region_az)

    cfn = aws_ctx.client("cloudformation")

    # 1. Check if stack already exists and is complete
    status = describe_stack_status(cfn, stack_name)
    if status in COMPLETE_STATUSES:
        logger.info(
            "Stack %s already in %s — skipping creation.", stack_name, status,
        )
        return get_stack_outputs(cfn, stack_name)

    if status in IN_PROGRESS_STATUSES:
        logger.info(
            "Stack %s is %s — waiting for completion.", stack_name, status,
        )
        waiter = cfn.get_waiter("stack_create_complete")
        waiter.wait(StackName=stack_name)
        return get_stack_outputs(cfn, stack_name)

    # 2. Read template
    if not os.path.isfile(template_path):
        raise FileNotFoundError(
            f"CFN template not found: {template_path}"
        )
    with open(template_path) as fh:
        template_body = fh.read()

    # 3. Check policy existence
    iam = aws_ctx.client("iam")
    policy_exists = check_tags_budget_policy_exists(iam)
    create_policy = "false" if policy_exists else "true"
    logger.info(
        "pclusterTagsAndBudget policy %s — CreatePolicy=%s",
        "exists" if policy_exists else "does not exist",
        create_policy,
    )

    # 4. Create stack
    params: List[Dict[str, str]] = [
        {"ParameterKey": "EnvironmentName", "ParameterValue": resource_prefix},
        {"ParameterKey": "VpcCIDR", "ParameterValue": VPC_CIDR},
        {"ParameterKey": "PublicSubnetCIDR", "ParameterValue": PUBLIC_SUBNET_CIDR},
        {"ParameterKey": "PrivateSubnetCIDR", "ParameterValue": PRIVATE_SUBNET_CIDR},
        {"ParameterKey": "AvailabilityZone", "ParameterValue": region_az},
        {"ParameterKey": "CreatePolicy", "ParameterValue": create_policy},
    ]

    logger.info("Creating CFN stack %s ...", stack_name)
    cfn.create_stack(
        StackName=stack_name,
        TemplateBody=template_body,
        Parameters=params,
        Capabilities=["CAPABILITY_NAMED_IAM"],
    )

    # 5. Wait for completion
    logger.info("Waiting for stack %s to complete ...", stack_name)
    waiter = cfn.get_waiter("stack_create_complete")
    try:
        waiter.wait(StackName=stack_name)
    except Exception as exc:
        # Check actual status for better error message
        final_status = describe_stack_status(cfn, stack_name)
        raise RuntimeError(
            f"CFN stack {stack_name} creation failed "
            f"(status={final_status}): {exc}"
        ) from exc

    final_status = describe_stack_status(cfn, stack_name)
    if final_status != "CREATE_COMPLETE":
        raise RuntimeError(
            f"CFN stack {stack_name} ended in unexpected status: {final_status}"
        )

    logger.info("Stack %s creation succeeded.", stack_name)
    return get_stack_outputs(cfn, stack_name)


# ---------------------------------------------------------------------------
# Preflight step factory
# ---------------------------------------------------------------------------


def make_cfn_preflight_step(
    aws_ctx: Any,
    region_az: str,
    *,
    template_path: str = DEFAULT_TEMPLATE_PATH,
):
    """Return a preflight step that ensures the baseline CFN stack.

    The step adds a single :class:`CheckResult` to the report:
    - PASS if the stack already exists or was created successfully.
    - FAIL if creation fails or template is missing.
    """

    def step(report: PreflightReport) -> PreflightReport:
        try:
            outputs = ensure_pcluster_env_stack(
                aws_ctx, region_az, template_path=template_path,
            )
            report.checks.append(
                CheckResult(
                    id="cfn.baseline_stack",
                    status=CheckStatus.PASS,
                    details={
                        "stack_name": derive_stack_name(region_az),
                        "vpc_id": outputs.vpc_id,
                        "public_subnet_id": outputs.public_subnet_id,
                        "private_subnet_id": outputs.private_subnet_id,
                        "policy_arn": outputs.policy_arn,
                    },
                )
            )
        except Exception as exc:
            report.checks.append(
                CheckResult(
                    id="cfn.baseline_stack",
                    status=CheckStatus.FAIL,
                    details={"error": str(exc)},
                    remediation=(
                        f"Baseline CFN stack creation failed: {exc}. "
                        "Check AWS credentials and template file."
                    ),
                )
            )
        return report

    return step
