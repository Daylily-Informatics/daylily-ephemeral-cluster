"""Tests for workset validation and rate limiting."""

import time
from unittest.mock import MagicMock, patch

import pytest

from daylib.workset_validation import (
    WorksetValidator,
    ValidationResult,
    ValidationStrictness,
    ValidationError,
    create_validator_from_settings,
)
from daylib.rate_limiting import (
    InMemoryStorage,
    RateLimiter,
    RateLimitCategory,
    create_rate_limit_dependency,
)


@pytest.fixture
def mock_s3():
    """Mock S3 client."""
    with patch("daylib.workset_validation.boto3.Session") as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def validator(mock_s3):
    """Create WorksetValidator instance."""
    return WorksetValidator(
        region="us-west-2",
        profile=None,
    )


@pytest.fixture
def strict_validator(mock_s3):
    """Create WorksetValidator instance with strict mode."""
    return WorksetValidator(
        region="us-west-2",
        profile=None,
        strictness=ValidationStrictness.STRICT,
    )


@pytest.fixture
def permissive_validator(mock_s3):
    """Create WorksetValidator instance with permissive mode."""
    return WorksetValidator(
        region="us-west-2",
        profile=None,
        strictness=ValidationStrictness.PERMISSIVE,
    )


def test_validate_against_schema_valid(validator):
    """Test schema validation with valid config."""
    config = {
        "samples": [
            {"sample_id": "sample1", "fastq_r1": "sample1_R1.fq.gz"},
        ],
        "reference_genome": "hg38",
        "priority": "normal",
    }

    errors = validator._validate_against_schema(config)

    assert len(errors) == 0


def test_validate_against_schema_missing_samples(validator):
    """Test schema validation with missing samples."""
    config = {
        "reference_genome": "hg38",
    }

    errors = validator._validate_against_schema(config)

    assert len(errors) > 0
    assert any("samples" in err.lower() for err in errors)


def test_validate_against_schema_invalid_reference(validator):
    """Test schema validation with invalid reference genome."""
    config = {
        "samples": [
            {"sample_id": "sample1", "fastq_r1": "sample1_R1.fq.gz"},
        ],
        "reference_genome": "invalid_ref",
    }

    errors = validator._validate_against_schema(config)

    assert len(errors) > 0
    assert any("reference_genome" in err.lower() for err in errors)


def test_validate_against_schema_invalid_priority(validator):
    """Test schema validation with invalid priority."""
    config = {
        "samples": [
            {"sample_id": "sample1", "fastq_r1": "sample1_R1.fq.gz"},
        ],
        "reference_genome": "hg38",
        "priority": "super_urgent",
    }

    errors = validator._validate_against_schema(config)

    assert len(errors) > 0
    assert any("priority" in err.lower() for err in errors)


def test_validate_against_schema_invalid_max_retries(validator):
    """Test schema validation with invalid max_retries."""
    config = {
        "samples": [
            {"sample_id": "sample1", "fastq_r1": "sample1_R1.fq.gz"},
        ],
        "reference_genome": "hg38",
        "max_retries": 100,
    }

    errors = validator._validate_against_schema(config)

    assert len(errors) > 0
    assert any("max_retries" in err.lower() for err in errors)


def test_estimate_resources(validator):
    """Test resource estimation."""
    config = {
        "samples": [
            {"sample_id": "sample1", "fastq_r1": "sample1_R1.fq.gz"},
            {"sample_id": "sample2", "fastq_r1": "sample2_R1.fq.gz"},
        ],
        "reference_genome": "hg38",
        "estimated_coverage": 30,
    }

    estimates = validator._estimate_resources(config)

    assert estimates["estimated_cost_usd"] is not None
    assert estimates["estimated_cost_usd"] > 0
    assert estimates["estimated_duration_minutes"] is not None
    assert estimates["estimated_vcpu_hours"] is not None
    assert estimates["estimated_storage_gb"] is not None


def test_estimate_resources_high_coverage(validator):
    """Test resource estimation with high coverage."""
    config = {
        "samples": [
            {"sample_id": "sample1", "fastq_r1": "sample1_R1.fq.gz"},
        ],
        "reference_genome": "hg38",
        "estimated_coverage": 100,
    }

    estimates = validator._estimate_resources(config)

    # Higher coverage should result in higher estimates
    assert estimates["estimated_cost_usd"] > 1.0
    assert estimates["estimated_vcpu_hours"] > 10.0


