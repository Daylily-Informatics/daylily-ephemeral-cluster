"""Tests for workset validation."""

from unittest.mock import MagicMock, patch

import pytest

from daylib.workset_validation import WorksetValidator, ValidationResult


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

