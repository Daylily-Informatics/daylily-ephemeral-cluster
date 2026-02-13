"""Tests for drift detection module (CP-016)."""

from __future__ import annotations

from unittest.mock import MagicMock

from daylily_ec.state.drift import (
    DriftCheck,
    DriftReport,
    DriftStatus,
    check_budget_drift,
    check_cfn_drift,
    check_heartbeat_drift,
    run_drift_check,
)
from daylily_ec.state.models import StateRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state(**kw) -> StateRecord:
    return StateRecord(run_id="20260201120000", **kw)


# ---------------------------------------------------------------------------
# DriftCheck / DriftReport dataclass basics
# ---------------------------------------------------------------------------


class TestDriftDataclasses:
    def test_drift_check_defaults(self):
        dc = DriftCheck(id="test", status=DriftStatus.OK)
        assert dc.expected == ""
        assert dc.actual == ""
        assert dc.error == ""
        assert dc.details == {}

    def test_drift_report_no_drift(self):
        r = DriftReport(cluster_name="c", checks=[
            DriftCheck(id="a", status=DriftStatus.OK),
        ])
        assert not r.has_drift
        assert not r.has_errors

    def test_drift_report_has_drift(self):
        r = DriftReport(cluster_name="c", checks=[
            DriftCheck(id="a", status=DriftStatus.DRIFTED),
        ])
        assert r.has_drift

    def test_drift_report_has_errors(self):
        r = DriftReport(cluster_name="c", checks=[
            DriftCheck(id="a", status=DriftStatus.ERROR),
        ])
        assert r.has_errors

    def test_to_dict(self):
        r = DriftReport(cluster_name="c", checks=[
            DriftCheck(id="x", status=DriftStatus.OK, expected="e", actual="a"),
        ])
        d = r.to_dict()
        assert d["cluster_name"] == "c"
        assert d["has_drift"] is False
        assert len(d["checks"]) == 1
        assert d["checks"][0]["id"] == "x"
        assert d["checks"][0]["status"] == "OK"


# ---------------------------------------------------------------------------
# check_cfn_drift
# ---------------------------------------------------------------------------


class TestCfnDrift:
    def test_no_stack_recorded(self):
        dc = check_cfn_drift(MagicMock(), _state())
        assert dc.status == DriftStatus.OK

    def test_stack_exists_complete(self):
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}],
        }
        dc = check_cfn_drift(cfn, _state(cfn_stack_name="my-stack"))
        assert dc.status == DriftStatus.OK

    def test_stack_not_found(self):
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {"Stacks": []}
        dc = check_cfn_drift(cfn, _state(cfn_stack_name="gone"))
        assert dc.status == DriftStatus.DRIFTED

    def test_stack_bad_status(self):
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "ROLLBACK_IN_PROGRESS"}],
        }
        dc = check_cfn_drift(cfn, _state(cfn_stack_name="bad"))
        assert dc.status == DriftStatus.DRIFTED

    def test_stack_api_error(self):
        cfn = MagicMock()
        cfn.describe_stacks.side_effect = Exception("boom")
        dc = check_cfn_drift(cfn, _state(cfn_stack_name="err"))
        assert dc.status == DriftStatus.ERROR
        assert "boom" in dc.error


# ---------------------------------------------------------------------------
# check_budget_drift
# ---------------------------------------------------------------------------


class TestBudgetDrift:
    def test_budget_exists(self):
        client = MagicMock()
        client.describe_budget.return_value = {}
        state = _state(global_budget_name="daylily-global")
        checks = check_budget_drift(client, "123", state)
        assert len(checks) == 1
        assert checks[0].status == DriftStatus.OK

    def test_budget_not_found(self):
        client = MagicMock()
        client.describe_budget.side_effect = Exception("NotFoundException")
        state = _state(cluster_budget_name="cls-budget")
        checks = check_budget_drift(client, "123", state)
        assert len(checks) == 1
        assert checks[0].status == DriftStatus.DRIFTED

    def test_budget_api_error(self):
        client = MagicMock()
        client.describe_budget.side_effect = Exception("AccessDenied")
        state = _state(global_budget_name="g")
        checks = check_budget_drift(client, "123", state)
        assert checks[0].status == DriftStatus.ERROR

    def test_no_budgets_recorded(self):
        checks = check_budget_drift(MagicMock(), "123", _state())
        assert len(checks) == 0

    def test_both_budgets(self):
        client = MagicMock()
        client.describe_budget.return_value = {}
        state = _state(global_budget_name="g", cluster_budget_name="c")
        checks = check_budget_drift(client, "123", state)
        assert len(checks) == 2


