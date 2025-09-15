"""
SelfMemory MCP Server

This module implements an MCP (Model Context Protocol) server that provides
memory operations for SelfMemory using simple Bearer token authentication.

Features:
- Simple Bearer token authentication with SelfMemory API keys
- Per-request client creation for proper user isolation
- Graceful error handling when core server is unavailable
- Clean add_memory and search_memories tools
- Streamable HTTP transport for production deployment
"""

import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()  # Load environment variables from .env

from mcp.server.fastmcp import Context, FastMCP

from selfmemory import SelfMemoryClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
CORE_SERVER_HOST = os.getenv("SELFMEMORY_API_HOST", "http://localhost:8081")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8080"))
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "0.0.0.0")

# Initialize MCP server without OAuth (simple Bearer token approach)
mcp = FastMCP(
    name="SelfMemory",
    instructions="Memory management server for SelfMemory - store and search personal memories with metadata",
    stateless_http=True,
    json_response=True,
    port=MCP_SERVER_PORT,
    host=MCP_SERVER_HOST,
)

logger.info(f"SelfMemory MCP Server initialized - Core server: {CORE_SERVER_HOST}")


def validate_and_get_client(ctx: Context) -> SelfMemoryClient:
    """
    Validate request and create authenticated SelfMemoryClient.
    Supports both dashboard session auth and direct API key auth.

    Args:
        ctx: FastMCP Context containing request information

    Returns:
        SelfMemoryClient: Client authenticated with the user's token

    Raises:
        ValueError: If authentication fails
    """
    try:
        # Extract headers from the HTTP request
        request = ctx.request_context.request
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise ValueError("No valid authorization header found")

        token = auth_header.replace("Bearer ", "")

        # Create and validate client - this will raise ValueError if token is invalid
        client = SelfMemoryClient(api_key=token, host=CORE_SERVER_HOST)

        logger.info(
            f"✅ MCP: API key authenticated for user: {client.user_info.get('user_id', 'unknown')}"
        )
        return client

    except AttributeError as e:
        logger.error(f"Context structure error: {e}")
        raise ValueError("Request context not available")
    except ValueError:
        # Re-raise ValueError as-is (these are our custom auth errors)
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise ValueError("Authentication failed")


@mcp.tool()
async def add_memory(
    content: str, ctx: Context, tags: str = "", people: str = "", category: str = ""
) -> dict[str, Any]:
    """
    Store new memories with metadata.

    Args:
        content: The memory content to store
        tags: Optional comma-separated tags (e.g., "work,meeting,important")
        people: Optional comma-separated people mentioned (e.g., "Alice,Bob")
        category: Optional topic category (e.g., "work", "personal", "learning")

    Returns:
        Dict containing success status and memory details or error information

    Examples:
        - add_memory("Had a great meeting about the new project", tags="work,meeting", people="Sarah,Mike")
        - add_memory("Learned about Python decorators today", category="learning")
        - add_memory("Birthday party this weekend", tags="personal,social", people="Emma")
    """
    try:
        logger.info(f"Adding memory: {content[:50]}...")

        # Validate token and get authenticated client
        client = validate_and_get_client(ctx)

        # Format data in the correct selfmemory format that the core server expects
        memory_data = {
            "messages": [{"role": "user", "content": content}],
            "metadata": {
                "tags": tags,
                "people_mentioned": people,
                "topic_category": category,
            },
        }

        # Use the client's underlying httpx client to send the correct format
        response = client.client.post("/api/memories", json=memory_data)
        response.raise_for_status()
        result = response.json()

        # Close the client connection
        client.close()

        logger.info("Memory added successfully")
        return result

    except ValueError as e:
        error_msg = f"Authentication error: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Failed to add memory: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}


@mcp.tool()
async def search_memories(
    query: str,
    ctx: Context,
    limit: int = 10,
    tags: list[str] | None = None,
    people: list[str] | None = None,
    category: str | None = None,
    threshold: float | None = None,
) -> dict[str, Any]:
    """
    Search memories using semantic search with optional filters.

    Args:
        query: The search query (e.g., "meeting notes", "python learning", "weekend plans")
        limit: Maximum number of results to return (default: 10, max: 50)
        tags: Optional list of tags to filter by (e.g., ["work", "important"])
        people: Optional list of people to filter by (e.g., ["Alice", "Bob"])
        category: Optional category filter (e.g., "work", "personal")
        threshold: Optional minimum similarity score (0.0 to 1.0)

    Returns:
        Dict containing search results with memories and metadata

    Examples:
        - search_memories("project meeting")
        - search_memories("Python", tags=["learning"], limit=5)
        - search_memories("birthday", people=["Emma"], category="personal")
    """
    try:
        logger.info(f"Searching memories: '{query}'")

        # Validate limit
        if limit > 50:
            limit = 50
        elif limit < 1:
            limit = 1

        # Validate token and get authenticated client
        client = validate_and_get_client(ctx)

        # Use SelfMemoryClient properly (no circular dependency)
        result = client.search(
            query=query,
            limit=limit,
            tags=tags,
            people_mentioned=people,
            topic_category=category,
            threshold=threshold,
        )

        # Close the client connection
        client.close()

        results_count = len(result.get("results", []))
        logger.info(f"Search completed: {results_count} results found")

        return result

    except ValueError as e:
        error_msg = f"Authentication error: {str(e)}"
        logger.error(error_msg)
        return {"results": [], "error": error_msg}
    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        logger.error(error_msg)
        return {"results": [], "error": error_msg}


def main():
    """Main entry point for the SelfMemory MCP server."""
    logger.info("=" * 60)
    logger.info("🚀 Starting SelfMemory MCP Server")
    logger.info("=" * 60)
    logger.info(f"📡 Core Server: {CORE_SERVER_HOST}")
    logger.info(f"🌐 MCP Server: http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}")
    logger.info("🔒 Authentication: Bearer Token")
    logger.info("🛠️  Tools: add_memory, search_memories")
    logger.info("=" * 60)

    try:
        # Run server with streamable HTTP transport
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
