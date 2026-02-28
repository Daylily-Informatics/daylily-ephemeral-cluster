"""Tests for daylily_ec.aws.quotas — CP-005 QuotaValidator."""

from __future__ import annotations

from unittest.mock import MagicMock

from daylily_ec.aws.quotas import (
    QUOTA_DEFS,
    SPOT_VCPU_QUOTA_CODE,
    _fetch_quota_value,
    check_all_quotas,
    compute_spot_vcpu_demand,
    make_quota_preflight_step,
)
from daylily_ec.state.models import CheckStatus, PreflightReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_aws_ctx(quota_responses: dict[str, float | None] | None = None):
    """Build a fake AWSContext with a mock service-quotas client.

    *quota_responses* maps quota_code → value.  If value is None, the client
    raises an exception for that call.
    """
    responses = quota_responses or {}
    ctx = MagicMock()
    ctx.region = "us-west-2"

    sq_client = MagicMock()

    def fake_get_service_quota(ServiceCode: str, QuotaCode: str):
        if QuotaCode in responses:
            val = responses[QuotaCode]
            if val is None:
                raise Exception(f"Simulated API failure for {QuotaCode}")
            return {"Quota": {"Value": val}}
        # Default: return generous quota
        return {"Quota": {"Value": 999.0}}

    sq_client.get_service_quota = MagicMock(side_effect=fake_get_service_quota)
    ctx.client = MagicMock(return_value=sq_client)
    return ctx


# ---------------------------------------------------------------------------
# TestComputeSpotVcpuDemand
# ---------------------------------------------------------------------------


class TestComputeSpotVcpuDemand:
    """Verify exact Bash parity for vCPU calculation."""

    def test_defaults(self):
        assert compute_spot_vcpu_demand(1, 1, 1) == 8 + 128 + 192

    def test_zero_all(self):
        assert compute_spot_vcpu_demand(0, 0, 0) == 0

    def test_only_8i(self):
        assert compute_spot_vcpu_demand(10, 0, 0) == 80

    def test_only_128i(self):
        assert compute_spot_vcpu_demand(0, 3, 0) == 384

    def test_only_192i(self):
        assert compute_spot_vcpu_demand(0, 0, 2) == 384

    def test_mixed(self):
        # (2*8) + (1*128) + (1*192) = 16 + 128 + 192 = 336
        assert compute_spot_vcpu_demand(2, 1, 1) == 336

    def test_large_values(self):
        # (10*8) + (5*128) + (3*192) = 80 + 640 + 576 = 1296
        assert compute_spot_vcpu_demand(10, 5, 3) == 1296


# ---------------------------------------------------------------------------
# TestQuotaDefs
# ---------------------------------------------------------------------------


class TestQuotaDefs:
    """Verify static quota definitions match spec."""

    def test_count(self):
        assert len(QUOTA_DEFS) == 6

    def test_spot_code_in_defs(self):
        codes = [q.quota_code for q in QUOTA_DEFS]
        assert SPOT_VCPU_QUOTA_CODE in codes

    def test_all_have_check_ids(self):
        for q in QUOTA_DEFS:
            assert q.check_id.startswith("quota.")

    def test_quota_codes(self):
        expected = {
            "L-1216C47A",
            "L-34B43A08",
            "L-F678F1CE",
            "L-0263D0A3",
            "L-FE5A380F",
            "L-A4707A72",
        }
        actual = {q.quota_code for q in QUOTA_DEFS}
        assert actual == expected

    def test_recommended_mins(self):
        by_code = {q.quota_code: q.recommended_min for q in QUOTA_DEFS}
        assert by_code["L-1216C47A"] == 20
        assert by_code["L-34B43A08"] == 192
        assert by_code["L-F678F1CE"] == 5
        assert by_code["L-0263D0A3"] == 5
        assert by_code["L-FE5A380F"] == 5
        assert by_code["L-A4707A72"] == 5


