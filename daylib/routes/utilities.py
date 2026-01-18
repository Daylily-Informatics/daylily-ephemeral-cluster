"""Utility API routes for Daylily.

Contains S3 discovery, cost estimation, and bucket validation endpoints.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

import boto3
import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from daylib.config import Settings
from daylib.routes.dependencies import calculate_cost_with_efficiency

LOGGER = logging.getLogger("daylily.routes.utilities")


# ========== Pydantic Models ==========


class CostEstimateRequest(BaseModel):
    """Request model for cost estimation."""

    pipeline_type: str = Field(..., description="Pipeline type: germline, somatic, rnaseq, wgs, wes")
    reference_genome: str = Field("GRCh38", description="Reference genome")
    sample_count: int = Field(1, ge=1, description="Number of samples")
    estimated_coverage: float = Field(30.0, ge=1.0, description="Estimated coverage depth")
    priority: str = Field("normal", description="Priority: urgent, high, normal, low")
    data_size_gb: float = Field(0.0, ge=0.0, description="Total data size in GB (0 = auto-calculate)")


class CostEstimateResponse(BaseModel):
    """Response model for cost estimation."""

    estimated_cost_usd: float
    compute_cost_usd: float
    storage_cost_usd: float
    transfer_cost_usd: float
    vcpu_hours: float
    estimated_duration_hours: float
    estimated_duration_minutes: int
    data_size_gb: float
    efficiency_multiplier: float
    pipeline_type: str
    sample_count: int
    priority: str
    cost_breakdown: Dict[str, str]
    notes: List[str]


class S3DiscoveryResponse(BaseModel):
    """Response model for S3 sample discovery."""

    samples: List[Dict[str, Any]]
    yaml_content: Optional[str] = None
    files_found: int
    bucket: str
    prefix: str
    normalized_prefix: str
    total_objects_scanned: int


class BucketValidationResponse(BaseModel):
    """Response model for S3 bucket validation."""

    bucket: str
    valid: bool
    fully_configured: bool
    exists: bool
    accessible: bool
    can_read: bool
    can_write: bool
    can_list: bool
    region: Optional[str] = None
    errors: List[str]
    warnings: List[str]
    setup_instructions: Optional[str] = None


# ========== Router Factory ==========


def create_utilities_router(
    settings: Settings,
    get_current_user: Callable[..., Any],
) -> APIRouter:
    """Create utilities router with injected dependencies.

    Args:
        settings: Application settings
        get_current_user: Dependency for current user authentication

    Returns:
        Configured APIRouter
    """
    router = APIRouter(tags=["utilities"])
    region = settings.get_effective_region()
    profile = settings.aws_profile

    @router.post("/api/estimate-cost", response_model=CostEstimateResponse)
    async def estimate_workset_cost(
        pipeline_type: str = Body(..., embed=True),
        reference_genome: str = Body("GRCh38", embed=True),
        sample_count: int = Body(1, embed=True),
        estimated_coverage: float = Body(30.0, embed=True),
        priority: str = Body("normal", embed=True),
        data_size_gb: float = Body(0.0, embed=True),
    ):
        """Estimate cost for a workset based on parameters."""
        # Base vCPU-hours per sample by pipeline type
        base_vcpu_hours_per_sample = {
            "germline": 4.0,
            "somatic": 8.0,
            "rnaseq": 2.0,
            "wgs": 12.0,
            "wes": 3.0,
        }

        base_hours = base_vcpu_hours_per_sample.get(pipeline_type, 4.0)
        coverage_factor = estimated_coverage / 30.0
        vcpu_hours = base_hours * sample_count * coverage_factor

        # Estimate duration assuming 16 vCPU instance average
        avg_vcpus = 16
        duration_hours = vcpu_hours / avg_vcpus

        # Cost per vCPU-hour by priority
        cost_per_vcpu_hour = {
            "urgent": 0.08,
            "high": 0.08,
            "normal": 0.03,
            "low": 0.015,
        }
        base_cost = cost_per_vcpu_hour.get(priority, 0.03)
        compute_cost = vcpu_hours * base_cost

        # Storage calculations
        if data_size_gb <= 0:
            data_size_gb = sample_count * 50.0
        storage_cost = data_size_gb * 0.023 / 4
        fsx_cost = data_size_gb * 0.14 / 4
        transfer_cost = data_size_gb * 0.10 * 0.09

        efficiency_multiplier = calculate_cost_with_efficiency(data_size_gb)
        adjusted_storage_cost = storage_cost * efficiency_multiplier if efficiency_multiplier > 0 else storage_cost

        # Priority multipliers
        priority_multiplier = {"urgent": 2.0, "high": 1.5, "normal": 1.0, "low": 0.6}
        multiplier = priority_multiplier.get(priority, 1.0)
        total_cost = (compute_cost + adjusted_storage_cost + fsx_cost + transfer_cost) * multiplier

        return CostEstimateResponse(
            estimated_cost_usd=round(total_cost, 2),
            compute_cost_usd=round(compute_cost * multiplier, 2),
            storage_cost_usd=round(adjusted_storage_cost + fsx_cost, 2),
            transfer_cost_usd=round(transfer_cost, 2),
            vcpu_hours=round(vcpu_hours, 1),
            estimated_duration_hours=round(duration_hours, 1),
            estimated_duration_minutes=int(duration_hours * 60),
            data_size_gb=round(data_size_gb, 1),
            efficiency_multiplier=round(efficiency_multiplier, 2),
            pipeline_type=pipeline_type,
            sample_count=sample_count,
            priority=priority,
            cost_breakdown={
                "compute": f"${compute_cost * multiplier:.2f}",
                "storage": f"${adjusted_storage_cost:.2f}",
                "fsx": f"${fsx_cost:.2f}",
                "transfer": f"${transfer_cost:.2f}",
            },
            notes=[
                "Costs are estimates based on typical workloads",
                f"Priority '{priority}' applies {multiplier}x multiplier",
                f"Storage efficiency multiplier: {efficiency_multiplier:.2f}x",
                "Actual costs depend on spot market and data complexity",
            ],
        )

    @router.post("/api/s3/discover-samples", response_model=S3DiscoveryResponse)
    async def discover_samples_from_s3(
        request: Request,
        bucket: str = Body(..., embed=True),
        prefix: str = Body(..., embed=True),
        current_user: Optional[Dict] = Depends(get_current_user),
    ):
        """Discover FASTQ samples from an S3 path."""
        samples = []
        yaml_content = None
        files_found = []
        all_keys_found = []

        LOGGER.info("S3 Discovery: Starting for bucket=%s, prefix=%s", bucket, prefix)

        try:
            session_kwargs = {"region_name": region}
            if profile:
                session_kwargs["profile_name"] = profile
            session = boto3.Session(**session_kwargs)
            s3_client = session.client("s3")

            normalized_prefix = prefix.strip()
            if normalized_prefix:
                normalized_prefix = normalized_prefix.lstrip("/")
                if not normalized_prefix.endswith("/"):
                    normalized_prefix += "/"

            paginator = s3_client.get_paginator("list_objects_v2")
            total_objects = 0

            for page in paginator.paginate(Bucket=bucket, Prefix=normalized_prefix):
                for obj in page.get("Contents", []):
                    total_objects += 1
                    key = obj["Key"]
                    filename = key.split("/")[-1]
                    all_keys_found.append(key)

                    if not filename:
                        continue

                    if filename.lower() == "daylily_work.yaml":
                        try:
                            response = s3_client.get_object(Bucket=bucket, Key=key)
                            yaml_content = response["Body"].read().decode("utf-8")
                        except Exception as e:
                            LOGGER.warning("Failed to read daylily_work.yaml: %s", str(e))

                    fastq_extensions = [".fastq", ".fq", ".fastq.gz", ".fq.gz", ".fastq.bz2", ".fq.bz2"]
                    if any(filename.lower().endswith(ext) for ext in fastq_extensions):
                        files_found.append({
                            "key": key,
                            "filename": filename,
                            "size": obj.get("Size", 0),
                        })

            # Parse samples from YAML if present
            if yaml_content:
                try:
                    yaml_data = yaml.safe_load(yaml_content)
                    if yaml_data and isinstance(yaml_data.get("samples"), list):
                        for sample in yaml_data["samples"]:
                            if isinstance(sample, dict):
                                samples.append({
                                    "sample_id": sample.get("sample_id") or sample.get("id") or sample.get("name", "unknown"),
                                    "r1_file": sample.get("r1_file") or sample.get("r1") or sample.get("fq1", ""),
                                    "r2_file": sample.get("r2_file") or sample.get("r2") or sample.get("fq2", ""),
                                    "status": "pending",
                                })
                except Exception as e:
                    LOGGER.warning("Failed to parse daylily_work.yaml: %s", str(e))

            # Auto-pair FASTQ files if no YAML samples
            if not samples and files_found:
                samples = _pair_fastq_files(files_found)

            return S3DiscoveryResponse(
                samples=samples,
                yaml_content=yaml_content,
                files_found=len(files_found),
                bucket=bucket,
                prefix=prefix,
                normalized_prefix=normalized_prefix,
                total_objects_scanned=total_objects,
            )

        except Exception as e:
            if "NoSuchBucket" in str(type(e).__name__) or "NoSuchBucket" in str(e):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"S3 bucket '{bucket}' not found")
            LOGGER.error("S3 Discovery failed: %s", str(e))
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to discover samples: {str(e)}")

    @router.post("/api/s3/validate-bucket", response_model=BucketValidationResponse)
    async def validate_s3_bucket(
        bucket: str = Body(..., embed=True),
        current_user: Optional[Dict] = Depends(get_current_user),
    ):
        """Validate an S3 bucket for Daylily use."""
        from daylib.s3_bucket_validator import S3BucketValidator

        try:
            validator = S3BucketValidator(region=region, profile=profile)
            result = validator.validate_bucket(bucket)

            instructions = None
            if not result.is_fully_configured:
                instructions = validator.get_setup_instructions(bucket, result, daylily_account_id="108782052779")

            return BucketValidationResponse(
                bucket=bucket,
                valid=result.is_valid,
                fully_configured=result.is_fully_configured,
                exists=result.exists,
                accessible=result.accessible,
                can_read=result.can_read,
                can_write=result.can_write,
                can_list=result.can_list,
                region=result.region,
                errors=result.errors,
                warnings=result.warnings,
                setup_instructions=instructions,
            )
        except Exception as e:
            LOGGER.error("S3 Validation failed for '%s': %s", bucket, str(e))
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to validate bucket: {str(e)}")

    @router.get("/api/s3/iam-policy/{bucket_name}")
    async def get_iam_policy_for_bucket(
        bucket_name: str,
        read_only: bool = False,
        current_user: Optional[Dict] = Depends(get_current_user),
    ):
        """Generate IAM policy for accessing a customer S3 bucket."""
        from daylib.s3_bucket_validator import S3BucketValidator

        validator = S3BucketValidator(region=region, profile=profile)
        policy = validator.generate_iam_policy_for_bucket(bucket_name, read_only=read_only)

        return {"bucket": bucket_name, "read_only": read_only, "policy": policy}

    @router.get("/api/s3/bucket-policy/{bucket_name}")
    async def get_bucket_policy_for_daylily(
        bucket_name: str,
        daylily_account_id: str = "108782052779",
        current_user: Optional[Dict] = Depends(get_current_user),
    ):
        """Generate S3 bucket policy for cross-account Daylily access."""
        from daylib.s3_bucket_validator import S3BucketValidator

        validator = S3BucketValidator(region=region, profile=profile)
        policy = validator.generate_customer_bucket_policy(bucket_name, daylily_account_id)

        return {
            "bucket": bucket_name,
            "daylily_account_id": daylily_account_id,
            "policy": policy,
            "apply_command": f"aws s3api put-bucket-policy --bucket {bucket_name} --policy file://bucket-policy.json",
        }

    return router


def _pair_fastq_files(files_found: List[Dict]) -> List[Dict]:
    """Pair R1/R2 FASTQ files into samples."""
    r1_patterns = [
        re.compile(r"^(.+?)[._](R1|r1)[._]?.*\.(fastq|fq)(\.gz|\.bz2)?$", re.IGNORECASE),
        re.compile(r"^(.+?)[._]1[._]?.*\.(fastq|fq)(\.gz|\.bz2)?$", re.IGNORECASE),
        re.compile(r"^(.+?)_S\d+_L\d+_R1_\d+\.(fastq|fq)(\.gz|\.bz2)?$", re.IGNORECASE),
    ]
    r2_patterns = [
        re.compile(r"^(.+?)[._](R2|r2)[._]?.*\.(fastq|fq)(\.gz|\.bz2)?$", re.IGNORECASE),
        re.compile(r"^(.+?)[._]2[._]?.*\.(fastq|fq)(\.gz|\.bz2)?$", re.IGNORECASE),
        re.compile(r"^(.+?)_S\d+_L\d+_R2_\d+\.(fastq|fq)(\.gz|\.bz2)?$", re.IGNORECASE),
    ]

    r1_files = {}
    r2_files = {}

    for f in files_found:
        filename = f["filename"]
        matched = False

        for pattern in r1_patterns:
            match = pattern.match(filename)
            if match:
                r1_files[match.group(1)] = f["key"]
                matched = True
                break

        if not matched:
            for pattern in r2_patterns:
                match = pattern.match(filename)
                if match:
                    r2_files[match.group(1)] = f["key"]
                    break

    samples = []
    for sample_name in sorted(set(r1_files.keys()) | set(r2_files.keys())):
        samples.append({
            "sample_id": sample_name,
            "r1_file": r1_files.get(sample_name, ""),
            "r2_file": r2_files.get(sample_name, ""),
            "status": "pending",
        })

    return samples

