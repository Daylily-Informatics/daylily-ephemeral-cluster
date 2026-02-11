"""Drift detection for Layer 1 and Layer 3 resources (CP-016).

Compares a persisted :class:`StateRecord` against live AWS state to
detect configuration drift without mutating anything.

Exit code convention: ``3`` = drift detected (for the CLI ``dayctl drift check``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from daylily_ec.state.models import StateRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DriftStatus
# ---------------------------------------------------------------------------


class DriftStatus(str, Enum):
    """Outcome of a single drift check."""

    OK = "OK"
    DRIFTED = "DRIFTED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# DriftCheck — a single check result
# ---------------------------------------------------------------------------


@dataclass
class DriftCheck:
    """Result of one drift check (e.g. CFN stack, budget, heartbeat)."""

    id: str
    status: DriftStatus
    expected: str = ""
    actual: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


# ---------------------------------------------------------------------------
# DriftReport — aggregate
# ---------------------------------------------------------------------------


@dataclass
class DriftReport:
    """Aggregate drift report for a cluster run."""

    cluster_name: str
    checks: List[DriftCheck] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return any(c.status == DriftStatus.DRIFTED for c in self.checks)

    @property
    def has_errors(self) -> bool:
        return any(c.status == DriftStatus.ERROR for c in self.checks)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (sorted for determinism)."""
        return {
            "cluster_name": self.cluster_name,
            "has_drift": self.has_drift,
            "checks": [
                {
                    "actual": c.actual,
                    "details": c.details,
                    "error": c.error,
                    "expected": c.expected,
                    "id": c.id,
                    "status": c.status.value,
                }
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Individual drift checkers
# ---------------------------------------------------------------------------


def check_cfn_drift(
    cfn_client: Any,
    state: StateRecord,
) -> DriftCheck:
    """Check whether the baseline CFN stack still exists and is not drifted."""
    stack_name = state.cfn_stack_name
    if not stack_name:
        return DriftCheck(
            id="cfn.stack",
            status=DriftStatus.OK,
            details={"reason": "no stack recorded in state"},
        )
    try:
        resp = cfn_client.describe_stacks(StackName=stack_name)
        stacks = resp.get("Stacks", [])
        if not stacks:
            return DriftCheck(
                id="cfn.stack",
                status=DriftStatus.DRIFTED,
                expected=stack_name,
                actual="<not found>",
            )
        status = stacks[0].get("StackStatus", "")
        if "COMPLETE" in status:
            return DriftCheck(
                id="cfn.stack",
                status=DriftStatus.OK,
                expected=stack_name,
                actual=status,
            )
        return DriftCheck(
            id="cfn.stack",
            status=DriftStatus.DRIFTED,
            expected="*_COMPLETE",
            actual=status,
        )
    except Exception as exc:
        return DriftCheck(
            id="cfn.stack",
            status=DriftStatus.ERROR,
            error=str(exc),
        )


def check_budget_drift(
    budgets_client: Any,
    account_id: str,
    state: StateRecord,
) -> List[DriftCheck]:
    """Verify that recorded budgets still exist."""
    results: List[DriftCheck] = []
    for label, name in [
        ("budget.global", state.global_budget_name),
        ("budget.cluster", state.cluster_budget_name),
    ]:
        if not name:
            continue
        try:
            budgets_client.describe_budget(
                AccountId=account_id,
                BudgetName=name,
            )
            results.append(
                DriftCheck(id=label, status=DriftStatus.OK, expected=name, actual=name)
            )
        except Exception as exc:
            err = str(exc)
            if "NotFoundException" in err:
                results.append(
                    DriftCheck(
                        id=label,
                        status=DriftStatus.DRIFTED,
                        expected=name,
                        actual="<not found>",
                    )
                )
            else:
                results.append(
                    DriftCheck(id=label, status=DriftStatus.ERROR, error=err)
                )
    return results


def check_heartbeat_drift(
    sns_client: Any,
    scheduler_client: Any,
    state: StateRecord,
) -> List[DriftCheck]:
    """Verify that the heartbeat SNS topic and schedule still exist."""
    results: List[DriftCheck] = []

    # SNS topic
    topic_arn = state.heartbeat_topic_arn
    if topic_arn:
        try:
            sns_client.get_topic_attributes(TopicArn=topic_arn)
            results.append(
                DriftCheck(
                    id="heartbeat.topic",
                    status=DriftStatus.OK,
                    expected=topic_arn,
                    actual=topic_arn,
                )
            )
        except Exception as exc:
            results.append(
                DriftCheck(
                    id="heartbeat.topic",
                    status=DriftStatus.DRIFTED,
                    expected=topic_arn,
                    actual="<not found>",
                    error=str(exc),
                )
            )

    # EventBridge schedule
    schedule_name = state.heartbeat_schedule_name
    if schedule_name:
        try:
            scheduler_client.get_schedule(Name=schedule_name, GroupName="default")
            results.append(
                DriftCheck(
                    id="heartbeat.schedule",
                    status=DriftStatus.OK,
                    expected=schedule_name,
                    actual=schedule_name,
                )
            )
        except Exception as exc:
            results.append(
                DriftCheck(
                    id="heartbeat.schedule",
                    status=DriftStatus.DRIFTED,
                    expected=schedule_name,
                    actual="<not found>",
                    error=str(exc),
                )
            )

    return results


# ---------------------------------------------------------------------------
# Top-level drift check
# ---------------------------------------------------------------------------


def run_drift_check(
    state: StateRecord,
    *,
    cfn_client: Optional[Any] = None,
    budgets_client: Optional[Any] = None,
    sns_client: Optional[Any] = None,
    scheduler_client: Optional[Any] = None,
    account_id: str = "",
) -> DriftReport:
    """Run all drift checks against *state* and return a :class:`DriftReport`.

    Clients that are ``None`` cause their respective checks to be skipped.
    """
    report = DriftReport(cluster_name=state.cluster_name or "unknown")

    if cfn_client is not None:
        report.checks.append(check_cfn_drift(cfn_client, state))

    if budgets_client is not None:
        report.checks.extend(
            check_budget_drift(budgets_client, account_id or state.account_id, state)
        )

    if sns_client is not None and scheduler_client is not None:
        report.checks.extend(
            check_heartbeat_drift(sns_client, scheduler_client, state)
        )

    return report

