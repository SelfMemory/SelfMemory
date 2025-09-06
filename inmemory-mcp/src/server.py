"""
Simple InMemory MCP Server - HTTP API Version

A clean, easy-to-understand MCP server that provides both HTTP API endpoints
and MCP protocol support for memory management.

Features:
- Add memories with metadata (tags, people, topics)
- Search memories with various filters
- Simple authentication with API keys
- Both HTTP REST API and MCP protocol support
"""

import logging
import os
from typing import List
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
import uvicorn
import argparse

# Use the existing inmemory client for all operations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from inmemory.client import InmemoryClient
from pydantic import BaseModel

# Setup simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Simple user validation using InmemoryClient
def validate_api_key_simple(api_key: str) -> str:
    """Validate API key using InmemoryClient"""
    try:
        client = InmemoryClient(api_key=api_key)
        user_info = client.user_info
        client.close()
        user_id = user_info.get("user_id")
        return user_id if user_id else None
    except Exception as e:
        logger.error(f"API key validation failed: {e}")
        return None

# Create FastAPI app
api = FastAPI(
    title="InMemory MCP API", 
    version="1.0.0", 
    description="Simple Memory Management API"
)

# Add CORS for web dashboard
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Current user context
current_user_id = None

def set_current_user(user_id: str):
    """Set current user ID"""
    global current_user_id
    current_user_id = user_id

def get_current_user() -> str:
    """Get current user ID"""
    if not current_user_id:
        raise ValueError("No user logged in")
    return current_user_id

