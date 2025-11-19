"""Unified authentication middleware supporting both OAuth 2.1 and API key methods.

This middleware:
1. Validates MCP-Protocol-Version header (MCP spec requirement)
2. Checks for Authorization header on /mcp/* requests
3. Returns 401 with WWW-Authenticate if missing (OAuth challenge)
4. Detects authentication method (OAuth JWT vs API key)
5. Validates token via appropriate method (Hydra or Core server)
6. Attaches unified token context to request.state for tool handlers

This enables both OAuth 2.1 and legacy API key authentication to work
seamlessly with the same MCP server endpoint.
"""

import logging
import time
from contextvars import ContextVar

from auth.unified_auth import TokenContext, detect_and_validate_auth
from fastapi import Request, Response
from oauth.metadata import create_401_response
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Global ContextVar for storing token context per request
# This allows tools to access authentication info set by middleware
current_token_context: ContextVar[dict | None] = ContextVar(
    "current_token_context", default=None
)


class UnifiedAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce unified authentication (OAuth 2.1 or API key) on MCP endpoints.

    This middleware enables both modern OAuth 2.1 clients and legacy API key clients
    to authenticate with the same MCP server endpoint, providing a smooth migration path.

    Features:
    - Supports OAuth 2.1 tokens from Hydra (JWT format)
    - Supports legacy API keys from SelfMemory dashboard
    - Automatic detection based on token format
    - Returns proper OAuth challenges for OAuth clients
    - Compatible with both SSE and HTTPS MCP transports
    """

    # Supported MCP protocol versions
    SUPPORTED_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

    def __init__(self, app, core_server_host: str):
        """Initialize unified auth middleware.

        Args:
            app: FastAPI application instance
            core_server_host: Core server URL for API key validation
        """
        super().__init__(app)
        self.core_server_host = core_server_host

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce unified authentication."""
        # Create root span for entire middleware dispatch
        with tracer.start_as_current_span("mcp_auth_middleware") as root_span:
            root_span.set_attribute("http.method", request.method)
            root_span.set_attribute("http.url.path", request.url.path)

            # Skip authentication for metadata endpoints (OAuth discovery)
            if request.url.path in [
                "/.well-known/oauth-protected-resource",
                "/.well-known/oauth-authorization-server",
                "/.well-known/openid-configuration",
            ]:
                root_span.set_attribute("auth.skipped.reason", "metadata_endpoint")
                return await call_next(request)

            # Skip authentication for registration endpoint (OAuth DCR)
            if request.url.path == "/register":
                root_span.set_attribute("auth.skipped.reason", "registration_endpoint")
                return await call_next(request)

            # Only protect MCP endpoints
            if not request.url.path.startswith("/mcp"):
                root_span.set_attribute("auth.skipped.reason", "not_mcp_endpoint")
                return await call_next(request)

            # MCP Spec: Validate MCP-Protocol-Version header
            # Required on all requests after initialization
            with tracer.start_as_current_span("validate_protocol_version"):
                protocol_version = request.headers.get("mcp-protocol-version")

                # Check if this is the initial initialization request
                # (InitializeRequest doesn't require the header yet)
                is_initialization = (
                    request.method == "POST" and request.url.path == "/mcp"
                )

                if not is_initialization and not protocol_version:
                    logger.warning(
                        "Missing MCP-Protocol-Version header on non-initialization request"
                    )
                    # For backward compatibility, assume latest version
                    protocol_version = self.SUPPORTED_VERSIONS[0]
                    logger.info(f"Defaulting to protocol version: {protocol_version}")

                # Validate version if present
                if protocol_version and protocol_version not in self.SUPPORTED_VERSIONS:
                    logger.error(
                        f"Unsupported MCP protocol version: {protocol_version}"
                    )
                    return Response(
                        content=f"Unsupported MCP protocol version: {protocol_version}. Supported versions: {', '.join(self.SUPPORTED_VERSIONS)}",
                        status_code=400,
                        media_type="text/plain",
                    )

                # Store protocol version for later use
                if protocol_version:
                    request.state.mcp_protocol_version = protocol_version
                    logger.debug(f"MCP protocol version: {protocol_version}")
                    root_span.set_attribute("mcp.protocol_version", protocol_version)

            # Check for Authorization header
            auth_header = request.headers.get("authorization")

            if not auth_header:
                # No auth header - return 401 with OAuth challenge
                # Note: This OAuth challenge is ignored by --oauth no clients
                logger.info(
                    f"🔒 No Authorization header - returning OAuth challenge for {request.url.path}"
                )
                root_span.set_attribute("auth.status", "missing_header")
                return self._create_oauth_challenge_response()

            # Detect and validate authentication (OAuth or API key)
            try:
                with tracer.start_as_current_span(
                    "detect_and_validate_auth"
                ) as auth_span:
                    auth_start_time = time.time()
                    token_context: TokenContext = await detect_and_validate_auth(
                        auth_header, self.core_server_host
                    )
                    auth_duration = time.time() - auth_start_time

                    auth_span.set_attribute("auth.type", token_context.auth_type)
                    auth_span.set_attribute("auth.duration_ms", auth_duration * 1000)
                    auth_span.set_attribute("user.id", token_context.user_id)
                    auth_span.set_attribute(
                        "project.id", token_context.project_id or ""
                    )
                    auth_span.set_attribute("scopes", ",".join(token_context.scopes))

                    root_span.set_attribute("auth.type", token_context.auth_type)
                    root_span.set_attribute("auth.duration_ms", auth_duration * 1000)

                    if auth_duration > 3.0:
                        logger.warning(f"⚠️  Slow auth validation: {auth_duration:.2f}s")
                        auth_span.add_event("slow_auth_warning", {"threshold_ms": 3000})

                # Validate project context exists (required for tools)
                if not token_context.project_id:
                    logger.error(
                        f"❌ Token missing project context: user={token_context.user_id}"
                    )
                    root_span.set_attribute("auth.status", "missing_project")
                    return self._create_error_response(
                        error="insufficient_scope",
                        error_description="Token missing project context",
                    )

                # Convert to dict for storage
                token_context_dict = token_context.to_dict()

                # Set in ContextVar for tool access
                current_token_context.set(token_context_dict)

                # Also attach to request state for compatibility
                request.state.token_context = token_context_dict

                logger.info(
                    f"✅ Authenticated via {token_context.auth_type}: "
                    f"user={token_context.user_id}, project={token_context.project_id}, "
                    f"scopes={token_context.scopes}"
                )
                root_span.set_attribute("auth.status", "success")

            except ValueError as e:
                # Authentication failed
                logger.warning(f"❌ Authentication failed: {e}")
                root_span.set_attribute("auth.status", "failed")
                root_span.record_exception(e)
                # Never return detailed error info to the client
                return self._create_error_response(
                    error="invalid_token",
                    error_description="Invalid authentication token.",
                )

            # Authentication successful - proceed with request
            with tracer.start_as_current_span("call_next"):
                response = await call_next(request)
            return response

    def _create_oauth_challenge_response(self) -> Response:
        """Create 401 response with OAuth challenge.

        Returns proper WWW-Authenticate header for OAuth 2.0 clients.
        API key clients (using --oauth no) will ignore this challenge.
        """
        error_response = create_401_response(
            error="invalid_token",
            error_description="Authorization required. Use OAuth 2.0 or API key.",
        )

        # Build WWW-Authenticate header
        www_auth = error_response["www_authenticate"]
        www_auth_header = f'Bearer realm="{www_auth["realm"]}", '
        www_auth_header += f'resource="{www_auth["resource"]}", '
        www_auth_header += f'resource_metadata="{www_auth["resource_metadata"]}"'

        if "error" in www_auth:
            www_auth_header += f', error="{www_auth["error"]}"'
        if "error_description" in www_auth:
            www_auth_header += f', error_description="{www_auth["error_description"]}"'

        return Response(
            content=error_response["error_description"],
            status_code=401,
            headers={"WWW-Authenticate": www_auth_header, "Content-Type": "text/plain"},
        )

    def _create_error_response(self, error: str, error_description: str) -> Response:
        """Create 401 error response for authentication failures.

        Args:
            error: OAuth error code (e.g., "invalid_token", "insufficient_scope")
            error_description: Human-readable error description
        """
        error_response = create_401_response(
            error=error, error_description=error_description
        )

        www_auth = error_response["www_authenticate"]
        www_auth_header = f'Bearer realm="{www_auth["realm"]}", '
        www_auth_header += f'error="{www_auth["error"]}", '
        www_auth_header += f'error_description="{www_auth["error_description"]}"'

        return Response(
            content=error_response["error_description"],
            status_code=401,
            headers={"WWW-Authenticate": www_auth_header, "Content-Type": "text/plain"},
        )
