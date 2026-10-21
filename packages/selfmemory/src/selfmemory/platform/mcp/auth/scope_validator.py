"""Token scope validation utilities.

This module centralizes scope validation logic to avoid duplication
across middleware and tool implementations.
"""

import logging

from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def validate_scope(
    token_scopes: list[str],
    required_scope: str,
    context_info: dict | None = None,
) -> bool:
    """Validate that token has required scope.

    Args:
        token_scopes: List of scopes granted to token
        required_scope: Required scope to check for
        context_info: Optional dict with user/project info for logging

    Returns:
        True if token has required scope, False otherwise

    Raises:
        ValueError: If token missing required scope
    """
    if required_scope not in token_scopes:
        context_str = ""
        if context_info:
            user = context_info.get("user_id", "unknown")
            project = context_info.get("project_id", "unknown")
            context_str = f" (user={user}, project={project})"

        error_msg = f"Token missing required scope: {required_scope}{context_str}"
        logger.warning(f"❌ {error_msg}")

        with tracer.start_as_current_span("scope_validation_failure"):
            raise ValueError(error_msg)

    logger.debug(f"✅ Scope validation passed: {required_scope}")
    return True


def validate_scopes(
    token_scopes: list[str],
    required_scopes: list[str],
    match_all: bool = True,
    context_info: dict | None = None,
) -> bool:
    """Validate that token has required scopes.

    Args:
        token_scopes: List of scopes granted to token
        required_scopes: List of required scopes
        match_all: If True, token must have ALL scopes. If False, token must have ANY.
        context_info: Optional dict with user/project info for logging

    Returns:
        True if validation passes

    Raises:
        ValueError: If scope validation fails
    """
    with tracer.start_as_current_span("validate_scopes") as span:
        span.set_attribute("required_scopes", ",".join(required_scopes))
        span.set_attribute("match_all", match_all)

        if match_all:
            missing = [s for s in required_scopes if s not in token_scopes]
            if missing:
                context_str = ""
                if context_info:
                    user = context_info.get("user_id", "unknown")
                    project = context_info.get("project_id", "unknown")
                    context_str = f" (user={user}, project={project})"

                error_msg = (
                    f"Token missing required scopes: {', '.join(missing)}{context_str}"
                )
                logger.warning(f"❌ {error_msg}")
                span.set_attribute("validation_status", "failed_missing_all")
                raise ValueError(error_msg)
        else:
            has_any = any(s in token_scopes for s in required_scopes)
            if not has_any:
                context_str = ""
                if context_info:
                    user = context_info.get("user_id", "unknown")
                    project = context_info.get("project_id", "unknown")
                    context_str = f" (user={user}, project={project})"

                error_msg = f"Token missing any of required scopes: {', '.join(required_scopes)}{context_str}"
                logger.warning(f"❌ {error_msg}")
                span.set_attribute("validation_status", "failed_missing_any")
                raise ValueError(error_msg)

        logger.debug(f"✅ Scope validation passed: required={required_scopes}")
        span.set_attribute("validation_status", "passed")
        return True


def get_required_scope_for_tool(tool_name: str) -> str | None:
    """Get required scope for MCP tool.

    Maps tool names to required scopes for easier maintenance.

    Args:
        tool_name: Name of the MCP tool

    Returns:
        Required scope or None if tool has no scope requirement
    """
    scope_map = {
        "search": "memories:read",
        "fetch": "memories:read",
        "add": "memories:write",
        "update": "memories:write",
        "delete": "memories:write",
    }
    return scope_map.get(tool_name)
