"""Tests for daylily_ec.aws.context — AWS context, identity, region/profile resolution.

CP-003 acceptance criteria:
1. Given --profile + --region-az, returns account_id and caller_arn
2. Stable for both IAM user and assumed-role ARNs
3. Region resolution precedence: CLI flag → env var → hardcoded default
4. AWS_PROFILE env respected when no --profile flag given
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from daylily_ec.aws.context import (
    AWSContext,
    _extract_username,
    parse_region_az,
    resolve_profile,
    resolve_region,
)


# ── parse_region_az ──────────────────────────────────────────────────


class TestParseRegionAz:
    def test_standard(self):
        region, az = parse_region_az("us-west-2b")
        assert region == "us-west-2"
        assert az == "b"

    def test_us_east_1a(self):
        region, az = parse_region_az("us-east-1a")
        assert region == "us-east-1"
        assert az == "a"

    def test_eu_west_1c(self):
        region, az = parse_region_az("eu-west-1c")
        assert region == "eu-west-1"
        assert az == "c"

    def test_invalid_last_char_digit(self):
        with pytest.raises(ValueError, match="expected a letter"):
            parse_region_az("us-west-2")

    def test_empty_string(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_region_az("")

    def test_single_letter(self):
        with pytest.raises(ValueError, match="no region component"):
            parse_region_az("a")


# ── resolve_region ───────────────────────────────────────────────────


class TestResolveRegion:
    def test_from_region_az(self):
        assert resolve_region("us-west-2b") == "us-west-2"

    def test_from_aws_default_region(self, monkeypatch):
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
        assert resolve_region() == "eu-central-1"

    def test_from_aws_region(self, monkeypatch):
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.setenv("AWS_REGION", "ap-southeast-1")
        assert resolve_region() == "ap-southeast-1"

    def test_fallback_default(self, monkeypatch):
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        assert resolve_region() == "us-east-1"

    def test_region_az_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
        assert resolve_region("us-west-2b") == "us-west-2"


# ── resolve_profile ──────────────────────────────────────────────────


class TestResolveProfile:
    def test_explicit_profile(self):
        assert resolve_profile("my-profile") == "my-profile"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "env-profile")
        assert resolve_profile() == "env-profile"

    def test_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "env-profile")
        assert resolve_profile("explicit") == "explicit"

    def test_missing_raises(self, monkeypatch):
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        with pytest.raises(RuntimeError, match="AWS_PROFILE is not set"):
            resolve_profile()


# ── _extract_username ────────────────────────────────────────────────


class TestExtractUsername:
    def test_iam_user(self):
        assert _extract_username("arn:aws:iam::123456789012:user/alice") == "alice"

    def test_assumed_role(self):
        arn = "arn:aws:sts::123456789012:assumed-role/MyRole/session-name"
        assert _extract_username(arn) == "session-name"

    def test_root(self):
        assert _extract_username("arn:aws:iam::123456789012:root") == "root"

    def test_federated(self):
        arn = "arn:aws:sts::123456789012:federated-user/bob"
        assert _extract_username(arn) == "bob"


# ── AWSContext.build ─────────────────────────────────────────────────


class TestAWSContextBuild:
    """Tests use mocked boto3 to avoid real AWS calls."""

    @patch("daylily_ec.aws.context.boto3.Session")
    def test_build_success(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_sts = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/alice",
            "UserId": "AIDAEXAMPLE",
        }

        ctx = AWSContext.build(region_az="us-west-2b", profile="test-profile")

        assert ctx.profile == "test-profile"
        assert ctx.region == "us-west-2"
        assert ctx.region_az == "us-west-2b"
        assert ctx.account_id == "123456789012"
        assert ctx.caller_arn == "arn:aws:iam::123456789012:user/alice"
        assert ctx.iam_username == "alice"
        mock_session_cls.assert_called_once_with(
            profile_name="test-profile", region_name="us-west-2"
        )

    @patch("daylily_ec.aws.context.boto3.Session")
    def test_build_assumed_role(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_sts = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_sts.get_caller_identity.return_value = {
            "Account": "987654321098",
            "Arn": "arn:aws:sts::987654321098:assumed-role/AdminRole/sess",
            "UserId": "AROAEXAMPLE:sess",
        }

        ctx = AWSContext.build(region_az="eu-west-1c", profile="role-profile")

        assert ctx.account_id == "987654321098"
        assert ctx.iam_username == "sess"
        assert ctx.region == "eu-west-1"

