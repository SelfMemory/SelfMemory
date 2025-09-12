#!/usr/bin/env python3
"""
InMemory Core API Server
A simple REST API server that provides the endpoints expected by the dashboard.
Runs on port 8081 and provides /api/memories endpoints.
"""

import hashlib
import logging
import os
import sys
from datetime import datetime
from typing import Any

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# MongoDB connection (same as dashboard)
MONGODB_URI = os.getenv("MONGODB_URI")
mongo_client = MongoClient(MONGODB_URI)
mongo_db = mongo_client.get_database()

# Use the existing inmemory client
from inmemory.client import InmemoryClient

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SelfMemory API",
    version="1.0.0",
    description="Core Memory Management API for Dashboard",
)

# Add CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def authenticate_user(authorization: str = Header(None)) -> tuple[str, str]:
    """Database-based API key authentication - looks up real user ID from MongoDB."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")

    api_key = authorization.replace("Bearer ", "")

    # Accept both formats: sk_im_ and inmem_sk_
    if not (api_key.startswith("sk_im_") or api_key.startswith("inmem_sk_")):
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
                logger.info(
                    f"🔄 Migrating old API key format to keyHash for key: {api_key[:12]}..."
                )
                mongo_db.api_keys.update_one(
                    {"_id": stored_key["_id"]},
                    {"$set": {"keyHash": key_hash}, "$unset": {"api_key": ""}},
                )
                stored_key["keyHash"] = key_hash  # Update local copy

        if not stored_key:
            logger.warning(f"❌ Invalid API key attempted: {api_key[:12]}...")
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Check if key is expired
        if stored_key.get("expiresAt") and stored_key["expiresAt"] < datetime.now():
            logger.warning(
                f"❌ Expired API key attempted: {stored_key.get('keyPrefix', 'unknown')}"
            )
            raise HTTPException(status_code=401, detail="API key expired")

        # Get user to verify it's active
        user = mongo_db.users.find_one({"_id": stored_key["userId"]})

        if not user or not user.get("isActive", True):
            logger.warning(
                f"❌ API key belongs to inactive user: {stored_key['userId']}"
            )
            raise HTTPException(status_code=401, detail="User account inactive")

        # Update last used timestamp
        mongo_db.api_keys.update_one(
            {"_id": stored_key["_id"]}, {"$set": {"lastUsed": datetime.now()}}
        )

        # Return the real user ID (as string) and API key
        user_id = str(stored_key["userId"])
        logger.info(f"✅ API key authenticated for user {user.get('email', user_id)}")
        return user_id, api_key

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API key authentication error: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")


# Request models
class MemoryCreateRequest(BaseModel):
    messages: list[dict[str, str]]
    user_id: str
    metadata: dict[str, Any] = {}


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 20
    user_id: str


# GET /api/memories - List memories
@app.get("/api/memories")
async def get_memories(
    limit: int = 100, offset: int = 0, auth_data: tuple = Depends(authenticate_user)
):
    """Get memories for authenticated user"""
    user_id, api_key = auth_data

    try:
        logger.info(f"Getting memories for user {user_id}")

        # Use InmemoryClient to search/get all memories
        client = InmemoryClient(api_key=api_key)

        # Search with empty query to get all memories
        result = client.search(query="", limit=limit)
        client.close()

        memories = result.get("results", [])

        # Transform memories to match dashboard format
        formatted_memories = []
        for memory in memories:
            formatted_memory = {
                "id": memory.get("id", memory.get("memory_id", "")),
                "content": memory.get("memory_content", memory.get("content", "")),
                "metadata": {
                    "tags": ",".join(memory.get("tags", []))
                    if isinstance(memory.get("tags"), list)
                    else memory.get("tags", ""),
                    "people_mentioned": ",".join(memory.get("people_mentioned", []))
                    if isinstance(memory.get("people_mentioned"), list)
                    else memory.get("people_mentioned", ""),
                    "topic_category": memory.get("topic_category", ""),
                    "created_at": memory.get("created_at", datetime.now().isoformat()),
                    "updated_at": memory.get("updated_at", datetime.now().isoformat()),
                },
                "created_at": memory.get("created_at", datetime.now().isoformat()),
                "updated_at": memory.get("updated_at", datetime.now().isoformat()),
            }
            formatted_memories.append(formatted_memory)

        logger.info(f"Retrieved {len(formatted_memories)} memories for user {user_id}")

        return {"results": formatted_memories}

    except Exception as e:
        logger.error(f"Error getting memories: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# POST /api/memories/search - Search memories
@app.post("/api/memories/search")
async def search_memories(
    request: MemorySearchRequest, auth_data: tuple = Depends(authenticate_user)
):
    """Search memories for authenticated user"""
    user_id, api_key = auth_data

    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Search query is required")

        logger.info(f"Searching memories for user {user_id}: '{request.query}'")

        # Use InmemoryClient to search memories
        client = InmemoryClient(api_key=api_key)

        result = client.search(query=request.query, limit=request.limit)
        client.close()

        memories = result.get("results", [])

        # Transform memories to match dashboard format
        formatted_memories = []
        for memory in memories:
            formatted_memory = {
                "id": memory.get("id", memory.get("memory_id", "")),
                "content": memory.get("memory_content", memory.get("content", "")),
                "score": memory.get("score", 0.9),  # Include relevance score
                "metadata": {
                    "tags": ",".join(memory.get("tags", []))
                    if isinstance(memory.get("tags"), list)
                    else memory.get("tags", ""),
                    "people_mentioned": ",".join(memory.get("people_mentioned", []))
                    if isinstance(memory.get("people_mentioned"), list)
                    else memory.get("people_mentioned", ""),
                    "topic_category": memory.get("topic_category", ""),
                    "created_at": memory.get("created_at", datetime.now().isoformat()),
                    "updated_at": memory.get("updated_at", datetime.now().isoformat()),
                },
                "created_at": memory.get("created_at", datetime.now().isoformat()),
                "updated_at": memory.get("updated_at", datetime.now().isoformat()),
            }
            formatted_memories.append(formatted_memory)

        logger.info(
            f"Found {len(formatted_memories)} memories for query '{request.query}'"
        )

        return {"results": formatted_memories, "total": len(formatted_memories)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# POST /api/memories - Create memory
@app.post("/api/memories")
async def create_memory(
    request: MemoryCreateRequest, auth_data: tuple = Depends(authenticate_user)
):
    """Create a new memory"""
    user_id, api_key = auth_data

    try:
        # Extract content from messages
        memory_content = ""
        if request.messages:
            # Combine all message content
            memory_content = " ".join(
                [
                    msg.get("content", "")
                    for msg in request.messages
                    if msg.get("content")
                ]
            )

        if not memory_content.strip():
            raise HTTPException(status_code=400, detail="Memory content is required")

        logger.info(f"Creating memory for user {user_id}: {memory_content[:50]}...")

        # Use InmemoryClient to add memory
        client = InmemoryClient(api_key=api_key)

        # Extract metadata
        metadata = request.metadata or {}
        tags = metadata.get("tags", "")
        people_mentioned = metadata.get("people_mentioned", "")
        topic_category = metadata.get("topic_category", "")

        result = client.add(
            memory_content=memory_content,
            tags=tags if tags.strip() else None,
            people_mentioned=people_mentioned if people_mentioned.strip() else None,
            topic_category=topic_category if topic_category.strip() else None,
        )
        client.close()

        if result.get("success", True):
            memory_id = result.get("memory_id", "unknown")
            logger.info(f"Memory created successfully for user {user_id}: {memory_id}")

            return {
                "success": True,
                "memory_id": memory_id,
                "message": "Memory created successfully",
            }
        error_msg = result.get("error", "Unknown error")
        logger.error(f"Failed to create memory: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating memory: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "InMemory Core API Server",
        "version": "1.0.0",
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "InMemory Core API Server",
        "version": "1.0.0",
        "endpoints": {
            "get_memories": "GET /api/memories",
            "search_memories": "POST /api/memories/search",
            "create_memory": "POST /api/memories",
            "health": "GET /health",
        },
        "status": "running",
    }


if __name__ == "__main__":
    logger.info("🚀 Starting InMemory Core API Server...")
    logger.info("📍 Server: http://localhost:8081")
    logger.info("🌐 API: http://localhost:8081/api/memories")
    logger.info("🏥 Health: http://localhost:8081/health")

    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")
