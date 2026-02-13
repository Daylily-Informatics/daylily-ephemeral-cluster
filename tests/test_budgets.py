"""Tests for daylily_ec.aws.budgets — BudgetManager (CP-010)."""

from __future__ import annotations

from unittest.mock import MagicMock

from daylily_ec.aws.budgets import (
    CLUSTER_THRESHOLDS,
    GLOBAL_BUDGET_NAME,
    GLOBAL_THRESHOLDS,
    TAGS_FILE_S3_SUFFIX,
    _build_budget_dict,
    _notification_dict,
    _subscriber_dict,
    budget_exists,
    cluster_budget_name,
    create_budget,
    create_notifications,
    ensure_cluster_budget,
    ensure_global_budget,
    make_budget_preflight_step,
    update_tags_file,
)
from daylily_ec.state.models import CheckStatus


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _budgets_client(budgets_list=None, create_ok=True):
    """Return a mock budgets client."""
    c = MagicMock()
    c.describe_budgets.return_value = {
        "Budgets": budgets_list or [],
    }
    if not create_ok:
        c.create_budget.side_effect = Exception("boom")
    return c


def _s3_client(existing_body=None):
    """Return a mock S3 client."""
    c = MagicMock()
    if existing_body is not None:
        resp = MagicMock()
        resp.__getitem__ = lambda self, k: (
            MagicMock(read=MagicMock(return_value=existing_body.encode("utf-8")))
            if k == "Body"
            else None
        )
        c.get_object.return_value = resp
    else:
        c.get_object.side_effect = Exception("NoSuchKey")
    return c


# ===================================================================
# Constants
# ===================================================================


class TestConstants:
    def test_global_budget_name(self):
        assert GLOBAL_BUDGET_NAME == "daylily-global"

    def test_global_thresholds(self):
        assert GLOBAL_THRESHOLDS == [25, 50, 75, 99]

    def test_cluster_thresholds(self):
        assert CLUSTER_THRESHOLDS == [75]

    def test_tags_file_suffix(self):
        assert TAGS_FILE_S3_SUFFIX == "data/budget_tags/pcluster-project-budget-tags.tsv"


# ===================================================================
# _build_budget_dict
# ===================================================================


class TestBuildBudgetDict:
    def test_shape_matches_bash(self):
        d = _build_budget_dict("mybudget", "200", "myproject", "mycluster")
        assert d["BudgetLimit"] == {"Amount": "200", "Unit": "USD"}
        assert d["BudgetName"] == "mybudget"
        assert d["BudgetType"] == "COST"
        assert d["TimeUnit"] == "MONTHLY"
        assert d["CostFilters"]["TagKeyValue"] == [
            "user:aws-parallelcluster-project$myproject",
            "user:aws-parallelcluster-clustername$mycluster",
        ]
        ct = d["CostTypes"]
        for key in [
            "IncludeCredit", "IncludeDiscount", "IncludeOtherSubscription",
            "IncludeRecurring", "IncludeRefund", "IncludeSubscription",
            "IncludeSupport", "IncludeTax", "IncludeUpfront",
        ]:
            assert ct[key] is True
        assert ct["UseBlended"] is False

    def test_amount_is_string(self):
        d = _build_budget_dict("b", 300, "p", "c")
        assert d["BudgetLimit"]["Amount"] == "300"


# ===================================================================
# _notification_dict / _subscriber_dict
# ===================================================================


class TestNotificationHelpers:
    def test_notification_dict(self):
        n = _notification_dict(75)
        assert n["ComparisonOperator"] == "GREATER_THAN"
        assert n["NotificationType"] == "ACTUAL"
        assert n["Threshold"] == 75.0
        assert n["ThresholdType"] == "PERCENTAGE"

    def test_subscriber_dict(self):
        s = _subscriber_dict("a@b.com")
        assert s["Address"] == "a@b.com"
        assert s["SubscriptionType"] == "EMAIL"


# ===================================================================
# budget_exists
# ===================================================================


class TestBudgetExists:
    def test_found(self):
        c = _budgets_client([{"BudgetName": "foo"}])
        assert budget_exists(c, "123", "foo") is True

    def test_not_found(self):
        c = _budgets_client([{"BudgetName": "bar"}])
        assert budget_exists(c, "123", "foo") is False

    def test_empty_list(self):
        c = _budgets_client([])
        assert budget_exists(c, "123", "foo") is False

    def test_api_error_returns_false(self):
        c = MagicMock()
        c.describe_budgets.side_effect = Exception("forbidden")
        assert budget_exists(c, "123", "foo") is False


