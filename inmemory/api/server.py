"""
InMemory API Server - FastAPI implementation for dashboard integration.

This server provides REST API endpoints that work with dashboard authentication
while using the local Memory class for storage operations.
"""

import logging
import os
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from ..memory import Memory
from ..repositories.mongodb_user_manager import MongoUserManager

logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()


# Simplified Pydantic models (no user_id required)
class MemoryRequest(BaseModel):
    memory_content: str = Field(..., description="The memory text to store")
    tags: str | None = Field("", description="Comma-separated tags")
    people_mentioned: str | None = Field("", description="Comma-separated people names")
    topic_category: str | None = Field("", description="Topic category")
    metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="Additional metadata"
    )


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query string")
    limit: int = Field(10, description="Maximum number of results")
    tags: list[str] | None = Field(None, description="List of tags to filter by")
    people_mentioned: list[str] | None = Field(
        None, description="List of people to filter by"
    )
    topic_category: str | None = Field(None, description="Topic category filter")
    temporal_filter: str | None = Field(None, description="Temporal filter")
    threshold: float | None = Field(None, description="Minimum similarity score")


class APIResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str | None = Field(None, description="Response message")
    data: dict[str, Any] | None = Field(None, description="Response data")
    error: str | None = Field(None, description="Error message if unsuccessful")


class MemoryResponse(APIResponse):
    memory_id: str | None = Field(None, description="ID of the created/modified memory")


class SearchResponse(APIResponse):
    results: list[dict[str, Any]] = Field(
        default_factory=list, description="Search results"
    )


class UserInfo(BaseModel):
    user_id: str
    api_key: str
    created_at: datetime
    last_used: datetime | None = None
    usage_count: int = 0


class InMemoryAPI:
    """Main API class for dashboard integration with MongoDB authentication."""

    def __init__(self):
        """Initialize the API with local memory storage and MongoDB authentication."""
        # Initialize local memory instance (zero-setup)
        self.memory = Memory()

        # Initialize MongoDB connection for API key validation
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/inmemory")
        try:
            self.mongo_manager = MongoUserManager(mongodb_uri)
            logger.info(f"Connected to MongoDB for authentication: {mongodb_uri}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            # Fallback to no authentication for development
            self.mongo_manager = None
            logger.warning("Running without authentication (development mode)")

        logger.info("InMemoryAPI initialized with MongoDB authentication")

    def _validate_api_key(self, api_key: str) -> str | None:
        """Validate an API key using MongoDB and return user_id."""
        if not self.mongo_manager:
            # Development mode - no authentication
            logger.info("No authentication in development mode")
            return "dev_user"

        try:
            # Use existing MongoDB logic for API key validation
            user_id = self.mongo_manager.validate_api_key(api_key)
            if user_id:
                logger.info(f"Valid API key for user: {user_id}")
                return user_id
            logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
            return None

        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return None


# Global API instance
api_instance = InMemoryAPI()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Get current user from API key."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = api_instance._validate_api_key(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="InMemory API",
        description="Local InMemory service for dashboard integration",
        version="1.0.0",
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
    @app.get("/v1/health")
    async def health_check():
        """Detailed health check."""
        try:
            health_result = api_instance.memory.health_check()
            return {
                "status": "healthy",
                "service": "InMemory Core API",
                "version": "1.0.0",
                "storage": health_result.get("storage_type", "embedded"),
                "memory_count": health_result.get("memory_count", 0),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "InMemory Core API",
                "error": str(e),
            }

    @app.get("/v1/auth/validate")
    async def validate_auth(current_user_id: str = Depends(get_current_user)):
        """Validate API key endpoint."""
        return {"valid": True, "user_id": current_user_id}

    # Simplified memory operations (no user_id required in body)
    @app.post("/v1/memories", response_model=MemoryResponse)
    async def add_memory(
        request: MemoryRequest, current_user_id: str = Depends(get_current_user)
    ):
        """Add a new memory."""
        try:
            # Use simplified Memory API (no user_id needed)
            result = api_instance.memory.add(
                memory_content=request.memory_content,
                tags=request.tags,
                people_mentioned=request.people_mentioned,
                topic_category=request.topic_category,
                metadata=request.metadata,
            )

            if result.get("success", True):
                return MemoryResponse(
                    success=True,
                    message="Memory added successfully",
                    memory_id=result.get("memory_id"),
                    data=result,
                )

            error_msg = result.get("error", "Failed to add memory")
            raise HTTPException(status_code=400, detail=error_msg)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding memory: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/v1/search", response_model=SearchResponse)
    async def search_memories(
        request: SearchRequest, current_user_id: str = Depends(get_current_user)
    ):
        """Search memories."""
        try:
            # Use simplified Memory API (no user_id needed)
            result = api_instance.memory.search(
                query=request.query,
                limit=request.limit,
                tags=request.tags,
                people_mentioned=request.people_mentioned,
                topic_category=request.topic_category,
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
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/v1/memories", response_model=SearchResponse)
    async def get_all_memories(
        limit: int = 100,
        offset: int = 0,
        current_user_id: str = Depends(get_current_user),
    ):
        """Get all memories."""
        try:
            # Use simplified Memory API (no user_id needed)
            result = api_instance.memory.get_all(limit=limit, offset=offset)

            return SearchResponse(
                success=True,
                message=f"Retrieved {len(result.get('results', []))} memories",
                results=result.get("results", []),
                data=result,
            )

        except Exception as e:
            logger.error(f"Error getting memories: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.delete("/v1/memories/{memory_id}", response_model=APIResponse)
    async def delete_memory(
        memory_id: str, current_user_id: str = Depends(get_current_user)
    ):
        """Delete a specific memory."""
        try:
            # Use simplified Memory API (no user_id needed)
            result = api_instance.memory.delete(memory_id)

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
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.delete("/v1/memories", response_model=APIResponse)
    async def delete_all_memories(current_user_id: str = Depends(get_current_user)):
        """Delete all memories."""
        try:
            # Use simplified Memory API (no user_id needed)
            result = api_instance.memory.delete_all()

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
            raise HTTPException(status_code=500, detail=str(e)) from e

    # Stats endpoint (no user_id required)
    @app.get("/v1/stats")
    async def get_stats(current_user_id: str = Depends(get_current_user)):
        """Get statistics."""
        try:
            result = api_instance.memory.get_stats()
            return result

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    return app


def run_server(host: str = "0.0.0.0", port: int = 8081, debug: bool = False):
    """Run the API server."""
    app = create_app()

    logger.info(f"Starting InMemory API server on {host}:{port}")
    logger.info("Dashboard can authenticate using API keys")
    logger.info("Local Memory storage with embedded ChromaDB")

    uvicorn.run(
        app,
        host=host,
        port=port,
        debug=debug,
        log_level="info" if not debug else "debug",
    )


if __name__ == "__main__":
    run_server(debug=True)
