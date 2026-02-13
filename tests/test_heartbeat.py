"""Tests for daylily_ec.aws.heartbeat — CP-015."""

from __future__ import annotations

from unittest.mock import MagicMock

from daylily_ec.aws.heartbeat import (
    HeartbeatNames,
    HeartbeatResult,
    _error_code,
    create_or_update_schedule,
    derive_names,
    ensure_heartbeat,
    ensure_topic_and_subscription,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _client_error(code: str) -> Exception:
    """Build a fake ClientError-like exception with a response dict."""
    exc = Exception(code)
    exc.response = {"Error": {"Code": code}}  # type: ignore[attr-defined]
    return exc


# ── HeartbeatNames ───────────────────────────────────────────────────────


class TestHeartbeatNames:
    def test_topic_name(self):
        n = HeartbeatNames(cluster_name="foo")
        assert n.topic_name == "daylily-foo-heartbeat"

    def test_schedule_name_truncated(self):
        long = "a" * 100
        n = HeartbeatNames(cluster_name=long)
        assert len(n.schedule_name) == 64

    def test_topic_arn(self):
        n = HeartbeatNames(cluster_name="c1")
        arn = n.topic_arn("123456789012", "us-west-2")
        assert arn == "arn:aws:sns:us-west-2:123456789012:daylily-c1-heartbeat"


class TestDeriveNames:
    def test_returns_heartbeat_names(self):
        n = derive_names("cl")
        assert isinstance(n, HeartbeatNames)
        assert n.cluster_name == "cl"


# ── _error_code ──────────────────────────────────────────────────────────


class TestErrorCode:
    def test_extracts_code(self):
        exc = _client_error("AuthorizationError")
        assert _error_code(exc) == "AuthorizationError"

    def test_no_response(self):
        assert _error_code(ValueError("x")) == ""

    def test_none_response(self):
        exc = Exception("x")
        exc.response = None  # type: ignore[attr-defined]
        assert _error_code(exc) == ""


# ── ensure_topic_and_subscription ────────────────────────────────────────


class TestEnsureTopicAndSubscription:
    def test_creates_topic_and_subscribes(self):
        sns = MagicMock()
        sns.create_topic.return_value = {"TopicArn": "arn:aws:sns:us-west-2:123:t"}
        sns.list_subscriptions_by_topic.return_value = {"Subscriptions": []}
        arn = ensure_topic_and_subscription(
            sns, "t", "a@b.com", "us-west-2", "123"
        )
        assert arn == "arn:aws:sns:us-west-2:123:t"
        sns.subscribe.assert_called_once()

    def test_skips_subscribe_if_already_exists(self):
        sns = MagicMock()
        sns.create_topic.return_value = {"TopicArn": "arn:t"}
        sns.list_subscriptions_by_topic.return_value = {
            "Subscriptions": [{"Protocol": "email", "Endpoint": "a@b.com"}]
        }
        ensure_topic_and_subscription(sns, "t", "a@b.com", "us-west-2", "123")
        sns.subscribe.assert_not_called()

    def test_auth_error_falls_back_to_existing(self):
        sns = MagicMock()
        sns.create_topic.side_effect = _client_error("AuthorizationError")
        sns.get_topic_attributes.return_value = {}
        sns.list_subscriptions_by_topic.return_value = {"Subscriptions": []}
        arn = ensure_topic_and_subscription(
            sns, "t", "a@b.com", "us-west-2", "123"
        )
        assert "arn:aws:sns:us-west-2:123:t" == arn

    def test_auth_error_no_existing_topic_raises(self):
        sns = MagicMock()
        sns.create_topic.side_effect = _client_error("AuthorizationError")
        sns.get_topic_attributes.side_effect = Exception("not found")
        try:
            ensure_topic_and_subscription(
                sns, "t", "a@b.com", "us-west-2", "123"
            )
            assert False, "Should have raised"
        except RuntimeError as exc:
            assert "forbidden" in str(exc).lower()

    def test_subscribe_auth_error_raises_runtime(self):
        sns = MagicMock()
        sns.create_topic.return_value = {"TopicArn": "arn:t"}
        sns.list_subscriptions_by_topic.return_value = {"Subscriptions": []}
        sns.subscribe.side_effect = _client_error("AuthorizationError")
        try:
            ensure_topic_and_subscription(
                sns, "t", "a@b.com", "us-west-2", "123"
            )
            assert False, "Should have raised"
        except RuntimeError as exc:
            assert "subscription" in str(exc).lower()

    def test_non_auth_create_error_propagates(self):
        sns = MagicMock()
        sns.create_topic.side_effect = _client_error("InternalError")
        try:
            ensure_topic_and_subscription(
                sns, "t", "a@b.com", "us-west-2", "123"
            )
            assert False, "Should have raised"
        except Exception as exc:
            assert _error_code(exc) == "InternalError"


# ── create_or_update_schedule ────────────────────────────────────────────


class TestCreateOrUpdateSchedule:
    def test_creates_schedule(self):
        sch = MagicMock()
        create_or_update_schedule(
            sch, "s1", "rate(60 minutes)", "role", "topic", "msg"
        )
        sch.create_schedule.assert_called_once()
        sch.update_schedule.assert_not_called()

    def test_conflict_falls_back_to_update(self):
        sch = MagicMock()
        sch.create_schedule.side_effect = _client_error("ConflictException")
        create_or_update_schedule(
            sch, "s1", "rate(60 minutes)", "role", "topic", "msg"
        )
        sch.update_schedule.assert_called_once()

    def test_timezone_included_when_set(self):
        sch = MagicMock()
        create_or_update_schedule(
            sch, "s1", "rate(60 minutes)", "role", "topic", "msg",
            timezone="US/Pacific",
        )
        call_kwargs = sch.create_schedule.call_args.kwargs
        assert call_kwargs["ScheduleExpressionTimezone"] == "US/Pacific"

    def test_non_conflict_error_propagates(self):
        sch = MagicMock()
        sch.create_schedule.side_effect = _client_error("AccessDenied")
        try:
            create_or_update_schedule(
                sch, "s1", "rate(60 minutes)", "role", "topic", "msg"
            )
            assert False, "Should have raised"
        except Exception as exc:
            assert _error_code(exc) == "AccessDenied"


# ── ensure_heartbeat ────────────────────────────────────────────────────


class TestEnsureHeartbeat:
    def test_success_path(self):
        sns = MagicMock()
        sns.create_topic.return_value = {
            "TopicArn": "arn:aws:sns:us-west-2:123:daylily-cl-heartbeat"
        }
        sns.list_subscriptions_by_topic.return_value = {"Subscriptions": []}
        sch = MagicMock()

        r = ensure_heartbeat(
            sns, sch,
            cluster_name="cl",
            region="us-west-2",
            account_id="123",
            email="a@b.com",
            schedule_expression="rate(60 minutes)",
            role_arn="arn:aws:iam::123:role/r",
        )
        assert r.success is True
        assert r.topic_arn.endswith("daylily-cl-heartbeat")
        assert r.schedule_name == "daylily-cl-heartbeat"
        assert r.role_arn == "arn:aws:iam::123:role/r"
        assert r.error == ""

    def test_non_fatal_on_failure(self):
        sns = MagicMock()
        sns.create_topic.side_effect = RuntimeError("boom")
        sch = MagicMock()

        r = ensure_heartbeat(
            sns, sch,
            cluster_name="cl",
            region="us-west-2",
            account_id="123",
            email="a@b.com",
            schedule_expression="rate(60 minutes)",
            role_arn="role",
        )
        assert r.success is False
        assert "boom" in r.error

    def test_result_defaults(self):
        r = HeartbeatResult(success=False)
        assert r.topic_arn == ""
        assert r.schedule_name == ""
        assert r.role_arn == ""
        assert r.error == ""