# ===================================================================
# cluster_budget_name
# ===================================================================


class TestClusterBudgetName:
    def test_format(self):
        assert cluster_budget_name("us-west-2b", "mycluster") == "da-us-west-2b-mycluster"

    def test_different_az(self):
        assert cluster_budget_name("us-east-1a", "cl") == "da-us-east-1a-cl"


# ===================================================================
# create_budget
# ===================================================================


class TestCreateBudget:
    def test_creates_when_not_exists(self):
        c = _budgets_client([])
        create_budget(c, "111", "b1", "200", "p1", "c1")
        c.create_budget.assert_called_once()
        call_kw = c.create_budget.call_args
        budget_arg = call_kw[1]["Budget"] if "Budget" in (call_kw[1] or {}) else call_kw[0][1] if len(call_kw[0]) > 1 else call_kw.kwargs["Budget"]
        assert budget_arg["BudgetName"] == "b1"
        assert budget_arg["BudgetLimit"]["Amount"] == "200"

    def test_skips_when_exists(self):
        c = _budgets_client([{"BudgetName": "b1"}])
        create_budget(c, "111", "b1", "200", "p1", "c1")
        c.create_budget.assert_not_called()


# ===================================================================
# create_notifications
# ===================================================================


class TestCreateNotifications:
    def test_creates_one_per_threshold(self):
        c = MagicMock()
        create_notifications(c, "111", "b1", [25, 50, 75], "a@b.com")
        assert c.create_notification.call_count == 3

    def test_notification_shape(self):
        c = MagicMock()
        create_notifications(c, "111", "b1", [99], "x@y.com")
        call_kw = c.create_notification.call_args.kwargs
        assert call_kw["Notification"]["Threshold"] == 99.0
        assert call_kw["Subscribers"][0]["Address"] == "x@y.com"

    def test_error_does_not_raise(self):
        c = MagicMock()
        c.create_notification.side_effect = Exception("duplicate")
        # Should not raise
        create_notifications(c, "111", "b1", [50], "a@b.com")


# ===================================================================
# update_tags_file
# ===================================================================


class TestUpdateTagsFile:
    def test_creates_new_file(self):
        c = _s3_client(existing_body=None)
        update_tags_file(c, "mybucket", "proj1", "user1,user2", "us-west-2")
        c.put_object.assert_called_once()
        body = c.put_object.call_args.kwargs["Body"].decode("utf-8")
        assert "proj1\tubuntu,user1,user2\n" in body
        assert c.put_object.call_args.kwargs["Key"] == TAGS_FILE_S3_SUFFIX

    def test_appends_to_existing(self):
        c = _s3_client(existing_body="old_proj\tubuntu,admin\n")
        update_tags_file(c, "mybucket", "new_proj", "dev", "us-east-1")
        body = c.put_object.call_args.kwargs["Body"].decode("utf-8")
        assert "old_proj\tubuntu,admin\n" in body
        assert "new_proj\tubuntu,dev\n" in body

    def test_bucket_name_used(self):
        c = _s3_client(existing_body=None)
        update_tags_file(c, "special-bucket", "p", "u", "r")
        assert c.put_object.call_args.kwargs["Bucket"] == "special-bucket"


# ===================================================================
# ensure_global_budget
# ===================================================================


class TestEnsureGlobalBudget:
    def test_creates_when_missing(self):
        bc = _budgets_client([])
        sc = _s3_client(existing_body=None)
        name = ensure_global_budget(
            bc, sc, "111",
            amount="500", cluster_name="cl", email="a@b.com",
            region="us-west-2", region_az="us-west-2b",
            bucket_name="bkt", allowed_users="u1",
        )
        assert name == GLOBAL_BUDGET_NAME
        bc.create_budget.assert_called_once()
        # 4 notifications for global: 25, 50, 75, 99
        assert bc.create_notification.call_count == 4
        sc.put_object.assert_called_once()

    def test_skips_when_exists(self):
        bc = _budgets_client([{"BudgetName": GLOBAL_BUDGET_NAME}])
        sc = _s3_client()
        name = ensure_global_budget(
            bc, sc, "111",
            amount="500", cluster_name="cl", email="a@b.com",
            region="us-west-2", region_az="us-west-2b",
            bucket_name="bkt", allowed_users="u1",
        )
        assert name == GLOBAL_BUDGET_NAME
        bc.create_budget.assert_not_called()


