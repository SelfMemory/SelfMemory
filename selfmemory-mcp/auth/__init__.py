"""Authentication module for MCP server.

This module provides Hydra OAuth 2.1 token validation and extraction.
"""

from .token_extractor import (
    create_project_client,
    extract_bearer_token,
    extract_token_context,
)

__all__ = [
    "create_project_client",
    "extract_bearer_token",
    "extract_token_context",
]
