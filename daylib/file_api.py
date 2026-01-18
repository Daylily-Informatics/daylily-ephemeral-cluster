"""
File Registration API endpoints for Daylily portal.

Provides REST API for file registration, metadata capture, file set management,
linked bucket management, and file discovery.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

import boto3
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from daylib.file_registry import (
    BiosampleMetadata,
    BucketFileDiscovery,
    DiscoveredFile,
    FileMetadata,
    FileRegistration,
    FileRegistry,
    FileSet,
    FileWorksetUsage,
    SequencingMetadata,
    detect_file_format,
    generate_file_id,
)
from daylib.s3_bucket_validator import (
    BucketValidationResult,
    LinkedBucket,
    LinkedBucketManager,
    S3BucketValidator,
)
from daylib.file_upload import (
    FileUploadManager,
    PresignedUrlResponse,
    UploadSession,
    generate_upload_path,
)
from daylib.file_metadata import (
    AnalysisInput,
    generate_stage_samples_tsv,
    SampleType,
    LibraryPrep,
    SequencingVendor,
    SequencingPlatform,
)

LOGGER = logging.getLogger("daylily.file_api")


def _get_authenticated_customer_id(current_user: Optional[Dict]) -> Optional[str]:
    """Extract customer_id for the authenticated user from auth context.

    Supports both an explicit ``customer_id`` field and the Cognito
    ``custom:customer_id`` claim used by :class:`~daylib.workset_auth.CognitoAuth`.

    Returns ``None`` when no customer_id information is available so that
    callers can decide whether to enforce ownership checks or operate in
    legacy/no-auth modes.
    """

    if not current_user:
        return None

    # Preferred: explicit customer_id key
    customer_id = current_user.get("customer_id")
    if customer_id:
        return str(customer_id)

    # Cognito custom attribute from JWT claims
    customer_id = current_user.get("custom:customer_id")
    if customer_id:
        return str(customer_id)

    return None


def verify_file_ownership(file: Optional[FileRegistration], customer_id: str) -> bool:
    """Check if a file belongs to a customer by customer_id.

    This mirrors :func:`daylib.workset_api.verify_workset_ownership` but for
    :class:`~daylib.file_registry.FileRegistration` records. Ownership is
    determined solely by the ``customer_id`` field, which is authoritative in
    the control-plane design.
    """

    if not file or not customer_id:
        return False

    return getattr(file, "customer_id", None) == customer_id


# Pydantic models for API requests/responses
class FileMetadataRequest(BaseModel):
    """Request model for file metadata."""
    s3_uri: str = Field(..., description="Full S3 URI")
    file_size_bytes: int = Field(..., description="File size in bytes")
    md5_checksum: Optional[str] = None
    file_format: str = "fastq"


class BiosampleMetadataRequest(BaseModel):
    """Request model for biosample metadata."""
    biosample_id: str
    subject_id: str
    sample_type: str = "blood"
    tissue_type: Optional[str] = None
    collection_date: Optional[str] = None
    preservation_method: Optional[str] = None
    tumor_fraction: Optional[float] = None


class SequencingMetadataRequest(BaseModel):
    """Request model for sequencing metadata."""
    platform: str = "ILLUMINA_NOVASEQ_X"
    vendor: str = "ILMN"
    run_id: str = ""
    lane: int = 0
    barcode_id: str = "S1"
    flowcell_id: Optional[str] = None
    run_date: Optional[str] = None


class FileRegistrationRequest(BaseModel):
    """Request model for file registration."""
    file_metadata: FileMetadataRequest
    sequencing_metadata: SequencingMetadataRequest
    biosample_metadata: BiosampleMetadataRequest
    paired_with: Optional[str] = None
    read_number: int = 1
    quality_score: Optional[float] = None
    percent_q30: Optional[float] = None
    concordance_vcf_path: Optional[str] = None
    is_positive_control: bool = False
    is_negative_control: bool = False
    tags: List[str] = Field(default_factory=list)


class FileRegistrationResponse(BaseModel):
    """Response model for file registration."""
    file_id: str
    customer_id: str
    s3_uri: str
    biosample_id: str
    subject_id: str
    registered_at: str
    status: str = "registered"


class FileSetRequest(BaseModel):
    """Request model for file set creation."""
    name: str
    description: Optional[str] = None
    biosample_metadata: Optional[BiosampleMetadataRequest] = None
    sequencing_metadata: Optional[SequencingMetadataRequest] = None
    file_ids: List[str] = Field(default_factory=list)


class FileSetResponse(BaseModel):
    """Response model for file set."""
    fileset_id: str
    customer_id: str
    name: str
    file_count: int
    created_at: str


class BulkImportRequest(BaseModel):
    """Request model for bulk file import."""
    files: List[FileRegistrationRequest]
    fileset_name: Optional[str] = None
    fileset_description: Optional[str] = None


class AddFileToFilesetRequest(BaseModel):
    """Request model to add a single file to an existing file set."""

    fileset_id: str = Field(..., description="ID of the fileset to add the file to")


class BulkImportResponse(BaseModel):
    """Response model for bulk import."""
    imported_count: int
    failed_count: int
    fileset_id: Optional[str] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# Bucket management models
class LinkBucketRequest(BaseModel):
    """Request model for linking an S3 bucket."""
    bucket_name: str = Field(..., description="S3 bucket name")
    bucket_type: str = Field("secondary", description="Bucket type: primary, secondary, archive, shared")
    display_name: Optional[str] = Field(None, description="User-friendly display name")
    description: Optional[str] = Field(None, description="Description of bucket purpose")
    prefix_restriction: Optional[str] = Field(None, description="Restrict access to specific prefix")
    read_only: bool = Field(False, description="If true, prevent writes to this bucket")
    validate_access: bool = Field(True, description="Whether to validate bucket access")


class LinkedBucketResponse(BaseModel):
    """Response model for linked bucket."""
    bucket_id: str
    customer_id: str
    bucket_name: str
    bucket_type: str
    display_name: str
    is_validated: bool
    can_read: bool
    can_write: bool
    can_list: bool
    region: Optional[str]
    linked_at: str


class BucketValidationResponse(BaseModel):
    """Response model for bucket validation."""
    bucket_name: str
    exists: bool
    accessible: bool
    can_read: bool
    can_write: bool
    can_list: bool
    is_valid: bool
    is_fully_configured: bool
    region: Optional[str]
    errors: List[str]
    warnings: List[str]
    remediation_steps: List[str]


class DiscoveredFileResponse(BaseModel):
    """Response model for discovered file."""
    s3_uri: str
    bucket_name: str
    key: str
    file_size_bytes: int
    last_modified: str
    detected_format: str
    is_registered: bool
    file_id: Optional[str]


class DiscoverFilesRequest(BaseModel):
    """Request model for file discovery."""
    bucket_name: str = Field(..., description="S3 bucket name to scan")
    prefix: str = Field("", description="Optional prefix to filter files")
    file_formats: Optional[List[str]] = Field(None, description="Filter by formats: fastq, bam, vcf, etc.")
    max_files: int = Field(1000, ge=1, le=10000, description="Maximum files to return")
    check_registration: bool = Field(True, description="Check if files are already registered")


class DiscoverFilesResponse(BaseModel):
    """Response model for file discovery."""
    bucket_name: str
    prefix: str
    total_files: int
    registered_count: int
    unregistered_count: int
    files: List[DiscoveredFileResponse]


class AutoRegisterRequest(BaseModel):
    """Request model for auto-registering discovered files."""
    bucket_name: str = Field(..., description="S3 bucket name")
    prefix: str = Field("", description="Prefix to scan")
    file_formats: Optional[List[str]] = Field(None, description="Filter by formats")
    biosample_id: str = Field(..., description="Default biosample ID for all files")
    subject_id: str = Field(..., description="Default subject ID for all files")
    sequencing_platform: str = Field("ILLUMINA_NOVASEQ_X", description="Sequencing platform")
    max_files: int = Field(100, ge=1, le=1000, description="Maximum files to register")


class AutoRegisterResponse(BaseModel):
    """Response model for auto-registration."""
    registered_count: int
    skipped_count: int
    errors: List[str]


# ========== Bucket Browsing Models ==========


class BrowseItem(BaseModel):
    """A file or folder in the S3 bucket browse view."""
    name: str = Field(..., description="File or folder name")
    key: str = Field(..., description="Full S3 key/path")
    is_folder: bool = Field(..., description="True if this is a folder (prefix)")
    size_bytes: Optional[int] = Field(None, description="File size (None for folders)")
    last_modified: Optional[str] = Field(None, description="Last modified timestamp")
    file_format: Optional[str] = Field(None, description="Detected file format")
    is_registered: bool = Field(False, description="True if file is registered in FileRegistry")
    file_id: Optional[str] = Field(None, description="File ID if registered")


class BrowseBucketResponse(BaseModel):
    """Response model for bucket browsing."""
    bucket_id: str
    bucket_name: str
    display_name: str
    current_prefix: str
    parent_prefix: Optional[str] = Field(None, description="Parent folder prefix")
    breadcrumbs: List[Dict[str, str]] = Field(default_factory=list)
    items: List[BrowseItem] = Field(default_factory=list)
    can_write: bool = Field(False, description="Whether user can create/delete")
    is_read_only: bool = Field(False, description="Whether bucket is read-only")
    total_items: int = Field(0, description="Total items in current view")


class CreateFolderRequest(BaseModel):
    """Request model for creating a folder."""
    folder_name: str = Field(..., min_length=1, max_length=255, description="New folder name")


class CreateFolderResponse(BaseModel):
    """Response model for folder creation."""
    success: bool
    folder_key: str = Field(..., description="Full S3 key of created folder")
    message: str


class DeleteFileRequest(BaseModel):
    """Request model for deleting a file."""
    file_key: str = Field(..., description="S3 key of file to delete")


class DeleteFileResponse(BaseModel):
    """Response model for file deletion."""
    success: bool
    deleted_key: str
    message: str


class FileSearchRequest(BaseModel):
    """Request model for file search."""
    tag: Optional[str] = Field(None, description="Search by tag")
    biosample_id: Optional[str] = Field(None, description="Search by biosample ID")
    subject_id: Optional[str] = Field(None, description="Search by subject ID")


# Upload models
class PresignedUploadRequest(BaseModel):
    """Request model for presigned upload URL."""
    bucket_name: str = Field(..., description="Target S3 bucket")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field("application/octet-stream", description="MIME type")
    file_size_bytes: Optional[int] = Field(None, description="File size for validation")
    use_multipart: bool = Field(False, description="Use multipart upload for large files")
    prefix: str = Field("uploads", description="Path prefix in bucket")


class PresignedUploadResponse(BaseModel):
    """Response model for presigned upload URL."""
    upload_url: str
    object_key: str
    bucket_name: str
    method: str
    expires_in: int
    fields: Dict[str, str] = Field(default_factory=dict)
    upload_id: Optional[str] = None  # For multipart uploads


class MultipartUploadPartRequest(BaseModel):
    """Request model for multipart upload part URL."""
    bucket_name: str
    object_key: str
    upload_id: str
    part_number: int = Field(..., ge=1, le=10000)


class CompleteMultipartRequest(BaseModel):
    """Request model for completing multipart upload."""
    bucket_name: str
    object_key: str
    upload_id: str
    parts: List[Dict[str, Any]] = Field(..., description="List of {PartNumber, ETag}")


class VerifyUploadRequest(BaseModel):
    """Request model for verifying upload."""
    bucket_name: str
    object_key: str
    expected_size: Optional[int] = None
    expected_etag: Optional[str] = None


class VerifyUploadResponse(BaseModel):
    """Response model for upload verification."""
    is_valid: bool
    size: Optional[int]
    etag: Optional[str]
    content_type: Optional[str]
    last_modified: Optional[str]
    error: Optional[str] = None


# Manifest generation models
class ManifestGenerationRequest(BaseModel):
    """Request model for manifest generation from registered files."""
    file_ids: Optional[List[str]] = Field(None, description="Specific file IDs to include")
    fileset_id: Optional[str] = Field(None, description="Generate from a file set")
    biosample_id: Optional[str] = Field(None, description="Filter by biosample ID")
    run_id: str = Field("R0", description="Run ID for the manifest")
    stage_target: str = Field("/fsx/staged_sample_data/", description="Stage target directory")
    include_header: bool = Field(True, description="Include TSV header row")


class ManifestGenerationResponse(BaseModel):
    """Response model for manifest generation."""
    tsv_content: str
    sample_count: int
    file_count: int
    warnings: List[str] = Field(default_factory=list)


def create_file_api_router(
    file_registry: FileRegistry,
    auth_dependency: Optional[Callable] = None,
    linked_bucket_manager: Optional[LinkedBucketManager] = None,
    bucket_file_discovery: Optional[BucketFileDiscovery] = None,
    s3_bucket_validator: Optional[S3BucketValidator] = None,
    file_upload_manager: Optional[FileUploadManager] = None,
) -> APIRouter:
    """Create FastAPI router for file registration endpoints.

    Args:
        file_registry: FileRegistry instance
        auth_dependency: Optional authentication dependency function
        linked_bucket_manager: Optional LinkedBucketManager for bucket management
        bucket_file_discovery: Optional BucketFileDiscovery for file discovery
        s3_bucket_validator: Optional S3BucketValidator for bucket validation
        file_upload_manager: Optional FileUploadManager for upload handling

    Returns:
        APIRouter with file registration endpoints
    """
    router = APIRouter(prefix="/api/files", tags=["files"])

    # Create a dummy auth dependency if none provided
    if auth_dependency is None:
        async def no_auth() -> Optional[Dict]:
            return None
        auth_dependency = no_auth
    
    @router.post("/register", response_model=FileRegistrationResponse)
    async def register_file(
        customer_id: str = Query(..., description="Customer ID"),
        request: FileRegistrationRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Register a file with metadata.

        Requires authentication if enabled. Customer ID must match authenticated user's customer.
        """
        try:
            # Enforce S3 URI uniqueness per customer. If a file with the same
            # S3 URI is already registered for this customer, treat this as a
            # conflict and surface a clear error to the caller.
            existing = file_registry.find_file_by_s3_uri(
                customer_id=customer_id,
                s3_uri=request.file_metadata.s3_uri,
            )
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "File with this S3 URI is already registered "
                        f"(file_id={existing.file_id})."
                    ),
                )

            # Use deterministic file IDs derived from customer + S3 URI so that
            # registration, discovery, and portal views all agree on identity.
            file_id = generate_file_id(request.file_metadata.s3_uri, customer_id)

            file_meta = FileMetadata(
                file_id=file_id,
                s3_uri=request.file_metadata.s3_uri,
                file_size_bytes=request.file_metadata.file_size_bytes,
                md5_checksum=request.file_metadata.md5_checksum,
                file_format=request.file_metadata.file_format,
            )
            
            seq_meta = SequencingMetadata(
                platform=request.sequencing_metadata.platform,
                vendor=request.sequencing_metadata.vendor,
                run_id=request.sequencing_metadata.run_id,
                lane=request.sequencing_metadata.lane,
                barcode_id=request.sequencing_metadata.barcode_id,
                flowcell_id=request.sequencing_metadata.flowcell_id,
                run_date=request.sequencing_metadata.run_date,
            )
            
            bio_meta = BiosampleMetadata(
                biosample_id=request.biosample_metadata.biosample_id,
                subject_id=request.biosample_metadata.subject_id,
                sample_type=request.biosample_metadata.sample_type,
                tissue_type=request.biosample_metadata.tissue_type,
                collection_date=request.biosample_metadata.collection_date,
                preservation_method=request.biosample_metadata.preservation_method,
                tumor_fraction=request.biosample_metadata.tumor_fraction,
            )
            
            registration = FileRegistration(
                file_id=file_id,
                customer_id=customer_id,
                file_metadata=file_meta,
                sequencing_metadata=seq_meta,
                biosample_metadata=bio_meta,
                paired_with=request.paired_with,
                read_number=request.read_number,
                quality_score=request.quality_score,
                percent_q30=request.percent_q30,
                concordance_vcf_path=request.concordance_vcf_path,
                is_positive_control=request.is_positive_control,
                is_negative_control=request.is_negative_control,
                tags=request.tags,
            )
            
            success = file_registry.register_file(registration)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"File {file_id} already registered",
                )

            return FileRegistrationResponse(
                file_id=file_id,
                customer_id=customer_id,
                s3_uri=request.file_metadata.s3_uri,
                biosample_id=request.biosample_metadata.biosample_id,
                subject_id=request.biosample_metadata.subject_id,
                registered_at=registration.registered_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to register file: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to register file: {str(e)}",
            )
    
    @router.get("/list")
    async def list_customer_files(
        customer_id: str = Query(..., description="Customer ID"),
        limit: int = Query(100, ge=1, le=1000),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """List all files for a customer.

        Requires authentication if enabled. Customer ID must match authenticated user's customer.
        """
        try:
            files = file_registry.list_customer_files(customer_id, limit=limit)
            return {
                "customer_id": customer_id,
                "file_count": len(files),
                "files": [
                    {
                        "file_id": f.file_id,
                        "s3_uri": f.file_metadata.s3_uri,
                        "biosample_id": f.biosample_metadata.biosample_id,
                        "subject_id": f.biosample_metadata.subject_id,
                        "registered_at": f.registered_at,
                    }
                    for f in files
                ],
            }
        except Exception as e:
            LOGGER.error("Failed to list files: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list files: {str(e)}",
            )
    
    @router.post("/filesets", response_model=FileSetResponse)
    async def create_fileset(
        customer_id: str = Query(..., description="Customer ID"),
        request: FileSetRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Create a file set grouping files with shared metadata.

        Requires authentication if enabled. Customer ID must match authenticated user's customer.
        """
        try:
            fileset_id = f"fileset-{uuid.uuid4().hex[:12]}"
            
            bio_meta = None
            if request.biosample_metadata:
                bio_meta = BiosampleMetadata(
                    biosample_id=request.biosample_metadata.biosample_id,
                    subject_id=request.biosample_metadata.subject_id,
                    sample_type=request.biosample_metadata.sample_type,
                    tissue_type=request.biosample_metadata.tissue_type,
                    collection_date=request.biosample_metadata.collection_date,
                    preservation_method=request.biosample_metadata.preservation_method,
                    tumor_fraction=request.biosample_metadata.tumor_fraction,
                )
            
            seq_meta = None
            if request.sequencing_metadata:
                seq_meta = SequencingMetadata(
                    platform=request.sequencing_metadata.platform,
                    vendor=request.sequencing_metadata.vendor,
                    run_id=request.sequencing_metadata.run_id,
                    lane=request.sequencing_metadata.lane,
                    barcode_id=request.sequencing_metadata.barcode_id,
                    flowcell_id=request.sequencing_metadata.flowcell_id,
                    run_date=request.sequencing_metadata.run_date,
                )
            
            fileset = FileSet(
                fileset_id=fileset_id,
                customer_id=customer_id,
                name=request.name,
                description=request.description,
                biosample_metadata=bio_meta,
                sequencing_metadata=seq_meta,
                file_ids=request.file_ids,
            )
            
            success = file_registry.create_fileset(fileset)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"FileSet {fileset_id} already exists",
                )
            
            return FileSetResponse(
                fileset_id=fileset_id,
                customer_id=customer_id,
                name=request.name,
                file_count=len(request.file_ids),
                created_at=fileset.created_at,
            )
        except Exception as e:
            LOGGER.error("Failed to create fileset: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create fileset: {str(e)}",
            )

    @router.get("/filesets")
    async def list_filesets(
        customer_id: str = Query(..., description="Customer ID"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """List all file sets for a customer."""
        try:
            filesets = file_registry.list_customer_filesets(customer_id)
            return [
                {
                    "fileset_id": fs.fileset_id,
                    "name": fs.name,
                    "description": fs.description,
                    "file_count": len(fs.file_ids),
                    "created_at": fs.created_at,
                    "tags": fs.tags,
                }
                for fs in filesets
            ]
        except Exception as e:
            LOGGER.error("Failed to list filesets: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list filesets: {str(e)}",
            )

    @router.post("/bulk-import", response_model=BulkImportResponse)
    async def bulk_import_files(
        customer_id: str = Query(..., description="Customer ID"),
        request: BulkImportRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Bulk import multiple files with metadata.

        Requires authentication if enabled. Customer ID must match authenticated user's customer.
        """
        imported_count = 0
        failed_count = 0
        errors = []
        fileset_id = None
        
        file_ids = []
        
        for idx, file_req in enumerate(request.files):
            try:
                file_id = f"file-{uuid.uuid4().hex[:12]}"
                
                file_meta = FileMetadata(
                    file_id=file_id,
                    s3_uri=file_req.file_metadata.s3_uri,
                    file_size_bytes=file_req.file_metadata.file_size_bytes,
                    md5_checksum=file_req.file_metadata.md5_checksum,
                    file_format=file_req.file_metadata.file_format,
                )
                
                seq_meta = SequencingMetadata(
                    platform=file_req.sequencing_metadata.platform,
                    vendor=file_req.sequencing_metadata.vendor,
                    run_id=file_req.sequencing_metadata.run_id,
                    lane=file_req.sequencing_metadata.lane,
                    barcode_id=file_req.sequencing_metadata.barcode_id,
                    flowcell_id=file_req.sequencing_metadata.flowcell_id,
                    run_date=file_req.sequencing_metadata.run_date,
                )
                
                bio_meta = BiosampleMetadata(
                    biosample_id=file_req.biosample_metadata.biosample_id,
                    subject_id=file_req.biosample_metadata.subject_id,
                    sample_type=file_req.biosample_metadata.sample_type,
                    tissue_type=file_req.biosample_metadata.tissue_type,
                    collection_date=file_req.biosample_metadata.collection_date,
                    preservation_method=file_req.biosample_metadata.preservation_method,
                    tumor_fraction=file_req.biosample_metadata.tumor_fraction,
                )
                
                registration = FileRegistration(
                    file_id=file_id,
                    customer_id=customer_id,
                    file_metadata=file_meta,
                    sequencing_metadata=seq_meta,
                    biosample_metadata=bio_meta,
                    paired_with=file_req.paired_with,
                    read_number=file_req.read_number,
                    quality_score=file_req.quality_score,
                    percent_q30=file_req.percent_q30,
                    concordance_vcf_path=file_req.concordance_vcf_path,
                    is_positive_control=file_req.is_positive_control,
                    is_negative_control=file_req.is_negative_control,
                    tags=file_req.tags,
                )
                
                if file_registry.register_file(registration):
                    imported_count += 1
                    file_ids.append(file_id)
                else:
                    failed_count += 1
                    errors.append({
                        "index": idx,
                        "s3_uri": file_req.file_metadata.s3_uri,
                        "error": "File already registered",
                    })
            except Exception as e:
                failed_count += 1
                errors.append({
                    "index": idx,
                    "s3_uri": file_req.file_metadata.s3_uri,
                    "error": str(e),
                })
        
        # Create fileset if requested
        if request.fileset_name and file_ids:
            try:
                fileset_id = f"fileset-{uuid.uuid4().hex[:12]}"
                fileset = FileSet(
                    fileset_id=fileset_id,
                    customer_id=customer_id,
                    name=request.fileset_name,
                    description=request.fileset_description,
                    file_ids=file_ids,
                )
                file_registry.create_fileset(fileset)
            except Exception as e:
                LOGGER.error("Failed to create fileset: %s", str(e))
        
        return BulkImportResponse(
            imported_count=imported_count,
            failed_count=failed_count,
            fileset_id=fileset_id,
            errors=errors,
        )

    # ========== Bucket Management Endpoints ==========

    @router.post("/buckets/link", response_model=LinkedBucketResponse)
    async def link_bucket(
        customer_id: str = Query(..., description="Customer ID"),
        request: LinkBucketRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Link an S3 bucket to a customer account.

        Validates bucket access and stores the configuration.
        """
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )

        try:
            LOGGER.info(
                "Linking bucket: customer_id=%s, bucket_name=%s, bucket_type=%s, display_name=%s",
                customer_id, request.bucket_name, request.bucket_type, request.display_name
            )
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug(
                    "Link bucket request details: prefix_restriction=%s, read_only=%s, validate_access=%s",
                    request.prefix_restriction, request.read_only, request.validate_access
                )

            linked_bucket, validation_result = linked_bucket_manager.link_bucket(
                customer_id=customer_id,
                bucket_name=request.bucket_name,
                bucket_type=request.bucket_type,
                display_name=request.display_name,
                description=request.description,
                prefix_restriction=request.prefix_restriction,
                read_only=request.read_only,
                validate=request.validate_access,
            )

            LOGGER.info(
                "Successfully linked bucket: bucket_id=%s, is_validated=%s, can_write=%s",
                linked_bucket.bucket_id, linked_bucket.is_validated, linked_bucket.can_write
            )

            return LinkedBucketResponse(
                bucket_id=linked_bucket.bucket_id,
                customer_id=linked_bucket.customer_id,
                bucket_name=linked_bucket.bucket_name,
                bucket_type=linked_bucket.bucket_type,
                display_name=linked_bucket.display_name or linked_bucket.bucket_name,
                is_validated=linked_bucket.is_validated,
                can_read=linked_bucket.can_read,
                can_write=linked_bucket.can_write,
                can_list=linked_bucket.can_list,
                region=linked_bucket.region,
                linked_at=linked_bucket.linked_at,
            )
        except Exception as e:
            # Don't use exc_info=True or log the raw exception object; this can trigger
            # deepcopy recursion issues when boto3 objects are attached to the exception.
            LOGGER.error("Failed to link bucket: %s", str(e))
            # Include more detail in the error message for debugging
            error_detail = str(e)
            if "ResourceNotFoundException" in error_detail:
                error_detail = (
                    "DynamoDB table not found. The linked buckets table may need to be created. "
                    f"Original error: {str(e)}"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to link bucket: {error_detail}",
            )

    @router.get("/buckets/list")
    async def list_linked_buckets(
        customer_id: str = Query(..., description="Customer ID"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """List all linked buckets for a customer."""
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )

        try:
            buckets = linked_bucket_manager.list_customer_buckets(customer_id)
            return {
                "customer_id": customer_id,
                "bucket_count": len(buckets),
                "buckets": [
                    {
                        "bucket_id": b.bucket_id,
                        "bucket_name": b.bucket_name,
                        "bucket_type": b.bucket_type,
                        "display_name": b.display_name,
                        "is_validated": b.is_validated,
                        "can_read": b.can_read,
                        "can_write": b.can_write,
                        "linked_at": b.linked_at,
                    }
                    for b in buckets
                ],
            }
        except Exception as e:
            LOGGER.error("Failed to list buckets: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list buckets: {str(e)}",
            )

    @router.post("/buckets/{bucket_id}/revalidate", response_model=BucketValidationResponse)
    async def revalidate_bucket(
        bucket_id: str,
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Re-validate a linked bucket and update its status."""
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )

        try:
            linked_bucket, validation_result = linked_bucket_manager.revalidate_bucket(bucket_id)
            if linked_bucket is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bucket {bucket_id} not found",
                )

            return BucketValidationResponse(
                bucket_name=validation_result.bucket_name,
                exists=validation_result.exists,
                accessible=validation_result.accessible,
                can_read=validation_result.can_read,
                can_write=validation_result.can_write,
                can_list=validation_result.can_list,
                is_valid=validation_result.is_valid,
                is_fully_configured=validation_result.is_fully_configured,
                region=validation_result.region,
                errors=validation_result.errors,
                warnings=validation_result.warnings,
                remediation_steps=validation_result.remediation_steps,
            )
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to revalidate bucket: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to revalidate bucket: {str(e)}",
            )

    @router.post("/buckets/validate", response_model=BucketValidationResponse)
    async def validate_bucket(
        bucket_name: str = Query(..., description="S3 bucket name to validate"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Validate an S3 bucket without linking it."""
        if s3_bucket_validator is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket validation not configured",
            )

        try:
            result = s3_bucket_validator.validate_bucket(bucket_name)
            return BucketValidationResponse(
                bucket_name=result.bucket_name,
                exists=result.exists,
                accessible=result.accessible,
                can_read=result.can_read,
                can_write=result.can_write,
                can_list=result.can_list,
                is_valid=result.is_valid,
                is_fully_configured=result.is_fully_configured,
                region=result.region,
                errors=result.errors,
                warnings=result.warnings,
                remediation_steps=result.remediation_steps,
            )
        except Exception as e:
            LOGGER.error("Failed to validate bucket: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to validate bucket: {str(e)}",
            )

    @router.post("/buckets/{bucket_id}/unlink")
    async def unlink_bucket(
        bucket_id: str,
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Unlink a bucket from the customer account.

        Removes the bucket configuration but does not affect files in the bucket.
        """
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )

        try:
            success = linked_bucket_manager.unlink_bucket(bucket_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bucket not found: {bucket_id}",
                )
            LOGGER.info("Unlinked bucket: %s", bucket_id)
            return {"status": "success", "message": f"Bucket {bucket_id} unlinked successfully"}
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to unlink bucket: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to unlink bucket: {str(e)}",
            )

    @router.patch("/buckets/{bucket_id}")
    async def update_bucket(
        bucket_id: str,
        display_name: Optional[str] = Body(None, description="New display name"),
        description: Optional[str] = Body(None, description="New description"),
        bucket_type: Optional[str] = Body(None, description="Bucket type: primary, secondary, archive, shared"),
        prefix_restriction: Optional[str] = Body(None, description="Prefix restriction"),
        read_only: Optional[bool] = Body(None, description="Read-only mode"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Update a linked bucket's configuration."""
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )

        try:
            updated = linked_bucket_manager.update_bucket(
                bucket_id=bucket_id,
                display_name=display_name,
                description=description,
                bucket_type=bucket_type,
                prefix_restriction=prefix_restriction,
                read_only=read_only,
            )
            if updated is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bucket not found: {bucket_id}",
                )
            LOGGER.info("Updated bucket: %s", bucket_id)
            return {
                "status": "success",
                "bucket": {
                    "bucket_id": updated.bucket_id,
                    "bucket_name": updated.bucket_name,
                    "display_name": updated.display_name,
                    "description": updated.description,
                    "bucket_type": updated.bucket_type,
                    "prefix_restriction": updated.prefix_restriction,
                    "read_only": updated.read_only,
                    "is_validated": updated.is_validated,
                    "can_read": updated.can_read,
                    "can_write": updated.can_write,
                    "can_list": updated.can_list,
                },
            }
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to update bucket: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update bucket: {str(e)}",
            )

    @router.get("/buckets/{bucket_id}")
    async def get_bucket(
        bucket_id: str,
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get a single bucket's details."""
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )

        try:
            bucket = linked_bucket_manager.get_bucket(bucket_id)
            if bucket is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bucket not found: {bucket_id}",
                )
            return {
                "bucket_id": bucket.bucket_id,
                "customer_id": bucket.customer_id,
                "bucket_name": bucket.bucket_name,
                "display_name": bucket.display_name,
                "description": bucket.description,
                "bucket_type": bucket.bucket_type,
                "prefix_restriction": bucket.prefix_restriction,
                "read_only": bucket.read_only,
                "is_validated": bucket.is_validated,
                "can_read": bucket.can_read,
                "can_write": bucket.can_write,
                "can_list": bucket.can_list,
                "region": bucket.region,
                "linked_at": bucket.linked_at,
            }
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to get bucket: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get bucket: {str(e)}",
            )

    @router.post("/buckets/{bucket_id}/discover", response_model=DiscoverFilesResponse)
    async def discover_bucket_files(
        bucket_id: str,
        customer_id: str = Query(..., description="Customer ID"),
        prefix: str = Query("", description="Optional prefix to filter files"),
        file_formats: Optional[str] = Query(None, description="Comma-separated formats: fastq,bam,vcf"),
        max_files: int = Query(1000, ge=1, le=10000, description="Maximum files to return"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Discover files in a specific linked bucket."""
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )
        if bucket_file_discovery is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="File discovery not configured",
            )

        try:
            LOGGER.debug(f"discover_bucket_files: Starting discovery for bucket_id={bucket_id}, customer_id={customer_id}")

            # Get the bucket to verify it exists and get bucket name
            LOGGER.debug(f"discover_bucket_files: Getting bucket info for {bucket_id}")
            bucket = linked_bucket_manager.get_bucket(bucket_id)
            if bucket is None:
                LOGGER.error(f"discover_bucket_files: Bucket not found: {bucket_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bucket not found: {bucket_id}",
                )
            LOGGER.debug(f"discover_bucket_files: Got bucket {bucket.bucket_name}")

            # Parse file formats if provided
            formats_list = None
            if file_formats:
                formats_list = [f.strip() for f in file_formats.split(",")]
            LOGGER.debug(f"discover_bucket_files: Parsed formats_list={formats_list}")

            # Use prefix restriction from bucket if no prefix specified
            effective_prefix = prefix or bucket.prefix_restriction or ""
            LOGGER.debug(f"discover_bucket_files: effective_prefix={effective_prefix}")

            LOGGER.info(
                "Discovering files in bucket %s (prefix=%s, formats=%s, max_files=%d)",
                bucket.bucket_name, effective_prefix, formats_list, max_files
            )

            LOGGER.debug("discover_bucket_files: Calling bucket_file_discovery.discover_files()")
            discovered = bucket_file_discovery.discover_files(
                bucket_name=bucket.bucket_name,
                prefix=effective_prefix,
                file_formats=formats_list,
                max_files=max_files,
            )
            LOGGER.info(f"discover_bucket_files: discover_files returned {len(discovered)} files")

            # Check registration status (only if file_registry is available)
            if file_registry:
                LOGGER.info("Checking registration status for %d discovered files", len(discovered))
                try:
                    LOGGER.debug("discover_bucket_files: Starting check_registration_status call")
                    discovered = bucket_file_discovery.check_registration_status(
                        discovered, file_registry, customer_id
                    )
                    LOGGER.info("discover_bucket_files: Successfully checked registration status for all files")
                except Exception as e:
                    # Don't use exc_info=True as it causes deepcopy issues with boto3 objects
                    LOGGER.error("discover_bucket_files: Error checking registration status: %s", str(e))
                    LOGGER.warning("discover_bucket_files: Continuing without registration status check")
            else:
                LOGGER.warning("discover_bucket_files: file_registry is None, skipping registration status check")

            registered_count = sum(1 for f in discovered if f.is_registered)

            LOGGER.info(
                "Discovered %d files in bucket %s (prefix=%s): %d registered, %d unregistered",
                len(discovered), bucket.bucket_name, effective_prefix, registered_count, len(discovered) - registered_count
            )

            return DiscoverFilesResponse(
                bucket_name=bucket.bucket_name,
                prefix=effective_prefix,
                total_files=len(discovered),
                registered_count=registered_count,
                unregistered_count=len(discovered) - registered_count,
                files=[
                    DiscoveredFileResponse(
                        s3_uri=f.s3_uri,
                        bucket_name=f.bucket_name,
                        key=f.key,
                        file_size_bytes=f.file_size_bytes,
                        last_modified=f.last_modified,
                        detected_format=f.detected_format,
                        is_registered=f.is_registered,
                        file_id=f.file_id,
                    )
                    for f in discovered
                ],
            )
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to discover files in bucket %s: %s", bucket_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to discover files: {str(e)}",
            )

    # ========== File Discovery Endpoints ==========

    @router.post("/discover", response_model=DiscoverFilesResponse)
    async def discover_files(
        customer_id: str = Query(..., description="Customer ID"),
        request: DiscoverFilesRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Discover files in an S3 bucket.

        Scans the bucket and returns a list of files with their metadata.
        Optionally checks if files are already registered.
        """
        if bucket_file_discovery is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="File discovery not configured",
            )

        try:
            discovered = bucket_file_discovery.discover_files(
                bucket_name=request.bucket_name,
                prefix=request.prefix,
                file_formats=request.file_formats,
                max_files=request.max_files,
            )

            if request.check_registration:
                discovered = bucket_file_discovery.check_registration_status(
                    discovered, file_registry, customer_id
                )

            registered_count = sum(1 for f in discovered if f.is_registered)

            return DiscoverFilesResponse(
                bucket_name=request.bucket_name,
                prefix=request.prefix,
                total_files=len(discovered),
                registered_count=registered_count,
                unregistered_count=len(discovered) - registered_count,
                files=[
                    DiscoveredFileResponse(
                        s3_uri=f.s3_uri,
                        bucket_name=f.bucket_name,
                        key=f.key,
                        file_size_bytes=f.file_size_bytes,
                        last_modified=f.last_modified,
                        detected_format=f.detected_format,
                        is_registered=f.is_registered,
                        file_id=f.file_id,
                    )
                    for f in discovered
                ],
            )
        except Exception as e:
            LOGGER.error("Failed to discover files: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to discover files: {str(e)}",
            )

    @router.post("/auto-register", response_model=AutoRegisterResponse)
    async def auto_register_files(
        customer_id: str = Query(..., description="Customer ID"),
        request: AutoRegisterRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Auto-register discovered files with default metadata.

        Scans the bucket and registers all unregistered files with the provided
        default metadata.
        """
        if bucket_file_discovery is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="File discovery not configured",
            )

        try:
            # First discover files
            discovered = bucket_file_discovery.discover_files(
                bucket_name=request.bucket_name,
                prefix=request.prefix,
                file_formats=request.file_formats,
                max_files=request.max_files,
            )

            # Check registration status
            discovered = bucket_file_discovery.check_registration_status(
                discovered, file_registry, customer_id
            )

            # Auto-register
            registered, skipped, errors = bucket_file_discovery.auto_register_files(
                discovered_files=discovered,
                registry=file_registry,
                customer_id=customer_id,
                biosample_id=request.biosample_id,
                subject_id=request.subject_id,
                sequencing_platform=request.sequencing_platform,
            )

            return AutoRegisterResponse(
                registered_count=registered,
                skipped_count=skipped,
                errors=errors,
            )
        except Exception as e:
            LOGGER.error("Failed to auto-register files: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to auto-register files: {str(e)}",
            )

    # ========== File Search Endpoints ==========

    @router.post("/search")
    async def search_files(
        customer_id: str = Query(..., description="Customer ID"),
        request: FileSearchRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Search files by various criteria."""
        try:
            results = []

            if request.tag:
                results = file_registry.search_files_by_tag(customer_id, request.tag)
            elif request.biosample_id:
                results = file_registry.search_files_by_biosample(customer_id, request.biosample_id)
            else:
                # Return all files if no search criteria
                results = file_registry.list_customer_files(customer_id, limit=100)

            return {
                "customer_id": customer_id,
                "file_count": len(results),
                "files": [
                    {
                        "file_id": f.file_id,
                        "s3_uri": f.file_metadata.s3_uri,
                        "biosample_id": f.biosample_metadata.biosample_id,
                        "subject_id": f.biosample_metadata.subject_id,
                        "tags": f.tags,
                        "registered_at": f.registered_at,
                    }
                    for f in results
                ],
            }
        except Exception as e:
            LOGGER.error("Failed to search files: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to search files: {str(e)}",
            )

    @router.put("/{file_id}/tags")
    async def update_file_tags(
        file_id: str,
        tags: List[str] = Body(..., description="New tags for the file"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Update tags for a file."""
        try:
            success = file_registry.update_file_tags(file_id, tags)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File {file_id} not found",
                )
            return {"file_id": file_id, "tags": tags, "status": "updated"}
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to update file tags: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update file tags: {str(e)}",
            )


    @router.get("/{file_id}/download")
    async def get_file_download_url(
        file_id: str,
        expires_in: int = Query(
            3600,
            ge=60,
            le=86400,
            description="Expiry in seconds for the presigned URL (60–86400).",
        ),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get a presigned S3 download URL for a registered file.

        The file must exist and have a valid ``s3://bucket/key`` URI.
        """
        try:
            file = file_registry.get_file(file_id)
            if not file:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File {file_id} not found",
                )

            # Enforce customer-based ownership when we know who the
            # authenticated customer is. This mirrors the
            # verify_workset_ownership pattern in workset_api, using
            # DynamoDB customer_id as the authoritative ownership field
            # rather than any bucket-based comparison.
            user_customer_id = _get_authenticated_customer_id(current_user)
            if user_customer_id:
                if not verify_file_ownership(file, user_customer_id):
                    LOGGER.warning(
                        "Download denied: file %s has customer_id=%s but user has customer_id=%s",
                        file_id,
                        getattr(file, "customer_id", None),
                        user_customer_id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="File does not belong to this customer",
                    )

            s3_uri = getattr(file.file_metadata, "s3_uri", None)
            if not s3_uri or not isinstance(s3_uri, str) or not s3_uri.startswith("s3://"):
                LOGGER.error("File %s has invalid s3_uri: %r", file_id, s3_uri)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file_id} does not have a valid s3_uri",
                )

            # Parse s3://bucket/key
            without_scheme = s3_uri[5:]
            if "/" not in without_scheme:
                LOGGER.error("File %s s3_uri missing key segment: %r", file_id, s3_uri)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file_id} does not have a valid s3_uri",
                )
            bucket_name, object_key = without_scheme.split("/", 1)

            s3_client = boto3.client("s3")
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": object_key},
                ExpiresIn=expires_in,
            )

            return {"url": presigned_url}
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error(
                "Failed to generate download URL for file %s: %s", file_id, str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate download URL for file {file_id}",
            )

    @router.patch("/{file_id}")
    async def update_file_metadata(
        file_id: str,
        payload: Dict = Body(..., description="File metadata updates"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Update file metadata.

        All fields are optional - only provided fields will be updated.
        """
        try:
            LOGGER.info("PATCH /files/%s - Received payload: %s", file_id, payload)

            # Verify file exists
            file = file_registry.get_file(file_id)
            if not file:
                LOGGER.warning("File %s not found", file_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File {file_id} not found",
                )

            LOGGER.info("Updating file %s with payload", file_id)
            success = file_registry.update_file(
                file_id=file_id,
                file_metadata=payload.get("file_metadata"),
                biosample_metadata=payload.get("biosample_metadata"),
                sequencing_metadata=payload.get("sequencing_metadata"),
                tags=payload.get("tags"),
                read_number=payload.get("read_number"),
                paired_with=payload.get("paired_with"),
                quality_score=payload.get("quality_score"),
                percent_q30=payload.get("percent_q30"),
                is_positive_control=payload.get("is_positive_control"),
                is_negative_control=payload.get("is_negative_control"),
            )

            if not success:
                LOGGER.error("Failed to update file %s", file_id)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update file {file_id}",
                )

            # Return updated file
            updated_file = file_registry.get_file(file_id)
            LOGGER.info("Successfully updated file %s", file_id)
            return {
                "file_id": file_id,
                "status": "updated",
                "file": {
                    "file_id": updated_file.file_id,
                    "s3_uri": updated_file.file_metadata.s3_uri,
                    "biosample_id": updated_file.biosample_metadata.biosample_id,
                    "subject_id": updated_file.biosample_metadata.subject_id,
                    "updated_at": updated_file.updated_at,
                } if updated_file else None,
            }
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to update file metadata: %s", str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update file metadata: {str(e)}",
            )

    @router.post("/filesets/{fileset_id}/add-files")
    async def add_files_to_fileset(
        fileset_id: str,
        file_ids: List[str] = Body(..., description="File IDs to add"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Add files to an existing file set."""
        try:
            success = file_registry.add_files_to_fileset(fileset_id, file_ids)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FileSet {fileset_id} not found",
                )
            return {"fileset_id": fileset_id, "added_files": len(file_ids), "status": "updated"}
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to add files to fileset: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add files to fileset: {str(e)}",
            )

    @router.post("/{file_id}/add-to-fileset")
    async def add_file_to_fileset(
        file_id: str,
        request: AddFileToFilesetRequest = Body(..., description="Fileset to add the file to"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Convenience endpoint to add a single file to an existing file set.

        This mirrors the customer-level API the portal uses for individual files,
        but operates on a *registered* file identified by ``file_id``.
        """
        try:
            # Verify the file exists so we can return a clean 404 if not.
            file = file_registry.get_file(file_id)
            if not file:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File {file_id} not found",
                )

            success = file_registry.add_files_to_fileset(request.fileset_id, [file_id])
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FileSet {request.fileset_id} not found",
                )

            return {
                "fileset_id": request.fileset_id,
                "file_id": file_id,
                "status": "updated",
            }
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error(
                "Failed to add file %s to fileset %s: %s", file_id, request.fileset_id, str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add file {file_id} to fileset {request.fileset_id}",
            )

    @router.post("/filesets/{fileset_id}/remove-files")
    async def remove_files_from_fileset(
        fileset_id: str,
        file_ids: List[str] = Body(..., description="File IDs to remove"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Remove files from a file set."""
        try:
            success = file_registry.remove_files_from_fileset(fileset_id, file_ids)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FileSet {fileset_id} not found",
                )
            return {"fileset_id": fileset_id, "removed_files": len(file_ids), "status": "updated"}
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to remove files from fileset: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove files from fileset: {str(e)}",
            )

    @router.get("/filesets/{fileset_id}")
    async def get_fileset(
        fileset_id: str,
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get file set details."""
        try:
            fileset = file_registry.get_fileset(fileset_id)
            if not fileset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FileSet {fileset_id} not found",
                )
            return {
                "fileset_id": fileset.fileset_id,
                "customer_id": fileset.customer_id,
                "name": fileset.name,
                "description": fileset.description,
                "file_count": len(fileset.file_ids),
                "file_ids": fileset.file_ids,
                "tags": fileset.tags,
                "created_at": fileset.created_at,
                "updated_at": fileset.updated_at,
            }
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to get fileset: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get fileset: {str(e)}",
            )

    @router.get("/filesets/{fileset_id}/files")
    async def get_fileset_files(
        fileset_id: str,
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get all files in a file set."""
        try:
            files = file_registry.get_fileset_files(fileset_id)
            return {
                "fileset_id": fileset_id,
                "file_count": len(files),
                "files": [
                    {
                        "file_id": f.file_id,
                        "s3_uri": f.file_metadata.s3_uri,
                        "filename": f.file_metadata.filename,
                        "biosample_id": f.biosample_metadata.biosample_id,
                    }
                    for f in files
                ],
            }
        except Exception as e:
            LOGGER.error("Failed to get fileset files: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get fileset files: {str(e)}",
            )

    @router.patch("/filesets/{fileset_id}")
    async def update_fileset(
        fileset_id: str,
        name: Optional[str] = Body(None),
        description: Optional[str] = Body(None),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Update file set metadata."""
        try:
            success = file_registry.update_fileset_metadata(
                fileset_id=fileset_id,
                name=name,
                description=description,
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FileSet {fileset_id} not found",
                )
            return {"fileset_id": fileset_id, "status": "updated"}
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to update fileset: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update fileset: {str(e)}",
            )

    @router.post("/filesets/{fileset_id}/clone")
    async def clone_fileset(
        fileset_id: str,
        new_name: str = Body(..., embed=True),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Clone a file set with a new name."""
        try:
            cloned = file_registry.clone_fileset(fileset_id, new_name)
            if not cloned:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FileSet {fileset_id} not found",
                )
            return {
                "original_fileset_id": fileset_id,
                "new_fileset_id": cloned.fileset_id,
                "name": cloned.name,
                "file_count": len(cloned.file_ids),
                "status": "cloned",
            }
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to clone fileset: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to clone fileset: {str(e)}",
            )

    @router.get("/customer/{customer_id}/filesets")
    async def list_customer_filesets(
        customer_id: str,
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """List all file sets for a customer."""
        try:
            filesets = file_registry.list_customer_filesets(customer_id)
            return {
                "customer_id": customer_id,
                "fileset_count": len(filesets),
                "filesets": [
                    {
                        "fileset_id": fs.fileset_id,
                        "name": fs.name,
                        "description": fs.description,
                        "file_count": len(fs.file_ids),
                        "created_at": fs.created_at,
                    }
                    for fs in filesets
                ],
            }
        except Exception as e:
            LOGGER.error("Failed to list filesets: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list filesets: {str(e)}",
            )

    # ========== File-Workset Tracking Endpoints ==========

    @router.post("/workset-usage/record")
    async def record_file_workset_usage(
        file_id: str = Body(..., embed=True),
        workset_id: str = Body(..., embed=True),
        customer_id: str = Body(..., embed=True),
        usage_type: str = Body("input", embed=True),
        workset_state: Optional[str] = Body(None, embed=True),
        notes: Optional[str] = Body(None, embed=True),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Record that a file is used in a workset."""
        try:
            success = file_registry.record_file_workset_usage(
                file_id=file_id,
                workset_id=workset_id,
                customer_id=customer_id,
                usage_type=usage_type,
                workset_state=workset_state,
                notes=notes,
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to record file-workset usage",
                )
            return {"status": "recorded", "file_id": file_id, "workset_id": workset_id}
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to record file-workset usage: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to record file-workset usage: {str(e)}",
            )

    @router.get("/files/{file_id}/workset-history")
    async def get_file_workset_history(
        file_id: str,
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get all worksets that have used a file."""
        try:
            usages = file_registry.get_file_workset_history(file_id)
            return {
                "file_id": file_id,
                "usage_count": len(usages),
                "usages": [
                    {
                        "workset_id": u.workset_id,
                        "usage_type": u.usage_type,
                        "added_at": u.added_at,
                        "workset_state": u.workset_state,
                        "notes": u.notes,
                    }
                    for u in usages
                ],
            }
        except Exception as e:
            LOGGER.error("Failed to get file workset history: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get file workset history: {str(e)}",
            )

    @router.get("/worksets/{workset_id}/files")
    async def get_workset_file_usage(
        workset_id: str,
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get all files used in a workset."""
        try:
            usages = file_registry.get_workset_files(workset_id)
            return {
                "workset_id": workset_id,
                "file_count": len(usages),
                "files": [
                    {
                        "file_id": u.file_id,
                        "usage_type": u.usage_type,
                        "added_at": u.added_at,
                        "workset_state": u.workset_state,
                    }
                    for u in usages
                ],
            }
        except Exception as e:
            LOGGER.error("Failed to get workset files: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get workset files: {str(e)}",
            )

    @router.get("/worksets/{workset_id}/recreation-files")
    async def get_workset_recreation_files(
        workset_id: str,
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get all input files needed to recreate a workset."""
        try:
            files = file_registry.get_files_for_workset_recreation(workset_id)
            return {
                "workset_id": workset_id,
                "file_count": len(files),
                "files": [
                    {
                        "file_id": f.file_id,
                        "s3_uri": f.file_metadata.s3_uri,
                        "filename": f.file_metadata.filename,
                        "biosample_id": f.biosample_metadata.biosample_id,
                        "subject_id": f.biosample_metadata.subject_id,
                    }
                    for f in files
                ],
            }
        except Exception as e:
            LOGGER.error("Failed to get workset recreation files: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get workset recreation files: {str(e)}",
            )

    @router.post("/worksets/{workset_id}/update-state")
    async def update_workset_file_states(
        workset_id: str,
        new_state: str = Body(..., embed=True),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Update the workset state for all file usages in a workset."""
        try:
            updated = file_registry.update_workset_usage_state(workset_id, new_state)
            return {
                "workset_id": workset_id,
                "new_state": new_state,
                "updated_count": updated,
            }
        except Exception as e:
            LOGGER.error("Failed to update workset file states: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update workset file states: {str(e)}",
            )

    # ========== File Upload Endpoints ==========

    @router.post("/upload/presigned-url", response_model=PresignedUploadResponse)
    async def get_presigned_upload_url(
        customer_id: str = Query(..., description="Customer ID"),
        request: PresignedUploadRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get a presigned URL for uploading a file.

        For files larger than 5GB, use multipart upload.
        """
        if file_upload_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="File upload not configured",
            )

        try:
            object_key = generate_upload_path(
                customer_id=customer_id,
                filename=request.filename,
                prefix=request.prefix,
            )

            if request.use_multipart:
                # Initiate multipart upload
                upload_id = file_upload_manager.initiate_multipart_upload(
                    bucket_name=request.bucket_name,
                    object_key=object_key,
                    content_type=request.content_type,
                )

                # Get URL for first part
                part_url = file_upload_manager.generate_part_upload_url(
                    bucket_name=request.bucket_name,
                    object_key=object_key,
                    upload_id=upload_id,
                    part_number=1,
                )

                return PresignedUploadResponse(
                    upload_url=part_url,
                    object_key=object_key,
                    bucket_name=request.bucket_name,
                    method="PUT",
                    expires_in=file_upload_manager.default_expiration,
                    upload_id=upload_id,
                )
            else:
                # Single PUT upload
                presigned = file_upload_manager.generate_presigned_put_url(
                    bucket_name=request.bucket_name,
                    object_key=object_key,
                    content_type=request.content_type,
                )

                return PresignedUploadResponse(
                    upload_url=presigned.url,
                    object_key=object_key,
                    bucket_name=request.bucket_name,
                    method=presigned.method,
                    expires_in=presigned.expires_in,
                    fields=presigned.fields,
                )
        except Exception as e:
            LOGGER.error("Failed to generate presigned URL: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate presigned URL: {str(e)}",
            )

    @router.post("/upload/multipart/part-url")
    async def get_multipart_part_url(
        request: MultipartUploadPartRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get a presigned URL for uploading a multipart part."""
        if file_upload_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="File upload not configured",
            )

        try:
            url = file_upload_manager.generate_part_upload_url(
                bucket_name=request.bucket_name,
                object_key=request.object_key,
                upload_id=request.upload_id,
                part_number=request.part_number,
            )

            return {
                "upload_url": url,
                "part_number": request.part_number,
                "expires_in": file_upload_manager.default_expiration,
            }
        except Exception as e:
            LOGGER.error("Failed to generate part URL: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate part URL: {str(e)}",
            )

    @router.post("/upload/multipart/complete")
    async def complete_multipart_upload(
        request: CompleteMultipartRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Complete a multipart upload."""
        if file_upload_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="File upload not configured",
            )

        try:
            result = file_upload_manager.complete_multipart_upload(
                bucket_name=request.bucket_name,
                object_key=request.object_key,
                upload_id=request.upload_id,
                parts=request.parts,
            )

            return {
                "status": "completed",
                "location": result.get("location"),
                "etag": result.get("etag"),
                "s3_uri": f"s3://{request.bucket_name}/{request.object_key}",
            }
        except Exception as e:
            LOGGER.error("Failed to complete multipart upload: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to complete multipart upload: {str(e)}",
            )

    @router.post("/upload/multipart/abort")
    async def abort_multipart_upload(
        bucket_name: str = Query(...),
        object_key: str = Query(...),
        upload_id: str = Query(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Abort a multipart upload."""
        if file_upload_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="File upload not configured",
            )

        try:
            success = file_upload_manager.abort_multipart_upload(
                bucket_name=bucket_name,
                object_key=object_key,
                upload_id=upload_id,
            )

            return {"status": "aborted" if success else "failed"}
        except Exception as e:
            LOGGER.error("Failed to abort multipart upload: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to abort multipart upload: {str(e)}",
            )

    @router.post("/upload/verify", response_model=VerifyUploadResponse)
    async def verify_upload(
        request: VerifyUploadRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Verify an uploaded file."""
        if file_upload_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="File upload not configured",
            )

        try:
            is_valid, file_info = file_upload_manager.verify_upload(
                bucket_name=request.bucket_name,
                object_key=request.object_key,
                expected_size=request.expected_size,
                expected_etag=request.expected_etag,
            )

            return VerifyUploadResponse(
                is_valid=is_valid,
                size=file_info.get("size"),
                etag=file_info.get("etag"),
                content_type=file_info.get("content_type"),
                last_modified=file_info.get("last_modified"),
                error=file_info.get("error"),
            )
        except Exception as e:
            LOGGER.error("Failed to verify upload: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to verify upload: {str(e)}",
            )

    # ========== Manifest Generation Endpoints ==========

    @router.post("/manifest/generate", response_model=ManifestGenerationResponse)
    async def generate_manifest(
        customer_id: str = Query(..., description="Customer ID"),
        request: ManifestGenerationRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Generate a stage_samples.tsv manifest from registered files.

        Can generate from:
        - Specific file IDs
        - A file set
        - All files matching a biosample ID
        """
        try:
            files = []
            warnings = []

            # Get files based on request parameters
            if request.file_ids:
                for fid in request.file_ids:
                    f = file_registry.get_file(fid)
                    if f:
                        files.append(f)
                    else:
                        warnings.append(f"File {fid} not found")
            elif request.fileset_id:
                fileset = file_registry.get_fileset(request.fileset_id)
                if fileset:
                    for fid in fileset.file_ids:
                        f = file_registry.get_file(fid)
                        if f:
                            files.append(f)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"FileSet {request.fileset_id} not found",
                    )
            elif request.biosample_id:
                files = file_registry.search_files_by_biosample(customer_id, request.biosample_id)
            else:
                # Get all files for customer
                files = file_registry.list_customer_files(customer_id, limit=1000)

            if not files:
                return ManifestGenerationResponse(
                    tsv_content="",
                    sample_count=0,
                    file_count=0,
                    warnings=["No files found matching criteria"],
                )

            # Group files by biosample to create paired analysis inputs
            biosample_files: Dict[str, List] = {}
            for f in files:
                bid = f.biosample_metadata.biosample_id
                if bid not in biosample_files:
                    biosample_files[bid] = []
                biosample_files[bid].append(f)

            # Create AnalysisInput objects
            analysis_inputs = []
            for biosample_id, sample_files in biosample_files.items():
                # Find R1 and R2 files
                r1_files = [f for f in sample_files if f.read_number == 1]
                r2_files = [f for f in sample_files if f.read_number == 2]

                # Pair files
                for r1 in r1_files:
                    r2_uri = ""
                    # Find matching R2
                    for r2 in r2_files:
                        if r2.paired_with == r1.file_id or r1.paired_with == r2.file_id:
                            r2_uri = r2.file_metadata.s3_uri
                            break

                    # Get first file's metadata for defaults
                    seq_meta = r1.sequencing_metadata
                    bio_meta = r1.biosample_metadata

                    analysis_input = AnalysisInput(
                        sample_id=biosample_id,
                        external_sample_id=bio_meta.subject_id,
                        run_id=request.run_id,
                        sample_type=SampleType(bio_meta.sample_type) if bio_meta.sample_type in [e.value for e in SampleType] else SampleType.BLOOD,
                        seq_platform=SequencingPlatform(seq_meta.platform) if seq_meta.platform in [e.value for e in SequencingPlatform] else SequencingPlatform.ILLUMINA_NOVASEQ_X,
                        seq_vendor=SequencingVendor(seq_meta.vendor) if seq_meta.vendor in [e.value for e in SequencingVendor] else SequencingVendor.ILLUMINA,
                        lane=seq_meta.lane,
                        barcode_id=seq_meta.barcode_id,
                        r1_fastq=r1.file_metadata.s3_uri,
                        r2_fastq=r2_uri,
                        stage_target=request.stage_target,
                        concordance_dir=r1.concordance_vcf_path or "",
                        is_positive_control=r1.is_positive_control,
                        is_negative_control=r1.is_negative_control,
                    )
                    analysis_inputs.append(analysis_input)

            # Generate TSV
            tsv_content = generate_stage_samples_tsv(
                analysis_inputs,
                include_header=request.include_header,
            )

            return ManifestGenerationResponse(
                tsv_content=tsv_content,
                sample_count=len(analysis_inputs),
                file_count=len(files),
                warnings=warnings,
            )
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to generate manifest: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate manifest: {str(e)}",
            )

    @router.get("/manifest/template")
    async def get_manifest_template(
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Get the manifest template with column definitions."""
        from daylib.file_metadata import TSV_COLUMN_DEFINITIONS

        return {
            "columns": list(TSV_COLUMN_DEFINITIONS.keys()),
            "definitions": TSV_COLUMN_DEFINITIONS,
            "sample_types": [e.value for e in SampleType],
            "lib_preps": [e.value for e in LibraryPrep],
            "seq_vendors": [e.value for e in SequencingVendor],
            "seq_platforms": [e.value for e in SequencingPlatform],
        }

    @router.post("/{file_id}/manifest", response_model=ManifestGenerationResponse)
    async def generate_manifest_for_file(
        file_id: str,
        run_id: str = Query("R0", description="Run ID for the manifest"),
        stage_target: str = Query("/fsx/staged_sample_data/", description="Stage target directory"),
        include_header: bool = Query(True, description="Include TSV header row"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Generate a stage_samples.tsv manifest from a single file.

        This is a convenience endpoint for generating a manifest containing just one file.
        """
        try:
            # Get the file
            file = file_registry.get_file(file_id)
            if not file:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File {file_id} not found",
                )

            # Create AnalysisInput from the file
            seq_meta = file.sequencing_metadata
            bio_meta = file.biosample_metadata

            # Find paired file if this is R1
            r2_uri = ""
            if file.read_number == 1 and file.paired_with:
                paired_file = file_registry.get_file(file.paired_with)
                if paired_file:
                    r2_uri = paired_file.file_metadata.s3_uri

            analysis_input = AnalysisInput(
                sample_id=bio_meta.biosample_id,
                external_sample_id=bio_meta.subject_id,
                run_id=run_id,
                sample_type=SampleType(bio_meta.sample_type) if bio_meta.sample_type in [e.value for e in SampleType] else SampleType.BLOOD,
                seq_platform=SequencingPlatform(seq_meta.platform) if seq_meta.platform in [e.value for e in SequencingPlatform] else SequencingPlatform.ILLUMINA_NOVASEQ_X,
                seq_vendor=SequencingVendor(seq_meta.vendor) if seq_meta.vendor in [e.value for e in SequencingVendor] else SequencingVendor.ILLUMINA,
                lane=seq_meta.lane,
                barcode_id=seq_meta.barcode_id,
                r1_fastq=file.file_metadata.s3_uri,
                r2_fastq=r2_uri,
                stage_target=stage_target,
                concordance_dir=file.concordance_vcf_path or "",
                is_positive_control=file.is_positive_control,
                is_negative_control=file.is_negative_control,
            )

            # Generate TSV
            tsv_content = generate_stage_samples_tsv(
                [analysis_input],
                include_header=include_header,
            )

            return ManifestGenerationResponse(
                tsv_content=tsv_content,
                sample_count=1,
                file_count=1,
                warnings=[],
            )
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to generate manifest for file %s: %s", file_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate manifest for file {file_id}: {str(e)}",
            )

    @router.post("/filesets/{fileset_id}/manifest", response_model=ManifestGenerationResponse)
    async def generate_manifest_for_fileset(
        fileset_id: str,
        run_id: str = Query("R0", description="Run ID for the manifest"),
        stage_target: str = Query("/fsx/staged_sample_data/", description="Stage target directory"),
        include_header: bool = Query(True, description="Include TSV header row"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Generate a stage_samples.tsv manifest from a file set.

        This endpoint generates a manifest containing all files in the specified file set.
        """
        try:
            # Get the fileset
            fileset = file_registry.get_fileset(fileset_id)
            if not fileset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FileSet {fileset_id} not found",
                )

            # Get all files in the fileset
            files = []
            for fid in fileset.file_ids:
                f = file_registry.get_file(fid)
                if f:
                    files.append(f)

            if not files:
                return ManifestGenerationResponse(
                    tsv_content="",
                    sample_count=0,
                    file_count=0,
                    warnings=["No files found in fileset"],
                )

            # Group files by biosample to create paired analysis inputs
            biosample_files: Dict[str, List] = {}
            for f in files:
                bid = f.biosample_metadata.biosample_id
                if bid not in biosample_files:
                    biosample_files[bid] = []
                biosample_files[bid].append(f)

            # Create AnalysisInput objects
            analysis_inputs = []
            for biosample_id, sample_files in biosample_files.items():
                # Find R1 and R2 files
                r1_files = [f for f in sample_files if f.read_number == 1]
                r2_files = [f for f in sample_files if f.read_number == 2]

                # Pair files
                for r1 in r1_files:
                    r2_uri = ""
                    # Find matching R2
                    for r2 in r2_files:
                        if r2.paired_with == r1.file_id or r1.paired_with == r2.file_id:
                            r2_uri = r2.file_metadata.s3_uri
                            break

                    # Get first file's metadata for defaults
                    seq_meta = r1.sequencing_metadata
                    bio_meta = r1.biosample_metadata

                    analysis_input = AnalysisInput(
                        sample_id=biosample_id,
                        external_sample_id=bio_meta.subject_id,
                        run_id=run_id,
                        sample_type=SampleType(bio_meta.sample_type) if bio_meta.sample_type in [e.value for e in SampleType] else SampleType.BLOOD,
                        seq_platform=SequencingPlatform(seq_meta.platform) if seq_meta.platform in [e.value for e in SequencingPlatform] else SequencingPlatform.ILLUMINA_NOVASEQ_X,
                        seq_vendor=SequencingVendor(seq_meta.vendor) if seq_meta.vendor in [e.value for e in SequencingVendor] else SequencingVendor.ILLUMINA,
                        lane=seq_meta.lane,
                        barcode_id=seq_meta.barcode_id,
                        r1_fastq=r1.file_metadata.s3_uri,
                        r2_fastq=r2_uri,
                        stage_target=stage_target,
                        concordance_dir=r1.concordance_vcf_path or "",
                        is_positive_control=r1.is_positive_control,
                        is_negative_control=r1.is_negative_control,
                    )
                    analysis_inputs.append(analysis_input)

            # Generate TSV
            tsv_content = generate_stage_samples_tsv(
                analysis_inputs,
                include_header=include_header,
            )

            return ManifestGenerationResponse(
                tsv_content=tsv_content,
                sample_count=len(analysis_inputs),
                file_count=len(files),
                warnings=[],
            )
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Failed to generate manifest for fileset %s: %s", fileset_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate manifest for fileset {fileset_id}: {str(e)}",
            )

    # ========== Bucket Browsing Endpoints ==========

    @router.get("/buckets/{bucket_id}/browse", response_model=BrowseBucketResponse)
    async def browse_bucket(
        bucket_id: str,
        customer_id: str = Query(..., description="Customer ID"),
        prefix: str = Query("", description="Current directory prefix"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Browse files and folders in a linked S3 bucket.

        Returns a hierarchical view of files and folders at the specified prefix.
        Files are checked against the FileRegistry to show registration status.
        """
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )

        # Get linked bucket and verify ownership
        bucket = linked_bucket_manager.get_bucket(bucket_id)
        if bucket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bucket not found",
            )

        if bucket.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bucket belongs to a different customer",
            )

        if not bucket.can_list:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot list objects in this bucket",
            )

        # Apply prefix restriction if set
        effective_prefix = prefix
        if bucket.prefix_restriction:
            if not prefix:
                effective_prefix = bucket.prefix_restriction
            elif not prefix.startswith(bucket.prefix_restriction):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prefix is outside allowed prefix restriction",
                )

        # Normalize prefix (ensure it ends with / if not empty)
        if effective_prefix and not effective_prefix.endswith("/"):
            effective_prefix += "/"
        if effective_prefix == "/":
            effective_prefix = ""

        try:
            import boto3
            from botocore.exceptions import ClientError

            session_kwargs = {"region_name": bucket.region or "us-west-2"}
            s3 = boto3.Session(**session_kwargs).client("s3")

            # List objects at the current prefix
            items: List[BrowseItem] = []
            folders_seen = set()

            paginator = s3.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(
                Bucket=bucket.bucket_name,
                Prefix=effective_prefix,
                Delimiter="/",
            )

            for page in page_iterator:
                # Add folders (common prefixes)
                for cp in page.get("CommonPrefixes", []):
                    folder_prefix = cp["Prefix"]
                    folder_name = folder_prefix.rstrip("/").split("/")[-1]
                    if folder_name and folder_prefix not in folders_seen:
                        folders_seen.add(folder_prefix)
                        items.append(BrowseItem(
                            name=folder_name,
                            key=folder_prefix,
                            is_folder=True,
                            size_bytes=None,
                            last_modified=None,
                            file_format=None,
                            is_registered=False,
                            file_id=None,
                        ))

                # Add files
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    # Skip the prefix itself (directory placeholder)
                    if key == effective_prefix or key.endswith("/"):
                        continue

                    file_name = key.split("/")[-1]
                    detected_format = detect_file_format(key)

                    # Check registration status
                    is_registered = False
                    file_id = None
                    if file_registry is not None:
                        s3_uri = f"s3://{bucket.bucket_name}/{key}"
                        file_id = generate_file_id(s3_uri, customer_id)
                        existing = file_registry.get_file(file_id)
                        is_registered = existing is not None

                    items.append(BrowseItem(
                        name=file_name,
                        key=key,
                        is_folder=False,
                        size_bytes=obj["Size"],
                        last_modified=obj["LastModified"].isoformat() if obj.get("LastModified") else None,
                        file_format=detected_format,
                        is_registered=is_registered,
                        file_id=file_id if is_registered else None,
                    ))

            # Sort: folders first, then files alphabetically
            items.sort(key=lambda x: (not x.is_folder, x.name.lower()))

            # Build breadcrumbs
            breadcrumbs = [{"name": "Root", "prefix": ""}]
            if effective_prefix:
                parts = effective_prefix.rstrip("/").split("/")
                accumulated = ""
                for part in parts:
                    accumulated = f"{accumulated}{part}/"
                    breadcrumbs.append({"name": part, "prefix": accumulated})

            # Calculate parent prefix
            parent_prefix = None
            if effective_prefix:
                parts = effective_prefix.rstrip("/").split("/")
                if len(parts) > 1:
                    parent_prefix = "/".join(parts[:-1]) + "/"
                else:
                    parent_prefix = ""

            return BrowseBucketResponse(
                bucket_id=bucket_id,
                bucket_name=bucket.bucket_name,
                display_name=bucket.display_name or bucket.bucket_name,
                current_prefix=effective_prefix,
                parent_prefix=parent_prefix,
                breadcrumbs=breadcrumbs,
                items=items,
                can_write=bucket.can_write and not bucket.read_only,
                is_read_only=bucket.read_only,
                total_items=len(items),
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            LOGGER.error("S3 error browsing bucket %s: %s", bucket_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to browse bucket: {error_code}",
            )
        except Exception as e:
            LOGGER.error("Error browsing bucket %s: %s", bucket_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to browse bucket: {str(e)}",
            )

    @router.post("/buckets/{bucket_id}/folders", response_model=CreateFolderResponse)
    async def create_folder(
        bucket_id: str,
        customer_id: str = Query(..., description="Customer ID"),
        prefix: str = Query("", description="Parent directory prefix"),
        request: CreateFolderRequest = Body(...),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Create a new folder (prefix) in a linked S3 bucket.

        Only available for buckets with write permissions and not marked read-only.
        """
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )

        bucket = linked_bucket_manager.get_bucket(bucket_id)
        if bucket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bucket not found",
            )

        if bucket.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bucket belongs to a different customer",
            )

        # Check write permissions
        if bucket.read_only:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bucket is marked as read-only",
            )

        if not bucket.can_write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No write permission to this bucket",
            )

        # Validate folder name (S3 naming constraints)
        folder_name = request.folder_name.strip()
        if not folder_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Folder name cannot be empty",
            )

        # Disallow certain characters that are problematic in S3
        invalid_chars = ["\\", "\x00", "\n", "\r"]
        for char in invalid_chars:
            if char in folder_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Folder name contains invalid character",
                )

        # Apply prefix restriction
        effective_prefix = prefix
        if bucket.prefix_restriction:
            if not prefix:
                effective_prefix = bucket.prefix_restriction
            elif not prefix.startswith(bucket.prefix_restriction):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prefix is outside allowed prefix restriction",
                )

        # Normalize and build folder key
        # Ensure prefix ends with / (but avoid double slashes)
        if effective_prefix:
            effective_prefix = effective_prefix.rstrip("/") + "/"
        folder_key = f"{effective_prefix}{folder_name}/"

        try:
            import boto3
            from botocore.exceptions import ClientError

            session_kwargs = {"region_name": bucket.region or "us-west-2"}
            s3 = boto3.Session(**session_kwargs).client("s3")

            # Create folder by putting an empty object with trailing slash
            s3.put_object(
                Bucket=bucket.bucket_name,
                Key=folder_key,
                Body=b"",
            )

            # Also create a .hold file to prevent the folder from disappearing
            # (S3 doesn't truly have folders, so an empty folder marker can disappear)
            hold_file_key = folder_key.rstrip("/") + "/.hold"
            s3.put_object(
                Bucket=bucket.bucket_name,
                Key=hold_file_key,
                Body=b"",
            )

            LOGGER.info(
                "Created folder %s in bucket %s for customer %s (with .hold file)",
                folder_key, bucket.bucket_name, customer_id
            )

            return CreateFolderResponse(
                success=True,
                folder_key=folder_key,
                message=f"Folder '{folder_name}' created successfully",
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            LOGGER.error("S3 error creating folder in %s: %s", bucket_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create folder: {error_code}",
            )

    @router.delete("/buckets/{bucket_id}/files", response_model=DeleteFileResponse)
    async def delete_file(
        bucket_id: str,
        customer_id: str = Query(..., description="Customer ID"),
        file_key: str = Query(..., description="S3 key of file to delete"),
        current_user: Optional[Dict] = Depends(auth_dependency),
    ):
        """Delete a file from a linked S3 bucket.

        Only available for:
        - Buckets with write permissions
        - Buckets not marked read-only
        - Files that are NOT registered in the FileRegistry
        """
        if linked_bucket_manager is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Bucket management not configured",
            )

        bucket = linked_bucket_manager.get_bucket(bucket_id)
        if bucket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bucket not found",
            )

        if bucket.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bucket belongs to a different customer",
            )

        # Check write permissions
        if bucket.read_only:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bucket is marked as read-only",
            )

        if not bucket.can_write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No write permission to this bucket",
            )

        # Check prefix restriction
        if bucket.prefix_restriction:
            if not file_key.startswith(bucket.prefix_restriction):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="File is outside allowed prefix restriction",
                )

        # Check if file is registered - PREVENT deletion of registered files
        if file_registry is not None:
            s3_uri = f"s3://{bucket.bucket_name}/{file_key}"
            file_id = generate_file_id(s3_uri, customer_id)
            existing = file_registry.get_file(file_id)
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot delete a registered file. Unregister the file first.",
                )

        try:
            import boto3
            from botocore.exceptions import ClientError

            session_kwargs = {"region_name": bucket.region or "us-west-2"}
            s3 = boto3.Session(**session_kwargs).client("s3")

            # Check file exists before deleting
            try:
                s3.head_object(Bucket=bucket.bucket_name, Key=file_key)
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="File not found",
                    )
                raise

            # Delete the file
            s3.delete_object(Bucket=bucket.bucket_name, Key=file_key)

            LOGGER.info(
                "Deleted file %s from bucket %s for customer %s",
                file_key, bucket.bucket_name, customer_id
            )

            return DeleteFileResponse(
                success=True,
                deleted_key=file_key,
                message=f"File deleted successfully",
            )

        except HTTPException:
            raise
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            LOGGER.error("S3 error deleting file from %s: %s", bucket_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file: {error_code}",
            )

    return router

