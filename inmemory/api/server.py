"""
InMemory API Server - FastAPI implementation for managed solution.

This module provides the REST API server for the managed InMemory service,
handling authentication, user management, and memory operations.
"""

import hashlib
import logging
import secrets
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from ..config import load_config

# Import existing InMemory components
from ..memory import Memory

logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()


# Pydantic models for API requests/responses
class MemoryRequest(BaseModel):
    memory_content: str = Field(..., description="The memory text to store")
    user_id: str = Field(..., description="User identifier")
    tags: str | None = Field("", description="Comma-separated tags")
    people_mentioned: str | None = Field(
        "", description="Comma-separated people names"
    )
    topic_category: str | None = Field("", description="Topic category")
    metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="Additional metadata"
    )


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query string")
    user_id: str = Field(..., description="User identifier")
    limit: int = Field(10, description="Maximum number of results")
    tags: list[str] | None = Field(None, description="List of tags to filter by")
    people_mentioned: list[str] | None = Field(
        None, description="List of people to filter by"
    )
    topic_category: str | None = Field(None, description="Topic category filter")
    temporal_filter: str | None = Field(None, description="Temporal filter")
    threshold: float | None = Field(None, description="Minimum similarity score")


class TemporalSearchRequest(BaseModel):
    temporal_query: str = Field(..., description="Temporal query")
    user_id: str = Field(..., description="User identifier")
    semantic_query: str | None = Field(
        None, description="Optional semantic search query"
    )
    limit: int = Field(10, description="Maximum number of results")


class TagSearchRequest(BaseModel):
    tags: list[str] = Field(..., description="Tags to search for")
    user_id: str = Field(..., description="User identifier")
    semantic_query: str | None = Field(
        None, description="Optional semantic search query"
    )
    match_all: bool = Field(False, description="Whether all tags must match")
    limit: int = Field(10, description="Maximum number of results")


class PeopleSearchRequest(BaseModel):
    people: list[str] = Field(..., description="People to search for")
    user_id: str = Field(..., description="User identifier")
    semantic_query: str | None = Field(
        None, description="Optional semantic search query"
    )
    limit: int = Field(10, description="Maximum number of results")


class APIKeyCreateRequest(BaseModel):
    name: str = Field("default", description="Name for the API key")


class APIResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str | None = Field(None, description="Response message")
    data: dict[str, Any] | None = Field(None, description="Response data")
    error: str | None = Field(None, description="Error message if unsuccessful")


class MemoryResponse(APIResponse):
    memory_id: str | None = Field(
        None, description="ID of the created/modified memory"
    )


class SearchResponse(APIResponse):
    results: list[dict[str, Any]] = Field(
        default_factory=list, description="Search results"
    )


class UserInfo(BaseModel):
    user_id: str
    api_key_hash: str
    created_at: datetime
    last_used: datetime | None = None
    usage_count: int = 0


class InMemoryAPI:
    """Main API class for the managed InMemory service."""

    def __init__(self):
        """Initialize the API with configuration and storage."""
        # Load configuration for API server
        self.config = load_config()

        # Initialize memory instance for operations
        self.memory = Memory(config=self.config)

        # In-memory store for API keys (in production, use Redis/Database)
        self.api_keys: dict[str, UserInfo] = {}

        # Load existing API keys from storage if available
        self._load_api_keys()

        logger.info("InMemoryAPI initialized")

    def _load_api_keys(self):
        """Load existing API keys from storage."""
        try:
            # Try to load from storage backend
            if hasattr(self.memory.store, "get_all_api_keys"):
                stored_keys = self.memory.store.get_all_api_keys()
                for key_info in stored_keys:
                    self.api_keys[key_info["api_key_hash"]] = UserInfo(**key_info)
                logger.info(f"Loaded {len(stored_keys)} existing API keys")
        except Exception as e:
            logger.warning(f"Could not load existing API keys: {e}")

    def _validate_api_key(self, api_key: str) -> UserInfo | None:
        """Validate an API key and return user info."""
        try:
            # Hash the API key for lookup
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            if key_hash in self.api_keys:
                user_info = self.api_keys[key_hash]
                # Update last used timestamp
                user_info.last_used = datetime.now()
                user_info.usage_count += 1
                return user_info

            return None
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return None

    def generate_api_key(self, user_id: str, name: str = "default") -> dict[str, Any]:
        """Generate a new API key for a user."""
        try:
            # Generate secure API key
            api_key = f"im_{secrets.token_urlsafe(32)}"
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Create user info
            user_info = UserInfo(
                user_id=user_id,
                api_key_hash=key_hash,
                created_at=datetime.now(),
                usage_count=0,
            )

            # Store in memory
            self.api_keys[key_hash] = user_info

            # Store in persistent storage if available
            try:
                if hasattr(self.memory.store, "store_api_key"):
                    self.memory.store.store_api_key(
                        user_id=user_id, api_key=api_key, name=name, created_via="api"
                    )
            except Exception as e:
                logger.warning(f"Could not persist API key: {e}")

            # Ensure user exists in memory system
            self.memory.create_user(user_id)

            logger.info(f"Generated API key for user {user_id}")
            return {
                "success": True,
                "api_key": api_key,
                "user_id": user_id,
                "name": name,
            }

        except Exception as e:
            logger.error(f"Failed to generate API key: {e}")
            return {"success": False, "error": str(e)}

    def revoke_api_key(self, api_key: str) -> dict[str, Any]:
        """Revoke an API key."""
        try:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            if key_hash in self.api_keys:
                user_info = self.api_keys[key_hash]
                del self.api_keys[key_hash]

                # Remove from persistent storage if available
                try:
                    if hasattr(self.memory.store, "revoke_api_key"):
                        self.memory.store.revoke_api_key(api_key)
                except Exception as e:
                    logger.warning(f"Could not remove API key from storage: {e}")

                logger.info(f"Revoked API key for user {user_info.user_id}")
                return {"success": True, "message": "API key revoked successfully"}
            return {"success": False, "error": "API key not found"}

        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            return {"success": False, "error": str(e)}


