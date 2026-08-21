from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import ClassVar

import pytest

from daylily_ec.aws.cost_centers import (
    CostCenterError,
    CostCenterUsage,
    authorize_cost_center,
    cost_center_is_expired,
    create_cost_center,
    disable_cost_center,
    edit_cost_center,
    ensure_active_cost_center,
    ensure_cost_center_registry,
    get_cost_center,
    get_cost_center_usage,
    initialize_cost_center_usage,
    list_cost_centers,
    put_cost_center_usage,
    validate_active_until,
    validate_cost_center_name,
    validate_latest_processed_hour,
    validate_max_usage_age_hours,
)


class NotFound(Exception):
    response: ClassVar[dict[str, object]] = {"Error": {"Code": "ResourceNotFoundException"}}


class ConditionalCheckFailedException(Exception):
    pass


class FakeWaiter:
    def wait(self, **_kwargs):
        return None


class FakeDynamo:
    def __init__(self):
        self.tables: set[str] = set()
        self.items: dict[str, dict[tuple[str, ...], dict]] = {}
        self.created: list[str] = []
        self.get_calls: list[dict[str, object]] = []

    def describe_table(self, TableName):
        if TableName not in self.tables:
            raise NotFound(TableName)
        key_schema = [{"AttributeName": "cost_center", "KeyType": "HASH"}]
        if "usage" in TableName:
            key_schema.append({"AttributeName": "month", "KeyType": "RANGE"})
        return {
            "Table": {
                "TableName": TableName,
                "TableStatus": "ACTIVE",
                "KeySchema": key_schema,
            }
        }

    def create_table(self, TableName, **_kwargs):
        self.tables.add(TableName)
        self.items.setdefault(TableName, {})
        self.created.append(TableName)

    def get_waiter(self, _name):
        return FakeWaiter()

    def put_item(self, TableName, Item, ConditionExpression=None):
        key = self._key(Item)
        exists = key in self.items.setdefault(TableName, {})
        if ConditionExpression == "attribute_not_exists(cost_center)" and exists:
            raise ConditionalCheckFailedException()
        if ConditionExpression == "attribute_exists(cost_center)" and not exists:
            raise ConditionalCheckFailedException()
        self.items[TableName][key] = deepcopy(Item)

    def get_item(self, TableName, Key, **_kwargs):
        self.get_calls.append({"TableName": TableName, **_kwargs})
        key = self._key(Key)
        item = self.items.setdefault(TableName, {}).get(key)
        return {"Item": deepcopy(item)} if item else {}

    def scan(self, TableName, **_kwargs):
        return {"Items": list(deepcopy(self.items.setdefault(TableName, {})).values())}

    @staticmethod
    def _key(item):
        if "month" in item:
            return (item["cost_center"]["S"], item["month"]["S"])
        return (item["cost_center"]["S"],)


def test_ensure_registry_creates_tables_and_idle():
    dynamo = FakeDynamo()

    result = ensure_cost_center_registry(
        dynamo,
        table_name="cc",
        usage_table_name="usage",
        actor_arn="arn",
        now="2026-07-05T00:00:00Z",
    )

    assert result == {"registry_table": "cc", "usage_table": "usage", "idle": "system"}
    assert dynamo.created == ["cc", "usage"]
    idle = get_cost_center(dynamo, "idle", table_name="cc", allow_idle=True)
    assert idle.status == "system"


def test_create_edit_disable_cost_center():
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")

    created = create_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="200",
        allowed_users=["ubuntu"],
        table_name="cc",
        now="2026-07-05T00:37:42Z",
        active_until="2026-12-31T23:59:59Z",
    )
    assert created.status == "active"
    assert created.allowed_users == ("ubuntu",)
    assert created.active_until == "2026-12-31T23:59:59Z"
    assert created.to_dict()["active_until"] == "2026-12-31T23:59:59Z"
    assert (
        get_cost_center(dynamo, "project-a", table_name="cc").active_until == "2026-12-31T23:59:59Z"
    )
    assert (
        get_cost_center_usage(
            dynamo,
            "project-a",
            month="2026-07",
            usage_table_name="usage",
            allow_missing=True,
        )
        is None
    )
    allocator_usage = put_cost_center_usage(
        dynamo,
        CostCenterUsage(
            name="project-a",
            month="2026-07",
            monthly_spend_usd="12.50",
            latest_processed_hour="2026-07-05T01:00:00Z",
            updated_at="2026-07-05T01:01:00Z",
        ),
        usage_table_name="usage",
    )
    assert (
        initialize_cost_center_usage(
            dynamo,
            "project-a",
            usage_table_name="usage",
            now="2026-07-05T02:00:00Z",
        )
        == allocator_usage
    )

    edited = edit_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="300",
        allowed_groups=["research"],
        allowed_users=[],
        table_name="cc",
        now="2026-07-05T01:00:00Z",
    )
    assert str(edited.monthly_cap_usd) == "300"
    assert edited.allowed_groups == ("research",)

    overridden = edit_cost_center(
        dynamo,
        "project-a",
        max_usage_age_hours=2160,
        table_name="cc",
        now="2026-07-05T01:30:00Z",
    )
    assert overridden.max_usage_age_hours == 2160
    assert get_cost_center(dynamo, "project-a", table_name="cc").max_usage_age_hours == 2160

    cleared = edit_cost_center(
        dynamo,
        "project-a",
        clear_active_until=True,
        table_name="cc",
        now="2026-07-05T01:45:00Z",
    )
    assert cleared.active_until == ""

    disabled = disable_cost_center(
        dynamo,
        "project-a",
        reason="closed",
        table_name="cc",
        now="2026-07-05T02:00:00Z",
    )
    assert disabled.status == "disabled"
    assert disabled.disabled_reason == "closed"
    assert disabled.max_usage_age_hours == 2160
    assert disabled.active_until == ""


