#!/usr/bin/env python3
import logging
import os
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import argparse

# Import existing business logic (local imports)
from add_memory_to_collection import add_memory_enhanced
from src.search.enhanced_search_engine import EnhancedSearchEngine
from mongodb_user_manager import initialize_mongo_user_manager, get_mongo_user_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize MongoDB user manager
try:
    mongo_user_manager = initialize_mongo_user_manager()
    logger.info("MongoDB user manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize MongoDB user manager: {e}")
    raise

# Initialize enhanced search engine
search_engine = EnhancedSearchEngine()

# FastAPI app for Core API
app = FastAPI(
    title="InMemory Core API",
    version="1.0.0",
    description="Core Memory Management API Service"
)

# Add CORS middleware for dashboard and MCP integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local dashboard
        "http://localhost:8080",  # MCP server
        "https://inmemory.cpluz.com",  # Production dashboard
        "*"  # Allow all origins for development
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

class SearchMemoriesRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(5, description="Maximum number of results")
    tags: str = Field("", description="Filter by tags")
    people_mentioned: str = Field("", description="Filter by people")
    topic_category: str = Field("", description="Filter by topic")
    temporal_filter: str = Field("", description="Temporal filter")

class TemporalSearchRequest(BaseModel):
    temporal_query: str = Field(..., description="Temporal query")
    semantic_query: str = Field("", description="Optional semantic query")
    limit: int = Field(5, description="Maximum number of results")

class SearchByTagsRequest(BaseModel):
    tags: str = Field(..., description="Comma-separated tags")
    semantic_query: str = Field("", description="Optional semantic query")
    match_all_tags: bool = Field(False, description="Match all tags (AND) or any tag (OR)")
    limit: int = Field(5, description="Maximum number of results")

class SearchByPeopleRequest(BaseModel):
    people: str = Field(..., description="Comma-separated people names")
    semantic_query: str = Field("", description="Optional semantic query")
    limit: int = Field(5, description="Maximum number of results")

class SearchByTopicRequest(BaseModel):
    topic_category: str = Field(..., description="Topic category")
    semantic_query: str = Field("", description="Optional semantic query")
    limit: int = Field(5, description="Maximum number of results")

