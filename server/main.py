import logging
from typing import Any

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

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
from .utils.permission_helpers import get_user_object_id_from_kratos_id
from .utils.rate_limiter import limiter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()

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

# Validate Ollama connectivity (embedding provider must be reachable)
if config.embedding.PROVIDER == "ollama":
    try:
        from ollama import Client as OllamaClient

        ollama_client = OllamaClient(host=config.embedding.OLLAMA_BASE_URL)
        ollama_client.list()
        logging.info(f"✅ Ollama connected at {config.embedding.OLLAMA_BASE_URL}")
    except Exception as e:
        logging.error("=" * 50)
        logging.error("OLLAMA CONNECTION FAILED")
        logging.error("=" * 50)
        logging.error(f"  URL: {config.embedding.OLLAMA_BASE_URL}")
        logging.error(f"  Error: {e}")
        logging.error("  Please ensure Ollama is running: ollama serve")
        logging.error("=" * 50)
        raise RuntimeError(
            "Ollama is not reachable. Start Ollama before the backend."
        ) from e

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

# Log security status for API documentation
if config.app.ENVIRONMENT == "production":
    logging.info("🔒 SECURITY: API documentation endpoints disabled in production")
else:
    logging.info(
        "📚 DEV MODE: API documentation available at /docs, /redoc, /openapi.json"
    )

# FastAPI app with conditional documentation based on environment
app = FastAPI(
    title="SelfMemory APIs",
    # Security: Disable API documentation in production to prevent information disclosure
    docs_url="/docs" if config.app.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if config.app.ENVIRONMENT != "production" else None,
    openapi_url="/openapi.json" if config.app.ENVIRONMENT != "production" else None,
)

# Initialize OpenTelemetry (production only)
initialize_telemetry(app)

# Add rate limiting to app state
app.state.limiter = limiter


# CORS middleware
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


# Include routers
app.include_router(api_keys_router)
app.include_router(chat_router)
app.include_router(hydra_proxy_router)
app.include_router(invitations_router)
app.include_router(notifications_router)
app.include_router(organizations_router)
app.include_router(projects_router)
app.include_router(users_router)


class Message(BaseModel):
    role: str = Field(..., description="Message role (e.g., 'user', 'assistant').")
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


@app.get("/api/memories", summary="List memories with multi-tenant isolation")
def list_memories(
    request: Request,
    auth: AuthContext = Depends(authenticate_api_key),
    user_id: str | None = None,
    project_id: str | None = None,
    organization_id: str | None = None,
    limit: int = 10,
    offset: int = 0,
):
    """List memories with multi-tenant isolation (supports both API key and Session auth)."""
    try:
        # For Session auth, extract and validate project context
        if auth.project_id is None:
            requested_project_id = project_id
            if not requested_project_id:
                raise HTTPException(
                    status_code=400,
                    detail="project_id required for session authentication",
                )

            try:
                project_obj_id = ObjectId(requested_project_id)
            except Exception as err:
                raise HTTPException(
                    status_code=400, detail="Invalid project_id format"
                ) from err

            from .dependencies import check_project_access

            if not check_project_access(auth.user_id, requested_project_id):
                raise HTTPException(status_code=403, detail="Access denied to project")

            project = mongo_db.projects.find_one({"_id": project_obj_id})
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            final_project_id = str(project["_id"])
        else:
            final_project_id = auth.project_id

        from .dependencies import has_permission

        if not has_permission(auth.user_id, final_project_id, "read"):
            raise HTTPException(
                status_code=403,
                detail="Permission denied - read access required",
            )

        logging.info(
            f"📋 Listing memories: project={final_project_id}, requester={auth.user_id}, limit={limit}, offset={offset}"
        )

        response = MEMORY_INSTANCE.get_all(
            user_id=final_project_id,
            limit=limit,
            offset=offset,
        )

        return JSONResponse(content=response)
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in list_memories:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/memories/stats", summary="Get memory statistics for a project")
def get_memory_stats(
    request: Request,
    auth: AuthContext = Depends(authenticate_api_key),
    project_id: str | None = None,
):
    """Get memory count stats without fetching full content."""
    try:
        if auth.project_id is None:
            requested_project_id = project_id
            if not requested_project_id:
                raise HTTPException(
                    status_code=400,
                    detail="project_id required for session authentication",
                )

            try:
                project_obj_id = ObjectId(requested_project_id)
            except Exception as err:
                raise HTTPException(
                    status_code=400, detail="Invalid project_id format"
                ) from err

            from .dependencies import check_project_access

            if not check_project_access(auth.user_id, requested_project_id):
                raise HTTPException(status_code=403, detail="Access denied to project")

            project = mongo_db.projects.find_one({"_id": project_obj_id})
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            final_project_id = str(project["_id"])
        else:
            final_project_id = auth.project_id

        from .dependencies import has_permission

        if not has_permission(auth.user_id, final_project_id, "read"):
            raise HTTPException(
                status_code=403,
                detail="Permission denied - read access required",
            )

        from datetime import datetime, timedelta, timezone

        from qdrant_client.models import FieldCondition, Filter, MatchValue

        qdrant_client = MEMORY_INSTANCE.vector_store.client
        collection_name = MEMORY_INSTANCE.vector_store.collection_name

        project_filter = Filter(
            must=[
                FieldCondition(
                    key="user_id", match=MatchValue(value=final_project_id)
                )
            ]
        )
        total = qdrant_client.count(
            collection_name=collection_name,
            count_filter=project_filter,
            exact=True,
        ).count

        # Scroll with minimal payload to compute this_week and tags in Python
        # (Qdrant Range filter only works with numeric fields, not date strings)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        this_week = 0
        tag_set = set()
        scroll_result = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=project_filter,
            limit=500,
            with_payload=["tags", "created_at"],
            with_vectors=False,
        )
        for point in scroll_result[0]:
            created_at_str = point.payload.get("created_at", "")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    if created_at >= seven_days_ago:
                        this_week += 1
                except (ValueError, TypeError):
                    pass

            tags_str = point.payload.get("tags", "")
            if tags_str:
                for tag in tags_str.split(","):
                    tag = tag.strip()
                    if tag:
                        tag_set.add(tag)

        return JSONResponse(
            content={
                "total": total,
                "this_week": this_week,
                "tag_count": len(tag_set),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_memory_stats:")
        raise HTTPException(status_code=500, detail=str(e)) from e


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

    logging.info("[MCP] Serving Protected Resource Metadata")
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
    """Kubernetes-style liveness probe. Returns 200 if the application is running."""
    if is_alive():
        return {"status": "alive", "timestamp": utc_now().isoformat()}

    return JSONResponse(
        status_code=503, content={"status": "dead", "timestamp": utc_now().isoformat()}
    )


@app.get("/health/ready", summary="Readiness probe")
def readiness_probe():
    """Kubernetes-style readiness probe. Returns 200 if the application is ready to serve traffic."""
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