def test_cost_center_usage_age_override_is_bounded_to_90_days():
    assert validate_max_usage_age_hours("2160") == 2160
    assert validate_max_usage_age_hours(None) is None
    with pytest.raises(CostCenterError, match="positive integer"):
        validate_max_usage_age_hours("24.5")
    with pytest.raises(CostCenterError, match="must not exceed"):
        validate_max_usage_age_hours("2161")


def test_active_until_is_exact_utc_and_authorization_enforces_exclusive_boundary():
    assert validate_active_until(None) == ""
    assert validate_active_until("2026-08-31T12:30:45Z") == "2026-08-31T12:30:45Z"
    for invalid in (
        "2026-08-31T12:30Z",
        "2026-08-31T12:30:45+00:00",
        "2026-02-30T12:30:45Z",
        " 2026-08-31T12:30:45Z",
    ):
        with pytest.raises(CostCenterError, match="active_until"):
            validate_active_until(invalid)

    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")
    item = create_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="200",
        allowed_users=["ubuntu"],
        active_until="2026-08-31T12:30:45Z",
        table_name="cc",
    )
    before = datetime(2026, 8, 31, 12, 30, 44, tzinfo=timezone.utc)
    boundary = datetime(2026, 8, 31, 12, 30, 45, tzinfo=timezone.utc)
    assert cost_center_is_expired(item, now=before) is False
    authorize_cost_center(item, user="ubuntu", now=before)
    assert cost_center_is_expired(item, now=boundary) is True
    with pytest.raises(CostCenterError, match="expired at active_until"):
        authorize_cost_center(item, user="ubuntu", now=boundary)


def test_ensure_active_cost_center_creates_once_and_rejects_contract_drift():
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")

    created, was_created = ensure_active_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="200",
        allowed_users=["ubuntu"],
        owner_emails=["owner@example.org"],
        table_name="cc",
        usage_table_name="usage",
        now="2026-07-05T00:37:42Z",
    )
    assert was_created is True
    assert created.name == "project-a"
    assert dynamo.items["usage"] == {}

    verified, was_created = ensure_active_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="200",
        allowed_users=["ubuntu"],
        owner_emails=["owner@example.org"],
        table_name="cc",
        usage_table_name="usage",
        now="2026-07-05T01:37:42Z",
    )
    assert was_created is False
    assert verified == created
    assert dynamo.get_calls
    assert all(call.get("ConsistentRead") is True for call in dynamo.get_calls)

    with pytest.raises(CostCenterError, match="does not match the explicit DYEC create inputs"):
        ensure_active_cost_center(
            dynamo,
            "project-a",
            monthly_cap_usd="300",
            allowed_users=["ubuntu"],
            owner_emails=["owner@example.org"],
            table_name="cc",
            usage_table_name="usage",
        )


def test_ensure_active_cost_center_accepts_only_an_exact_concurrent_create() -> None:
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")
    create_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="200",
        allowed_users=["ubuntu"],
        owner_emails=["owner@example.org"],
        table_name="cc",
        now="2026-07-05T00:37:42Z",
    )
    concurrent_item = dynamo.items["cc"].pop(("project-a",))
    original_put_item = dynamo.put_item

    def race_put_item(*, TableName, Item, ConditionExpression=None):
        if ConditionExpression == "attribute_not_exists(cost_center)":
            dynamo.items[TableName][("project-a",)] = deepcopy(concurrent_item)
            raise ConditionalCheckFailedException()
        return original_put_item(
            TableName=TableName,
            Item=Item,
            ConditionExpression=ConditionExpression,
        )

    dynamo.put_item = race_put_item  # type: ignore[method-assign]
    item, created = ensure_active_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="200",
        allowed_users=["ubuntu"],
        owner_emails=["owner@example.org"],
        table_name="cc",
        usage_table_name="usage",
        now="2026-07-05T00:37:42Z",
    )

    assert created is False
    assert item.status == "active"
    assert dynamo.get_calls[-1]["ConsistentRead"] is True


