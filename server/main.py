"""
InMemory Server - FastAPI REST API for InMemory

This server imports and uses the inmemory library to provide REST endpoints
"""

import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import the inmemory library
from inmemory import Memory
from inmemory.repositories.mongodb_user_manager import MongoUserManager
from inmemory.search.enhanced_search_engine import EnhancedSearchEngine

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize MongoDB authentication and local Memory storage
try:
    # Initialize MongoDB for authentication (shared with dashboard)
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/inmemory")
    logger.info(f"Connecting to MongoDB for authentication: {mongodb_uri}")

    try:
        mongo_manager = MongoUserManager(mongodb_uri)
        logger.info("MongoDB authentication initialized successfully")

        # Test the connection immediately
        test_result = mongo_manager.api_keys.find_one()
        logger.info("MongoDB connection test successful")

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        logger.error(f"MongoDB URI: {mongodb_uri}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Full exception details: {repr(e)}")
        logger.warning("Running without authentication (development mode)")
        mongo_manager = None

    # Initialize Memory with Qdrant configuration (to access existing memories)

    # Create Memory with dict parameters targeting existing dashboard collection
    memory_instance = Memory(
        db={
            "provider": "qdrant",
            "host": "localhost",
            "port": 6333,
            "collection_name": "memories_68a9b5b25a3190e71a79b4fd",  # Existing dashboard collection
        },
        embedding={
            "provider": "ollama",
            "model": "nomic-embed-text",
            "ollama_host": "http://localhost:11434",
        },
    )
    logger.info("Memory instance initialized with Qdrant (existing memories)")

    # Also initialize enhanced search engine for advanced operations
    search_engine = EnhancedSearchEngine()
    logger.info("Enhanced search engine initialized (existing Qdrant infrastructure)")

except Exception as e:
    logger.error(f"Failed to initialize server components: {e}")
    raise

# FastAPI app
app = FastAPI(
    title="InMemory Server API",
    version="1.0.0",
    description="REST API for InMemory using the inmemory library",
)

# Add CORS middleware for dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local dashboard
        "http://localhost:8080",  # Alternative ports
        "https://inmemory.cpluz.com",  # Production dashboard
        "*",  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API requests
class AddMemoryRequest(BaseModel):
    memory_content: str = Field(..., description="The memory text to store")
    tags: str = Field("", description="Comma-separated tags")
    people_mentioned: str = Field("", description="Comma-separated people names")
    topic_category: str = Field("", description="Topic category")
    metadata: dict[str, Any] | None = Field(default_factory=dict)


class SearchMemoriesRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Maximum number of results")
    tags: str = Field("", description="Filter by tags")
    people_mentioned: str = Field("", description="Filter by people")
    topic_category: str = Field("", description="Filter by topic")
    temporal_filter: str = Field("", description="Temporal filter")


