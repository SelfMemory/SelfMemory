#!/usr/bin/env python3
"""
Simple InMemory MCP Server

A straightforward MCP server that provides memory storage and search for AI assistants.
Uses FastMCP with Starlette for easy setup and deployment.

Main features:
- Store memories with tags and metadata
- Search memories by content, tags, people, or topics
- Simple authentication with API keys
"""

import logging
import os
import sys
from typing import List
import uvicorn
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from pydantic import Field

# Add parent directory to import inmemory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from inmemory.client import InmemoryClient
except ImportError as e:
    logging.error(f"Cannot import InmemoryClient: {e}")
    sys.exit(1)

# Setup simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("InMemory")

# Store current user info
current_user = {"user_id": None, "api_key": None}

def set_user_context(user_id: str, api_key: str):
    """Set the current user context"""
    current_user["user_id"] = user_id
    current_user["api_key"] = api_key

def get_user_context():
    """Get current user context"""
    if not current_user["user_id"]:
        raise ValueError("No user logged in")
    return current_user["user_id"], current_user["api_key"]

def validate_api_key(api_key: str) -> str:
    """Check if API key is valid and return user_id"""
    try:
        client = InmemoryClient(api_key=api_key)
        user_info = client.user_info
        client.close()
        
        user_id = user_info.get("user_id")
        if user_id:
            logger.info(f"Valid API key for user: {user_id}")
            return user_id
        return None
    except Exception as e:
        logger.error(f"Invalid API key: {e}")
        return None

@mcp.tool()
async def add_memory(
    text: str = Field(..., description="The memory text to store"),
    tags: str = Field("", description="Tags separated by commas (optional)"),
    people_mentioned: str = Field("", description="People mentioned, separated by commas (optional)"),
    topic_category: str = Field("", description="Topic or category (optional)"),
) -> List[TextContent]:
    """
    Store a new memory. Use this when the user shares information that should be remembered.
    
    Example: add_memory("I love pizza", "food,preferences", "John", "food")
    """
    try:
        user_id, api_key = get_user_context()
        
        # Create client and add memory
        client = InmemoryClient(api_key=api_key)
        result = client.add(
            memory_content=text,
            tags=tags.strip() if tags.strip() else None,
            people_mentioned=people_mentioned.strip() if people_mentioned.strip() else None,
            topic_category=topic_category.strip() if topic_category.strip() else None
        )
        client.close()
        
        # Format response
        if result.get("success", True):
            memory_id = result.get("memory_id", "unknown")
            response = f"✅ Memory saved!\n\nID: {memory_id}\nContent: {text[:100]}..."
        else:
            response = f"❌ Failed to save: {result.get('error', 'Unknown error')}"
            
        return [TextContent(type="text", text=response)]
        
    except Exception as e:
        logger.error(f"Error adding memory: {e}")
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

@mcp.tool()
async def search_memory(
    query: str = Field(..., description="What to search for"),
    limit: int = Field(5, description="How many results to return (max 10)"),
    tags: str = Field("", description="Filter by tags (optional)"),
    people_mentioned: str = Field("", description="Filter by people (optional)"),
    topic_category: str = Field("", description="Filter by topic (optional)"),
) -> List[TextContent]:
    """
    Search through stored memories to find relevant information.
    
    Example: search_memory("pizza preferences", 3, "food", "John")
    """
    try:
        user_id, api_key = get_user_context()
        
        # Create client and search
        client = InmemoryClient(api_key=api_key)
        
        # Parse filters
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        people_list = [p.strip() for p in people_mentioned.split(",") if p.strip()] if people_mentioned else None
        category = topic_category.strip() if topic_category else None
        
        result = client.search(
            query=query,
            limit=min(limit or 5, 10),  # Cap at 10 results
            tags=tag_list,
            people_mentioned=people_list,
            topic_category=category
        )
        client.close()
        
        memories = result.get("results", [])
        
        if not memories:
            return [TextContent(type="text", text=f"🔍 No memories found for: '{query}'")]
        
        # Format results simply
        response_lines = [f"🔍 Found {len(memories)} memories for '{query}':\n"]
        
        for i, memory in enumerate(memories, 1):
            # Try different possible field names for content
            content = (memory.get("memory_content") or 
                     memory.get("content") or 
                     memory.get("text") or 
                     memory.get("message", ""))
            
            score = memory.get("score", 0)
            created_at = memory.get("created_at", "")
            
            # Debug: log the memory structure to understand what fields are available
            logger.info(f"FastMCP Memory structure: {list(memory.keys())}")
            
            if content:
                response_lines.append(f"{i}. {content}")
            else:
                response_lines.append(f"{i}. [Content not found - available fields: {list(memory.keys())}]")
            
            response_lines.append(f"   📅 {created_at} | Score: {score:.2f}")
            
            # Add metadata if available
            if memory.get("tags"):
                response_lines.append(f"   🏷️ {memory['tags']}")
            if memory.get("people_mentioned"):
                response_lines.append(f"   👥 {memory['people_mentioned']}")
            
            response_lines.append("")  # Empty line between results
        
        return [TextContent(type="text", text="\n".join(response_lines))]
        
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def health_check(request: Request):
    """Simple health check"""
    return JSONResponse({
        "status": "healthy",
        "service": "InMemory MCP Server",
        "tools": ["add_memory", "search_memory"]
    })