def test_ensure_active_cost_center_never_reactivates_disabled_row() -> None:
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")
    create_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="200",
        allowed_users=["ubuntu"],
        owner_emails=["owner@example.org"],
        table_name="cc",
    )
    disable_cost_center(
        dynamo,
        "project-a",
        reason="closed",
        table_name="cc",
    )

    with pytest.raises(CostCenterError, match="status='disabled'"):
        ensure_active_cost_center(
            dynamo,
            "project-a",
            monthly_cap_usd="200",
            allowed_users=["ubuntu"],
            owner_emails=["owner@example.org"],
            table_name="cc",
            usage_table_name="usage",
        )

    assert get_cost_center(dynamo, "project-a", table_name="cc").status == "disabled"


def test_ensure_active_cost_center_requires_existing_tables() -> None:
    dynamo = FakeDynamo()

    with pytest.raises(CostCenterError, match="bootstrap is not implicit"):
        ensure_active_cost_center(
            dynamo,
            "project-a",
            monthly_cap_usd="200",
            allowed_users=["ubuntu"],
            owner_emails=["owner@example.org"],
            table_name="cc",
            usage_table_name="usage",
        )

    assert dynamo.created == []


def test_ensure_active_cost_center_requires_one_canonical_owner_and_cap() -> None:
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")

    with pytest.raises(CostCenterError, match="Exactly one canonical owner email"):
        ensure_active_cost_center(
            dynamo,
            "project-a",
            monthly_cap_usd="200",
            allowed_users=["ubuntu"],
            owner_emails=["a@example.org", "b@example.org"],
            table_name="cc",
            usage_table_name="usage",
        )

    item, created = ensure_active_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="200.000",
        allowed_users=["ubuntu"],
        owner_emails=["owner@example.org"],
        table_name="cc",
        usage_table_name="usage",
    )
    assert created is True
    assert str(item.monthly_cap_usd) == "200"


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity"])
def test_ensure_active_cost_center_rejects_nonfinite_cap(amount: str) -> None:
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")

    with pytest.raises(CostCenterError, match="finite number"):
        ensure_active_cost_center(
            dynamo,
            "project-a",
            monthly_cap_usd=amount,
            allowed_users=["ubuntu"],
            owner_emails=["owner@example.org"],
            table_name="cc",
            usage_table_name="usage",
        )


def test_active_cost_center_rejects_zero_monthly_cap():
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")

    with pytest.raises(CostCenterError, match="greater than zero"):
        create_cost_center(
            dynamo,
            "project-a",
            monthly_cap_usd="0",
            allowed_users=["ubuntu"],
            table_name="cc",
        )


def test_create_publishes_registry_without_synthesizing_usage():
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")

    create_cost_center(
        dynamo,
        "project-a",
        monthly_cap_usd="200",
        allowed_users=["ubuntu"],
        table_name="cc",
        now="2026-07-05T00:37:42Z",
    )

    assert get_cost_center(dynamo, "project-a", table_name="cc") is not None
    assert dynamo.items["usage"] == {}


def test_idle_is_reserved_for_users():
    with pytest.raises(CostCenterError, match="reserved"):
        validate_cost_center_name("idle")


def test_list_and_usage():
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo, table_name="cc", usage_table_name="usage")
    create_cost_center(
        dynamo,
        "b-project",
        monthly_cap_usd="10",
        allowed_users=["ubuntu"],
        table_name="cc",
    )
    create_cost_center(
        dynamo,
        "a-project",
        monthly_cap_usd="10",
        allowed_users=["ubuntu"],
        table_name="cc",
    )

    assert [item.name for item in list_cost_centers(dynamo, table_name="cc", status="active")] == [
        "a-project",
        "b-project",
    ]

    written = put_cost_center_usage(
        dynamo,
        CostCenterUsage(
            name="a-project",
            month="2026-07",
            monthly_spend_usd="5",
            latest_processed_hour="2026-07-05T00:00:00Z",
            updated_at="2026-07-05T01:00:00Z",
        ),
        usage_table_name="usage",
    )
    assert written.latest_processed_hour == "2026-07-05T00:00:00Z"
    usage = get_cost_center_usage(dynamo, "a-project", month="2026-07", usage_table_name="usage")
    assert str(usage.monthly_spend_usd) == "5"

    assert validate_latest_processed_hour("2026-07-05T01:00:00+00:00") == ("2026-07-05T01:00:00Z")
    with pytest.raises(CostCenterError, match="rounded to the UTC hour"):
        validate_latest_processed_hour("2026-07-05T01:30:00Z")
    with pytest.raises(CostCenterError, match="monthly_spend_usd"):
        put_cost_center_usage(
            dynamo,
            CostCenterUsage(
                name="a-project",
                month="2026-07",
                monthly_spend_usd="-1",
                latest_processed_hour="2026-07-05T00:00:00Z",
                updated_at="2026-07-05T01:00:00Z",
            ),
            usage_table_name="usage",
        )
