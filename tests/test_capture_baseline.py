"""Baseline-capture tooling: global-trail coverage and principal bucketing.

Regression context: the 2026-08-14 baseline capture was first run against
us-west-2 only and reported zero IAM activity, which would have supported the
false conclusion that the deployer needs no IAM permissions. The deploy had in
fact made 95 IAM write calls — all recorded in the us-east-1 global trail.
"""
import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "util" / "capture_baseline.py"


def _load():
    spec = importlib.util.spec_from_file_location("capture_baseline", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capture = _load()


class TestPlanScans:
    def test_global_trail_is_scanned_alongside_the_deploy_region(self):
        assert capture.plan_scans("us-west-2", "us-east-1") == [
            ("us-west-2", False),
            ("us-east-1", True),
        ]

    def test_global_region_is_filtered_to_global_services(self):
        """The global trail also carries its own region's regional activity."""
        scans = dict(capture.plan_scans("us-west-2", "us-east-1"))
        assert scans["us-west-2"] is False
        assert scans["us-east-1"] is True

    def test_deploying_into_the_global_region_needs_one_unfiltered_pass(self):
        """Otherwise us-east-1 regional events would be dropped by the filter."""
        assert capture.plan_scans("us-east-1", "us-east-1") == [("us-east-1", False)]

    @pytest.mark.parametrize("empty", ["", "   ", None])
    def test_global_region_can_be_disabled_explicitly(self, empty):
        assert capture.plan_scans("us-west-2", empty) == [("us-west-2", False)]


class TestGlobalEventSources:
    @pytest.mark.parametrize("service", ["iam", "sts", "budgets", "route53"])
    def test_services_daylily_actually_uses_are_covered(self, service):
        """Dropping any of these hides real deployer permissions."""
        assert service in capture.GLOBAL_EVENT_SOURCES

    @pytest.mark.parametrize("service", ["ec2", "fsx", "cloudformation", "s3"])
    def test_regional_services_are_not_treated_as_global(self, service):
        assert service not in capture.GLOBAL_EVENT_SOURCES


class TestClassify:
    """Bucketing is what stops instance-role calls inflating the deployer policy."""

    def test_deployer_direct_call(self):
        ev = {"userIdentity": {"type": "AssumedRole",
                               "arn": "arn:aws:sts::1:assumed-role/DaylilyBaselineDeploy/s"}}
        assert capture.classify(ev, "DaylilyBaselineDeploy") == "deployer"

    def test_cloudformation_using_deployer_credentials_still_needs_the_permission(self):
        ev = {"userIdentity": {"type": "AssumedRole",
                               "arn": "arn:aws:sts::1:assumed-role/DaylilyBaselineDeploy/s"},
              "invokedBy": "cloudformation.amazonaws.com"}
        assert capture.classify(ev, "DaylilyBaselineDeploy") == "deployer-via-cfn"

    def test_head_node_role_is_not_the_deployer(self):
        """ec2:CreateFleet arrives this way; it belongs to the node boundary."""
        ev = {"userIdentity": {"type": "AssumedRole",
                               "arn": "arn:aws:sts::1:assumed-role/c-RoleHeadNode-x/i-1",
                               "sessionContext": {"sessionIssuer": {
                                   "arn": "arn:aws:iam::1:role/c-RoleHeadNode-x"}}}}
        assert capture.classify(ev, "DaylilyBaselineDeploy") == "instance-role"

    def test_aws_service_principal_needs_no_permission(self):
        assert capture.classify({"userIdentity": {"type": "AWSService"}}, "X") == "service"
