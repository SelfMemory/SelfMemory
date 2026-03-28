"""Middleware for unified authentication on MCP endpoints.

This middleware enforces authentication using the unified auth logic that supports:
1. OAuth 2.1 tokens from Hydra (JWT or opaque format)
2. Legacy API keys from SelfMemory dashboard

Authentication logic is imported from auth.unified_auth to maintain DRY principles.
"""

import logging
from contextvars import ContextVar

from auth.unified_auth import detect_and_validate_auth
from fastapi import Request, Response
from oauth.metadata import build_www_authenticate_header, create_401_response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Global ContextVar for storing token context per request
# This allows tools to access authentication info set by middleware
current_token_context: ContextVar[dict | None] = ContextVar(
    "current_token_context", default=None
)


class UnifiedAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce unified authentication (OAuth 2.1 + API key) on MCP endpoints.

    This middleware:
    1. Validates MCP-Protocol-Version header (MCP spec requirement)
    2. Detects authentication method (JWT vs API key)
    3. Validates token via appropriate method (Hydra or Core server)
    4. Returns RFC 6750 WWW-Authenticate challenge on auth failure
    5. Attaches unified token context to request for tool handlers
    """

    SUPPORTED_MCP_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

    def __init__(self, app, core_server_host: str):
        super().__init__(app)
        self.core_server_host = core_server_host

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce authentication."""

        public_paths = [
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-authorization-server",
            "/.well-known/openid-configuration",
            "/register",
        ]

        if request.url.path in public_paths:
            return await call_next(request)

        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        # Validate MCP protocol version
        version_error = self._validate_protocol_version(request)
        if version_error:
            return version_error

        auth_header = request.headers.get("authorization")

        if not auth_header:
            logger.warning("No Authorization header - returning OAuth challenge")
            return self._create_auth_challenge()

        try:
            token_context = await detect_and_validate_auth(
                auth_header, self.core_server_host
            )

            token_context_data = token_context.to_dict()
            current_token_context.set(token_context_data)
            request.scope["auth_context"] = token_context_data

            logger.info(
                f"Authentication successful: {token_context.auth_type} - "
                f"user={token_context.user_id}, project={token_context.project_id}"
            )

            response = await call_next(request)
            return response

        except ValueError as e:
            logger.warning(f"Authentication failed: {e}")
            return self._create_error_response("invalid_token", "Authentication failed")

    def _validate_protocol_version(self, request: Request) -> Response | None:
        """Validate MCP-Protocol-Version header per MCP spec.

        The initialization request (POST /mcp) does not require this header.
        Non-initialization requests default to latest version for backward compatibility.

        Returns:
            Error Response if version is unsupported, None if valid.
        """
        protocol_version = request.headers.get("mcp-protocol-version")
        is_initialization = request.method == "POST" and request.url.path in (
            "/mcp",
            "/mcp/",
        )

        if not is_initialization and not protocol_version:
            protocol_version = self.SUPPORTED_MCP_VERSIONS[0]

        if protocol_version and protocol_version not in self.SUPPORTED_MCP_VERSIONS:
            logger.warning(f"Unsupported MCP protocol version: {protocol_version}")
            return Response(
                content=f"Unsupported MCP protocol version: {protocol_version}. "
                f"Supported: {', '.join(self.SUPPORTED_MCP_VERSIONS)}",
                status_code=400,
                media_type="text/plain",
            )

        return None

    def _create_auth_challenge(self) -> Response:
        """Create 401 response with RFC 6750 WWW-Authenticate header."""
        error_response = create_401_response(
            error="invalid_token",
            error_description="Authorization required. Provide OAuth token or API key.",
        )
        www_auth_header = build_www_authenticate_header(
            error_response["www_authenticate"]
        )

        return Response(
            content=error_response["error_description"],
            status_code=401,
            headers={"WWW-Authenticate": www_auth_header, "Content-Type": "text/plain"},
        )

    def _create_error_response(self, error: str, description: str) -> Response:
        """Create 401 error response with WWW-Authenticate header."""
        error_response = create_401_response(error=error, error_description=description)
        www_auth_header = build_www_authenticate_header(
            error_response["www_authenticate"]
        )

        return Response(
            content=error_response["error_description"],
            status_code=401,
            headers={"WWW-Authenticate": www_auth_header, "Content-Type": "text/plain"},
        )
