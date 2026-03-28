"""Tool-level authentication and scope validation.

Centralizes the auth extraction + scope validation + telemetry pattern
that repeats in every MCP tool implementation.
"""

import logging

from mcp.server.fastmcp import Context
from opentelemetry import trace

from .scope_validator import validate_scope

logger = logging.getLogger(__name__)


def get_validated_tool_context(
    ctx: Context,
    required_scope: str,
    current_token_context_var,
) -> dict:
    """Extract auth context from MCP Context, validate scope, and set telemetry.

    Replaces the repetitive auth extraction + null check + scope check +
    telemetry attribute pattern in every tool function.

    Args:
        ctx: FastMCP Context from the tool invocation
        required_scope: Required scope string (e.g., "memories:read")
        current_token_context_var: The ContextVar holding the token context

    Returns:
        Validated token context dict with user_id, project_id, scopes, raw_token

    Raises:
        ValueError: If auth context is missing or scope validation fails
    """
    # Priority 1: request.scope['auth_context']
    token_context = _extract_from_request_scope(ctx)

    # Priority 2: ContextVar
    if not token_context:
        token_context = current_token_context_var.get()

    if not token_context:
        logger.error("No auth context available from any source")
        raise ValueError("Authentication context not available")

    logger.info(
        f"Auth via {token_context.get('auth_type')}: "
        f"user={token_context.get('user_id')}"
    )

    # Set telemetry attributes on current span
    span = trace.get_current_span()
    span.set_attribute("auth.type", token_context.get("auth_type", ""))
    span.set_attribute("user.id", token_context.get("user_id", ""))
    span.set_attribute("project.id", token_context.get("project_id", ""))

    # Validate required scope
    validate_scope(
        token_scopes=token_context["scopes"],
        required_scope=required_scope,
        context_info=token_context,
    )

    return token_context


def _extract_from_request_scope(ctx: Context) -> dict | None:
    """Extract auth context from request.scope if available."""
    if not hasattr(ctx, "request_context") or not ctx.request_context:
        return None

    try:
        request = ctx.request_context.request
        if hasattr(request, "scope"):
            return request.scope.get("auth_context")
    except Exception as e:
        logger.warning(f"Error accessing request_context: {e}")

    return None