def test_validate_workset_dry_run(validator):
    """Test workset validation in dry-run mode."""
    result = validator.validate_workset(
        bucket="test-bucket",
        prefix="worksets/test/",
        dry_run=True,
    )

    assert isinstance(result, ValidationResult)
    assert result.is_valid
    assert len(result.errors) == 0


def test_check_reference_data_dry_run(validator):
    """Test reference data check in dry-run mode."""
    errors, warnings = validator._check_reference_data("hg38", dry_run=True)

    assert len(errors) == 0
    # Warnings are acceptable in dry-run


# ========== New Tests for Enhanced Validation ==========


def test_validate_workset_id_valid(validator):
    """Test workset ID validation with valid IDs."""
    valid_ids = [
        "my-workset",
        "workset_123",
        "WS-2024-01-01",
        "a" * 64,  # Max length
        "abc",  # Min length
    ]
    for ws_id in valid_ids:
        errors = validator.validate_workset_id(ws_id)
        assert len(errors) == 0, f"Expected no errors for '{ws_id}', got: {errors}"


def test_validate_workset_id_invalid(validator):
    """Test workset ID validation with invalid IDs."""
    invalid_ids = [
        "",  # Empty
        "ab",  # Too short
        "-starts-with-dash",  # Starts with dash
        "_starts_with_underscore",  # Starts with underscore
        "has spaces",
        "a" * 65,  # Too long
    ]
    for ws_id in invalid_ids:
        errors = validator.validate_workset_id(ws_id)
        assert len(errors) > 0, f"Expected errors for '{ws_id}', got none"


def test_validate_prefix_format_valid(validator):
    """Test prefix validation with valid prefixes."""
    valid_prefixes = [
        "worksets/test/",
        "a/b/c",
        "myprefix",
        "",  # Empty is valid
    ]
    for prefix in valid_prefixes:
        errors = validator.validate_prefix_format(prefix)
        assert len(errors) == 0, f"Expected no errors for '{prefix}', got: {errors}"


def test_validate_config_dict(validator):
    """Test direct config validation."""
    config = {
        "samples": [{"sample_id": "s1", "fastq_r1": "s1.fq.gz"}],
        "reference_genome": "hg38",
    }
    result = validator.validate_config_dict(config, workset_id="test-workset")

    assert result.is_valid
    assert len(result.errors) == 0
    assert result.estimated_cost_usd is not None


def test_validate_config_dict_with_invalid_workset_id(validator):
    """Test config validation catches invalid workset ID."""
    config = {
        "samples": [{"sample_id": "s1", "fastq_r1": "s1.fq.gz"}],
        "reference_genome": "hg38",
    }
    result = validator.validate_config_dict(config, workset_id="ab")  # Too short

    assert not result.is_valid
    assert len(result.errors) > 0
    assert any("workset_id" in str(e).lower() for e in result.detailed_errors)


def test_validation_result_to_dict(validator):
    """Test ValidationResult serialization."""
    result = validator.validate_workset(
        bucket="test-bucket",
        prefix="worksets/test/",
        dry_run=True,
    )

    result_dict = result.to_dict()

    assert "is_valid" in result_dict
    assert "errors" in result_dict
    assert "warnings" in result_dict
    assert "detailed_errors" in result_dict
    assert isinstance(result_dict["detailed_errors"], list)


def test_strictness_permissive_allows_warnings(permissive_validator):
    """Test permissive mode doesn't fail on warnings."""
    result = permissive_validator.validate_workset(
        bucket="test-bucket",
        prefix="worksets/test/",
        dry_run=True,
    )

    # In permissive mode, even with warnings, should be valid
    assert result.is_valid


def test_validation_error_str():
    """Test ValidationError string representation."""
    error = ValidationError(
        field="bucket",
        message="Bucket not found",
        code="BUCKET_NOT_FOUND",
        remediation="Create the bucket first",
    )

    error_str = str(error)

    assert "BUCKET_NOT_FOUND" in error_str
    assert "bucket" in error_str.lower()
    assert "Create the bucket" in error_str


