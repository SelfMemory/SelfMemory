"""OAuth 2.1 Authentication Middleware for MCP Server.

This module provides middleware to enforce OAuth 2.1 authentication on MCP endpoints.
Implements RFC 6750 (Bearer Token Usage) and MCP protocol requirements.

Following Uncle Bob's Clean Code:
- Single responsibility: Authentication only
- Small, focused functions
- Clear error handling
- No business logic mixed in
"""

import logging
from contextvars import ContextVar

from auth.token_extractor import extract_bearer_token
from fastapi import Request, Response
from oauth.metadata import create_401_response
from starlette.middleware.base import BaseHTTPMiddleware

from server.auth.hydra_validator import validate_token

logger = logging.getLogger(__name__)

# Global ContextVar for storing OAuth token context per request
# This allows tools to access authentication info set by middleware
current_token_context: ContextVar[dict | None] = ContextVar(
    "current_token_context", default=None
)


class OAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce OAuth 2.1 authentication on MCP endpoints.

    This middleware:
    1. Validates MCP-Protocol-Version header (MCP spec requirement)
    2. Checks for Authorization header on /mcp/* requests
    3. Returns 401 with WWW-Authenticate if missing (OAuth challenge)
    4. Validates token via Hydra if present
    5. Attaches token context to request.state for tool handlers

    This enables VS Code's OAuth flow to work correctly by responding
    with proper 401 challenges that trigger the OAuth flow.
    """

    # Supported MCP protocol versions
    SUPPORTED_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce OAuth authentication."""

        # Skip authentication for metadata endpoint
        if request.url.path == "/.well-known/oauth-protected-resource":
            return await call_next(request)

        # Only protect MCP endpoints
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        # Validate MCP protocol version
        protocol_validation = self._validate_protocol_version(request)
        if protocol_validation:
            return protocol_validation  # Return error response

        # Check for Authorization header
        auth_header = request.headers.get("authorization")

        if not auth_header:
            return self._create_auth_challenge()

        # Validate token and set context
        token_validation = await self._validate_and_set_token_context(
            request, auth_header
        )
        if token_validation:
            return token_validation  # Return error response

        # Token valid - proceed with request
        response = await call_next(request)
        return response

    def _validate_protocol_version(self, request: Request) -> Response | None:
        """Validate MCP-Protocol-Version header.

        Args:
            request: Incoming request

        Returns:
            Response if validation fails, None if valid
        """
        protocol_version = request.headers.get("mcp-protocol-version")

        # Check if this is the initial initialization request
        is_initialization = request.method == "POST" and request.url.path == "/mcp"

        if not is_initialization and not protocol_version:
            logger.warning(
                "Missing MCP-Protocol-Version header on non-initialization request"
            )
            # For backward compatibility, assume latest version
            protocol_version = self.SUPPORTED_VERSIONS[0]
            logger.info(f"Defaulting to protocol version: {protocol_version}")

        # Validate version if present
        if protocol_version and protocol_version not in self.SUPPORTED_VERSIONS:
            logger.error(f"Unsupported MCP protocol version: {protocol_version}")
            return Response(
                content=f"Unsupported MCP protocol version: {protocol_version}. "
                f"Supported versions: {', '.join(self.SUPPORTED_VERSIONS)}",
                status_code=400,
                media_type="text/plain",
            )

        # Store protocol version for later use
        if protocol_version:
            request.state.mcp_protocol_version = protocol_version
            logger.debug(f"MCP protocol version: {protocol_version}")

        return None

    def _create_auth_challenge(self) -> Response:
        """Create 401 response with OAuth challenge.

        Returns:
            401 Response with WWW-Authenticate header
        """
        logger.info("🔒 No Authorization header - returning OAuth challenge")

        error_response = create_401_response(
            error="invalid_token",
            error_description="Authorization required. Please authenticate via OAuth 2.0.",
        )

        # Build WWW-Authenticate header
        www_auth = error_response["www_authenticate"]
        www_auth_header = self._build_www_authenticate_header(www_auth)

        return Response(
            content=error_response["error_description"],
            status_code=401,
            headers={"WWW-Authenticate": www_auth_header, "Content-Type": "text/plain"},
        )

    def _build_www_authenticate_header(self, www_auth: dict) -> str:
        """Build WWW-Authenticate header string from dict.

        Args:
            www_auth: Dictionary with authentication parameters

        Returns:
            Formatted WWW-Authenticate header value
        """
        parts = [
            f'realm="{www_auth["realm"]}"',
            f'resource="{www_auth["resource"]}"',
            f'resource_metadata="{www_auth["resource_metadata"]}"',
        ]

        if "error" in www_auth:
            parts.append(f'error="{www_auth["error"]}"')
        if "error_description" in www_auth:
            parts.append(f'error_description="{www_auth["error_description"]}"')

        return "Bearer " + ", ".join(parts)

    async def _validate_and_set_token_context(
        self, request: Request, auth_header: str
    ) -> Response | None:
        """Validate token and set context.

        Args:
            request: Incoming request
            auth_header: Authorization header value

        Returns:
            Response if validation fails, None if valid
        """
        try:
            token = extract_bearer_token(auth_header)
            hydra_token = validate_token(token)

            # Validate project context exists
            if not hydra_token.project_id:
                logger.error(
                    f"❌ Token missing project context: subject={hydra_token.subject}"
                )
                return self._create_error_response(
                    "insufficient_scope", "Token missing project context"
                )

            # Create and set token context
            token_context_data = {
                "user_id": hydra_token.subject,
                "project_id": hydra_token.project_id,
                "organization_id": hydra_token.organization_id,
                "scopes": hydra_token.scopes,
                "raw_token": token,
            }

            # Set in ContextVar for tool access
            current_token_context.set(token_context_data)

            # Also attach to request state for compatibility
            request.state.token_context = token_context_data

            logger.info(
                f"✅ Token validated and context set: user={hydra_token.subject}, "
                f"project={hydra_token.project_id}, scopes={hydra_token.scopes}"
            )

            return None

        except ValueError as e:
            # Invalid token
            logger.warning(f"❌ Token validation failed: {e}")
            return self._create_error_response("invalid_token", str(e))

    def _create_error_response(self, error: str, description: str) -> Response:
        """Create error response with proper OAuth error format.

        Args:
            error: OAuth error code
            description: Human-readable error description

        Returns:
            401 Response with error details
        """
        error_response = create_401_response(error=error, error_description=description)

        www_auth = error_response["www_authenticate"]
        www_auth_header = self._build_www_authenticate_header(www_auth)

        return Response(
            content=error_response["error_description"],
            status_code=401,
            headers={"WWW-Authenticate": www_auth_header, "Content-Type": "text/plain"},
        )
