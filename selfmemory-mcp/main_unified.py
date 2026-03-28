"""SelfMemory MCP Server with Unified Authentication

Supports both OAuth 2.1 and API key authentication:
1. OAuth 2.1 with PKCE (RFC 7636) for modern clients (VS Code, ChatGPT)
2. Legacy API key authentication for backward compatibility (SSE clients)

Features:
- Automatic authentication detection (JWT vs API key)
- Protected Resource Metadata (RFC 9728)
- Authorization Server Metadata (RFC 8414)
- Dynamic Client Registration (RFC 7591)
- Same tools work with both auth methods
- Single endpoint for all clients

Installation:
  OAuth (automatic):
    npx install-mcp https://server/mcp --client claude
  API Key (manual):
    npx install-mcp https://server/mcp --client claude --oauth no \
      --header "Authorization: Bearer <api_key>"
"""

import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path FIRST so telemetry can import shared modules
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load environment variables before any imports that depend on them
from dotenv import load_dotenv  # noqa: E402

load_dotenv(_PROJECT_ROOT / ".env")

import httpx  # noqa: E402
from fastapi import FastAPI, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from mcp.server.fastmcp import Context, FastMCP  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from opentelemetry import trace  # noqa: E402
from telemetry import init_logging, init_telemetry  # noqa: E402

init_logging()
init_telemetry(service_name="selfmemory-mcp")

# Get tracer for tool instrumentation
tracer = trace.get_tracer(__name__)

from auth.token_extractor import create_project_client  # noqa: E402
from auth.tool_auth import get_validated_tool_context  # noqa: E402
from config import config  # noqa: E402
from middleware import UnifiedAuthMiddleware, current_token_context  # noqa: E402
from oauth.client_registration import (  # noqa: E402
    inject_memory_scopes,
    sanitize_registration_request,
    sanitize_registration_response,
)
from oauth.discovery_proxy import proxy_discovery_metadata  # noqa: E402
from oauth.metadata import get_protected_resource_metadata  # noqa: E402
from tools.fetch import format_fetch_result  # noqa: E402
from tools.search import format_search_results  # noqa: E402
from utils import handle_tool_errors  # noqa: E402

logger = logging.getLogger(__name__)

# Configuration
CORE_SERVER_HOST = config.server.selfmemory_api_host

# Derive allowed host from MCP_SERVER_URL for DNS rebinding protection
_parsed_mcp_url = urlparse(config.hydra.mcp_server_url)
_mcp_host = _parsed_mcp_url.hostname
_allowed_hosts = [_mcp_host, "127.0.0.1:*", "localhost:*"]
if _parsed_mcp_url.port:
    _allowed_hosts.insert(1, f"{_mcp_host}:{_parsed_mcp_url.port}")

# Initialize MCP server
mcp = FastMCP(
    name="SelfMemory",
    instructions="Memory management server with unified authentication (OAuth 2.1 + API key)",
    stateless_http=False,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowed_hosts,
    ),
)


# Setup lifespan context manager
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Manage server lifecycle - ensures MCP session manager is running."""
    async with mcp.session_manager.run():
        yield


# Initialize FastAPI app with lifespan and conditional documentation
app = FastAPI(
    title="SelfMemory MCP Server (Unified Auth)",
    description="Supports both OAuth 2.1 and API key authentication",
    lifespan=lifespan,
    # Security: Disable API documentation in production to prevent information disclosure
    docs_url="/docs" if config.server.environment != "production" else None,
    redoc_url="/redoc" if config.server.environment != "production" else None,
    openapi_url="/openapi.json" if config.server.environment != "production" else None,
)

# Log documentation security status
if config.server.environment == "production":
    logger.info("🔒 SECURITY: MCP API documentation endpoints disabled in production")
else:
    logger.info(
        "📚 DEV MODE: MCP API documentation available at /docs, /redoc, /openapi.json"
    )

logger.info("SelfMemory MCP Server initialized with unified authentication")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)


# ============================================================================
# Unified Authentication Middleware
# ============================================================================

# Register unified auth middleware (supports both OAuth and API key)
app.add_middleware(UnifiedAuthMiddleware, core_server_host=CORE_SERVER_HOST)


# ============================================================================
# Request Logging Middleware (Development)
# ============================================================================


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing for performance monitoring."""
    start = time.time()
    logger.info(f"📍 {request.method} {request.url.path}")
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(
        f"📤 {request.method} {request.url.path} -> {response.status_code} ({duration_ms:.0f}ms)"
    )
    return response


