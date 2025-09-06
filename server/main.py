import logging
import os
import hashlib
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from inmemory import Memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load environment variables
load_dotenv()

# Default configuration (mem0 style - simple and clean)
DEFAULT_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "inmemory_memories",
            "host": "localhost",
            "port": 6333  # Default Qdrant Docker port
        }
    },
    "embedding": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434"
        }
    }
}

# Global Memory instance (mem0 style - single instance for all users)
MEMORY_INSTANCE = Memory(config=DEFAULT_CONFIG)

# FastAPI app
app = FastAPI(
    title="InMemory REST APIs",
    description="A REST API for managing and searching memories - following mem0 patterns.",
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

# Pydantic models (mem0 style)
class Message(BaseModel):
    role: str = Field(..., description="Role of the message (user or assistant).")
    content: str = Field(..., description="Message content.")

class MemoryCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to store.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

# Simple authentication (optional - can be removed for even more simplicity)
def authenticate_api_key(authorization: str = Header(None)) -> str:
    """Simple API key authentication - accepts both sk_im_ and inmem_sk_ formats."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    api_key = authorization.replace("Bearer ", "")
    
    # Accept both formats: sk_im_ and inmem_sk_
    if not (api_key.startswith("sk_im_") or api_key.startswith("inmem_sk_")):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    
    # Generate user_id from API key (like mem0)
    return hashlib.md5(api_key.encode()).hexdigest()

# API Endpoints (mem0 exact pattern)
@app.get("/api/v1/ping", summary="Ping endpoint for client validation")
def ping_endpoint(user_id: str = Depends(authenticate_api_key)):
    """Ping endpoint that returns user info on successful authentication."""
    return {
        "status": "ok",
        "user_id": user_id,
        "key_id": "default",
        "permissions": ["read", "write"],
        "name": "InMemory User"
    }

@app.post("/configure", summary="Configure InMemory")
def set_config(config: Dict[str, Any]):
    """Set memory configuration (mem0 style)."""
    global MEMORY_INSTANCE
    MEMORY_INSTANCE = Memory(config=config)
    return {"message": "Configuration set successfully"}

@app.post("/api/memories", summary="Create memories")
def add_memory(memory_create: MemoryCreate, user_id: str = Depends(authenticate_api_key)):
    """Store new memories (mem0 style with user isolation)."""
    if not any([memory_create.user_id, memory_create.agent_id, memory_create.run_id, user_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    
    try:
        # Extract memory content from messages (mem0 style)
        memory_content = ""
        if memory_create.messages:
            # Combine all message contents
            memory_content = " ".join([msg.content for msg in memory_create.messages])
        
        # Extract metadata fields for inmemory-core compatibility
        metadata = memory_create.metadata or {}
        tags = metadata.get("tags", "")
        people_mentioned = metadata.get("people_mentioned", "")
        topic_category = metadata.get("topic_category", "")
        
        # Use the single global instance with user_id for isolation (inmemory-core pattern)
        response = MEMORY_INSTANCE.add(
            memory_content=memory_content,
            user_id=user_id or memory_create.user_id,  # Data-level isolation
            tags=tags,
            people_mentioned=people_mentioned,
            topic_category=topic_category,
            metadata=metadata
        )
        return JSONResponse(content=response)
    except Exception as e:
        logging.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memories", summary="Get memories")
def get_all_memories(user_id: str = Depends(authenticate_api_key)):
    """Retrieve stored memories (mem0 style)."""
    try:
        return MEMORY_INSTANCE.get_all(user_id=user_id)
    except Exception as e:
        logging.exception("Error in get_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memories/{memory_id}", summary="Get a memory")
def get_memory(memory_id: str, user_id: str = Depends(authenticate_api_key)):
    """Retrieve a specific memory by ID (mem0 style)."""
    try:
        return MEMORY_INSTANCE.get(memory_id, user_id=user_id)
    except Exception as e:
        logging.exception("Error in get_memory:")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/memories/search", summary="Search memories")
def search_memories(search_req: SearchRequest, user_id: str = Depends(authenticate_api_key)):
    """Search for memories (mem0 style)."""
    try:
        # Build base parameters - exclude query, filters, and None values
        params = {k: v for k, v in search_req.model_dump().items() 
                 if v is not None and k not in ["query", "filters"]}
        
        # Override with authenticated user_id if available (takes precedence)
        if user_id:
            params["user_id"] = user_id
        
        # Handle filters parameter by extracting supported filter options
        if search_req.filters:
            # Extract supported filter parameters from the filters dict
            supported_filters = [
                "limit", "tags", "people_mentioned", "topic_category", 
                "temporal_filter", "threshold", "match_all_tags", 
                "include_metadata", "sort_by"
            ]
            for filter_key in supported_filters:
                if filter_key in search_req.filters:
                    filter_value = search_req.filters[filter_key]
                    
                    # Handle special cases for data type conversion
                    if filter_key == "tags" and isinstance(filter_value, list):
                        # Convert list of tags to comma-separated string if needed
                        params[filter_key] = filter_value  # Keep as list - Memory.search() expects list
                    elif filter_key == "people_mentioned" and isinstance(filter_value, list):
                        # Keep as list - Memory.search() expects list
                        params[filter_key] = filter_value
                    else:
                        params[filter_key] = filter_value
        
        # Call search with query and unpacked params (mem0 pattern)
        return MEMORY_INSTANCE.search(query=search_req.query, **params)
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/memories/{memory_id}", summary="Delete a memory")
def delete_memory(memory_id: str, user_id: str = Depends(authenticate_api_key)):
    """Delete a specific memory (mem0 style)."""
    try:
        MEMORY_INSTANCE.delete(memory_id=memory_id, user_id=user_id)
        return {"message": "Memory deleted successfully"}
    except Exception as e:
        logging.exception("Error in delete_memory:")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/memories", summary="Delete all memories")
def delete_all_memories(user_id: str = Depends(authenticate_api_key)):
    """Delete all memories for a user (mem0 style)."""
    try:
        MEMORY_INSTANCE.delete_all(user_id=user_id)
        return {"message": "All memories deleted"}
    except Exception as e:
        logging.exception("Error in delete_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", summary="Health check")
def health_check():
    """Health check (mem0 style)."""
    try:
        return MEMORY_INSTANCE.health_check()
    except Exception as e:
        logging.exception("Error in health_check:")
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.post("/reset", summary="Reset all memories")
def reset_memory():
    """Completely reset stored memories (mem0 style)."""
    try:
        MEMORY_INSTANCE.reset()
        return {"message": "All memories reset"}
    except Exception as e:
        logging.exception("Error in reset_memory:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", summary="Redirect to docs")
def home():
    """Redirect to the OpenAPI documentation."""
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("INMEMORY_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("INMEMORY_SERVER_PORT", "8081"))
    
    logging.info("Starting InMemory Server...")
    logging.info(f"API available at: http://{host}:{port}/")
    logging.info(f"Documentation: http://{host}:{port}/docs")
    
    uvicorn.run(app, host=host, port=port, log_level="info")
