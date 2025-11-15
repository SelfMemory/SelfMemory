"""OAuth metadata for MCP server (RFC 9728).

This module provides OAuth 2.0 Protected Resource Metadata
for MCP client discovery.
"""

from .metadata import create_401_response, get_protected_resource_metadata

__all__ = [
    "get_protected_resource_metadata",
    "create_401_response",
]