# ---------------------------------------------------------------------------
# check_heartbeat_drift
# ---------------------------------------------------------------------------


class TestHeartbeatDrift:
    def test_topic_exists(self):
        sns = MagicMock()
        sns.get_topic_attributes.return_value = {}
        sched = MagicMock()
        state = _state(heartbeat_topic_arn="arn:aws:sns:us-east-1:123:t")
        checks = check_heartbeat_drift(sns, sched, state)
        assert len(checks) == 1
        assert checks[0].status == DriftStatus.OK
        assert checks[0].id == "heartbeat.topic"

    def test_topic_missing(self):
        sns = MagicMock()
        sns.get_topic_attributes.side_effect = Exception("NotFound")
        sched = MagicMock()
        state = _state(heartbeat_topic_arn="arn:aws:sns:us-east-1:123:t")
        checks = check_heartbeat_drift(sns, sched, state)
        assert checks[0].status == DriftStatus.DRIFTED

    def test_schedule_exists(self):
        sns = MagicMock()
        sched = MagicMock()
        sched.get_schedule.return_value = {}
        state = _state(heartbeat_schedule_name="sched-name")
        checks = check_heartbeat_drift(sns, sched, state)
        assert len(checks) == 1
        assert checks[0].id == "heartbeat.schedule"
        assert checks[0].status == DriftStatus.OK

    def test_schedule_missing(self):
        sns = MagicMock()
        sched = MagicMock()
        sched.get_schedule.side_effect = Exception("ResourceNotFound")
        state = _state(heartbeat_schedule_name="sched-gone")
        checks = check_heartbeat_drift(sns, sched, state)
        assert checks[0].status == DriftStatus.DRIFTED

    def test_no_heartbeat_recorded(self):
        checks = check_heartbeat_drift(MagicMock(), MagicMock(), _state())
        assert len(checks) == 0

    def test_both_topic_and_schedule(self):
        sns = MagicMock()
        sched = MagicMock()
        sched.get_schedule.return_value = {}
        sns.get_topic_attributes.return_value = {}
        state = _state(
            heartbeat_topic_arn="arn:aws:sns:us-east-1:123:t",
            heartbeat_schedule_name="sched",
        )
        checks = check_heartbeat_drift(sns, sched, state)
        assert len(checks) == 2
        assert all(c.status == DriftStatus.OK for c in checks)


# ---------------------------------------------------------------------------
# run_drift_check (aggregation)
# ---------------------------------------------------------------------------


class TestRunDriftCheck:
    def test_no_clients_returns_empty(self):
        report = run_drift_check(_state(cluster_name="c"))
        assert report.cluster_name == "c"
        assert len(report.checks) == 0
        assert not report.has_drift

    def test_cfn_only(self):
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}],
        }
        state = _state(cluster_name="c", cfn_stack_name="stk")
        report = run_drift_check(state, cfn_client=cfn)
        assert len(report.checks) == 1
        assert report.checks[0].id == "cfn.stack"

    def test_all_clients_happy(self):
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "UPDATE_COMPLETE"}],
        }
        budgets = MagicMock()
        budgets.describe_budget.return_value = {}
        sns = MagicMock()
        sns.get_topic_attributes.return_value = {}
        sched = MagicMock()
        sched.get_schedule.return_value = {}

        state = _state(
            cluster_name="full",
            cfn_stack_name="stk",
            global_budget_name="g",
            heartbeat_topic_arn="arn:aws:sns:us-east-1:123:t",
            heartbeat_schedule_name="sched",
        )
        report = run_drift_check(
            state,
            cfn_client=cfn,
            budgets_client=budgets,
            sns_client=sns,
            scheduler_client=sched,
            account_id="123",
        )
        assert not report.has_drift
        assert not report.has_errors
        assert len(report.checks) >= 3

    def test_drift_detected(self):
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {"Stacks": []}
        state = _state(cluster_name="d", cfn_stack_name="gone")
        report = run_drift_check(state, cfn_client=cfn)
        assert report.has_drift

    def test_unknown_cluster_name_when_none(self):
        report = run_drift_check(_state())
        assert report.cluster_name == "unknown"

