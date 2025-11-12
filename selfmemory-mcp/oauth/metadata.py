"""OAuth 2.0 Protected Resource Metadata (RFC 9728).

This module provides metadata endpoints for OAuth 2.0 protected resource
discovery, allowing OAuth clients like ChatGPT to discover the authorization
server and supported scopes.
"""

from config import config


def get_protected_resource_metadata() -> dict:
    """Generate RFC 9728 metadata for MCP server.
    
    Returns OAuth 2.0 Protected Resource Metadata that tells clients:
    - Which authorization server to use (MCP server proxy, not Hydra directly)
    - What scopes are supported
    - How to send Bearer tokens
    
    This metadata is served at /.well-known/oauth-protected-resource
    per RFC 9728 specification.
    
    IMPORTANT: Points to MCP server (not Hydra) so clients use our proxy endpoints
    which inject registration_endpoint into the metadata.
    
    Returns:
        Protected resource metadata dictionary
    """
    return {
        "resource": config.hydra.resource_url,  # RFC 8707: Use canonical URL (no trailing slash)
        "authorization_servers": [config.hydra.resource_url],  # Point to MCP server proxy, not Hydra!
        "scopes_supported": config.hydra.scopes_supported,
        "bearer_methods_supported": config.hydra.bearer_methods_supported,
    }


def create_401_response(error: str = "invalid_token", error_description: str | None = None) -> dict:
    """Create 401 error response with WWW-Authenticate header info.
    
    When authentication fails, returns proper OAuth 2.0 error response
    with WWW-Authenticate header information per RFC 6750.
    
    Args:
        error: OAuth error code (e.g., "invalid_token", "insufficient_scope")
        error_description: Optional human-readable error description
        
    Returns:
        Error response dict with WWW-Authenticate details
    """
    www_authenticate = {
        "realm": "SelfMemory MCP",
        "resource": config.hydra.resource_url,  # RFC 8707: Use canonical URL
        "resource_metadata": f"{config.hydra.resource_url}/.well-known/oauth-protected-resource",
    }
    
    # Add error and error_description to WWW-Authenticate if provided
    if error:
        www_authenticate["error"] = error
    if error_description:
        www_authenticate["error_description"] = error_description
    
    return {
        "error": error,
        "error_description": error_description or "Authentication failed",
        "www_authenticate": www_authenticate,
    }