# ---------------------------------------------------------------------------
# TestFetchQuotaValue
# ---------------------------------------------------------------------------


class TestFetchQuotaValue:
    """Test the internal _fetch_quota_value helper."""

    def test_success(self):
        client = MagicMock()
        client.get_service_quota.return_value = {"Quota": {"Value": 42.0}}
        assert _fetch_quota_value(client, "ec2", "L-FAKE") == 42.0

    def test_api_error_returns_none(self):
        client = MagicMock()
        client.get_service_quota.side_effect = Exception("boom")
        assert _fetch_quota_value(client, "ec2", "L-FAKE") is None


# ---------------------------------------------------------------------------
# TestCheckAllQuotas
# ---------------------------------------------------------------------------


class TestCheckAllQuotas:
    """Integration tests for check_all_quotas."""

    def test_all_pass_generous_quotas(self):
        """All quotas above recommended → 6 PASS results."""
        ctx = _make_aws_ctx()  # defaults to 999 for all
        results = check_all_quotas(ctx, max_count_8i=1, max_count_128i=1, max_count_192i=1)
        assert len(results) == 6
        assert all(r.status == CheckStatus.PASS for r in results)

    def test_result_ids_match_defs(self):
        ctx = _make_aws_ctx()
        results = check_all_quotas(ctx)
        expected_ids = {q.check_id for q in QUOTA_DEFS}
        actual_ids = {r.id for r in results}
        assert actual_ids == expected_ids

    def test_details_include_required_fields(self):
        """Each result details must include quota_code, service_code, recommended_min."""
        ctx = _make_aws_ctx()
        results = check_all_quotas(ctx)
        for r in results:
            assert "quota_code" in r.details
            assert "service_code" in r.details
            assert "recommended_min" in r.details
            assert "current_value" in r.details

    def test_below_recommended_warns(self):
        """Quota below recommended_min → WARN."""
        ctx = _make_aws_ctx({"L-1216C47A": 5.0})  # on-demand, recommended=20
        results = check_all_quotas(ctx)
        od = [r for r in results if r.id == "quota.ondemand_vcpu"][0]
        assert od.status == CheckStatus.WARN
        assert "below" in od.remediation.lower()

    def test_api_failure_warns(self):
        """API failure for a quota → WARN with note."""
        ctx = _make_aws_ctx({"L-F678F1CE": None})  # VPC quota fails
        results = check_all_quotas(ctx)
        vpc = [r for r in results if r.id == "quota.vpcs"][0]
        assert vpc.status == CheckStatus.WARN
        assert vpc.details.get("note") == "API call failed"
        assert vpc.details.get("current_value") is None

    def test_spot_vcpu_demand_below_quota_passes(self):
        """Spot demand < quota → PASS."""
        # demand = (1*8) + (1*128) + (1*192) = 328, quota = 999
        ctx = _make_aws_ctx()
        results = check_all_quotas(ctx)
        spot = [r for r in results if r.id == "quota.spot_vcpu"][0]
        assert spot.status == CheckStatus.PASS

    def test_spot_vcpu_demand_exceeds_quota_interactive_warns(self):
        """Spot demand >= quota + interactive → WARN."""
        # demand = (10*8) + (5*128) + (3*192) = 1296, quota = 200
        ctx = _make_aws_ctx({"L-34B43A08": 200.0})
        results = check_all_quotas(
            ctx,
            max_count_8i=10,
            max_count_128i=5,
            max_count_192i=3,
            non_interactive=False,
        )
        spot = [r for r in results if r.id == "quota.spot_vcpu"][0]
        assert spot.status == CheckStatus.WARN
        assert spot.details["tot_vcpu_demand"] == 1296
        assert "1296" in spot.remediation

    def test_spot_vcpu_demand_exceeds_quota_noninteractive_fails(self):
        """Spot demand >= quota + non-interactive → FAIL."""
        ctx = _make_aws_ctx({"L-34B43A08": 200.0})
        results = check_all_quotas(
            ctx,
            max_count_8i=10,
            max_count_128i=5,
            max_count_192i=3,
            non_interactive=True,
        )
        spot = [r for r in results if r.id == "quota.spot_vcpu"][0]
        assert spot.status == CheckStatus.FAIL

    def test_spot_demand_exactly_equal_to_quota(self):
        """Spot demand == quota → triggers warning/fail (>= comparison)."""
        # demand = (1*8) + (1*128) + (1*192) = 328
        ctx = _make_aws_ctx({"L-34B43A08": 328.0})
        results = check_all_quotas(ctx, non_interactive=True)
        spot = [r for r in results if r.id == "quota.spot_vcpu"][0]
        assert spot.status == CheckStatus.FAIL

    def test_spot_demand_one_below_quota_passes(self):
        """Spot demand < quota by 1 → PASS (not below recommended either)."""
        # demand = 328, quota = 329
        ctx = _make_aws_ctx({"L-34B43A08": 329.0})
        results = check_all_quotas(ctx)
        spot = [r for r in results if r.id == "quota.spot_vcpu"][0]
        assert spot.status == CheckStatus.PASS

    def test_all_api_failures(self):
        """All 6 API calls fail → 6 WARN results."""
        failing = {q.quota_code: None for q in QUOTA_DEFS}
        ctx = _make_aws_ctx(failing)
        results = check_all_quotas(ctx)
        assert len(results) == 6
        assert all(r.status == CheckStatus.WARN for r in results)

    def test_client_created_once(self):
        """service-quotas client should be created once, not per-check."""
        ctx = _make_aws_ctx()
        check_all_quotas(ctx)
        ctx.client.assert_called_once_with("service-quotas")

    def test_spot_details_include_demand(self):
        """Spot check details always include tot_vcpu_demand when demand >= quota."""
        ctx = _make_aws_ctx({"L-34B43A08": 100.0})
        results = check_all_quotas(ctx, max_count_8i=2, max_count_128i=1, max_count_192i=1)
        spot = [r for r in results if r.id == "quota.spot_vcpu"][0]
        assert spot.details["tot_vcpu_demand"] == (2 * 8) + 128 + 192


