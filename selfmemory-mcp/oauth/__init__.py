"""OAuth metadata and utilities for MCP server.

Provides RFC 9728 Protected Resource Metadata, RFC 6750 error responses,
and Dynamic Client Registration (RFC 7591) sanitization.
"""

from .discovery_proxy import proxy_discovery_metadata
from .metadata import (
    build_www_authenticate_header,
    create_401_response,
    get_protected_resource_metadata,
)

__all__ = [
    "get_protected_resource_metadata",
    "create_401_response",
    "build_www_authenticate_header",
    "proxy_discovery_metadata",
]
