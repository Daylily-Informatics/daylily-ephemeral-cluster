"""Tests for daylily_ec.aws.s3 — S3 bucket discovery, selection, verification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from daylily_ec.aws.s3 import (
    BUCKET_NAME_FILTER,
    _resolve_bucket_region,
    bucket_url,
    list_candidate_buckets,
    make_s3_bucket_preflight_step,
    select_bucket,
    verify_reference_bundle,
)
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_s3_client(
    buckets: list[str] | None = None,
    locations: dict[str, str | None] | None = None,
):
    """Build a mock S3 client.

    *buckets* is a list of bucket names returned by ``list_buckets``.
    *locations* maps bucket_name → LocationConstraint value (None means us-east-1).
    """
    locs = locations or {}
    client = MagicMock()
    client.list_buckets.return_value = {
        "Buckets": [{"Name": n} for n in (buckets or [])],
    }

    def fake_get_location(Bucket: str):
        if Bucket in locs:
            return {"LocationConstraint": locs[Bucket]}
        return {"LocationConstraint": None}

    client.get_bucket_location = MagicMock(side_effect=fake_get_location)
    return client


def _make_aws_ctx(
    buckets: list[str] | None = None,
    locations: dict[str, str | None] | None = None,
    region: str = "us-west-2",
):
    """Build a fake AWSContext with a mock S3 client."""
    s3_client = _make_s3_client(buckets, locations)
    ctx = MagicMock()
    ctx.region = region
    ctx.client = MagicMock(return_value=s3_client)
    return ctx


# ---------------------------------------------------------------------------
# _resolve_bucket_region
# ---------------------------------------------------------------------------


class TestResolveBucketRegion:
    def test_none_means_us_east_1(self):
        client = MagicMock()
        client.get_bucket_location.return_value = {"LocationConstraint": None}
        assert _resolve_bucket_region(client, "b") == "us-east-1"

    def test_explicit_region(self):
        client = MagicMock()
        client.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}
        assert _resolve_bucket_region(client, "b") == "eu-west-1"

    def test_api_error_returns_none(self):
        client = MagicMock()
        client.get_bucket_location.side_effect = Exception("denied")
        assert _resolve_bucket_region(client, "b") is None


# ---------------------------------------------------------------------------
# list_candidate_buckets
# ---------------------------------------------------------------------------


class TestListCandidateBuckets:
    def test_filters_by_name_and_region(self):
        ctx = _make_aws_ctx(
            buckets=[
                "my-omics-analysis-us-west-2",
                "other-bucket",
                "dev-omics-analysis-us-east-1",
            ],
            locations={
                "my-omics-analysis-us-west-2": "us-west-2",
                "other-bucket": "us-west-2",
                "dev-omics-analysis-us-east-1": "us-east-1",
            },
            region="us-west-2",
        )
        result = list_candidate_buckets(ctx)
        assert result == ["my-omics-analysis-us-west-2"]

    def test_none_location_maps_to_us_east_1(self):
        ctx = _make_aws_ctx(
            buckets=["prod-omics-analysis-global"],
            locations={"prod-omics-analysis-global": None},
            region="us-east-1",
        )
        result = list_candidate_buckets(ctx)
        assert result == ["prod-omics-analysis-global"]

    def test_no_matching_buckets(self):
        ctx = _make_aws_ctx(buckets=["unrelated-bucket"], region="us-west-2")
        assert list_candidate_buckets(ctx) == []

    def test_empty_bucket_list(self):
        ctx = _make_aws_ctx(buckets=[], region="us-west-2")
        assert list_candidate_buckets(ctx) == []

    def test_api_error_returns_empty(self):
        ctx = MagicMock()
        ctx.region = "us-west-2"
        s3_client = MagicMock()
        s3_client.list_buckets.side_effect = Exception("access denied")
        ctx.client.return_value = s3_client
        assert list_candidate_buckets(ctx) == []

    def test_target_region_override(self):
        ctx = _make_aws_ctx(
            buckets=["omics-analysis-eu"],
            locations={"omics-analysis-eu": "eu-west-1"},
            region="us-west-2",
        )
        result = list_candidate_buckets(ctx, target_region="eu-west-1")
        assert result == ["omics-analysis-eu"]

    def test_results_sorted(self):
        ctx = _make_aws_ctx(
            buckets=["z-omics-analysis", "a-omics-analysis"],
            locations={
                "z-omics-analysis": "us-west-2",
                "a-omics-analysis": "us-west-2",
            },
            region="us-west-2",
        )
        assert list_candidate_buckets(ctx) == [
            "a-omics-analysis",
            "z-omics-analysis",
        ]

    def test_bucket_name_filter_constant(self):
        assert BUCKET_NAME_FILTER == "omics-analysis"

# ---------------------------------------------------------------------------
# select_bucket
# ---------------------------------------------------------------------------


class TestSelectBucket:
    def test_auto_apply_set_value_in_candidates(self):
        result = select_bucket(
            ["bucket-a", "bucket-b"],
            cfg_action="USESETVALUE",
            cfg_set_value="bucket-b",
        )
        assert result == "bucket-b"

    def test_auto_apply_set_value_not_in_candidates(self):
        result = select_bucket(
            ["bucket-a"],
            cfg_action="USESETVALUE",
            cfg_set_value="bucket-missing",
        )
        # Falls through to single-candidate auto-select
        assert result == "bucket-a"

    def test_single_candidate_auto_select(self):
        result = select_bucket(["only-bucket"])
        assert result == "only-bucket"

    @patch.dict("os.environ", {"DAY_DISABLE_AUTO_SELECT": "1"})
    def test_single_candidate_disabled_auto_select(self):
        result = select_bucket(["only-bucket"])
        assert result is None

    def test_cfg_bucket_name_fallback(self):
        result = select_bucket(
            ["bucket-a", "bucket-b"],
            cfg_bucket_name="bucket-a",
        )
        assert result == "bucket-a"

    def test_cfg_bucket_name_not_in_candidates(self):
        result = select_bucket(
            ["bucket-a", "bucket-b"],
            cfg_bucket_name="bucket-c",
        )
        assert result is None

    def test_no_candidates_returns_none(self):
        result = select_bucket([])
        assert result is None

    def test_multiple_candidates_no_config_returns_none(self):
        result = select_bucket(["bucket-a", "bucket-b"])
        assert result is None

    @patch.dict("os.environ", {"DAY_DISABLE_AUTO_SELECT": "1"})
    def test_auto_select_disabled_skips_set_value(self):
        """DAY_DISABLE_AUTO_SELECT=1 disables auto-apply of set_value."""
        result = select_bucket(
            ["bucket-a"],
            cfg_action="USESETVALUE",
            cfg_set_value="bucket-a",
        )
        assert result is None

    def test_priority_set_value_over_single(self):
        """set_value takes priority over single-candidate auto-select."""
        result = select_bucket(
            ["bucket-a"],
            cfg_action="USESETVALUE",
            cfg_set_value="bucket-a",
        )
        assert result == "bucket-a"


# ---------------------------------------------------------------------------
# verify_reference_bundle
# ---------------------------------------------------------------------------


class TestVerifyReferenceBundle:
    @patch("daylily_ec.aws.s3.shutil.which", return_value="/usr/bin/fake")
    @patch("daylily_ec.aws.s3.subprocess.run")
    def test_success(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0)
        assert verify_reference_bundle("my-bucket", profile="prof", region="us-west-2")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "verify" in cmd
        assert "--bucket" in cmd
        assert "my-bucket" in cmd
        assert "--exclude-b37" in cmd
        assert "--profile" in cmd
        assert "prof" in cmd
        assert "--region" in cmd
        assert "us-west-2" in cmd

    @patch("daylily_ec.aws.s3.shutil.which", return_value="/usr/bin/fake")
    @patch("daylily_ec.aws.s3.subprocess.run")
    def test_failure(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=1, stderr="bad", stdout="")
        assert not verify_reference_bundle("bad-bucket")

    @patch("daylily_ec.aws.s3.shutil.which", return_value=None)
    def test_missing_command(self, mock_which):
        assert not verify_reference_bundle("any-bucket")

    @patch("daylily_ec.aws.s3.shutil.which", return_value="/usr/bin/fake")
    @patch("daylily_ec.aws.s3.subprocess.run")
    def test_timeout(self, mock_run, mock_which):
        import subprocess as sp

        mock_run.side_effect = sp.TimeoutExpired(cmd="x", timeout=300)
        assert not verify_reference_bundle("bucket")

    @patch("daylily_ec.aws.s3.shutil.which", return_value="/usr/bin/fake")
    @patch("daylily_ec.aws.s3.subprocess.run")
    def test_no_profile_no_region(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0)
        verify_reference_bundle("bucket")
        cmd = mock_run.call_args[0][0]
        assert "--profile" not in cmd
        assert "--region" not in cmd


# ---------------------------------------------------------------------------
# bucket_url
# ---------------------------------------------------------------------------


class TestBucketUrl:
    def test_format(self):
        assert bucket_url("my-bucket") == "s3://my-bucket"

    def test_empty(self):
        assert bucket_url("") == "s3://"


# ---------------------------------------------------------------------------
# make_s3_bucket_preflight_step
# ---------------------------------------------------------------------------


class TestMakeS3BucketPreflightStep:
    @patch("daylily_ec.aws.s3.shutil.which", return_value="/usr/bin/fake")
    @patch("daylily_ec.aws.s3.subprocess.run")
    def test_full_success(self, mock_run, mock_which):
        """Happy path: single bucket found, verified, PASS."""
        mock_run.return_value = MagicMock(returncode=0)
        ctx = _make_aws_ctx(
            buckets=["prod-omics-analysis-usw2"],
            locations={"prod-omics-analysis-usw2": "us-west-2"},
        )
        step = make_s3_bucket_preflight_step(
            ctx, profile="myprof",
        )
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert len(report.checks) == 2
        assert report.checks[0].id == "s3.bucket_select"
        assert report.checks[0].status == CheckStatus.PASS
        assert report.checks[0].details["selected"] == "prod-omics-analysis-usw2"
        assert report.checks[0].details["bucket_url"] == "s3://prod-omics-analysis-usw2"
        assert report.checks[1].id == "s3.bucket_verify"
        assert report.checks[1].status == CheckStatus.PASS

    def test_no_candidates_fail(self):
        """No matching buckets → FAIL."""
        ctx = _make_aws_ctx(buckets=["unrelated"], region="us-west-2")
        step = make_s3_bucket_preflight_step(ctx)
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert len(report.checks) == 1
        assert report.checks[0].id == "s3.bucket_select"
        assert report.checks[0].status == CheckStatus.FAIL
        assert "No S3 buckets" in report.checks[0].remediation

    def test_multiple_no_config_fail(self):
        """Multiple candidates, no auto-select config → FAIL."""
        ctx = _make_aws_ctx(
            buckets=["a-omics-analysis", "b-omics-analysis"],
            locations={
                "a-omics-analysis": "us-west-2",
                "b-omics-analysis": "us-west-2",
            },
        )
        step = make_s3_bucket_preflight_step(ctx)
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert len(report.checks) == 1
        assert report.checks[0].status == CheckStatus.FAIL
        assert "auto-selected" in report.checks[0].remediation

    @patch("daylily_ec.aws.s3.shutil.which", return_value="/usr/bin/fake")
    @patch("daylily_ec.aws.s3.subprocess.run")
    def test_verification_failure_hard_gate(self, mock_run, mock_which):
        """Verification failure → FAIL (hard gate)."""
        mock_run.return_value = MagicMock(returncode=1, stderr="err", stdout="")
        ctx = _make_aws_ctx(
            buckets=["omics-analysis-bucket"],
            locations={"omics-analysis-bucket": "us-west-2"},
        )
        step = make_s3_bucket_preflight_step(ctx)
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert len(report.checks) == 2
        assert report.checks[0].status == CheckStatus.PASS  # select ok
        assert report.checks[1].id == "s3.bucket_verify"
        assert report.checks[1].status == CheckStatus.FAIL
        assert not report.passed

    @patch("daylily_ec.aws.s3.shutil.which", return_value="/usr/bin/fake")
    @patch("daylily_ec.aws.s3.subprocess.run")
    def test_config_set_value_selection(self, mock_run, mock_which):
        """Config set_value selects correct bucket from multiple."""
        mock_run.return_value = MagicMock(returncode=0)
        ctx = _make_aws_ctx(
            buckets=["a-omics-analysis", "b-omics-analysis"],
            locations={
                "a-omics-analysis": "us-west-2",
                "b-omics-analysis": "us-west-2",
            },
        )
        step = make_s3_bucket_preflight_step(
            ctx,
            cfg_action="USESETVALUE",
            cfg_set_value="b-omics-analysis",
        )
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert report.checks[0].details["selected"] == "b-omics-analysis"
        assert report.passed

    @patch("daylily_ec.aws.s3.shutil.which", return_value="/usr/bin/fake")
    @patch("daylily_ec.aws.s3.subprocess.run")
    def test_preserves_existing_checks(self, mock_run, mock_which):
        """Step preserves checks already in the report."""
        mock_run.return_value = MagicMock(returncode=0)
        ctx = _make_aws_ctx(
            buckets=["omics-analysis-x"],
            locations={"omics-analysis-x": "us-west-2"},
        )
        step = make_s3_bucket_preflight_step(ctx)
        report = PreflightReport(region="us-west-2")
        report.checks.append(
            CheckResult(id="prior.check", status=CheckStatus.PASS)
        )
        report = step(report)

        assert len(report.checks) == 3
        assert report.checks[0].id == "prior.check"

    @patch("daylily_ec.aws.s3.shutil.which", return_value="/usr/bin/fake")
    @patch("daylily_ec.aws.s3.subprocess.run")
    def test_uses_report_region(self, mock_run, mock_which):
        """Step uses report.region, not aws_ctx.region."""
        mock_run.return_value = MagicMock(returncode=0)
        ctx = _make_aws_ctx(
            buckets=["omics-analysis-eu"],
            locations={"omics-analysis-eu": "eu-west-1"},
            region="us-west-2",
        )
        step = make_s3_bucket_preflight_step(ctx)
        report = PreflightReport(region="eu-west-1")
        report = step(report)

        assert report.checks[0].status == CheckStatus.PASS
        assert report.checks[0].details["selected"] == "omics-analysis-eu"

    def test_returns_callable(self):
        ctx = _make_aws_ctx()
        step = make_s3_bucket_preflight_step(ctx)
        assert callable(step)
