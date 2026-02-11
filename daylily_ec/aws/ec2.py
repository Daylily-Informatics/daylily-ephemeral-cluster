"""Subnet discovery/selection and IAM policy ARN selection — CP-009.

Mirrors the Bash logic in ``bin/daylily-create-ephemeral-cluster`` lines
1710-1918:

1. **Baseline inspection** — if both public & private subnets are absent in the
   target AZ, trigger CFN stack creation (CP-008).  If only one is missing →
   hard fail.

2. **Subnet selection** — discover subnets via ``ec2:DescribeSubnets``, filter
   by tag name containing ``Public Subnet`` / ``Private Subnet`` and AZ.
   Auto-select via triplet config or single-candidate logic (respecting
   ``DAY_DISABLE_AUTO_SELECT``).

3. **Policy ARN selection** — list ``pclusterTagsAndBudget`` IAM policies,
   auto-select if single and auto-select enabled.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from daylily_ec.config.triplets import (
    is_auto_select_disabled,
    should_auto_apply,
)
from daylily_ec.state.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PUBLIC_SUBNET_TAG_FILTER = "Public Subnet"
PRIVATE_SUBNET_TAG_FILTER = "Private Subnet"
PCLUSTER_TAGS_POLICY_NAME = "pclusterTagsAndBudget"


# ---------------------------------------------------------------------------
# Subnet info dataclass
# ---------------------------------------------------------------------------


@dataclass
class SubnetInfo:
    """A discovered subnet."""

    subnet_id: str = ""
    name: str = ""
    availability_zone: str = ""
    vpc_id: str = ""


# ---------------------------------------------------------------------------
# Subnet discovery
# ---------------------------------------------------------------------------


def list_subnets(
    ec2_client: Any,
    region_az: str,
    *,
    tag_filter: str,
) -> List[SubnetInfo]:
    """List subnets in *region_az* whose Name tag contains *tag_filter*.

    Exact Bash parity::

        aws ec2 describe-subnets \\
          --query "Subnets[?AvailabilityZone=='$region_az']..." \\
          | grep "Public Subnet"
    """
    try:
        paginator = ec2_client.get_paginator("describe_subnets")
        filters = [
            {"Name": "availability-zone", "Values": [region_az]},
        ]
        results: List[SubnetInfo] = []
        for page in paginator.paginate(Filters=filters):
            for s in page.get("Subnets", []):
                name = ""
                for tag in s.get("Tags", []):
                    if tag.get("Key") == "Name":
                        name = tag.get("Value", "")
                        break
                if tag_filter in name:
                    results.append(
                        SubnetInfo(
                            subnet_id=s["SubnetId"],
                            name=name,
                            availability_zone=s.get("AvailabilityZone", ""),
                            vpc_id=s.get("VpcId", ""),
                        )
                    )
        return results
    except Exception as exc:
        logger.debug("Error listing subnets in %s: %s", region_az, exc)
        return []


def list_public_subnets(ec2_client: Any, region_az: str) -> List[SubnetInfo]:
    """Convenience: list subnets tagged with ``Public Subnet``."""
    return list_subnets(ec2_client, region_az, tag_filter=PUBLIC_SUBNET_TAG_FILTER)


def list_private_subnets(ec2_client: Any, region_az: str) -> List[SubnetInfo]:
    """Convenience: list subnets tagged with ``Private Subnet``."""
    return list_subnets(ec2_client, region_az, tag_filter=PRIVATE_SUBNET_TAG_FILTER)


# ---------------------------------------------------------------------------
# Baseline inspection (Bash L1710-1732)
# ---------------------------------------------------------------------------


def inspect_baseline_subnets(
    ec2_client: Any,
    region_az: str,
) -> Tuple[List[SubnetInfo], List[SubnetInfo]]:
    """Check whether public and private subnets exist in *region_az*.

    Returns ``(public_list, private_list)`` — the caller decides what to do
    based on emptiness of each list (both empty → create stack, one empty →
    hard fail, both present → proceed).
    """
    pub = list_public_subnets(ec2_client, region_az)
    priv = list_private_subnets(ec2_client, region_az)
    return pub, priv


# ---------------------------------------------------------------------------
# Subnet selection (Bash L1742-1860)
# ---------------------------------------------------------------------------


def select_subnet(
    candidates: List[SubnetInfo],
    *,
    cfg_action: str = "",
    cfg_set_value: str = "",
    cfg_fallback: str = "",
) -> Optional[str]:
    """Choose a subnet ID from *candidates* using Bash-parity selection logic.

    Precedence (exact Bash parity, same as :func:`daylily_ec.aws.s3.select_bucket`):

    1. Config ``set_value`` if :func:`should_auto_apply` is True **and**
       value matches a candidate subnet ID.
    2. Single candidate auto-select (unless ``DAY_DISABLE_AUTO_SELECT=1``).
    3. ``cfg_fallback`` (e.g. ``CONFIG_PUBLIC_SUBNET_ID``) if it matches a
       candidate.
    4. ``None`` — caller should prompt interactively.
    """
    candidate_ids = [s.subnet_id for s in candidates]

    # 1. Triplet set_value auto-apply
    if should_auto_apply(cfg_action, cfg_set_value):
        if cfg_set_value in candidate_ids:
            return cfg_set_value

    # 2. Single candidate auto-select
    if len(candidates) == 1:
        if not is_auto_select_disabled():
            return candidates[0].subnet_id

    # 3. Config fallback (CONFIG_PUBLIC_SUBNET_ID / CONFIG_PRIVATE_SUBNET_ID)
    if cfg_fallback and cfg_fallback in candidate_ids:
        return cfg_fallback

    # 4. Needs interactive prompt (not handled here)
    return None


# ---------------------------------------------------------------------------
# Policy ARN listing (Bash L1863)
# ---------------------------------------------------------------------------


def list_pcluster_tags_budget_policies(iam_client: Any) -> List[str]:
    """List ARNs of IAM policies named ``pclusterTagsAndBudget``.

    Exact Bash parity::

        aws iam list-policies \\
          --query 'Policies[?PolicyName==`pclusterTagsAndBudget`].Arn' \\
          --output text
    """
    try:
        paginator = iam_client.get_paginator("list_policies")
        arns: List[str] = []
        for page in paginator.paginate(Scope="All"):
            for pol in page.get("Policies", []):
                if pol.get("PolicyName") == PCLUSTER_TAGS_POLICY_NAME:
                    arns.append(pol["Arn"])
        return arns
    except Exception as exc:
        logger.debug("Error listing policies: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Policy ARN selection (Bash L1862-1918)
# ---------------------------------------------------------------------------


def select_policy_arn(
    candidates: List[str],
    *,
    cfg_action: str = "",
    cfg_set_value: str = "",
    cfg_fallback: str = "",
) -> Optional[str]:
    """Choose a policy ARN from *candidates* using Bash-parity selection logic.

    Same precedence as :func:`select_subnet`:

    1. Config ``set_value`` if :func:`should_auto_apply` is True **and**
       value matches a candidate ARN.
    2. Single candidate auto-select (unless ``DAY_DISABLE_AUTO_SELECT=1``).
    3. ``cfg_fallback`` (``CONFIG_IAM_POLICY_ARN``) if it matches a candidate.
    4. ``None`` — caller should prompt interactively.
    """
    # 1. Triplet set_value auto-apply
    if should_auto_apply(cfg_action, cfg_set_value):
        if cfg_set_value in candidates:
            return cfg_set_value

    # 2. Single candidate auto-select
    if len(candidates) == 1:
        if not is_auto_select_disabled():
            return candidates[0]

    # 3. Config fallback
    if cfg_fallback and cfg_fallback in candidates:
        return cfg_fallback

    # 4. Needs interactive prompt
    return None


# ---------------------------------------------------------------------------
# Preflight step factory
# ---------------------------------------------------------------------------


def make_subnet_policy_preflight_step(
    ec2_client: Any,
    iam_client: Any,
    region_az: str,
    *,
    pub_cfg_action: str = "",
    pub_cfg_set_value: str = "",
    pub_cfg_fallback: str = "",
    priv_cfg_action: str = "",
    priv_cfg_set_value: str = "",
    priv_cfg_fallback: str = "",
    iam_cfg_action: str = "",
    iam_cfg_set_value: str = "",
    iam_cfg_fallback: str = "",
) -> CheckResult:
    """Run subnet discovery + policy selection as a preflight check.

    Returns a :class:`CheckResult` with id ``ec2.subnet_policy_selection``.

    **Logic** (mirrors Bash L1710-1918):

    * Inspect baseline subnets in AZ.
    * If both missing → WARN (caller should trigger CFN stack creation).
    * If partial → FAIL.
    * Discover and select public/private subnets.
    * List and select policy ARN.
    * PASS only if all three selections resolved.
    """
    details: dict = {}
    remediation: List[str] = []

    # --- baseline inspection ---
    pub_list, priv_list = inspect_baseline_subnets(ec2_client, region_az)
    pub_exist = len(pub_list) > 0
    priv_exist = len(priv_list) > 0
    details["public_subnets_found"] = len(pub_list)
    details["private_subnets_found"] = len(priv_list)

    if not pub_exist and not priv_exist:
        details["baseline_status"] = "both_missing"
        remediation.append(
            "Both public and private subnets missing in AZ "
            f"{region_az}. Run CFN stack creation first."
        )
        return CheckResult(
            id="ec2.subnet_policy_selection",
            status=CheckStatus.WARN,
            details=details,
            remediation="; ".join(remediation),
        )

    if not pub_exist or not priv_exist:
        missing = "public" if not pub_exist else "private"
        details["baseline_status"] = f"{missing}_missing"
        remediation.append(
            f"Only {missing} subnet is missing in AZ {region_az}. "
            "Incomplete setup — cannot auto-recover."
        )
        return CheckResult(
            id="ec2.subnet_policy_selection",
            status=CheckStatus.FAIL,
            details=details,
            remediation="; ".join(remediation),
        )

    details["baseline_status"] = "ok"

    # --- subnet selection ---
    pub_selected = select_subnet(
        pub_list,
        cfg_action=pub_cfg_action,
        cfg_set_value=pub_cfg_set_value,
        cfg_fallback=pub_cfg_fallback,
    )
    priv_selected = select_subnet(
        priv_list,
        cfg_action=priv_cfg_action,
        cfg_set_value=priv_cfg_set_value,
        cfg_fallback=priv_cfg_fallback,
    )
    details["public_subnet_selected"] = pub_selected or ""
    details["private_subnet_selected"] = priv_selected or ""

    if pub_selected is None:
        remediation.append("Could not auto-select public subnet; interactive prompt needed.")
    if priv_selected is None:
        remediation.append("Could not auto-select private subnet; interactive prompt needed.")

    # --- policy ARN selection ---
    policy_arns = list_pcluster_tags_budget_policies(iam_client)
    details["policy_arns_found"] = len(policy_arns)

    arn_selected = select_policy_arn(
        policy_arns,
        cfg_action=iam_cfg_action,
        cfg_set_value=iam_cfg_set_value,
        cfg_fallback=iam_cfg_fallback,
    )
    details["policy_arn_selected"] = arn_selected or ""

    if arn_selected is None and len(policy_arns) == 0:
        remediation.append(
            f"No IAM policy named '{PCLUSTER_TAGS_POLICY_NAME}' found. "
            "Run CFN stack creation to create it."
        )
    elif arn_selected is None:
        remediation.append("Could not auto-select IAM policy ARN; interactive prompt needed.")

    # --- determine overall status ---
    if remediation:
        # Any unresolved selection is a WARN (prompt needed), not a hard FAIL
        # Hard FAIL was already returned above for partial subnet scenario
        status = CheckStatus.WARN
    else:
        status = CheckStatus.PASS

    return CheckResult(
        id="ec2.subnet_policy_selection",
        status=status,
        details=details,
        remediation="; ".join(remediation) if remediation else "",
    )

