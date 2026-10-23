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
        "An organization's knowledge wiki. Read: search, fetch, wiki_tree, "
        "list_scopes, list_files, read_file, ask, run_status. Write (needs the "
        "memories:write scope and write permission on the project): write_file, "
        "delete_file, ingest, cancel_run. Paths are relative to the org root, "
        "e.g. wiki/projects/<id>/page.md or raw/projects/<id>/notes.md."
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
# The organization's knowledge wiki. Every call forwards the caller's own
# token to the core server, which applies that caller's project permissions
# (writes need canWrite there). Here we additionally check the token's OAuth
# scope: memories:read for reads, memories:write for anything that changes data.
# ============================================================================


READ_SCOPE = "memories:read"
WRITE_SCOPE = "memories:write"


def _wiki_client(ctx: Context, scope: str = READ_SCOPE) -> WikiClient:
    """A client carrying the caller's token, after checking it has ``scope``."""
    token_context = get_validated_tool_context(ctx, scope, current_token_context)
    return WikiClient(CORE_SERVER_HOST, token_context["raw_token"])


_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

_WRITE = {
    "readOnlyHint": False,
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
async def ask(
    question: str, ctx: Context, scope: str | None = None, wait: bool = True
) -> dict:
    """Ask a question answered by the wiki agent, with page citations.

    Slower than ``search``/``fetch`` (an agent reads the wiki), but follows
    links across pages. Read-only.

    With ``wait=True`` (default) this blocks for up to a few minutes and
    returns the answer; if the agent is still working at the deadline it
    returns ``status: "running"`` and a ``run_id``. With ``wait=False`` it
    returns the ``run_id`` immediately. Either way, poll ``run_status`` with
    the ``run_id`` until the status is ``done``, ``failed`` or ``cancelled``.

    Args:
        question: The question
        ctx: MCP context
        scope: Optional scope key to restrict to (e.g. ``project:<id>``)
        wait: Block until the answer is ready (True) or return at once (False)
    """
    with tracer.start_as_current_span("mcp_tool.ask") as span:
        span.set_attribute("ask.wait", wait)
        client = _wiki_client(ctx)
        if not wait:
            job = await client.start_run("query", question, scope)
            return create_tool_success(
                {"status": job.get("status", "queued"), "run_id": job["job_id"]}
            )
        run = await client.ask(question, scope)
        return create_tool_success(_run_view(run))


def _run_view(run: dict) -> dict:
    result = run.get("result") or {}
    return {
        "status": run.get("status"),
        "answer": result.get("answer", ""),
        "error": result.get("error"),
        "run_id": run.get("id"),
    }


@mcp.tool(annotations={"title": "List Scopes", **_READ_ONLY})
@handle_tool_errors
async def list_scopes(ctx: Context) -> dict:
    """List the wiki scopes (org room, projects, sub-projects, personal) the
    caller can read, with whether each is writable.

    Each scope has a ``key`` (e.g. ``org``, ``project:<id>``) used by
    ``list_files``, ``ingest`` and ``ask``, plus its ``wiki`` and ``raw``
    folder paths: wiki pages live under ``wiki``, uploaded sources under
    ``raw``. Use those as path prefixes for ``read_file``/``write_file``.
    """
    with tracer.start_as_current_span("mcp_tool.list_scopes"):
        return create_tool_success(await _wiki_client(ctx).scopes())


@mcp.tool(annotations={"title": "List Files", **_READ_ONLY})
@handle_tool_errors
async def list_files(ctx: Context, scope: str | None = None) -> dict:
    """List wiki page paths, for every readable scope or just one.

    Returned paths can be passed straight to ``read_file``, ``write_file``
    or ``delete_file``.

    Args:
        ctx: MCP context
        scope: Optional scope key from ``list_scopes`` (e.g. ``project:<id>``);
            omit to list every readable scope
    """
    with tracer.start_as_current_span("mcp_tool.list_files"):
        tree = await _wiki_client(ctx).tree()
        scopes = tree.get("scopes", [])
        if scope is not None:
            scopes = [s for s in scopes if s.get("key") == scope]
            if not scopes:
                raise ValueError(f"scope not found or not readable: {scope}")
        return create_tool_success(
            {
                "scopes": [
                    {
                        "key": s["key"],
                        "label": s.get("label"),
                        "writable": s.get("writable", False),
                        "files": s.get("files", []),
                    }
                    for s in scopes
                ]
            }
        )


@mcp.tool(annotations={"title": "Read File", **_READ_ONLY})
@handle_tool_errors
async def read_file(path: str, ctx: Context) -> dict:
    """Read one file's raw content (a wiki page or an uploaded raw source).

    Unlike ``fetch`` this returns the exact text, suitable for editing and
    writing back with ``write_file``. Binary files return ``binary: true``
    and their ``size`` instead of ``content``.

    Args:
        path: File path relative to the org root, e.g.
            ``wiki/projects/<id>/policies/security-policy.md``
        ctx: MCP context

    Returns ``{path, side, scope, content}``; ``side`` is ``wiki`` or ``raw``.
    """
    with tracer.start_as_current_span("mcp_tool.read_file"):
        return create_tool_success(await _wiki_client(ctx).read_file(path))


@mcp.tool(annotations={"title": "Write File", **_WRITE})
@handle_tool_errors
async def write_file(path: str, content: str, ctx: Context) -> dict:
    """Create or fully replace one file. Requires write access.

    Writes under ``wiki/`` are committed to that scope's history; writes
    under ``raw/`` store a source document (run ``ingest`` afterwards to
    have the agent fold it into the wiki). The whole file is replaced, so
    ``read_file`` first when editing an existing page.

    Args:
        path: File path relative to the org root, e.g.
            ``wiki/projects/<id>/topics/onboarding.md``
        content: The complete new UTF-8 text of the file
        ctx: MCP context

    Returns ``{ok, side, sha}``; ``sha`` is the wiki commit (null for raw).
    """
    with tracer.start_as_current_span("mcp_tool.write_file") as span:
        span.set_attribute("content.length", len(content))
        result = await _wiki_client(ctx, WRITE_SCOPE).write_file(path, content)
        return create_tool_success(result)


@mcp.tool(
    annotations={
        "title": "Delete File",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
@handle_tool_errors
async def delete_file(path: str, ctx: Context) -> dict:
    """Delete one file. Requires write access.

    Wiki deletions are committed (recoverable from history); raw source
    deletions are not. A scope's agent-maintained ``index.md`` and
    ``log.md`` cannot be deleted.

    Args:
        path: File path relative to the org root
        ctx: MCP context
    """
    with tracer.start_as_current_span("mcp_tool.delete_file"):
        result = await _wiki_client(ctx, WRITE_SCOPE).delete_file(path)
        return create_tool_success(result)


@mcp.tool(
    annotations={
        "title": "Ingest into Wiki",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
@handle_tool_errors
async def ingest(scope: str, message: str, ctx: Context) -> dict:
    """Have the wiki agent ingest new knowledge into a scope. Requires write
    access.

    The agent reads ``message`` (the knowledge itself, or instructions such
    as "ingest the new files in raw/") plus the scope's raw sources, and
    updates the wiki pages. Returns a ``run_id`` immediately; ingests take
    minutes, so poll ``run_status`` until it is ``done`` or ``failed``.

    Args:
        scope: Scope key to write into, from ``list_scopes`` (e.g.
            ``project:<id>``); must be writable
        message: What to ingest
        ctx: MCP context
    """
    with tracer.start_as_current_span("mcp_tool.ingest"):
        job = await _wiki_client(ctx, WRITE_SCOPE).start_run("ingest", message, scope)
        return create_tool_success(
            {"status": job.get("status", "queued"), "run_id": job["job_id"]}
        )


@mcp.tool(
    annotations={
        "title": "Run Status",
        **_READ_ONLY,
        "idempotentHint": False,
    }
)
@handle_tool_errors
async def run_status(run_id: str, ctx: Context) -> dict:
    """Check an ``ask`` or ``ingest`` run started by this caller.

    ``status`` is one of ``queued``, ``running``, ``done``, ``failed`` or
    ``cancelled``. When finished, ``result`` holds the outcome (for ``ask``,
    ``result.answer``; on failure, ``result.error``).

    Args:
        run_id: The ``run_id`` returned by ``ask`` or ``ingest``
        ctx: MCP context
    """
    with tracer.start_as_current_span("mcp_tool.run_status"):
        run = await _wiki_client(ctx).run(run_id)
        return create_tool_success(
            {
                "run_id": run.get("id", run_id),
                "status": run.get("status"),
                "command": run.get("command"),
                "result": run.get("result"),
            }
        )


@mcp.tool(
    annotations={
        "title": "Cancel Run",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
@handle_tool_errors
async def cancel_run(run_id: str, ctx: Context) -> dict:
    """Cancel a queued or running ``ask``/``ingest`` run started by this
    caller. Requires write access.

    Args:
        run_id: The ``run_id`` to cancel
        ctx: MCP context
    """
    with tracer.start_as_current_span("mcp_tool.cancel_run"):
        run = await _wiki_client(ctx, WRITE_SCOPE).cancel_run(run_id)
        return create_tool_success(
            {"run_id": run.get("id", run_id), "status": run.get("status")}
        )


TOOL_NAMES = (
    "search",
    "fetch",
    "wiki_tree",
    "ask",
    "list_scopes",
    "list_files",
    "read_file",
    "write_file",
    "delete_file",
    "ingest",
    "run_status",
    "cancel_run",
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
    logger.info(f"🛠️  Tools: {', '.join(TOOL_NAMES)} (both auth methods)")

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
