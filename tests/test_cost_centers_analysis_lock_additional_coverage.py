from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import daylily_ec.analysis_lock as locks
import daylily_ec.aws.cost_centers as costs


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "fsx" / "analysis_results" / "owner" / "analysis"
    root.mkdir(parents=True)
    return root


def _agent(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv("DAYOA_AGENT_ID", name)
    monkeypatch.setenv("DAYOA_AGENT_KIND", "test")


def _cost_center(**overrides: object) -> costs.CostCenter:
    values = {
        "name": "project",
        "status": "active",
        "monthly_cap_usd": Decimal("10"),
        "allowed_users": ("alice",),
        "allowed_groups": ("research",),
        "owner_emails": ("owner@example.com",),
        "notes": "note",
        "created_at": "created",
        "created_by_arn": "creator",
        "updated_at": "updated",
        "updated_by_arn": "updater",
        "disabled_at": "",
        "disabled_reason": "",
    }
    values.update(overrides)
    return costs.CostCenter(**values)


class _Dynamo:
    def __init__(self) -> None:
        self.items: dict[str, dict[tuple[str, ...], dict]] = {}
        self.pages: list[dict] = []
        self.created: list[str] = []
        self.waited: list[str] = []

    @staticmethod
    def _key(item: dict) -> tuple[str, ...]:
        values = [item["cost_center"]["S"]]
        if "month" in item:
            values.append(item["month"]["S"])
        return tuple(values)

    def get_item(self, TableName, Key, **kwargs):
        item = self.items.setdefault(TableName, {}).get(self._key(Key))
        return {"Item": deepcopy(item)} if item else {}

    def put_item(self, TableName, Item, **kwargs):
        self.items.setdefault(TableName, {})[self._key(Item)] = deepcopy(Item)

    def scan(self, **kwargs):
        if self.pages:
            return self.pages.pop(0)
        return {"Items": list(self.items.setdefault(kwargs["TableName"], {}).values())}

    def describe_table(self, **kwargs):
        raise RuntimeError("Resource not found")

    def create_table(self, **kwargs):
        self.created.append(kwargs["TableName"])

    def get_waiter(self, name):
        return SimpleNamespace(wait=lambda **kwargs: self.waited.append(kwargs["TableName"]))


def test_cost_center_serialization_and_validation_edges() -> None:
    assert _cost_center().to_dict()["monthly_cap_usd"] == "10"
    usage = costs.CostCenterUsage("project", "2026-07", Decimal("1.2"), "hour", "now")
    assert usage.to_dict()["monthly_spend_usd"] == "1.2"
    assert costs.validate_cost_center_name(" idle ", allow_idle=True) == "idle"
    for value, pattern in [
        ("", "non-empty"),
        ("has space", "whitespace"),
        ("bad|pipe", "whitespace"),
        ("-bad", "must start"),
    ]:
        with pytest.raises(costs.CostCenterError, match=pattern):
            costs.validate_cost_center_name(value)
    with pytest.raises(costs.CostCenterError, match="YYYY-MM"):
        costs.validate_month("July")
    assert costs.validate_month("2026-07") == "2026-07"
    for value, pattern in [
        ("", "non-empty"),
        ("bad", "ISO-8601"),
        ("2026-07-01T01:00:00", "timezone"),
        ("2026-07-01T01:02:00Z", "rounded"),
    ]:
        with pytest.raises(costs.CostCenterError, match=pattern):
            costs.validate_latest_processed_hour(value)
    assert costs.validate_latest_processed_hour("2026-07-01T03:00:00+02:00") == (
        "2026-07-01T01:00:00Z"
    )


def test_registry_and_mutation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    dynamo = _Dynamo()
    monkeypatch.setattr(
        costs, "get_cost_center", lambda *args, **kwargs: _cost_center(status="active")
    )
    monkeypatch.setattr(costs, "_ensure_registry_table", lambda *args: None)
    monkeypatch.setattr(costs, "_ensure_usage_table", lambda *args: None)
    with pytest.raises(costs.CostCenterError, match="not system-owned"):
        costs.ensure_cost_center_registry(dynamo)

    with pytest.raises(costs.CostCenterError, match="At least one"):
        costs.create_cost_center(dynamo, "project", monthly_cap_usd="10")
    with pytest.raises(costs.CostCenterError, match="No edit fields"):
        costs.edit_cost_center(dynamo, "project")
    with pytest.raises(costs.CostCenterError, match="active or disabled"):
        costs.edit_cost_center(dynamo, "project", status="system")
    with pytest.raises(costs.CostCenterError, match="At least one"):
        costs.edit_cost_center(dynamo, "project", allowed_users=[], allowed_groups=[])
    with pytest.raises(costs.CostCenterError, match="disable reason"):
        costs.disable_cost_center(dynamo, "project", reason="")


def test_cost_center_reads_lists_and_usage_pagination() -> None:
    dynamo = _Dynamo()
    assert costs.get_cost_center(dynamo, "missing", allow_missing=True) is None
    with pytest.raises(costs.CostCenterError, match="does not exist"):
        costs.get_cost_center(dynamo, "missing")
    with pytest.raises(costs.CostCenterError, match="status must"):
        costs.list_cost_centers(dynamo, status="bad")

    raw_a = costs._cost_center_to_item(_cost_center(name="a"))
    raw_b = costs._cost_center_to_item(_cost_center(name="b", status="disabled"))
    dynamo.pages = [
        {"Items": [raw_b], "LastEvaluatedKey": {"cost_center": {"S": "b"}}},
        {"Items": [raw_a]},
    ]
    assert [item.name for item in costs.list_cost_centers(dynamo)] == ["a", "b"]
    dynamo.pages = [{"Items": [raw_b, raw_a]}]
    assert [item.name for item in costs.list_cost_centers(dynamo, status="active")] == ["a"]

    assert (
        costs.get_cost_center_usage(dynamo, "missing", month="2026-07", allow_missing=True) is None
    )
    with pytest.raises(costs.CostCenterError, match="No usage snapshot"):
        costs.get_cost_center_usage(dynamo, "missing", month="2026-07")
    usage_july = costs._usage_to_item(costs.CostCenterUsage("b", "2026-07", Decimal("2"), "h", "u"))
    usage_june = costs._usage_to_item(costs.CostCenterUsage("a", "2026-06", Decimal("1"), "h", "u"))
    dynamo.pages = [
        {"Items": [usage_june], "LastEvaluatedKey": {"cost_center": {"S": "a"}}},
        {"Items": [usage_july]},
    ]
    assert [item.name for item in costs.list_cost_center_usage(dynamo, month="2026-07")] == ["b"]


def test_initialize_usage_race_and_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    dynamo = _Dynamo()
    existing = costs.CostCenterUsage("project", "2026-07", Decimal("5"), "h", "u")
    reads = iter([None, existing])
    monkeypatch.setattr(costs, "get_cost_center_usage", lambda *args, **kwargs: next(reads))

    class ConditionalCheckFailedException(Exception):
        pass

    dynamo.put_item = lambda **kwargs: (_ for _ in ()).throw(ConditionalCheckFailedException())
    assert (
        costs.initialize_cost_center_usage(dynamo, "project", now="2026-07-05T02:15:00Z")
        is existing
    )

    for item, kwargs, pattern in [
        (_cost_center(name="idle"), {"user": "alice"}, "cannot be used"),
        (_cost_center(status="disabled"), {"user": "alice"}, "not active"),
        (_cost_center(), {"user": "nobody"}, "not authorized"),
    ]:
        with pytest.raises(costs.CostCenterError, match=pattern):
            costs.authorize_cost_center(item, **kwargs)
    costs.authorize_cost_center(_cost_center(allowed_users=("*",)), user="anyone")
    costs.authorize_cost_center(_cost_center(), user="nobody", groups=["research"])


def test_cost_center_storage_helper_edges() -> None:
    dynamo = _Dynamo()
    costs._ensure_table(
        dynamo,
        table_name="table",
        key_schema=[{"AttributeName": "cost_center", "KeyType": "HASH"}],
        attribute_definitions=[{"AttributeName": "cost_center", "AttributeType": "S"}],
    )
    assert dynamo.created == ["table"] and dynamo.waited == ["table"]

    class Coded(Exception):
        response = {"Error": {"Code": "TableNotFoundException"}}

    assert costs._is_not_found(Coded())
    assert not costs._is_not_found(RuntimeError("access denied"))
    for value, pattern in [("bad", "must be a number"), ("-1", ">= 0")]:
        with pytest.raises(costs.CostCenterError, match=pattern):
            costs._validate_decimal(value, field="amount")
    assert costs._normalize_list([" a ", "a", "", "b"], field="users") == ("a", "b")
    with pytest.raises(costs.CostCenterError, match="whitespace"):
        costs._normalize_list(["bad user"], field="users")

    full = _cost_center(disabled_at="then", disabled_reason="done")
    raw = costs._cost_center_to_item(full)
    assert costs._cost_center_from_item(raw) == full
    with pytest.raises(costs.CostCenterError, match="unknown status"):
        costs._cost_center_from_item({**raw, "status": {"S": "mystery"}})
    with pytest.raises(costs.CostCenterError, match="missing required string"):
        costs._s({}, "required")
    with pytest.raises(costs.CostCenterError, match="missing required number"):
        costs._n({}, "required")
    assert costs._ss({"values": {"SS": ["b", "", "a"]}}, "values") == ("a", "b")


def test_analysis_path_metadata_and_json_errors(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(locks.AnalysisLockError, match="does not exist"):
        locks.normalize_analysis_root(missing)
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(locks.AnalysisLockError, match="under an analysis_results"):
        locks.normalize_analysis_root(outside)
    shallow = tmp_path / "analysis_results" / "owner"
    shallow.mkdir(parents=True)
    with pytest.raises(locks.AnalysisLockError, match="analysis_id"):
        locks.normalize_analysis_root(shallow)
    assert locks._safe_segment(" .. ") == "agent"
    assert locks._json_default(Path("x")) == "x"

    root = _root(tmp_path)
    owner = locks.owner_metadata_path(root)
    owner.parent.mkdir()
    owner.write_text("invalid", encoding="utf-8")
    with pytest.raises(locks.AnalysisLockError, match="Invalid owner metadata"):
        locks.ensure_owner_metadata(root)
    owner.unlink()
    lock_owner = locks.lock_owner_path(root)
    lock_owner.parent.mkdir()
    lock_owner.write_text("invalid", encoding="utf-8")
    with pytest.raises(locks.AnalysisLockError, match="Invalid active lock"):
        locks.read_active_lock(root)


def test_analysis_lock_error_and_reentrant_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    _agent(monkeypatch, "agent-a")
    with pytest.raises(locks.AnalysisLockError, match="Unsupported visit"):
        locks.write_visit(root, mode="invalid", intent="test")
    with pytest.raises(locks.AnalysisLockError, match="only for protected"):
        locks.acquire_lock(root, operation="read", intent="test")
    locks.acquire_lock(root, operation="write", intent="test")
    again = locks.acquire_lock(root, operation="write", intent="test")
    assert again["already_owned"] is True

    _agent(monkeypatch, "agent-b")
    with pytest.raises(locks.AnalysisLockError, match="another agent"):
        locks.heartbeat_lock(root)
    with pytest.raises(locks.AnalysisLockError, match="another agent"):
        locks.release_lock(root)
    _agent(monkeypatch, "agent-a")
    locks.release_lock(root)
    with pytest.raises(locks.AnalysisLockError, match="No active"):
        locks.heartbeat_lock(root)
    with pytest.raises(locks.AnalysisLockError, match="No active"):
        locks.release_lock(root)
    with pytest.raises(locks.AnalysisLockError, match="No active"):
        locks.takeover_token(root, operation="write")
    with pytest.raises(locks.AnalysisLockError, match="must be protected"):
        locks.takeover_token(root, operation="read")
    with pytest.raises(locks.AnalysisLockError, match="No active"):
        locks.takeover_request(root, operation="write", reason="test")


def test_analysis_takeover_guard_and_guarded_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    _agent(monkeypatch, "owner")
    locks.acquire_lock(root, operation="write", intent="work")
    token = locks.takeover_token(root, operation="kill")
    _agent(monkeypatch, "new")
    common = dict(
        analysis_root=root,
        operation="kill",
        confirm_token=token,
        approved_by="approver",
        reason="stale",
        intent="takeover",
    )
    with pytest.raises(locks.AnalysisLockError, match="reason is required"):
        locks.takeover_lock(**{**common, "reason": ""})
    with pytest.raises(locks.AnalysisLockError, match="does not match"):
        locks.takeover_lock(**{**common, "confirm_token": "bad"})
    with pytest.raises(locks.AnalysisLockError, match="Unsupported guarded"):
        locks.assert_operation_allowed(root, operation="invalid", intent="test")
    locks.takeover_lock(**common)

    monkeypatch.setattr(
        locks.subprocess, "run", lambda command, check: SimpleNamespace(returncode=7)
    )
    assert locks.guarded_run(root, operation="kill", intent="test", command=["false"]) == 7


def test_analysis_s3_visit_and_module_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(locks.AnalysisLockError, match="must be s3"):
        locks.write_s3_visit("https://bucket/key", {})
    writes: list[dict] = []
    fake_boto3 = SimpleNamespace(
        client=lambda service: SimpleNamespace(put_object=lambda **kwargs: writes.append(kwargs))
    )
    monkeypatch.setitem(__import__("sys").modules, "boto3", fake_boto3)
    uri = locks.write_s3_visit("s3://bucket/prefix", {"agent_id": "a/b"})
    assert uri.startswith("s3://bucket/prefix/_dayoa_agent_visits/")
    assert writes[0]["ContentType"] == "application/json"

    root = _root(tmp_path)
    assert locks.main([]) == 2
    assert locks.main(["status", str(root)]) == 0
    assert locks.main(["unknown", str(root)]) == 1