# Global API instance
api_instance = InMemoryAPI()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> UserInfo:
    """Get current user from API key."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_info = api_instance._validate_api_key(credentials.credentials)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_info


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="InMemory API",
        description="Managed InMemory service for enhanced memory management",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint (no auth required)
    @app.get("/v1/ping/")
    async def ping():
        """Health check endpoint."""
        return {
            "success": True,
            "message": "InMemory API is running",
            "timestamp": datetime.now().isoformat(),
            "service": "managed",
        }

    @app.get("/v1/health/")
    async def health_check():
        """Detailed health check."""
        health_result = api_instance.memory.health_check()
        return health_result

    # Authentication endpoints
    @app.post("/v1/auth/generate-key/")
    async def generate_api_key(request: APIKeyCreateRequest):
        """Generate a new API key."""
        # For demo purposes, allow anonymous key generation
        # In production, this would require admin authentication
        user_id = f"user_{secrets.token_hex(8)}"
        result = api_instance.generate_api_key(user_id, request.name)

        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])

    @app.delete("/v1/auth/revoke-key/")
    async def revoke_api_key(current_user: UserInfo = Depends(get_current_user)):
        """Revoke the current API key."""
        # Find the API key from the current user
        for key_hash, user_info in api_instance.api_keys.items():
            if user_info.user_id == current_user.user_id:
                # Reconstruct the key or store it differently for revocation
                # For now, we'll revoke by user_id
                del api_instance.api_keys[key_hash]
                return {"success": True, "message": "API key revoked"}

        raise HTTPException(status_code=404, detail="API key not found")

    # Memory operations endpoints
    @app.post("/v1/memories/", response_model=MemoryResponse)
    async def add_memory(
        request: MemoryRequest, current_user: UserInfo = Depends(get_current_user)
    ):
        """Add a new memory."""
        try:
            result = api_instance.memory.add(
                memory_content=request.memory_content,
                user_id=request.user_id,
                tags=request.tags,
                people_mentioned=request.people_mentioned,
                topic_category=request.topic_category,
                metadata=request.metadata,
            )

            if isinstance(result, dict) and result.get("success", True):
                return MemoryResponse(
                    success=True,
                    message="Memory added successfully",
                    memory_id=result.get("memory_id"),
                    data=result,
                )
            error_msg = (
                result.get("error", "Failed to add memory")
                if isinstance(result, dict)
                else str(result)
            )
            raise HTTPException(status_code=400, detail=error_msg)

        except Exception as e:
            logger.error(f"Error adding memory: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/memories/search/", response_model=SearchResponse)
    async def search_memories(
        request: SearchRequest, current_user: UserInfo = Depends(get_current_user)
    ):
        """Search memories."""
        try:
            result = api_instance.memory.search(
                query=request.query,
                user_id=request.user_id,
                limit=request.limit,
                tags=request.tags,
                people_mentioned=request.people_mentioned,
                topic_category=request.topic_category,
                temporal_filter=request.temporal_filter,
                threshold=request.threshold,
            )

            return SearchResponse(
                success=True,
                message=f"Found {len(result.get('results', []))} memories",
                results=result.get("results", []),
                data=result,
            )

        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/v1/memories/", response_model=SearchResponse)
    async def get_all_memories(
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        current_user: UserInfo = Depends(get_current_user),
    ):
        """Get all memories for a user."""
        try:
            result = api_instance.memory.get_all(
                user_id=user_id, limit=limit, offset=offset
            )

            return SearchResponse(
                success=True,
                message=f"Retrieved {len(result.get('results', []))} memories",
                results=result.get("results", []),
                data=result,
            )

        except Exception as e:
            logger.error(f"Error getting memories: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/v1/memories/{memory_id}", response_model=APIResponse)
    async def delete_memory(
        memory_id: str, user_id: str, current_user: UserInfo = Depends(get_current_user)
    ):
        """Delete a specific memory."""
        try:
            result = api_instance.memory.delete(memory_id, user_id)

            if result.get("success", False):
                return APIResponse(
                    success=True, message="Memory deleted successfully", data=result
                )
            error_msg = result.get("error", "Failed to delete memory")
            raise HTTPException(status_code=404, detail=error_msg)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/v1/memories/", response_model=APIResponse)
    async def delete_all_memories(
        user_id: str, current_user: UserInfo = Depends(get_current_user)
    ):
        """Delete all memories for a user."""
        try:
            result = api_instance.memory.delete_all(user_id)

            if result.get("success", False):
                return APIResponse(
                    success=True,
                    message=f"Deleted {result.get('deleted_count', 0)} memories",
                    data=result,
                )
            error_msg = result.get("error", "Failed to delete memories")
            raise HTTPException(status_code=400, detail=error_msg)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting all memories: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Advanced search endpoints
    @app.post("/v1/memories/temporal-search/", response_model=SearchResponse)
    async def temporal_search(
        request: TemporalSearchRequest,
        current_user: UserInfo = Depends(get_current_user),
    ):
        """Search memories using temporal queries."""
        try:
            result = api_instance.memory.temporal_search(
                temporal_query=request.temporal_query,
                user_id=request.user_id,
                semantic_query=request.semantic_query,
                limit=request.limit,
            )

            return SearchResponse(
                success=True,
                message=f"Found {len(result.get('results', []))} memories",
                results=result.get("results", []),
                data=result,
            )

        except Exception as e:
            logger.error(f"Error in temporal search: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/memories/tag-search/", response_model=SearchResponse)
    async def tag_search(
        request: TagSearchRequest, current_user: UserInfo = Depends(get_current_user)
    ):
        """Search memories by tags."""
        try:
            result = api_instance.memory.search_by_tags(
                tags=request.tags,
                user_id=request.user_id,
                semantic_query=request.semantic_query,
                match_all=request.match_all,
                limit=request.limit,
            )

            return SearchResponse(
                success=True,
                message=f"Found {len(result.get('results', []))} memories",
                results=result.get("results", []),
                data=result,
            )

        except Exception as e:
            logger.error(f"Error in tag search: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/memories/people-search/", response_model=SearchResponse)
    async def people_search(
        request: PeopleSearchRequest, current_user: UserInfo = Depends(get_current_user)
    ):
        """Search memories by people mentioned."""
        try:
            result = api_instance.memory.search_by_people(
                people=request.people,
                user_id=request.user_id,
                semantic_query=request.semantic_query,
                limit=request.limit,
            )

            return SearchResponse(
                success=True,
                message=f"Found {len(result.get('results', []))} memories",
                results=result.get("results", []),
                data=result,
            )

        except Exception as e:
            logger.error(f"Error in people search: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # User management endpoints
    @app.get("/v1/users/{user_id}/stats")
    async def get_user_stats(
        user_id: str, current_user: UserInfo = Depends(get_current_user)
    ):
        """Get statistics for a user."""
        try:
            result = api_instance.memory.get_user_stats(user_id)
            return result

        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/v1/users/current")
    async def get_current_user_info(current_user: UserInfo = Depends(get_current_user)):
        """Get current user information."""
        return {
            "user_id": current_user.user_id,
            "created_at": current_user.created_at.isoformat(),
            "last_used": current_user.last_used.isoformat()
            if current_user.last_used
            else None,
            "usage_count": current_user.usage_count,
        }

    return app


def run_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Run the API server."""
    app = create_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
        debug=debug,
        log_level="info" if not debug else "debug",
    )


if __name__ == "__main__":
    run_server(debug=True)
