"""Middleware for unified authentication on MCP endpoints.

This middleware enforces authentication using the unified auth logic that supports:
1. OAuth 2.1 tokens from Hydra (JWT or opaque format)
2. Legacy API keys from SelfMemory dashboard

Authentication logic is imported from auth.unified_auth to maintain DRY principles.
"""

import logging
from contextvars import ContextVar

# Import auth logic from auth module (DRY - Don't Repeat Yourself)
from auth.unified_auth import detect_and_validate_auth
from fastapi import Request, Response
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
    1. Detects authentication method (JWT vs API key)
    2. Validates token via appropriate method (Hydra or Core server)
    3. Attaches unified token context to request for tool handlers
    4. Works transparently with both auth methods
    """

    def __init__(self, app, core_server_host: str):
        """Initialize unified auth middleware.

        Args:
            app: FastAPI application
            core_server_host: Core server URL for API key validation
        """
        super().__init__(app)
        self.core_server_host = core_server_host

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce authentication."""

        # Skip authentication for public endpoints
        public_paths = [
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-authorization-server",
            "/.well-known/openid-configuration",
            "/register",
        ]

        if request.url.path in public_paths:
            return await call_next(request)

        # Only protect MCP endpoints
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        # Check for Authorization header
        auth_header = request.headers.get("authorization")

        if not auth_header:
            logger.warning("🔒 No Authorization header - access denied")
            return Response(
                content="Authorization required. Please provide OAuth token or API key.",
                status_code=401,
                headers={"Content-Type": "text/plain"},
            )

        # Validate token and set context
        try:
            token_context = await detect_and_validate_auth(
                auth_header, self.core_server_host
            )

            # Convert TokenContext to dict
            token_context_data = token_context.to_dict()

            # Set in ContextVar for tool access
            current_token_context.set(token_context_data)

            # Also attach to request.scope for ASGI compatibility
            request.scope["auth_context"] = token_context_data

            logger.info(
                f"✅ Authentication successful: {token_context.auth_type} - "
                f"user={token_context.user_id}, project={token_context.project_id}"
            )

            # Token valid - proceed with request
            response = await call_next(request)
            return response

        except ValueError as e:
            logger.warning(f"❌ Authentication failed: {e}")
            return Response(
                content="Authentication failed.",
                status_code=401,
                headers={"Content-Type": "text/plain"},
            )