async def memories_endpoint(request: Request):
    """Handle memories endpoint for MCP client compatibility"""
    # Check for API key in Authorization header
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        from starlette.responses import Response
        return Response("Need Authorization: Bearer <api_key>", status_code=401)
    
    api_key = auth_header.replace("Bearer ", "").strip()
    user_id = validate_api_key(api_key)
    
    if not user_id:
        from starlette.responses import Response
        return Response("Invalid API key", status_code=401)
    
    # Return basic memory info for MCP client
    return JSONResponse({
        "status": "ok",
        "service": "InMemory MCP Server",
        "user_id": user_id,
        "available_tools": ["add_memory", "search_memory"]
    })

async def handle_sse_connection(scope, receive, send):
    """Handle MCP connections via Server-Sent Events"""
    request = Request(scope, receive)
    
    # Check for API key in Authorization header
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        from starlette.responses import Response
        response = Response("Need Authorization: Bearer <api_key>", status_code=401)
        await response(scope, receive, send)
        return
    
    api_key = auth_header.replace("Bearer ", "").strip()
    user_id = validate_api_key(api_key)
    
    if not user_id:
        from starlette.responses import Response
        response = Response("Invalid API key", status_code=401)
        await response(scope, receive, send)
        return
    
    logger.info(f"MCP connection established for user: {user_id}")
    set_user_context(user_id, api_key)
    
    # Use the MCP SSE transport directly
    sse_transport = SseServerTransport("/messages/")
    
    # Handle the MCP connection
    async with sse_transport.connect_sse(scope, receive, send) as (read_stream, write_stream):
        init_options = {}
        if hasattr(mcp._mcp_server, 'create_initialization_options'):
            init_options = mcp._mcp_server.create_initialization_options()
        
        await mcp._mcp_server.run(read_stream, write_stream, init_options)

