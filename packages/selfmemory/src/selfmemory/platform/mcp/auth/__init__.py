"""Authentication module for MCP server.

This module provides:
1. Hydra OAuth 2.1 token validation and extraction
2. Unified authentication supporting both OAuth and API key methods
3. Tool-level auth context extraction and scope validation
"""

from selfmemory.platform.mcp.auth.token_extractor import (
    extract_bearer_token,
    extract_token_context,
)
from selfmemory.platform.mcp.auth.tool_auth import get_validated_tool_context
from selfmemory.platform.mcp.auth.unified_auth import (
    AuthType,
    TokenContext,
    detect_and_validate_auth,
    looks_like_jwt,
    validate_api_key,
    validate_oauth_token,
)

__all__ = [
    # Token extraction
    "extract_bearer_token",
    "extract_token_context",
    # Tool auth
    "get_validated_tool_context",
    # Unified authentication
    "AuthType",
    "TokenContext",
    "detect_and_validate_auth",
    "looks_like_jwt",
    "validate_api_key",
    "validate_oauth_token",
]