# ========== Rate Limiting Tests ==========


class TestInMemoryStorage:
    """Tests for InMemoryStorage rate limit backend."""

    def test_first_request_allowed(self):
        """First request should always be allowed."""
        storage = InMemoryStorage()
        allowed, remaining, limit, reset = storage.check_rate_limit("test-key", 10, 60)

        assert allowed is True
        assert remaining == 9
        assert limit == 10

    def test_requests_within_limit(self):
        """Requests within limit should be allowed."""
        storage = InMemoryStorage()

        for i in range(10):
            allowed, remaining, _, _ = storage.check_rate_limit("test-key", 10, 60)
            assert allowed is True
            assert remaining == 9 - i

    def test_requests_exceed_limit(self):
        """Requests exceeding limit should be denied."""
        storage = InMemoryStorage()

        # Use up all tokens
        for _ in range(10):
            storage.check_rate_limit("test-key", 10, 60)

        # Next request should be denied
        allowed, remaining, _, _ = storage.check_rate_limit("test-key", 10, 60)
        assert allowed is False
        assert remaining == 0

    def test_different_keys_independent(self):
        """Different keys should have independent limits."""
        storage = InMemoryStorage()

        # Use up all tokens for key1
        for _ in range(10):
            storage.check_rate_limit("key1", 10, 60)

        # key2 should still have tokens
        allowed, remaining, _, _ = storage.check_rate_limit("key2", 10, 60)
        assert allowed is True
        assert remaining == 9

    def test_cleanup_old_buckets(self):
        """Old buckets should be cleaned up."""
        storage = InMemoryStorage()

        # Create some buckets
        storage.check_rate_limit("key1", 10, 60)
        storage.check_rate_limit("key2", 10, 60)

        # Manually age the buckets
        for key in storage._buckets:
            storage._buckets[key].last_update = time.time() - 7200  # 2 hours ago

        # Cleanup with 1 hour max age
        removed = storage.cleanup_old_buckets(max_age_seconds=3600)

        assert removed == 2
        assert len(storage._buckets) == 0


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_get_limit_for_category(self):
        """Test getting limits for different categories."""
        mock_settings = MagicMock()
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_auth_per_minute = 5
        mock_settings.rate_limit_read_per_minute = 100
        mock_settings.rate_limit_write_per_minute = 50
        mock_settings.rate_limit_admin_per_minute = 10
        mock_settings.rate_limit_whitelist = ""

        limiter = RateLimiter(settings=mock_settings)

        assert limiter.get_limit_for_category(RateLimitCategory.AUTH) == 5
        assert limiter.get_limit_for_category(RateLimitCategory.READ) == 100
        assert limiter.get_limit_for_category(RateLimitCategory.WRITE) == 50
        assert limiter.get_limit_for_category(RateLimitCategory.ADMIN) == 10

    def test_rate_limit_disabled(self):
        """Test that disabled rate limiting allows all requests."""
        mock_settings = MagicMock()
        mock_settings.rate_limit_enabled = False
        mock_settings.rate_limit_whitelist = ""

        limiter = RateLimiter(settings=mock_settings)

        # Create mock request
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "127.0.0.1"
        mock_request.state = MagicMock()
        mock_request.state.user_id = None

        allowed, headers = limiter.check_rate_limit(mock_request, RateLimitCategory.READ)

        assert allowed is True
        assert headers == {}

    def test_whitelisted_ip_bypasses_limit(self):
        """Test that whitelisted IPs bypass rate limiting."""
        mock_settings = MagicMock()
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_read_per_minute = 1
        mock_settings.rate_limit_whitelist = "127.0.0.1,10.0.0.1"
        mock_settings.is_rate_limit_whitelisted = lambda x: x in ["127.0.0.1", "10.0.0.1"]

        limiter = RateLimiter(settings=mock_settings)

        # Create mock request from whitelisted IP
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "127.0.0.1"
        mock_request.state = MagicMock()
        mock_request.state.user_id = None

        # Should be allowed even with limit of 1
        for _ in range(10):
            allowed, _ = limiter.check_rate_limit(mock_request, RateLimitCategory.READ)
            assert allowed is True