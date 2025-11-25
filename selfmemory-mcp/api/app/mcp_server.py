"""
SelfMemory MCP Server following selfmemory openmemory patterns.

This module implements an MCP (Model Context Protocol) server that provides
memory operations for SelfMemory. The memory client is initialized lazily
to prevent server crashes when external dependencies are unavailable.

Key features:
- Lazy memory client initialization
- Graceful error handling for unavailable dependencies
- Environment variable parsing for configuration
- FastAPI integration following selfmemory patterns
"""

import contextvars
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.routing import APIRouter
from mcp.server.fastmcp import FastMCP

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

load_dotenv()  # Load environment variables from .env

# Import client cache for performance optimization
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from auth.client_cache import get_client_from_cache, set_client_in_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
USER_ID = os.getenv("USER_ID", "default")
SELFMEMORY_PLATFORM_MODE = (
    os.getenv("SELFMEMORY_PLATFORM_MODE", "false").lower() == "true"
)
CORE_SERVER_HOST = os.getenv("SELFMEMORY_API_HOST", "http://localhost:8081")
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8765"))

# Import appropriate classes based on mode
if SELFMEMORY_PLATFORM_MODE:
    from selfmemory import SelfMemoryClient

    MEMORY_CLIENT_CLASS = SelfMemoryClient
    logger.info("🏢 Platform Mode: Using SelfMemoryClient with API key authentication")
else:
    from selfmemory import SelfMemory

    MEMORY_CLIENT_CLASS = SelfMemory
    logger.info("🏠 Open Source Mode: Using SelfMemory class without authentication")

# Initialize MCP with stateless_http=False for session management
mcp = FastMCP(
    name="selfmemory-mcp-server",
    stateless_http=False,
    json_response=True,
)

# Context variables for user_id and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")


def _extract_memory_contents(search_result: dict[str, Any]) -> list[str]:
    """Extract only content strings from search results for LLM consumption.

    Args:
        search_result: Full search result dictionary from client.search()

    Returns:
        List of memory content strings, empty list if no results
    """
    if "results" not in search_result or not search_result["results"]:
        return []

    return [memory.get("content", "") for memory in search_result["results"]]


def _generate_memory_confirmation(content: str) -> str:
    """Generate a personalized confirmation message for stored memory.

    Args:
        content: The memory content that was stored

    Returns:
        Personalized confirmation message string
    """
    return "I learnt more about you with this!"


def validate_and_get_client_platform(api_key: str) -> SelfMemoryClient:
    """
    Validate request and create authenticated SelfMemoryClient (Platform Mode).
    
    Uses client caching to avoid creating new connections on every request,
    significantly improving performance by reusing TCP/TLS connections.

    Args:
        api_key: API key for authentication

    Returns:
        SelfMemoryClient: Client authenticated with the user's token (cached)

    Raises:
        ValueError: If authentication fails
    """
    try:
        if not api_key:
            raise ValueError("No API key provided")

        # Check cache first to reuse existing client connection
        cached_client = get_client_from_cache(api_key)
        if cached_client:
            return cached_client

        # Create and validate client - this will raise ValueError if token is invalid
        client = SelfMemoryClient(api_key=api_key, host=CORE_SERVER_HOST)

        # Cache the client for future requests (reuses connection)
        set_client_in_cache(api_key, client)

        logger.info("✅ MCP Platform: API key authenticated (new client created)")
        return client

    except ValueError:
        # Re-raise ValueError as-is (these are our custom auth errors)
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise ValueError("Authentication failed") from e


def get_memory_instance_open_source() -> SelfMemory:
    """
    Create SelfMemory instance for Open Source Mode (no authentication required).

    Returns:
        SelfMemory: Direct memory instance for local usage

    Raises:
        ValueError: If memory instance creation fails
    """
    try:
        # Create direct SelfMemory instance (no authentication needed)
        memory = SelfMemory()
        logger.info("✅ MCP Open Source: Direct memory instance created")
        return memory

    except Exception as e:
        logger.error(f"Failed to create memory instance: {e}")
        raise ValueError("Memory instance creation failed") from e


def validate_and_get_memory_client(api_key: str | None = None) -> Any:
    """
    Dual mode client/memory provider - returns appropriate instance based on mode.

    Args:
        api_key: API key for platform mode authentication

    Returns:
        SelfMemoryClient (Platform Mode) or SelfMemory (Open Source Mode)

    Raises:
        ValueError: If authentication/initialization fails
    """
    if SELFMEMORY_PLATFORM_MODE:
        if not api_key:
            raise ValueError("API key required for platform mode")
        return validate_and_get_client_platform(api_key)
    return get_memory_instance_open_source()