# Authentication dependency
def authenticate_api_key(authorization: str = Header(None)) -> str:
    """
    Authenticate API key, ensure collection exists, and return user_id.
    
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
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    api_key = authorization.replace("Bearer ", "")
    user_manager = get_mongo_user_manager()
    user_id = user_manager.validate_api_key(api_key)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    
    # Lazily ensure user collection exists on first API usage
    # This prevents 'last_used' from being updated during key creation
    try:
        from qdrant_db import ensure_user_collection_exists
        ensure_user_collection_exists(user_id)
        logger.debug(f"Ensured collection exists for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to ensure collection for user {user_id}: {e}")
        # Don't fail authentication if collection creation fails
        # The specific operation will fail later with a more appropriate error
    
    return user_id

# Core API Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "InMemory Core API Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/v1/health",
            "auth": "/v1/auth/validate",
            "memories": "/v1/memories",
            "search": "/v1/search",
            "temporal-search": "/v1/temporal-search",
            "search-by-tags": "/v1/search-by-tags",
            "search-by-people": "/v1/search-by-people",
            "search-by-topic": "/v1/search-by-topic"
        }
    }

@app.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "InMemory Core API",
        "version": "1.0.0"
    }

@app.get("/v1/auth/validate")
async def validate_auth(user_id: str = Depends(authenticate_api_key)):
    """Validate API key and return user info."""
    return {
        "valid": True,
        "user_id": user_id,
        "message": "API key is valid"
    }

# Collection creation endpoint for user setup
class EnsureCollectionRequest(BaseModel):
    user_id: str = Field(..., description="User ID to create collection for")

@app.post("/api/collections/ensure")
async def ensure_user_collection(
    request: EnsureCollectionRequest,
    authenticated_user_id: str = Depends(authenticate_api_key)
):
    """Ensure user's Qdrant collection exists."""
    try:
        # Ensure the authenticated user is creating their own collection
        if request.user_id != authenticated_user_id:
            raise HTTPException(status_code=403, detail="Cannot create collection for another user")
        
        # Import collection creation logic
        from qdrant_db import ensure_user_collection_exists
        
        collection_name = ensure_user_collection_exists(request.user_id)
        
        logger.info(f"Ensured collection exists for user {request.user_id}: {collection_name}")
        
        return {
            "success": True,
            "collection_name": collection_name,
            "user_id": request.user_id,
            "message": "Collection created successfully"
        }
    except ValueError as e:
        # User validation failed
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to ensure collection for user {request.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")

@app.post("/v1/memories")
async def add_memory_api(
    request: AddMemoryRequest,
    user_id: str = Depends(authenticate_api_key)
):
    """Add a new memory via Core API."""
    try:
        result = add_memory_enhanced(
            memory_content=request.memory_content,
            user_id=user_id,
            tags=request.tags,
            people_mentioned=request.people_mentioned,
            topic_category=request.topic_category,
        )
        
        return {
            "success": True,
            "message": "Memory added successfully",
            "result": result
        }
    except Exception as e:
        logger.error(f"Failed to add memory via Core API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add memory: {str(e)}")

@app.get("/v1/memories")
async def get_memories_api(
    limit: int = 10,
    offset: int = 0,
    user_id: str = Depends(authenticate_api_key)
):
    """Get user's memories via Core API."""
    try:
        # Use enhanced search to get recent memories
        results = search_engine.search_memories(
            query="",  # Empty query gets most recent
            user_id=user_id,
            limit=limit + offset  # Get more to handle offset
        )
        
        # Apply manual offset (since search doesn't support offset)
        paginated_results = results[offset:offset + limit] if results else []
        
        # Format response
        memories = []
        for result in paginated_results:
            memory_data = {
                "id": result.get("id", "unknown"),
                "memory_content": result.get("memory", ""),
                "memory": result.get("memory", ""),  # Both formats for compatibility
                "tags": result.get("tags", []),
                "people_mentioned": result.get("people_mentioned", []),
                "topic_category": result.get("topic_category", ""),
                "temporal_data": result.get("temporal_data", {}),
                "score": result.get("score", 0),
                "created_at": result.get("created_at", ""),
                "updated_at": result.get("updated_at", "")
            }
            memories.append(memory_data)
        
        return {
            "memories": memories,
            "total": len(results) if results else 0,
            "hasMore": len(results) > offset + limit if results else False
        }
    except Exception as e:
        logger.error(f"Failed to get memories via Core API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get memories: {str(e)}")

@app.post("/v1/search")
async def search_memories_api(
    request: SearchMemoriesRequest,
    user_id: str = Depends(authenticate_api_key)
):
    """Search memories via Core API."""
    try:
        # Parse filters
        tag_list = [tag.strip() for tag in request.tags.split(",") if tag.strip()] if request.tags else None
        people_list = [person.strip() for person in request.people_mentioned.split(",") if person.strip()] if request.people_mentioned else None
        category = request.topic_category.strip() if request.topic_category else None
        temporal = request.temporal_filter.strip() if request.temporal_filter else None
        
        results = search_engine.search_memories(
            query=request.query,
            user_id=user_id,
            limit=request.limit,
            tags=tag_list,
            people_mentioned=people_list,
            topic_category=category,
            temporal_filter=temporal,
        )
        
        # Ensure consistent format
        formatted_results = []
        for result in (results or []):
            formatted_result = {
                "id": result.get("id", "unknown"),
                "memory_content": result.get("memory", ""),
                "memory": result.get("memory", ""),  # Both formats for compatibility
                "tags": result.get("tags", []),
                "people_mentioned": result.get("people_mentioned", []),
                "topic_category": result.get("topic_category", ""),
                "temporal_data": result.get("temporal_data", {}),
                "score": result.get("score", 0)
            }
            formatted_results.append(formatted_result)
        
        return {
            "memories": formatted_results,
            "total": len(formatted_results)
        }
    except Exception as e:
        logger.error(f"Failed to search memories via Core API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}")

@app.post("/v1/temporal-search")
async def temporal_search_api(
    request: TemporalSearchRequest,
    user_id: str = Depends(authenticate_api_key)
):
    """Temporal search via Core API."""
    try:
        results = search_engine.temporal_search(
            temporal_query=request.temporal_query,
            user_id=user_id,
            semantic_query=request.semantic_query if request.semantic_query.strip() else None,
            limit=request.limit,
        )
        
        # Ensure consistent format
        formatted_results = []
        for result in (results or []):
            formatted_result = {
                "id": result.get("id", "unknown"),
                "memory_content": result.get("memory", ""),
                "memory": result.get("memory", ""),  # Both formats for compatibility
                "tags": result.get("tags", []),
                "people_mentioned": result.get("people_mentioned", []),
                "topic_category": result.get("topic_category", ""),
                "temporal_data": result.get("temporal_data", {}),
                "score": result.get("score", 0)
            }
            formatted_results.append(formatted_result)
        
        return {
            "memories": formatted_results,
            "total": len(formatted_results)
        }
    except Exception as e:
        logger.error(f"Failed temporal search via Core API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Temporal search failed: {str(e)}")

@app.post("/v1/search-by-tags")
async def search_by_tags_api(
    request: SearchByTagsRequest,
    user_id: str = Depends(authenticate_api_key)
):
    """Search by tags via Core API."""
    try:
        tag_list = [tag.strip() for tag in request.tags.split(",") if tag.strip()]
        if not tag_list:
            raise HTTPException(status_code=400, detail="Please provide at least one tag to search for")

        results = search_engine.tag_search(
            tags=tag_list,
            user_id=user_id,
            semantic_query=request.semantic_query if request.semantic_query.strip() else None,
            match_all_tags=request.match_all_tags,
            limit=request.limit,
        )
        
        # Ensure consistent format
        formatted_results = []
        for result in (results or []):
            formatted_result = {
                "id": result.get("id", "unknown"),
                "memory_content": result.get("memory", ""),
                "memory": result.get("memory", ""),  # Both formats for compatibility
                "tags": result.get("tags", []),
                "people_mentioned": result.get("people_mentioned", []),
                "topic_category": result.get("topic_category", ""),
                "temporal_data": result.get("temporal_data", {}),
                "score": result.get("score", 0)
            }
            formatted_results.append(formatted_result)
        
        return {
            "memories": formatted_results,
            "total": len(formatted_results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed tag search via Core API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Tag search failed: {str(e)}")

@app.post("/v1/search-by-people")
async def search_by_people_api(
    request: SearchByPeopleRequest,
    user_id: str = Depends(authenticate_api_key)
):
    """Search by people via Core API."""
    try:
        people_list = [person.strip() for person in request.people.split(",") if person.strip()]
        if not people_list:
            raise HTTPException(status_code=400, detail="Please provide at least one person's name to search for")

        results = search_engine.people_search(
            people=people_list,
            user_id=user_id,
            semantic_query=request.semantic_query if request.semantic_query.strip() else None,
            limit=request.limit,
        )
        
        # Ensure consistent format
        formatted_results = []
        for result in (results or []):
            formatted_result = {
                "id": result.get("id", "unknown"),
                "memory_content": result.get("memory", ""),
                "memory": result.get("memory", ""),  # Both formats for compatibility
                "tags": result.get("tags", []),
                "people_mentioned": result.get("people_mentioned", []),
                "topic_category": result.get("topic_category", ""),
                "temporal_data": result.get("temporal_data", {}),
                "score": result.get("score", 0)
            }
            formatted_results.append(formatted_result)
        
        return {
            "memories": formatted_results,
            "total": len(formatted_results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed people search via Core API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"People search failed: {str(e)}")

@app.post("/v1/search-by-topic")
async def search_by_topic_api(
    request: SearchByTopicRequest,
    user_id: str = Depends(authenticate_api_key)
):
    """Search by topic via Core API."""
    try:
        if not request.topic_category.strip():
            raise HTTPException(status_code=400, detail="Please provide a topic category to search for")

        results = search_engine.topic_search(
            topic_category=request.topic_category.strip(),
            user_id=user_id,
            semantic_query=request.semantic_query if request.semantic_query.strip() else None,
            limit=request.limit,
        )
        
        # Ensure consistent format
        formatted_results = []
        for result in (results or []):
            formatted_result = {
                "id": result.get("id", "unknown"),
                "memory_content": result.get("memory", ""),
                "memory": result.get("memory", ""),  # Both formats for compatibility
                "tags": result.get("tags", []),
                "people_mentioned": result.get("people_mentioned", []),
                "topic_category": result.get("topic_category", ""),
                "temporal_data": result.get("temporal_data", {}),
                "score": result.get("score", 0)
            }
            formatted_results.append(formatted_result)
        
        return {
            "memories": formatted_results,
            "total": len(formatted_results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed topic search via Core API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Topic search failed: {str(e)}")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Core Memory API Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8081, help='Port to listen on (default: 8081)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    logger.info("Starting InMemory Core API Service...")
    logger.info(f"API will be available at: http://{args.host}:{args.port}/")
    logger.info(f"Health check: http://{args.host}:{args.port}/v1/health")
    logger.info(f"Documentation: http://{args.host}:{args.port}/docs")

    # Run the server
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
