"""Structured exception classes for SelfMemory based on mem0's error handling system.

This module provides comprehensive exception classes that replace generic errors
with specific, actionable exceptions. Each exception includes error codes,
user-friendly suggestions, and debug information to enable better error handling
and recovery in SelfMemory applications.

Adapted from mem0's exception system for SelfMemory's multi-tenant architecture.
"""

from typing import Any, Dict, Optional


class SelfMemoryError(Exception):
    """Base exception for all SelfMemory-related errors.
    
    This is the base class for all SelfMemory-specific exceptions. It provides a structured
    approach to error handling with error codes, contextual details, suggestions for
    resolution, and debug information.
    
    Attributes:
        message (str): Human-readable error message.
        error_code (str): Unique error identifier for programmatic handling.
        details (dict): Additional context about the error.
        suggestion (str): User-friendly suggestion for resolving the error.
        debug_info (dict): Technical debugging information.
    """
    
    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        debug_info: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a SelfMemoryError.
        
        Args:
            message: Human-readable error message.
            error_code: Unique error identifier.
            details: Additional context about the error.
            suggestion: User-friendly suggestion for resolving the error.
            debug_info: Technical debugging information.
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestion = suggestion
        self.debug_info = debug_info or {}
        super().__init__(self.message)
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"details={self.details!r}, "
            f"suggestion={self.suggestion!r}, "
            f"debug_info={self.debug_info!r})"
        )


class AuthenticationError(SelfMemoryError):
    """Raised when authentication fails in SelfMemory.
    
    This exception is raised when Ory Kratos/Hydra authentication fails,
    API key validation fails, or authentication credentials are invalid.
    
    Common scenarios:
        - Invalid Ory Kratos session
        - Expired Hydra OAuth token
        - Invalid API key
        - Missing authentication headers
        - Insufficient permissions
    """
    pass


class ValidationError(SelfMemoryError):
    """Raised when input validation fails in SelfMemory.
    
    This exception is raised when request parameters, memory content,
    or configuration values fail validation checks.
    
    Common scenarios:
        - Invalid user_id, project_id, or organization_id format
        - Missing required fields
        - Content too long or too short
        - Invalid metadata format
        - Malformed multi-tenant context
    """
    pass


class IsolationError(SelfMemoryError):
    """Raised when multi-tenant isolation is violated.
    
    This SelfMemory-specific exception is raised when operations attempt
    to access memories across tenant boundaries or violate isolation rules.
    
    Common scenarios:
        - User accessing another organization's memories
        - Project accessing memories from different organization
        - Missing project_id when organization_id is provided
        - Cross-tenant data leakage attempt
    """
    
    def __init__(self, message: str, error_code: str = "ISOLATION_001", details: dict = None, 
                 suggestion: str = "Please check your user_id, project_id, and organization_id", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class MemoryNotFoundError(SelfMemoryError):
    """Raised when a memory is not found or not accessible."""
    pass


class NetworkError(SelfMemoryError):
    """Raised when network connectivity issues occur."""
    pass


class ConfigurationError(SelfMemoryError):
    """Raised when client configuration is invalid."""
    pass


class MemoryQuotaExceededError(SelfMemoryError):
    """Raised when user's memory quota is exceeded."""
    pass


class MemoryCorruptionError(SelfMemoryError):
    """Raised when memory data is corrupted."""
    pass


class VectorSearchError(SelfMemoryError):
    """Raised when vector search operations fail."""
    pass


class CacheError(SelfMemoryError):
    """Raised when caching operations fail."""
    pass


# SelfMemory-specific exception classes
class VectorStoreError(SelfMemoryError):
    """Raised when vector store operations fail.
    
    This exception is raised when Qdrant, ChromaDB, or other vector store
    operations fail in SelfMemory.
    """
    
    def __init__(self, message: str, error_code: str = "VECTOR_001", details: dict = None, 
                 suggestion: str = "Please check your vector store configuration and connection", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class EmbeddingError(SelfMemoryError):
    """Raised when embedding operations fail.
    
    This exception is raised when Ollama or other embedding providers
    fail in SelfMemory.
    """
    
    def __init__(self, message: str, error_code: str = "EMBED_001", details: dict = None, 
                 suggestion: str = "Please check your embedding model configuration", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class LLMError(SelfMemoryError):
    """Raised when LLM operations fail.
    
    This exception is raised when LLM operations for fact extraction
    and memory processing fail in SelfMemory.
    """
    
    def __init__(self, message: str, error_code: str = "LLM_001", details: dict = None, 
                 suggestion: str = "Please check your LLM configuration and API key", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class DatabaseError(SelfMemoryError):
    """Raised when database operations fail.
    
    This exception is raised when MongoDB or other database operations
    fail in SelfMemory.
    """
    
    def __init__(self, message: str, error_code: str = "DB_001", details: dict = None, 
                 suggestion: str = "Please check your database configuration and connection", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class ProjectError(SelfMemoryError):
    """Raised when project-related operations fail.
    
    This SelfMemory-specific exception is raised when project operations
    fail, such as project creation, access, or management.
    """
    
    def __init__(self, message: str, error_code: str = "PROJECT_001", details: dict = None, 
                 suggestion: str = "Please check your project configuration and permissions", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class OrganizationError(SelfMemoryError):
    """Raised when organization-related operations fail.
    
    This SelfMemory-specific exception is raised when organization operations
    fail, such as organization access or management.
    """
    
    def __init__(self, message: str, error_code: str = "ORG_001", details: dict = None, 
                 suggestion: str = "Please check your organization configuration and permissions", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


# HTTP status mapping for SelfMemory API
HTTP_STATUS_TO_EXCEPTION = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthenticationError,
    404: MemoryNotFoundError,
    408: NetworkError,
    409: ValidationError,
    413: MemoryQuotaExceededError,
    422: ValidationError,
    500: SelfMemoryError,
    502: NetworkError,
    503: NetworkError,
    504: NetworkError,
}


def create_exception_from_response(
    status_code: int,
    response_text: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    debug_info: Optional[Dict[str, Any]] = None,
) -> SelfMemoryError:
    """Create an appropriate exception based on HTTP response.
    
    Args:
        status_code: HTTP status code from the response.
        response_text: Response body text.
        error_code: Optional specific error code.
        details: Additional error context.
        debug_info: Debug information.
    
    Returns:
        An instance of the appropriate SelfMemoryError subclass.
    """
    exception_class = HTTP_STATUS_TO_EXCEPTION.get(status_code, SelfMemoryError)
    
    if not error_code:
        error_code = f"HTTP_{status_code}"
    
    suggestions = {
        400: "Please check your request parameters and try again",
        401: "Please check your authentication credentials",
        403: "You don't have permission to perform this operation",
        404: "The requested resource was not found",
        408: "Request timed out. Please try again",
        409: "Resource conflict. Please check your request",
        413: "Request too large. Please reduce the size of your request",
        422: "Invalid request data. Please check your input",
        500: "Internal server error. Please try again later",
        502: "Service temporarily unavailable. Please try again later",
        503: "Service unavailable. Please try again later",
        504: "Gateway timeout. Please try again later",
    }
    
    suggestion = suggestions.get(status_code, "Please try again later")
    
    return exception_class(
        message=response_text or f"HTTP {status_code} error",
        error_code=error_code,
        details=details or {},
        suggestion=suggestion,
        debug_info=debug_info or {},
    )


# Backward compatibility alias (for migration from mem0)
MemoryError = SelfMemoryError
Mem0ValidationError = ValidationError
