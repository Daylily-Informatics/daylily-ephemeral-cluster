from __future__ import annotations

from copy import deepcopy

import pytest

from daylily_ec.aws.cost_centers import (
    CostCenterError,
    create_cost_center,
    disable_cost_center,
    edit_cost_center,
    ensure_cost_center_registry,
    get_cost_center,
    get_cost_center_usage,
    list_cost_centers,
    put_cost_center_usage,
    validate_cost_center_name,
    validate_latest_processed_hour,
    CostCenterUsage,
)


class NotFound(Exception):
    response = {"Error": {"Code": "ResourceNotFoundException"}}


class ConditionalCheckFailed(Exception):
    pass


class FakeWaiter:
    def wait(self, **_kwargs):
        return None


class FakeDynamo:
    def __init__(self):
        self.tables: set[str] = set()
        self.items: dict[str, dict[tuple[str, ...], dict]] = {}
        self.created: list[str] = []

    def describe_table(self, TableName):
        if TableName not in self.tables:
            raise NotFound(TableName)
        return {"Table": {"TableName": TableName}}

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
            raise ConditionalCheckFailed()
        if ConditionExpression == "attribute_exists(cost_center)" and not exists:
            raise ConditionalCheckFailed()
        self.items[TableName][key] = deepcopy(Item)

    def get_item(self, TableName, Key, **_kwargs):
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
        now="2026-07-05T00:00:00Z",
    )
    assert created.status == "active"
    assert created.allowed_users == ("ubuntu",)

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

    disabled = disable_cost_center(
        dynamo,
        "project-a",
        reason="closed",
        table_name="cc",
        now="2026-07-05T02:00:00Z",
    )
    assert disabled.status == "disabled"
    assert disabled.disabled_reason == "closed"


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

    assert validate_latest_processed_hour("2026-07-05T01:00:00+00:00") == (
        "2026-07-05T01:00:00Z"
    )
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
