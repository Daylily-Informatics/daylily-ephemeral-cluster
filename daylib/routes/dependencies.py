"""Shared dependencies, Pydantic models, and utility functions for route modules.

This module contains:
- Pydantic request/response models used across multiple routes
- Utility functions for file handling and cost calculation
- Common helper functions for template rendering
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field

from daylib.workset_state_db import WorksetPriority, WorksetState

LOGGER = logging.getLogger("daylily.routes")


# ========== Helper Functions ==========


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size_float: float = float(size_bytes)
    while size_float >= 1024 and i < len(units) - 1:
        size_float /= 1024
        i += 1
    return f"{size_float:.1f} {units[i]}"


def get_file_icon(filename: str) -> str:
    """Get Font Awesome icon name for file type."""
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    icon_map = {
        "fastq": "dna",
        "fq": "dna",
        "gz": "file-archive",
        "zip": "file-archive",
        "tar": "file-archive",
        "bam": "dna",
        "sam": "dna",
        "vcf": "dna",
        "bed": "dna",
        "fasta": "dna",
        "fa": "dna",
        "yaml": "file-code",
        "yml": "file-code",
        "json": "file-code",
        "csv": "file-csv",
        "tsv": "file-csv",
        "txt": "file-alt",
        "log": "file-alt",
        "pdf": "file-pdf",
        "html": "file-code",
        "md": "file-alt",
    }
    return icon_map.get(ext, "file")


def calculate_cost_with_efficiency(total_size_gb: float) -> float:
    """Calculate cost using efficiency formula.
    
    Formula: (total_size / (total_size - (total_size * 0.98)))
    This represents the cost multiplier based on data efficiency.
    The 0.98 factor represents 98% efficiency, so the denominator is 2% of total_size.
    """
    if total_size_gb <= 0:
        return 0.0
    denominator = total_size_gb - (total_size_gb * 0.98)
    if denominator <= 0:
        return 0.0
    return total_size_gb / denominator


def convert_customer_for_template(customer_config):
    """Convert CustomerConfig with Decimal fields to template-friendly object.

    DynamoDB returns Decimal types which can't be used in Jinja2 template math operations.
    This converts them to native Python types.
    """
    if not customer_config:
        return None

    class TemplateCustomer:
        def __init__(self, config):
            self.customer_id = config.customer_id
            self.customer_name = config.customer_name
            self.email = config.email
            self.s3_bucket = config.s3_bucket
            self.max_concurrent_worksets = (
                int(config.max_concurrent_worksets) if config.max_concurrent_worksets else 10
            )
            self.max_storage_gb = float(config.max_storage_gb) if config.max_storage_gb else 500
            self.billing_account_id = config.billing_account_id
            self.cost_center = config.cost_center

    return TemplateCustomer(customer_config)


def verify_workset_ownership(workset: Dict[str, Any], customer_id: str) -> bool:
    """Check if a workset belongs to a customer.

    Ownership is determined by the customer_id field in the workset record.
    This replaces the legacy check that compared workset.bucket to customer.s3_bucket.
    """
    if not workset or not customer_id:
        return False

    # Primary check: customer_id field (authoritative)
    ws_customer_id = workset.get("customer_id")
    if ws_customer_id:
        return bool(ws_customer_id == customer_id)

    # Fallback: check metadata.submitted_by for older worksets
    metadata = workset.get("metadata", {})
    if isinstance(metadata, dict):
        submitted_by = metadata.get("submitted_by")
        if submitted_by:
            return bool(submitted_by == customer_id)

    LOGGER.warning(
        "Workset %s has no customer_id field - ownership check failed",
        workset.get("workset_id", "unknown"),
    )
    return False


# ========== Pydantic Models for Workset API ==========


class WorksetCreate(BaseModel):
    """Request model for creating a workset."""

    workset_id: str = Field(..., description="Unique workset identifier")
    bucket: str = Field(..., description="S3 bucket name")
    prefix: str = Field(..., description="S3 prefix for workset files")
    priority: WorksetPriority = Field(WorksetPriority.NORMAL, description="Execution priority")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class WorksetResponse(BaseModel):
    """Response model for workset data."""

    workset_id: str
    state: str
    priority: str
    bucket: str
    prefix: str
    created_at: str
    updated_at: str
    cluster_name: Optional[str] = None
    error_details: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class WorksetStateUpdate(BaseModel):
    """Request model for updating workset state."""

    state: WorksetState
    reason: str
    error_details: Optional[str] = None
    cluster_name: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class QueueStats(BaseModel):
    """Queue statistics response."""

    queue_depth: Dict[str, int]
    total_worksets: int
    ready_worksets: int
    in_progress_worksets: int
    error_worksets: int


class SchedulingStats(BaseModel):
    """Scheduling statistics response."""

    total_clusters: int
    total_vcpu_capacity: int
    total_vcpus_used: int
    vcpu_utilization_percent: float
    total_active_worksets: int
    queue_depth: Dict[str, int]


# ========== Pydantic Models for Customer API ==========


class CustomerCreate(BaseModel):
    """Request model for creating a customer."""

    customer_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    max_concurrent_worksets: int = Field(5, ge=1, le=50)
    max_storage_gb: int = Field(1000, ge=100, le=10000)
    billing_account_id: Optional[str] = None
    cost_center: Optional[str] = None


class CustomerResponse(BaseModel):
    """Response model for customer data."""

    customer_id: str
    customer_name: str
    email: str
    s3_bucket: str
    max_concurrent_worksets: int
    max_storage_gb: int
    billing_account_id: Optional[str] = None
    cost_center: Optional[str] = None


# ========== Pydantic Models for Validation and Utilities ==========


class WorksetValidationResponse(BaseModel):
    """Response model for workset validation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    estimated_cost_usd: Optional[float] = None
    estimated_duration_minutes: Optional[int] = None
    estimated_vcpu_hours: Optional[float] = None
    estimated_storage_gb: Optional[float] = None


