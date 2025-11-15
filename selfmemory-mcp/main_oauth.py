"""SelfMemory MCP Server with OAuth 2.1 Support

Implements OAuth 2.1 for ChatGPT integration while maintaining backward
compatibility with existing Bearer token authentication.

Features:
- OAuth 2.1 with PKCE (RFC 7636)
- Protected Resource Metadata (RFC 9728)
- Authorization Server Metadata (RFC 8414)
- Dynamic Client Registration (RFC 7591)
- ChatGPT-compatible tools: search, fetch
- Backward compatible tools: add_memory, search_memories
"""

import logging
import os
import sys
from pathlib import Path
from contextvars import ContextVar

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import Context, FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
import httpx

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

load_dotenv()

# Import OAuth components
from auth.token_extractor import create_project_client, extract_token_context, extract_bearer_token
from config import config
from oauth.metadata import get_protected_resource_metadata, create_401_response
from tools.fetch import format_fetch_result
from tools.search import format_search_results
from utils import create_tool_success, handle_tool_errors
from server.auth.hydra_validator import validate_token

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
CORE_SERVER_HOST = config.server.selfmemory_api_host

# Global ContextVar for storing OAuth token context per request
# This allows tools to access authentication info set by middleware
current_token_context: ContextVar[dict | None] = ContextVar('current_token_context', default=None)

# Initialize MCP server first (needed for lifespan)
mcp = FastMCP(
    name="SelfMemory",
    instructions="Memory management server with OAuth 2.1 for ChatGPT integration",
    stateless_http=True,
    json_response=True,
)

