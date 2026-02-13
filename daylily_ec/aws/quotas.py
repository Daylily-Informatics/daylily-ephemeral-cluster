"""AWS service quota validation.

Checks 6 AWS service quotas and computes spot vCPU demand from
``max_count_*`` config values.  Matches Bash ``check_quota()`` behavior.

Quota definitions follow REFACTOR_SPEC §10.5-A.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Quota definitions (spec §10.5-A)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuotaDef:
    """Static definition for a single AWS service quota check."""

    name: str
    service_code: str
    quota_code: str
    recommended_min: int
    check_id: str


QUOTA_DEFS: list[QuotaDef] = [
    QuotaDef("On-Demand vCPU Max", "ec2", "L-1216C47A", 20, "quota.ondemand_vcpu"),
    QuotaDef("Spot vCPU Max", "ec2", "L-34B43A08", 192, "quota.spot_vcpu"),
    QuotaDef("VPCs", "vpc", "L-F678F1CE", 5, "quota.vpcs"),
    QuotaDef("Elastic IPs", "ec2", "L-0263D0A3", 5, "quota.elastic_ips"),
    QuotaDef("NAT Gateways", "vpc", "L-FE5A380F", 5, "quota.nat_gateways"),
    QuotaDef("Internet Gateways", "vpc", "L-A4707A72", 5, "quota.internet_gateways"),
]

SPOT_VCPU_QUOTA_CODE = "L-34B43A08"


# ---------------------------------------------------------------------------
# Spot vCPU computation (exact Bash parity)
# ---------------------------------------------------------------------------


def compute_spot_vcpu_demand(
    max_count_8i: int,
    max_count_128i: int,
    max_count_192i: int,
) -> int:
    """Compute total spot vCPUs requested.

    Matches Bash::

        tot_vcpu=$(( (CONFIG_MAX_COUNT_8I * 8)
                    + (CONFIG_MAX_COUNT_128I * 128)
                    + (CONFIG_MAX_COUNT_192I * 192) ))
    """
    return (max_count_8i * 8) + (max_count_128i * 128) + (max_count_192i * 192)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_quota_value(
    client: Any,
    service_code: str,
    quota_code: str,
) -> Optional[float]:
    """Call ``get_service_quota`` and return the numeric value, or *None* on error."""
    try:
        resp = client.get_service_quota(
            ServiceCode=service_code,
            QuotaCode=quota_code,
        )
        return float(resp["Quota"]["Value"])
    except Exception as exc:
        logger.warning(
            "Failed to fetch quota %s/%s: %s", service_code, quota_code, exc
        )
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_all_quotas(
    aws_ctx: Any,
    *,
    max_count_8i: int = 1,
    max_count_128i: int = 1,
    max_count_192i: int = 1,
    non_interactive: bool = False,
) -> List[CheckResult]:
    """Run all 6 quota checks and return a list of :class:`CheckResult`.

    Parameters:
        aws_ctx: :class:`~daylily_ec.aws.context.AWSContext` (or any object
            with a ``client(service)`` method and a ``region`` attribute).
        max_count_8i: Max 8xlarge instance count from config.
        max_count_128i: Max 128xlarge instance count from config.
        max_count_192i: Max 192xlarge instance count from config.
        non_interactive: If *True*, spot vCPU demand >= quota produces FAIL;
            otherwise WARN (caller handles interactive prompt).
    """
    tot_vcpu = compute_spot_vcpu_demand(max_count_8i, max_count_128i, max_count_192i)
    sq_client = aws_ctx.client("service-quotas")
    results: List[CheckResult] = []

    for qdef in QUOTA_DEFS:
        quota_value = _fetch_quota_value(sq_client, qdef.service_code, qdef.quota_code)

        details: dict[str, Any] = {
            "quota_code": qdef.quota_code,
            "service_code": qdef.service_code,
            "recommended_min": qdef.recommended_min,
        }

        # --- API failure → WARN ---
        if quota_value is None:
            results.append(
                CheckResult(
                    id=qdef.check_id,
                    status=CheckStatus.WARN,
                    details={
                        **details,
                        "current_value": None,
                        "note": "API call failed",
                    },
                    remediation=(
                        f"Unable to retrieve quota {qdef.quota_code} for "
                        f"{qdef.name}. Check service-quotas permissions."
                    ),
                )
            )
            continue

        details["current_value"] = quota_value

        # --- Spot vCPU special handling (L-34B43A08) ---
        if qdef.quota_code == SPOT_VCPU_QUOTA_CODE:
            details["tot_vcpu_demand"] = tot_vcpu
            if tot_vcpu >= quota_value:
                status = CheckStatus.FAIL if non_interactive else CheckStatus.WARN
                results.append(
                    CheckResult(
                        id=qdef.check_id,
                        status=status,
                        details=details,
                        remediation=(
                            f"Requested spot vCPUs ({tot_vcpu}) >= quota "
                            f"({int(quota_value)}). Request a quota increase "
                            "or reduce max_count_*I values."
                        ),
                    )
                )
                continue

        # --- Below recommended → WARN ---
        if quota_value < qdef.recommended_min:
            results.append(
                CheckResult(
                    id=qdef.check_id,
                    status=CheckStatus.WARN,
                    details=details,
                    remediation=(
                        f"{qdef.name} quota ({int(quota_value)}) is below "
                        f"recommended minimum ({qdef.recommended_min}). "
                        "Consider requesting an increase."
                    ),
                )
            )
            continue

        # --- PASS ---
        results.append(
            CheckResult(
                id=qdef.check_id,
                status=CheckStatus.PASS,
                details=details,
            )
        )

    return results


def make_quota_preflight_step(
    aws_ctx: Any,
    *,
    max_count_8i: int = 1,
    max_count_128i: int = 1,
    max_count_192i: int = 1,
    non_interactive: bool = False,
) -> Callable[[PreflightReport], PreflightReport]:
    """Return a preflight step that appends quota :class:`CheckResult` s.

    Usage::

        step = make_quota_preflight_step(ctx, max_count_8i=2)
        report = step(report)
    """

    def step(report: PreflightReport) -> PreflightReport:
        checks = check_all_quotas(
            aws_ctx,
            max_count_8i=max_count_8i,
            max_count_128i=max_count_128i,
            max_count_192i=max_count_192i,
            non_interactive=non_interactive,
        )
        report.checks.extend(checks)
        return report

    return step

