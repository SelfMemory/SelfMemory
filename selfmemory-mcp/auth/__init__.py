"""Authentication module for MCP server.

This module provides:
1. Hydra OAuth 2.1 token validation and extraction
2. Unified authentication supporting both OAuth and API key methods
"""

from .token_extractor import (
    create_project_client,
    extract_bearer_token,
    extract_token_context,
)
from .unified_auth import (
    AuthType,
    TokenContext,
    detect_and_validate_auth,
    looks_like_jwt,
    validate_api_key,
    validate_oauth_token,
)

__all__ = [
    # Token extraction
    "create_project_client",
    "extract_bearer_token",
    "extract_token_context",
    # Unified authentication
    "AuthType",
    "TokenContext",
    "detect_and_validate_auth",
    "looks_like_jwt",
    "validate_api_key",
    "validate_oauth_token",
]
