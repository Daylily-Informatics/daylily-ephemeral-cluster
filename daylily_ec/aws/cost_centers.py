"""Global cost-center registry backed by DynamoDB."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Sequence


DEFAULT_COST_CENTER_HOME_REGION = "us-west-2"
DEFAULT_COST_CENTER_TABLE = "dayec-cost-centers"
DEFAULT_COST_CENTER_USAGE_TABLE = "dayec-cost-center-usage"
RESERVED_IDLE_COST_CENTER = "idle"

VALID_STATUSES = {"active", "disabled", "system"}
COST_CENTER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,127}$")
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


class CostCenterError(RuntimeError):
    """Raised when cost-center registry operations cannot continue safely."""


@dataclass(frozen=True)
class CostCenter:
    name: str
    status: str
    monthly_cap_usd: Decimal
    allowed_users: tuple[str, ...]
    allowed_groups: tuple[str, ...]
    owner_emails: tuple[str, ...]
    notes: str
    created_at: str
    created_by_arn: str
    updated_at: str
    updated_by_arn: str
    disabled_at: str = ""
    disabled_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "cost_center": self.name,
            "status": self.status,
            "monthly_cap_usd": str(self.monthly_cap_usd),
            "allowed_users": list(self.allowed_users),
            "allowed_groups": list(self.allowed_groups),
            "owner_emails": list(self.owner_emails),
            "notes": self.notes,
            "created_at": self.created_at,
            "created_by_arn": self.created_by_arn,
            "updated_at": self.updated_at,
            "updated_by_arn": self.updated_by_arn,
            "disabled_at": self.disabled_at,
            "disabled_reason": self.disabled_reason,
        }


@dataclass(frozen=True)
class CostCenterUsage:
    name: str
    month: str
    monthly_spend_usd: Decimal
    latest_processed_hour: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "cost_center": self.name,
            "month": self.month,
            "monthly_spend_usd": str(self.monthly_spend_usd),
            "latest_processed_hour": self.latest_processed_hour,
            "updated_at": self.updated_at,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_cost_center_name(name: str, *, allow_idle: bool = False) -> str:
    value = str(name or "").strip()
    if not value:
        raise CostCenterError("Cost-center name must be non-empty.")
    if any(ch.isspace() for ch in value) or "|" in value:
        raise CostCenterError("Cost-center name must not contain whitespace or '|'.")
    if not COST_CENTER_NAME_RE.fullmatch(value):
        raise CostCenterError(
            "Cost-center name must start with a letter or number and contain only "
            "letters, numbers, '.', '_', ':', '@', '+', or '-'."
        )
    if value == RESERVED_IDLE_COST_CENTER and not allow_idle:
        raise CostCenterError("'idle' is a reserved system cost center.")
    return value


def validate_month(month: str) -> str:
    value = str(month or "").strip()
    if not MONTH_RE.fullmatch(value):
        raise CostCenterError("Usage month must be YYYY-MM.")
    return value


def validate_latest_processed_hour(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CostCenterError("latest_processed_hour must be non-empty.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CostCenterError("latest_processed_hour must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise CostCenterError("latest_processed_hour must include a timezone.")
    utc = parsed.astimezone(timezone.utc).replace(microsecond=0)
    if utc.minute != 0 or utc.second != 0:
        raise CostCenterError("latest_processed_hour must be rounded to the UTC hour.")
    return utc.isoformat().replace("+00:00", "Z")


def ensure_cost_center_registry(
    dynamodb_client: Any,
    *,
    table_name: str = DEFAULT_COST_CENTER_TABLE,
    usage_table_name: str = DEFAULT_COST_CENTER_USAGE_TABLE,
    actor_arn: str = "",
    now: str | None = None,
) -> dict[str, str]:
    """Ensure registry and usage tables exist and reserve system `idle`."""
    _ensure_registry_table(dynamodb_client, table_name)
    _ensure_usage_table(dynamodb_client, usage_table_name)
    timestamp = now or utc_now_iso()
    idle = get_cost_center(
        dynamodb_client,
        RESERVED_IDLE_COST_CENTER,
        table_name=table_name,
        allow_missing=True,
        allow_idle=True,
    )
    if idle is None:
        _put_cost_center(
            dynamodb_client,
            table_name,
            CostCenter(
                name=RESERVED_IDLE_COST_CENTER,
                status="system",
                monthly_cap_usd=Decimal("0"),
                allowed_users=(),
                allowed_groups=(),
                owner_emails=(),
                notes="System-owned idle allocation bucket.",
                created_at=timestamp,
                created_by_arn=actor_arn,
                updated_at=timestamp,
                updated_by_arn=actor_arn,
            ),
            condition="attribute_not_exists(cost_center)",
        )
    elif idle.status != "system":
        raise CostCenterError("Reserved 'idle' cost center exists but is not system-owned.")

    return {"registry_table": table_name, "usage_table": usage_table_name, "idle": "system"}


def create_cost_center(
    dynamodb_client: Any,
    name: str,
    *,
    monthly_cap_usd: str | Decimal,
    allowed_users: Sequence[str] = (),
    allowed_groups: Sequence[str] = (),
    owner_emails: Sequence[str] = (),
    notes: str = "",
    actor_arn: str = "",
    table_name: str = DEFAULT_COST_CENTER_TABLE,
    usage_table_name: str = DEFAULT_COST_CENTER_USAGE_TABLE,
    now: str | None = None,
) -> CostCenter:
    resolved_name = validate_cost_center_name(name)
    cap = _validate_decimal(monthly_cap_usd, field="monthly_cap_usd")
    users = _normalize_list(allowed_users, field="allowed_users")
    groups = _normalize_list(allowed_groups, field="allowed_groups")
    if not users and not groups:
        raise CostCenterError("At least one allowed user or allowed group is required.")
    timestamp = now or utc_now_iso()
    item = CostCenter(
        name=resolved_name,
        status="active",
        monthly_cap_usd=cap,
        allowed_users=users,
        allowed_groups=groups,
        owner_emails=_normalize_list(owner_emails, field="owner_emails"),
        notes=str(notes or ""),
        created_at=timestamp,
        created_by_arn=actor_arn,
        updated_at=timestamp,
        updated_by_arn=actor_arn,
    )
    # Seed usage before publishing an active registry row. A failed registry write
    # may leave an inert usage row, but a failed usage write cannot leave a cost
    # center that is authorized yet impossible to submit against.
    initialize_cost_center_usage(
        dynamodb_client,
        resolved_name,
        usage_table_name=usage_table_name,
        now=timestamp,
    )
    _put_cost_center(dynamodb_client, table_name, item, condition="attribute_not_exists(cost_center)")
    return item


def edit_cost_center(
    dynamodb_client: Any,
    name: str,
    *,
    monthly_cap_usd: str | Decimal | None = None,
    allowed_users: Sequence[str] | None = None,
    allowed_groups: Sequence[str] | None = None,
    owner_emails: Sequence[str] | None = None,
    notes: str | None = None,
    status: str | None = None,
    actor_arn: str = "",
    table_name: str = DEFAULT_COST_CENTER_TABLE,
    now: str | None = None,
) -> CostCenter:
    resolved_name = validate_cost_center_name(name)
    current = get_cost_center(dynamodb_client, resolved_name, table_name=table_name)
    changes = [
        monthly_cap_usd is not None,
        allowed_users is not None,
        allowed_groups is not None,
        owner_emails is not None,
        notes is not None,
        status is not None,
    ]
    if not any(changes):
        raise CostCenterError("No edit fields were provided.")
    if status is not None and status not in {"active", "disabled"}:
        raise CostCenterError("Cost-center status must be active or disabled.")
    users = current.allowed_users if allowed_users is None else _normalize_list(allowed_users, field="allowed_users")
    groups = current.allowed_groups if allowed_groups is None else _normalize_list(allowed_groups, field="allowed_groups")
    if not users and not groups:
        raise CostCenterError("At least one allowed user or allowed group is required.")
    timestamp = now or utc_now_iso()
    updated = CostCenter(
        name=current.name,
        status=current.status if status is None else status,
        monthly_cap_usd=current.monthly_cap_usd
        if monthly_cap_usd is None
        else _validate_decimal(monthly_cap_usd, field="monthly_cap_usd"),
        allowed_users=users,
        allowed_groups=groups,
        owner_emails=current.owner_emails
        if owner_emails is None
        else _normalize_list(owner_emails, field="owner_emails"),
        notes=current.notes if notes is None else str(notes),
        created_at=current.created_at,
        created_by_arn=current.created_by_arn,
        updated_at=timestamp,
        updated_by_arn=actor_arn,
        disabled_at=current.disabled_at,
        disabled_reason=current.disabled_reason,
    )
    _put_cost_center(dynamodb_client, table_name, updated, condition="attribute_exists(cost_center)")
    return updated


def disable_cost_center(
    dynamodb_client: Any,
    name: str,
    *,
    reason: str,
    actor_arn: str = "",
    table_name: str = DEFAULT_COST_CENTER_TABLE,
    now: str | None = None,
) -> CostCenter:
    resolved_name = validate_cost_center_name(name)
    if not str(reason or "").strip():
        raise CostCenterError("A disable reason is required.")
    current = get_cost_center(dynamodb_client, resolved_name, table_name=table_name)
    timestamp = now or utc_now_iso()
    updated = CostCenter(
        name=current.name,
        status="disabled",
        monthly_cap_usd=current.monthly_cap_usd,
        allowed_users=current.allowed_users,
        allowed_groups=current.allowed_groups,
        owner_emails=current.owner_emails,
        notes=current.notes,
        created_at=current.created_at,
        created_by_arn=current.created_by_arn,
        updated_at=timestamp,
        updated_by_arn=actor_arn,
        disabled_at=timestamp,
        disabled_reason=str(reason).strip(),
    )
    _put_cost_center(dynamodb_client, table_name, updated, condition="attribute_exists(cost_center)")
    return updated


def get_cost_center(
    dynamodb_client: Any,
    name: str,
    *,
    table_name: str = DEFAULT_COST_CENTER_TABLE,
    allow_missing: bool = False,
    allow_idle: bool = False,
) -> CostCenter | None:
    resolved_name = validate_cost_center_name(name, allow_idle=allow_idle)
    response = dynamodb_client.get_item(
        TableName=table_name,
        Key={"cost_center": {"S": resolved_name}},
        ConsistentRead=True,
    )
    raw = response.get("Item")
    if not raw:
        if allow_missing:
            return None
        raise CostCenterError(f"Cost center '{resolved_name}' does not exist.")
    return _cost_center_from_item(raw)


def list_cost_centers(
    dynamodb_client: Any,
    *,
    table_name: str = DEFAULT_COST_CENTER_TABLE,
    status: str = "all",
) -> list[CostCenter]:
    if status not in VALID_STATUSES | {"all"}:
        raise CostCenterError("status must be active, disabled, system, or all.")
    items: list[CostCenter] = []
    kwargs: dict[str, Any] = {"TableName": table_name}
    while True:
        response = dynamodb_client.scan(**kwargs)
        for raw in response.get("Items", []):
            item = _cost_center_from_item(raw)
            if status == "all" or item.status == status:
                items.append(item)
        token = response.get("LastEvaluatedKey")
        if not token:
            break
        kwargs["ExclusiveStartKey"] = token
    return sorted(items, key=lambda item: item.name)


def get_cost_center_usage(
    dynamodb_client: Any,
    name: str,
    *,
    month: str,
    usage_table_name: str = DEFAULT_COST_CENTER_USAGE_TABLE,
    allow_missing: bool = False,
    allow_idle: bool = True,
) -> CostCenterUsage | None:
    resolved_name = validate_cost_center_name(name, allow_idle=allow_idle)
    resolved_month = validate_month(month)
    response = dynamodb_client.get_item(
        TableName=usage_table_name,
        Key={
            "cost_center": {"S": resolved_name},
            "month": {"S": resolved_month},
        },
        ConsistentRead=True,
    )
    raw = response.get("Item")
    if not raw:
        if allow_missing:
            return None
        raise CostCenterError(
            f"No usage snapshot for cost center '{resolved_name}' month '{resolved_month}'."
        )
    return _usage_from_item(raw)


def list_cost_center_usage(
    dynamodb_client: Any,
    *,
    month: str,
    usage_table_name: str = DEFAULT_COST_CENTER_USAGE_TABLE,
) -> list[CostCenterUsage]:
    resolved_month = validate_month(month)
    items: list[CostCenterUsage] = []
    kwargs: dict[str, Any] = {"TableName": usage_table_name}
    while True:
        response = dynamodb_client.scan(**kwargs)
        for raw in response.get("Items", []):
            usage = _usage_from_item(raw)
            if usage.month == resolved_month:
                items.append(usage)
        token = response.get("LastEvaluatedKey")
        if not token:
            break
        kwargs["ExclusiveStartKey"] = token
    return sorted(items, key=lambda item: item.name)


def put_cost_center_usage(
    dynamodb_client: Any,
    usage: CostCenterUsage,
    *,
    usage_table_name: str = DEFAULT_COST_CENTER_USAGE_TABLE,
) -> CostCenterUsage:
    normalized = CostCenterUsage(
        name=validate_cost_center_name(usage.name, allow_idle=True),
        month=validate_month(usage.month),
        monthly_spend_usd=_validate_decimal(usage.monthly_spend_usd, field="monthly_spend_usd"),
        latest_processed_hour=validate_latest_processed_hour(usage.latest_processed_hour),
        updated_at=str(usage.updated_at or utc_now_iso()).strip(),
    )
    dynamodb_client.put_item(TableName=usage_table_name, Item=_usage_to_item(normalized))
    return normalized


def initialize_cost_center_usage(
    dynamodb_client: Any,
    name: str,
    *,
    usage_table_name: str = DEFAULT_COST_CENTER_USAGE_TABLE,
    now: str | None = None,
) -> CostCenterUsage:
    """Create the current-month zero snapshot without replacing allocator data."""
    timestamp = now or utc_now_iso()
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
    processed_hour = parsed.replace(minute=0, second=0, microsecond=0)
    usage = CostCenterUsage(
        name=validate_cost_center_name(name),
        month=processed_hour.strftime("%Y-%m"),
        monthly_spend_usd=Decimal("0"),
        latest_processed_hour=processed_hour.isoformat().replace("+00:00", "Z"),
        updated_at=timestamp,
    )
    existing = get_cost_center_usage(
        dynamodb_client,
        usage.name,
        month=usage.month,
        usage_table_name=usage_table_name,
        allow_missing=True,
    )
    if existing is not None:
        return existing
    try:
        dynamodb_client.put_item(
            TableName=usage_table_name,
            Item=_usage_to_item(usage),
            ConditionExpression="attribute_not_exists(cost_center)",
        )
    except Exception as exc:
        if exc.__class__.__name__ != "ConditionalCheckFailedException" and (
            "ConditionalCheckFailed" not in str(exc)
        ):
            raise
        raced = get_cost_center_usage(
            dynamodb_client,
            usage.name,
            month=usage.month,
            usage_table_name=usage_table_name,
            allow_missing=True,
        )
        if raced is None:
            raise
        return raced
    return usage


def authorize_cost_center(
    item: CostCenter,
    *,
    user: str,
    groups: Iterable[str] = (),
) -> None:
    if item.name == RESERVED_IDLE_COST_CENTER:
        raise CostCenterError("'idle' cannot be used for Slurm submissions.")
    if item.status != "active":
        raise CostCenterError(f"Cost center '{item.name}' is not active.")
    current_user = str(user or "").strip()
    current_groups = {str(group).strip() for group in groups if str(group).strip()}
    if current_user in item.allowed_users or "*" in item.allowed_users:
        return
    if current_groups.intersection(item.allowed_groups):
        return
    raise CostCenterError(f"User '{current_user}' is not authorized for cost center '{item.name}'.")


def _ensure_registry_table(dynamodb_client: Any, table_name: str) -> None:
    _ensure_table(
        dynamodb_client,
        table_name=table_name,
        key_schema=[{"AttributeName": "cost_center", "KeyType": "HASH"}],
        attribute_definitions=[{"AttributeName": "cost_center", "AttributeType": "S"}],
    )


def _ensure_usage_table(dynamodb_client: Any, table_name: str) -> None:
    _ensure_table(
        dynamodb_client,
        table_name=table_name,
        key_schema=[
            {"AttributeName": "cost_center", "KeyType": "HASH"},
            {"AttributeName": "month", "KeyType": "RANGE"},
        ],
        attribute_definitions=[
            {"AttributeName": "cost_center", "AttributeType": "S"},
            {"AttributeName": "month", "AttributeType": "S"},
        ],
    )


def _ensure_table(
    dynamodb_client: Any,
    *,
    table_name: str,
    key_schema: list[dict[str, str]],
    attribute_definitions: list[dict[str, str]],
) -> None:
    try:
        dynamodb_client.describe_table(TableName=table_name)
        return
    except Exception as exc:
        if not _is_not_found(exc):
            raise
    dynamodb_client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=key_schema,
        AttributeDefinitions=attribute_definitions,
    )
    try:
        waiter = dynamodb_client.get_waiter("table_exists")
    except Exception:
        waiter = None
    if waiter is not None:
        waiter.wait(TableName=table_name)


def _is_not_found(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = str((response.get("Error") or {}).get("Code") or "")
        if code in {"ResourceNotFoundException", "TableNotFoundException"}:
            return True
    text = str(exc).lower()
    return "resource not found" in text or "notfound" in text or "not found" in text


def _validate_decimal(value: str | Decimal, *, field: str) -> Decimal:
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CostCenterError(f"{field} must be a number.") from exc
    if decimal < 0:
        raise CostCenterError(f"{field} must be >= 0.")
    return decimal


def _normalize_list(values: Sequence[str], *, field: str) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        if any(ch.isspace() for ch in value):
            raise CostCenterError(f"{field} entries must not contain whitespace.")
        if value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return tuple(normalized)


def _put_cost_center(
    dynamodb_client: Any,
    table_name: str,
    item: CostCenter,
    *,
    condition: str,
) -> None:
    try:
        dynamodb_client.put_item(
            TableName=table_name,
            Item=_cost_center_to_item(item),
            ConditionExpression=condition,
        )
    except Exception as exc:
        if exc.__class__.__name__ == "ConditionalCheckFailedException" or "ConditionalCheckFailed" in str(exc):
            raise CostCenterError(f"Cost center '{item.name}' already exists or is missing.") from exc
        raise


def _cost_center_to_item(item: CostCenter) -> dict[str, Any]:
    raw = {
        "cost_center": {"S": item.name},
        "status": {"S": item.status},
        "monthly_cap_usd": {"N": str(item.monthly_cap_usd)},
        "notes": {"S": item.notes},
        "created_at": {"S": item.created_at},
        "created_by_arn": {"S": item.created_by_arn},
        "updated_at": {"S": item.updated_at},
        "updated_by_arn": {"S": item.updated_by_arn},
    }
    if item.allowed_users:
        raw["allowed_users"] = {"SS": list(item.allowed_users)}
    if item.allowed_groups:
        raw["allowed_groups"] = {"SS": list(item.allowed_groups)}
    if item.owner_emails:
        raw["owner_emails"] = {"SS": list(item.owner_emails)}
    if item.disabled_at:
        raw["disabled_at"] = {"S": item.disabled_at}
    if item.disabled_reason:
        raw["disabled_reason"] = {"S": item.disabled_reason}
    return raw


def _cost_center_from_item(raw: dict[str, Any]) -> CostCenter:
    status = _s(raw, "status")
    if status not in VALID_STATUSES:
        raise CostCenterError(f"Cost center has unknown status '{status}'.")
    return CostCenter(
        name=_s(raw, "cost_center"),
        status=status,
        monthly_cap_usd=Decimal(_n(raw, "monthly_cap_usd", "0")),
        allowed_users=_ss(raw, "allowed_users"),
        allowed_groups=_ss(raw, "allowed_groups"),
        owner_emails=_ss(raw, "owner_emails"),
        notes=_s(raw, "notes", ""),
        created_at=_s(raw, "created_at", ""),
        created_by_arn=_s(raw, "created_by_arn", ""),
        updated_at=_s(raw, "updated_at", ""),
        updated_by_arn=_s(raw, "updated_by_arn", ""),
        disabled_at=_s(raw, "disabled_at", ""),
        disabled_reason=_s(raw, "disabled_reason", ""),
    )


def _usage_to_item(usage: CostCenterUsage) -> dict[str, Any]:
    return {
        "cost_center": {"S": usage.name},
        "month": {"S": usage.month},
        "monthly_spend_usd": {"N": str(usage.monthly_spend_usd)},
        "latest_processed_hour": {"S": usage.latest_processed_hour},
        "updated_at": {"S": usage.updated_at},
    }


def _usage_from_item(raw: dict[str, Any]) -> CostCenterUsage:
    return CostCenterUsage(
        name=_s(raw, "cost_center"),
        month=validate_month(_s(raw, "month")),
        monthly_spend_usd=Decimal(_n(raw, "monthly_spend_usd", "0")),
        latest_processed_hour=_s(raw, "latest_processed_hour"),
        updated_at=_s(raw, "updated_at", ""),
    )


def _s(raw: dict[str, Any], key: str, default: str | None = None) -> str:
    value = raw.get(key)
    if value is None:
        if default is not None:
            return default
        raise CostCenterError(f"DynamoDB item is missing required string field '{key}'.")
    return str(value.get("S", default or ""))


def _n(raw: dict[str, Any], key: str, default: str | None = None) -> str:
    value = raw.get(key)
    if value is None:
        if default is not None:
            return default
        raise CostCenterError(f"DynamoDB item is missing required number field '{key}'.")
    return str(value.get("N", default or "0"))


def _ss(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key) or {}
    values = value.get("SS") or []
    return tuple(sorted(str(item) for item in values if str(item)))
