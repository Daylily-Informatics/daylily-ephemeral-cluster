"""Tests for daylily_ec.aws.s3 — S3 bucket discovery, selection, verification."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

from daylily_ec.aws.s3 import (
    BUCKET_NAME_FILTER,
    ROLE_CONTROL_DATA,
    ROLE_REFERENCE,
    ROLE_RUNTIME_ASSETS,
    ROLE_STAGING,
    _resolve_bucket_region,
    _standard_s3_config,
    bucket_url,
    list_candidate_buckets,
    make_s3_bucket_preflight_step,
    normalize_role_s3_uri,
    role_prefix_key,
    verify_reference_bundle,
    verify_s3_roles,
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


def _make_reference_s3_client(
    *,
    bucket_exists: bool = True,
    version: str | None = "0.7.131c",
    missing_prefixes: set[str] | None = None,
):
    client = MagicMock()
    if bucket_exists:
        client.head_bucket.return_value = {}
    else:
        client.head_bucket.side_effect = Exception("missing bucket")

    if version is None:
        client.get_object.side_effect = Exception("missing version marker")
    else:
        client.get_object.return_value = {"Body": io.BytesIO(version.encode("utf-8"))}

    missing = missing_prefixes or set()

    def fake_list_objects_v2(*, Bucket: str, Prefix: str, MaxKeys: int):
        if Prefix in missing:
            return {}
        return {"Contents": [{"Key": f"{Prefix}example"}]}

    client.list_objects_v2.side_effect = fake_list_objects_v2
    return client


def _role_values() -> dict[str, str]:
    return {
        ROLE_REFERENCE: "s3://dayoa-reference/references/",
        ROLE_CONTROL_DATA: "s3://dayoa-control/control/",
        ROLE_RUNTIME_ASSETS: "s3://dayoa-runtime/runtime/",
        ROLE_STAGING: "s3://dayoa-staging/staging/",
    }


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

    def test_discovery_disables_s3_accelerate(self):
        ctx = _make_aws_ctx(
            buckets=["my-omics-analysis-us-west-2"],
            locations={"my-omics-analysis-us-west-2": "us-west-2"},
            region="us-west-2",
        )

        list_candidate_buckets(ctx)

        assert ctx.client.call_args.kwargs["config"].s3["use_accelerate_endpoint"] is False

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
# explicit role URI validation
# ---------------------------------------------------------------------------


class TestExplicitRoleUris:
    def test_normalize_bucket_and_prefix(self):
        spec = normalize_role_s3_uri("s3://bucket-a/references", role=ROLE_REFERENCE)

        assert spec.role == ROLE_REFERENCE
        assert spec.uri == "s3://bucket-a/references/"
        assert spec.bucket == "bucket-a"
        assert spec.prefix == "references"

    def test_normalize_bare_bucket_value(self):
        spec = normalize_role_s3_uri("bucket-a/runtime", role=ROLE_RUNTIME_ASSETS)

        assert spec.uri == "s3://bucket-a/runtime/"
        assert role_prefix_key(spec, "cached_envs/") == "runtime/cached_envs/"

    def test_rejects_missing_and_non_s3_values(self):
        for value in ("", "https://bucket/key"):
            try:
                normalize_role_s3_uri(value, role=ROLE_REFERENCE)
            except ValueError as exc:
                assert ROLE_REFERENCE in str(exc)
            else:
                raise AssertionError(f"expected ValueError for {value!r}")

    @patch("daylily_ec.aws.s3._reference_bucket_s3_client")
    def test_verify_s3_roles_checks_required_role_prefixes(self, mock_client_factory):
        client = _make_reference_s3_client()
        mock_client_factory.return_value = client

        ok, details = verify_s3_roles(_role_values(), profile="prof", region="us-west-2")

        assert ok is True
        assert details["roles"][ROLE_REFERENCE]["uri"] == "s3://dayoa-reference/references/"
        assert details["buckets"] == [
            "dayoa-control",
            "dayoa-reference",
            "dayoa-runtime",
            "dayoa-staging",
        ]
        assert client.get_object.call_args_list[0].kwargs == {
            "Bucket": "dayoa-reference",
            "Key": "references/s3_reference_data_version.info",
        }
        checked_prefixes = [call.kwargs["Prefix"] for call in client.list_objects_v2.call_args_list]
        assert "references/genomic_data/organism_references/H_sapiens/hg38/" in checked_prefixes
        assert "control/genomic_data/organism_reads/" in checked_prefixes
        assert "runtime/cached_envs/" in checked_prefixes

    def test_verify_s3_roles_rejects_overlapping_role_prefixes(self):
        values = _role_values()
        values[ROLE_REFERENCE] = "s3://same-bucket/data/"
        values[ROLE_CONTROL_DATA] = "s3://same-bucket/data/reads/"

        ok, details = verify_s3_roles(values)

        assert ok is False
        assert "must not overlap" in details["issues"][0]


# ---------------------------------------------------------------------------
# verify_reference_bundle
# ---------------------------------------------------------------------------


class TestVerifyReferenceBundle:
    @patch("daylily_ec.aws.s3._reference_bucket_s3_client")
    def test_success(self, mock_client_factory):
        mock_client_factory.return_value = _make_reference_s3_client()

        assert verify_reference_bundle("my-bucket", profile="prof", region="us-west-2")
        mock_client_factory.assert_called_once_with(profile="prof", region="us-west-2")

    @patch("daylily_ec.aws.s3._reference_bucket_s3_client")
    def test_failure_when_required_prefix_missing(self, mock_client_factory):
        mock_client_factory.return_value = _make_reference_s3_client(
            missing_prefixes={"cluster_boot_config/"},
        )

        assert not verify_reference_bundle("bad-bucket")

    @patch("daylily_ec.aws.s3._reference_bucket_s3_client")
    def test_failure_when_version_marker_missing(self, mock_client_factory):
        mock_client_factory.return_value = _make_reference_s3_client(version=None)

        assert not verify_reference_bundle("any-bucket")

    @patch("daylily_ec.aws.s3._reference_bucket_s3_client")
    def test_failure_when_bucket_missing(self, mock_client_factory):
        mock_client_factory.return_value = _make_reference_s3_client(bucket_exists=False)

        assert not verify_reference_bundle("bucket")

    @patch("daylily_ec.aws.s3._reference_bucket_s3_client")
    def test_no_profile_no_region(self, mock_client_factory):
        mock_client_factory.return_value = _make_reference_s3_client()

        verify_reference_bundle("bucket")
        mock_client_factory.assert_called_once_with(profile="", region="")


class TestStandardS3Config:
    def test_disables_accelerate_endpoint(self):
        assert _standard_s3_config().s3["use_accelerate_endpoint"] is False


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
    @patch("daylily_ec.aws.s3.verify_s3_roles")
    def test_full_success(self, mock_verify):
        mock_verify.return_value = (
            True,
            {
                "roles": {
                    role: {"uri": value if value.endswith("/") else f"{value}/", "bucket": value.split("/")[2], "prefix": ""}
                    for role, value in _role_values().items()
                },
                "buckets": [
                    "dayoa-control",
                    "dayoa-reference",
                    "dayoa-runtime",
                    "dayoa-staging",
                ],
                "issues": [],
            },
        )
        ctx = _make_aws_ctx(region="us-west-2")
        step = make_s3_bucket_preflight_step(
            ctx,
            profile="myprof",
            reference_bucket=_role_values()[ROLE_REFERENCE],
            control_data_bucket=_role_values()[ROLE_CONTROL_DATA],
            runtime_assets_bucket=_role_values()[ROLE_RUNTIME_ASSETS],
            stage_bucket=_role_values()[ROLE_STAGING],
        )
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert len(report.checks) == 2
        assert report.checks[0].id == "s3.role_config"
        assert report.checks[0].status == CheckStatus.PASS
        assert report.checks[1].id == "s3.role_verify"
        assert report.checks[1].status == CheckStatus.PASS
        mock_verify.assert_called_once_with(_role_values(), profile="myprof", region="us-west-2")

    def test_missing_role_config_fails(self):
        ctx = _make_aws_ctx(region="us-west-2")
        step = make_s3_bucket_preflight_step(ctx)
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert len(report.checks) == 1
        assert report.checks[0].id == "s3.role_config"
        assert report.checks[0].status == CheckStatus.FAIL
        assert "explicit reference_bucket" in report.checks[0].remediation

    @patch("daylily_ec.aws.s3.verify_s3_roles")
    def test_verification_failure_hard_gate(self, mock_verify):
        mock_verify.return_value = (
            False,
            {
                "roles": {
                    role: {"uri": value if value.endswith("/") else f"{value}/", "bucket": value.split("/")[2], "prefix": ""}
                    for role, value in _role_values().items()
                },
                "buckets": ["dayoa-reference"],
                "issues": ["reference: missing version marker"],
            },
        )
        ctx = _make_aws_ctx(region="us-west-2")
        step = make_s3_bucket_preflight_step(
            ctx,
            reference_bucket=_role_values()[ROLE_REFERENCE],
            control_data_bucket=_role_values()[ROLE_CONTROL_DATA],
            runtime_assets_bucket=_role_values()[ROLE_RUNTIME_ASSETS],
            stage_bucket=_role_values()[ROLE_STAGING],
        )
        report = PreflightReport(region="us-west-2")
        report = step(report)

        assert len(report.checks) == 2
        assert report.checks[0].status == CheckStatus.PASS
        assert report.checks[1].id == "s3.role_verify"
        assert report.checks[1].status == CheckStatus.FAIL
        assert not report.passed

    @patch("daylily_ec.aws.s3.verify_s3_roles")
    def test_preserves_existing_checks(self, mock_verify):
        mock_verify.return_value = (
            True,
            {"roles": {role: {"uri": value, "bucket": value.split("/")[2], "prefix": ""} for role, value in _role_values().items()}, "buckets": [], "issues": []},
        )
        ctx = _make_aws_ctx(region="us-west-2")
        step = make_s3_bucket_preflight_step(
            ctx,
            reference_bucket=_role_values()[ROLE_REFERENCE],
            control_data_bucket=_role_values()[ROLE_CONTROL_DATA],
            runtime_assets_bucket=_role_values()[ROLE_RUNTIME_ASSETS],
            stage_bucket=_role_values()[ROLE_STAGING],
        )
        report = PreflightReport(region="us-west-2")
        report.checks.append(
            CheckResult(id="prior.check", status=CheckStatus.PASS)
        )
        report = step(report)

        assert len(report.checks) == 3
        assert report.checks[0].id == "prior.check"

    @patch("daylily_ec.aws.s3.verify_s3_roles")
    def test_uses_report_region(self, mock_verify):
        mock_verify.return_value = (
            True,
            {"roles": {role: {"uri": value, "bucket": value.split("/")[2], "prefix": ""} for role, value in _role_values().items()}, "buckets": [], "issues": []},
        )
        ctx = _make_aws_ctx(region="us-west-2")
        step = make_s3_bucket_preflight_step(
            ctx,
            reference_bucket=_role_values()[ROLE_REFERENCE],
            control_data_bucket=_role_values()[ROLE_CONTROL_DATA],
            runtime_assets_bucket=_role_values()[ROLE_RUNTIME_ASSETS],
            stage_bucket=_role_values()[ROLE_STAGING],
        )
        report = PreflightReport(region="eu-west-1")
        report = step(report)

        assert report.checks[0].status == CheckStatus.PASS
        mock_verify.assert_called_once_with(_role_values(), profile="", region="eu-west-1")

    def test_returns_callable(self):
        ctx = _make_aws_ctx()
        step = make_s3_bucket_preflight_step(ctx)
        assert callable(step)
