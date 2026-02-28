"""BudgetManager — create/verify AWS Budgets (replaces bin/create_budget.sh).

Exact-parity with the Bash script::

    bin/create_budget.sh -p <project> -a <amount> -r <region>
                         -e <email> -t <thresholds> -c <cluster>
                         -z <az> -b <bucket_url> -u <users>

Two budget types:
- **Global**: ``daylily-global`` with thresholds [25, 50, 75, 99]
- **Cluster**: ``da-<region_az>-<cluster>`` with threshold [75]
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from daylily_ec.state.models import CheckResult, CheckStatus

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GLOBAL_BUDGET_NAME = "daylily-global"
"""Name used for the account-wide budget."""

GLOBAL_THRESHOLDS: List[int] = [25, 50, 75, 99]
"""Notification thresholds for the global budget (percent)."""

CLUSTER_THRESHOLDS: List[int] = [75]
"""Notification thresholds for per-cluster budgets (percent)."""

TAGS_FILE_S3_SUFFIX = "data/budget_tags/pcluster-project-budget-tags.tsv"
"""Relative path under the S3 bucket for the budget tags TSV."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_budget_dict(
    budget_name: str,
    amount: str,
    project_name: str,
    cluster_name: str,
) -> Dict[str, Any]:
    """Return a budget dict matching the Bash BUDGET_TEMPLATE exactly."""
    return {
        "BudgetLimit": {"Amount": str(amount), "Unit": "USD"},
        "BudgetName": budget_name,
        "BudgetType": "COST",
        "CostFilters": {
            "TagKeyValue": [
                f"user:aws-parallelcluster-project${project_name}",
                f"user:aws-parallelcluster-clustername${cluster_name}",
            ],
        },
        "CostTypes": {
            "IncludeCredit": True,
            "IncludeDiscount": True,
            "IncludeOtherSubscription": True,
            "IncludeRecurring": True,
            "IncludeRefund": True,
            "IncludeSubscription": True,
            "IncludeSupport": True,
            "IncludeTax": True,
            "IncludeUpfront": True,
            "UseBlended": False,
        },
        "TimeUnit": "MONTHLY",
    }


def _notification_dict(threshold: int) -> Dict[str, Any]:
    """Return a notification dict matching the Bash create-notification call."""
    return {
        "ComparisonOperator": "GREATER_THAN",
        "NotificationType": "ACTUAL",
        "Threshold": float(threshold),
        "ThresholdType": "PERCENTAGE",
    }


def _subscriber_dict(email: str) -> Dict[str, Any]:
    """Return a subscriber dict for an email address."""
    return {"Address": email, "SubscriptionType": "EMAIL"}


# ---------------------------------------------------------------------------
# Budget existence check
# ---------------------------------------------------------------------------