def authenticate_user(authorization: str = Header(None)) -> str:
    """
    Simple authentication - check API key and return user_id
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Use: Bearer <api_key>")
    
    api_key = authorization.replace("Bearer ", "")
    user_id = validate_api_key_simple(api_key)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return user_id

# Simple request models
class AddMemoryRequest(BaseModel):
    memory_content: str
    tags: str = ""
    people_mentioned: str = ""
    topic_category: str = ""

class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    tags: str = ""
    people_mentioned: str = ""
    topic_category: str = ""

class DeleteRequest(BaseModel):
    memory_id: str

# HTTP API Endpoints
@api.get("/")
async def root():
    """API information"""
    return {
        "service": "InMemory MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "add_memory": "POST /v1/tools/add_memory",
            "search_memories": "POST /v1/tools/search_memories", 
            "delete_memory": "POST /v1/tools/delete_memory",
            "health": "GET /v1/health"
        }
    }

@api.get("/v1/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "service": "InMemory MCP Server"}

@api.post("/v1/tools/add_memory")
async def add_memory_endpoint(
    request: AddMemoryRequest,
    user_id: str = Depends(authenticate_user)
) -> dict:
    """Add a new memory"""
    try:
        set_current_user(user_id)
        
        # Use InmemoryClient to add memory
        client = InmemoryClient(api_key=request.headers.get("authorization", "").replace("Bearer ", ""))
        result = client.add(
            memory_content=request.memory_content,
            tags=request.tags if request.tags.strip() else None,
            people_mentioned=request.people_mentioned if request.people_mentioned.strip() else None,
            topic_category=request.topic_category if request.topic_category.strip() else None,
        )
        client.close()
        
        if result.get("success", True):
            memory_id = result.get("memory_id", "unknown")
            return {"result": f"✅ Memory saved! ID: {memory_id}"}
        else:
            return {"result": f"❌ Failed to save: {result.get('error', 'Unknown error')}"}
            
    except Exception as e:
        logger.error(f"Error adding memory: {e}")
        return {"result": f"❌ Error: {str(e)}"}

@api.post("/v1/tools/search_memories")
async def search_memories_endpoint(
    request: SearchRequest,
    user_id: str = Depends(authenticate_user)
) -> dict:
    """Search memories"""
    try:
        set_current_user(user_id)
        
        # Parse filters
        tag_list = [t.strip() for t in request.tags.split(",") if t.strip()] if request.tags else None
        people_list = [p.strip() for p in request.people_mentioned.split(",") if p.strip()] if request.people_mentioned else None
        category = request.topic_category.strip() if request.topic_category else None

        # Use InmemoryClient to search
        client = InmemoryClient(api_key=request.headers.get("authorization", "").replace("Bearer ", ""))
        result = client.search(
            query=request.query,
            limit=request.limit,
            tags=tag_list,
            people_mentioned=people_list,
            topic_category=category,
        )
        client.close()
        
        memories = result.get("results", [])
        if not memories:
            return {"result": "🔍 No memories found"}

        # Format results simply
        formatted_results = [f"🧠 Found {len(memories)} memories:\n"]
        
        for i, memory in enumerate(memories, 1):
            content = memory.get("memory_content", "")
            score = memory.get("score", 0)
            
            formatted_results.append(f"{i}. {content}")
            
            # Add metadata
            metadata = []
            if memory.get("tags"):
                metadata.append(f"Tags: {memory['tags']}")
            if memory.get("people_mentioned"):
                metadata.append(f"People: {memory['people_mentioned']}")
            if memory.get("topic_category"):
                metadata.append(f"Topic: {memory['topic_category']}")
            
            if metadata:
                formatted_results.append(f"   📊 {' | '.join(metadata)}")
            
            if score:
                formatted_results.append(f"   🎯 Score: {score:.3f}")
            
            formatted_results.append("")  # Empty line

        return {"result": "\n".join(formatted_results)}
        
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        return {"result": f"❌ Error: {str(e)}"}

@api.post("/v1/tools/delete_memory")
async def delete_memory_endpoint(
    request: DeleteRequest,
    user_id: str = Depends(authenticate_user)
) -> dict:
    """Delete a memory"""
    try:
        set_current_user(user_id)
        
        if not request.memory_id.strip():
            return {"result": "❌ Memory ID required"}
        
        # For now, return a placeholder since delete functionality needs to be implemented
        return {"result": f"⚠️ Delete functionality not yet implemented for ID: {request.memory_id}"}
            
    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        return {"result": f"❌ Error: {str(e)}"}

# MCP Protocol Support
MCP_TOOLS = [
    {
        "name": "add_memory",
        "description": "Store a new memory with optional metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_content": {"type": "string", "description": "The memory text"},
                "tags": {"type": "string", "description": "Comma-separated tags", "default": ""},
                "people_mentioned": {"type": "string", "description": "Comma-separated names", "default": ""},
                "topic_category": {"type": "string", "description": "Topic category", "default": ""}
            },
            "required": ["memory_content"]
        }
    },
    {
        "name": "search_memories",
        "description": "Search through stored memories",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 5},
                "tags": {"type": "string", "description": "Filter by tags", "default": ""},
                "people_mentioned": {"type": "string", "description": "Filter by people", "default": ""},
                "topic_category": {"type": "string", "description": "Filter by topic", "default": ""}
            },
            "required": ["query"]
        }
    },
    {
        "name": "delete_memory",
        "description": "Delete a memory by ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "Memory ID to delete"}
            },
            "required": ["memory_id"]
        }
    }
]

async def execute_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Execute MCP tool and return result"""
    try:
        if tool_name == "add_memory":
            # Use InmemoryClient for adding memory
            client = InmemoryClient(api_key="dummy")  # This will be set properly in context
            result = client.add(
                memory_content=arguments.get("memory_content", ""),
                tags=arguments.get("tags", "") if arguments.get("tags", "").strip() else None,
                people_mentioned=arguments.get("people_mentioned", "") if arguments.get("people_mentioned", "").strip() else None,
                topic_category=arguments.get("topic_category", "") if arguments.get("topic_category", "").strip() else None,
            )
            client.close()
            
            if result.get("success", True):
                return f"✅ Memory saved! ID: {result.get('memory_id', 'unknown')}"
            else:
                return f"❌ Failed to save: {result.get('error', 'Unknown error')}"
            
        elif tool_name == "search_memories":
            # Parse filters
            tag_list = [t.strip() for t in arguments.get("tags", "").split(",") if t.strip()] or None
            people_list = [p.strip() for p in arguments.get("people_mentioned", "").split(",") if p.strip()] or None
            category = arguments.get("topic_category", "").strip() or None

            # Use InmemoryClient for searching
            client = InmemoryClient(api_key="dummy")  # This will be set properly in context
            result = client.search(
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 5),
                tags=tag_list,
                people_mentioned=people_list,
                topic_category=category,
            )
            client.close()
            
            memories = result.get("results", [])
            if not memories:
                return "🔍 No memories found"

            # Simple formatting
            formatted = [f"🧠 Found {len(memories)} memories:\n"]
            for i, memory in enumerate(memories, 1):
                content = memory.get("memory_content", "")
                score = memory.get("score", 0)
                formatted.append(f"{i}. {content}")
                if score:
                    formatted.append(f"   🎯 Score: {score:.3f}")
                formatted.append("")
            return "\n".join(formatted)
            
        elif tool_name == "delete_memory":
            memory_id = arguments.get("memory_id", "").strip()
            if not memory_id:
                return "❌ Memory ID required"
                
            # Placeholder for delete functionality
            return f"⚠️ Delete functionality not yet implemented for ID: {memory_id}"
                
        else:
            return f"❌ Unknown tool: {tool_name}"
            
    except Exception as e:
        logger.error(f"MCP tool error: {e}")
        return f"❌ Error: {str(e)}"

