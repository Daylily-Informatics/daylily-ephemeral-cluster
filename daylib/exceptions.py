"""Custom exception hierarchy for Daylily.

Provides structured exceptions that map to HTTP status codes and
include error codes for consistent API responses.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class DaylilyException(Exception):
    """Base exception for all Daylily errors.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code (e.g., "WORKSET_NOT_FOUND")
        status_code: HTTP status code to return
        details: Additional error context
    """

    status_code: int = 500
    default_code: str = "INTERNAL_ERROR"
    default_message: str = "An internal error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert exception to API response format."""
        response = {
            "error": self.message,
            "code": self.code,
            "details": self.details,
        }
        if request_id:
            response["request_id"] = request_id
        return response


# ========== Client Errors (4xx) ==========


class ValidationError(DaylilyException):
    """Request validation failed."""

    status_code = 400
    default_code = "VALIDATION_ERROR"
    default_message = "Request validation failed"


class AuthenticationError(DaylilyException):
    """Authentication required or failed."""

    status_code = 401
    default_code = "AUTHENTICATION_REQUIRED"
    default_message = "Authentication required"


class AuthorizationError(DaylilyException):
    """User lacks permission for this action."""

    status_code = 403
    default_code = "FORBIDDEN"
    default_message = "You do not have permission to perform this action"


class NotFoundError(DaylilyException):
    """Requested resource not found."""

    status_code = 404
    default_code = "NOT_FOUND"
    default_message = "Resource not found"


class ConflictError(DaylilyException):
    """Resource conflict (e.g., already exists)."""

    status_code = 409
    default_code = "CONFLICT"
    default_message = "Resource conflict"


class RateLimitError(DaylilyException):
    """Rate limit exceeded."""

    status_code = 429
    default_code = "RATE_LIMIT_EXCEEDED"
    default_message = "Rate limit exceeded. Please try again later."


# ========== Server Errors (5xx) ==========


class ServiceUnavailableError(DaylilyException):
    """Service temporarily unavailable."""

    status_code = 503
    default_code = "SERVICE_UNAVAILABLE"
    default_message = "Service temporarily unavailable"


class DependencyError(DaylilyException):
    """External dependency failed."""

    status_code = 502
    default_code = "DEPENDENCY_ERROR"
    default_message = "External service error"


# ========== Domain-Specific Errors ==========


class WorksetNotFoundError(NotFoundError):
    """Workset not found."""

    default_code = "WORKSET_NOT_FOUND"
    default_message = "Workset not found"


class WorksetAlreadyExistsError(ConflictError):
    """Workset already exists."""

    default_code = "WORKSET_ALREADY_EXISTS"
    default_message = "Workset already exists"


class CustomerNotFoundError(NotFoundError):
    """Customer not found."""

    default_code = "CUSTOMER_NOT_FOUND"
    default_message = "Customer not found"


class FileNotFoundError(NotFoundError):
    """File not found in registry."""

    default_code = "FILE_NOT_FOUND"
    default_message = "File not found"


class BucketAccessError(AuthorizationError):
    """Cannot access S3 bucket."""

    default_code = "BUCKET_ACCESS_DENIED"
    default_message = "Cannot access the specified S3 bucket"


class WorksetLockError(ConflictError):
    """Workset is locked by another process."""

    default_code = "WORKSET_LOCKED"
    default_message = "Workset is currently locked by another process"


class InvalidStateTransitionError(ValidationError):
    """Invalid workset state transition."""

    default_code = "INVALID_STATE_TRANSITION"
    default_message = "Invalid state transition"