# ============================================================================
# Trailing Slash Handler for MCP (Prevents 307 Redirects)
# ============================================================================


@app.middleware("http")
async def handle_trailing_slash(request: Request, call_next):
    """Handle trailing slash for MCP endpoints without 307 redirect.

    This ensures both /mcp and /mcp/ work seamlessly for SSE clients.
    FastAPI automatically adds trailing slashes and returns 307 redirects,
    which breaks SSE streaming. This middleware rewrites the path internally
    instead of redirecting the client.
    """
    path = request.url.path

    # If path is /mcp (no slash), rewrite it to /mcp/ internally
    if path == "/mcp" or path.startswith("/mcp?"):
        # Create new scope with updated path
        scope = request.scope.copy()
        scope["path"] = "/mcp/"
        scope["raw_path"] = b"/mcp/"

        # Preserve query string if present
        if "?" in path:
            query = path.split("?", 1)[1]
            scope["query_string"] = query.encode()

        # Create new request with updated scope
        request = Request(scope, request.receive)

    response = await call_next(request)
    return response


# ============================================================================
# OAuth Discovery Endpoints (For OAuth Clients)
# ============================================================================


@app.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata():
    """OAuth 2.0 Protected Resource Metadata (RFC 9728).

    Advertises this MCP server as an OAuth-protected resource.
    Used by OAuth clients to discover authentication requirements.
    """
    return get_protected_resource_metadata()


@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server(request: Request):
    """Proxy OAuth 2.0 Authorization Server Metadata to Hydra (RFC 8414)."""
    return await proxy_discovery_metadata(request)


@app.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request):
    """Proxy OpenID Connect Discovery to Hydra."""
    return await proxy_discovery_metadata(request)


@app.post("/register")
async def dynamic_client_registration(request: Request):
    """Proxy Dynamic Client Registration to Hydra (RFC 7591).

    Sanitizes client metadata, injects memory scopes and audience,
    then forwards to Hydra admin API.
    """
    hydra_url = f"{config.hydra.admin_url}/clients"

    try:
        body_bytes = await request.body()
        registration_data = json.loads(body_bytes)

        client_name = registration_data.get("client_name", "Unknown")
        logger.info(f"DCR request from: {client_name}")

        # Sanitize invalid fields (URLs, contacts)
        registration_data = sanitize_registration_request(registration_data)

        # Inject memory scopes
        current_scopes = registration_data.get("scope", "openid offline_access")
        registration_data["scope"] = inject_memory_scopes(
            current_scopes, ["memories:read", "memories:write"]
        )

        # Whitelist MCP server as audience (RFC 8707)
        mcp_server_url = config.hydra.mcp_server_url.rstrip("/")
        current_audience = registration_data.get("audience", [])
        if isinstance(current_audience, str):
            current_audience = [current_audience] if current_audience else []
        elif not isinstance(current_audience, list):
            current_audience = []

        if mcp_server_url not in current_audience:
            current_audience.append(mcp_server_url)

        registration_data["audience"] = current_audience

        # Forward to Hydra
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                hydra_url,
                json=registration_data,
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )

            if response.status_code in (200, 201):
                logger.info("Client registered with Hydra")
                response_data = sanitize_registration_response(response.json())
                return Response(
                    content=json.dumps(response_data),
                    status_code=response.status_code,
                    media_type="application/json",
                )

            logger.warning(f"Registration returned {response.status_code}")
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type="application/json",
            )
    except httpx.HTTPError as e:
        logger.error(f"Failed to register client: {e}")
        return Response(
            content="Failed to register client due to a server error.",
            status_code=502,
            media_type="text/plain",
        )


