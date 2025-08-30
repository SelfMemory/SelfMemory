"""
Modern MCP Server for InMemory using FastMCP.

This implementation follows the mem0/openmemory pattern for a clean,
maintainable MCP server with proper error handling and context management.
"""

import contextvars
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.routing import APIRouter
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize MCP
mcp = FastMCP("inmemory-mcp-server")

# Context variables for user_id and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp")

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")

def get_memory_client_safe():
    """Get memory client with error handling. Returns None if client cannot be initialized."""
    try:
        # Import here to avoid circular imports and allow lazy loading
        from inmemory.memory import Memory
        
        # Initialize with environment variables or defaults
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": os.getenv("QDRANT_HOST", "localhost"),
                    "port": int(os.getenv("QDRANT_PORT", "6333")),
                }
            },
            "embedder": {
                "provider": os.getenv("EMBEDDING_PROVIDER", "ollama"),
                "config": {
                    "model": os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
                    "ollama_base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                }
            }
        }
        
        return Memory(config=config)
    except Exception as e:
        logger.warning(f"Failed to initialize memory client: {e}")
        return None

@mcp.tool(description="Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevant information which can be useful in the future conversation.")
async def add_memory(text: str) -> str:
    """Add a new memory to the user's memory store."""
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)

    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        result = memory_client.add(
            messages=text,
            user_id=uid,
            metadata={
                "source_app": "inmemory-mcp",
                "mcp_client": client_name,
            }
        )
        
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        else:
            return str(result)
            
    except Exception as e:
        logger.error(f"Failed to add memory: {str(e)}")
        return f"Error adding memory: {str(e)}"

@mcp.tool(description="Search through stored memories. This method is called EVERYTIME the user asks anything.")
async def search_memory(query: str, limit: int = 5) -> str:
    """Search through the user's stored memories."""
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        results = memory_client.search(
            query=query,
            user_id=uid,
            limit=limit
        )
        
        if not results:
            return "No memories found matching your search criteria."
        
        # Format results for better readability
        formatted_results = []
        for i, result in enumerate(results, 1):
            memory_text = result.get('memory', result.get('text', str(result)))
            score = result.get('score', 0)
            formatted_results.append(f"{i}. {memory_text} (Score: {score:.3f})")
        
        return f"Found {len(results)} memories:\n\n" + "\n\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"Failed to search memories: {str(e)}")
        return f"Error searching memories: {str(e)}"

@mcp.tool(description="List all memories in the user's memory store.")
async def list_memories(limit: int = 10) -> str:
    """List all memories for the user."""
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        results = memory_client.get_all(user_id=uid, limit=limit)
        
        if not results:
            return "No memories found."
        
        # Format results
        formatted_results = []
        for i, result in enumerate(results, 1):
            memory_text = result.get('memory', result.get('text', str(result)))
            formatted_results.append(f"{i}. {memory_text}")
        
        return f"Found {len(results)} memories:\n\n" + "\n\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"Failed to list memories: {str(e)}")
        return f"Error listing memories: {str(e)}"

@mcp.tool(description="Delete a specific memory by its content or ID.")
async def delete_memory(memory_id: str) -> str:
    """Delete a specific memory."""
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        result = memory_client.delete(memory_id=memory_id, user_id=uid)
        return f"Successfully deleted memory: {memory_id}"
        
    except Exception as e:
        logger.error(f"Failed to delete memory: {str(e)}")
        return f"Error deleting memory: {str(e)}"

@mcp.tool(description="Delete all memories for the user.")
async def delete_all_memories() -> str:
    """Delete all memories for the user."""
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        result = memory_client.delete_all(user_id=uid)
        return "Successfully deleted all memories."
        
    except Exception as e:
        logger.error(f"Failed to delete all memories: {str(e)}")
        return f"Error deleting all memories: {str(e)}"

@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    """Handle SSE connections for a specific user and client"""
    # Extract user_id and client_name from path parameters
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")

    try:
        # Handle SSE connection
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )
    finally:
        # Clean up context variables
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)

@mcp_router.post("/messages/")
async def handle_get_message(request: Request):
    return await handle_post_message(request)

@mcp_router.post("/{client_name}/sse/{user_id}/messages/")
async def handle_post_message_with_params(request: Request):
    return await handle_post_message(request)

async def handle_post_message(request: Request):
    """Handle POST messages for SSE"""
    try:
        body = await request.body()

        # Create a simple receive function that returns the body
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        # Create a simple send function that does nothing
        async def send(message):
            return {}

        # Call handle_post_message with the correct arguments
        await sse.handle_post_message(request.scope, receive, send)

        # Return a success response
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error handling POST message: {e}")
        return {"status": "error", "message": str(e)}

def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    mcp._mcp_server.name = "inmemory-mcp-server"
    
    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)

def create_app() -> FastAPI:
    """Create FastAPI application with MCP server."""
    app = FastAPI(
        title="InMemory MCP Server",
        description="MCP Server for InMemory - Personal Memory Management",
        version="1.0.0"
    )
    
    setup_mcp_server(app)
    
    @app.get("/")
    async def root():
        return {
            "message": "InMemory MCP Server",
            "version": "1.0.0",
            "tools": ["add_memory", "search_memory", "list_memories", "delete_memory", "delete_all_memories"]
        }
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "inmemory-mcp-server"}
    
    return app

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting InMemory MCP Server...")
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
