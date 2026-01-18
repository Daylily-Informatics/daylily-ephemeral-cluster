"""
Biospecimen API endpoints for Daylily portal.

Provides REST API for managing Subject, Biospecimen, Biosample, and Library entities.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from daylib.biospecimen import (
    BiospecimenRegistry,
    Biospecimen,
    Biosample,
    Library,
    Subject,
    generate_biospecimen_id,
    generate_biosample_id,
    generate_library_id,
    generate_subject_id,
)

LOGGER = logging.getLogger("daylily.biospecimen_api")


# =============================================================================
# Pydantic Models for API
# =============================================================================

class SubjectRequest(BaseModel):
    """Request model for creating/updating a subject."""
    identifier: str = Field(..., description="External identifier for the subject")
    display_name: Optional[str] = None
    sex: Optional[str] = Field(None, pattern="^(male|female|unknown|other)$")
    date_of_birth: Optional[str] = None
    species: str = "Homo sapiens"
    cohort: Optional[str] = None
    external_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class SubjectResponse(BaseModel):
    """Response model for subject."""
    subject_id: str
    customer_id: str
    display_name: Optional[str] = None
    sex: Optional[str] = None
    date_of_birth: Optional[str] = None
    species: str = "Homo sapiens"
    cohort: Optional[str] = None
    external_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class BiospecimenRequest(BaseModel):
    """Request model for creating/updating a biospecimen."""
    identifier: str = Field(..., description="External identifier for the biospecimen")
    subject_id: str = Field(..., description="Subject ID this biospecimen belongs to")
    biospecimen_type: str = "tissue"
    collection_date: Optional[str] = None
    collection_method: Optional[str] = None
    preservation_method: Optional[str] = None
    tissue_type: Optional[str] = None
    anatomical_site: Optional[str] = None
    tumor_fraction: Optional[float] = None
    is_tumor: bool = False
    produced_date: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class BiospecimenResponse(BaseModel):
    """Response model for biospecimen."""
    biospecimen_id: str
    customer_id: str
    subject_id: str
    biospecimen_type: str
    collection_date: Optional[str] = None
    collection_method: Optional[str] = None
    preservation_method: Optional[str] = None
    tissue_type: Optional[str] = None
    anatomical_site: Optional[str] = None
    tumor_fraction: Optional[float] = None
    is_tumor: bool = False
    produced_date: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class BiosampleRequest(BaseModel):
    """Request model for creating/updating a biosample."""
    identifier: str = Field(..., description="External identifier for the biosample")
    biospecimen_id: str = Field(..., description="Biospecimen ID this biosample belongs to")
    sample_type: str = "blood"
    tissue_type: Optional[str] = None
    anatomical_site: Optional[str] = None
    collection_date: Optional[str] = None
    collection_method: Optional[str] = None
    preservation_method: Optional[str] = None
    tumor_fraction: Optional[float] = None
    tumor_grade: Optional[str] = None
    tumor_stage: Optional[str] = None
    is_tumor: bool = False
    matched_normal_id: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class BiosampleResponse(BaseModel):
    """Response model for biosample."""
    biosample_id: str
    customer_id: str
    biospecimen_id: str
    subject_id: str
    sample_type: str
    tissue_type: Optional[str] = None
    anatomical_site: Optional[str] = None
    collection_date: Optional[str] = None
    collection_method: Optional[str] = None
    preservation_method: Optional[str] = None
    tumor_fraction: Optional[float] = None
    tumor_grade: Optional[str] = None
    tumor_stage: Optional[str] = None
    is_tumor: bool = False
    matched_normal_id: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class LibraryRequest(BaseModel):
    """Request model for creating/updating a library."""
    identifier: str = Field(..., description="External identifier for the library")
    biosample_id: str = Field(..., description="Biosample ID this library belongs to")
    library_prep: str = "pcr_free_wgs"
    library_kit: Optional[str] = None
    target_insert_size: Optional[int] = None
    capture_kit: Optional[str] = None
    target_regions_bed: Optional[str] = None
    target_coverage: Optional[float] = None
    target_read_count: Optional[int] = None
    protocol_id: Optional[str] = None
    lab_id: Optional[str] = None
    prep_date: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class LibraryResponse(BaseModel):
    """Response model for library."""
    library_id: str
    customer_id: str
    biosample_id: str
    library_prep: str
    library_kit: Optional[str] = None
    target_insert_size: Optional[int] = None
    capture_kit: Optional[str] = None
    target_regions_bed: Optional[str] = None
    target_coverage: Optional[float] = None
    target_read_count: Optional[int] = None
    protocol_id: Optional[str] = None
    lab_id: Optional[str] = None
    prep_date: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class HierarchyResponse(BaseModel):
    """Response model for subject hierarchy."""
    subject: SubjectResponse
    biospecimens: List[Dict[str, Any]] = Field(default_factory=list)


class StatisticsResponse(BaseModel):
    """Response model for biospecimen statistics."""
    subjects: int
    biospecimens: int
    biosamples: int
    libraries: int


# =============================================================================
# Router Factory
# =============================================================================

def create_biospecimen_router(
    registry: BiospecimenRegistry,
    get_customer_id: Callable[[Request], str],
) -> APIRouter:
    """
    Create a FastAPI router for biospecimen API endpoints.

    Args:
        registry: BiospecimenRegistry instance
        get_customer_id: Callable that takes a Request and returns the current customer ID.
                        Should raise HTTPException(401) if customer cannot be resolved.

    Returns:
        Configured APIRouter
    """
    router = APIRouter(prefix="/api/biospecimen", tags=["biospecimen"])

    # =========================================================================
    # Subject Endpoints
    # =========================================================================

    @router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
    async def create_subject(http_request: Request, request: SubjectRequest):
        """Create a new subject."""
        customer_id = get_customer_id(http_request)
        subject_id = generate_subject_id(customer_id, request.identifier)

        subject = Subject(
            subject_id=subject_id,
            customer_id=customer_id,
            display_name=request.display_name or request.identifier,
            sex=request.sex,
            date_of_birth=request.date_of_birth,
            species=request.species,
            cohort=request.cohort,
            external_ids=request.external_ids,
            notes=request.notes,
            tags=request.tags,
        )

        if not registry.create_subject(subject):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subject with identifier '{request.identifier}' already exists"
            )

        return SubjectResponse(**subject.__dict__)

    @router.get("/subjects", response_model=List[SubjectResponse])
    async def list_subjects(http_request: Request, limit: int = Query(100, ge=1, le=1000)):
        """List all subjects for the current customer."""
        customer_id = get_customer_id(http_request)
        subjects = registry.list_subjects(customer_id, limit=limit)
        return [SubjectResponse(**s.__dict__) for s in subjects]

    @router.get("/subjects/{subject_id}", response_model=SubjectResponse)
    async def get_subject(http_request: Request, subject_id: str):
        """Get a subject by ID."""
        subject = registry.get_subject(subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Verify customer ownership
        customer_id = get_customer_id(http_request)
        if subject.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return SubjectResponse(**subject.__dict__)

    @router.get("/subjects/{subject_id}/hierarchy", response_model=Dict[str, Any])
    async def get_subject_hierarchy(http_request: Request, subject_id: str):
        """Get complete hierarchy for a subject including biosamples and libraries."""
        subject = registry.get_subject(subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        customer_id = get_customer_id(http_request)
        if subject.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return registry.get_subject_hierarchy(subject_id)

    @router.put("/subjects/{subject_id}", response_model=SubjectResponse)
    async def update_subject(http_request: Request, subject_id: str, request: SubjectRequest):
        """Update a subject."""
        subject = registry.get_subject(subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        customer_id = get_customer_id(http_request)
        if subject.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Update fields
        subject.display_name = request.display_name or request.identifier
        subject.sex = request.sex
        subject.date_of_birth = request.date_of_birth
        subject.species = request.species
        subject.cohort = request.cohort
        subject.external_ids = request.external_ids
        subject.notes = request.notes
        subject.tags = request.tags

        if not registry.update_subject(subject):
            raise HTTPException(status_code=500, detail="Failed to update subject")

        return SubjectResponse(**subject.__dict__)

    # =========================================================================
    # Biosample Endpoints
    # =========================================================================

    @router.post("/biosamples", response_model=BiosampleResponse, status_code=status.HTTP_201_CREATED)
    async def create_biosample(http_request: Request, request: BiosampleRequest):
        """Create a new biosample."""
        customer_id = get_customer_id(http_request)

        # Verify biospecimen exists and belongs to customer
        biospecimen = registry.get_biospecimen(request.biospecimen_id)
        if not biospecimen:
            raise HTTPException(status_code=404, detail="Biospecimen not found")
        if biospecimen.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Biospecimen does not belong to customer")

        biosample_id = generate_biosample_id(customer_id, request.identifier)

        biosample = Biosample(
            biosample_id=biosample_id,
            customer_id=customer_id,
            biospecimen_id=request.biospecimen_id,
            subject_id=biospecimen.subject_id,  # Get subject_id from biospecimen
            sample_type=request.sample_type,
            tissue_type=request.tissue_type,
            anatomical_site=request.anatomical_site,
            collection_date=request.collection_date,
            collection_method=request.collection_method,
            preservation_method=request.preservation_method,
            tumor_fraction=request.tumor_fraction,
            tumor_grade=request.tumor_grade,
            tumor_stage=request.tumor_stage,
            is_tumor=request.is_tumor,
            matched_normal_id=request.matched_normal_id,
            notes=request.notes,
            tags=request.tags,
        )

        if not registry.create_biosample(biosample):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Biosample with identifier '{request.identifier}' already exists"
            )

        return BiosampleResponse(**biosample.__dict__)

    @router.get("/biosamples", response_model=List[BiosampleResponse])
    async def list_biosamples(
        http_request: Request,
        limit: int = Query(100, ge=1, le=1000),
        subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    ):
        """List biosamples for the current customer."""
        customer_id = get_customer_id(http_request)

        if subject_id:
            biosamples = registry.list_biosamples_for_subject(subject_id)
            # Filter to customer
            biosamples = [b for b in biosamples if b.customer_id == customer_id]
        else:
            biosamples = registry.list_biosamples(customer_id, limit=limit)

        return [BiosampleResponse(**b.__dict__) for b in biosamples]

    @router.get("/biosamples/{biosample_id}", response_model=BiosampleResponse)
    async def get_biosample(http_request: Request, biosample_id: str):
        """Get a biosample by ID."""
        biosample = registry.get_biosample(biosample_id)
        if not biosample:
            raise HTTPException(status_code=404, detail="Biosample not found")

        customer_id = get_customer_id(http_request)
        if biosample.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return BiosampleResponse(**biosample.__dict__)

    @router.put("/biosamples/{biosample_id}", response_model=BiosampleResponse)
    async def update_biosample(http_request: Request, biosample_id: str, request: BiosampleRequest):
        """Update a biosample."""
        biosample = registry.get_biosample(biosample_id)
        if not biosample:
            raise HTTPException(status_code=404, detail="Biosample not found")

        customer_id = get_customer_id(http_request)
        if biosample.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Update fields (subject_id cannot be changed)
        biosample.sample_type = request.sample_type
        biosample.tissue_type = request.tissue_type
        biosample.anatomical_site = request.anatomical_site
        biosample.collection_date = request.collection_date
        biosample.collection_method = request.collection_method
        biosample.preservation_method = request.preservation_method
        biosample.tumor_fraction = request.tumor_fraction
        biosample.tumor_grade = request.tumor_grade
        biosample.tumor_stage = request.tumor_stage
        biosample.is_tumor = request.is_tumor
        biosample.matched_normal_id = request.matched_normal_id
        biosample.notes = request.notes
        biosample.tags = request.tags

        if not registry.update_biosample(biosample):
            raise HTTPException(status_code=500, detail="Failed to update biosample")

        return BiosampleResponse(**biosample.__dict__)

    # =========================================================================
    # Library Endpoints
    # =========================================================================

    @router.post("/libraries", response_model=LibraryResponse, status_code=status.HTTP_201_CREATED)
    async def create_library(http_request: Request, request: LibraryRequest):
        """Create a new library."""
        customer_id = get_customer_id(http_request)

        # Verify biosample exists and belongs to customer
        biosample = registry.get_biosample(request.biosample_id)
        if not biosample:
            raise HTTPException(status_code=404, detail="Biosample not found")
        if biosample.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Biosample does not belong to customer")

        library_id = generate_library_id(customer_id, request.identifier)

        library = Library(
            library_id=library_id,
            customer_id=customer_id,
            biosample_id=request.biosample_id,
            library_prep=request.library_prep,
            library_kit=request.library_kit,
            target_insert_size=request.target_insert_size,
            capture_kit=request.capture_kit,
            target_regions_bed=request.target_regions_bed,
            target_coverage=request.target_coverage,
            target_read_count=request.target_read_count,
            protocol_id=request.protocol_id,
            lab_id=request.lab_id,
            prep_date=request.prep_date,
            notes=request.notes,
            tags=request.tags,
        )

        if not registry.create_library(library):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Library with identifier '{request.identifier}' already exists"
            )

        return LibraryResponse(**library.__dict__)

    @router.get("/libraries", response_model=List[LibraryResponse])
    async def list_libraries(
        http_request: Request,
        limit: int = Query(100, ge=1, le=1000),
        biosample_id: Optional[str] = Query(None, description="Filter by biosample ID"),
    ):
        """List libraries for the current customer."""
        customer_id = get_customer_id(http_request)

        if biosample_id:
            libraries = registry.list_libraries_for_biosample(biosample_id)
            libraries = [lib for lib in libraries if lib.customer_id == customer_id]
        else:
            libraries = registry.list_libraries(customer_id, limit=limit)

        return [LibraryResponse(**lib.__dict__) for lib in libraries]

    @router.get("/libraries/{library_id}", response_model=LibraryResponse)
    async def get_library(http_request: Request, library_id: str):
        """Get a library by ID."""
        library = registry.get_library(library_id)
        if not library:
            raise HTTPException(status_code=404, detail="Library not found")

        customer_id = get_customer_id(http_request)
        if library.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return LibraryResponse(**library.__dict__)

    @router.put("/libraries/{library_id}", response_model=LibraryResponse)
    async def update_library(http_request: Request, library_id: str, request: LibraryRequest):
        """Update a library."""
        library = registry.get_library(library_id)
        if not library:
            raise HTTPException(status_code=404, detail="Library not found")

        customer_id = get_customer_id(http_request)
        if library.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Update fields (biosample_id cannot be changed)
        library.library_prep = request.library_prep
        library.library_kit = request.library_kit
        library.target_insert_size = request.target_insert_size
        library.capture_kit = request.capture_kit
        library.target_regions_bed = request.target_regions_bed
        library.target_coverage = request.target_coverage
        library.target_read_count = request.target_read_count
        library.protocol_id = request.protocol_id
        library.lab_id = request.lab_id
        library.prep_date = request.prep_date
        library.notes = request.notes
        library.tags = request.tags

        if not registry.update_library(library):
            raise HTTPException(status_code=500, detail="Failed to update library")

        return LibraryResponse(**library.__dict__)

    # =========================================================================
    # Statistics Endpoint
    # =========================================================================

    @router.get("/statistics", response_model=StatisticsResponse)
    async def get_statistics(http_request: Request):
        """Get biospecimen statistics for the current customer."""
        customer_id = get_customer_id(http_request)
        stats = registry.get_statistics(customer_id)
        return StatisticsResponse(**stats)

    return router