def budget_exists(
    budgets_client: Any,
    account_id: str,
    budget_name: str,
) -> bool:
    """Return ``True`` if a budget named *budget_name* already exists.

    Mirrors the Bash check::

        aws budgets describe-budgets \\
            --query "Budgets[?BudgetName=='<name>'] | [0].BudgetName"
    """
    try:
        resp = budgets_client.describe_budgets(AccountId=account_id)
        for b in resp.get("Budgets", []):
            if b.get("BudgetName") == budget_name:
                return True
        return False
    except Exception:
        log.debug("budget_exists: could not list budgets", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Budget creation
# ---------------------------------------------------------------------------


def create_budget(
    budgets_client: Any,
    account_id: str,
    budget_name: str,
    amount: str,
    project_name: str,
    cluster_name: str,
) -> None:
    """Create a single AWS Budget (idempotent — no-op if exists)."""
    if budget_exists(budgets_client, account_id, budget_name):
        log.info("Budget '%s' already exists, skipping creation", budget_name)
        return
    budget = _build_budget_dict(budget_name, amount, project_name, cluster_name)
    budgets_client.create_budget(AccountId=account_id, Budget=budget)
    log.info("Created budget '%s' (%s USD/month)", budget_name, amount)


def create_notifications(
    budgets_client: Any,
    account_id: str,
    budget_name: str,
    thresholds: List[int],
    email: str,
) -> None:
    """Add threshold notifications to an existing budget."""
    for thr in thresholds:
        try:
            budgets_client.create_notification(
                AccountId=account_id,
                BudgetName=budget_name,
                Notification=_notification_dict(thr),
                Subscribers=[_subscriber_dict(email)],
            )
            log.info("Created %d%% notification on '%s'", thr, budget_name)
        except Exception:
            log.warning(
                "Failed to create %d%% notification on '%s'",
                thr,
                budget_name,
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# S3 tags-file update
# ---------------------------------------------------------------------------


def update_tags_file(
    s3_client: Any,
    bucket_name: str,
    project_name: str,
    users: str,
    region: str,
) -> None:
    """Append a line to the S3 budget-tags TSV (Bash ``write_or_append_tags_to_s3``).

    File path: ``s3://<bucket>/data/budget_tags/pcluster-project-budget-tags.tsv``

    Each line: ``<project_name>\\tubuntu,<users>``
    """
    key = TAGS_FILE_S3_SUFFIX
    existing = ""
    try:
        resp = s3_client.get_object(Bucket=bucket_name, Key=key)
        existing = resp["Body"].read().decode("utf-8", errors="replace")
    except Exception:
        log.debug("Tags file not found; will create a new one")

    new_line = f"{project_name}\tubuntu,{users}\n"
    body = existing + new_line

    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=body.encode("utf-8"),
    )
    log.info("Updated tags file s3://%s/%s", bucket_name, key)


# ---------------------------------------------------------------------------
# High-level ensure functions
# ---------------------------------------------------------------------------


def cluster_budget_name(region_az: str, cluster_name: str) -> str:
    """Derive the per-cluster budget name (Bash: ``da-<region_az>-<cluster>``)."""
    return f"da-{region_az}-{cluster_name}"


def ensure_global_budget(
    budgets_client: Any,
    s3_client: Any,
    account_id: str,
    *,
    amount: str,
    cluster_name: str,
    email: str,
    region: str,
    region_az: str,
    bucket_name: str,
    allowed_users: str,
) -> str:
    """Ensure the ``daylily-global`` budget exists with notifications.

    Returns the budget name.
    """
    name = GLOBAL_BUDGET_NAME
    already = budget_exists(budgets_client, account_id, name)
    if not already:
        create_budget(
            budgets_client, account_id, name, amount, name, cluster_name
        )
        create_notifications(
            budgets_client, account_id, name, GLOBAL_THRESHOLDS, email
        )
        update_tags_file(s3_client, bucket_name, name, allowed_users, region)
    else:
        log.info("Global budget '%s' already exists", name)
    return name


def ensure_cluster_budget(
    budgets_client: Any,
    s3_client: Any,
    account_id: str,
    *,
    amount: str,
    cluster_name: str,
    email: str,
    region: str,
    region_az: str,
    bucket_name: str,
    allowed_users: str,
) -> str:
    """Ensure the per-cluster budget ``da-<region_az>-<cluster>`` exists.

    Returns the budget name.
    """
    name = cluster_budget_name(region_az, cluster_name)
    already = budget_exists(budgets_client, account_id, name)
    if not already:
        create_budget(
            budgets_client, account_id, name, amount, name, cluster_name
        )
        create_notifications(
            budgets_client, account_id, name, CLUSTER_THRESHOLDS, email
        )
        update_tags_file(s3_client, bucket_name, name, allowed_users, region)
    else:
        log.info("Cluster budget '%s' already exists", name)
    return name


# ---------------------------------------------------------------------------
# Preflight step factory
# ---------------------------------------------------------------------------


def make_budget_preflight_step(
    budgets_client: Any,
    account_id: str,
    *,
    global_budget_name: str = GLOBAL_BUDGET_NAME,
    cluster_name: str = "",
    region_az: str = "",
) -> CheckResult:
    """Return a :class:`CheckResult` reporting budget readiness.

    - PASS: both global and cluster budgets exist
    - WARN: global exists but cluster does not (will be created)
    - WARN: neither exists (will be created)
    - FAIL: only on API error
    """
    g_exists = budget_exists(budgets_client, account_id, global_budget_name)
    c_name = cluster_budget_name(region_az, cluster_name) if cluster_name and region_az else ""
    c_exists = budget_exists(budgets_client, account_id, c_name) if c_name else False

    details = {
        "global_budget": global_budget_name,
        "global_exists": g_exists,
        "cluster_budget": c_name,
        "cluster_exists": c_exists,
    }

    if g_exists and c_exists:
        return CheckResult(
            id="budget.readiness",
            status=CheckStatus.PASS,
            details=details,
        )

    missing = []
    if not g_exists:
        missing.append(global_budget_name)
    if c_name and not c_exists:
        missing.append(c_name)

    return CheckResult(
        id="budget.readiness",
        status=CheckStatus.WARN,
        details=details,
        remediation=f"Budgets will be created: {', '.join(missing)}",
    )

