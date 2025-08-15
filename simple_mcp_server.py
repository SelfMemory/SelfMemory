import logging
import os
from typing import Annotated
from dotenv import load_dotenv
import asyncio
import json

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.types import Scope, Receive, Send
import uvicorn
import argparse

from add_memory_to_collection import add_memory_enhanced
from src.search.enhanced_search_engine import EnhancedSearchEngine
from mongodb_user_manager import initialize_mongo_user_manager, get_mongo_user_manager
from pydantic import BaseModel, Field

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

# FastAPI app for HTTP endpoints
api = FastAPI(title="InMemory MCP API", version="1.0.0", description="Memory Management MCP HTTP API")

# Add CORS middleware for dashboard integration
api.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local dashboard
        "https://inmemory.cpluz.com",  # Production dashboard
        "*"  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variable to store current user context for MCP tools
_current_user_id = None

def get_current_user_id() -> str:
    """Get the current user ID from context."""
    if _current_user_id is None:
        raise ValueError("No user context available")
    return _current_user_id

def set_current_user_id(user_id: str) -> None:
    """Set the current user ID in context."""
    global _current_user_id
    _current_user_id = user_id

# Authentication dependency
def authenticate_api_key(authorization: str = Header(None)) -> str:
    """
    Authenticate API key and return user_id.
    
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
    
    return user_id

# Pydantic models for MCP tools
class AddMemoryRequest(BaseModel):
    memory_content: str
    tags: str = ""
    people_mentioned: str = ""
    topic_category: str = ""

class SearchMemoriesRequest(BaseModel):
    query: str
    limit: int = 5
    tags: str = ""
    people_mentioned: str = ""
    topic_category: str = ""
    temporal_filter: str = ""

# MCP Tools as HTTP endpoints for Claude Desktop
@api.post("/v1/tools/add_memory")
async def add_memory_tool(
    request: AddMemoryRequest,
    user_id: str = Depends(authenticate_api_key)
) -> dict:
    """Add memory tool for MCP."""
    try:
        set_current_user_id(user_id)
        result = add_memory_enhanced(
            memory_content=request.memory_content,
            user_id=user_id,
            tags=request.tags,
            people_mentioned=request.people_mentioned,
            topic_category=request.topic_category,
        )
        return {"result": result}
    except Exception as e:
        logger.error(f"Failed to add memory via MCP tool: {str(e)}")
        return {"result": f"❌ Error: Failed to add memory - {str(e)}"}

@api.post("/v1/tools/search_memories")
async def search_memories_tool(
    request: SearchMemoriesRequest,
    user_id: str = Depends(authenticate_api_key)
) -> dict:
    """Search memories tool for MCP."""
    try:
        set_current_user_id(user_id)
        # Parse comma-separated filters
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

        if not results:
            return {"result": "🔍 No memories found matching your search criteria."}

        # Format results
        formatted_results = [f"🧠 Found {len(results)} memories:\n"]
        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")
            if result.get("tags"):
                formatted_results.append(f"   🏷️ Tags: {', '.join(result['tags'])}")

        return {"result": "\n".join(formatted_results)}
    except Exception as e:
        logger.error(f"Failed to search memories via MCP tool: {str(e)}")
        return {"result": f"❌ Error: Search failed - {str(e)}"}

@api.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "InMemory MCP Server API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/v1/health",
            "tools": "/v1/tools/"
        }
    }

@api.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "InMemory MCP Server",
        "version": "1.0.0"
    }

# Simple MCP protocol handler
async def handle_mcp_request(scope: Scope, receive: Receive, send: Send):
    """Handle MCP protocol requests."""
    # Get Authorization header for API key authentication
    headers = dict(scope.get("headers", []))
    auth_header = headers.get(b"authorization", b"").decode()
    
    if not auth_header.startswith("Bearer "):
        response = PlainTextResponse("Unauthorized: Bearer token required", status_code=401)
        await response(scope, receive, send)
        return
    
    api_key = auth_header.replace("Bearer ", "")
    user_manager = get_mongo_user_manager()
    user_id = user_manager.validate_api_key(api_key)
    
    if not user_id:
        response = PlainTextResponse("Unauthorized: Invalid API key", status_code=401)
        await response(scope, receive, send)
        return
    
    logger.info(f"MCP connection established for user: {user_id}")
    set_current_user_id(user_id)
    
    # Handle the MCP initialization
    mcp_response = {
        "jsonrpc": "2.0",
        "result": {
            "protocolVersion": "2025-06-18",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "InMemory",
                "version": "1.0.0"
            }
        }
    }
    
    response_body = json.dumps(mcp_response).encode()
    
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-type', b'application/json'],
            [b'content-length', str(len(response_body)).encode()],
        ]
    })
    
    await send({
        'type': 'http.response.body',
        'body': response_body,
    })

def create_app(*, debug: bool = False) -> Starlette:
    """Create a Starlette application that serves both MCP and FastAPI HTTP endpoints."""
    return Starlette(
        debug=debug,
        routes=[
            Mount("/api", api),  # FastAPI routes
            Route("/", endpoint=handle_mcp_request),  # Simple MCP endpoint
        ],
    )

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run Simple MCP Memory Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on (default: 8080)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    logger.info("Starting Simple MCP Memory Server...")
    logger.info(f"Server will be available at:")
    logger.info(f"  MCP: http://{args.host}:{args.port}/")
    logger.info(f"  HTTP API: http://{args.host}:{args.port}/api/v1/")
    logger.info(f"  Health Check: http://{args.host}:{args.port}/api/v1/health")
    
    # Create app
    app = create_app(debug=args.debug)

    # Run the server
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