# Setup lifespan context manager
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Manage server lifecycle - ensures MCP session manager is running."""
    async with mcp.session_manager.run():
        yield

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="SelfMemory MCP Server",
    lifespan=lifespan
)

logger.info("SelfMemory MCP Server initialized with OAuth 2.1 support")

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
# OAuth Authentication Middleware
# ============================================================================

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
        
        # MCP Spec: Validate MCP-Protocol-Version header
        # Required on all requests after initialization
        protocol_version = request.headers.get("mcp-protocol-version")
        
        # Check if this is the initial initialization request
        # (InitializeRequest doesn't require the header yet)
        is_initialization = (
            request.method == "POST" and 
            request.url.path == "/mcp"
        )
        
        if not is_initialization and not protocol_version:
            logger.warning("Missing MCP-Protocol-Version header on non-initialization request")
            # For backward compatibility, assume latest version
            protocol_version = self.SUPPORTED_VERSIONS[0]
            logger.info(f"Defaulting to protocol version: {protocol_version}")
        
        # Validate version if present
        if protocol_version and protocol_version not in self.SUPPORTED_VERSIONS:
            logger.error(f"Unsupported MCP protocol version: {protocol_version}")
            return Response(
                content=f"Unsupported MCP protocol version: {protocol_version}. Supported versions: {', '.join(self.SUPPORTED_VERSIONS)}",
                status_code=400,
                media_type="text/plain"
            )
        
        # Store protocol version for later use
        if protocol_version:
            request.state.mcp_protocol_version = protocol_version
            logger.debug(f"MCP protocol version: {protocol_version}")
        
        # Check for Authorization header
        auth_header = request.headers.get("authorization")
        
        if not auth_header:
            # No auth header - return 401 with OAuth challenge
            logger.info(f"🔒 No Authorization header - returning OAuth challenge for {request.url.path}")
            
            error_response = create_401_response(
                error="invalid_token",
                error_description="Authorization required. Please authenticate via OAuth 2.0."
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
                headers={
                    "WWW-Authenticate": www_auth_header,
                    "Content-Type": "text/plain"
                }
            )
        
        # Extract and validate token
        try:
            token = extract_bearer_token(auth_header)
            hydra_token = validate_token(token)
            
            # Validate project context exists
            if not hydra_token.project_id:
                logger.error(f"❌ Token missing project context: subject={hydra_token.subject}")
                error_response = create_401_response(
                    error="insufficient_scope",
                    error_description="Token missing project context"
                )
                
                www_auth = error_response["www_authenticate"]
                www_auth_header = f'Bearer realm="{www_auth["realm"]}", error="{www_auth["error"]}", error_description="{www_auth["error_description"]}"'
                
                return Response(
                    content=error_response["error_description"],
                    status_code=401,
                    headers={
                        "WWW-Authenticate": www_auth_header,
                        "Content-Type": "text/plain"
                    }
                )
            
            # Create token context dictionary
            token_context_data = {
                "user_id": hydra_token.subject,
                "project_id": hydra_token.project_id,
                "organization_id": hydra_token.organization_id,
                "scopes": hydra_token.scopes,
                "raw_token": token,  # Store raw token for tools (avoids ctx.request access)
            }
            
            # Set in ContextVar for tool access
            current_token_context.set(token_context_data)
            
            # Also attach to request state for compatibility
            request.state.token_context = token_context_data
            
            logger.info(
                f"✅ Token validated and context set: user={hydra_token.subject}, "
                f"project={hydra_token.project_id}, scopes={hydra_token.scopes}"
            )
            
        except ValueError as e:
            # Invalid token
            logger.warning(f"❌ Token validation failed: {e}")
            
            error_response = create_401_response(
                error="invalid_token",
                error_description="Token validation failed"
            )
            
            www_auth = error_response["www_authenticate"]
            www_auth_header = f'Bearer realm="{www_auth["realm"]}", error="{www_auth["error"]}", error_description="{www_auth["error_description"]}"'
            
            return Response(
                content=error_response["error_description"],
                status_code=401,
                headers={
                    "WWW-Authenticate": www_auth_header,
                    "Content-Type": "text/plain"
                }
            )
        
        # Token valid - proceed with request
        response = await call_next(request)
        return response


# Register OAuth middleware
app.add_middleware(OAuthMiddleware)

@app.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata():
    """OAuth 2.0 Protected Resource Metadata (RFC 9728)."""
    return get_protected_resource_metadata()

# Add this to main_oauth.py temporarily
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"📥 {request.method} {request.url.path} - Headers: {dict(request.headers)}")
    response = await call_next(request)
    logger.info(f"📤 Response: {response.status_code}")
    return response

# Add to main_oauth.py
@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    logger.info(f"📍 {request.method} {request.url.path}")
    return await call_next(request)


# ============================================================================
# OAuth Discovery Proxy Endpoints (Forward to Hydra)
# ============================================================================

@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server(request: Request):
    """Proxy OAuth 2.0 Authorization Server Metadata to Hydra (RFC 8414).
    
    VS Code and other OAuth clients discover the authorization server
    by fetching this endpoint. Hydra only provides OIDC discovery, but
    OIDC configuration is a superset of OAuth 2.0 metadata, so we return it.
    
    We also inject the registration_endpoint since Hydra doesn't advertise it.
    The endpoint URL is dynamically built from the incoming request to support
    both local (localhost) and production (domain) access.
    """
    # Hydra doesn't have separate oauth-authorization-server endpoint
    # Use OIDC discovery which includes all OAuth 2.0 metadata
    hydra_url = f"{config.hydra.public_url}/.well-known/openid-configuration"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(hydra_url, timeout=10.0)
            response.raise_for_status()
            
            # Parse the response and inject registration_endpoint
            import json
            config_data = response.json()
            
            # Build registration_endpoint dynamically from request URL
            # This ensures localhost gets localhost URL, production gets production URL
            base_url = f"{request.url.scheme}://{request.url.netloc}"
            config_data["registration_endpoint"] = f"{base_url}/register"
            
            logger.info(f"✅ Proxied OAuth authorization server metadata with DCR endpoint: {base_url}/register")
            return Response(
                content=json.dumps(config_data),
                status_code=200,
                media_type="application/json"
            )
    except httpx.HTTPError as e:
        logger.error(f"❌ Failed to fetch authorization server metadata from Hydra: {e}")
        return Response(
            content=f"Failed to fetch authorization server metadata: {str(e)}",
            status_code=502,
            media_type="text/plain"
        )


@app.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request):
    """Proxy OpenID Connect Discovery to Hydra.
    
    Some OAuth clients prefer OpenID Connect discovery over plain OAuth.
    We proxy this to Hydra's OIDC discovery endpoint and inject the
    registration_endpoint so clients can use Dynamic Client Registration.
    """
    import json
    
    hydra_url = f"{config.hydra.public_url}/.well-known/openid-configuration"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(hydra_url, timeout=10.0)
            response.raise_for_status()
            
            # Parse and inject registration_endpoint
            config_data = response.json()
            
            # Build registration_endpoint dynamically from request URL
            base_url = f"{request.url.scheme}://{request.url.netloc}"
            config_data["registration_endpoint"] = f"{base_url}/register"
            
            logger.info(f"✅ Proxied OpenID Connect discovery with DCR endpoint: {base_url}/register")
            return Response(
                content=json.dumps(config_data),
                status_code=200,
                media_type="application/json"
            )
    except httpx.HTTPError as e:
        logger.error(f"❌ Failed to fetch OpenID configuration from Hydra: {e}")
        return Response(
            content=f"Failed to fetch OpenID configuration: {str(e)}",
            status_code=502,
            media_type="text/plain"
        )


@app.post("/register")
async def dynamic_client_registration(request: Request):
    """Proxy Dynamic Client Registration to Hydra (RFC 7591).
    
    Allows OAuth clients like VS Code to automatically register themselves
    with the authorization server without manual configuration.
    
    IMPORTANT: Injects memory scopes (memories:read, memories:write) into
    client registration so MCP tools can function properly.
    
    Follows HTTP redirects (e.g., 307) to handle Hydra's routing.
    """
    import json
    
    hydra_url = f"{config.hydra.admin_url}/clients"
    
    logger.info("=" * 80)
    logger.info("🔥 DYNAMIC CLIENT REGISTRATION CALLED!")
    logger.info(f"🔥 Request from: {request.client.host if request.client else 'unknown'}")
    logger.info(f"🔥 User-Agent: {request.headers.get('user-agent', 'unknown')}")
    logger.info("=" * 80)
    
    try:
        # Get and parse request body
        body_bytes = await request.body()
        registration_data = json.loads(body_bytes)
        
        logger.info(f"📝 Original registration request: {registration_data.get('client_name', 'Unknown client')}")
        logger.info(f"   Original scopes: {registration_data.get('scope', 'none')}")
        logger.info(f"   Redirect URIs: {registration_data.get('redirect_uris', [])}")
        logger.info(f"   Grant types: {registration_data.get('grant_types', [])}")
        
        # SANITIZE: Remove invalid optional metadata fields that Hydra will reject
        # Cursor/VS Code MCP client sends invalid URL fields that fail Hydra validation
        url_fields = ["client_uri", "logo_uri", "tos_uri", "policy_uri"]
        for field in url_fields:
            if field in registration_data:
                value = registration_data[field]
                # Remove null values, empty strings, or non-HTTP URLs
                if value is None or (isinstance(value, str) and (not value or not value.startswith(("http://", "https://")))):
                    logger.info(f"🧹 Removing invalid {field}: {repr(value)}")
                    del registration_data[field]
        
        # Handle contacts array - must be valid array or removed
        if "contacts" in registration_data:
            contacts = registration_data["contacts"]
            if contacts is None or not isinstance(contacts, list) or len(contacts) == 0:
                logger.info(f"🧹 Removing invalid contacts field: {repr(contacts)}")
                del registration_data["contacts"]
            else:
                # Validate each contact is a valid email
                valid_contacts = [c for c in contacts if c and isinstance(c, str) and "@" in c]
                if len(valid_contacts) == 0:
                    logger.info(f"🧹 Removing contacts with no valid emails")
                    del registration_data["contacts"]
                elif len(valid_contacts) < len(contacts):
                    logger.info(f"🧹 Filtered contacts: {len(contacts)} -> {len(valid_contacts)}")
                    registration_data["contacts"] = valid_contacts
        
        logger.info(f"✨ Sanitized registration data ready for Hydra")
        
        # Inject memory scopes into client registration
        current_scopes = registration_data.get("scope", "openid offline_access")
        if isinstance(current_scopes, str):
            current_scopes = current_scopes.split()
        elif isinstance(current_scopes, list):
            # Already a list, use as-is
            pass
        else:
            # Fallback to defaults if unexpected type
            current_scopes = ["openid", "offline_access"]
        
        # Normalize scope names (fix common client mistakes)
        # Keep BOTH 'offline' and 'offline_access' to handle clients that request either
        # This fixes the Hydra error: "Client is not allowed to request scope 'offline'"
        has_offline = 'offline' in current_scopes
        has_offline_access = 'offline_access' in current_scopes
        
        # Remove both variants first
        current_scopes = [s for s in current_scopes if s not in ['offline', 'offline_access']]
        
        # Add both variants so Hydra accepts either in authorization requests
        if has_offline or has_offline_access:
            current_scopes.extend(['offline', 'offline_access'])
        
        # Add memory scopes if not present
        required_scopes = ["memories:read", "memories:write"]
        for scope in required_scopes:
            if scope not in current_scopes:
                current_scopes.append(scope)
        
        # Update registration data with injected scopes
        registration_data["scope"] = " ".join(current_scopes)
        
        logger.info(f"✨ Injected memory scopes into registration")
        logger.info(f"   Updated scopes: {registration_data['scope']}")
        
        # Forward modified request to Hydra
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                hydra_url,
                json=registration_data,  # Send modified registration
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            
            if response.status_code in (200, 201):
                logger.info(f"✅ Dynamically registered OAuth client with Hydra (status {response.status_code})")
                logger.info(f"   Client can now request memory scopes: memories:read, memories:write")
                
                # SANITIZE RESPONSE: Remove invalid fields from Hydra's response
                # Hydra may return these fields as null/empty which MCP client rejects
                try:
                    response_data = response.json()
                    
                    # Remove invalid URL fields from response
                    for field in url_fields:
                        if field in response_data:
                            value = response_data[field]
                            if value is None or (isinstance(value, str) and (not value or not value.startswith(("http://", "https://")))):
                                logger.info(f"🧹 Removing invalid {field} from response: {repr(value)}")
                                del response_data[field]
                    
                    # Remove invalid contacts from response
                    if "contacts" in response_data:
                        contacts = response_data["contacts"]
                        if contacts is None or not isinstance(contacts, list) or len(contacts) == 0:
                            logger.info(f"🧹 Removing invalid contacts from response: {repr(contacts)}")
                            del response_data["contacts"]
                    
                    logger.info(f"✨ Sanitized response ready for MCP client")
                    
                    return Response(
                        content=json.dumps(response_data),
                        status_code=response.status_code,
                        media_type="application/json"
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"⚠️  Failed to sanitize response, returning as-is: {e}")
                    return Response(
                        content=response.content,
                        status_code=response.status_code,
                        media_type="application/json"
                    )
            else:
                logger.warning(f"⚠️  Client registration returned status {response.status_code}")
                logger.warning(f"Response: {response.text[:200]}")
            
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    media_type="application/json"
                )
    except httpx.HTTPError as e:
        logger.error(f"❌ Failed to register client with Hydra: {e}")
        return Response(
            content=f"Failed to register client: {str(e)}",
            status_code=502,
            media_type="text/plain"
        )
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse registration request body: {e}")
        return Response(
            content=f"Invalid registration request: {str(e)}",
            status_code=400,
            media_type="text/plain"
        )


# Mount MCP server
mcp.settings.streamable_http_path = "/"
app.mount("/mcp", mcp.streamable_http_app())


# ============================================================================
# ChatGPT-Compatible Tools (MCP 2025-06-18 Format)
# ============================================================================

@mcp.tool(
    annotations={
        "title": "Search Memories",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
@handle_tool_errors
async def search(query: str, ctx: Context) -> dict:
    """Search through stored memories. Required for ChatGPT deep research.
    
    Uses Hydra OAuth token context to scope search to authorized project.
    
    Args:
        query: Search query string for semantic memory search
        ctx: MCP context containing request with OAuth token
        
    Returns:
        Search results with memory IDs, titles, and URLs
    """
    logger.info(f"ChatGPT search: '{query}'")

    # Get token context from ContextVar (set by middleware)
    token_context = current_token_context.get()
    
    if not token_context:
        logger.error("❌ No token context available in ContextVar")
        raise ValueError("No authentication context available")
    
    logger.info(f"✅ Retrieved token context: user={token_context.get('user_id')}, project={token_context.get('project_id')}")
    
    # Verify required scopes
    if "memories:read" not in token_context["scopes"]:
        raise ValueError("Token missing required scope: memories:read")
    
    project_id = token_context["project_id"]
    logger.info(f"Search scoped to project: {project_id}")

    # Get raw OAuth token from context (avoids ctx.request access for Windsurf compatibility)
    oauth_token = token_context.get("raw_token")
    if not oauth_token:
        raise ValueError("No OAuth token in context")
    
    client = create_project_client(project_id, oauth_token, CORE_SERVER_HOST)

    result = client.search(query=query, limit=10)
    client.close()

    return format_search_results(result.get("results", []))


@mcp.tool(
    annotations={
        "title": "Add Memory",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False
    }
)
@handle_tool_errors
async def add(content: str, ctx: Context) -> dict:
    """Store a new memory (ChatGPT format).
    
    Uses Hydra OAuth token context to store memory in authorized project.
    
    Args:
        content: The memory content to store
        ctx: MCP context containing request with OAuth token
        
    Returns:
        Confirmation with memory ID and status
    """
    logger.info(f"ChatGPT add: {content[:50]}...")

    # Get token context from ContextVar (set by middleware)
    token_context = current_token_context.get()
    
    if not token_context:
        logger.error("❌ No token context available in ContextVar")
        raise ValueError("No authentication context available")
    
    logger.info(f"✅ Retrieved token context: user={token_context.get('user_id')}, project={token_context.get('project_id')}")
    
    # Verify required scopes
    if "memories:write" not in token_context["scopes"]:
        raise ValueError("Token missing required scope: memories:write")
    
    project_id = token_context["project_id"]
    logger.info(f"Add memory to project: {project_id}")

    # Get raw OAuth token from context (avoids ctx.request access for Windsurf compatibility)
    oauth_token = token_context.get("raw_token")
    if not oauth_token:
        raise ValueError("No OAuth token in context")
    
    client = create_project_client(project_id, oauth_token, CORE_SERVER_HOST)

    memory_data = {
        "messages": [{"role": "user", "content": content}],
        "metadata": {"source": "chatgpt", "project_id": project_id}
    }

    response = client.client.post("/api/memories", json=memory_data)
    response.raise_for_status()
    result = response.json()
    client.close()

    memory_id = result.get("id")
    return create_tool_success({
        "status": "success",
        "id": memory_id,
        "message": "Memory stored successfully"
    })


@mcp.tool(
    annotations={
        "title": "Fetch Memory",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
@handle_tool_errors
async def fetch(id: str, ctx: Context) -> dict:
    """Retrieve complete document content by ID.
    
    Uses Hydra OAuth token context to fetch memory from authorized project.
    
    Args:
        id: Unique memory identifier
        ctx: MCP context containing request with OAuth token
        
    Returns:
        Complete memory document with content and metadata
    """
    logger.info(f"ChatGPT fetch: id={id}")

    # Get token context from ContextVar (set by middleware)
    token_context = current_token_context.get()
    
    if not token_context:
        logger.error("❌ No token context available in ContextVar")
        raise ValueError("No authentication context available")
    
    logger.info(f"✅ Retrieved token context: user={token_context.get('user_id')}, project={token_context.get('project_id')}")
    
    # Verify required scopes
    if "memories:read" not in token_context["scopes"]:
        raise ValueError("Token missing required scope: memories:read")
    
    project_id = token_context["project_id"]
    logger.info(f"Fetch from project: {project_id}")

    # Get raw OAuth token from context (avoids ctx.request access for Windsurf compatibility)
    oauth_token = token_context.get("raw_token")
    if not oauth_token:
        raise ValueError("No OAuth token in context")
    
    client = create_project_client(project_id, oauth_token, CORE_SERVER_HOST)

    result = client.search(query=id, limit=1)
    client.close()

    results = result.get("results", [])
    if not results:
        raise ValueError(f"Memory not found: {id}")

    return format_fetch_result(results[0])




def main():
    """Main entry point for the SelfMemory MCP server."""
    import uvicorn

    logger.info("=" * 60)
    logger.info("🚀 Starting SelfMemory MCP Server with Hydra OAuth 2.1")
    logger.info("=" * 60)
    logger.info(f"📡 Core Server: {CORE_SERVER_HOST}")
    logger.info(f"🌐 Server: http://{config.server.host}:{config.server.port}")
    logger.info(f"🔐 Hydra Public: {config.hydra.public_url}")
    logger.info(f"🔐 Hydra Admin: {config.hydra.admin_url}")
    logger.info("🛠️  Tools: search, add, fetch (Hydra OAuth 2.1)")
    
    # Check if running in development mode (enable auto-reload)
    dev_mode = os.getenv("MCP_DEV_MODE", "false").lower() == "true"
    if dev_mode:
        logger.info("🔄 Development Mode: Auto-reload enabled")
    logger.info("=" * 60)

    if dev_mode:
        # For reload to work, need to pass app as import string
        uvicorn.run(
            "main_oauth:app",
            host=config.server.host,
            port=config.server.port,
            log_level="info",
            reload=True,
            reload_includes=["*.py"],
            reload_dirs=[str(Path(__file__).parent)]
        )
    else:
        # Production mode - pass app directly (no reload)
        uvicorn.run(
            app,
            host=config.server.host,
            port=config.server.port,
            log_level="info"
        )


if __name__ == "__main__":
    main()
