"""Daylily API route modules.

This package contains FastAPI routers organized by functionality:
- worksets: Core workset CRUD operations
- customers: Customer management and customer-scoped operations
- utilities: S3 discovery, cost estimation, and other helper endpoints
- portal: HTML portal pages and web interface routes
"""

from daylib.routes.dependencies import (
    # Pydantic models
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
    format_file_size,
    get_file_icon,
    calculate_cost_with_efficiency,
    convert_customer_for_template,
    verify_workset_ownership,
)

# Router factories
from daylib.routes.worksets import create_worksets_router
from daylib.routes.utilities import create_utilities_router
from daylib.routes.portal import create_portal_router, PortalDependencies

__all__ = [
    # Router factories
    "create_worksets_router",
    "create_utilities_router",
    "create_portal_router",
    "PortalDependencies",
    # Pydantic models
    "WorksetCreate",
    "WorksetResponse",
    "WorksetStateUpdate",
    "QueueStats",
    "SchedulingStats",
    "CustomerCreate",
    "CustomerResponse",
    "WorksetValidationResponse",
    "WorkYamlGenerateRequest",
    "ChangePasswordRequest",
    "APITokenCreateRequest",
    "PortalFileAutoRegisterRequest",
    "PortalFileAutoRegisterResponse",
    # Utility functions
    "format_file_size",
    "get_file_icon",
    "calculate_cost_with_efficiency",
    "convert_customer_for_template",
    "verify_workset_ownership",
]

