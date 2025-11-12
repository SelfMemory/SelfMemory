from mcp.server.fastmcp import Context, FastMCP

# Create an MCP server
mcp = FastMCP("selfmemory")

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
