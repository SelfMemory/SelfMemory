"""
Memory utility functions for SelfMemory.

This module contains utility functions for building metadata and filters
used in memory operations, following Clean Code principles with single
responsibility and clear separation of concerns.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def validate_isolation_context(
    *,  # Enforce keyword-only arguments
    user_id: str,
    project_id: str | None = None,
    organization_id: str | None = None,
    operation: str = "operation"
) -> None:
    """
    Validate multi-tenant isolation context for memory operations.
    
    This function performs strict validation to ensure that isolation
    parameters are consistent and prevent data leakage between tenants.
    
    Args:
        user_id: Required user identifier for memory isolation
        project_id: Optional project identifier for project-level isolation
        organization_id: Optional organization identifier for org-level isolation
        operation: Name of the operation being performed (for logging)
        
    Raises:
        ValueError: If isolation context is invalid or inconsistent
        
    Examples:
        >>> validate_isolation_context(
        ...     user_id="alice",
        ...     project_id="proj_123",
        ...     organization_id="org_456",
        ...     operation="memory_search"
        ... )
    """
    # Validate that user_id is provided (required for this system)
    if not user_id or not isinstance(user_id, str) or not user_id.strip():
        raise ValueError(f"ISOLATION ERROR ({operation}): user_id is required and must be a non-empty string")

    # Validate project/organization consistency
    if project_id and not organization_id:
        raise ValueError(f"ISOLATION ERROR ({operation}): organization_id is required when project_id is provided")
    if organization_id and not project_id:
        raise ValueError(f"ISOLATION ERROR ({operation}): project_id is required when organization_id is provided")

    # Log isolation context for audit trail
    if project_id and organization_id:
        logger.info(f"✅ ISOLATION VALIDATED ({operation}): user={user_id}, project={project_id}, org={organization_id}")
    else:
        logger.info(f"✅ ISOLATION VALIDATED ({operation}): user={user_id} (backward compatibility mode)")


def audit_memory_access(
    *,  # Enforce keyword-only arguments
    operation: str,
    user_id: str,
    project_id: str | None = None,
    organization_id: str | None = None,
    memory_id: str | None = None,
    memory_count: int | None = None,
    success: bool = True,
    error: str | None = None
) -> None:
    """
    Audit memory access operations for security monitoring.
    
    This function logs all memory access operations with full context
    to enable security monitoring and detect potential isolation violations.
    
    Args:
        operation: Name of the operation being performed
        user_id: User identifier performing the operation
        project_id: Optional project identifier
        organization_id: Optional organization identifier
        memory_id: Optional specific memory ID being accessed
        memory_count: Optional count of memories affected
        success: Whether the operation was successful
        error: Optional error message if operation failed
        
    Examples:
        >>> audit_memory_access(
        ...     operation="memory_search",
        ...     user_id="alice",
        ...     project_id="proj_123",
        ...     organization_id="org_456",
        ...     memory_count=5,
        ...     success=True
        ... )
    """
    context_info = f"user={user_id}"
    if project_id and organization_id:
        context_info += f", project={project_id}, org={organization_id}"
    
    if memory_id:
        context_info += f", memory_id={memory_id}"
    if memory_count is not None:
        context_info += f", count={memory_count}"
    
    status = "SUCCESS" if success else "FAILED"
    log_message = f"🔒 AUDIT [{status}] {operation}: {context_info}"
    
    if error:
        log_message += f", error={error}"
    
    if success:
        logger.info(log_message)
    else:
        logger.warning(log_message)


def build_add_metadata(
    *,  # Enforce keyword-only arguments
    user_id: str,
    input_metadata: dict[str, Any],
    project_id: str | None = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """
    Build metadata specifically for add operations with multi-tenant isolation.

    This function creates user-scoped metadata for storing memories with complete
    isolation between users, projects, and organizations. Designed specifically 
    for add operations where metadata is always required.

    Args:
        user_id: Required user identifier for memory isolation
        input_metadata: Required metadata to include with the memory
        project_id: Optional project identifier for project-level isolation
        organization_id: Optional organization identifier for org-level isolation

    Returns:
        dict: Processed metadata ready for storage with isolation context

    Raises:
        ValueError: If user_id is not provided or is empty
        ValueError: If input_metadata is not provided or is empty
        ValueError: If project_id is provided but organization_id is missing
        ValueError: If organization_id is provided but project_id is missing

    Examples:
        Basic user isolation (backward compatible):
        >>> metadata = build_add_metadata(
        ...     user_id="alice",
        ...     input_metadata={"data": "I love pizza", "tags": "food"}
        ... )
        
        Multi-tenant isolation:
        >>> metadata = build_add_metadata(
        ...     user_id="alice",
        ...     project_id="proj_123",
        ...     organization_id="org_456",
        ...     input_metadata={"data": "I love pizza", "tags": "food"}
        ... )
    """
    # Validate that user_id is provided (required for this system)
    if not user_id or not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id is required and must be a non-empty string")

    if not input_metadata:
        raise ValueError("input_metadata is required and cannot be empty")

    # Validate project/organization consistency
    if project_id and not organization_id:
        raise ValueError("organization_id is required when project_id is provided")
    if organization_id and not project_id:
        raise ValueError("project_id is required when organization_id is provided")

    processed_metadata = input_metadata.copy()

    # Add user isolation metadata
    processed_metadata["user_id"] = user_id.strip()

    # Add multi-tenant isolation metadata if provided
    if project_id and organization_id:
        processed_metadata["project_id"] = project_id.strip()
        processed_metadata["organization_id"] = organization_id.strip()
        logger.info(f"Adding memory with multi-tenant context: user={user_id}, project={project_id}, org={organization_id}")
    else:
        logger.info(f"Adding memory with user-only context: user={user_id} (backward compatibility mode)")

    # Add timestamp for tracking
    processed_metadata["created_at"] = datetime.now().isoformat()

    return processed_metadata


def build_search_filters(
    *,  # Enforce keyword-only arguments
    user_id: str,
    input_filters: dict[str, Any] | None = None,
    project_id: str | None = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """
    Build filters specifically for search operations with multi-tenant isolation.

    This function creates user-scoped filters for querying memories with complete
    isolation between users, projects, and organizations. Designed specifically 
    for search operations where filters are needed.

    Args:
        user_id: Required user identifier for memory isolation
        input_filters: Optional additional filters to include
        project_id: Optional project identifier for project-level isolation
        organization_id: Optional organization identifier for org-level isolation

    Returns:
        dict: Effective filters ready for querying with isolation context

    Raises:
        ValueError: If user_id is not provided or is empty
        ValueError: If project_id is provided but organization_id is missing
        ValueError: If organization_id is provided but project_id is missing

    Examples:
        Basic user isolation (backward compatible):
        >>> filters = build_search_filters(user_id="alice")
        >>> filters = build_search_filters(
        ...     user_id="alice",
        ...     input_filters={"tags": ["work"], "topic_category": "meetings"}
        ... )
        
        Multi-tenant isolation:
        >>> filters = build_search_filters(
        ...     user_id="alice",
        ...     project_id="proj_123",
        ...     organization_id="org_456",
        ...     input_filters={"tags": ["work"], "topic_category": "meetings"}
        ... )
    """
    # Validate that user_id is provided (required for this system)
    if not user_id or not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id is required and must be a non-empty string")

    # Validate project/organization consistency
    if project_id and not organization_id:
        raise ValueError("organization_id is required when project_id is provided")
    if organization_id and not project_id:
        raise ValueError("project_id is required when organization_id is provided")

    # Build effective filters for querying
    effective_filters = input_filters.copy() if input_filters else {}

    # Add user isolation filter
    effective_filters["user_id"] = user_id.strip()

    # Add multi-tenant isolation filters if provided
    if project_id and organization_id:
        effective_filters["project_id"] = project_id.strip()
        effective_filters["organization_id"] = organization_id.strip()
        logger.info(f"Searching memories with multi-tenant context: user={user_id}, project={project_id}, org={organization_id}")
    else:
        logger.info(f"Searching memories with user-only context: user={user_id} (backward compatibility mode)")

    return effective_filters