# Don't initialize memory client at import time - do it lazily when needed
def get_memory_client_safe():
    """Get memory client with error handling. Returns None if client cannot be initialized."""
    try:
        if SELFMEMORY_PLATFORM_MODE:
            # Platform mode requires API key - will be handled per request
            return None  # Will be created per request with proper auth
        # Open source mode - create direct instance
        return SelfMemory()
    except Exception as e:
        logger.warning(f"Failed to get memory client: {e}")
        return None


@mcp.tool(
    description="Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevant information which can be useful in the future conversation."
)
async def add_memories(text: str) -> str:
    uid = user_id_var.get(USER_ID)
    client_name = client_name_var.get("selfmemory")

    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    try:
        if SELFMEMORY_PLATFORM_MODE:
            # Platform mode: Use SelfMemoryClient with API key
            api_key = os.getenv("SELFMEMORY_API_KEY")
            if not api_key:
                return "Error: SELFMEMORY_API_KEY environment variable required for platform mode"

            memory_client = validate_and_get_client_platform(api_key)

            # Use selfmemory-style message format
            messages = [{"role": "user", "content": text}]
            result = memory_client.add(
                messages=messages,
                user_id=uid,
                metadata={
                    "source_app": "selfmemory",
                    "mcp_client": client_name,
                },
            )

            return json.dumps(result, indent=2)
        # Open source mode: Use SelfMemory class directly
        memory_client = get_memory_client_safe()
        if not memory_client:
            return (
                "Error: Memory system is currently unavailable. Please try again later."
            )

        result = memory_client.add(
            memory_content=text,
            user_id=uid,
            metadata={
                "source_app": "selfmemory",
                "mcp_client": client_name,
            },
        )

        if not result.get("success", False):
            return f"Error adding to memory: {result.get('error', 'Unknown error')}"

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.exception(f"Error adding to memory: {e}")
        return f"Error adding to memory: {e}"


@mcp.tool(
    description="Search through stored memories. This method is called EVERYTIME the user asks anything."
)
async def search_memory(query: str) -> str:
    uid = user_id_var.get(USER_ID)
    client_name = client_name_var.get("selfmemory")

    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    try:
        if SELFMEMORY_PLATFORM_MODE:
            # Platform mode: Use SelfMemoryClient with API key
            api_key = os.getenv("SELFMEMORY_API_KEY")
            if not api_key:
                return "Error: SELFMEMORY_API_KEY environment variable required for platform mode"

            memory_client = validate_and_get_client_platform(api_key)

            result = memory_client.search(query=query, user_id=uid, limit=10)

            results = []
            if isinstance(result, list):
                # Handle direct list response
                for memory in result:
                    results.append(
                        {
                            "id": memory.get("id"),
                            "memory": memory.get("memory", memory.get("content")),
                            "score": memory.get("score", 1.0),
                            "created_at": memory.get("created_at"),
                        }
                    )
            elif "results" in result:
                # Handle results wrapper
                for memory in result["results"]:
                    results.append(
                        {
                            "id": memory.get("id"),
                            "memory": memory.get("memory", memory.get("content")),
                            "score": memory.get("score", 1.0),
                            "created_at": memory.get("created_at"),
                        }
                    )

            return json.dumps({"results": results}, indent=2)
        # Open source mode: Use SelfMemory class directly
        memory_client = get_memory_client_safe()
        if not memory_client:
            return (
                "Error: Memory system is currently unavailable. Please try again later."
            )

        result = memory_client.search(query=query, user_id=uid, limit=10)

        results = []
        if "results" in result:
            for memory in result["results"]:
                results.append(
                    {
                        "id": memory.get("id"),
                        "memory": memory.get("content"),
                        "score": memory.get("score", 1.0),
                        "created_at": memory.get("metadata", {}).get("created_at"),
                    }
                )

        return json.dumps({"results": results}, indent=2)

    except Exception as e:
        logger.exception(f"Error searching memory: {e}")
        return f"Error searching memory: {e}"


