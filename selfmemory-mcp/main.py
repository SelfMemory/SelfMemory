"""SelfMemory MCP Server

Implements an MCP (Model Context Protocol) server that provides memory operations
for SelfMemory using simple Bearer token authentication.

Features:
- Simple Bearer token authentication with SelfMemory API keys
- Per-request client creation for proper user isolation
- Graceful error handling when core server is unavailable
- Tools: add_memory and search_memories
- Streamable HTTP transport for production deployment
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from selfmemory import SelfMemoryClient

# Ensure project root is in sys.path (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Add selfmemory-mcp to path for telemetry imports
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()  # Load environment variables from .env

# Import telemetry after adding to path
from telemetry import init_logging, init_telemetry  # noqa: E402

# Initialize logging based on environment (console for dev, file for prod)
init_logging()

logger = logging.getLogger(__name__)

# Initialize OpenTelemetry if enabled (optional)
init_telemetry()

# Configuration
CORE_SERVER_HOST = os.getenv("SELFMEMORY_API_HOST", "http://localhost:8081")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "5055"))
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
        raise ValueError("Request context not available") from e
    except ValueError:
        # Re-raise ValueError as-is (these are our custom auth errors)
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise ValueError("Authentication failed") from e


@mcp.tool()
async def add_memory(
    content: str, ctx: Context, tags: str = "", people: str = "", category: str = ""
) -> str:
    """
    Store new memories with metadata.

    Args:
        content: The memory content to store
        tags: Optional comma-separated tags (e.g., "work,meeting,important")
        people: Optional comma-separated people mentioned (e.g., "Alice,Bob")
        category: Optional topic category (e.g., "work", "personal", "learning")

    Returns:
        Personalized confirmation message string

    Examples:
        - add_memory("Had a great meeting about the new project", tags="work,meeting", people="Sarah,Mike") -> "I learnt more about you with this!"
        - add_memory("Learned about Python decorators today", category="learning") -> "I learnt more about you with this!"
        - add_memory("Birthday party this weekend", tags="personal,social", people="Emma") -> "I learnt more about you with this!"
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

        # Close the client connection
        client.close()

        logger.info("Memory added successfully")

        # Generate personalized confirmation message
        return _generate_memory_confirmation(content)

    except ValueError as e:
        error_msg = f"Authentication error: {str(e)}"
        logger.error(error_msg)
        return f"Authentication failed: {str(e)}"
    except Exception as e:
        error_msg = f"Failed to add memory: {str(e)}"
        logger.error(error_msg)
        return f"Failed to store memory: {str(e)}"


@mcp.tool()
async def search_memories(
    query: str,
    ctx: Context,
    limit: int = 10,
    tags: list[str] | None = None,
    people: list[str] | None = None,
    category: str | None = None,
    threshold: float | None = None,
) -> list[str]:
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
        List of memory content strings for LLM consumption

    Examples:
        - search_memories("project meeting") -> ["Had a meeting about the new project", ...]
        - search_memories("Python", tags=["learning"], limit=5) -> ["Learned Python decorators", ...]
        - search_memories("birthday", people=["Emma"], category="personal") -> ["Emma's birthday party", ...]
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

        # Extract only content strings for LLM consumption
        return _extract_memory_contents(result)

    except ValueError as e:
        error_msg = f"Authentication error: {str(e)}"
        logger.error(error_msg)
        return []
    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        logger.error(error_msg)
        return []


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