# Authentication dependency
def authenticate_api_key(authorization: str = Header(None)) -> str:
    """
    Authenticate API key using MongoDB (shared with dashboard).

    Args:
        authorization: Authorization header with Bearer token

    Returns:
        str: User ID if valid

    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Invalid authorization header format"
        )

    api_key = authorization.replace("Bearer ", "")

    # Use MongoDB for authentication (shared with dashboard)
    if not mongo_manager:
        logger.error("MongoDB authentication not available - cannot validate API key")
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable - MongoDB connection required",
        )

    try:
        user_id = mongo_manager.validate_api_key(api_key)
        if not user_id:
            logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
            raise HTTPException(status_code=401, detail="Invalid or expired API key")

        logger.info(f"API key validated successfully for user: {user_id}")
        return user_id

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        raise HTTPException(status_code=401, detail="Authentication error") from e


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "InMemory Server API",
        "version": "1.0.0",
        "library": "inmemory",
        "endpoints": {
            "health": "/v1/health",
            "auth": "/v1/auth/validate",
            "memories": "/v1/memories",
            "search": "/v1/search",
        },
    }


@app.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "InMemory Server API",
        "version": "1.0.0",
        "storage": "qdrant_existing_infrastructure",
    }


@app.get("/v1/auth/validate")
async def validate_auth(user_id: str = Depends(authenticate_api_key)):
    """Validate API key and return user info."""
    return {"valid": True, "user_id": user_id, "message": "API key is valid"}


@app.post("/v1/memories")
async def add_memory_api(
    request: AddMemoryRequest, user_id: str = Depends(authenticate_api_key)
):
    """Add a new memory using Memory class (unified Qdrant storage)."""
    try:
        # Use the Memory class directly (unified storage)
        result = memory_instance.add(
            memory_content=request.memory_content,
            tags=request.tags,
            people_mentioned=request.people_mentioned,
            topic_category=request.topic_category,
            metadata={"user_id": user_id},
        )

        if result.get("success"):
            logger.info(f"Memory added via Memory class: {result.get('memory_id')}")
            return {
                "success": True,
                "message": result.get("message"),
                "memory_id": result.get("memory_id"),
                "action": "added",
                "metadata": {"user_id": user_id, "storage": "unified_qdrant"},
            }
        return {
            "success": False,
            "message": result.get("error"),
            "memory_id": None,
            "action": "failed",
        }

    except Exception as e:
        logger.error(f"Exception in add_memory_api: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to add memory: {str(e)}",
            "memory_id": None,
            "action": "failed",
        }


@app.get("/v1/memories")
async def get_memories_api(
    limit: int = 10, offset: int = 0, user_id: str = Depends(authenticate_api_key)
):
    """Get user's memories using the inmemory library."""
    try:
        # Use the inmemory library Memory class
        results = memory_instance.get_all(limit=limit, offset=offset)

        # Format for dashboard compatibility
        memories = []
        for result in results.get("results", []):
            metadata = result.get("metadata", {})

            # Convert string fields to arrays for dashboard compatibility
            tags_str = metadata.get("tags", "")
            people_str = metadata.get("people_mentioned", "")

            tags_array = (
                [tag.strip() for tag in tags_str.split(",") if tag.strip()]
                if tags_str
                else []
            )
            people_array = (
                [person.strip() for person in people_str.split(",") if person.strip()]
                if people_str
                else []
            )

            memory_data = {
                "id": result.get("id"),
                "memory_content": result.get("content", ""),
                "memory": result.get("content", ""),  # Both formats for compatibility
                "tags": tags_array,  # Convert to array
                "people_mentioned": people_array,  # Convert to array
                "topic_category": metadata.get("topic_category", ""),
                "metadata": metadata,
                "score": 1.0,  # Default score for get_all
                "created_at": result.get("metadata", {}).get("created_at", ""),
                "updated_at": result.get("metadata", {}).get("created_at", ""),
            }
            memories.append(memory_data)

        return {
            "memories": memories,
            "total": len(memories),
            "hasMore": len(results.get("results", [])) >= limit,
        }

    except Exception as e:
        logger.error(f"Failed to get memories: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get memories: {str(e)}"
        ) from e