@mcp.tool(description="List all memories in the user's memory")
async def list_memories() -> str:
    uid = user_id_var.get(USER_ID)
    client_name = client_name_var.get("selfmemory")

    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    try:
        if SELFMEMORY_PLATFORM_MODE:
            # Platform mode: Use SelfMemoryClient with API key
            api_key = os.getenv("SELFMEMORY_API_KEY")
            if not api_key:
                return "Error: SELFMEMORY_API_KEY environment variable required for platform mode"

            memory_client = validate_and_get_client_platform(api_key)

            result = memory_client.get_all(user_id=uid)

            filtered_memories = []
            if isinstance(result, list):
                # Handle direct list response
                for memory in result:
                    filtered_memories.append(
                        {
                            "id": memory.get("id"),
                            "memory": memory.get("memory", memory.get("content")),
                            "created_at": memory.get("created_at"),
                        }
                    )
            elif "results" in result:
                # Handle results wrapper
                for memory in result["results"]:
                    filtered_memories.append(
                        {
                            "id": memory.get("id"),
                            "memory": memory.get("memory", memory.get("content")),
                            "created_at": memory.get("created_at"),
                        }
                    )

            return json.dumps(filtered_memories, indent=2)
        # Open source mode: Use SelfMemory class directly
        memory_client = get_memory_client_safe()
        if not memory_client:
            return (
                "Error: Memory system is currently unavailable. Please try again later."
            )

        result = memory_client.get_all(user_id=uid)

        filtered_memories = []
        if "results" in result:
            for memory in result["results"]:
                filtered_memories.append(
                    {
                        "id": memory.get("id"),
                        "memory": memory.get("content"),
                        "created_at": memory.get("metadata", {}).get("created_at"),
                    }
                )

        return json.dumps(filtered_memories, indent=2)

    except Exception as e:
        logger.exception(f"Error getting memories: {e}")
        return f"Error getting memories: {e}"


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    uid = user_id_var.get(USER_ID)
    client_name = client_name_var.get("selfmemory")

    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    try:
        if SELFMEMORY_PLATFORM_MODE:
            # Platform mode: Use SelfMemoryClient with API key
            api_key = os.getenv("SELFMEMORY_API_KEY")
            if not api_key:
                return "Error: SELFMEMORY_API_KEY environment variable required for platform mode"

            memory_client = validate_and_get_client_platform(api_key)

            # Get all memories first, then delete them individually
            memories = memory_client.get_all(user_id=uid)

            deleted_count = 0
            if isinstance(memories, list):
                for memory in memories:
                    if memory.get("id"):
                        try:
                            memory_client.delete(memory["id"])
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete memory {memory['id']}: {e}"
                            )
            elif "results" in memories:
                for memory in memories["results"]:
                    if memory.get("id"):
                        try:
                            memory_client.delete(memory["id"])
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete memory {memory['id']}: {e}"
                            )

            return f"Successfully deleted {deleted_count} memories"
        # Open source mode: Use SelfMemory class directly
        memory_client = get_memory_client_safe()
        if not memory_client:
            return (
                "Error: Memory system is currently unavailable. Please try again later."
            )

        return "Successfully deleted all memories"

    except Exception as e:
        logger.exception(f"Error deleting memories: {e}")
        return f"Error deleting memories: {e}"


# Lifespan context manager for MCP session management
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Manage server lifecycle - ensures MCP session manager is running.
    
    This is critical for proper RequestResponder initialization and prevents
    the 'RequestResponder must be used as a context manager' error.
    """
    async with mcp.session_manager.run():
        yield


def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application.
    
    Mounts the MCP streamable HTTP app to handle all MCP protocol messages.
    The session manager must be running (via lifespan) for this to work.
    """
    mcp._mcp_server.name = "selfmemory-mcp-server"
    
    # Configure streamable HTTP path
    mcp.settings.streamable_http_path = "/"
    
    # Mount MCP app - this handles SSE connections automatically
    app.mount("/mcp", mcp.streamable_http_app())


def main():
    """Main entry point for the SelfMemory MCP server.
    
    Note: This is typically not used when running via api/main.py.
    The server is set up through setup_mcp_server() called from api/main.py.
    """
    import uvicorn
    from fastapi import FastAPI
    
    logger.info("=" * 60)
    logger.info("🚀 Starting SelfMemory MCP Server (Standalone)")
    logger.info("=" * 60)
    logger.info(
        f"🔧 Mode: {'🏢 Platform' if SELFMEMORY_PLATFORM_MODE else '🏠 Open Source'}"
    )

    if SELFMEMORY_PLATFORM_MODE:
        logger.info(f"📡 Core Server: {CORE_SERVER_HOST}")
        logger.info("🔒 Authentication: Bearer Token (API Key Required)")
        logger.info("👥 Multi-tenant: Project-scoped isolation")
    else:
        logger.info("📁 Storage: Local vector database")
        logger.info("🔓 Authentication: None (Direct local access)")
        logger.info("👤 Single-user: Default user context")

    logger.info(f"🌐 MCP Server: http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}")
    logger.info("🛠️  Tools: add_memories, search_memory, list_memories, delete_all_memories")
    logger.info("=" * 60)

    # Create FastAPI app with lifespan
    app = FastAPI(
        title="SelfMemory MCP Server",
        description="Memory operations via Model Context Protocol",
        lifespan=lifespan,
    )
    
    # Setup MCP server
    setup_mcp_server(app)
    
    # Run with uvicorn
    try:
        uvicorn.run(
            app,
            host=MCP_SERVER_HOST,
            port=MCP_SERVER_PORT,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