async def handle_mcp_request(request: Request):
    """Handle MCP protocol requests"""
    # Authentication
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"error": "Bearer token required"}, status_code=401)
    
    api_key = auth_header.replace("Bearer ", "")
    user_id = validate_api_key_simple(api_key)
    
    if not user_id:
        return JSONResponse({"error": "Invalid API key"}, status_code=401)
    
    set_current_user(user_id)
    
    # Parse MCP message
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        msg_id = body.get("id")
        
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": True}},
                    "serverInfo": {"name": "InMemory", "version": "1.0.0"}
                }
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": MCP_TOOLS}
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            result = await execute_mcp_tool(tool_name, arguments)
            
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": result}]
                }
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"}
            }
            
        return JSONResponse(response)
        
    except Exception as e:
        logger.error(f"MCP error: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": body.get("id") if 'body' in locals() else None,
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
        }, status_code=500)

async def handle_mcp_info(request: Request):
    """Handle MCP info requests (GET)"""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"error": "Bearer token required"}, status_code=401)
    
    api_key = auth_header.replace("Bearer ", "")
    user_id = validate_api_key_simple(api_key)
    
    if not user_id:
        return JSONResponse({"error": "Invalid API key"}, status_code=401)
    
    return JSONResponse({
        "jsonrpc": "2.0",
        "result": {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {"listChanged": True}},
            "serverInfo": {"name": "InMemory", "version": "1.0.0"},
            "tools": MCP_TOOLS
        }
    })

def create_app(debug: bool = False) -> Starlette:
    """Create the main Starlette app"""
    return Starlette(
        debug=debug,
        routes=[
            Mount("/api", api),  # HTTP API routes
            Route("/", endpoint=handle_mcp_request, methods=["POST"]),  # MCP protocol
            Route("/", endpoint=handle_mcp_info, methods=["GET"]),  # MCP info
        ],
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Simple InMemory MCP Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port (default: 8080)')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()

    logger.info("🚀 Starting Simple InMemory MCP Server...")
    logger.info(f"📍 MCP Protocol: http://{args.host}:{args.port}/")
    logger.info(f"🌐 HTTP API: http://{args.host}:{args.port}/api/v1/")
    logger.info(f"🏥 Health Check: http://{args.host}:{args.port}/api/v1/health")
    logger.info("🛠️  Tools: add_memory, search_memories, delete_memory")
    
    app = create_app(debug=args.debug)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