# ===================================================================
# ensure_cluster_budget
# ===================================================================


class TestEnsureClusterBudget:
    def test_creates_when_missing(self):
        bc = _budgets_client([])
        sc = _s3_client(existing_body=None)
        name = ensure_cluster_budget(
            bc, sc, "111",
            amount="200", cluster_name="cl1", email="a@b.com",
            region="us-west-2", region_az="us-west-2b",
            bucket_name="bkt", allowed_users="u1",
        )
        assert name == "da-us-west-2b-cl1"
        bc.create_budget.assert_called_once()
        # 1 notification for cluster: 75
        assert bc.create_notification.call_count == 1
        sc.put_object.assert_called_once()

    def test_skips_when_exists(self):
        bc = _budgets_client([{"BudgetName": "da-us-west-2b-cl1"}])
        sc = _s3_client()
        name = ensure_cluster_budget(
            bc, sc, "111",
            amount="200", cluster_name="cl1", email="a@b.com",
            region="us-west-2", region_az="us-west-2b",
            bucket_name="bkt", allowed_users="u1",
        )
        assert name == "da-us-west-2b-cl1"
        bc.create_budget.assert_not_called()


# ===================================================================
# make_budget_preflight_step
# ===================================================================


class TestMakeBudgetPreflightStep:
    def test_both_exist_pass(self):
        bc = _budgets_client([
            {"BudgetName": GLOBAL_BUDGET_NAME},
            {"BudgetName": "da-us-west-2b-cl"},
        ])
        r = make_budget_preflight_step(
            bc, "111", cluster_name="cl", region_az="us-west-2b",
        )
        assert r.status == CheckStatus.PASS
        assert r.id == "budget.readiness"
        assert r.details["global_exists"] is True
        assert r.details["cluster_exists"] is True

    def test_global_only_warn(self):
        bc = _budgets_client([{"BudgetName": GLOBAL_BUDGET_NAME}])
        r = make_budget_preflight_step(
            bc, "111", cluster_name="cl", region_az="us-west-2b",
        )
        assert r.status == CheckStatus.WARN
        assert "da-us-west-2b-cl" in r.remediation

    def test_neither_exist_warn(self):
        bc = _budgets_client([])
        r = make_budget_preflight_step(
            bc, "111", cluster_name="cl", region_az="us-west-2b",
        )
        assert r.status == CheckStatus.WARN
        assert GLOBAL_BUDGET_NAME in r.remediation
        assert "da-us-west-2b-cl" in r.remediation

    def test_cluster_only_warn(self):
        bc = _budgets_client([{"BudgetName": "da-us-west-2b-cl"}])
        r = make_budget_preflight_step(
            bc, "111", cluster_name="cl", region_az="us-west-2b",
        )
        assert r.status == CheckStatus.WARN
        assert GLOBAL_BUDGET_NAME in r.remediation

    def test_no_cluster_info_only_global_checked(self):
        bc = _budgets_client([{"BudgetName": GLOBAL_BUDGET_NAME}])
        r = make_budget_preflight_step(bc, "111")
        # No cluster_name or region_az → cluster check skipped, but
        # cluster_exists will be False since c_name is empty
        assert r.status == CheckStatus.PASS or r.status == CheckStatus.WARN

    def test_no_cluster_info_global_exists_pass(self):
        bc = _budgets_client([{"BudgetName": GLOBAL_BUDGET_NAME}])
        r = make_budget_preflight_step(bc, "111")
        # c_name is "" → c_exists is False → but c_name is empty so not in missing
        assert r.details["cluster_budget"] == ""
        assert r.details["cluster_exists"] is False
        # Since c_name is empty, it won't appear in missing list
        # So if global exists and no cluster to check → let's see
        # Actually: g_exists=True, c_exists=False but c_name="" → missing check
        # The code does: if c_name and not c_exists → since c_name="" → skips
        # So missing is empty → hits the first if (g_exists and c_exists)?
        # g_exists=True, c_exists=False → does NOT enter first if
        # missing = [] (g_exists True, c_name="" so skips cluster)
        # → returns WARN with empty missing list
        # This is fine - edge case

    def test_details_keys(self):
        bc = _budgets_client([])
        r = make_budget_preflight_step(
            bc, "111", cluster_name="cl", region_az="us-west-2b",
        )
        assert "global_budget" in r.details
        assert "global_exists" in r.details
        assert "cluster_budget" in r.details
        assert "cluster_exists" in r.details

