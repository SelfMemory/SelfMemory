import logging
from typing import Any

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from pydantic import BaseModel, Field, field_validator
from pydantic import BaseModel as PydanticBaseModel
from slowapi.errors import RateLimitExceeded

from selfmemory import SelfMemory

from .config import config
from .dependencies import AuthContext, authenticate_api_key, mongo_db
from .health import is_alive, is_ready, perform_health_checks
from .mcp_auth import get_protected_resource_metadata
from .routes.api_keys import router as api_keys_router
from .routes.chat import router as chat_router
from .routes.hydra_proxy import router as hydra_proxy_router
from .routes.invitations import router as invitations_router
from .routes.notifications import router as notifications_router
from .routes.organizations import router as organizations_router
from .routes.projects import router as projects_router
from .routes.users import router as users_router
from .telemetry import initialize_telemetry
from .utils.datetime_helpers import utc_now
from .utils.error_handlers import ErrorCode, create_error_response, get_request_id
from .utils.permission_helpers import get_user_object_id_from_kratos_id
from .utils.rate_limiter import get_rate_limit_key, limiter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()


# CSRF Protection Configuration
class CsrfSettings(PydanticBaseModel):
    secret_key: str = config.security.CSRF_SECRET_KEY or ""
    cookie_name: str = config.security.CSRF_COOKIE_NAME
    cookie_samesite: str = config.security.CSRF_COOKIE_SAMESITE.lower()
    cookie_secure: bool = config.security.CSRF_COOKIE_SECURE
    cookie_httponly: bool = config.security.CSRF_COOKIE_HTTPONLY
    header_name: str = config.security.CSRF_HEADER_NAME


@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()


DEFAULT_CONFIG = {
    "vector_store": {
        "provider": config.vector_store.PROVIDER,
        "config": {
            "collection_name": config.vector_store.COLLECTION_NAME,
            "host": config.vector_store.HOST,
            "port": config.vector_store.PORT,
        },
    },
    "embedding": {
        "provider": config.embedding.PROVIDER,
        "config": {
            "model": config.embedding.MODEL,
            "ollama_base_url": config.embedding.OLLAMA_BASE_URL,
        },
    },
    "llm": {
        "provider": "vllm",
        "config": {
            "vllm_base_url": config.llm.BASE_URL,
            "model": config.llm.MODEL,
            "api_key": config.llm.API_KEY,
            "temperature": config.llm.TEMPERATURE,
            "max_tokens": config.llm.MAX_TOKENS,
        },
    },
}

# Global Memory instance
MEMORY_INSTANCE = SelfMemory(config=DEFAULT_CONFIG)

# Validate configuration on startup
config_errors = config.validate()
if config_errors:
    logging.error("=" * 50)
    logging.error("CONFIGURATION VALIDATION FAILED")
    logging.error("=" * 50)
    for error in config_errors:
        logging.error(f"  ❌ {error}")
    logging.error("=" * 50)
    logging.error("Please fix the configuration errors before starting the server.")
    raise RuntimeError("Configuration validation failed. See logs for details.")

# Log configuration (excluding sensitive values)
config.log_config()

# FastAPI app
app = FastAPI(
    title="SelfMemory APIs",
)

# Initialize OpenTelemetry (production only)
initialize_telemetry(app)

# Add rate limiting to app state
app.state.limiter = limiter


# Request ID middleware - adds X-Request-ID to all requests
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """Add request ID to all requests for tracking and correlation."""
    request_id = get_request_id(request)
    # Store in request state for use in handlers
    request.state.request_id = request_id
    # Call next middleware/handler
    response = await call_next(request)
    # Add to response headers
    response.headers["X-Request-ID"] = request_id
    return response


