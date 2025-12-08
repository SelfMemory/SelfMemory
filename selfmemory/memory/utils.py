"""
Memory utility functions for SelfMemory.

This module contains utility functions for building metadata and filters
used in memory operations, following Clean Code principles with single
responsibility and clear separation of concerns.
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def validate_isolation_context(
    *,  # Enforce keyword-only arguments
    user_id: str,
    project_id: str | None = None,
    organization_id: str | None = None,
    operation: str = "operation",
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
        raise ValueError(
            f"ISOLATION ERROR ({operation}): user_id is required and must be a non-empty string"
        )

    # Validate project/organization consistency
    if project_id and not organization_id:
        raise ValueError(
            f"ISOLATION ERROR ({operation}): organization_id is required when project_id is provided"
        )
    if organization_id and not project_id:
        raise ValueError(
            f"ISOLATION ERROR ({operation}): project_id is required when organization_id is provided"
        )

    # Log isolation context for audit trail
    if project_id and organization_id:
        logger.info(
            f"✅ ISOLATION VALIDATED ({operation}): user={user_id}, project={project_id}, org={organization_id}"
        )
    else:
        logger.info(
            f"✅ ISOLATION VALIDATED ({operation}): user={user_id} (backward compatibility mode)"
        )


def audit_memory_access(
    *,  # Enforce keyword-only arguments
    operation: str,
    user_id: str,
    project_id: str | None = None,
    organization_id: str | None = None,
    memory_id: str | None = None,
    memory_count: int | None = None,
    success: bool = True,
    error: str | None = None,
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
        logger.info(
            f"Adding memory with multi-tenant context: user={user_id}, project={project_id}, org={organization_id}"
        )
    else:
        logger.info(
            f"Adding memory with user-only context: user={user_id} (backward compatibility mode)"
        )

    # Add timestamp for tracking (always use UTC)
    processed_metadata["created_at"] = datetime.now(timezone.utc).isoformat()

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
        logger.info(
            f"Searching memories with multi-tenant context: user={user_id}, project={project_id}, org={organization_id}"
        )
    else:
        logger.info(
            f"Searching memories with user-only context: user={user_id} (backward compatibility mode)"
        )

    return effective_filters

import re

from selfmemory.configs.prompts import (
    USER_MEMORY_EXTRACTION_PROMPT,
    AGENT_MEMORY_EXTRACTION_PROMPT,
)


def get_fact_retrieval_messages(message, is_agent_memory=False):
    """Get fact retrieval messages based on the memory type.
    
    Args:
        message: The message content to extract facts from
        is_agent_memory: If True, use agent memory extraction prompt, else use user memory extraction prompt
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    if is_agent_memory:
        return AGENT_MEMORY_EXTRACTION_PROMPT, f"Input:\n{message}"
    else:
        return USER_MEMORY_EXTRACTION_PROMPT, f"Input:\n{message}"


def parse_messages(messages):
    """Parse message list into formatted string for LLM processing.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        str: Formatted message string
    """
    response = ""
    for msg in messages:
        if msg["role"] == "system":
            response += f"system: {msg['content']}\n"
        if msg["role"] == "user":
            response += f"user: {msg['content']}\n"
        if msg["role"] == "assistant":
            response += f"assistant: {msg['content']}\n"
    return response


def remove_code_blocks(content: str) -> str:
    """Remove enclosing code block markers from LLM responses.
    
    Args:
        content: String potentially containing code block markers
        
    Returns:
        str: Cleaned content without code block markers
    """
    pattern = r"^```[a-zA-Z0-9]*\n([\s\S]*?)\n```$"
    match = re.match(pattern, content.strip())
    match_res = match.group(1).strip() if match else content.strip()
    return re.sub(r"<think>.*?</think>", "", match_res, flags=re.DOTALL).strip()


def extract_json(text):
    """Extract JSON content from string, removing code block markers if present.
    
    Args:
        text: String potentially containing JSON in code blocks
        
    Returns:
        str: Extracted JSON string
    """
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = text  # assume it's raw JSON
    return json_str


