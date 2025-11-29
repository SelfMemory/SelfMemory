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

import httpx

# Load environment variables FIRST, before any imports that depend on them
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import Context, FastMCP
from opentelemetry import trace
from telemetry import init_telemetry

load_dotenv()


init_telemetry(service_name="selfmemory-mcp")

# Get tracer for tool instrumentation
tracer = trace.get_tracer(__name__)


# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from auth.token_extractor import create_project_client  # noqa: E402
from config import config  # noqa: E402
from middleware import UnifiedAuthMiddleware, current_token_context  # noqa: E402
from oauth.metadata import get_protected_resource_metadata  # noqa: E402
from tools.fetch import format_fetch_result  # noqa: E402
from tools.search import format_search_results  # noqa: E402
from utils import create_tool_success, handle_tool_errors  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
CORE_SERVER_HOST = config.server.selfmemory_api_host

# Initialize MCP server
mcp = FastMCP(
    name="SelfMemory",
    instructions="Memory management server with unified authentication (OAuth 2.1 + API key)",
    stateless_http=False,
    json_response=True,
)


# Setup lifespan context manager
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Manage server lifecycle - ensures MCP session manager is running."""
    async with mcp.session_manager.run():
        yield


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="SelfMemory MCP Server (Unified Auth)",
    description="Supports both OAuth 2.1 and API key authentication",
    lifespan=lifespan,
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
    """Log all requests for debugging."""
    logger.info(f"📍 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"📤 Response: {response.status_code}")
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
    """Proxy OAuth 2.0 Authorization Server Metadata to Hydra (RFC 8414).

    VS Code and other OAuth clients discover the authorization server
    by fetching this endpoint. We proxy to Hydra's OIDC discovery and
    inject the registration_endpoint for Dynamic Client Registration.

    IMPORTANT: Points authorization_endpoint to our backend proxy to enable
    scope injection for Docker MCP Toolkit compatibility.
    """
    hydra_url = f"{config.hydra.public_url}/.well-known/openid-configuration"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(hydra_url, timeout=10.0)
            response.raise_for_status()

            config_data = response.json()

            # Inject registration endpoint (Hydra doesn't advertise this)
            base_url = f"{request.url.scheme}://{request.url.netloc}"
            config_data["registration_endpoint"] = f"{base_url}/register"

            logger.info(
                f"✅ Proxied OAuth authorization server metadata with DCR: {base_url}/register"
            )

            return Response(
                content=json.dumps(config_data),
                status_code=200,
                media_type="application/json",
            )
    except httpx.HTTPError as e:
        logger.error(f"❌ Failed to fetch authorization server metadata: {e}")
        return Response(
            content="Failed to fetch authorization server metadata.",
            status_code=502,
            media_type="text/plain",
        )


@app.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request):
    """Proxy OpenID Connect Discovery to Hydra.

    Some OAuth clients prefer OIDC discovery over plain OAuth.
    We proxy to Hydra and inject the registration_endpoint.
    """
    hydra_url = f"{config.hydra.public_url}/.well-known/openid-configuration"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(hydra_url, timeout=10.0)
            response.raise_for_status()

            config_data = response.json()

            # Inject registration endpoint
            base_url = f"{request.url.scheme}://{request.url.netloc}"
            config_data["registration_endpoint"] = f"{base_url}/register"

            # Note: authorization_endpoint stays as Hydra's (not modified)
            # Scope handling is done via consent-level fallback, not authorization proxy

            logger.info(
                f"✅ Proxied OpenID Connect discovery with DCR: {base_url}/register"
            )
            return Response(
                content=json.dumps(config_data),
                status_code=200,
                media_type="application/json",
            )
    except httpx.HTTPError as e:
        logger.error(f"❌ Failed to fetch OpenID configuration: {e}")
        return Response(
            content="Failed to fetch OpenID configuration.",
            status_code=502,
            media_type="text/plain",
        )


@app.post("/register")
async def dynamic_client_registration(request: Request):
    """Proxy Dynamic Client Registration to Hydra (RFC 7591).

    Allows OAuth clients like VS Code to automatically register themselves.
    Injects memory scopes (memories:read, memories:write) into registration.
    """
    hydra_url = f"{config.hydra.admin_url}/clients"

    logger.info("=" * 80)
    logger.info("🔥 DYNAMIC CLIENT REGISTRATION")
    logger.info(f"🔥 From: {request.client.host if request.client else 'unknown'}")
    logger.info("=" * 80)

    try:
        # Get and parse request body
        body_bytes = await request.body()
        registration_data = json.loads(body_bytes)

        client_name = registration_data.get("client_name", "Unknown")
        logger.info(f"📝 Client: {client_name}")

        # DIAGNOSTIC: Log audience configuration
        logger.info("🔍 DCR AUDIENCE CONFIG:")
        logger.info(f"   MCP_SERVER_URL from config: {config.hydra.mcp_server_url}")
        logger.info(
            f"   MCP_SERVER_URL from env: {os.getenv('MCP_SERVER_URL', 'NOT SET')}"
        )
        logger.info(f"   Request base URL: {request.url.scheme}://{request.url.netloc}")

        # Sanitize invalid URL fields (Hydra rejects null/empty URLs)
        url_fields = ["client_uri", "logo_uri", "tos_uri", "policy_uri"]
        for field in url_fields:
            if field in registration_data:
                value = registration_data[field]
                if value is None or (
                    isinstance(value, str)
                    and (not value or not value.startswith(("http://", "https://")))
                ):
                    logger.info(f"🧹 Removing invalid {field}: {repr(value)}")
                    del registration_data[field]

        # Sanitize contacts array
        if "contacts" in registration_data:
            contacts = registration_data["contacts"]
            if contacts is None or not isinstance(contacts, list) or len(contacts) == 0:
                logger.info(f"🧹 Removing invalid contacts: {repr(contacts)}")
                del registration_data["contacts"]

        # === SCOPE-AGNOSTIC HANDLING ===
        # Accept whatever scopes the client sends, and ensure our required scopes are included
        # This makes the server work with ANY OAuth client (Docker, Windsurf, ChatGPT, etc.)

        current_scopes = registration_data.get("scope", "openid offline_access")
        if isinstance(current_scopes, str):
            current_scopes = current_scopes.split()
        elif not isinstance(current_scopes, list):
            current_scopes = ["openid", "offline_access"]

        logger.info(f"📥 Client requested scopes: {' '.join(current_scopes)}")

        # Fix offline scope (accept both offline and offline_access)
        has_offline = "offline" in current_scopes or "offline_access" in current_scopes
        current_scopes = [
            s for s in current_scopes if s not in ["offline", "offline_access"]
        ]
        if has_offline:
            current_scopes.extend(["offline", "offline_access"])

        # Always ensure our core memory scopes are included (required for tools to work)
        required_scopes = ["memories:read", "memories:write"]
        for scope in required_scopes:
            if scope not in current_scopes:
                current_scopes.append(scope)
                logger.info(f"➕ Added required scope: {scope}")

        # Keep any client-specific scopes (mcp.read, mcp.write, etc.) - we're scope-agnostic
        registration_data["scope"] = " ".join(current_scopes)
        logger.info(f"✨ Final scopes: {registration_data['scope']}")

        # Forward to Hydra
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                hydra_url,
                json=registration_data,
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )

            if response.status_code in (200, 201):
                logger.info("✅ Client registered with Hydra")

                # Sanitize response
                response_data = response.json()
                for field in url_fields:
                    if field in response_data:
                        value = response_data[field]
                        if value is None or (
                            isinstance(value, str)
                            and not value.startswith(("http://", "https://"))
                        ):
                            del response_data[field]

                return Response(
                    content=json.dumps(response_data),
                    status_code=response.status_code,
                    media_type="application/json",
                )
            logger.warning(f"⚠️  Registration returned {response.status_code}")
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type="application/json",
            )
    except httpx.HTTPError as e:
        logger.error(f"❌ Failed to register client: {e}")
        return Response(
            content="Failed to register client due to a server error.",
            status_code=502,
            media_type="text/plain",
        )


# Helper function to get auth context
def get_auth_from_context(ctx: Context) -> dict:
    """Extract authentication context from FastMCP Context.

    Uses two methods in order of preference:
    1. request.scope['auth_context'] - Standard ASGI scope (set by UnifiedAuthMiddleware)
    2. ContextVar - Thread-safe context variable (set by UnifiedAuthMiddleware)

    MCP requests are sequential per session, making this approach safe.
    """
    # Priority 1: Access request.scope['auth_context'] via request_context
    # This is where UnifiedAuthMiddleware injects the auth context (propagates to mounted apps)
    if hasattr(ctx, "request_context") and ctx.request_context:
        logger.debug("🔍 Accessing request_context from FastMCP Context")
        try:
            request = ctx.request_context.request
            if hasattr(request, "scope"):
                auth_context = request.scope.get("auth_context")
                if auth_context:
                    logger.debug("✅ Got auth from request.scope['auth_context']")
                    return auth_context
        except Exception as e:
            logger.warning(f"⚠️  Error accessing request_context: {e}")

    # Priority 2: Try ContextVar (set by UnifiedAuthMiddleware)
    token_context = current_token_context.get()
    if token_context:
        logger.debug("✅ Got auth from ContextVar")
        return token_context

    # No auth context found - this should not happen if middleware is working
    logger.error("❌ No auth context available from any source")
    raise ValueError("Authentication context not available")


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
        logger.info(f"🔍 Search: '{query}'")

        # Get token context from MCP Context (set by middleware)
        with tracer.start_as_current_span("get_token_context"):
            token_context = get_auth_from_context(ctx)

            if not token_context:
                logger.error("❌ No token context available in search tool")
                raise ValueError("No authentication context available")

            logger.info(
                f"✅ Auth via {token_context.get('auth_type')}: user={token_context.get('user_id')}"
            )

            span.set_attribute("auth.type", token_context.get("auth_type"))
            span.set_attribute("user.id", token_context.get("user_id"))
            span.set_attribute("project.id", token_context.get("project_id", ""))

        # Verify required scopes
        with tracer.start_as_current_span("verify_scopes"):
            if "memories:read" not in token_context["scopes"]:
                raise ValueError("Token missing required scope: memories:read")

        project_id = token_context["project_id"]
        oauth_token = token_context["raw_token"]

        # Create client and execute search (works with both OAuth tokens and API keys)
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
        logger.info(f"➕ Add: {content[:50]}...")

        # Get token context from MCP Context
        with tracer.start_as_current_span("get_token_context"):
            token_context = get_auth_from_context(ctx)

            if not token_context:
                logger.error("❌ No token context available in add tool")
                raise ValueError("No authentication context available")

            logger.info(
                f"✅ Auth via {token_context.get('auth_type')}: user={token_context.get('user_id')}"
            )

            span.set_attribute("auth.type", token_context.get("auth_type"))
            span.set_attribute("user.id", token_context.get("user_id"))
            span.set_attribute("project.id", token_context.get("project_id", ""))

        # Verify required scopes
        with tracer.start_as_current_span("verify_scopes"):
            if "memories:write" not in token_context["scopes"]:
                raise ValueError("Token missing required scope: memories:write")

        project_id = token_context["project_id"]
        oauth_token = token_context["raw_token"]

        # Create client and store memory
        with tracer.start_as_current_span("store_memory") as store_span:
            store_start = time.time()
            client = create_project_client(project_id, oauth_token, CORE_SERVER_HOST)

            memory_data = {
                "messages": [{"role": "user", "content": content}],
                "metadata": {"source": "mcp_unified", "project_id": project_id},
            }

            response = client.client.post("/api/memories", json=memory_data)
            response.raise_for_status()
            result = response.json()
            # Don't close cached clients - let cache manage lifecycle

            store_duration = time.time() - store_start
            store_span.set_attribute("store.duration_ms", store_duration * 1000)
            store_span.set_attribute("memory.id", result.get("id", ""))

            if store_duration > 3.0:
                logger.warning(f"⚠️  Slow memory storage: {store_duration:.2f}s")
                store_span.add_event("slow_store_warning", {"threshold_ms": 3000})

        tool_duration = time.time() - tool_start
        span.set_attribute("tool.duration_ms", tool_duration * 1000)
        logger.info(f"✅ Add completed in {tool_duration:.3f}s")

        memory_id = result.get("id")
        return create_tool_success(
            {
                "status": "success",
                "id": memory_id,
                "message": "Memory stored successfully",
            }
        )


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
        logger.info(f"📥 Fetch: id={id}")

        # Get token context from MCP Context
        with tracer.start_as_current_span("get_token_context"):
            token_context = get_auth_from_context(ctx)

            if not token_context:
                logger.error("❌ No token context available in fetch tool")
                raise ValueError("No authentication context available")

            logger.info(
                f"✅ Auth via {token_context.get('auth_type')}: user={token_context.get('user_id')}"
            )

            span.set_attribute("auth.type", token_context.get("auth_type"))
            span.set_attribute("user.id", token_context.get("user_id"))
            span.set_attribute("project.id", token_context.get("project_id", ""))

        # Verify required scopes
        with tracer.start_as_current_span("verify_scopes"):
            if "memories:read" not in token_context["scopes"]:
                raise ValueError("Token missing required scope: memories:read")

        project_id = token_context["project_id"]
        oauth_token = token_context["raw_token"]

        # Fetch memory
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