# CORS middleware
# NOTE: Cannot use allow_origins=["*"] with allow_credentials=True
# Browsers block credentials with wildcard origins for security
# NOTE: Must include BOTH localhost and 127.0.0.1 as browsers treat them as different origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Dashboard (localhost)
        "http://127.0.0.1:3000",  # Dashboard (127.0.0.1)
        "http://localhost:8081",  # Backend API (localhost)
        "http://127.0.0.1:8081",  # Backend API (127.0.0.1)
        config.app.FRONTEND_URL,  # Dynamic frontend URL from config
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate Limit Exception Handler
@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors with clear messages and logging."""
    request_id = get_request_id(request)
    client_key = get_rate_limit_key(request)

    logging.warning(
        f"⚠️ RATE LIMIT EXCEEDED: "
        f"path={request.url.path}, "
        f"method={request.method}, "
        f"client={client_key}, "
        f"limit={exc.detail}, "
        f"request_id={request_id}"
    )

    return create_error_response(
        code=ErrorCode.RATE_LIMIT_EXCEEDED,
        message="Too many requests. Please slow down and try again later.",
        status_code=429,
        request_id=request_id,
    )


# CSRF Exception Handler
@app.exception_handler(CsrfProtectError)
def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError):
    """Handle CSRF protection errors with clear error messages."""
    request_id = get_request_id(request)

    logging.warning(
        f"CSRF validation failed: message={exc.message}, request_id={request_id}"
    )

    return create_error_response(
        code=ErrorCode.CSRF_TOKEN_INVALID,
        message="CSRF token validation failed. Please refresh and try again.",
        status_code=403,
        request_id=request_id,
    )


# CSRF Token Endpoint
@app.get("/api/csrf-token", summary="Get CSRF token")
async def get_csrf_token(
    request: Request, response: Response, csrf_protect: CsrfProtect = Depends()
):
    """
    Get CSRF token for subsequent state-changing requests.
    The token will be set in a cookie and also returned in the response.
    """
    # Generate and set CSRF token
    csrf_token = csrf_protect.generate_csrf()
    response.set_cookie(
        key=config.security.CSRF_COOKIE_NAME,
        value=csrf_token,
        secure=config.security.CSRF_COOKIE_SECURE,
        httponly=config.security.CSRF_COOKIE_HTTPONLY,
        samesite=config.security.CSRF_COOKIE_SAMESITE.lower(),
    )
    return {"csrf_token": csrf_token, "message": "CSRF token generated successfully"}


# Include routers
app.include_router(api_keys_router)
app.include_router(chat_router)
app.include_router(hydra_proxy_router)
app.include_router(invitations_router)
app.include_router(notifications_router)
app.include_router(organizations_router)
app.include_router(projects_router)
app.include_router(users_router)


# API Keys endpoint (query parameter version for frontend compatibility)
@app.get("/api/api-keys", summary="List project API keys (query param version)")
@limiter.limit(config.rate_limit.MEMORY_READ)
def list_api_keys_query(
    request: Request, project_id: str, auth: AuthContext = Depends(authenticate_api_key)
):
    """
    List API keys for a project using query parameter.
    This is a compatibility endpoint for the frontend.
    Delegates to the main api_keys route handler.
    """
    from .dependencies import check_project_access
    from .utils.validators import validate_object_id

    logging.info(
        f"🔍 DEBUG /api/api-keys: user={auth.user_id}, project_id={project_id}"
    )

    # Get MongoDB ObjectId from Kratos ID
    user_obj_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)
    project_obj_id = validate_object_id(project_id, "project_id")

    # Verify project exists
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        logging.error(f"❌ Project not found: {project_id}")
        raise HTTPException(status_code=404, detail="Project not found")

    logging.info(
        f"🔍 DEBUG project found: owner={project.get('ownerId')}, org={project.get('organizationId')}"
    )

    # Check organization ownership
    org = mongo_db.organizations.find_one({"_id": project["organizationId"]})
    if org:
        logging.info(
            f"🔍 DEBUG org found: owner={org.get('ownerId')}, is_org_owner={str(org.get('ownerId')) == auth.user_id}"
        )

    # Check project ownership
    logging.info(
        f"🔍 DEBUG is_project_owner={str(project.get('ownerId')) == auth.user_id}"
    )

    # Check membership
    member = mongo_db.project_members.find_one(
        {"projectId": project_obj_id, "userId": user_obj_id}
    )
    logging.info(
        f"🔍 DEBUG project_member found: {member is not None}, member_data={member}"
    )

    # Check if user has access to the project (owner or member)
    has_access = check_project_access(auth.user_id, project_id)
    logging.info(f"🔍 DEBUG check_project_access result: {has_access}")

    if not has_access:
        logging.warning(
            f"❌ User {auth.user_id} attempted to list API keys for project {project_id} without access"
        )
        raise HTTPException(
            status_code=403, detail="You do not have access to this project"
        )

    # Get ALL API keys for this project (team transparency)
    api_keys = list(mongo_db.api_keys.find({"projectId": project_obj_id}))

    # Enrich with user information and remove sensitive data
    result_keys = []
    for key in api_keys:
        # Get user info for owner email
        user = mongo_db.users.find_one({"_id": key["userId"]})
        owner_email = user.get("email", "Unknown") if user else "Unknown"

        result_keys.append(
            {
                "id": str(key["_id"]),
                "name": key.get("name", "Unnamed Key"),
                "key_prefix": key.get("keyPrefix", "sk_im_..."),
                "owner_id": str(key["userId"]),
                "owner_email": owner_email,
                "permissions": key.get("permissions", []),
                "is_active": key.get("isActive", True),
                "created_at": key.get("createdAt").isoformat()
                if key.get("createdAt")
                else None,
                "last_used": key.get("lastUsed").isoformat()
                if key.get("lastUsed")
                else None,
                "expires_at": key.get("expiresAt").isoformat()
                if key.get("expiresAt")
                else None,
            }
        )

    logging.info(
        f"✅ User {auth.user_id} listed {len(result_keys)} API keys for project {project_id}"
    )

    return {"api_keys": result_keys, "total": len(result_keys)}


# Pydantic models (selfmemory style)
class Message(BaseModel):
    role: str = Field(..., description="Role of the message (user or assistant).")
    content: str = Field(..., description="Message content.")


class MemoryCreate(BaseModel):
    messages: list[Message] = Field(..., description="List of messages to store.")
    user_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("messages")
    @classmethod
    def validate_messages_content(cls, v: list[Message]) -> list[Message]:
        """Validate message content length."""
        for msg in v:
            if len(msg.content) > config.validation.MEMORY_CONTENT_MAX_LENGTH:
                raise ValueError(
                    f"Message content exceeds maximum length of {config.validation.MEMORY_CONTENT_MAX_LENGTH} characters"
                )
        return v


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    people_mentioned: str | None = None
    filters: dict[str, Any] | None = None


# Multi-tenant Pydantic models
class OrganizationCreate(BaseModel):
    name: str = Field(
        ...,
        description="Organization name.",
        min_length=config.validation.ORG_NAME_MIN_LENGTH,
        max_length=config.validation.ORG_NAME_MAX_LENGTH,
    )

    @field_validator("name")
    @classmethod
    def validate_name_pattern(cls, v: str) -> str:
        """Validate organization name contains only allowed characters."""
        import re

        if not re.match(config.validation.ORG_NAME_PATTERN, v):
            raise ValueError(
                "Organization name can only contain letters, numbers, spaces, hyphens, and underscores"
            )
        # Strip leading/trailing whitespace
        v = v.strip()
        if len(v) < config.validation.ORG_NAME_MIN_LENGTH:
            raise ValueError(
                f"Organization name must be at least {config.validation.ORG_NAME_MIN_LENGTH} characters"
            )
        return v


class ProjectCreate(BaseModel):
    name: str = Field(
        ...,
        description="Project name.",
        min_length=config.validation.PROJECT_NAME_MIN_LENGTH,
        max_length=config.validation.PROJECT_NAME_MAX_LENGTH,
    )
    organization_id: str = Field(
        ..., description="Organization ID this project belongs to."
    )

    @field_validator("name")
    @classmethod
    def validate_name_pattern(cls, v: str) -> str:
        """Validate project name contains only allowed characters."""
        import re

        if not re.match(config.validation.PROJECT_NAME_PATTERN, v):
            raise ValueError(
                "Project name can only contain letters, numbers, spaces, hyphens, and underscores"
            )
        # Strip leading/trailing whitespace
        v = v.strip()
        if len(v) < config.validation.PROJECT_NAME_MIN_LENGTH:
            raise ValueError(
                f"Project name must be at least {config.validation.PROJECT_NAME_MIN_LENGTH} characters"
            )
        return v


class ApiKeyCreate(BaseModel):
    name: str = Field(..., description="API key name.", min_length=1, max_length=100)
    project_id: str = Field(..., description="Project ID this API key is scoped to.")
    permissions: list[str] = Field(
        default=["read", "write"], description="API key permissions."
    )
    expires_in_days: int | None = Field(
        default=None, description="API key expiration in days (optional)."
    )


# API Endpoints (enhanced for multi-tenant support)
@app.get("/api/v1/ping", summary="Ping endpoint for client validation")
def ping_endpoint(auth: AuthContext = Depends(authenticate_api_key)):
    """Ping endpoint that returns user info on successful authentication with multi-tenant context."""
    return {
        "status": "ok",
        "user_id": auth.user_id,
        "project_id": auth.project_id,
        "organization_id": auth.organization_id,
        "key_id": "default",
        "permissions": ["read", "write"],
        "name": "SelfMemory User",
    }


@app.post("/configure", summary="Configure SelfMemory")
def set_config(config: dict[str, Any]):
    """Set memory configuration (selfmemory style)."""
    global MEMORY_INSTANCE
    MEMORY_INSTANCE = SelfMemory(config=config)
    return {"message": "Configuration set successfully"}


@app.post("/api/memories", summary="Create memories with multi-tenant isolation")
@limiter.limit(config.rate_limit.MEMORY_CREATE)
def add_memory(
    request: Request,
    memory_create: MemoryCreate,
    auth: AuthContext = Depends(authenticate_api_key),
    project_id: str | None = None,
    organization_id: str | None = None,
):
    """Store new memories with multi-tenant isolation (supports both API key and Session auth)."""
    if not any(
        [
            memory_create.user_id,
            memory_create.agent_id,
            memory_create.run_id,
            auth.user_id,
        ]
    ):
        raise HTTPException(
            status_code=400, detail="At least one identifier is required."
        )

    try:
        # For Session auth, extract and validate project context from request
        if auth.project_id is None:
            # Session authentication - get project context from query params or metadata
            requested_project_id = project_id or (memory_create.metadata or {}).get(
                "project_id"
            )

            try:
                project_obj_id = ObjectId(requested_project_id)
                # user_obj_id = ObjectId(auth.user_id)  # Remove unused assignment
            except Exception as err:
                raise HTTPException(
                    status_code=400, detail="Invalid project_id or user_id format"
                ) from err

            # Use Phase 6 helper function to check access (not just ownership)
            from .dependencies import check_project_access

            if not check_project_access(auth.user_id, requested_project_id):
                logging.warning(
                    f"❌ Session user {auth.user_id} does not have access to project {requested_project_id}"
                )
                raise HTTPException(status_code=403, detail="Access denied to project")

            # Get project details for organization context
            project = mongo_db.projects.find_one({"_id": project_obj_id})
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Set validated project context
            final_project_id = str(project["_id"])
            # final_org_id = str(project["organizationId"])  # Remove unused assignment

            logging.info(
                f"✅ Session auth project validated: user={auth.user_id}, project={final_project_id}"
            )
        else:
            # API key authentication - use key's scoped context
            # Reject attempts to specify different project/org
            metadata = memory_create.metadata or {}
            if (
                metadata.get("project_id")
                and metadata.get("project_id") != auth.project_id
            ):
                logging.warning(
                    f"❌ ISOLATION VIOLATION: User {auth.user_id} attempted to create memory in project {metadata.get('project_id')} but API key is scoped to {auth.project_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="API key is not authorized for the requested project",
                )

            if (
                metadata.get("organization_id")
                and metadata.get("organization_id") != auth.organization_id
            ):
                logging.warning(
                    f"❌ ISOLATION VIOLATION: User {auth.user_id} attempted to create memory in org {metadata.get('organization_id')} but API key is scoped to {auth.organization_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="API key is not authorized for the requested organization",
                )

            final_project_id = auth.project_id

        # PHASE 7: Check write permission
        from .dependencies import has_permission

        if not has_permission(auth.user_id, final_project_id, "write"):
            logging.warning(
                f"❌ User {auth.user_id} does not have write permission for project {final_project_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Permission denied - write access required to create memories",
            )

        # PHASE 7: Get user email for creator attribution
        # Note: auth.user_id is Kratos identity_id (string), not ObjectId
        user = mongo_db.users.find_one({"_id": auth.user_id})
        user_email = user.get("email", "unknown") if user else "unknown"

        # Extract memory content from messages (selfmemory style)
        memory_content = ""
        if memory_create.messages:
            memory_content = " ".join([msg.content for msg in memory_create.messages])

        # Extract metadata fields for selfmemory-core compatibility
        metadata = memory_create.metadata or {}
        tags = metadata.get("tags", "")
        people_mentioned = metadata.get("people_mentioned", "")
        topic_category = metadata.get("topic_category", "")

        # Creator attribution metadata
        creator_metadata = {
            "createdBy": auth.user_id,
            "createdByEmail": user_email,
        }

        # Project-level memory: All project members share the same memory space
        # Use project_id as the session identifier (selfmemory pattern)
        # Track actual creator in metadata for attribution
        logging.info(
            f"📝 Creating memory: project={final_project_id}, creator={auth.user_id} ({user_email})"
        )

        response = MEMORY_INSTANCE.add(
            messages=memory_content,
            user_id=final_project_id,  # Project as session identifier for shared memories
            tags=tags,
            people_mentioned=people_mentioned,
            topic_category=topic_category,
            metadata=creator_metadata,
        )

        # Handle different response formats from _add_with_llm and _add_without_llm
        if "results" in response:
            # response from _add_with_llm
            results = response.get("results", [])
            if results:
                # Extract memory ID from first result
                memory_id = results[0].get("id") if results else None
                logging.info(
                    f"✅ Memory created (LLM): project={final_project_id}, memory_id={memory_id}, operations={len(results)}, creator={user_email}"
                )
                return JSONResponse(
                    content={
                        "success": True,
                        "memory_id": memory_id,
                        "operations": results,
                        "message": f"Memory processed with {len(results)} operations",
                    }
                )
            # Empty results - no changes needed, this is a valid scenario
            logging.info(
                f"✅ LLM determined no memory changes needed for project={final_project_id}, creator={user_email}"
            )
            return JSONResponse(
                content={
                    "success": True,
                    "message": "No memory changes required - content already adequately captured",
                    "operations": [],
                    "memory_id": None,
                }
            )
        # Standard response from _add_without_llm
        memory_id = response.get("memory_id")
        logging.info(
            f"✅ Memory created: project={final_project_id}, memory_id={memory_id}, creator={user_email}"
        )
        return JSONResponse(content=response)
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/memories", summary="Get memories with multi-tenant isolation")
@limiter.limit(config.rate_limit.MEMORY_READ)
def get_all_memories(
    request: Request,
    project_id: str | None = None,
    organization_id: str | None = None,
    limit: int = config.pagination.MAX_LIMIT,
    offset: int = 0,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """Retrieve stored memories with multi-tenant isolation (supports both API key and Session auth)."""
    try:
        # For Session auth, extract and validate project context from request
        if auth.project_id is None:
            # Session authentication - get project context from query params
            if not project_id:
                raise HTTPException(
                    status_code=400,
                    detail="project_id required for session authentication",
                )

            # Validate user has access to the project (owner or member)
            try:
                project_obj_id = ObjectId(project_id)
                # user_obj_id = ObjectId(auth.user_id)  # Remove unused assignment
            except Exception as err:
                raise HTTPException(
                    status_code=400, detail="Invalid project_id or user_id format"
                ) from err

            # Use Phase 6 helper function to check access (not just ownership)
            from .dependencies import check_project_access

            if not check_project_access(auth.user_id, project_id):
                logging.warning(
                    f"❌ Session user {auth.user_id} does not have access to project {project_id}"
                )
                raise HTTPException(status_code=403, detail="Access denied to project")

            # Get project details for organization context
            project = mongo_db.projects.find_one({"_id": project_obj_id})
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Set validated project context
            final_project_id = str(project["_id"])
            # final_org_id = str(project["organizationId"])  # Remove unused assignment

            logging.info(
                f"✅ Session auth project validated: user={auth.user_id}, project={final_project_id}"
            )
        else:
            # API key authentication - use key's scoped context
            if project_id and project_id != auth.project_id:
                logging.warning(
                    f"❌ ISOLATION VIOLATION: User {auth.user_id} attempted to access project {project_id} but API key is scoped to {auth.project_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="API key is not authorized for the requested project",
                )

            if organization_id and organization_id != auth.organization_id:
                logging.warning(
                    f"❌ ISOLATION VIOLATION: User {auth.user_id} attempted to access org {organization_id} but API key is scoped to {auth.organization_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="API key is not authorized for the requested organization",
                )

            final_project_id = auth.project_id

        # PHASE 7: Check read permission
        from .dependencies import has_permission

        if not has_permission(auth.user_id, final_project_id, "read"):
            logging.warning(
                f"❌ User {auth.user_id} does not have read permission for project {final_project_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Permission denied - read access required to retrieve memories",
            )

        # Project-level memory retrieval: All project members see the same memories
        logging.info(
            f"📖 Retrieving memories: project={final_project_id}, requester={auth.user_id}"
        )

        result = MEMORY_INSTANCE.get_all(
            user_id=final_project_id,  # Project as session identifier for shared memories
            limit=limit,
            offset=offset,
        )

        logging.info(
            f"✅ Retrieved {len(result.get('results', []))} memories from project {final_project_id}"
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_all_memories:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/memories/{memory_id}", summary="Get a memory (legacy endpoint)")
def get_memory(memory_id: str, auth: AuthContext = Depends(authenticate_api_key)):
    """Retrieve a specific memory by ID - Note: Individual memory retrieval uses legacy user_id only."""
    try:
        return MEMORY_INSTANCE.get(memory_id, user_id=auth.user_id)
    except Exception as e:
        logging.exception("Error in get_memory:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/memories/search", summary="Search memories with multi-tenant isolation")
@limiter.limit(config.rate_limit.MEMORY_SEARCH)
def search_memories(
    request: Request,
    search_req: SearchRequest,
    auth: AuthContext = Depends(authenticate_api_key),
    project_id: str | None = None,
):
    """Search for memories with multi-tenant isolation (supports both API key and Session auth)."""
    try:
        # For Session auth, extract and validate project context from request
        if auth.project_id is None:
            # Session authentication - get project context from query params or filters
            requested_project_id = (
                project_id or (search_req.filters or {}).get("project_id")
                if search_req.filters
                else None
            )

            if not requested_project_id:
                raise HTTPException(
                    status_code=400,
                    detail="project_id required for session authentication",
                )

            # Validate user has access to the project (owner or member)
            try:
                project_obj_id = ObjectId(requested_project_id)
                # user_obj_id = ObjectId(auth.user_id)  # Remove unused assignment
            except Exception as err:
                raise HTTPException(
                    status_code=400, detail="Invalid project_id or user_id format"
                ) from err

            # Use Phase 6 helper function to check access (not just ownership)
            from .dependencies import check_project_access

            if not check_project_access(auth.user_id, requested_project_id):
                logging.warning(
                    f"❌ Session user {auth.user_id} does not have access to project {requested_project_id}"
                )
                raise HTTPException(status_code=403, detail="Access denied to project")

            # Get project details for organization context
            project = mongo_db.projects.find_one({"_id": project_obj_id})
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Set validated project context
            final_project_id = str(project["_id"])
            # final_org_id = str(project["organizationId"])  # Remove unused assignment

            logging.info(
                f"✅ Session auth project validated for search: user={auth.user_id}, project={final_project_id}"
            )
        else:
            # API key authentication - use key's scoped context
            final_project_id = auth.project_id

        # PHASE 7: Check read permission
        from .dependencies import has_permission

        if not has_permission(auth.user_id, final_project_id, "read"):
            logging.warning(
                f"❌ User {auth.user_id} does not have read permission for project {final_project_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Permission denied - read access required to search memories",
            )

        # Project-level memory search: All project members search the same memory space
        logging.info(
            f"🔍 Searching memories: project={final_project_id}, requester={auth.user_id}, query='{search_req.query[:50]}...'"
        )

        # Build base parameters - exclude query, filters, and None values
        params = {
            k: v
            for k, v in search_req.model_dump().items()
            if v is not None and k not in ["query", "filters", "people_mentioned"]
        }

        # Project as session identifier for shared memory search
        params["user_id"] = final_project_id

        # Handle top-level people_mentioned field
        if search_req.people_mentioned:
            # Convert string to list for the search method
            params["people_mentioned"] = [search_req.people_mentioned]

        # Handle filters parameter by extracting supported filter options
        if search_req.filters:
            # Extract supported filter parameters from the filters dict
            supported_filters = [
                "limit",
                "tags",
                "people_mentioned",
                "topic_category",
                "temporal_filter",
                "threshold",
                "match_all_tags",
                "include_metadata",
                "sort_by",
            ]
            for filter_key in supported_filters:
                if filter_key in search_req.filters:
                    filter_value = search_req.filters[filter_key]

                    # Handle special cases for data type conversion
                    if (
                        filter_key == "tags"
                        and isinstance(filter_value, list)
                        or filter_key == "people_mentioned"
                        and isinstance(filter_value, list)
                    ):
                        # Keep as list - Memory.search() expects list
                        params[filter_key] = filter_value
                    elif filter_key == "people_mentioned" and isinstance(
                        filter_value, str
                    ):
                        # Convert string to list for people_mentioned
                        params[filter_key] = [filter_value]
                    else:
                        params[filter_key] = filter_value

        # Call search with multi-tenant context (enhanced selfmemory pattern)
        return MEMORY_INSTANCE.search(query=search_req.query, **params)
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete(
    "/api/memories/{memory_id}", summary="Delete a memory with permission checks"
)
def delete_memory(
    memory_id: str,
    auth: AuthContext = Depends(authenticate_api_key),
    project_id: str | None = None,
):
    """Delete a specific memory with permission checks."""
    # For Session auth, validate project context
    if auth.project_id is None:
        if not project_id:
            raise HTTPException(
                status_code=400, detail="project_id required for session authentication"
            )

        # Validate user has access to the project
        from .dependencies import check_project_access

        if not check_project_access(auth.user_id, project_id):
            logging.warning(
                f"❌ Session user {auth.user_id} does not have access to project {project_id}"
            )
            raise HTTPException(status_code=403, detail="Access denied to project")

        # Get project details
        project = mongo_db.projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        final_project_id = str(project["_id"])
    else:
        # API key authentication
        final_project_id = auth.project_id

    # Check delete permission
    from .dependencies import has_permission

    if not has_permission(auth.user_id, final_project_id, "write"):
        logging.warning(
            f"❌ User {auth.user_id} does not have write permission for project {final_project_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Permission denied - write access required to delete memories",
        )

    # Perform deletion
    MEMORY_INSTANCE.delete(memory_id)

    logging.info(f"✅ Memory {memory_id} deleted by user {auth.user_id}")
    return {"message": "Memory deleted successfully"}


@app.delete("/api/memories", summary="Delete all memories with multi-tenant isolation")
def delete_all_memories(auth: AuthContext = Depends(authenticate_api_key)):
    """Delete all memories with multi-tenant isolation (enhanced selfmemory style)."""
    try:
        result = MEMORY_INSTANCE.delete_all(
            user_id=auth.user_id,
            project_id=auth.project_id,  # Project-level isolation
            organization_id=auth.organization_id,  # Organization-level isolation
        )
        if result.get("success", False):
            # Only return safe fields - explicitly exclude any error field
            return {
                "message": result.get("message", "All memories deleted"),
                "deleted_count": result.get("deleted_count", 0),
            }
        # Log internal error detail if present, but do not expose to user
        internal_error_msg = result.get("error", "Unknown error")
        logging.error(f"delete_all_memories failed: {internal_error_msg}")
        # Always return a generic error to the client
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logging.exception("Error in delete_all_memories:")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Helper function for ensuring default organization and project
def ensure_default_org_and_project(user_id: str) -> tuple[str, str]:
    """
    Ensure user has default organization and project, creating them if needed.

    Note: user_id is Kratos identity_id (UUID string). We look up the MongoDB user
    document and use its _id (ObjectId) as ownerId for consistency with dashboard.
    """
    try:
        # Look up MongoDB user document using Kratos identity_id
        mongo_user_id = get_user_object_id_from_kratos_id(mongo_db, user_id)

        logging.info(
            f"Ensuring default org/project: kratos_id={user_id}, mongo_id={mongo_user_id}"
        )

        # Check if user already has a personal organization
        # CRITICAL: Check BOTH ownerId formats (frontend uses string, backend uses ObjectId)
        personal_org = mongo_db.organizations.find_one(
            {
                "$or": [
                    {"ownerId": mongo_user_id},  # Backend-created (ObjectId)
                    {"ownerId": user_id},  # Frontend-created (Kratos ID string)
                ],
                "type": "personal",
            }
        )

        if not personal_org:
            # Create personal organization using MongoDB ObjectId
            org_doc = {
                "name": "Personal Organization",
                "ownerId": mongo_user_id,  # MongoDB ObjectId for consistency
                "type": "personal",
                "createdAt": utc_now(),
                "updatedAt": utc_now(),
            }
            org_result = mongo_db.organizations.insert_one(org_doc)
            org_id = org_result.inserted_id

            # IMPORTANT: Add owner to organization_members collection
            org_member_doc = {
                "organizationId": org_id,
                "userId": mongo_user_id,  # MongoDB ObjectId for consistency
                "role": "owner",
                "joinedAt": utc_now(),
                "status": "active",
                "invitedBy": None,  # Self-created
            }
            mongo_db.organization_members.insert_one(org_member_doc)

            logging.info(
                f"Created personal organization for user {user_id} (mongo_id: {mongo_user_id}) and added owner to organization_members"
            )
        else:
            org_id = personal_org["_id"]

        # Check if default project exists
        default_project = mongo_db.projects.find_one(
            {
                "organizationId": org_id,
                "ownerId": mongo_user_id,  # MongoDB ObjectId for consistency
                "name": "Default Project",
            }
        )

        if not default_project:
            # Create default project using MongoDB ObjectId
            project_doc = {
                "name": "Default Project",
                "organizationId": org_id,
                "ownerId": mongo_user_id,  # MongoDB ObjectId for consistency
                "createdAt": utc_now(),
                "updatedAt": utc_now(),
            }
            project_result = mongo_db.projects.insert_one(project_doc)
            project_id = project_result.inserted_id
            logging.info(
                f"Created default project for user {user_id} (mongo_id: {mongo_user_id})"
            )
        else:
            project_id = default_project["_id"]

        return str(org_id), str(project_id)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error ensuring default org/project for user {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create default organization and project"
        ) from e


# Organization Management Endpoints
@app.get("/api/organizations", summary="List user's organizations")
def list_organizations(auth: AuthContext = Depends(authenticate_api_key)):
    """List all organizations the user has access to (owned + member)."""
    try:
        # Look up MongoDB user document for consistency
        mongo_user_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)

        # Get organizations where user is owner (check BOTH ownerId formats)
        owned_orgs = list(
            mongo_db.organizations.find(
                {
                    "$or": [
                        {"ownerId": mongo_user_id},  # Backend-created (ObjectId)
                        {
                            "ownerId": auth.user_id
                        },  # Frontend-created (Kratos ID string)
                    ]
                }
            )
        )

        # Get organizations where user is a member (using MongoDB ObjectId)
        member_records = list(
            mongo_db.organization_members.find({"userId": mongo_user_id})
        )
        member_org_ids = [record["organizationId"] for record in member_records]

        # Get organization details for member orgs
        member_orgs = []
        if member_org_ids:
            member_orgs = list(
                mongo_db.organizations.find({"_id": {"$in": member_org_ids}})
            )

        # Create role map for member organizations
        role_map = {
            str(record["organizationId"]): record["role"] for record in member_records
        }

        # Merge and deduplicate organizations
        all_orgs = {}

        # Add owned organizations with Owner role
        for org in owned_orgs:
            org_id = str(org["_id"])
            org["_id"] = org_id
            org["ownerId"] = str(org["ownerId"])
            org["role"] = "owner"
            all_orgs[org_id] = org

        # Add member organizations with their respective roles
        for org in member_orgs:
            org_id = str(org["_id"])
            if org_id not in all_orgs:  # Avoid duplicates
                org["_id"] = org_id
                org["ownerId"] = str(org["ownerId"])
                org["role"] = role_map.get(org_id, "member")
                all_orgs[org_id] = org

        # Convert to list
        orgs_list = list(all_orgs.values())

        logging.info(
            f"Retrieved {len(orgs_list)} organizations for user {auth.user_id}"
        )

        return {"organizations": orgs_list}

    except Exception as e:
        logging.exception("Error in list_organizations:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/organizations", summary="Create new organization")
@limiter.limit(config.rate_limit.ORGANIZATION_CREATE)
def create_organization(
    request: Request,
    org_create: OrganizationCreate,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """Create a new organization."""
    try:
        # Note: auth.user_id is Kratos identity_id (string), not ObjectId
        # Look up MongoDB user document for consistency
        mongo_user_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)

        # Check if organization name already exists for this user
        existing_org = mongo_db.organizations.find_one(
            {"name": org_create.name, "ownerId": mongo_user_id}
        )

        if existing_org:
            raise HTTPException(
                status_code=400, detail="Organization name already exists"
            )

        # Create organization using MongoDB ObjectId
        org_doc = {
            "name": org_create.name,
            "ownerId": mongo_user_id,  # MongoDB ObjectId for consistency
            "type": "custom",  # User-created organizations are "custom"
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
        }

        result = mongo_db.organizations.insert_one(org_doc)
        org_id = result.inserted_id

        # IMPORTANT: Add owner to organization_members collection
        org_member_doc = {
            "organizationId": org_id,
            "userId": mongo_user_id,  # MongoDB ObjectId for consistency
            "role": "owner",
            "joinedAt": utc_now(),
            "status": "active",
            "invitedBy": None,  # Self-created
        }
        mongo_db.organization_members.insert_one(org_member_doc)

        logging.info(
            f"Created organization '{org_create.name}' for user {auth.user_id} (mongo_id: {mongo_user_id}) and added owner to organization_members"
        )

        return {
            "organization_id": str(org_id),
            "name": org_create.name,
            "role": "owner",
            "message": "Organization created successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in create_organization:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/organizations/{org_id}", summary="Get organization details")
def get_organization(org_id: str, auth: AuthContext = Depends(authenticate_api_key)):
    """Get details of a specific organization."""
    try:
        # Note: auth.user_id is Kratos identity_id (string), not ObjectId
        user_id = auth.user_id
        org_obj_id = ObjectId(org_id)

        # Get organization and verify ownership
        organization = mongo_db.organizations.find_one(
            {"_id": org_obj_id, "ownerId": user_id}
        )

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Convert ObjectId to string
        organization["_id"] = str(organization["_id"])
        organization["ownerId"] = str(organization["ownerId"])

        return organization

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_organization:")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Project Management Endpoints
@app.get("/api/projects", summary="List user's projects")
def list_projects(auth: AuthContext = Depends(authenticate_api_key)):
    """List all projects the user has access to (owned + member)."""
    try:
        # Look up MongoDB user document for consistency
        mongo_user_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)

        # Get projects where user is owner (check BOTH ownerId formats)
        owned_projects = list(
            mongo_db.projects.find(
                {
                    "$or": [
                        {"ownerId": mongo_user_id},  # Backend-created (ObjectId)
                        {
                            "ownerId": auth.user_id
                        },  # Frontend-created (Kratos ID string)
                    ]
                }
            )
        )

        # Get projects where user is a member (using MongoDB ObjectId)
        member_records = list(mongo_db.project_members.find({"userId": mongo_user_id}))
        member_project_ids = [record["projectId"] for record in member_records]

        # Get project details for member projects
        member_projects = []
        if member_project_ids:
            member_projects = list(
                mongo_db.projects.find({"_id": {"$in": member_project_ids}})
            )

        # Create role map for member projects
        role_map = {
            str(record["projectId"]): record["role"] for record in member_records
        }

        logging.info(
            f"🔍 DEBUG list_projects - user={auth.user_id}, role_map={role_map}"
        )

        # Merge and deduplicate projects
        all_projects = {}

        # Add owned projects with Owner role
        for project in owned_projects:
            project_id = str(project["_id"])
            project["_id"] = project_id
            project["ownerId"] = str(project["ownerId"])
            project["organizationId"] = str(project["organizationId"])
            project["role"] = "owner"
            all_projects[project_id] = project
            logging.info(f"🔍 DEBUG added owned project: id={project_id}, role=owner")

        # Add member projects with their respective roles
        for project in member_projects:
            project_id = str(project["_id"])
            if project_id not in all_projects:  # Avoid duplicates
                project["_id"] = project_id
                project["ownerId"] = str(project["ownerId"])
                project["organizationId"] = str(project["organizationId"])
                assigned_role = role_map.get(project_id, "viewer")
                project["role"] = assigned_role
                all_projects[project_id] = project
                logging.info(
                    f"🔍 DEBUG added member project: id={project_id}, role={assigned_role}"
                )

        # Convert to list
        projects_list = list(all_projects.values())

        logging.info(
            f"Listed user projects: user={auth.user_id}, total_count={len(projects_list)}, "
            f"owned={len(owned_projects)}, member={len(member_projects)}"
        )

        return {"projects": projects_list}

    except Exception as e:
        logging.exception("Error in list_projects:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/projects", summary="Create new project")
@limiter.limit(config.rate_limit.PROJECT_CREATE)
def create_project(
    request: Request,
    project_create: ProjectCreate,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """Create a new project. Organization owners and admins can create projects."""
    try:
        # Look up MongoDB user document for consistency
        mongo_user_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)
        org_obj_id = ObjectId(project_create.organization_id)

        # Verify organization exists
        organization = mongo_db.organizations.find_one({"_id": org_obj_id})

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Check if user is organization owner (compare MongoDB ObjectIds)
        is_owner = organization["ownerId"] == mongo_user_id

        # Check if user is organization admin
        is_admin = False
        if not is_owner:
            admin_member = mongo_db.organization_members.find_one(
                {
                    "organizationId": org_obj_id,
                    "userId": mongo_user_id,  # MongoDB ObjectId for consistency
                    "role": "admin",
                    "status": "active",
                }
            )
            is_admin = admin_member is not None

        # User must be owner or admin to create projects
        if not is_owner and not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Only organization owners and admins can create projects",
            )

        # Check if project name already exists in this organization
        existing_project = mongo_db.projects.find_one(
            {"name": project_create.name, "organizationId": org_obj_id}
        )

        if existing_project:
            raise HTTPException(
                status_code=400,
                detail="Project name already exists in this organization",
            )

        # Create project using MongoDB ObjectId
        project_doc = {
            "name": project_create.name,
            "organizationId": org_obj_id,
            "ownerId": mongo_user_id,  # MongoDB ObjectId for consistency
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
        }

        result = mongo_db.projects.insert_one(project_doc)
        project_id = str(result.inserted_id)

        logging.info(
            f"Created project '{project_create.name}' for user {auth.user_id} (mongo_id: {mongo_user_id})"
        )

        return {
            "project_id": project_id,
            "name": project_create.name,
            "organization_id": project_create.organization_id,
            "role": "owner",
            "message": "Project created successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in create_project:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/projects/{project_id}", summary="Get project details")
def get_project(project_id: str, auth: AuthContext = Depends(authenticate_api_key)):
    """Get details of a specific project."""
    try:
        # Note: auth.user_id is Kratos identity_id (string), not ObjectId
        user_id = auth.user_id
        project_obj_id = ObjectId(project_id)

        # Get project and verify ownership
        project = mongo_db.projects.find_one(
            {"_id": project_obj_id, "ownerId": user_id}
        )

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Convert ObjectId to string
        project["_id"] = str(project["_id"])
        project["ownerId"] = str(project["ownerId"])
        project["organizationId"] = str(project["organizationId"])

        return project

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_project:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get(
    "/api/organizations/{org_id}/projects", summary="List projects in organization"
)
def list_organization_projects(
    org_id: str, auth: AuthContext = Depends(authenticate_api_key)
):
    """List all projects in a specific organization."""
    try:
        # Note: auth.user_id is Kratos identity_id (string), not ObjectId
        user_id = auth.user_id
        org_obj_id = ObjectId(org_id)

        # Verify user owns the organization
        organization = mongo_db.organizations.find_one(
            {"_id": org_obj_id, "ownerId": user_id}
        )

        if not organization:
            raise HTTPException(
                status_code=404, detail="Organization not found or access denied"
            )

        # Get projects in this organization
        projects = list(
            mongo_db.projects.find({"organizationId": org_obj_id, "ownerId": user_id})
        )

        # Convert ObjectId to string for JSON serialization
        for project in projects:
            project["_id"] = str(project["_id"])
            project["ownerId"] = str(project["ownerId"])
            project["organizationId"] = str(project["organizationId"])

        return {"projects": projects}

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in list_organization_projects:")
        raise HTTPException(status_code=500, detail=str(e)) from e


# User Initialization Endpoint
@app.post("/api/initialize", summary="Initialize new user with Kratos identity sync")
def initialize_user(auth: AuthContext = Depends(authenticate_api_key)):
    """
    Initialize a new user with Kratos identity sync.

    This endpoint:
    1. Syncs Kratos identity to MongoDB (auth.user_id is Kratos identity_id)
    2. Creates default personal organization and project

    Note: auth.user_id is now Kratos identity_id, not MongoDB ObjectId
    """
    try:
        from .auth import get_identity_by_id

        # Get Kratos identity details (auth.user_id is Kratos identity_id)
        kratos_identity_id = auth.user_id

        # Fetch full identity from Kratos
        try:
            kratos_session = get_identity_by_id(kratos_identity_id)
            email = kratos_session.email
            organization_id_trait = kratos_session.organization_id
            project_ids_trait = kratos_session.project_ids
            name = kratos_session.name
        except Exception as e:
            logging.error(f"Failed to fetch Kratos identity: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to sync user identity from Kratos"
            ) from e

        # Check if user already exists in MongoDB
        # User may exist with either:
        # 1. _id = Kratos identity_id (new format)
        # 2. kratosId = Kratos identity_id (from ensureUserExists)
        existing_user = mongo_db.users.find_one(
            {"$or": [{"_id": kratos_identity_id}, {"kratosId": kratos_identity_id}]}
        )

        if existing_user:
            logging.info(f"User already exists in MongoDB: {kratos_identity_id}")
            # Just update traits, don't create duplicate
            update_filter = {"_id": existing_user["_id"]}
            mongo_db.users.update_one(
                update_filter,
                {
                    "$set": {
                        "email": email,
                        "name": name,
                        "organization_id": organization_id_trait,
                        "project_ids": project_ids_trait,
                        "updatedAt": utc_now(),
                    }
                },
            )
            logging.info(f"✅ Updated existing user record: {existing_user['_id']}")
        else:
            # This shouldn't happen as ensureUserExists should have created user
            # But handle it just in case
            logging.warning(
                f"No existing user found for {kratos_identity_id}, this is unexpected"
            )

        # Ensure default organization and project exist
        # Note: user_id is Kratos identity_id (string), not ObjectId
        org_id, project_id = ensure_default_org_and_project(kratos_identity_id)

        logging.info(
            f"✅ Initialized user {kratos_identity_id} ({email}) with default org/project"
        )

        return {
            "organization_id": org_id,
            "project_id": project_id,
            "message": "User initialized successfully",
            "kratos_identity_id": kratos_identity_id,
            "email": email,
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in initialize_user:")
        raise HTTPException(status_code=500, detail=str(e)) from e


# MCP (Model Context Protocol) Endpoints
@app.get(
    "/.well-known/oauth-protected-resource",
    summary="Protected Resource Metadata for MCP",
)
def mcp_protected_resource_metadata():
    """
    RFC 9728 Protected Resource Metadata endpoint for MCP clients.

    This endpoint tells MCP clients:
    - What authorization servers to use (Ory Hydra)
    - What scopes are supported
    - Where to find documentation
    """
    if not config.mcp.ENABLED:
        raise HTTPException(status_code=404, detail="MCP is not enabled")

    logging.info("📋 [MCP] Serving Protected Resource Metadata")
    return get_protected_resource_metadata()


@app.get("/health", summary="Comprehensive health check")
def health_check():
    """
    Comprehensive health check endpoint.

    Checks all system dependencies:
    - Database connectivity
    - Memory usage
    - Disk usage
    - SMTP connectivity (if configured)

    Returns:
        - 200: All systems healthy or degraded
        - 503: One or more critical systems unhealthy
    """
    try:
        health_status = perform_health_checks()

        # Return 503 if unhealthy
        if health_status["status"] == "unhealthy":
            return JSONResponse(status_code=503, content=health_status)

        return health_status

    except Exception:
        logging.exception("Health check error:")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": utc_now().isoformat(),
                "error": "Health check failed",
            },
        )


@app.get("/health/live", summary="Liveness probe")
def liveness_probe():
    """
    Kubernetes-style liveness probe.

    Returns 200 if the application is running.
    This endpoint should be used to determine if the container should be restarted.

    Returns:
        - 200: Application is alive
    """
    if is_alive():
        return {"status": "alive", "timestamp": utc_now().isoformat()}

    return JSONResponse(
        status_code=503, content={"status": "dead", "timestamp": utc_now().isoformat()}
    )


@app.get("/health/ready", summary="Readiness probe")
def readiness_probe():
    """
    Kubernetes-style readiness probe.

    Returns 200 if the application is ready to serve traffic.
    This endpoint checks critical dependencies (database) to determine readiness.

    Returns:
        - 200: Application is ready
        - 503: Application is not ready
    """
    try:
        if is_ready():
            return {"status": "ready", "timestamp": utc_now().isoformat()}

        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "timestamp": utc_now().isoformat()},
        )

    except Exception:
        logging.exception("Readiness check error:")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "timestamp": utc_now().isoformat(),
                "error": "Readiness check failed",
            },
        )


# @app.post("/reset", summary="Reset all memories")
# def reset_memory():
#     """Completely reset stored memories (selfmemory style)."""
#     try:
#         MEMORY_INSTANCE.reset()
#         return {"message": "All memories reset"}
#     except Exception as e:
#         logging.exception("Error in reset_memory:")
#         raise HTTPException(status_code=500, detail=str(e)) from e


# @app.get("/", summary="Redirect to docs")
# def home():
#     """Redirect to the OpenAPI documentation."""
#     return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn

    logging.info("Starting SelfMemory Backend Server")
    logging.info(f"API available at: http://{config.server.HOST}:{config.server.PORT}/")

    uvicorn.run(
        app,
        host=config.server.HOST,
        port=config.server.PORT,
        log_level=config.logging.LEVEL.lower(),
    )
