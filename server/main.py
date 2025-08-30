import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from inmemory import Memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load environment variables
load_dotenv()

# Environment configuration (following mem0 pattern)
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = os.environ.get("QDRANT_PORT", "6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "inmemory_memories")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

# Default configuration (mem0 style)
DEFAULT_CONFIG = {
    "embedding": {
        "provider": "ollama",
        "config": {
            "model": EMBEDDING_MODEL,
            "ollama_base_url": OLLAMA_HOST,
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": QDRANT_HOST,
            "port": int(QDRANT_PORT),
            "collection_name": QDRANT_COLLECTION,
        }
    }
}

# Initialize global Memory instance (exactly like mem0)
MEMORY_INSTANCE = Memory(config=DEFAULT_CONFIG)

# FastAPI app
app = FastAPI(
    title="InMemory REST API",
    description="A REST API for managing and searching memories using the InMemory SDK.",
    version="1.0.0",
)

# Add CORS middleware for dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080", 
        "https://inmemory.cpluz.com",
        "*",  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models (adapted from mem0)
class MemoryCreate(BaseModel):
    memory_content: str = Field(..., description="The memory text to store")
    tags: Optional[str] = None
    people_mentioned: Optional[str] = None
    topic_category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Maximum number of results")
    tags: Optional[List[str]] = None
    people_mentioned: Optional[List[str]] = None
    topic_category: Optional[str] = None
    temporal_filter: Optional[str] = None
    threshold: Optional[float] = None


# API Endpoints (following mem0 pattern)

@app.post("/configure", summary="Configure InMemory")
def set_config(config: Dict[str, Any]):
    """Set memory configuration."""
    global MEMORY_INSTANCE
    MEMORY_INSTANCE = Memory(config=config)
    return {"message": "Configuration set successfully"}


@app.post("/memories", summary="Create memories")
def add_memory(memory_create: MemoryCreate):
    """Store new memories."""
    try:
        params = {k: v for k, v in memory_create.model_dump().items() if v is not None}
        response = MEMORY_INSTANCE.add(**params)
        return JSONResponse(content=response)
    except Exception as e:
        logging.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories", summary="Get memories")
def get_all_memories(
    limit: int = 100,
    offset: int = 0,
):
    """Retrieve stored memories."""
    try:
        response = MEMORY_INSTANCE.get_all(limit=limit, offset=offset)
        return JSONResponse(content=response)
    except Exception as e:
        logging.exception("Error in get_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}", summary="Get a memory")
def get_memory(memory_id: str):
    """Retrieve a specific memory by ID."""
    try:
        # Get all memories and filter by ID (since Memory class doesn't have get method)
        all_memories = MEMORY_INSTANCE.get_all(limit=10000)
        for memory in all_memories.get("results", []):
            if memory.get("id") == memory_id:
                return JSONResponse(content=memory)
        raise HTTPException(status_code=404, detail="Memory not found")
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", summary="Search memories")
def search_memories(search_req: SearchRequest):
    """Search for memories based on a query."""
    try:
        params = {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}
        response = MEMORY_INSTANCE.search(query=search_req.query, **params)
        return JSONResponse(content=response)
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories/{memory_id}", summary="Delete a memory")
def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    try:
        response = MEMORY_INSTANCE.delete(memory_id=memory_id)
        if response.get("success"):
            return {"message": "Memory deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Memory not found or deletion failed")
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in delete_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories", summary="Delete all memories")
def delete_all_memories():
    """Delete all memories."""
    try:
        response = MEMORY_INSTANCE.delete_all()
        if response.get("success"):
            return {"message": f"All memories deleted. Count: {response.get('deleted_count', 0)}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete all memories")
    except Exception as e:
        logging.exception("Error in delete_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", summary="Health check")
def health_check():
    """Perform health check on all components."""
    try:
        health = MEMORY_INSTANCE.health_check()
        return JSONResponse(content=health)
    except Exception as e:
        logging.exception("Error in health_check:")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "service": "inmemory"
            }
        )


@app.get("/stats", summary="Get statistics")
def get_stats():
    """Get statistics for memories."""
    try:
        stats = MEMORY_INSTANCE.get_stats()
        return JSONResponse(content=stats)
    except Exception as e:
        logging.exception("Error in get_stats:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset", summary="Reset all memories")
def reset_memory():
    """Completely reset stored memories (same as delete_all)."""
    try:
        response = MEMORY_INSTANCE.delete_all()
        if response.get("success"):
            return {"message": f"All memories reset. Count: {response.get('deleted_count', 0)}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reset memories")
    except Exception as e:
        logging.exception("Error in reset_memory:")
        raise HTTPException(status_code=500, detail=str(e))


# Dashboard compatibility endpoints (for existing dashboard)
@app.post("/v1/memories", summary="Create memories (v1 compatibility)")
def add_memory_v1(memory_create: MemoryCreate):
    """Store new memories (v1 API compatibility)."""
    return add_memory(memory_create)


@app.get("/v1/memories", summary="Get memories (v1 compatibility)")
def get_all_memories_v1(limit: int = 100, offset: int = 0):
    """Retrieve stored memories (v1 API compatibility)."""
    return get_all_memories(limit=limit, offset=offset)


@app.post("/v1/search", summary="Search memories (v1 compatibility)")
def search_memories_v1(search_req: SearchRequest):
    """Search for memories (v1 API compatibility)."""
    return search_memories(search_req)


@app.delete("/v1/memories/{memory_id}", summary="Delete a memory (v1 compatibility)")
def delete_memory_v1(memory_id: str):
    """Delete a specific memory (v1 API compatibility)."""
    return delete_memory(memory_id)


@app.get("/v1/health", summary="Health check (v1 compatibility)")
def health_check_v1():
    """Health check (v1 API compatibility)."""
    return health_check()


@app.get("/", summary="Redirect to the OpenAPI documentation", include_in_schema=False)
def home():
    """Redirect to the OpenAPI documentation."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    
    # Get host and port from environment or use defaults
    host = os.getenv("INMEMORY_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("INMEMORY_SERVER_PORT", "8081"))
    
    logging.info("Starting InMemory Server...")
    logging.info(f"API will be available at: http://{host}:{port}/")
    logging.info(f"Health check: http://{host}:{port}/health")
    logging.info(f"Documentation: http://{host}:{port}/docs")
    
    # Run the server
    uvicorn.run(app, host=host, port=port, log_level="info")
