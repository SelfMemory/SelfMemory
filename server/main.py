import hashlib
import logging
import os
from datetime import datetime
from typing import Any, NamedTuple

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from pymongo import MongoClient

from selfmemory import SelfMemory


# Authentication context for multi-tenant support
class AuthContext(NamedTuple):
    user_id: str
    project_id: str | None = None
    organization_id: str | None = None


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables
load_dotenv()

# MongoDB connection (same as dashboard)
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/selfmemory")
mongo_client = MongoClient(MONGODB_URI)
mongo_db = mongo_client.get_database()

# Default configuration (selfmemory style - simple and clean)
DEFAULT_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "selfmemory_memories",
            "host": "localhost",
            "port": 6333,  # Default Qdrant Docker port
        },
    },
    "embedding": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434",
        },
    },
}

# Global Memory instance (selfmemory style - single instance for all users)
MEMORY_INSTANCE = SelfMemory(config=DEFAULT_CONFIG)

# FastAPI app
app = FastAPI(
    title="SelfMemory REST APIs",
    description="A REST API for managing and searching memories - following selfmemory patterns.",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    filters: dict[str, Any] | None = None


# Multi-tenant Pydantic models
class OrganizationCreate(BaseModel):
    name: str = Field(
        ..., description="Organization name.", min_length=1, max_length=100
    )


class ProjectCreate(BaseModel):
    name: str = Field(..., description="Project name.", min_length=1, max_length=100)
    organization_id: str = Field(
        ..., description="Organization ID this project belongs to."
    )


class ApiKeyCreate(BaseModel):
    name: str = Field(..., description="API key name.", min_length=1, max_length=100)
    project_id: str = Field(..., description="Project ID this API key is scoped to.")
    permissions: list[str] = Field(
        default=["read", "write"], description="API key permissions."
    )
    expires_in_days: int | None = Field(
        default=None, description="API key expiration in days (optional)."
    )


# Database-based authentication with multi-tenant support
def authenticate_api_key(authorization: str = Header(None)) -> AuthContext:
    """Database-based authentication - supports both API key (Bearer) and Session auth.

    - Bearer token: For SDK/API users with project-scoped API keys
    - Session auth: For dashboard users authenticated via NextAuth
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Handle Session authentication (dashboard users)
    if authorization.startswith("Session "):
        user_id = authorization.replace("Session ", "")

        try:
            user_obj_id = ObjectId(user_id)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid user ID format")

        # Validate user exists and is active
        user = mongo_db.users.find_one({"_id": user_obj_id})

        if not user:
            logging.warning(f"❌ Session auth: User not found: {user_id}")
            raise HTTPException(
                status_code=401, detail="Invalid session - user not found"
            )

        if not user.get("isActive", True):
            logging.warning(
                f"❌ Session auth: Inactive user attempted access: {user_id}"
            )
            raise HTTPException(status_code=401, detail="User account inactive")

        logging.info(
            f"✅ Session auth validated for user: {user.get('email', user_id)}"
        )

        # For session auth, project context comes from request parameters
        # Return AuthContext without project context - will be extracted by endpoint
        return AuthContext(
            user_id=user_id,
            project_id=None,  # Will be set by endpoint from request params
            organization_id=None,  # Will be set by endpoint from request params
        )

    # Handle API Key authentication (SDK users)
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must start with 'Bearer ' or 'Session '",
        )

    api_key = authorization.replace("Bearer ", "")

    # Accept only format: sk_im_
    if not api_key.startswith("sk_im_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    try:
        # Hash the provided API key to match stored hash
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Look for API key using keyHash (unified format)
        stored_key = mongo_db.api_keys.find_one({"keyHash": key_hash, "isActive": True})

        # Fallback: Look for old plain text keys for backward compatibility
        if not stored_key:
            stored_key = mongo_db.api_keys.find_one(
                {"api_key": api_key, "isActive": True}
            )

            # If found old format, migrate it to new format
            if stored_key:
                mongo_db.api_keys.update_one(
                    {"_id": stored_key["_id"]},
                    {"$set": {"keyHash": key_hash}, "$unset": {"api_key": ""}},
                )
                stored_key["keyHash"] = key_hash  # Update local copy

        if not stored_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Check if key is expired
        if stored_key.get("expiresAt") and stored_key["expiresAt"] < datetime.now():
            logging.warning(
                f"❌ Expired API key attempted: {stored_key.get('keyPrefix', 'unknown')}"
            )
            raise HTTPException(status_code=401, detail="API key expired")

        # Get user to verify it's active
        user = mongo_db.users.find_one({"_id": stored_key["userId"]})

        if not user or not user.get("isActive", True):
            logging.warning(
                f"❌ API key belongs to inactive user: {stored_key['userId']}"
            )
            raise HTTPException(status_code=401, detail="User account inactive")

        # Extract multi-tenant context from API key
        user_id = str(stored_key["userId"])
        project_id = None
        organization_id = None

        # Get project context if API key has projectId
        if stored_key.get("projectId"):
            project = mongo_db.projects.find_one({"_id": stored_key["projectId"]})
            if project:
                project_id = str(project["_id"])
                organization_id = str(project["organizationId"])

                # Verify user has access to this project
                if project["ownerId"] != stored_key["userId"]:
                    logging.warning(
                        f"❌ User {user_id} attempted to access project {project_id} they don't own"
                    )
                    raise HTTPException(
                        status_code=403, detail="Access denied to project"
                    )

                logging.info(
                    f"✅ Multi-tenant context: user={user.get('email', user_id)}, project={project_id}, org={organization_id}"
                )
            else:
                logging.warning(
                    f"❌ API key references non-existent project: {stored_key['projectId']}"
                )
                raise HTTPException(status_code=404, detail="Project not found")
        else:
            # Backward compatibility: API key without project context
            logging.info(
                f"✅ Legacy context: user={user.get('email', user_id)} (no project context)"
            )

        # Update last used timestamp
        mongo_db.api_keys.update_one(
            {"_id": stored_key["_id"]}, {"$set": {"lastUsed": datetime.now()}}
        )

        return AuthContext(
            user_id=user_id, project_id=project_id, organization_id=organization_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"API key authentication error: {e}")
        raise HTTPException(status_code=500, detail="Authentication error") from e


# Legacy authentication for backward compatibility
def authenticate_api_key_legacy(authorization: str = Header(None)) -> str:
    """Legacy authentication that returns only user_id for backward compatibility."""
    auth_context = authenticate_api_key(authorization)
    return auth_context.user_id


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
def add_memory(
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
            requested_org_id = organization_id or (memory_create.metadata or {}).get(
                "organization_id"
            )

            if not requested_project_id:
                raise HTTPException(
                    status_code=400,
                    detail="project_id required for session authentication",
                )

            # Validate user owns the project
            try:
                project_obj_id = ObjectId(requested_project_id)
                user_obj_id = ObjectId(auth.user_id)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid project_id or user_id format"
                )

            project = mongo_db.projects.find_one(
                {"_id": project_obj_id, "ownerId": user_obj_id}
            )

            if not project:
                logging.warning(
                    f"❌ Session user {auth.user_id} does not own project {requested_project_id}"
                )
                raise HTTPException(status_code=403, detail="Access denied to project")

            # Set validated project context
            final_project_id = str(project["_id"])
            final_org_id = str(project["organizationId"])

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
            final_org_id = auth.organization_id

        # Extract memory content from messages (selfmemory style)
        memory_content = ""
        if memory_create.messages:
            memory_content = " ".join([msg.content for msg in memory_create.messages])

        # Extract metadata fields for selfmemory-core compatibility
        metadata = memory_create.metadata or {}
        tags = metadata.get("tags", "")
        people_mentioned = metadata.get("people_mentioned", "")
        topic_category = metadata.get("topic_category", "")

        # Create memory with validated project context
        response = MEMORY_INSTANCE.add(
            memory_content=memory_content,
            user_id=auth.user_id or memory_create.user_id,
            tags=tags,
            people_mentioned=people_mentioned,
            topic_category=topic_category,
            project_id=final_project_id,
            organization_id=final_org_id,
        )

        logging.info(
            f"✅ Memory created: user={auth.user_id}, project={final_project_id}, org={final_org_id}"
        )
        return JSONResponse(content=response)
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/memories", summary="Get memories with multi-tenant isolation")
def get_all_memories(
    project_id: str | None = None,
    organization_id: str | None = None,
    limit: int = 100,
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

            # Validate user owns the project
            try:
                project_obj_id = ObjectId(project_id)
                user_obj_id = ObjectId(auth.user_id)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid project_id or user_id format"
                )

            project = mongo_db.projects.find_one(
                {"_id": project_obj_id, "ownerId": user_obj_id}
            )

            if not project:
                logging.warning(
                    f"❌ Session user {auth.user_id} does not own project {project_id}"
                )
                raise HTTPException(status_code=403, detail="Access denied to project")

            # Set validated project context
            final_project_id = str(project["_id"])
            final_org_id = str(project["organizationId"])

            logging.info(
                f"✅ Session auth project validated: user={auth.user_id}, project={final_project_id}"
            )
        else:
            # API key authentication - use key's scoped context
            # Reject attempts to specify different project/org
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
            final_org_id = auth.organization_id

        # Retrieve memories with validated project context
        result = MEMORY_INSTANCE.get_all(
            user_id=auth.user_id,
            project_id=final_project_id,
            organization_id=final_org_id,
            limit=limit,
            offset=offset,
        )

        logging.info(
            f"✅ Retrieved memories: user={auth.user_id}, project={final_project_id}, org={final_org_id}"
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
def search_memories(
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

            # Validate user owns the project
            try:
                project_obj_id = ObjectId(requested_project_id)
                user_obj_id = ObjectId(auth.user_id)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid project_id or user_id format"
                )

            project = mongo_db.projects.find_one(
                {"_id": project_obj_id, "ownerId": user_obj_id}
            )

            if not project:
                logging.warning(
                    f"❌ Session user {auth.user_id} does not own project {requested_project_id}"
                )
                raise HTTPException(status_code=403, detail="Access denied to project")

            # Set validated project context
            final_project_id = str(project["_id"])
            final_org_id = str(project["organizationId"])

            logging.info(
                f"✅ Session auth project validated for search: user={auth.user_id}, project={final_project_id}"
            )
        else:
            # API key authentication - use key's scoped context
            final_project_id = auth.project_id
            final_org_id = auth.organization_id

        logging.info(
            f"🔍 Search initiated for user={auth.user_id}, project={final_project_id}, org={final_org_id}"
        )

        # Build base parameters - exclude query, filters, and None values
        params = {
            k: v
            for k, v in search_req.model_dump().items()
            if v is not None and k not in ["query", "filters"]
        }

        # Use validated multi-tenant context
        params["user_id"] = auth.user_id
        params["project_id"] = final_project_id  # Project-level isolation
        params["organization_id"] = final_org_id  # Organization-level isolation

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
                    else:
                        params[filter_key] = filter_value

        # Call search with multi-tenant context (enhanced selfmemory pattern)
        return MEMORY_INSTANCE.search(query=search_req.query, **params)
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/memories/{memory_id}", summary="Delete a memory (legacy endpoint)")
def delete_memory(memory_id: str, auth: AuthContext = Depends(authenticate_api_key)):
    """Delete a specific memory - Note: Individual memory deletion uses legacy approach."""
    try:
        MEMORY_INSTANCE.delete(memory_id)
        return {"message": "Memory deleted successfully"}
    except Exception as e:
        logging.exception("Error in delete_memory:")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
            return {
                "message": result.get("message", "All memories deleted"),
                "deleted_count": result.get("deleted_count", 0),
            }
        else:
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
    """Ensure user has default organization and project, creating them if needed."""
    try:
        user_obj_id = ObjectId(user_id)

        # Check if user already has a personal organization
        personal_org = mongo_db.organizations.find_one(
            {"ownerId": user_obj_id, "type": "personal"}
        )

        if not personal_org:
            # Create personal organization
            org_doc = {
                "name": "Personal Organization",
                "ownerId": user_obj_id,
                "type": "personal",
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
            }
            org_result = mongo_db.organizations.insert_one(org_doc)
            org_id = org_result.inserted_id
            logging.info(f"Created personal organization for user {user_id}")
        else:
            org_id = personal_org["_id"]

        # Check if default project exists
        default_project = mongo_db.projects.find_one(
            {
                "organizationId": org_id,
                "ownerId": user_obj_id,
                "name": "Default Project",
            }
        )

        if not default_project:
            # Create default project
            project_doc = {
                "name": "Default Project",
                "organizationId": org_id,
                "ownerId": user_obj_id,
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
            }
            project_result = mongo_db.projects.insert_one(project_doc)
            project_id = project_result.inserted_id
            logging.info(f"Created default project for user {user_id}")
        else:
            project_id = default_project["_id"]

        return str(org_id), str(project_id)

    except Exception as e:
        logging.error(f"Error ensuring default org/project for user {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create default organization and project"
        )


# Organization Management Endpoints
@app.get("/api/organizations", summary="List user's organizations")
def list_organizations(auth: AuthContext = Depends(authenticate_api_key)):
    """List all organizations the user has access to."""
    try:
        user_obj_id = ObjectId(auth.user_id)

        # Get user's organizations (they own)
        organizations = list(mongo_db.organizations.find({"ownerId": user_obj_id}))

        # Convert ObjectId to string for JSON serialization
        for org in organizations:
            org["_id"] = str(org["_id"])
            org["ownerId"] = str(org["ownerId"])

        return {"organizations": organizations}

    except Exception as e:
        logging.exception("Error in list_organizations:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/organizations", summary="Create new organization")
def create_organization(
    org_create: OrganizationCreate, auth: AuthContext = Depends(authenticate_api_key)
):
    """Create a new organization."""
    try:
        user_obj_id = ObjectId(auth.user_id)

        # Check if organization name already exists for this user
        existing_org = mongo_db.organizations.find_one(
            {"name": org_create.name, "ownerId": user_obj_id}
        )

        if existing_org:
            raise HTTPException(
                status_code=400, detail="Organization name already exists"
            )

        # Create organization
        org_doc = {
            "name": org_create.name,
            "ownerId": user_obj_id,
            "type": "custom",  # User-created organizations are "custom"
            "createdAt": datetime.now(),
            "updatedAt": datetime.now(),
        }

        result = mongo_db.organizations.insert_one(org_doc)
        org_id = str(result.inserted_id)

        logging.info(
            f"Created organization '{org_create.name}' for user {auth.user_id}"
        )

        return {
            "organization_id": org_id,
            "name": org_create.name,
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
        user_obj_id = ObjectId(auth.user_id)
        org_obj_id = ObjectId(org_id)

        # Get organization and verify ownership
        organization = mongo_db.organizations.find_one(
            {"_id": org_obj_id, "ownerId": user_obj_id}
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
    """List all projects the user has access to."""
    try:
        user_obj_id = ObjectId(auth.user_id)

        # Get user's projects (they own)
        projects = list(mongo_db.projects.find({"ownerId": user_obj_id}))

        # Convert ObjectId to string for JSON serialization
        for project in projects:
            project["_id"] = str(project["_id"])
            project["ownerId"] = str(project["ownerId"])
            project["organizationId"] = str(project["organizationId"])

        return {"projects": projects}

    except Exception as e:
        logging.exception("Error in list_projects:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/projects", summary="Create new project")
def create_project(
    project_create: ProjectCreate, auth: AuthContext = Depends(authenticate_api_key)
):
    """Create a new project."""
    try:
        user_obj_id = ObjectId(auth.user_id)
        org_obj_id = ObjectId(project_create.organization_id)

        # Verify user owns the organization
        organization = mongo_db.organizations.find_one(
            {"_id": org_obj_id, "ownerId": user_obj_id}
        )

        if not organization:
            raise HTTPException(
                status_code=404, detail="Organization not found or access denied"
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

        # Create project
        project_doc = {
            "name": project_create.name,
            "organizationId": org_obj_id,
            "ownerId": user_obj_id,
            "createdAt": datetime.now(),
            "updatedAt": datetime.now(),
        }

        result = mongo_db.projects.insert_one(project_doc)
        project_id = str(result.inserted_id)

        logging.info(f"Created project '{project_create.name}' for user {auth.user_id}")

        return {
            "project_id": project_id,
            "name": project_create.name,
            "organization_id": project_create.organization_id,
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
        user_obj_id = ObjectId(auth.user_id)
        project_obj_id = ObjectId(project_id)

        # Get project and verify ownership
        project = mongo_db.projects.find_one(
            {"_id": project_obj_id, "ownerId": user_obj_id}
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
        user_obj_id = ObjectId(auth.user_id)
        org_obj_id = ObjectId(org_id)

        # Verify user owns the organization
        organization = mongo_db.organizations.find_one(
            {"_id": org_obj_id, "ownerId": user_obj_id}
        )

        if not organization:
            raise HTTPException(
                status_code=404, detail="Organization not found or access denied"
            )

        # Get projects in this organization
        projects = list(
            mongo_db.projects.find(
                {"organizationId": org_obj_id, "ownerId": user_obj_id}
            )
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


# API Key Management Endpoints
@app.get("/api/projects/{project_id}/api-keys", summary="List API keys for project")
def list_project_api_keys(
    project_id: str, auth: AuthContext = Depends(authenticate_api_key)
):
    """List all API keys for a specific project."""
    try:
        user_obj_id = ObjectId(auth.user_id)
        project_obj_id = ObjectId(project_id)

        # Verify user owns the project
        project = mongo_db.projects.find_one(
            {"_id": project_obj_id, "ownerId": user_obj_id}
        )

        if not project:
            raise HTTPException(
                status_code=404, detail="Project not found or access denied"
            )

        # Get API keys for this project
        api_keys = list(
            mongo_db.api_keys.find({"projectId": project_obj_id, "userId": user_obj_id})
        )

        # Convert ObjectId to string and remove sensitive data
        for key in api_keys:
            key["_id"] = str(key["_id"])
            key["userId"] = str(key["userId"])
            key["projectId"] = str(key["projectId"])
            # Remove sensitive fields
            key.pop("keyHash", None)
            key.pop("api_key", None)  # Legacy field

        return {"api_keys": api_keys}

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in list_project_api_keys:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/projects/{project_id}/api-keys", summary="Create API key for project")
def create_project_api_key(
    project_id: str,
    key_create: ApiKeyCreate,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """Create a new API key for a specific project."""
    try:
        import secrets
        import string

        user_obj_id = ObjectId(auth.user_id)
        project_obj_id = ObjectId(project_id)

        # Verify project_id matches the request body
        if key_create.project_id != project_id:
            raise HTTPException(status_code=400, detail="Project ID mismatch")

        # Verify user owns the project
        project = mongo_db.projects.find_one(
            {"_id": project_obj_id, "ownerId": user_obj_id}
        )

        if not project:
            raise HTTPException(
                status_code=404, detail="Project not found or access denied"
            )

        # Generate API key
        alphabet = string.ascii_letters + string.digits
        api_key = "sk_im_" + "".join(secrets.choice(alphabet) for _ in range(40))
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_prefix = api_key[:10] + "..."

        # Calculate expiration if specified
        expires_at = None
        if key_create.expires_in_days:
            from datetime import timedelta

            expires_at = datetime.now() + timedelta(days=key_create.expires_in_days)

        # Create API key document
        key_doc = {
            "name": key_create.name,
            "userId": user_obj_id,
            "projectId": project_obj_id,
            "keyHash": key_hash,
            "keyPrefix": key_prefix,
            "permissions": key_create.permissions,
            "isActive": True,
            "autoGenerated": False,
            "expiresAt": expires_at,
            "createdAt": datetime.now(),
            "lastUsed": None,
        }

        result = mongo_db.api_keys.insert_one(key_doc)
        key_id = str(result.inserted_id)

        logging.info(f"Created API key '{key_create.name}' for project {project_id}")

        return {
            "api_key_id": key_id,
            "name": key_create.name,
            "api_key": api_key,  # Only returned on creation
            "key_prefix": key_prefix,
            "permissions": key_create.permissions,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "message": "API key created successfully. Store this key securely - it won't be shown again.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in create_project_api_key:")
        raise HTTPException(status_code=500, detail=str(e)) from e


# User Initialization Endpoint
@app.post("/api/initialize", summary="Initialize new user with default org and project")
def initialize_user(auth: AuthContext = Depends(authenticate_api_key)):
    """Initialize a new user with default organization, project, and API key."""
    try:
        # Ensure default organization and project exist
        org_id, project_id = ensure_default_org_and_project(auth.user_id)

        # Check if user already has an API key for the default project
        existing_key = mongo_db.api_keys.find_one(
            {
                "userId": ObjectId(auth.user_id),
                "projectId": ObjectId(project_id),
                "autoGenerated": True,
            }
        )

        if existing_key:
            # User already initialized
            return {
                "organization_id": org_id,
                "project_id": project_id,
                "api_key_id": str(existing_key["_id"]),
                "key_prefix": existing_key.get("keyPrefix", "sk_im_..."),
                "message": "User already initialized",
            }

        # Create default API key
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits
        api_key = "sk_im_" + "".join(secrets.choice(alphabet) for _ in range(40))
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_prefix = api_key[:10] + "..."

        key_doc = {
            "name": "Default API Key",
            "userId": ObjectId(auth.user_id),
            "projectId": ObjectId(project_id),
            "keyHash": key_hash,
            "keyPrefix": key_prefix,
            "permissions": ["read", "write"],
            "isActive": True,
            "autoGenerated": True,
            "expiresAt": None,
            "createdAt": datetime.now(),
            "lastUsed": None,
        }

        result = mongo_db.api_keys.insert_one(key_doc)
        key_id = str(result.inserted_id)

        logging.info(f"Initialized user {auth.user_id} with default org/project/key")

        return {
            "organization_id": org_id,
            "project_id": project_id,
            "api_key_id": key_id,
            "api_key": api_key,  # Only returned on creation
            "key_prefix": key_prefix,
            "message": "User initialized successfully with default organization, project, and API key",
        }

    except Exception as e:
        logging.exception("Error in initialize_user:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health", summary="Health check")
def health_check():
    """Health check (selfmemory style)."""
    try:
        return MEMORY_INSTANCE.health_check()
    except Exception:
        logging.exception("Error in health_check:")
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": "An internal error occurred"},
        )


@app.post("/reset", summary="Reset all memories")
def reset_memory():
    """Completely reset stored memories (selfmemory style)."""
    try:
        MEMORY_INSTANCE.reset()
        return {"message": "All memories reset"}
    except Exception as e:
        logging.exception("Error in reset_memory:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/", summary="Redirect to docs")
def home():
    """Redirect to the OpenAPI documentation."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("SELFMEMORY_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SELFMEMORY_SERVER_PORT", "8081"))

    logging.info("Starting SelfMemory Server...")
    logging.info(f"API available at: http://{host}:{port}/")
    logging.info(f"Documentation: http://{host}:{port}/docs")

    uvicorn.run(app, host=host, port=port, log_level="info")
