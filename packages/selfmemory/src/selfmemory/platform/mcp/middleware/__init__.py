"""Middleware for SelfMemory MCP Server."""

from selfmemory.platform.mcp.middleware.unified_auth import (
    UnifiedAuthMiddleware,
    current_token_context,
)

__all__ = [
    "UnifiedAuthMiddleware",
    "current_token_context",
]