class WorkYamlGenerateRequest(BaseModel):
    """Request model for generating daylily_work.yaml."""

    samples: List[Dict[str, str]]
    reference_genome: str
    pipeline: str = "germline"
    priority: str = "normal"
    max_retries: int = 3
    estimated_coverage: float = 30.0


# ========== Pydantic Models for Portal Auth ==========


class ChangePasswordRequest(BaseModel):
    """Request model for changing the current user's password."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class APITokenCreateRequest(BaseModel):
    """Request model for creating a new API token from the portal."""

    name: str = Field(..., min_length=1, max_length=100)
    # 0 means "no automatic expiry" (token is long-lived until revoked)
    expiry_days: int = Field(0, ge=0, le=3650)


# ========== Portal File Registration Models ==========


class PortalFileAutoRegisterRequest(BaseModel):
    """Request model for auto-registering discovered files from the portal.

    Notes:
    - `customer_id` is intentionally omitted; the server derives it from the
      authenticated portal session to prevent cross-customer registration.
    - Either `bucket_id` (preferred) or `bucket_name` must be provided.
    """

    bucket_id: Optional[str] = Field(None, description="Linked bucket ID")
    bucket_name: Optional[str] = Field(None, description="S3 bucket name (fallback if bucket_id not provided)")
    prefix: str = Field("", description="Prefix to scan")
    file_formats: Optional[List[str]] = Field(None, description="Filter by formats (e.g. fastq,bam,vcf)")
    selected_keys: Optional[List[str]] = Field(
        None,
        description="Optional list of S3 object keys to register (subset of discovered files)",
    )
    max_files: int = Field(1000, ge=1, le=10000, description="Maximum files to scan in the bucket")
    biosample_id: str = Field(..., min_length=1, description="Biosample ID to apply to all registered files")
    subject_id: str = Field(..., min_length=1, description="Subject ID to apply to all registered files")
    sequencing_platform: str = Field(
        "NOVASEQX",
        description="Sequencing platform (prefer SequencingPlatform enum values like NOVASEQX, NOVASEQ6000)",
    )


class PortalFileAutoRegisterResponse(BaseModel):
    """Response model for portal auto-registration."""

    registered_count: int
    skipped_count: int
    errors: List[str]
    missing_selected_keys: Optional[List[str]] = None