@app.delete("/v1/memories/{memory_id}")
async def delete_memory_api(
    memory_id: str, user_id: str = Depends(authenticate_api_key)
):
    """Delete a specific memory using the inmemory library."""
    try:
        logger.info(f"DELETE API: Deleting memory {memory_id} for user {user_id}")

        if not memory_id or not memory_id.strip():
            raise HTTPException(
                status_code=400, detail="Memory ID is required for deletion"
            )

        # Use the inmemory library Memory class
        result = memory_instance.delete(memory_id.strip())

        if result.get("success", False):
            logger.info(f"Successfully deleted memory {memory_id}")
            return {
                "success": True,
                "message": f"Memory deleted successfully (ID: {memory_id})",
                "memory_id": memory_id,
            }

        logger.error(f"Delete operation returned False for memory {memory_id}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete memory {memory_id}"
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to delete memory {memory_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete memory: {str(e)}"
        ) from e


@app.post("/v1/search")
async def search_memories_api(
    request: SearchMemoriesRequest, user_id: str = Depends(authenticate_api_key)
):
    """Search memories using the inmemory library."""
    try:
        # Parse filters
        tag_list = (
            [tag.strip() for tag in request.tags.split(",") if tag.strip()]
            if request.tags
            else None
        )
        people_list = (
            [
                person.strip()
                for person in request.people_mentioned.split(",")
                if person.strip()
            ]
            if request.people_mentioned
            else None
        )

        # Use the inmemory library Memory class
        results = memory_instance.search(
            query=request.query,
            limit=request.limit,
            tags=tag_list,
            people_mentioned=people_list,
            topic_category=request.topic_category if request.topic_category else None,
            temporal_filter=request.temporal_filter
            if request.temporal_filter
            else None,
        )

        # Format for dashboard compatibility
        formatted_results = []
        for result in results.get("results", []):
            metadata = result.get("metadata", {})

            # Convert string fields to arrays for dashboard compatibility
            tags_str = metadata.get("tags", "")
            people_str = metadata.get("people_mentioned", "")

            tags_array = (
                [tag.strip() for tag in tags_str.split(",") if tag.strip()]
                if tags_str
                else []
            )
            people_array = (
                [person.strip() for person in people_str.split(",") if person.strip()]
                if people_str
                else []
            )

            formatted_result = {
                "id": result.get("id"),
                "memory_content": result.get("content", ""),
                "memory": result.get("content", ""),  # Both formats for compatibility
                "tags": tags_array,  # Convert to array
                "people_mentioned": people_array,  # Convert to array
                "topic_category": metadata.get("topic_category", ""),
                "metadata": metadata,
                "score": result.get("score", 0),
                "created_at": result.get("metadata", {}).get("created_at", ""),
                "updated_at": result.get("metadata", {}).get("created_at", ""),
            }
            formatted_results.append(formatted_result)

        return {"memories": formatted_results, "total": len(formatted_results)}

    except Exception as e:
        logger.error(f"Failed to search memories: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to search memories: {str(e)}"
        ) from e


# Dashboard compatibility endpoints (same as /v1/* but with /api/* paths)
@app.post("/api/memories")
async def add_memory_api_dashboard(
    request: AddMemoryRequest, user_id: str = Depends(authenticate_api_key)
):
    """Add memory endpoint for dashboard compatibility (same as /v1/memories)."""
    return await add_memory_api(request, user_id)


@app.get("/api/memories")
async def get_memories_api_dashboard(
    limit: int = 10, offset: int = 0, user_id: str = Depends(authenticate_api_key)
):
    """Get memories endpoint for dashboard compatibility (same as /v1/memories)."""
    return await get_memories_api(limit, offset, user_id)


@app.delete("/api/memories/{memory_id}")
async def delete_memory_api_dashboard(
    memory_id: str, user_id: str = Depends(authenticate_api_key)
):
    """Delete memory endpoint for dashboard compatibility (same as /v1/memories/{id})."""
    return await delete_memory_api(memory_id, user_id)


@app.post("/api/search")
async def search_memories_api_dashboard(
    request: SearchMemoriesRequest, user_id: str = Depends(authenticate_api_key)
):
    """Search memories endpoint for dashboard compatibility (same as /v1/search)."""
    return await search_memories_api(request, user_id)


if __name__ == "__main__":
    import uvicorn

    # Get host and port from environment or use defaults
    host = os.getenv("INMEMORY_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("INMEMORY_SERVER_PORT", "8081"))

    logger.info("Starting InMemory Server...")
    logger.info(f"API will be available at: http://{host}:{port}/")
    logger.info(f"Health check: http://{host}:{port}/v1/health")
    logger.info(f"Dashboard compatibility: http://{host}:{port}/api/memories")
    logger.info(f"Documentation: http://{host}:{port}/docs")

    # Run the server
    uvicorn.run(app, host=host, port=port, log_level="info")