# Mount MCP server
mcp.settings.streamable_http_path = "/"
app.mount("/mcp", mcp.streamable_http_app())


# ============================================================================
# MCP Tools (Work with Both OAuth and API Key Authentication)
# ============================================================================


@mcp.tool(
    annotations={
        "title": "Search Memories",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
@handle_tool_errors
async def search(query: str, ctx: Context) -> dict:
    """Search through stored memories.

    Works with both OAuth tokens and API keys.

    Args:
        query: Search query string for semantic memory search
        ctx: MCP context (not used - token context from middleware)

    Returns:
        Search results with memory IDs, titles, and URLs
    """
    with tracer.start_as_current_span("mcp_tool.search") as span:
        span.set_attribute("tool.name", "search")
        span.set_attribute("query.length", len(query))

        tool_start = time.time()
        logger.info(f"Search: '{query}'")

        token_context = get_validated_tool_context(
            ctx, "memories:read", current_token_context
        )
        project_id = token_context["project_id"]
        oauth_token = token_context["raw_token"]

        with tracer.start_as_current_span("execute_search") as search_span:
            search_start = time.time()
            client = create_project_client(project_id, oauth_token, CORE_SERVER_HOST)
            result = client.search(query=query, limit=10)
            # Don't close cached clients - let cache manage lifecycle

            search_duration = time.time() - search_start
            search_span.set_attribute("search.duration_ms", search_duration * 1000)
            search_span.set_attribute("results.count", len(result.get("results", [])))

            if search_duration > 5.0:
                logger.warning(f"⚠️  Slow search execution: {search_duration:.2f}s")
                search_span.add_event("slow_search_warning", {"threshold_ms": 5000})

        tool_duration = time.time() - tool_start
        span.set_attribute("tool.duration_ms", tool_duration * 1000)
        logger.info(f"✅ Search completed in {tool_duration:.3f}s")

        return format_search_results(result.get("results", []))


@mcp.tool(
    annotations={
        "title": "Add Memory",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
@handle_tool_errors
async def add(content: str, ctx: Context) -> dict:
    """Store a new memory.

    Works with both OAuth tokens and API keys.

    Args:
        content: The memory content to store
        ctx: MCP context (not used - token context from middleware)

    Returns:
        Confirmation with memory ID and status
    """
    with tracer.start_as_current_span("mcp_tool.add") as span:
        span.set_attribute("tool.name", "add")
        span.set_attribute("content.length", len(content))

        tool_start = time.time()
        logger.info(f"Add: {content[:50]}...")

        token_context = get_validated_tool_context(
            ctx, "memories:write", current_token_context
        )
        project_id = token_context["project_id"]
        oauth_token = token_context["raw_token"]

        with tracer.start_as_current_span("store_memory") as store_span:
            store_start = time.time()
            client = create_project_client(project_id, oauth_token, CORE_SERVER_HOST)

            # Parse content format (simple string or JSON array)
            parsed_content: str | dict | list[dict] = content
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list | dict):
                    parsed_content = parsed
            except (json.JSONDecodeError, ValueError):
                parsed_content = content

            result = client.add(
                parsed_content,
                metadata={"source": "mcp_unified"},
            )
            if not result.get("success", True):
                raise RuntimeError(result.get("error", "Failed to store memory"))
            # Don't close cached clients - let cache manage lifecycle

            store_duration = time.time() - store_start
            store_span.set_attribute("store.duration_ms", store_duration * 1000)
            store_span.set_attribute(
                "memory.id", result.get("memory_id", result.get("id", ""))
            )

            if store_duration > 3.0:
                logger.warning(f"⚠️  Slow memory storage: {store_duration:.2f}s")
                store_span.add_event("slow_store_warning", {"threshold_ms": 3000})

        tool_duration = time.time() - tool_start
        span.set_attribute("tool.duration_ms", tool_duration * 1000)
        logger.info(f"✅ Add completed in {tool_duration:.3f}s")

        # Return full API response (includes operations!)
        # This matches OpenMemory's approach and provides LLM operation details
        return result


@mcp.tool(
    annotations={
        "title": "Fetch Memory",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
@handle_tool_errors
async def fetch(id: str, ctx: Context) -> dict:
    """Retrieve complete memory content by ID.

    Works with both OAuth tokens and API keys.

    Args:
        id: Unique memory identifier
        ctx: MCP context (not used - token context from middleware)

    Returns:
        Complete memory document with content and metadata
    """
    with tracer.start_as_current_span("mcp_tool.fetch") as span:
        span.set_attribute("tool.name", "fetch")
        span.set_attribute("memory.id", id)

        tool_start = time.time()
        logger.info(f"Fetch: id={id}")

        token_context = get_validated_tool_context(
            ctx, "memories:read", current_token_context
        )
        project_id = token_context["project_id"]
        oauth_token = token_context["raw_token"]

        with tracer.start_as_current_span("fetch_memory") as fetch_span:
            fetch_start = time.time()
            client = create_project_client(project_id, oauth_token, CORE_SERVER_HOST)
            result = client.search(query=id, limit=1)
            # Don't close cached clients - let cache manage lifecycle

            fetch_duration = time.time() - fetch_start
            fetch_span.set_attribute("fetch.duration_ms", fetch_duration * 1000)

            if fetch_duration > 3.0:
                logger.warning(f"⚠️  Slow memory fetch: {fetch_duration:.2f}s")
                fetch_span.add_event("slow_fetch_warning", {"threshold_ms": 3000})

        results = result.get("results", [])
        if not results:
            span.set_attribute("fetch.status", "not_found")
            raise ValueError(f"Memory not found: {id}")

        span.set_attribute("fetch.status", "found")
        tool_duration = time.time() - tool_start
        span.set_attribute("tool.duration_ms", tool_duration * 1000)
        logger.info(f"✅ Fetch completed in {tool_duration:.3f}s")

        return format_fetch_result(results[0])


# ============================================================================
# Server Entry Point
# ============================================================================


def main():
    """Main entry point for the unified SelfMemory MCP server."""
    import uvicorn

    logger.info("=" * 60)
    logger.info("🚀 Starting SelfMemory MCP Server (UNIFIED AUTH)")
    logger.info("=" * 60)
    logger.info(f"📡 Core Server: {CORE_SERVER_HOST}")
    logger.info(f"🌐 MCP Server: http://{config.server.host}:{config.server.port}")
    logger.info(f"🔐 Hydra Public: {config.hydra.public_url}")
    logger.info(f"🔐 Hydra Admin: {config.hydra.admin_url}")
    logger.info("")
    logger.info("🔑 Authentication Methods:")
    logger.info("   1. OAuth 2.1 (automatic via Hydra)")
    logger.info("   2. API Key (manual with --oauth no)")
    logger.info("")
    logger.info("📦 Installation:")
    logger.info("   OAuth:  npx install-mcp https://server/mcp --client claude")
    logger.info("   APIKey: npx install-mcp https://server/mcp --client claude \\")
    logger.info('             --oauth no --header "Authorization: Bearer <key>"')
    logger.info("")
    logger.info("🛠️  Tools: search, add, fetch (both auth methods)")

    # Check dev mode
    dev_mode = os.getenv("MCP_DEV_MODE", "false").lower() == "true"
    if dev_mode:
        logger.info("🔄 Development Mode: Auto-reload enabled")
    logger.info("=" * 60)

    if dev_mode:
        uvicorn.run(
            "main_unified:app",
            host=config.server.host,
            port=config.server.port,
            log_level="info",
            reload=True,
            reload_includes=["*.py"],
            reload_dirs=[str(Path(__file__).parent)],
        )
    else:
        uvicorn.run(
            app, host=config.server.host, port=config.server.port, log_level="info"
        )


if __name__ == "__main__":
    main()