async def sse_endpoint(request: Request):
    """SSE endpoint that handles MCP connections"""
    # Check for API key in Authorization header
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        from starlette.responses import Response
        return Response("Need Authorization: Bearer <api_key>", status_code=401)
    
    api_key = auth_header.replace("Bearer ", "").strip()
    user_id = validate_api_key(api_key)
    
    if not user_id:
        from starlette.responses import Response
        return Response("Invalid API key", status_code=401)
    
    logger.info(f"MCP connection established for user: {user_id}")
    set_user_context(user_id, api_key)
    
    # Handle POST requests for message sending
    if request.method == "POST":
        try:
            # Read the message body
            body = await request.body()
            message_text = body.decode()
            logger.info(f"Received MCP message: {message_text}")
            
            # Parse the JSON-RPC message
            import json
            try:
                message = json.loads(message_text)
                message_id = message.get("id")
                method = message.get("method")
                
                # Handle different MCP methods
                if method == "initialize":
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {
                                "tools": {"listChanged": True},
                                "resources": {"subscribe": True, "listChanged": True},
                                "prompts": {"listChanged": True},
                                "logging": {}
                            },
                            "serverInfo": {
                                "name": "InMemory MCP Server",
                                "version": "1.0.0"
                            }
                        }
                    })
                elif method == "tools/list":
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "result": {
                            "tools": [
                                {
                                    "name": "add_memory",
                                    "description": "Store a new memory with optional tags, people mentioned, and topic category",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "text": {"type": "string", "description": "The memory text to store"},
                                            "tags": {"type": "string", "description": "Tags separated by commas (optional)"},
                                            "people_mentioned": {"type": "string", "description": "People mentioned, separated by commas (optional)"},
                                            "topic_category": {"type": "string", "description": "Topic or category (optional)"}
                                        },
                                        "required": ["text"]
                                    }
                                },
                                {
                                    "name": "search_memory",
                                    "description": "Search through stored memories to find relevant information",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "query": {"type": "string", "description": "What to search for"},
                                            "limit": {"type": "number", "description": "How many results to return (max 10)", "default": 5},
                                            "tags": {"type": "string", "description": "Filter by tags (optional)"},
                                            "people_mentioned": {"type": "string", "description": "Filter by people (optional)"},
                                            "topic_category": {"type": "string", "description": "Filter by topic (optional)"}
                                        },
                                        "required": ["query"]
                                    }
                                }
                            ]
                        }
                    })
                elif method == "tools/call":
                    # Handle tool execution
                    params = message.get("params", {})
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})
                    
                    try:
                        if tool_name == "add_memory":
                            # Execute add_memory tool
                            text = arguments.get("text", "")
                            tags = arguments.get("tags", "")
                            people_mentioned = arguments.get("people_mentioned", "")
                            topic_category = arguments.get("topic_category", "")
                            
                            # Create client and add memory using correct mem0-style format
                            client = InmemoryClient(api_key=api_key)
                            
                            # Convert to mem0-style messages format
                            messages = [{"role": "user", "content": text}]
                            metadata = {
                                "tags": tags.strip() if tags.strip() else "",
                                "people_mentioned": people_mentioned.strip() if people_mentioned.strip() else "",
                                "topic_category": topic_category.strip() if topic_category.strip() else ""
                            }
                            
                            # Make direct API call with correct format
                            try:
                                payload = {
                                    "messages": messages,
                                    "metadata": metadata
                                }
                                response = client.client.post("/api/memories", json=payload)
                                response.raise_for_status()
                                result = response.json()
                            except Exception as e:
                                result = {"success": False, "error": str(e)}
                            finally:
                                client.close()
                            
                            # Format response
                            if result.get("success", True):
                                memory_id = result.get("memory_id", "unknown")
                                response_text = f"✅ Memory saved!\n\nID: {memory_id}\nContent: {text[:100]}..."
                            else:
                                response_text = f"❌ Failed to save: {result.get('error', 'Unknown error')}"
                            
                            return JSONResponse({
                                "jsonrpc": "2.0",
                                "id": message_id,
                                "result": {
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": response_text
                                        }
                                    ]
                                }
                            })
                            
                        elif tool_name == "search_memory":
                            # Execute search_memory tool
                            query = arguments.get("query", "")
                            limit = arguments.get("limit", 5)
                            tags = arguments.get("tags", "")
                            people_mentioned = arguments.get("people_mentioned", "")
                            topic_category = arguments.get("topic_category", "")
                            
                            # Create client and search using correct mem0-style format
                            client = InmemoryClient(api_key=api_key)
                            
                            # Parse filters
                            tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
                            people_list = [p.strip() for p in people_mentioned.split(",") if p.strip()] if people_mentioned else []
                            category = topic_category.strip() if topic_category else None
                            
                            # Make direct API call with correct format
                            try:
                                filters = {
                                    "limit": min(limit or 5, 10),  # Cap at 10 results
                                }
                                if tag_list:
                                    filters["tags"] = tag_list
                                if people_list:
                                    filters["people_mentioned"] = people_list
                                if category:
                                    filters["topic_category"] = category
                                
                                payload = {
                                    "query": query,
                                    "filters": filters
                                }
                                response = client.client.post("/api/memories/search", json=payload)
                                response.raise_for_status()
                                result = response.json()
                            except Exception as e:
                                result = {"results": [], "error": str(e)}
                            finally:
                                client.close()
                            
                            memories = result.get("results", [])
                            
                            if not memories:
                                response_text = f"🔍 No memories found for: '{query}'"
                            else:
                                # Format results simply
                                response_lines = [f"🔍 Found {len(memories)} memories for '{query}':\n"]
                                
                                for i, memory in enumerate(memories, 1):
                                    # Try different possible field names for content
                                    content = (memory.get("memory_content") or 
                                             memory.get("content") or 
                                             memory.get("text") or 
                                             memory.get("message", ""))
                                    
                                    score = memory.get("score", 0)
                                    created_at = memory.get("created_at", "")
                                    
                                    # Debug: log the memory structure to understand what fields are available
                                    logger.info(f"Memory structure: {list(memory.keys())}")
                                    
                                    if content:
                                        response_lines.append(f"{i}. {content}")
                                    else:
                                        response_lines.append(f"{i}. [Content not found - available fields: {list(memory.keys())}]")
                                    
                                    response_lines.append(f"   📅 {created_at} | Score: {score:.2f}")
                                    
                                    # Add metadata if available
                                    if memory.get("tags"):
                                        response_lines.append(f"   🏷️ {memory['tags']}")
                                    if memory.get("people_mentioned"):
                                        response_lines.append(f"   👥 {memory['people_mentioned']}")
                                    
                                    response_lines.append("")  # Empty line between results
                                
                                response_text = "\n".join(response_lines)
                            
                            return JSONResponse({
                                "jsonrpc": "2.0",
                                "id": message_id,
                                "result": {
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": response_text
                                        }
                                    ]
                                }
                            })
                        else:
                            return JSONResponse({
                                "jsonrpc": "2.0",
                                "id": message_id,
                                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                            })
                            
                    except Exception as tool_error:
                        logger.error(f"Error executing tool {tool_name}: {tool_error}")
                        return JSONResponse({
                            "jsonrpc": "2.0",
                            "id": message_id,
                            "error": {"code": -32603, "message": f"Tool execution error: {str(tool_error)}"}
                        })
                else:
                    # For other methods, return a proper JSON-RPC response
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "result": {"status": "received", "method": method}
                    })
                    
            except json.JSONDecodeError:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }, status_code=400)
                
        except Exception as e:
            logger.error(f"Error handling POST message: {e}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
            }, status_code=500)
    
    # Handle GET requests for SSE connection
    from sse_starlette.sse import EventSourceResponse
    
    async def event_generator():
        try:
            # Create a simple MCP session
            from mcp.server import Server
            from mcp.types import ServerCapabilities
            
            # Initialize MCP server capabilities
            server_capabilities = ServerCapabilities(
                tools={"listChanged": True},
                resources={"subscribe": True, "listChanged": True},
                prompts={"listChanged": True},
                logging={}
            )
            
            # Send initialization message
            yield {
                "event": "message",
                "data": '{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}'
            }
            
            # Keep connection alive
            import asyncio
            while True:
                await asyncio.sleep(1)
                yield {
                    "event": "ping",
                    "data": "ping"
                }
                
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
            yield {
                "event": "error", 
                "data": f"Error: {str(e)}"
            }
    
    return EventSourceResponse(event_generator())

def create_app(debug: bool = False) -> Starlette:
    """Create the Starlette app with simple routing"""
    sse = SseServerTransport("/messages/")
    
    return Starlette(
        debug=debug,
        routes=[
            Route("/health", endpoint=health_check),
            Route("/memories", endpoint=memories_endpoint, methods=["GET"]),  # Add memories endpoint
            Route("/sse", endpoint=sse_endpoint, methods=["GET"]),
            Route("/mcp/sse", endpoint=sse_endpoint, methods=["GET", "POST"]),  # Accept both GET and POST
            Route("/messages/{path:path}", endpoint=sse.handle_post_message, methods=["POST"]),
        ],
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Simple InMemory MCP Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port (default: 8080)')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()

    logger.info("🚀 Starting Simple InMemory MCP Server...")
    logger.info(f"📍 Server: http://{args.host}:{args.port}/sse")
    logger.info(f"📍 MCP Client: http://{args.host}:{args.port}/mcp/sse")
    logger.info(f"🏥 Health: http://{args.host}:{args.port}/health")
    logger.info("🛠️  Tools: add_memory, search_memory")
    
    app = create_app(debug=args.debug)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
