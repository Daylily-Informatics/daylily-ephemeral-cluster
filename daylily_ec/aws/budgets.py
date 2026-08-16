"""BudgetManager — create/verify AWS Budgets (replaces bin/create_budget.sh).

Exact-parity with the Bash script::

    bin/create_budget.sh -p <project> -a <amount> -r <region>
                         -e <email> -t <thresholds> -c <cluster>
                         -z <az> -b <bucket_url> -u <users>

Two budget types:
- **Global**: ``daylily-global`` with thresholds [25, 50, 75, 99]
- **Cluster**: cluster-name budget with threshold [75]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
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

TAGS_FILE_S3_SUFFIX = "runtime_assets/budget_tags/pcluster-project-budget-tags.tsv"
"""Relative path under the S3 bucket for the budget tags TSV."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_budget_dict(
    budget_name: str,
    amount: str,
    cluster_name: str,
) -> Dict[str, Any]:
    """Return a cluster-tag-scoped AWS Budget dict."""
    return {
        "BudgetLimit": {"Amount": str(amount), "Unit": "USD"},
        "BudgetName": budget_name,
        "BudgetType": "COST",
        "CostFilters": {
            "TagKeyValue": [
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
    """Return ``True`` only when *budget_name* exists.

    Budget inspection errors are not treated as "missing"; callers need those
    failures to stop before an attempted duplicate create.
    """
    try:
        budgets_client.describe_budget(AccountId=account_id, BudgetName=budget_name)
        return True
    except Exception as exc:
        if _is_budget_not_found(exc):
            return False
        raise


def _is_budget_not_found(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = str((response.get("Error") or {}).get("Code") or "")
        if code in {"NotFoundException", "ResourceNotFoundException"}:
            return True
    name = exc.__class__.__name__
    if name in {"NotFoundException", "ResourceNotFoundException"}:
        return True
    text = str(exc)
    if "NotFoundException" in text or "not found" in text.lower():
        return True
    return False


def describe_budget(
    budgets_client: Any,
    account_id: str,
    budget_name: str,
) -> Dict[str, Any] | None:
    try:
        return budgets_client.describe_budget(
            AccountId=account_id,
            BudgetName=budget_name,
        ).get("Budget")
    except Exception as exc:
        if _is_budget_not_found(exc):
            return None
        raise


# ---------------------------------------------------------------------------
# Budget creation
# ---------------------------------------------------------------------------


def create_budget(
    budgets_client: Any,
    account_id: str,
    budget_name: str,
    amount: str,
    cluster_name: str,
) -> None:
    """Create a single AWS Budget (idempotent — no-op if exists)."""
    if budget_exists(budgets_client, account_id, budget_name):
        log.info("Budget '%s' already exists, skipping creation", budget_name)
        return
    budget = _build_budget_dict(budget_name, amount, cluster_name)
    budgets_client.create_budget(AccountId=account_id, Budget=budget)
    log.info("Created budget '%s' (%s USD/month)", budget_name, amount)


@dataclass(frozen=True)
class BudgetLimitUpdateResult:
    """Verified result of planning or applying one fixed-budget limit update."""

    budget_name: str
    previous_amount: str
    requested_amount: str
    observed_amount: str
    unit: str
    changed: bool
    dry_run: bool
    update_submitted: bool


def _positive_decimal(value: object, *, label: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a positive USD decimal") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"{label} must be a positive USD decimal")
    return amount


def _fixed_monthly_usd_limit(budget: Dict[str, Any]) -> tuple[Decimal, str]:
    if budget.get("BudgetType") != "COST":
        raise ValueError("AWS Budget must be a COST budget")
    if budget.get("TimeUnit") != "MONTHLY":
        raise ValueError("AWS Budget must use the MONTHLY time unit")
    if budget.get("PlannedBudgetLimits"):
        raise ValueError("planned AWS Budgets cannot be changed with the fixed-limit command")
    if budget.get("AutoAdjustData"):
        raise ValueError(
            "auto-adjusting AWS Budgets cannot be changed with the fixed-limit command"
        )

    limit = budget.get("BudgetLimit")
    if not isinstance(limit, dict):
        raise ValueError("AWS Budget is missing its fixed BudgetLimit")
    unit = str(limit.get("Unit") or "")
    if unit != "USD":
        raise ValueError("AWS Budget limit unit must be USD")
    return _positive_decimal(limit.get("Amount"), label="current budget amount"), unit


def _filter_contract_fields(budget: Dict[str, Any]) -> tuple[str, str]:
    """Return the one complete AWS Budgets filter contract in use."""

    legacy_fields = ("CostFilters", "CostTypes")
    expression_fields = ("FilterExpression", "Metrics")
    legacy_present = tuple(field for field in legacy_fields if field in budget)
    expression_present = tuple(field for field in expression_fields if field in budget)

    if legacy_present and expression_present:
        raise ValueError("AWS Budget mixes legacy and expression filter contracts; refusing update")
    if legacy_present and legacy_present != legacy_fields:
        raise ValueError("AWS Budget has an incomplete CostFilters/CostTypes contract")
    if expression_present and expression_present != expression_fields:
        raise ValueError("AWS Budget has an incomplete FilterExpression/Metrics contract")
    if not legacy_present and not expression_present:
        raise ValueError("AWS Budget is missing its filter and metric contract")
    return legacy_fields if legacy_present else expression_fields


def update_budget_limit(
    budgets_client: Any,
    account_id: str,
    budget_name: str,
    amount: str,
    *,
    expected_current_amount: str,
    dry_run: bool = False,
) -> BudgetLimitUpdateResult:
    """Replace the monthly limit of an existing AWS Budget.

    AWS Budgets returns read-only fields from ``describe_budget`` which cannot
    be sent back to ``update_budget``. This path supports fixed monthly USD
    cost budgets only, preserves their documented mutable contract, and changes
    only ``BudgetLimit`` after the caller proves the observed current limit.
    """

    normalized_amount = _positive_decimal(amount, label="budget amount")
    expected_amount = _positive_decimal(
        expected_current_amount,
        label="expected current budget amount",
    )

    existing = describe_budget(budgets_client, account_id, budget_name)
    if existing is None:
        raise ValueError(f"AWS Budget '{budget_name}' does not exist")
    current_amount, unit = _fixed_monthly_usd_limit(existing)
    filter_fields = _filter_contract_fields(existing)
    if current_amount != expected_amount:
        raise ValueError(
            f"AWS Budget '{budget_name}' expected current limit "
            f"{format(expected_amount, 'f')} USD but observed "
            f"{format(current_amount, 'f')} USD"
        )

    mutable_fields = (
        "BudgetName",
        "BudgetType",
        *filter_fields,
        "TimeUnit",
        "TimePeriod",
        "BillingViewArn",
    )
    new_budget = {
        field: existing[field]
        for field in mutable_fields
        if field in existing and existing[field] is not None
    }
    new_budget["BudgetName"] = budget_name
    new_budget["BudgetLimit"] = {
        "Amount": format(normalized_amount, "f"),
        "Unit": unit,
    }
    changed = current_amount != normalized_amount
    update_submitted = changed and not dry_run
    observed_amount = current_amount
    if update_submitted:
        budgets_client.update_budget(AccountId=account_id, NewBudget=new_budget)
        observed = describe_budget(budgets_client, account_id, budget_name)
        if observed is None:
            raise RuntimeError(f"AWS Budget '{budget_name}' disappeared after update")
        observed_amount, observed_unit = _fixed_monthly_usd_limit(observed)
        if observed_unit != unit or observed_amount != normalized_amount:
            raise RuntimeError(
                f"AWS Budget '{budget_name}' update verification failed: expected "
                f"{format(normalized_amount, 'f')} {unit}, observed "
                f"{format(observed_amount, 'f')} {observed_unit}"
            )
        log.info(
            "Updated budget '%s' from %s to %s USD/month",
            budget_name,
            format(current_amount, "f"),
            format(observed_amount, "f"),
        )

    return BudgetLimitUpdateResult(
        budget_name=budget_name,
        previous_amount=format(current_amount, "f"),
        requested_amount=format(normalized_amount, "f"),
        observed_amount=format(observed_amount, "f"),
        unit=unit,
        changed=changed,
        dry_run=dry_run,
        update_submitted=update_submitted,
    )


def create_notifications(
    budgets_client: Any,
    account_id: str,
    budget_name: str,
    thresholds: List[int],
    email: str,
) -> None:
    """Add threshold notifications to an existing budget."""
    email = email.strip()
    if not email:
        log.info("No budget notification email configured for '%s'; skipping notifications.", budget_name)
        return
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
    """Upsert a line in the S3 budget-tags TSV.

    File path: ``s3://<reference-bucket>/runtime_assets/budget_tags/pcluster-project-budget-tags.tsv``

    Each line: ``<project_name>\\tubuntu,<users>``
    """
    key = TAGS_FILE_S3_SUFFIX
    existing = ""
    try:
        resp = s3_client.get_object(Bucket=bucket_name, Key=key)
        existing = resp["Body"].read().decode("utf-8", errors="replace")
    except Exception:
        log.debug("Tags file not found; will create a new one")

    allowed_users = _normalize_allowed_budget_users(users)
    new_line = f"{project_name}\t{allowed_users}\n"
    body_lines = []
    replaced = False
    for raw_line in existing.splitlines():
        if raw_line.split("\t", 1)[0] == project_name:
            if not replaced:
                body_lines.append(new_line.rstrip("\n"))
                replaced = True
            continue
        body_lines.append(raw_line)
    if not replaced:
        body_lines.append(new_line.rstrip("\n"))
    body = "\n".join(body_lines).rstrip("\n") + "\n"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=body.encode("utf-8"),
    )
    log.info("Updated tags file s3://%s/%s", bucket_name, key)


def _normalize_allowed_budget_users(users: str) -> str:
    values = ["ubuntu"]
    seen = {"ubuntu"}
    for item in users.split(","):
        value = item.strip()
        if not value or value in seen:
            continue
        values.append(value)
        seen.add(value)
    return ",".join(values)


# ---------------------------------------------------------------------------
# High-level ensure functions
# ---------------------------------------------------------------------------


def cluster_budget_name(region_az: str, cluster_name: str) -> str:
    """Derive the per-cluster budget name."""
    _ = region_az
    return cluster_name


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
        create_budget(budgets_client, account_id, name, amount, cluster_name)
        create_notifications(budgets_client, account_id, name, GLOBAL_THRESHOLDS, email)
    else:
        log.info("Global budget '%s' already exists", name)
    update_tags_file(s3_client, bucket_name, name, allowed_users, region)
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
    """Ensure the per-cluster budget exists.

    Returns the budget name.
    """
    name = cluster_budget_name(region_az, cluster_name)
    already = budget_exists(budgets_client, account_id, name)
    if not already:
        create_budget(budgets_client, account_id, name, amount, cluster_name)
        create_notifications(budgets_client, account_id, name, CLUSTER_THRESHOLDS, email)
    else:
        log.info("Cluster budget '%s' already exists", name)
    update_tags_file(s3_client, bucket_name, name, allowed_users, region)
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
    try:
        g_exists = budget_exists(budgets_client, account_id, global_budget_name)
        c_name = cluster_budget_name(region_az, cluster_name) if cluster_name and region_az else ""
        c_exists = budget_exists(budgets_client, account_id, c_name) if c_name else False
    except Exception as exc:
        return CheckResult(
            id="budget.readiness",
            status=CheckStatus.FAIL,
            details={
                "global_budget": global_budget_name,
                "cluster_budget": (
                    cluster_budget_name(region_az, cluster_name)
                    if cluster_name and region_az
                    else ""
                ),
                "error": str(exc),
            },
            remediation="Grant budget read access and verify AWS Budgets can be inspected.",
        )

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
