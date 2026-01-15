"""
File Registration API endpoints for Daylily portal.

Provides REST API for file registration, metadata capture, and file set management.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from daylib.file_registry import (
    BiosampleMetadata,
    FileMetadata,
    FileRegistration,
    FileRegistry,
    FileSet,
    SequencingMetadata,
)

LOGGER = logging.getLogger("daylily.file_api")


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


class BulkImportResponse(BaseModel):
    """Response model for bulk import."""
    imported_count: int
    failed_count: int
    fileset_id: Optional[str] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)


def create_file_api_router(
    file_registry: FileRegistry,
    auth_dependency: Optional[Callable] = None,
) -> APIRouter:
    """Create FastAPI router for file registration endpoints.

    Args:
        file_registry: FileRegistry instance
        auth_dependency: Optional authentication dependency function

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
            file_id = f"file-{uuid.uuid4().hex[:12]}"
            
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
            LOGGER.error("Failed to register file: %s", e)
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
            LOGGER.error("Failed to list files: %s", e)
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
            LOGGER.error("Failed to create fileset: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create fileset: {str(e)}",
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
                LOGGER.error("Failed to create fileset: %s", e)
        
        return BulkImportResponse(
            imported_count=imported_count,
            failed_count=failed_count,
            fileset_id=fileset_id,
            errors=errors,
        )
    
    return router

