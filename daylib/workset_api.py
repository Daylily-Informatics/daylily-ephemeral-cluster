"""FastAPI web interface for workset monitoring and management.

Provides REST API and web dashboard for workset operations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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

    return app