def build_filters_and_metadata(
    *,  # Enforce keyword-only arguments
    user_id: str | None = None,
    project_id: str | None = None,
    organization_id: str | None = None,
    actor_id: str | None = None,  # For query-time filtering
    input_metadata: dict[str, Any] | None = None,
    input_filters: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Build metadata for storage and filters for querying based on project-based session identifiers.
    
    Adapted from mem0's _build_filters_and_metadata but enhanced for SelfMemory's 
    superior project-based multi-tenant architecture.

    This helper supports SelfMemory's session identifiers (user_id, project_id, organization_id)
    for flexible session scoping and optionally narrows queries to a specific actor_id.

    Args:
        user_id: User identifier for individual user context
        project_id: Project identifier for project-level isolation  
        organization_id: Organization identifier for org-level isolation
        actor_id: Explicit actor identifier for actor-specific filtering
        input_metadata: Base metadata to be augmented with session identifiers
        input_filters: Base filters to be augmented with session and actor identifiers

    Returns:
        tuple[dict[str, Any], dict[str, Any]]: A tuple containing:
            - base_metadata_template: Metadata template for storing memories
            - effective_query_filters: Filters for querying memories

    Raises:
        ValueError: If session context is invalid (missing required identifiers)

    Examples:
        Basic user isolation:
        >>> metadata, filters = build_filters_and_metadata(user_id="alice")
        
        Project-based isolation (recommended):
        >>> metadata, filters = build_filters_and_metadata(
        ...     user_id="alice", 
        ...     project_id="proj_123", 
        ...     organization_id="org_456"
        ... )
    """
    from copy import deepcopy
    
    base_metadata_template = deepcopy(input_metadata) if input_metadata else {}
    effective_query_filters = deepcopy(input_filters) if input_filters else {}

    # Track provided session identifiers
    session_ids_provided = []

    # Add user_id (always required for SelfMemory)
    if user_id:
        base_metadata_template["user_id"] = user_id
        effective_query_filters["user_id"] = user_id
        session_ids_provided.append("user_id")

    # Add project-based isolation (SelfMemory's superior approach)
    if project_id:
        base_metadata_template["project_id"] = project_id
        effective_query_filters["project_id"] = project_id
        session_ids_provided.append("project_id")

    if organization_id:
        base_metadata_template["organization_id"] = organization_id
        effective_query_filters["organization_id"] = organization_id
        session_ids_provided.append("organization_id")

    # Validate session context
    if not session_ids_provided:
        raise ValueError(
            "At least 'user_id' must be provided for memory operations. "
            "For multi-tenant isolation, also provide 'project_id' and 'organization_id'."
        )

    # Validate project/organization consistency (SelfMemory requirement)
    if project_id and not organization_id:
        raise ValueError("organization_id is required when project_id is provided")
    if organization_id and not project_id:
        raise ValueError("project_id is required when organization_id is provided")

    # Add optional actor filter for query-time filtering
    resolved_actor_id = actor_id or effective_query_filters.get("actor_id")
    if resolved_actor_id:
        effective_query_filters["actor_id"] = resolved_actor_id

    # Log session context for debugging
    context_info = f"user={user_id}"
    if project_id and organization_id:
        context_info += f", project={project_id}, org={organization_id}"
    if resolved_actor_id:
        context_info += f", actor={resolved_actor_id}"
    
    logger.debug(f"Built session context: {context_info}")

    return base_metadata_template, effective_query_filters


def map_to_mem0_session(
    user_id: str,
    project_id: str | None = None,
    organization_id: str | None = None,
) -> dict[str, str]:
    """
    Map SelfMemory's project-based session identifiers to mem0's session format.
    
    This provides compatibility with mem0's expected session format while preserving
    SelfMemory's superior multi-tenant architecture.

    Args:
        user_id: SelfMemory user identifier  
        project_id: SelfMemory project identifier (becomes mem0's user_id)
        organization_id: SelfMemory organization identifier (preserved as metadata)

    Returns:
        dict: Session mapping compatible with mem0's format

    Examples:
        Project-based mapping (recommended):
        >>> session = map_to_mem0_session("alice", "proj_123", "org_456") 
        >>> # Returns: {"user_id": "proj_123", "agent_id": "alice", "run_id": "alice_proj_123"}
        
        User-only mapping (fallback):
        >>> session = map_to_mem0_session("alice")
        >>> # Returns: {"user_id": "alice", "agent_id": None, "run_id": None}
    """
    if project_id and organization_id:
        # Project-based mapping: Project becomes mem0's "user", real user becomes "agent"
        return {
            "user_id": project_id,                           # Project → mem0 user_id
            "agent_id": user_id,                            # Real user → mem0 agent_id  
            "run_id": f"{user_id}_{project_id}",           # Session context
            "organization_id": organization_id,             # Preserved for additional isolation
            "original_user_id": user_id,                   # Track original user
            "original_project_id": project_id              # Track original project
        }
    else:
        # User-only mapping (backward compatibility)
        return {
            "user_id": user_id,
            "agent_id": None,
            "run_id": None
        }
