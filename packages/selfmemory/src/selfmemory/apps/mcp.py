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
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

# Load environment variables before any imports that depend on them
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import httpx  # noqa: E402
from fastapi import FastAPI, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from mcp.server.fastmcp import Context, FastMCP  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from opentelemetry import trace  # noqa: E402

from selfmemory.platform.mcp.telemetry import init_logging, init_telemetry  # noqa: E402

init_logging()
init_telemetry(service_name="selfmemory-mcp")

# Get tracer for tool instrumentation
tracer = trace.get_tracer(__name__)

from selfmemory.features.wiki.interfaces.mcp.fetch import (
    format_fetch_result,  # noqa: E402
)
from selfmemory.features.wiki.interfaces.mcp.search import (
    format_search_results,  # noqa: E402
)
from selfmemory.features.wiki.interfaces.mcp.wiki_client import WikiClient  # noqa: E402
from selfmemory.platform.mcp.auth.tool_auth import (
    get_validated_tool_context,  # noqa: E402
)
from selfmemory.platform.mcp.config import config  # noqa: E402
from selfmemory.platform.mcp.middleware import (  # noqa: E402
    UnifiedAuthMiddleware,
    current_token_context,
)
from selfmemory.platform.mcp.oauth.client_registration import (  # noqa: E402
    inject_memory_scopes,
    sanitize_registration_request,
    sanitize_registration_response,
)
from selfmemory.platform.mcp.oauth.discovery_proxy import (
    proxy_discovery_metadata,  # noqa: E402
)
from selfmemory.platform.mcp.oauth.metadata import (
    get_protected_resource_metadata,  # noqa: E402
)
from selfmemory.platform.mcp.utils import (  # noqa: E402
    create_tool_success,
    handle_tool_errors,
)

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
    instructions=(
        "Read access to an organization's knowledge wiki: search pages, fetch "
        "them, list the tree, or ask the wiki agent a question with citations."
    ),
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
#
# Read access to the organization's knowledge wiki. Every call forwards the
# caller's own token to the core server, which applies that caller's scopes.
# ============================================================================


def _wiki_client(ctx: Context) -> WikiClient:
    token_context = get_validated_tool_context(
        ctx, "memories:read", current_token_context
    )
    return WikiClient(CORE_SERVER_HOST, token_context["raw_token"])


_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


@mcp.tool(annotations={"title": "Search Wiki", **_READ_ONLY})
@handle_tool_errors
async def search(query: str, ctx: Context) -> dict:
    """Search the knowledge wiki for pages mentioning the query terms.

    Returns page paths usable with ``fetch``. Lexical, fast, no model call.

    Args:
        query: Words to look for
        ctx: MCP context
    """
    with tracer.start_as_current_span("mcp_tool.search") as span:
        span.set_attribute("query.length", len(query))
        result = await _wiki_client(ctx).search(query, limit=10)
        return format_search_results(result.get("results", []))


@mcp.tool(annotations={"title": "Fetch Wiki Page", **_READ_ONLY})
@handle_tool_errors
async def fetch(id: str, ctx: Context) -> dict:
    """Read one wiki page in full.

    Args:
        id: Page path from ``search`` or ``wiki_tree``,
            e.g. ``wiki/projects/<id>/policies/security-policy.md``
        ctx: MCP context
    """
    with tracer.start_as_current_span("mcp_tool.fetch"):
        page = await _wiki_client(ctx).fetch(id)
        return format_fetch_result(page)


@mcp.tool(annotations={"title": "Wiki Tree", **_READ_ONLY})
@handle_tool_errors
async def wiki_tree(ctx: Context) -> dict:
    """List every readable scope and the pages in it.

    Start from a scope's ``index.md`` and drill down: the wiki is an Open
    Knowledge Format hierarchy of category folders and concept pages.
    """
    with tracer.start_as_current_span("mcp_tool.wiki_tree"):
        tree = await _wiki_client(ctx).tree()
        scopes = [
            {
                "key": s["key"],
                "label": s["label"],
                "writable": s["writable"],
                "pages": s.get("files", []),
            }
            for s in tree.get("scopes", [])
        ]
        return create_tool_success({"scopes": scopes})


@mcp.tool(
    annotations={
        "title": "Ask the Wiki",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
@handle_tool_errors
async def ask(question: str, ctx: Context, scope: str | None = None) -> dict:
    """Ask a question answered by the wiki agent, with page citations.

    Slower than ``search``/``fetch`` (an agent reads the wiki), but follows
    links across pages. Read-only.

    Args:
        question: The question
        ctx: MCP context
        scope: Optional scope key to restrict to (e.g. ``project:<id>``)
    """
    with tracer.start_as_current_span("mcp_tool.ask"):
        run = await _wiki_client(ctx).ask(question, scope)
        result = run.get("result") or {}
        return create_tool_success(
            {
                "status": run.get("status"),
                "answer": result.get("answer", ""),
                "error": result.get("error"),
                "run_id": run.get("id"),
            }
        )


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
            "selfmemory.apps.mcp:app",
            host=config.server.host,
            port=config.server.port,
            log_level="info",
            reload=True,
            reload_includes=["*.py"],
            reload_dirs=[str(Path(__file__).resolve().parents[1])],
        )
    else:
        uvicorn.run(
            app, host=config.server.host, port=config.server.port, log_level="info"
        )


if __name__ == "__main__":
    main()
