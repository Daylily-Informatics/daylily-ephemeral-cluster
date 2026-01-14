"""FastAPI web interface for workset monitoring and management.

Provides REST API and web dashboard for workset operations.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, EmailStr

from daylib.workset_state_db import ErrorCategory, WorksetPriority, WorksetState, WorksetStateDB
from daylib.workset_scheduler import WorksetScheduler

# Optional imports for authentication
try:
    from daylib.workset_auth import CognitoAuth, create_auth_dependency
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    CognitoAuth = None
    create_auth_dependency = None

from daylib.workset_customer import CustomerManager, CustomerConfig
from daylib.workset_validation import WorksetValidator

LOGGER = logging.getLogger("daylily.workset_api")


# Helper functions for file management
def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.1f} {units[i]}"


def _get_file_icon(filename: str) -> str:
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


def _convert_customer_for_template(customer_config):
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
            self.max_concurrent_worksets = int(config.max_concurrent_worksets) if config.max_concurrent_worksets else 10
            self.max_storage_gb = float(config.max_storage_gb) if config.max_storage_gb else 500
            self.billing_account_id = config.billing_account_id
            self.cost_center = config.cost_center

    return TemplateCustomer(customer_config)


# Pydantic models for API
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


# New models for customer portal
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


def create_app(
    state_db: WorksetStateDB,
    scheduler: Optional[WorksetScheduler] = None,
    cognito_auth: Optional[CognitoAuth] = None,
    customer_manager: Optional[CustomerManager] = None,
    validator: Optional[WorksetValidator] = None,
    enable_auth: bool = False,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        state_db: Workset state database
        scheduler: Optional workset scheduler
        cognito_auth: Optional Cognito authentication
        customer_manager: Optional customer manager
        validator: Optional workset validator
        enable_auth: Enable authentication (requires cognito_auth)

    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="Daylily Workset Monitor API",
        description="REST API for workset monitoring and management with multi-tenant support",
        version="2.0.0",
    )

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Setup authentication dependency if enabled
    if enable_auth:
        if not AUTH_AVAILABLE:
            LOGGER.error(
                "Authentication requested but python-jose not installed. "
                "Install with: pip install 'python-jose[cryptography]'"
            )
            raise ImportError(
                "Authentication requires python-jose. "
                "Install with: pip install 'python-jose[cryptography]' "
                "or set enable_auth=False"
            )
        if not cognito_auth:
            raise ValueError("enable_auth=True requires cognito_auth parameter")
        get_current_user = create_auth_dependency(cognito_auth)
        LOGGER.info("Authentication enabled - API endpoints will require valid JWT tokens")
    else:
        # Create a dummy dependency that always returns None
        async def get_current_user() -> Optional[Dict]:
            return None
        LOGGER.info("Authentication disabled - API endpoints will not require authentication")
    
    @app.get("/", tags=["health"])
    async def root():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "daylily-workset-monitor",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    
    @app.post("/worksets", response_model=WorksetResponse, status_code=status.HTTP_201_CREATED, tags=["worksets"])
    async def create_workset(workset: WorksetCreate):
        """Register a new workset."""
        success = state_db.register_workset(
            workset_id=workset.workset_id,
            bucket=workset.bucket,
            prefix=workset.prefix,
            priority=workset.priority,
            metadata=workset.metadata,
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workset {workset.workset_id} already exists",
            )
        
        # Retrieve the created workset
        created = state_db.get_workset(workset.workset_id)
        if not created:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created workset",
            )
        
        return WorksetResponse(**created)
    
    @app.get("/worksets/{workset_id}", response_model=WorksetResponse, tags=["worksets"])
    async def get_workset(workset_id: str):
        """Get workset details."""
        workset = state_db.get_workset(workset_id)
        if not workset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workset {workset_id} not found",
            )
        
        return WorksetResponse(**workset)
    
    @app.get("/worksets", response_model=List[WorksetResponse], tags=["worksets"])
    async def list_worksets(
        state: Optional[WorksetState] = Query(None, description="Filter by state"),
        priority: Optional[WorksetPriority] = Query(None, description="Filter by priority"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    ):
        """List worksets with optional filters."""
        if state:
            worksets = state_db.list_worksets_by_state(state, priority=priority, limit=limit)
        else:
            # Get all states
            worksets = []
            for ws_state in WorksetState:
                batch = state_db.list_worksets_by_state(ws_state, priority=priority, limit=limit)
                worksets.extend(batch)
                if len(worksets) >= limit:
                    break
            worksets = worksets[:limit]
        
        return [WorksetResponse(**w) for w in worksets]

    @app.put("/worksets/{workset_id}/state", response_model=WorksetResponse, tags=["worksets"])
    async def update_workset_state(workset_id: str, update: WorksetStateUpdate):
        """Update workset state."""
        # Verify workset exists
        workset = state_db.get_workset(workset_id)
        if not workset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workset {workset_id} not found",
            )

        state_db.update_state(
            workset_id=workset_id,
            new_state=update.state,
            reason=update.reason,
            error_details=update.error_details,
            cluster_name=update.cluster_name,
            metrics=update.metrics,
        )

        # Return updated workset
        updated = state_db.get_workset(workset_id)
        return WorksetResponse(**updated)

    @app.post("/worksets/{workset_id}/lock", tags=["worksets"])
    async def acquire_workset_lock(workset_id: str, owner_id: str = Query(..., description="Lock owner ID")):
        """Acquire lock on a workset."""
        success = state_db.acquire_lock(workset_id, owner_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Failed to acquire lock on workset {workset_id}",
            )

        return {"status": "locked", "workset_id": workset_id, "owner_id": owner_id}

    @app.delete("/worksets/{workset_id}/lock", tags=["worksets"])
    async def release_workset_lock(workset_id: str, owner_id: str = Query(..., description="Lock owner ID")):
        """Release lock on a workset."""
        success = state_db.release_lock(workset_id, owner_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Failed to release lock on workset {workset_id} (not owner)",
            )

        return {"status": "unlocked", "workset_id": workset_id}

    @app.get("/queue/stats", response_model=QueueStats, tags=["monitoring"])
    async def get_queue_stats():
        """Get queue statistics."""
        queue_depth = state_db.get_queue_depth()

        return QueueStats(
            queue_depth=queue_depth,
            total_worksets=sum(queue_depth.values()),
            ready_worksets=queue_depth.get(WorksetState.READY.value, 0),
            in_progress_worksets=queue_depth.get(WorksetState.IN_PROGRESS.value, 0),
            error_worksets=queue_depth.get(WorksetState.ERROR.value, 0),
        )

    @app.get("/scheduler/stats", response_model=SchedulingStats, tags=["monitoring"])
    async def get_scheduler_stats():
        """Get scheduler statistics."""
        if not scheduler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Scheduler not configured",
            )

        stats = scheduler.get_scheduling_stats()
        return SchedulingStats(**stats)

    @app.get("/worksets/next", response_model=Optional[WorksetResponse], tags=["scheduling"])
    async def get_next_workset():
        """Get the next workset to execute based on priority."""
        if not scheduler:
            # Fallback to simple priority-based selection
            worksets = state_db.get_ready_worksets_prioritized(limit=1)
            if not worksets:
                return None
            return WorksetResponse(**worksets[0])

        next_workset = scheduler.get_next_workset()
        if not next_workset:
            return None

        return WorksetResponse(**next_workset)

    # ========== Customer Management Endpoints ==========

    if customer_manager:
        @app.post("/customers", response_model=CustomerResponse, tags=["customers"])
        async def create_customer(
            customer: CustomerCreate,
            current_user: Optional[Dict] = Depends(get_current_user),
        ):
            """Create a new customer with provisioned resources."""
            config = customer_manager.onboard_customer(
                customer_name=customer.customer_name,
                email=customer.email,
                max_concurrent_worksets=customer.max_concurrent_worksets,
                max_storage_gb=customer.max_storage_gb,
                billing_account_id=customer.billing_account_id,
                cost_center=customer.cost_center,
            )

            return CustomerResponse(
                customer_id=config.customer_id,
                customer_name=config.customer_name,
                email=config.email,
                s3_bucket=config.s3_bucket,
                max_concurrent_worksets=config.max_concurrent_worksets,
                max_storage_gb=config.max_storage_gb,
                billing_account_id=config.billing_account_id,
                cost_center=config.cost_center,
            )

        @app.get("/customers/{customer_id}", response_model=CustomerResponse, tags=["customers"])
        async def get_customer(
            customer_id: str,
            current_user: Optional[Dict] = Depends(get_current_user),
        ):
            """Get customer details."""
            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            return CustomerResponse(
                customer_id=config.customer_id,
                customer_name=config.customer_name,
                email=config.email,
                s3_bucket=config.s3_bucket,
                max_concurrent_worksets=config.max_concurrent_worksets,
                max_storage_gb=config.max_storage_gb,
                billing_account_id=config.billing_account_id,
                cost_center=config.cost_center,
            )

        @app.get("/customers", response_model=List[CustomerResponse], tags=["customers"])
        async def list_customers(
            current_user: Optional[Dict] = Depends(get_current_user),
        ):
            """List all customers."""
            configs = customer_manager.list_customers()

            return [
                CustomerResponse(
                    customer_id=c.customer_id,
                    customer_name=c.customer_name,
                    email=c.email,
                    s3_bucket=c.s3_bucket,
                    max_concurrent_worksets=c.max_concurrent_worksets,
                    max_storage_gb=c.max_storage_gb,
                    billing_account_id=c.billing_account_id,
                    cost_center=c.cost_center,
                )
                for c in configs
            ]

        @app.get("/customers/{customer_id}/usage", tags=["customers"])
        async def get_customer_usage(
            customer_id: str,
            current_user: Optional[Dict] = Depends(get_current_user),
        ):
            """Get customer resource usage."""
            usage = customer_manager.get_customer_usage(customer_id)
            if not usage:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            return usage

        # ========== File Management Endpoints ==========

        @app.get("/api/customers/{customer_id}/files", tags=["files"])
        async def list_customer_files(
            customer_id: str,
            prefix: str = "",
        ):
            """List files in customer's S3 bucket.

            Note: This endpoint does not require authentication to support portal usage.
            In production, you may want to add authentication or rate limiting.
            """
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            try:
                s3 = boto3.client("s3")
                response = s3.list_objects_v2(
                    Bucket=config.s3_bucket,
                    Prefix=prefix,
                    Delimiter="/",
                )

                files = []

                # Add folders (CommonPrefixes)
                for cp in response.get("CommonPrefixes", []):
                    folder_path = cp["Prefix"]
                    folder_name = folder_path.rstrip("/").split("/")[-1]
                    files.append({
                        "key": folder_path,
                        "name": folder_name,
                        "type": "folder",
                        "size": 0,
                        "size_formatted": "-",
                        "modified": None,
                        "icon": "folder",
                    })

                # Add files (Contents)
                for obj in response.get("Contents", []):
                    key = obj["Key"]
                    # Skip the prefix itself
                    if key == prefix:
                        continue
                    name = key.split("/")[-1]
                    if not name:
                        continue
                    size = obj["Size"]
                    files.append({
                        "key": key,
                        "name": name,
                        "type": "file",
                        "size": size,
                        "size_formatted": _format_file_size(size),
                        "modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
                        "icon": _get_file_icon(name),
                    })

                return {"files": files, "prefix": prefix, "bucket": config.s3_bucket}

            except Exception as e:
                LOGGER.error("Failed to list files: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        @app.post("/api/customers/{customer_id}/files/upload", tags=["files"])
        async def upload_file(
            customer_id: str,
            file: UploadFile = File(...),
            prefix: str = Form(""),
        ):
            """Upload a file to customer's S3 bucket.

            This endpoint proxies the upload through the server to avoid S3 CORS issues.
            For large files in production, consider configuring S3 CORS and using presigned URLs.
            """
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            try:
                s3 = boto3.client("s3")
                # Build the full key with prefix
                key = f"{prefix}{file.filename}" if prefix else file.filename

                # Read file content and upload to S3
                content = await file.read()
                s3.put_object(
                    Bucket=config.s3_bucket,
                    Key=key,
                    Body=content,
                    ContentType=file.content_type or "application/octet-stream",
                )

                LOGGER.info(f"Uploaded {key} to bucket {config.s3_bucket}")
                return {"success": True, "key": key, "bucket": config.s3_bucket}

            except Exception as e:
                LOGGER.error("Failed to upload file: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        @app.post("/api/customers/{customer_id}/files/create-folder", tags=["files"])
        async def create_folder(
            customer_id: str,
            folder_path: str = Body(..., embed=True),
        ):
            """Create a folder in customer's S3 bucket.

            Note: This endpoint does not require authentication to support portal usage.
            In production, you may want to add authentication or rate limiting.
            """
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            try:
                s3 = boto3.client("s3")
                # S3 folders are just empty objects with trailing slash
                folder_key = folder_path.rstrip("/") + "/"
                s3.put_object(Bucket=config.s3_bucket, Key=folder_key, Body=b"")
                LOGGER.info(f"Created folder {folder_key} in bucket {config.s3_bucket}")
                return {"success": True, "folder": folder_key}

            except Exception as e:
                LOGGER.error("Failed to create folder: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        @app.get("/api/customers/{customer_id}/files/{file_key:path}/preview", tags=["files"])
        async def preview_file(
            customer_id: str,
            file_key: str,
            lines: int = 20,
        ):
            """Preview file contents.

            For compressed files (.gz, .tgz, .tar.gz), decompresses and shows first N lines.
            For text files, shows first N lines directly.
            For binary files, returns a message indicating preview is not available.
            """
            import gzip
            import tarfile
            import io

            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            try:
                s3 = boto3.client("s3")

                # Get file metadata first
                head = s3.head_object(Bucket=config.s3_bucket, Key=file_key)
                file_size = head.get("ContentLength", 0)
                content_type = head.get("ContentType", "application/octet-stream")

                # Determine file type from extension
                file_lower = file_key.lower()
                is_gzip = file_lower.endswith(".gz") or file_lower.endswith(".gzip")
                is_tar_gz = file_lower.endswith(".tar.gz") or file_lower.endswith(".tgz")
                is_zip = file_lower.endswith(".zip")

                # Text-like extensions
                text_extensions = {
                    ".txt", ".log", ".csv", ".tsv", ".json", ".xml", ".html", ".htm",
                    ".yaml", ".yml", ".md", ".rst", ".py", ".js", ".ts", ".sh", ".bash",
                    ".r", ".R", ".pl", ".rb", ".java", ".c", ".cpp", ".h", ".hpp",
                    ".fastq", ".fq", ".fasta", ".fa", ".sam", ".vcf", ".bed", ".gff", ".gtf",
                }

                # Check if it's a text file (or compressed text)
                base_name = file_key
                if is_gzip and not is_tar_gz:
                    base_name = file_key[:-3] if file_lower.endswith(".gz") else file_key[:-5]

                ext = "." + base_name.split(".")[-1] if "." in base_name else ""
                is_text = ext.lower() in text_extensions or content_type.startswith("text/")

                # For very large files, limit how much we download
                max_download = 10 * 1024 * 1024  # 10MB max to download for preview

                # Get file content (limited range for large files)
                if file_size > max_download:
                    response = s3.get_object(
                        Bucket=config.s3_bucket,
                        Key=file_key,
                        Range=f"bytes=0-{max_download}"
                    )
                else:
                    response = s3.get_object(Bucket=config.s3_bucket, Key=file_key)

                body = response["Body"].read()
                preview_lines = []
                file_type = "text"

                if is_tar_gz:
                    # Handle .tar.gz or .tgz - list contents and show first file preview
                    file_type = "tar.gz"
                    try:
                        with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tar:
                            members = tar.getnames()[:20]  # First 20 entries
                            preview_lines.append(f"=== Archive contents ({len(tar.getnames())} files) ===")
                            for m in members:
                                preview_lines.append(m)
                            if len(tar.getnames()) > 20:
                                preview_lines.append(f"... and {len(tar.getnames()) - 20} more files")
                    except Exception as e:
                        preview_lines = [f"Error reading tar.gz: {str(e)}"]

                elif is_gzip:
                    # Handle .gz files - decompress and show content
                    file_type = "gzip"
                    try:
                        decompressed = gzip.decompress(body)
                        text = decompressed.decode("utf-8", errors="replace")
                        preview_lines = text.split("\n")[:lines]
                    except Exception as e:
                        preview_lines = [f"Error decompressing: {str(e)}"]

                elif is_zip:
                    # Handle .zip files - list contents
                    import zipfile
                    file_type = "zip"
                    try:
                        with zipfile.ZipFile(io.BytesIO(body)) as zf:
                            names = zf.namelist()[:20]
                            preview_lines.append(f"=== Archive contents ({len(zf.namelist())} files) ===")
                            for name in names:
                                preview_lines.append(name)
                            if len(zf.namelist()) > 20:
                                preview_lines.append(f"... and {len(zf.namelist()) - 20} more files")
                    except Exception as e:
                        preview_lines = [f"Error reading zip: {str(e)}"]

                elif is_text or file_size < 1024 * 1024:  # Try text for small files
                    # Try to decode as text
                    try:
                        text = body.decode("utf-8", errors="replace")
                        preview_lines = text.split("\n")[:lines]
                    except Exception:
                        file_type = "binary"
                        preview_lines = ["[Binary file - preview not available]"]
                else:
                    file_type = "binary"
                    preview_lines = ["[Binary file - preview not available]"]

                return {
                    "filename": file_key.split("/")[-1],
                    "file_type": file_type,
                    "size": file_size,
                    "lines": preview_lines,
                    "total_lines": len(preview_lines),
                    "truncated": len(preview_lines) >= lines,
                }

            except s3.exceptions.NoSuchKey:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {file_key}",
                )
            except Exception as e:
                LOGGER.error("Failed to preview file: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        @app.get("/api/customers/{customer_id}/files/{file_key:path}/download-url", tags=["files"])
        async def get_download_url(
            customer_id: str,
            file_key: str,
        ):
            """Get presigned URL for file download.

            Note: This endpoint does not require authentication to support portal usage.
            In production, you may want to add authentication or rate limiting.
            """
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            try:
                s3 = boto3.client("s3")
                url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": config.s3_bucket, "Key": file_key},
                    ExpiresIn=3600,
                )
                return {"url": url}

            except Exception as e:
                LOGGER.error("Failed to generate download URL: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        @app.delete("/api/customers/{customer_id}/files/{file_key:path}", tags=["files"])
        async def delete_file(
            customer_id: str,
            file_key: str,
        ):
            """Delete a file from customer's S3 bucket.

            Note: This endpoint does not require authentication to support portal usage.
            In production, you may want to add authentication or rate limiting.
            """
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            try:
                s3 = boto3.client("s3")
                s3.delete_object(Bucket=config.s3_bucket, Key=file_key)
                return {"success": True, "deleted": file_key}

            except Exception as e:
                LOGGER.error("Failed to delete file: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        # ========== Customer Workset Endpoints ==========

        @app.get("/api/customers/{customer_id}/worksets", tags=["customer-worksets"])
        async def list_customer_worksets(
            customer_id: str,
            state: Optional[str] = None,
            limit: int = 100,
        ):
            """List worksets for a customer.

            Filters worksets by the customer's S3 bucket.
            """
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            # Get all worksets and filter by customer's bucket
            all_worksets = []
            if state:
                try:
                    ws_state = WorksetState(state)
                    all_worksets = state_db.list_worksets_by_state(ws_state, limit=limit)
                except ValueError:
                    all_worksets = state_db.list_worksets_by_state(None, limit=limit)
            else:
                # Get worksets from all states
                for ws_state in WorksetState:
                    batch = state_db.list_worksets_by_state(ws_state, limit=limit)
                    all_worksets.extend(batch)

            # Filter to only this customer's worksets (by bucket)
            customer_worksets = [
                w for w in all_worksets
                if w.get("bucket") == config.s3_bucket
            ]

            return {"worksets": customer_worksets[:limit]}

        @app.get("/api/customers/{customer_id}/worksets/{workset_id}", tags=["customer-worksets"])
        async def get_customer_workset(
            customer_id: str,
            workset_id: str,
        ):
            """Get a specific workset for a customer."""
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            workset = state_db.get_workset(workset_id)
            if not workset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workset {workset_id} not found",
                )

            # Verify workset belongs to this customer
            if workset.get("bucket") != config.s3_bucket:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            return workset

        @app.post("/api/customers/{customer_id}/worksets", tags=["customer-worksets"])
        async def create_customer_workset(
            customer_id: str,
            workset_name: str = Body(..., embed=True),
            pipeline_type: str = Body(..., embed=True),
            reference_genome: str = Body(..., embed=True),
            s3_prefix: str = Body("", embed=True),
            priority: str = Body("normal", embed=True),
            notification_email: Optional[str] = Body(None, embed=True),
            enable_qc: bool = Body(True, embed=True),
            archive_results: bool = Body(True, embed=True),
            s3_bucket: Optional[str] = Body(None, embed=True),
        ):
            """Create a new workset for a customer from the portal form."""
            import uuid

            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            # Generate a unique workset ID from the name
            safe_name = workset_name.replace(" ", "-").lower()[:30]
            workset_id = f"{safe_name}-{uuid.uuid4().hex[:8]}"

            # Use customer's bucket if not provided
            bucket = s3_bucket or config.s3_bucket
            prefix = s3_prefix or f"worksets/{workset_id}/"

            try:
                ws_priority = WorksetPriority(priority)
            except ValueError:
                ws_priority = WorksetPriority.NORMAL

            # Store additional metadata from the form
            metadata = {
                "workset_name": workset_name,
                "pipeline_type": pipeline_type,
                "reference_genome": reference_genome,
                "notification_email": notification_email,
                "enable_qc": enable_qc,
                "archive_results": archive_results,
                "submitted_by": customer_id,
            }

            success = state_db.register_workset(
                workset_id=workset_id,
                bucket=bucket,
                prefix=prefix,
                priority=ws_priority,
                metadata=metadata,
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Workset {workset_id} already exists",
                )

            created = state_db.get_workset(workset_id)
            return created

        @app.post("/api/customers/{customer_id}/worksets/{workset_id}/cancel", tags=["customer-worksets"])
        async def cancel_customer_workset(
            customer_id: str,
            workset_id: str,
        ):
            """Cancel a customer's workset."""
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            workset = state_db.get_workset(workset_id)
            if not workset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workset {workset_id} not found",
                )

            if workset.get("bucket") != config.s3_bucket:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            state_db.update_state(workset_id, WorksetState.CANCELLED, "Cancelled by user")
            updated = state_db.get_workset(workset_id)
            return updated

        @app.post("/api/customers/{customer_id}/worksets/{workset_id}/retry", tags=["customer-worksets"])
        async def retry_customer_workset(
            customer_id: str,
            workset_id: str,
        ):
            """Retry a failed customer workset."""
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            workset = state_db.get_workset(workset_id)
            if not workset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workset {workset_id} not found",
                )

            if workset.get("bucket") != config.s3_bucket:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            # Reset to pending state for retry
            state_db.update_state(workset_id, WorksetState.PENDING, "Retry requested by user")
            updated = state_db.get_workset(workset_id)
            return updated

        @app.get("/api/customers/{customer_id}/worksets/{workset_id}/logs", tags=["customer-worksets"])
        async def get_customer_workset_logs(
            customer_id: str,
            workset_id: str,
        ):
            """Get logs for a customer's workset."""
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            workset = state_db.get_workset(workset_id)
            if not workset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workset {workset_id} not found",
                )

            if workset.get("bucket") != config.s3_bucket:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            # Return workset history as logs
            history = workset.get("history", [])
            return {"logs": history, "workset_id": workset_id}

    # ========== Workset Validation Endpoints ==========

    if validator:
        @app.post("/worksets/validate", response_model=WorksetValidationResponse, tags=["validation"])
        async def validate_workset(
            bucket: str = Query(..., description="S3 bucket name"),
            prefix: str = Query(..., description="S3 prefix"),
            dry_run: bool = Query(False, description="Dry-run mode"),
            current_user: Optional[Dict] = Depends(get_current_user),
        ):
            """Validate a workset configuration."""
            result = validator.validate_workset(bucket, prefix, dry_run)

            return WorksetValidationResponse(
                is_valid=result.is_valid,
                errors=result.errors,
                warnings=result.warnings,
                estimated_cost_usd=result.estimated_cost_usd,
                estimated_duration_minutes=result.estimated_duration_minutes,
                estimated_vcpu_hours=result.estimated_vcpu_hours,
                estimated_storage_gb=result.estimated_storage_gb,
            )

    # ========== YAML Generator Endpoint ==========

    @app.post("/worksets/generate-yaml", tags=["utilities"])
    async def generate_work_yaml(
        request: WorkYamlGenerateRequest,
        current_user: Optional[Dict] = Depends(get_current_user),
    ):
        """Generate daylily_work.yaml from form data."""
        import yaml

        work_config = {
            "samples": request.samples,
            "reference_genome": request.reference_genome,
            "pipeline": request.pipeline,
            "priority": request.priority,
            "max_retries": request.max_retries,
            "estimated_coverage": request.estimated_coverage,
        }

        yaml_content = yaml.dump(work_config, default_flow_style=False, sort_keys=False)

        return {
            "yaml_content": yaml_content,
            "config": work_config,
        }

    # ========== Customer Portal Routes ==========

    # Setup templates directory
    templates_dir = Path(__file__).parent.parent / "templates"
    static_dir = Path(__file__).parent.parent / "static"

    if templates_dir.exists():
        templates = Jinja2Templates(directory=str(templates_dir))

        # Mount static files
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        def get_template_context(request: Request, **kwargs) -> Dict[str, Any]:
            """Build common template context."""
            context = {
                "request": request,
                "auth_enabled": enable_auth,
                "current_year": datetime.now().year,
                **kwargs,
            }
            # If customer is passed, also set customer_id for convenience
            if "customer" in kwargs and kwargs["customer"]:
                context["customer_id"] = kwargs["customer"].customer_id
            return context

        @app.get("/portal", response_class=HTMLResponse, tags=["portal"])
        async def portal_dashboard(request: Request):
            """Customer portal dashboard."""
            # Get customer from session/auth (simplified for now)
            customer = None
            worksets = []
            stats = {
                "active_worksets": 0,
                "completed_worksets": 0,
                "storage_used_gb": 0,
                "storage_percent": 0,
                "max_storage_gb": 500,
                "cost_this_month": 0,
            }

            if customer_manager:
                customers = customer_manager.list_customers()
                if customers:
                    customer_raw = customers[0]  # Demo: use first customer
                    customer = _convert_customer_for_template(customer_raw)
                    customer_id = customer_raw.customer_id

                    # Get worksets for this customer
                    all_worksets = []
                    for ws_state in WorksetState:
                        batch = state_db.list_worksets_by_state(ws_state, limit=100)
                        all_worksets.extend(batch)
                    worksets = all_worksets[:10]

                    # Calculate stats
                    stats["active_worksets"] = len([w for w in all_worksets if w.get("state") == "in_progress"])
                    stats["completed_worksets"] = len([w for w in all_worksets if w.get("state") == "completed"])

            return templates.TemplateResponse(
                request,
                "dashboard.html",
                get_template_context(
                    request,
                    customer=customer,
                    worksets=worksets,
                    stats=stats,
                    active_page="dashboard",
                ),
            )

        @app.get("/portal/login", response_class=HTMLResponse, tags=["portal"])
        async def portal_login(request: Request, error: Optional[str] = None, success: Optional[str] = None):
            """Login page."""
            return templates.TemplateResponse(
                request,
                "auth/login.html",
                get_template_context(request, error=error, success=success),
            )

        @app.post("/portal/login", tags=["portal"])
        async def portal_login_submit(
            request: Request,
            email: str = Form(...),
            password: str = Form(...),
        ):
            """Handle login form submission."""
            # For now, just redirect to dashboard (real auth would validate with Cognito)
            # In production, you would:
            # 1. Call cognito_auth.authenticate(email, password)
            # 2. Set session cookie with JWT token
            # 3. Redirect to dashboard

            # Simplified: just redirect to dashboard for demo purposes
            # TODO: Implement actual Cognito authentication
            return RedirectResponse(url="/portal/", status_code=302)

        @app.get("/portal/register", response_class=HTMLResponse, tags=["portal"])
        async def portal_register(request: Request, error: Optional[str] = None, success: Optional[str] = None):
            """Registration page."""
            return templates.TemplateResponse(
                request,
                "auth/register.html",
                get_template_context(request, error=error, success=success),
            )

        @app.post("/portal/register", response_class=HTMLResponse, tags=["portal"])
        async def portal_register_submit(
            request: Request,
            customer_name: str = Form(...),
            email: str = Form(...),
            max_concurrent_worksets: int = Form(10),
            max_storage_gb: int = Form(500),
            billing_account_id: Optional[str] = Form(None),
            cost_center: Optional[str] = Form(None),
        ):
            """Handle registration form submission."""
            if not customer_manager:
                return templates.TemplateResponse(
                    request,
                    "auth/register.html",
                    get_template_context(request, error="Customer management not configured"),
                )

            try:
                config = customer_manager.onboard_customer(
                    customer_name=customer_name,
                    email=email,
                    max_concurrent_worksets=max_concurrent_worksets,
                    max_storage_gb=max_storage_gb,
                    billing_account_id=billing_account_id,
                    cost_center=cost_center,
                )
                # Redirect to login page with success message
                success_msg = f"Account created successfully! Your customer ID is: {config.customer_id}. Please log in."
                return RedirectResponse(
                    url=f"/portal/login?success={success_msg}",
                    status_code=302,
                )
            except Exception as e:
                return templates.TemplateResponse(
                    request,
                    "auth/register.html",
                    get_template_context(request, error=str(e)),
                )

        @app.get("/portal/worksets", response_class=HTMLResponse, tags=["portal"])
        async def portal_worksets(request: Request, page: int = 1):
            """Worksets list page."""
            worksets = []
            for ws_state in WorksetState:
                batch = state_db.list_worksets_by_state(ws_state, limit=100)
                worksets.extend(batch)

            # Pagination
            per_page = 20
            total_pages = (len(worksets) + per_page - 1) // per_page
            start = (page - 1) * per_page
            worksets = worksets[start:start + per_page]

            return templates.TemplateResponse(
                request,
                "worksets/list.html",
                get_template_context(
                    request,
                    worksets=worksets,
                    current_page=page,
                    total_pages=total_pages,
                    active_page="worksets",
                ),
            )

        @app.get("/portal/worksets/new", response_class=HTMLResponse, tags=["portal"])
        async def portal_worksets_new(request: Request):
            """New workset submission page."""
            customer = None
            if customer_manager:
                customers = customer_manager.list_customers()
                if customers:
                    customer = _convert_customer_for_template(customers[0])

            return templates.TemplateResponse(
                request,
                "worksets/new.html",
                get_template_context(request, customer=customer, active_page="worksets"),
            )

        @app.get("/portal/worksets/{workset_id}", response_class=HTMLResponse, tags=["portal"])
        async def portal_workset_detail(request: Request, workset_id: str):
            """Workset detail page."""
            workset = state_db.get_workset(workset_id)
            if not workset:
                raise HTTPException(status_code=404, detail="Workset not found")

            return templates.TemplateResponse(
                request,
                "worksets/detail.html",
                get_template_context(request, workset=workset, active_page="worksets"),
            )

        @app.get("/portal/yaml-generator", response_class=HTMLResponse, tags=["portal"])
        async def portal_yaml_generator(request: Request):
            """YAML generator page."""
            customer = None
            if customer_manager:
                customers = customer_manager.list_customers()
                if customers:
                    customer = _convert_customer_for_template(customers[0])

            return templates.TemplateResponse(
                request,
                "yaml_generator.html",
                get_template_context(request, customer=customer, active_page="yaml"),
            )

        @app.get("/portal/files", response_class=HTMLResponse, tags=["portal"])
        async def portal_files(request: Request, prefix: str = ""):
            """File manager page."""
            customer = None
            files = []
            storage = {"used_gb": 0, "max_gb": 500, "percent": 0}
            breadcrumbs = []

            if customer_manager:
                customers = customer_manager.list_customers()
                if customers:
                    customer_raw = customers[0]
                    customer = _convert_customer_for_template(customer_raw)
                    storage["max_gb"] = customer.max_storage_gb

                    # Load files from S3
                    try:
                        s3 = boto3.client("s3")
                        response = s3.list_objects_v2(
                            Bucket=customer.s3_bucket,
                            Prefix=prefix,
                            Delimiter="/",
                        )

                        # Add folders (CommonPrefixes)
                        for cp in response.get("CommonPrefixes", []):
                            folder_path = cp["Prefix"]
                            folder_name = folder_path.rstrip("/").split("/")[-1]
                            files.append({
                                "key": folder_path,
                                "name": folder_name,
                                "type": "folder",
                                "size_formatted": "-",
                                "modified": "-",
                                "icon": "folder",
                            })

                        # Add files (Contents)
                        for obj in response.get("Contents", []):
                            key = obj["Key"]
                            if key == prefix:
                                continue
                            name = key.split("/")[-1]
                            if not name:
                                continue
                            files.append({
                                "key": key,
                                "name": name,
                                "type": "file",
                                "size_formatted": _format_file_size(obj["Size"]),
                                "modified": obj["LastModified"].strftime("%Y-%m-%d %H:%M") if obj.get("LastModified") else "-",
                                "icon": _get_file_icon(name),
                            })

                    except Exception as e:
                        LOGGER.warning("Failed to list S3 files: %s", e)

            # Build breadcrumbs from prefix
            if prefix:
                parts = prefix.strip("/").split("/")
                path = ""
                for part in parts:
                    path = f"{path}/{part}" if path else part
                    breadcrumbs.append({"name": part, "path": path + "/"})

            return templates.TemplateResponse(
                request,
                "files.html",
                get_template_context(
                    request,
                    customer=customer,
                    files=files,
                    storage=storage,
                    breadcrumbs=breadcrumbs,
                    prefix=prefix,
                    active_page="files",
                ),
            )

        @app.get("/portal/usage", response_class=HTMLResponse, tags=["portal"])
        async def portal_usage(request: Request):
            """Usage and billing page."""
            customer = None
            usage = {
                "total_cost": 0,
                "cost_change": 0,
                "vcpu_hours": 0,
                "memory_gb_hours": 0,
                "storage_gb": 0,
                "active_worksets": 0,
            }
            usage_details = []

            if customer_manager:
                customers = customer_manager.list_customers()
                if customers:
                    customer = _convert_customer_for_template(customers[0])
                    customer_usage = customer_manager.get_customer_usage(customers[0].customer_id)
                    if customer_usage:
                        usage.update(customer_usage)

            return templates.TemplateResponse(
                request,
                "usage.html",
                get_template_context(
                    request,
                    customer=customer,
                    usage=usage,
                    usage_details=usage_details,
                    active_page="usage",
                ),
            )

        @app.get("/portal/account", response_class=HTMLResponse, tags=["portal"])
        async def portal_account(request: Request):
            """Account settings page."""
            customer = None
            if customer_manager:
                customers = customer_manager.list_customers()
                if customers:
                    customer = _convert_customer_for_template(customers[0])

            return templates.TemplateResponse(
                request,
                "account.html",
                get_template_context(request, customer=customer, active_page="account"),
            )

        @app.get("/portal/logout", response_class=RedirectResponse, tags=["portal"])
        async def portal_logout(request: Request):
            """Logout and redirect to login page."""
            # In a real implementation, you would clear session/cookies here
            return RedirectResponse(url="/portal/login", status_code=302)

    return app

