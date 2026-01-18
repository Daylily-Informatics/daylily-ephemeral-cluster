"""FastAPI web interface for workset monitoring and management.

Provides REST API and web dashboard for workset operations.

This module uses shared Pydantic models from daylib.routes.dependencies.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import logging
import os
import re
import tarfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
import yaml  # type: ignore[import-untyped]

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, EmailStr
from starlette.middleware.sessions import SessionMiddleware

from daylib.config import Settings, get_settings
from daylib.workset_state_db import ErrorCategory, WorksetPriority, WorksetState, WorksetStateDB
from daylib.workset_scheduler import WorksetScheduler

# Import shared Pydantic models from routes module
from daylib.routes.dependencies import (
    WorksetCreate,
    WorksetResponse,
    WorksetStateUpdate,
    QueueStats,
    SchedulingStats,
    CustomerCreate,
    CustomerResponse,
    WorksetValidationResponse,
    WorkYamlGenerateRequest,
    ChangePasswordRequest,
    APITokenCreateRequest,
    PortalFileAutoRegisterRequest,
    PortalFileAutoRegisterResponse,
    # Utility functions
    format_file_size as _format_file_size,
    get_file_icon as _get_file_icon,
    calculate_cost_with_efficiency as _calculate_cost_with_efficiency,
    convert_customer_for_template as _convert_customer_for_template,
    verify_workset_ownership,
)

# Optional imports for authentication
try:
    from daylib.workset_auth import CognitoAuth, create_auth_dependency
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    CognitoAuth = None  # type: ignore[misc, assignment]
    create_auth_dependency = None  # type: ignore[assignment]

from daylib.workset_customer import CustomerManager, CustomerConfig
from daylib.workset_validation import WorksetValidator

# Optional integration layer import
try:
    from daylib.workset_integration import WorksetIntegration
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False
    WorksetIntegration = None  # type: ignore[misc, assignment]

# File management imports
try:
    from daylib.file_api import create_file_api_router
    from daylib.file_registry import FileRegistry, BucketFileDiscovery
    from daylib.s3_bucket_validator import S3BucketValidator, LinkedBucketManager
    FILE_MANAGEMENT_AVAILABLE = True
except ImportError:
    FILE_MANAGEMENT_AVAILABLE = False
    create_file_api_router = None  # type: ignore[assignment]
    FileRegistry = None  # type: ignore[misc, assignment]
    BucketFileDiscovery = None  # type: ignore[misc, assignment]
    S3BucketValidator = None  # type: ignore[misc, assignment]
    LinkedBucketManager = None  # type: ignore[misc, assignment]

# Biospecimen layer imports
try:
    from daylib.biospecimen import BiospecimenRegistry
    from daylib.biospecimen_api import create_biospecimen_router
    BIOSPECIMEN_AVAILABLE = True
except ImportError:
    BIOSPECIMEN_AVAILABLE = False
    BiospecimenRegistry = None  # type: ignore[misc, assignment]
    create_biospecimen_router = None  # type: ignore[assignment]

# Manifest storage imports
try:
    from daylib.manifest_registry import ManifestRegistry, ManifestTooLargeError
    MANIFEST_STORAGE_AVAILABLE = True
except ImportError:
    MANIFEST_STORAGE_AVAILABLE = False
    ManifestRegistry = None  # type: ignore[misc, assignment]
    ManifestTooLargeError = None  # type: ignore[misc, assignment]

LOGGER = logging.getLogger("daylily.workset_api")


# Note: Pydantic models and utility functions are now imported from daylib.routes.dependencies
# See the imports at the top of this file for:
# - WorksetCreate, WorksetResponse, WorksetStateUpdate, QueueStats, SchedulingStats
# - CustomerCreate, CustomerResponse, WorksetValidationResponse, WorkYamlGenerateRequest
# - ChangePasswordRequest, APITokenCreateRequest
# - PortalFileAutoRegisterRequest, PortalFileAutoRegisterResponse
# - _format_file_size, _get_file_icon, _calculate_cost_with_efficiency, _convert_customer_for_template
# - verify_workset_ownership


def create_app(
    state_db: WorksetStateDB,
    scheduler: Optional[WorksetScheduler] = None,
    cognito_auth: Optional[CognitoAuth] = None,
    customer_manager: Optional[CustomerManager] = None,
    validator: Optional[WorksetValidator] = None,
    integration: Optional["WorksetIntegration"] = None,
    file_registry: Optional["FileRegistry"] = None,
    manifest_registry: Optional["ManifestRegistry"] = None,
    enable_auth: bool = False,
    settings: Optional[Settings] = None,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        state_db: Workset state database
        scheduler: Optional workset scheduler
        cognito_auth: Optional Cognito authentication
        customer_manager: Optional customer manager
        validator: Optional workset validator
        integration: Optional integration layer for S3 sync
        file_registry: Optional file registry for file management
        enable_auth: Enable authentication (requires cognito_auth)
        settings: Optional Settings instance (uses get_settings() if not provided)

    Returns:
        FastAPI application instance
    """
    # Load settings from environment if not provided
    if settings is None:
        settings = get_settings()

    # Validate demo mode is not enabled in production
    settings.validate_demo_mode()
    if settings.demo_mode:
        LOGGER.warning(
            "DEMO MODE ENABLED - First-customer fallback is active. "
            "This should NEVER be used in production!"
        )

    # Configure logging based on settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Set specific loggers to DEBUG for file management (in development)
    if settings.is_development:
        logging.getLogger("daylily.file_api").setLevel(logging.DEBUG)
        logging.getLogger("daylily.file_registry").setLevel(logging.DEBUG)
        logging.getLogger("daylily.s3_bucket_validator").setLevel(logging.DEBUG)
        logging.getLogger("daylily.manifest_registry").setLevel(logging.DEBUG)

    LOGGER.info("Creating Daylily application (env=%s, log_level=%s)", settings.daylily_env, settings.log_level)

    # AWS configuration from settings
    region = settings.get_effective_region()
    profile = settings.aws_profile

    # Initialize manifest registry (optional but enabled by default when available)
    if MANIFEST_STORAGE_AVAILABLE and manifest_registry is None and ManifestRegistry is not None:
        try:
            manifest_registry = ManifestRegistry(
                table_name=settings.daylily_manifest_table,
                region=region,
                profile=profile,
            )
            LOGGER.info("Manifest storage enabled (table: %s)", settings.daylily_manifest_table)
        except Exception as e:
            LOGGER.warning("Failed to initialize ManifestRegistry: %s", str(e))
            manifest_registry = None

    # Initialize LinkedBucketManager early so portal routes can use it
    linked_bucket_manager = None
    # BucketFileDiscovery is optional; keep a stable binding for portal routes
    bucket_file_discovery = None
    if FILE_MANAGEMENT_AVAILABLE and LinkedBucketManager is not None:
        try:
            linked_bucket_manager = LinkedBucketManager(
                table_name=settings.daylily_linked_buckets_table,
                region=region,
                profile=profile,
            )
            LOGGER.info("LinkedBucketManager initialized for portal and file API")
        except Exception as e:
            LOGGER.warning("Failed to create LinkedBucketManager: %s", str(e))

    app = FastAPI(
        title="Daylily Workset Monitor API",
        description="REST API for workset monitoring and management with multi-tenant support",
        version="2.0.0",
    )

    # Enable CORS with settings-based configuration
    try:
        cors_origins = settings.get_cors_origins()
    except ValueError as e:
        LOGGER.error("CORS configuration error: %s", e)
        raise
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add session middleware for portal authentication
    if settings.is_production and settings.session_secret_key == "daylily-dev-secret-change-in-production":
        LOGGER.warning("Using default session secret in production - this is insecure!")
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

    # ========== Global Exception Handlers ==========
    # Import custom exceptions
    from daylib.exceptions import DaylilyException

    @app.exception_handler(DaylilyException)
    async def daylily_exception_handler(request: Request, exc: DaylilyException):
        """Handle all DaylilyException subclasses with consistent JSON response."""
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())[:8]
        LOGGER.error(
            "DaylilyException: code=%s, message=%s, request_id=%s, path=%s",
            exc.code, exc.message, request_id, request.url.path
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(request_id=request_id),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions with consistent JSON response."""
        # Don't intercept HTTPException - let FastAPI handle those
        if isinstance(exc, HTTPException):
            raise exc

        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())[:8]
        LOGGER.exception(
            "Unhandled exception: %s, request_id=%s, path=%s",
            str(exc), request_id, request.url.path
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={
                "error": "An internal error occurred",
                "code": "INTERNAL_ERROR",
                "details": {"exception_type": type(exc).__name__} if settings.is_development else {},
                "request_id": request_id,
            },
        )

    # Add request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add request ID to all requests for tracing."""
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

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
        # Create JWT auth as optional - we'll also accept session auth
        jwt_auth_dependency = create_auth_dependency(cognito_auth, optional=True)
        LOGGER.info("Authentication enabled - API endpoints will accept session or JWT auth")
    else:
        jwt_auth_dependency = None
        LOGGER.info("Authentication disabled - API endpoints will not require authentication")

    # Create a combined auth dependency that accepts either:
    # 1. Session-based auth from portal (user_email in session)
    # 2. JWT token auth from API calls (Authorization header)
    # 3. API key auth via X-API-Key header (resolved via CustomerManager)
    def get_current_user(request: Request) -> Optional[Dict]:
        """Combined auth dependency for portal session and API JWT auth."""
        # First try session-based auth (portal)
        if hasattr(request, "session"):
            user_email = request.session.get("user_email")
            if user_email:
                return {
                    "email": user_email,
                    "auth_type": "session",
                    "authenticated": True,
                }

        # Then try JWT auth if available (check Authorization header)
        if jwt_auth_dependency and cognito_auth:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    from fastapi.security import HTTPAuthorizationCredentials
                    token = auth_header[7:]  # Remove "Bearer " prefix
                    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
                    user = cognito_auth.get_current_user(credentials)
                    if user:
                        user["auth_type"] = "jwt"
                        return user
                except HTTPException:
                    # JWT auth failed, but that's ok - we already checked session
                    pass
                except Exception as e:
                    LOGGER.debug("JWT auth check failed: %s", str(e))

        # Finally, try API key auth via X-API-Key header if customer_manager is available
        if customer_manager:
            api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
            if api_key:
                try:
                    customer = customer_manager.get_customer_by_api_key(api_key)
                except Exception as e:  # pragma: no cover - defensive logging
                    LOGGER.warning("API key lookup failed: %s", str(e))
                    customer = None

                if customer:
                    return {
                        "email": customer.email,
                        "customer_id": customer.customer_id,
                        "auth_type": "api_key",
                        "authenticated": True,
                    }

        # No valid authentication found
        if enable_auth:
            # For API endpoints that require auth, raise an error
            # But only for non-portal routes (portal uses session redirects)
            if not request.url.path.startswith("/portal"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required - provide session cookie or Bearer token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return None

    LOGGER.info("Combined session/JWT authentication configured")

    def get_customer_for_session(request: Request) -> Tuple[Optional[Dict[Any, Any]], Optional[CustomerConfig]]:
        """Get the customer for the currently logged-in user.

        Looks up the customer by the user's email from the session.
        Returns (customer, customer_config) tuple or (None, None) if not found.
        """
        if not customer_manager:
            return None, None

        user_email = None
        if hasattr(request, "session"):
            user_email = request.session.get("user_email")

        if not user_email:
            return None, None

        customer_config = customer_manager.get_customer_by_email(user_email)
        if customer_config:
            return _convert_customer_for_template(customer_config), customer_config

        return None, None

    def get_customer_with_demo_fallback(
        request: Request,
        require_auth: bool = True,
    ) -> Optional[Dict[Any, Any]]:
        """Get customer from session with optional demo mode fallback.

        Args:
            request: The HTTP request
            require_auth: If True, raise HTTPException when no customer found (unless demo mode)

        Returns:
            Customer dict or None

        Raises:
            HTTPException(401): If require_auth=True and no customer found (and demo mode disabled)
        """
        # Try session first
        customer, _config = get_customer_for_session(request)
        if customer:
            return customer

        # Demo mode fallback - only if explicitly enabled
        if settings.demo_mode and customer_manager:
            customers = customer_manager.list_customers()
            if customers:
                LOGGER.debug("Demo mode: using first customer as fallback")
                result: Dict[Any, Any] = _convert_customer_for_template(customers[0])
                return result

        # No customer found
        if require_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Please log in.",
            )

        return None

    @app.get("/", tags=["health"])
    async def root():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "daylily-workset-monitor",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workset {workset_id} not found after update",
            )
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

    # ========== Cost Estimation Endpoints ==========

    @app.post("/api/estimate-cost", tags=["utilities"])
    async def estimate_workset_cost(
        pipeline_type: str = Body(..., embed=True),
        reference_genome: str = Body("GRCh38", embed=True),
        sample_count: int = Body(1, embed=True),
        estimated_coverage: float = Body(30.0, embed=True),
        priority: str = Body("normal", embed=True),
        data_size_gb: float = Body(0.0, embed=True),
    ):
        """Estimate cost for a workset based on parameters.

        Uses pipeline type, sample count, and coverage to estimate:
        - vCPU hours required
        - Estimated duration
        - Cost in USD (based on current spot pricing)

        Note: These are estimates. Actual costs depend on data complexity,
        spot market conditions, and cluster utilization.
        """
        # Base vCPU-hours per sample by pipeline type
        base_vcpu_hours_per_sample = {
            "germline": 4.0,
            "somatic": 8.0,
            "rnaseq": 2.0,
            "wgs": 12.0,
            "wes": 3.0,
        }

        base_hours = base_vcpu_hours_per_sample.get(pipeline_type, 4.0)

        # Adjust for coverage (30x is baseline)
        coverage_factor = estimated_coverage / 30.0

        # Calculate total vCPU hours
        vcpu_hours = base_hours * sample_count * coverage_factor

        # Estimate duration assuming 16 vCPU instance average
        avg_vcpus = 16
        duration_hours = vcpu_hours / avg_vcpus

        # Base cost per vCPU-hour (typical spot pricing)
        cost_per_vcpu_hour = {
            "urgent": 0.08,  # On-demand pricing
            "high": 0.08,
            "normal": 0.03,  # Spot pricing
            "low": 0.015,    # Interruptible spot
        }

        base_cost = cost_per_vcpu_hour.get(priority, 0.03)

        # Calculate compute cost
        compute_cost = vcpu_hours * base_cost

        # Storage cost estimate ($0.023/GB-month, estimate 1 week)
        # Data size = sample_count * 50GB average per sample if not provided
        if data_size_gb <= 0:
            data_size_gb = sample_count * 50.0
        storage_cost = data_size_gb * 0.023 / 4  # ~1 week

        # FSx Lustre cost (if applicable) - $0.14/GB-month
        fsx_cost = data_size_gb * 0.14 / 4  # ~1 week

        # Data transfer cost (estimate 10% of data out at $0.09/GB)
        transfer_cost = data_size_gb * 0.10 * 0.09

        # Apply efficiency formula to storage costs
        # Formula: total_size / (total_size - (total_size * 0.98))
        efficiency_multiplier = _calculate_cost_with_efficiency(data_size_gb)
        adjusted_storage_cost = storage_cost * efficiency_multiplier if efficiency_multiplier > 0 else storage_cost

        # Total estimated cost
        total_cost = compute_cost + adjusted_storage_cost + fsx_cost + transfer_cost

        # Priority multipliers
        priority_multiplier = {
            "urgent": 2.0,
            "high": 1.5,
            "normal": 1.0,
            "low": 0.6,
        }
        multiplier = priority_multiplier.get(priority, 1.0)

        return {
            "estimated_cost_usd": round(total_cost * multiplier, 2),
            "compute_cost_usd": round(compute_cost * multiplier, 2),
            "storage_cost_usd": round(adjusted_storage_cost + fsx_cost, 2),
            "transfer_cost_usd": round(transfer_cost, 2),
            "vcpu_hours": round(vcpu_hours, 1),
            "estimated_duration_hours": round(duration_hours, 1),
            "estimated_duration_minutes": int(duration_hours * 60),
            "data_size_gb": round(data_size_gb, 1),
            "efficiency_multiplier": round(efficiency_multiplier, 2),
            "pipeline_type": pipeline_type,
            "sample_count": sample_count,
            "priority": priority,
            "cost_breakdown": {
                "compute": f"${compute_cost * multiplier:.2f}",
                "storage": f"${adjusted_storage_cost:.2f}",
                "fsx": f"${fsx_cost:.2f}",
                "transfer": f"${transfer_cost:.2f}",
            },
            "notes": [
                "Costs are estimates based on typical workloads",
                f"Priority '{priority}' applies {multiplier}x multiplier",
                f"Storage efficiency multiplier: {efficiency_multiplier:.2f}x",
                "Actual costs depend on spot market and data complexity",
            ],
        }

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
                LOGGER.error("Failed to list files: %s", str(e))
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
                LOGGER.error("Failed to upload file: %s", str(e))
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

                # Also create a .hold file to prevent the folder from disappearing
                # (S3 doesn't truly have folders, so an empty folder marker can disappear)
                hold_file_key = folder_key.rstrip("/") + "/.hold"
                s3.put_object(Bucket=config.s3_bucket, Key=hold_file_key, Body=b"")

                LOGGER.info(f"Created folder {folder_key} in bucket {config.s3_bucket} (with .hold file)")
                return {"success": True, "folder": folder_key}

            except Exception as e:
                LOGGER.error("Failed to create folder: %s", str(e))
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
                LOGGER.error("Failed to preview file: %s", str(e))
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
                LOGGER.error("Failed to generate download URL: %s", str(e))
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
                LOGGER.error("Failed to delete file: %s", str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )


        # ========== Customer Manifest Endpoints ==========

        @app.get("/api/customers/{customer_id}/manifests", tags=["customer-manifests"])
        async def list_customer_manifests(
            customer_id: str,
            limit: int = Query(200, ge=1, le=500),
        ):
            """List saved manifests for a customer (metadata only)."""
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )
            if not manifest_registry:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Manifest storage not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            manifests = manifest_registry.list_customer_manifests(customer_id, limit=limit)
            return {"manifests": manifests}

        @app.post(
            "/api/customers/{customer_id}/manifests",
            tags=["customer-manifests"],
            status_code=status.HTTP_201_CREATED,
        )
        async def save_customer_manifest(
            customer_id: str,
            tsv_content: str = Body(..., embed=True),
            name: Optional[str] = Body(None, embed=True),
            description: Optional[str] = Body(None, embed=True),
        ):
            """Save a stage_samples.tsv manifest for later reuse."""
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )
            if not manifest_registry:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Manifest storage not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            try:
                saved = manifest_registry.save_manifest(
                    customer_id=customer_id,
                    tsv_content=tsv_content,
                    name=name,
                    description=description,
                )
            except ManifestTooLargeError as e:
                raise HTTPException(status_code=413, detail=str(e))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

            download_url = f"/api/customers/{customer_id}/manifests/{saved.manifest_id}/download"
            return {
                "manifest": saved.to_metadata_dict(),
                "download_url": download_url,
            }

        @app.get("/api/customers/{customer_id}/manifests/{manifest_id}", tags=["customer-manifests"])
        async def get_customer_manifest_metadata(customer_id: str, manifest_id: str):
            """Get saved manifest metadata (not content)."""
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )
            if not manifest_registry:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Manifest storage not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            m = manifest_registry.get_manifest(customer_id=customer_id, manifest_id=manifest_id)
            if not m:
                raise HTTPException(status_code=404, detail="Manifest not found")
            return {"manifest": m.to_metadata_dict()}

        @app.get(
            "/api/customers/{customer_id}/manifests/{manifest_id}/download",
            tags=["customer-manifests"],
        )
        async def download_customer_manifest(customer_id: str, manifest_id: str):
            """Download the saved stage_samples.tsv content."""
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )
            if not manifest_registry:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Manifest storage not configured",
                )

            config = customer_manager.get_customer_config(customer_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found",
                )

            tsv = manifest_registry.get_manifest_tsv(customer_id=customer_id, manifest_id=manifest_id)
            if tsv is None:
                raise HTTPException(status_code=404, detail="Manifest not found")

            filename = f"{manifest_id}.stage_samples.tsv"
            return Response(
                content=tsv,
                media_type="text/tab-separated-values",
                headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
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
            all_worksets: List[Dict[str, Any]] = []
            if state:
                try:
                    ws_state = WorksetState(state)
                    all_worksets = state_db.list_worksets_by_state(ws_state, limit=limit)
                except ValueError:
                    # Invalid state value - return all states
                    for ws_state in WorksetState:
                        batch = state_db.list_worksets_by_state(ws_state, limit=limit)
                        all_worksets.extend(batch)
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

        @app.get("/api/customers/{customer_id}/worksets/archived", tags=["customer-worksets"])
        async def list_archived_worksets(customer_id: str):
            """List all archived worksets for a customer."""
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

            # Get all archived worksets and filter by customer's bucket
            all_archived = state_db.list_archived_worksets(limit=500)
            customer_archived = [
                w for w in all_archived if w.get("bucket") == config.s3_bucket
            ]
            return customer_archived

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

            # Verify workset belongs to this customer (by customer_id, not bucket)
            if not verify_workset_ownership(workset, customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            return workset

        @app.post("/api/customers/{customer_id}/worksets", tags=["customer-worksets"])
        async def create_customer_workset(
            request: Request,
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
            samples: Optional[List[Dict[str, Any]]] = Body(None, embed=True),
            yaml_content: Optional[str] = Body(None, embed=True),
            manifest_id: Optional[str] = Body(None, embed=True),
            manifest_tsv_content: Optional[str] = Body(None, embed=True),
        ):
            """Create a new workset for a customer from the portal form.

            This endpoint registers the workset in both DynamoDB (for UI state tracking)
            and writes S3 sentinel files (for processing engine discovery).

            Samples can be provided via:
            - samples: Direct list of sample dicts
            - yaml_content: YAML with samples array
            - manifest_id: ID of a saved manifest (retrieves TSV from ManifestRegistry)
            - manifest_tsv_content: Raw stage_samples.tsv content
            """
            if not customer_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Customer management not configured",
                )

            # Validate customer_id - reject null, empty, or 'Unknown'
            if not customer_id or customer_id.strip() == "" or customer_id == "Unknown":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Valid customer ID is required. Please log in with a registered account.",
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

            # Use control-plane bucket (monitor bucket) for workset registration
            bucket = None
            if integration and integration.bucket:
                bucket = integration.bucket
            if not bucket:
                # Get from settings via app.state
                app_settings = request.app.state.settings
                bucket = app_settings.get_control_bucket()
            if not bucket:
                error_detail = (
                    "Control bucket is not configured for workset registration. "
                    "Please set DAYLILY_CONTROL_BUCKET or DAYLILY_MONITOR_BUCKET environment variable, "
                    "or pass --control-bucket to the API server. "
                    "See CONTROL_BUCKET_CONFIGURATION_GUIDE.md for details."
                )
                LOGGER.error(error_detail)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_detail,
                )

            # Use provided prefix or generate one based on workset ID
            prefix = s3_prefix.strip() if s3_prefix else ""
            # Strip s3:// prefix from prefix if provided
            if prefix.startswith("s3://"):
                prefix = prefix[5:]
                # Extract bucket and prefix if full S3 URI was provided
                if "/" in prefix:
                    parts = prefix.split("/", 1)
                    # bucket = parts[0]  # Could use this if needed
                    prefix = parts[1]
            if not prefix:
                prefix = f"worksets/{workset_id}/"
            if not prefix.endswith("/"):
                prefix += "/"

            # Process samples from various sources (priority: samples > manifest_id > manifest_tsv_content > yaml_content)
            workset_samples = samples or []
            manifest_tsv_for_s3 = None  # Raw TSV content to write to S3

            # Try manifest_id first (if no direct samples provided)
            if manifest_id and not workset_samples:
                if not manifest_registry:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Manifest storage not configured; cannot use manifest_id",
                    )
                tsv = manifest_registry.get_manifest_tsv(customer_id=customer_id, manifest_id=manifest_id)
                if not tsv:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Manifest {manifest_id} not found for customer {customer_id}",
                    )
                # Import parse function
                from daylib.manifest_registry import parse_tsv_to_samples
                workset_samples = parse_tsv_to_samples(tsv)
                manifest_tsv_for_s3 = tsv
                LOGGER.info("Loaded %d samples from saved manifest %s", len(workset_samples), manifest_id)

            # Try manifest_tsv_content next
            if manifest_tsv_content and not workset_samples:
                from daylib.manifest_registry import parse_tsv_to_samples
                workset_samples = parse_tsv_to_samples(manifest_tsv_content)
                manifest_tsv_for_s3 = manifest_tsv_content
                LOGGER.info("Parsed %d samples from provided TSV content", len(workset_samples))

            # Finally try YAML content
            if yaml_content and not workset_samples:
                try:
                    yaml_data = yaml.safe_load(yaml_content)
                    if yaml_data and isinstance(yaml_data.get("samples"), list):
                        workset_samples = yaml_data["samples"]
                except Exception as e:
                    LOGGER.warning("Failed to parse YAML content: %s", str(e))

            # Normalize sample format and add default status
            normalized_samples = []
            for sample in workset_samples:
                if isinstance(sample, dict):
                    normalized = {
                        "sample_id": sample.get("sample_id") or sample.get("id") or sample.get("name", "unknown"),
                        "r1_file": sample.get("r1_file") or sample.get("r1") or sample.get("fq1", ""),
                        "r2_file": sample.get("r2_file") or sample.get("r2") or sample.get("fq2", ""),
                        "status": sample.get("status", "pending"),
                    }
                    normalized_samples.append(normalized)

            # Issue 4: Validate that workset has at least one sample
            if len(normalized_samples) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Workset must contain at least one sample. Please upload files, specify an S3 path with samples, provide a saved manifest ID, or upload a manifest TSV.",
                )

            # Store additional metadata from the form
            metadata = {
                "workset_name": workset_name,
                "pipeline_type": pipeline_type,
                "reference_genome": reference_genome,
                "notification_email": notification_email,
                "enable_qc": enable_qc,
                "archive_results": archive_results,
                "submitted_by": customer_id,
                "priority": priority,
                "samples": normalized_samples,
                "sample_count": len(normalized_samples),
                "data_bucket": config.s3_bucket,
                "data_buckets": [config.s3_bucket] if config.s3_bucket else [],
            }

            # If we have raw TSV content (from manifest), pass it for direct S3 write
            if manifest_tsv_for_s3:
                metadata["stage_samples_tsv"] = manifest_tsv_for_s3

            # Use integration layer if available for unified registration
            if integration:
                success = integration.register_workset(
                    workset_id=workset_id,
                    bucket=bucket,
                    prefix=prefix,
                    priority=priority,
                    metadata=metadata,
                    customer_id=customer_id,
                    write_s3=True,
                    write_dynamodb=True,
                )
            else:
                # Fallback to DynamoDB-only registration
                try:
                    ws_priority = WorksetPriority(priority)
                except ValueError:
                    ws_priority = WorksetPriority.NORMAL

                success = state_db.register_workset(
                    workset_id=workset_id,
                    bucket=bucket,
                    prefix=prefix,
                    priority=ws_priority,
                    metadata=metadata,
                    customer_id=customer_id,
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

            # Verify workset belongs to this customer (by customer_id, not bucket)
            if not verify_workset_ownership(workset, customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            state_db.update_state(workset_id, WorksetState.ERROR, "Cancelled by user")
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

            # Verify workset belongs to this customer (by customer_id, not bucket)
            if not verify_workset_ownership(workset, customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            # Reset to ready state for retry
            state_db.update_state(workset_id, WorksetState.READY, "Retry requested by user")
            updated = state_db.get_workset(workset_id)
            return updated

        @app.post("/api/customers/{customer_id}/worksets/{workset_id}/archive", tags=["customer-worksets"])
        async def archive_customer_workset(
            request: Request,
            customer_id: str,
            workset_id: str,
            reason: Optional[str] = Body(None, embed=True),
        ):
            """Archive a customer's workset.

            Moves workset to archived state. Archived worksets can be restored.
            Admins can archive any workset.
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

            workset = state_db.get_workset(workset_id)
            if not workset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workset {workset_id} not found",
                )

            # Check if user is admin (can archive any workset) or owns the workset (by customer_id)
            is_admin = getattr(request, "session", {}).get("is_admin", False)
            if not is_admin and not verify_workset_ownership(workset, customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            # Archive the workset
            success = state_db.archive_workset(
                workset_id, archived_by=customer_id, archive_reason=reason
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to archive workset",
                )

            # Optionally move S3 files to archive prefix
            bucket = workset.get("bucket")
            prefix = workset.get("prefix", "").rstrip("/")
            if bucket and prefix and integration:
                try:
                    archive_prefix = f"archived/{prefix.split('/')[-1]}/"
                    s3 = boto3.client("s3")
                    # Copy files to archive location
                    paginator = s3.get_paginator("list_objects_v2")
                    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                        for obj in page.get("Contents", []):
                            old_key = obj["Key"]
                            new_key = old_key.replace(prefix, archive_prefix.rstrip("/"), 1)
                            s3.copy_object(
                                Bucket=bucket,
                                CopySource={"Bucket": bucket, "Key": old_key},
                                Key=new_key,
                            )
                            s3.delete_object(Bucket=bucket, Key=old_key)
                    LOGGER.info("Moved workset %s files to archive: %s", workset_id, archive_prefix)
                except Exception as e:
                    LOGGER.warning("Failed to move workset files to archive: %s", str(e))

            return state_db.get_workset(workset_id)

        @app.post("/api/customers/{customer_id}/worksets/{workset_id}/delete", tags=["customer-worksets"])
        async def delete_customer_workset(
            request: Request,
            customer_id: str,
            workset_id: str,
            hard_delete: bool = Body(False, embed=True),
            reason: Optional[str] = Body(None, embed=True),
        ):
            """Delete a customer's workset.

            Args:
                hard_delete: If True, permanently removes all S3 data and DynamoDB record.
                            If False (default), marks as deleted but preserves data.

            Admins can delete any workset.
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

            workset = state_db.get_workset(workset_id)
            if not workset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workset {workset_id} not found",
                )

            # Check if user is admin (can delete any workset) or owns the workset (by customer_id)
            is_admin = getattr(request, "session", {}).get("is_admin", False)
            if not is_admin and not verify_workset_ownership(workset, customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            # If hard delete, remove S3 files first
            if hard_delete:
                bucket = workset.get("bucket")
                prefix = workset.get("prefix", "").rstrip("/") + "/"
                if bucket and prefix:
                    try:
                        s3 = boto3.client("s3")
                        paginator = s3.get_paginator("list_objects_v2")
                        objects_to_delete = []
                        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                            for obj in page.get("Contents", []):
                                objects_to_delete.append({"Key": obj["Key"]})

                        if objects_to_delete:
                            # Delete in batches of 1000 (S3 limit)
                            for i in range(0, len(objects_to_delete), 1000):
                                batch = objects_to_delete[i:i + 1000]
                                s3.delete_objects(
                                    Bucket=bucket,
                                    Delete={"Objects": batch},
                                )
                            LOGGER.info(
                                "Deleted %d S3 objects for workset %s",
                                len(objects_to_delete),
                                workset_id,
                            )
                    except Exception as e:
                        LOGGER.error("Failed to delete S3 objects for workset %s: %s", workset_id, str(e))
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to delete S3 data: {str(e)}",
                        )

            # Update DynamoDB state
            success = state_db.delete_workset(
                workset_id,
                deleted_by=customer_id,
                delete_reason=reason,
                hard_delete=hard_delete,
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete workset from database",
                )

            if hard_delete:
                return {"status": "deleted", "workset_id": workset_id, "hard_delete": True}
            return state_db.get_workset(workset_id)

        @app.post("/api/customers/{customer_id}/worksets/{workset_id}/restore", tags=["customer-worksets"])
        async def restore_customer_workset(
            customer_id: str,
            workset_id: str,
        ):
            """Restore an archived workset back to ready state."""
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

            # Verify workset belongs to this customer (by customer_id, not bucket)
            if not verify_workset_ownership(workset, customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            if workset.get("state") != "archived":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only archived worksets can be restored",
                )

            success = state_db.restore_workset(workset_id, restored_by=customer_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to restore workset",
                )

            return state_db.get_workset(workset_id)

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

            # Verify workset belongs to this customer (by customer_id, not bucket)
            if not verify_workset_ownership(workset, customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workset does not belong to this customer",
                )

            # Return workset state_history as logs
            history = workset.get("state_history", [])
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

    # ========== S3 Discovery Endpoint ==========

    @app.post("/api/s3/discover-samples", tags=["utilities"])
    async def discover_samples_from_s3(
        request: Request,
        bucket: str = Body(..., embed=True),
        prefix: str = Body(..., embed=True),
        current_user: Optional[Dict] = Depends(get_current_user),
    ):
        """Discover FASTQ samples from an S3 path.

        Lists files in the given S3 location and automatically pairs R1/R2 files
        into samples. Also attempts to parse daylily_work.yaml if present.
        """
        samples = []
        yaml_content = None
        files_found = []
        all_keys_found = []  # For debugging

        LOGGER.info("S3 Discovery: Starting discovery for bucket=%s, prefix=%s", bucket, prefix)

        try:
            # Create boto3 session using settings
            app_settings = request.app.state.settings
            session_kwargs = {"region_name": app_settings.get_effective_region()}
            if app_settings.aws_profile:
                session_kwargs["profile_name"] = app_settings.aws_profile
            session = boto3.Session(**session_kwargs)
            s3_client = session.client("s3")

            # Normalize prefix - handle various input formats
            # Strip whitespace and handle both with/without trailing slash
            normalized_prefix = prefix.strip()
            if normalized_prefix:
                # Remove leading slash if present
                normalized_prefix = normalized_prefix.lstrip("/")
                # Ensure trailing slash for listing
                if not normalized_prefix.endswith("/"):
                    normalized_prefix += "/"

            LOGGER.info("S3 Discovery: Using normalized prefix: '%s'", normalized_prefix)

            # List objects in the S3 path
            paginator = s3_client.get_paginator("list_objects_v2")
            total_objects = 0

            for page in paginator.paginate(Bucket=bucket, Prefix=normalized_prefix):
                for obj in page.get("Contents", []):
                    total_objects += 1
                    key = obj["Key"]
                    filename = key.split("/")[-1]
                    all_keys_found.append(key)

                    # Skip directory markers (empty keys ending with /)
                    if not filename:
                        continue

                    # Check for daylily_work.yaml (case-insensitive)
                    if filename.lower() == "daylily_work.yaml":
                        LOGGER.info("S3 Discovery: Found daylily_work.yaml at %s", key)
                        try:
                            response = s3_client.get_object(Bucket=bucket, Key=key)
                            yaml_content = response["Body"].read().decode("utf-8")
                            LOGGER.info("S3 Discovery: Successfully read daylily_work.yaml")
                        except Exception as e:
                            LOGGER.warning("S3 Discovery: Failed to read daylily_work.yaml: %s", str(e))

                    # Check for FASTQ files - extended patterns
                    fastq_extensions = [".fastq", ".fq", ".fastq.gz", ".fq.gz", ".fastq.bz2", ".fq.bz2"]
                    if any(filename.lower().endswith(ext) for ext in fastq_extensions):
                        LOGGER.debug("S3 Discovery: Found FASTQ file: %s", filename)
                        files_found.append({
                            "key": key,
                            "filename": filename,
                            "size": obj.get("Size", 0),
                        })

            LOGGER.info("S3 Discovery: Found %d total objects, %d FASTQ files", total_objects, len(files_found))

            # If we found a daylily_work.yaml, parse samples from it
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
                        LOGGER.info("S3 Discovery: Parsed %d samples from YAML", len(samples))
                except Exception as e:
                    LOGGER.warning("S3 Discovery: Failed to parse daylily_work.yaml: %s", str(e))

            # If no samples from YAML, try to pair FASTQ files
            if not samples and files_found:
                LOGGER.info("S3 Discovery: No YAML samples, attempting to pair %d FASTQ files", len(files_found))

                # Pattern matching for R1/R2 pairs - more flexible patterns
                # Supports: sample_R1.fastq.gz, sample.R1.fastq.gz, sample_1.fastq.gz,
                #           sample_R1_001.fastq.gz, sample_S1_L001_R1_001.fastq.gz (Illumina)
                r1_patterns = [
                    # Standard patterns: sample_R1.fastq.gz, sample.R1.fastq.gz
                    re.compile(r"^(.+?)[._](R1|r1)[._]?.*\.(fastq|fq)(\.gz|\.bz2)?$", re.IGNORECASE),
                    # Numeric patterns: sample_1.fastq.gz
                    re.compile(r"^(.+?)[._]1[._]?.*\.(fastq|fq)(\.gz|\.bz2)?$", re.IGNORECASE),
                    # Illumina patterns: sample_S1_L001_R1_001.fastq.gz
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

                    # Try R1 patterns
                    for pattern in r1_patterns:
                        match = pattern.match(filename)
                        if match:
                            sample_name = match.group(1)
                            r1_files[sample_name] = f["key"]
                            LOGGER.debug("S3 Discovery: Matched R1 file %s -> sample %s", filename, sample_name)
                            matched = True
                            break

                    if not matched:
                        # Try R2 patterns
                        for pattern in r2_patterns:
                            match = pattern.match(filename)
                            if match:
                                sample_name = match.group(1)
                                r2_files[sample_name] = f["key"]
                                LOGGER.debug("S3 Discovery: Matched R2 file %s -> sample %s", filename, sample_name)
                                break

                # Pair R1 and R2 files
                all_sample_names = set(r1_files.keys()) | set(r2_files.keys())
                LOGGER.info("S3 Discovery: Found %d R1 files, %d R2 files, %d unique sample names",
                           len(r1_files), len(r2_files), len(all_sample_names))

                for sample_name in sorted(all_sample_names):
                    samples.append({
                        "sample_id": sample_name,
                        "r1_file": r1_files.get(sample_name, ""),
                        "r2_file": r2_files.get(sample_name, ""),
                        "status": "pending",
                    })

            LOGGER.info("S3 Discovery: Returning %d samples, %d files found", len(samples), len(files_found))

            return {
                "samples": samples,
                "yaml_content": yaml_content,
                "files_found": len(files_found),
                "bucket": bucket,
                "prefix": prefix,
                "normalized_prefix": normalized_prefix,
                "total_objects_scanned": total_objects,
            }

        except s3_client.exceptions.NoSuchBucket if 's3_client' in dir() else Exception as e:
            if "NoSuchBucket" in str(type(e).__name__):
                LOGGER.error("S3 Discovery: Bucket '%s' does not exist", bucket)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"S3 bucket '{bucket}' not found",
                )
            LOGGER.error("S3 Discovery: Failed to discover samples from S3: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to discover samples: {str(e)}",
            )
        except Exception as e:
            LOGGER.error("S3 Discovery: Failed to discover samples from S3: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to discover samples: {str(e)}",
            )

    # ========== S3 Bucket Validation Endpoint ==========

    @app.post("/api/s3/validate-bucket", tags=["utilities"])
    async def validate_s3_bucket(
        bucket: str = Body(..., embed=True),
        current_user: Optional[Dict] = Depends(get_current_user),
    ):
        """Validate an S3 bucket for Daylily use.

        Checks:
        - Bucket exists and is accessible
        - Read permissions (list and get objects)
        - Write permissions (put objects to worksets/ prefix)

        Returns validation result with setup instructions if needed.
        """
        from daylib.s3_bucket_validator import S3BucketValidator

        try:
            validator = S3BucketValidator(region=region, profile=profile)
            result = validator.validate_bucket(bucket)

            # Generate setup instructions if not fully configured
            instructions = None
            if not result.is_fully_configured:
                instructions = validator.get_setup_instructions(
                    bucket, result, daylily_account_id="108782052779"
                )

            return {
                "bucket": bucket,
                "valid": result.is_valid,
                "fully_configured": result.is_fully_configured,
                "exists": result.exists,
                "accessible": result.accessible,
                "can_read": result.can_read,
                "can_write": result.can_write,
                "can_list": result.can_list,
                "region": result.region,
                "errors": result.errors,
                "warnings": result.warnings,
                "setup_instructions": instructions,
            }
        except Exception as e:
            LOGGER.error("S3 Validation: Failed to validate bucket '%s': %s", bucket, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to validate bucket: {str(e)}",
            )

    @app.get("/api/s3/iam-policy/{bucket_name}", tags=["utilities"])
    async def get_iam_policy_for_bucket(
        bucket_name: str,
        read_only: bool = False,
        current_user: Optional[Dict] = Depends(get_current_user),
    ):
        """Generate IAM policy for accessing a customer S3 bucket.

        Args:
            bucket_name: S3 bucket name
            read_only: If True, generate read-only policy

        Returns:
            IAM policy document that can be attached to a role/user.
        """
        from daylib.s3_bucket_validator import S3BucketValidator

        validator = S3BucketValidator(region=region, profile=profile)
        policy = validator.generate_iam_policy_for_bucket(bucket_name, read_only=read_only)

        return {
            "bucket": bucket_name,
            "read_only": read_only,
            "policy": policy,
        }

    @app.get("/api/s3/bucket-policy/{bucket_name}", tags=["utilities"])
    async def get_bucket_policy_for_daylily(
        bucket_name: str,
        daylily_account_id: str = "108782052779",
        current_user: Optional[Dict] = Depends(get_current_user),
    ):
        """Generate S3 bucket policy for cross-account Daylily access.

        Args:
            bucket_name: Customer's S3 bucket name
            daylily_account_id: Daylily service account ID

        Returns:
            S3 bucket policy document to apply to customer bucket.
        """
        from daylib.s3_bucket_validator import S3BucketValidator

        validator = S3BucketValidator(region=region, profile=profile)
        policy = validator.generate_customer_bucket_policy(bucket_name, daylily_account_id)

        return {
            "bucket": bucket_name,
            "daylily_account_id": daylily_account_id,
            "policy": policy,
            "apply_command": f"aws s3api put-bucket-policy --bucket {bucket_name} --policy file://bucket-policy.json",
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

        # Portal routes are now in daylib/routes/portal.py
        from daylib.routes.portal import create_portal_router, PortalDependencies
        portal_deps = PortalDependencies(
            state_db=state_db,
            templates=templates,
            settings=settings,
            enable_auth=enable_auth,
            cognito_auth=cognito_auth,
            customer_manager=customer_manager,
            file_registry=file_registry,
            linked_bucket_manager=linked_bucket_manager,
        )
        portal_router = create_portal_router(portal_deps)
        app.include_router(portal_router)
        LOGGER.info("Portal routes registered via create_portal_router")

    # ========== File Management API Integration ==========

    if file_registry and FILE_MANAGEMENT_AVAILABLE:
        LOGGER.info("Integrating file management API endpoints")
        try:
            # Pass auth dependency - use combined session/JWT auth
            auth_dep = get_current_user

            # Create S3 bucket validator for validation endpoints
            s3_bucket_validator = None
            bucket_file_discovery = None

            if S3BucketValidator is not None:
                try:
                    s3_bucket_validator = S3BucketValidator(region=region, profile=profile)
                    LOGGER.info("S3BucketValidator initialized for file API")
                except Exception as e:
                    LOGGER.warning("Failed to create LinkedBucketManager: %s", str(e))

            if BucketFileDiscovery is not None and s3_bucket_validator:
                try:
                    bucket_file_discovery = BucketFileDiscovery(
                        region=region,
                        profile=profile,
                    )
                    LOGGER.info("BucketFileDiscovery initialized for file API")
                except Exception as e:
                    LOGGER.warning("Failed to create BucketFileDiscovery: %s", str(e))

            file_router = create_file_api_router(
                file_registry,
                auth_dependency=auth_dep,
                s3_bucket_validator=s3_bucket_validator,
                linked_bucket_manager=linked_bucket_manager,
                bucket_file_discovery=bucket_file_discovery,
            )
            app.include_router(file_router)
            auth_status = "with combined session/JWT authentication"
            LOGGER.info(f"File management API endpoints registered at /api/files/* ({auth_status})")
        except Exception as e:
            LOGGER.error("Failed to integrate file management API: %s", str(e))
            LOGGER.warning("File management endpoints will not be available")
    elif file_registry and not FILE_MANAGEMENT_AVAILABLE:
        LOGGER.warning(
            "FileRegistry provided but file management modules not available. "
            "File management endpoints will not be registered."
        )
    else:
        LOGGER.info("File management not configured - file API endpoints not registered")

    # ========== Biospecimen API Integration ==========

    if BIOSPECIMEN_AVAILABLE:
        LOGGER.info("Integrating biospecimen API endpoints")
        try:
            biospecimen_registry = BiospecimenRegistry(region=region, profile=profile)

            def get_customer_id_from_request(request: Request) -> str:
                """Get customer ID from request session or raise 401.

                Resolution order:
                1. Session customer_id (portal login)
                2. API key customer lookup (if implemented)

                Raises:
                    HTTPException(401): If customer cannot be resolved
                """
                # Try session first (portal login)
                session = getattr(request, 'session', None)
                if session:
                    customer_id = session.get('customer_id')
                    if customer_id:
                        return str(customer_id)

                # No valid authentication found
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required. Please log in to access biospecimen data.",
                )

            biospecimen_router = create_biospecimen_router(
                registry=biospecimen_registry,
                get_customer_id=get_customer_id_from_request,
            )
            app.include_router(biospecimen_router)
            LOGGER.info("Biospecimen API endpoints registered at /api/biospecimen/*")
        except Exception as e:
            LOGGER.error("Failed to integrate biospecimen API: %s", str(e))
            LOGGER.warning("Biospecimen endpoints will not be available")
    else:
        LOGGER.info("Biospecimen module not available - biospecimen API endpoints not registered")

    # Store settings in app state for access in route handlers
    app.state.settings = settings

    return app