# ---------------------------------------------------------------------------
# TestMakeQuotaPreflightStep
# ---------------------------------------------------------------------------


class TestMakeQuotaPreflightStep:
    """Test the preflight step factory."""

    def test_returns_callable(self):
        ctx = _make_aws_ctx()
        step = make_quota_preflight_step(ctx)
        assert callable(step)

    def test_step_appends_checks_to_report(self):
        ctx = _make_aws_ctx()
        step = make_quota_preflight_step(ctx)
        report = PreflightReport(run_id="test123", region="us-west-2")
        result = step(report)
        assert len(result.checks) == 6
        assert result is report  # mutates in place

    def test_step_passes_config_values(self):
        ctx = _make_aws_ctx({"L-34B43A08": 100.0})
        step = make_quota_preflight_step(
            ctx,
            max_count_8i=10,
            max_count_128i=5,
            max_count_192i=3,
            non_interactive=True,
        )
        report = PreflightReport(run_id="test456")
        result = step(report)
        spot = [c for c in result.checks if c.id == "quota.spot_vcpu"][0]
        assert spot.status == CheckStatus.FAIL
        assert spot.details["tot_vcpu_demand"] == 1296

    def test_step_preserves_existing_checks(self):
        """Step should extend, not replace, existing checks."""
        from daylily_ec.state.models import CheckResult

        ctx = _make_aws_ctx()
        step = make_quota_preflight_step(ctx)
        report = PreflightReport(run_id="test789")
        report.checks.append(
            CheckResult(id="toolchain.python", status=CheckStatus.PASS)
        )
        result = step(report)
        assert len(result.checks) == 7  # 1 existing + 6 quota
        assert result.checks[0].id == "toolchain.python"




