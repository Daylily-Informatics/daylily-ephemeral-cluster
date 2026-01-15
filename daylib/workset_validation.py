"""Workset validation and pre-flight checks.

Validates workset configuration, estimates resources, and checks dependencies.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
import yaml
from botocore.exceptions import ClientError

LOGGER = logging.getLogger("daylily.workset_validation")


@dataclass
class ValidationResult:
    """Result of workset validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    estimated_cost_usd: Optional[float] = None
    estimated_duration_minutes: Optional[int] = None
    estimated_vcpu_hours: Optional[float] = None
    estimated_storage_gb: Optional[float] = None


class WorksetValidator:
    """Validates workset configuration and dependencies."""

    # JSON Schema for daylily_work.yaml
    WORK_YAML_SCHEMA = {
        "type": "object",
        "required": ["samples", "reference_genome"],
        "properties": {
            "samples": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["sample_id", "fastq_r1"],
                    "properties": {
                        "sample_id": {"type": "string", "minLength": 1},
                        "fastq_r1": {"type": "string", "minLength": 1},
                        "fastq_r2": {"type": "string"},
                        "coverage": {"type": "number", "minimum": 0},
                    },
                },
            },
            "reference_genome": {
                "type": "string",
                "enum": ["hg38", "hg19", "grch38", "grch37"],
            },
            "pipeline": {
                "type": "string",
                "enum": ["germline", "somatic", "rna-seq"],
            },
            "priority": {
                "type": "string",
                "enum": ["urgent", "normal", "low"],
            },
            "max_retries": {"type": "integer", "minimum": 0, "maximum": 10},
            "preferred_cluster": {"type": "string"},
            "estimated_coverage": {"type": "number", "minimum": 0},
        },
    }

    def __init__(
        self,
        region: str,
        profile: Optional[str] = None,
        cost_config_path: Optional[str] = None,
    ):
        """Initialize validator.

        Args:
            region: AWS region
            profile: AWS profile name
            cost_config_path: Path to cost estimation config
        """
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self.s3 = session.client("s3")
        self.region = region
        self.cost_config_path = cost_config_path or "config/daylily_ephemeral_cost_config.yaml"

    def validate_workset(
        self,
        bucket: str,
        prefix: str,
        dry_run: bool = False,
    ) -> ValidationResult:
        """Validate a workset configuration.

        Args:
            bucket: S3 bucket name
            prefix: S3 prefix for workset
            dry_run: If True, only validate without checking S3

        Returns:
            ValidationResult with validation status and estimates
        """
        errors = []
        warnings = []

        # Step 1: Validate daylily_work.yaml exists and is valid
        work_yaml_path = f"{prefix.rstrip('/')}/daylily_work.yaml"
        
        if not dry_run:
            try:
                work_yaml_content = self._get_s3_object(bucket, work_yaml_path)
                work_config = yaml.safe_load(work_yaml_content)
            except Exception as e:
                errors.append(f"Failed to load daylily_work.yaml: {e}")
                return ValidationResult(False, errors, warnings)
        else:
            # In dry-run mode, use a minimal valid config
            work_config = {
                "samples": [{"sample_id": "test", "fastq_r1": "test.fq.gz"}],
                "reference_genome": "hg38",
            }

        # Step 2: Validate against JSON schema
        schema_errors = self._validate_against_schema(work_config)
        errors.extend(schema_errors)

        # Step 3: Check reference data availability
        ref_errors, ref_warnings = self._check_reference_data(
            work_config.get("reference_genome"),
            dry_run,
        )
        errors.extend(ref_errors)
        warnings.extend(ref_warnings)

        # Step 4: Validate FASTQ files exist (if not dry-run)
        if not dry_run:
            fastq_errors = self._validate_fastq_files(bucket, prefix, work_config)
            errors.extend(fastq_errors)

        # Step 5: Estimate resources
        estimates = self._estimate_resources(work_config)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            **estimates,
        )

    def _get_s3_object(self, bucket: str, key: str) -> str:
        """Get S3 object content as string."""
        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            raise ValueError(f"S3 object not found: s3://{bucket}/{key}") from e

    def _validate_against_schema(self, config: Dict[str, Any]) -> List[str]:
        """Validate config against JSON schema.

        Args:
            config: Configuration dict

        Returns:
            List of validation errors
        """
        errors = []

        # Check required fields
        if "samples" not in config:
            errors.append("Missing required field: samples")
        elif not isinstance(config["samples"], list) or len(config["samples"]) == 0:
            errors.append("samples must be a non-empty array")
        else:
            # Validate each sample
            for i, sample in enumerate(config["samples"]):
                if not isinstance(sample, dict):
                    errors.append(f"Sample {i} must be an object")
                    continue

                if "sample_id" not in sample:
                    errors.append(f"Sample {i} missing required field: sample_id")
                if "fastq_r1" not in sample:
                    errors.append(f"Sample {i} missing required field: fastq_r1")

        if "reference_genome" not in config:
            errors.append("Missing required field: reference_genome")
        elif config["reference_genome"] not in ["hg38", "hg19", "grch38", "grch37"]:
            errors.append(
                f"Invalid reference_genome: {config['reference_genome']}. "
                "Must be one of: hg38, hg19, grch38, grch37"
            )

        # Validate optional fields
        if "priority" in config and config["priority"] not in ["urgent", "normal", "low"]:
            errors.append(f"Invalid priority: {config['priority']}")

        if "max_retries" in config:
            try:
                retries = int(config["max_retries"])
                if retries < 0 or retries > 10:
                    errors.append("max_retries must be between 0 and 10")
            except (ValueError, TypeError):
                errors.append("max_retries must be an integer")

        return errors

    def _check_reference_data(
        self,
        reference_genome: Optional[str],
        dry_run: bool,
    ) -> Tuple[List[str], List[str]]:
        """Check if reference data is available.

        Args:
            reference_genome: Reference genome name
            dry_run: Skip actual checks if True

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        if not reference_genome:
            return errors, warnings

        if dry_run:
            LOGGER.info("Dry-run mode: skipping reference data check")
            return errors, warnings

        # Check if reference bucket exists (example)
        reference_bucket = "daylily-reference-data"
        reference_key = f"genomes/{reference_genome}/genome.fa"

        try:
            self.s3.head_object(Bucket=reference_bucket, Key=reference_key)
            LOGGER.info("Reference genome %s found", reference_genome)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                warnings.append(
                    f"Reference genome {reference_genome} not found in {reference_bucket}. "
                    "It may need to be downloaded."
                )
            else:
                warnings.append(f"Could not verify reference data: {e}")

        return errors, warnings

    def _validate_fastq_files(
        self,
        bucket: str,
        prefix: str,
        config: Dict[str, Any],
    ) -> List[str]:
        """Validate that FASTQ files exist in S3.

        Args:
            bucket: S3 bucket
            prefix: S3 prefix
            config: Workset configuration

        Returns:
            List of errors
        """
        errors = []
        samples = config.get("samples", [])

        for i, sample in enumerate(samples):
            sample_id = sample.get("sample_id", f"sample_{i}")
            fastq_r1 = sample.get("fastq_r1")
            fastq_r2 = sample.get("fastq_r2")

            if fastq_r1:
                r1_key = f"{prefix.rstrip('/')}/{fastq_r1}"
                try:
                    self.s3.head_object(Bucket=bucket, Key=r1_key)
                except ClientError:
                    errors.append(f"FASTQ R1 not found for {sample_id}: s3://{bucket}/{r1_key}")

            if fastq_r2:
                r2_key = f"{prefix.rstrip('/')}/{fastq_r2}"
                try:
                    self.s3.head_object(Bucket=bucket, Key=r2_key)
                except ClientError:
                    errors.append(f"FASTQ R2 not found for {sample_id}: s3://{bucket}/{r2_key}")

        return errors

    def _estimate_resources(self, config: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Estimate resource requirements using cost calculation scripts.

        Args:
            config: Workset configuration

        Returns:
            Dict with resource estimates
        """
        estimates = {
            "estimated_cost_usd": None,
            "estimated_duration_minutes": None,
            "estimated_vcpu_hours": None,
            "estimated_storage_gb": None,
        }

        try:
            # Calculate based on samples and coverage
            num_samples = len(config.get("samples", []))
            avg_coverage = config.get("estimated_coverage", 30)

            # Simple estimation (can be enhanced with actual cost scripts)
            # Assume ~200 vCPU-minutes per 1x coverage per sample
            vcpu_minutes = num_samples * avg_coverage * 200
            estimates["estimated_vcpu_hours"] = vcpu_minutes / 60

            # Assume ~$0.05 per vCPU-hour
            estimates["estimated_cost_usd"] = estimates["estimated_vcpu_hours"] * 0.05

            # Assume ~60 minutes per sample at 30x coverage
            estimates["estimated_duration_minutes"] = int(num_samples * (avg_coverage / 30) * 60)

            # Assume ~1.5 GB per 1x coverage per sample
            estimates["estimated_storage_gb"] = num_samples * avg_coverage * 1.5

            LOGGER.info(
                "Estimated resources: %d samples, %.1fx coverage, $%.2f, %d minutes",
                num_samples,
                avg_coverage,
                estimates["estimated_cost_usd"] or 0,
                estimates["estimated_duration_minutes"] or 0,
            )

        except Exception as e:
            LOGGER.warning("Failed to estimate resources: %s", str(e))

        return estimates


