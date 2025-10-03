"""
Error Handling Utilities

Standardized error handling following Uncle Bob's Clean Code principles:
- No fallback mechanisms (explicit errors)
- Clear error messages for users
- Detailed logging for developers
- Consistent error format
- Request ID tracking for correlation

Standard Error Response Format:
{
    "error": {
        "code": "ERROR_CODE",
        "message": "User-friendly message",
        "request_id": "abc-123",
        "timestamp": "2025-01-03T12:00:00Z"
    }
}
"""

import logging
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from ..utils.datetime_helpers import utc_now

logger = logging.getLogger(__name__)


# Error codes for consistent error handling
class ErrorCode:
    """Standard error codes for the application."""

    # Authentication & Authorization
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_API_KEY = "INVALID_API_KEY"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_ID_FORMAT = "INVALID_ID_FORMAT"

    # Resource errors
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # Rate limiting & Security
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    CSRF_TOKEN_INVALID = "CSRF_TOKEN_INVALID"

    # System errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"


def get_request_id(request: Request) -> str:
    """
    Get or generate request ID for tracking.

    Args:
        request: FastAPI request object

    Returns:
        str: Request ID (from header or generated)
    """
    # Try to get from header first
    request_id = request.headers.get("X-Request-ID")

    # Generate if not present
    if not request_id:
        request_id = str(uuid.uuid4())

    return request_id


def create_error_response(
    code: str,
    message: str,
    status_code: int = 500,
    request_id: str | None = None,
) -> JSONResponse:
    """
    Create standardized error response.

    Args:
        code: Error code from ErrorCode class
        message: User-friendly error message
        status_code: HTTP status code
        request_id: Request ID for tracking (optional)

    Returns:
        JSONResponse: Standardized error response
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
                "timestamp": utc_now().isoformat(),
            }
        },
    )


def handle_exception(
    request: Request, error: Exception, context: str = "", log_level: str = "ERROR"
) -> JSONResponse:
    """
    Handle exceptions with standardized logging and response.

    Following Uncle Bob's principles:
    - Never expose internal details to users
    - Always log detailed information for debugging
    - Return consistent error format
    - No fallback mechanisms (explicit errors)

    Args:
        request: FastAPI request object
        error: Exception that occurred
        context: Context description for logging
        log_level: Logging level (ERROR, WARNING, etc.)

    Returns:
        JSONResponse: Standardized error response
    """
    request_id = get_request_id(request)

    # If it's already an HTTPException, use its details
    if isinstance(error, HTTPException):
        # Map common status codes to error codes
        code_map = {
            400: ErrorCode.INVALID_INPUT,
            401: ErrorCode.AUTHENTICATION_FAILED,
            403: ErrorCode.PERMISSION_DENIED,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            500: ErrorCode.INTERNAL_ERROR,
        }

        error_code = code_map.get(error.status_code, ErrorCode.INTERNAL_ERROR)
        message = error.detail
        status_code = error.status_code

        # Log HTTPException details
        log_message = (
            f"HTTPException in {context}: "
            f"status={error.status_code}, "
            f"detail={error.detail}, "
            f"request_id={request_id}"
        )

        if log_level == "WARNING":
            logger.warning(log_message)
        else:
            logger.error(log_message)
    else:
        # Generic exception - log detailed info but return generic message
        error_code = ErrorCode.INTERNAL_ERROR
        message = "Internal server error"
        status_code = 500

        # Log full exception details (including stack trace)
        logger.exception(
            f"Exception in {context}: "
            f"type={type(error).__name__}, "
            f"error={str(error)}, "
            f"request_id={request_id}"
        )

    return create_error_response(
        code=error_code, message=message, status_code=status_code, request_id=request_id
    )


def handle_validation_error(request: Request, field: str, message: str) -> JSONResponse:
    """
    Handle validation errors with standardized format.

    Args:
        request: FastAPI request object
        field: Field that failed validation
        message: Validation error message

    Returns:
        JSONResponse: Standardized validation error response
    """
    request_id = get_request_id(request)

    logger.warning(
        f"Validation error: field={field}, message={message}, request_id={request_id}"
    )

    return create_error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message=f"Validation failed for {field}: {message}",
        status_code=400,
        request_id=request_id,
    )


def handle_not_found(
    request: Request, resource_type: str, resource_id: str | None = None
) -> JSONResponse:
    """
    Handle resource not found errors.

    Args:
        request: FastAPI request object
        resource_type: Type of resource (e.g., "Project", "Organization")
        resource_id: ID of resource (optional, not logged for security)

    Returns:
        JSONResponse: Standardized not found error response
    """
    request_id = get_request_id(request)

    message = f"{resource_type} not found"

    logger.warning(f"Resource not found: type={resource_type}, request_id={request_id}")

    return create_error_response(
        code=ErrorCode.NOT_FOUND,
        message=message,
        status_code=404,
        request_id=request_id,
    )


def handle_permission_denied(
    request: Request, action: str, resource_type: str
) -> JSONResponse:
    """
    Handle permission denied errors.

    Args:
        request: FastAPI request object
        action: Action that was denied (e.g., "delete", "write")
        resource_type: Type of resource (e.g., "project", "memory")

    Returns:
        JSONResponse: Standardized permission denied error response
    """
    request_id = get_request_id(request)

    message = f"Permission denied - {action} access required for {resource_type}"

    logger.warning(
        f"Permission denied: "
        f"action={action}, "
        f"resource_type={resource_type}, "
        f"request_id={request_id}"
    )

    return create_error_response(
        code=ErrorCode.PERMISSION_DENIED,
        message=message,
        status_code=403,
        request_id=request_id,
    )


def handle_database_error(
    request: Request, operation: str, error: Exception
) -> JSONResponse:
    """
    Handle database errors with proper logging.

    Args:
        request: FastAPI request object
        operation: Database operation that failed
        error: Exception that occurred

    Returns:
        JSONResponse: Standardized database error response
    """
    request_id = get_request_id(request)

    # Log detailed error for debugging
    logger.error(
        f"Database error during {operation}: "
        f"type={type(error).__name__}, "
        f"error={str(error)}, "
        f"request_id={request_id}"
    )

    # Return generic message to user (no internal details)
    return create_error_response(
        code=ErrorCode.DATABASE_ERROR,
        message="Database operation failed",
        status_code=500,
        request_id=request_id,
    )
