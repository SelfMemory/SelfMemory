#!/usr/bin/env python3
import logging
from typing import Annotated
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
import argparse
from pydantic import Field

# Import existing business logic directly (like previous version)
from add_memory_to_collection import add_memory_enhanced
from src.search.enhanced_search_engine import EnhancedSearchEngine
from mongodb_user_manager import get_mongo_user_manager, initialize_mongo_user_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server (like previous version)
mcp: FastMCP = FastMCP("InMemory", dependencies=["qdrant-client", "ollama"])

# Initialize enhanced search engine (like previous version)
search_engine = EnhancedSearchEngine()

# Global variable to store current user context (like previous version)
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

# MCP Tools - Direct business logic calls (like previous version)
@mcp.tool()
async def add_memory(
    memory_content: str = Field(..., description="The memory text to store"),
    tags: str = Field("", description="Comma-separated tags (e.g., 'project,meeting')"),
    people_mentioned: str = Field("", description="Comma-separated names"),
    topic_category: str = Field("", description="Category or topic"),
) -> str:
    """
    Add memory by extracting key facts, decisions, preferences, or events worth remembering. Add each memory separately.
    Add a memory with rich metadata including tags, people mentioned, topic category, and automatic temporal data.
    Includes duplicate detection to prevent storing similar memories.

    Returns:
        Formatted result with memory ID and metadata details
    """
    try:
        user_id = get_current_user_id()
        result = add_memory_enhanced(
            memory_content=memory_content,
            user_id=user_id,
            tags=tags,
            people_mentioned=people_mentioned,
            topic_category=topic_category,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to add enhanced memory via MCP: {str(e)}")
        return f"❌ Error: Failed to add memory - {str(e)}"

@mcp.tool()
async def search_memories(
    query: str = Field(
        ..., description="Semantic search query to find relevant memories"
    ),
    limit: int = Field(
        5, description="Maximum number of results to return (1-unlimited, default: 5)"
    ),
    tags: str = Field(
        "", description="Filter by comma-separated tags (e.g., 'work,meeting')"
    ),
    people_mentioned: str = Field(
        "", description="Filter by comma-separated people names (e.g., 'John,Sarah')"
    ),
    topic_category: str = Field(
        "", description="Filter by topic category (e.g., 'work', 'personal')"
    ),
    temporal_filter: str = Field(
        "", description="Temporal filter (e.g., 'yesterday', 'this_week', 'weekends')"
    ),
) -> str:
    """
    Enhanced memory search with comprehensive filtering options including semantic similarity,
    metadata filtering, and temporal constraints.

    Returns:
        Formatted search results with metadata
    """
    try:
        # Parse comma-separated filters (like previous version)
        tag_list = (
            [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else None
        )
        people_list = (
            [person.strip() for person in people_mentioned.split(",") if person.strip()]
            if people_mentioned
            else None
        )
        category = topic_category.strip() if topic_category else None
        temporal = temporal_filter.strip() if temporal_filter else None

        user_id = get_current_user_id()
        results = search_engine.search_memories(
            query=query,
            user_id=user_id,
            limit=limit,
            tags=tag_list,
            people_mentioned=people_list,
            topic_category=category,
            temporal_filter=temporal,
        )

        if not results:
            return "🔍 No memories found matching your search criteria."

        # Format results (like previous version)
        formatted_results = [f"🧠 Found {len(results)} memories:\n"]

        for i, result in enumerate(results, 1):
            score_emoji = (
                "🎯"
                if result.get("score", 0) > 0.9
                else "✅"
                if result.get("score", 0) > 0.8
                else "📝"
            )
            formatted_results.append(f"{score_emoji} {i}. {result['memory']}")

            # Add metadata if available
            metadata_parts = []
            if result.get("tags"):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get("people_mentioned"):
                metadata_parts.append(
                    f"People: {', '.join(result['people_mentioned'])}"
                )
            if result.get("topic_category"):
                metadata_parts.append(f"Topic: {result['topic_category']}")
            if result.get("temporal_data"):
                temporal_data = result["temporal_data"]
                if temporal_data.get("day_of_week"):
                    metadata_parts.append(
                        f"Time: {temporal_data.get('day_of_week')}, Q{temporal_data.get('quarter', '?')} {temporal_data.get('year', '?')}"
                    )

            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")

            if result.get("score"):
                formatted_results.append(f"   🎯 Similarity: {result['score']:.3f}")

            formatted_results.append("")  # Empty line between results

        return "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Enhanced search failed via MCP: {str(e)}")
        return f"❌ Error: Search failed - {str(e)}"

@mcp.tool()
async def temporal_search(
    temporal_query: str = Field(
        ...,
        description="Natural language time query (e.g., 'yesterday', 'this_week', 'weekends', 'q3', 'morning')",
    ),
    semantic_query: str = Field(
        "", description="Optional semantic search query to combine with temporal filter"
    ),
    limit: int = Field(
        5, description="Maximum number of results (1-unlimited, default: 5)"
    ),
) -> str:
    """
    Search memories based on time/temporal criteria with optional semantic filtering.

    Supported temporal queries:
    - 'today', 'yesterday'
    - 'this_week', 'weekends', 'weekdays'
    - 'q1', 'q2', 'q3', 'q4' (quarters)
    - 'morning', 'afternoon', 'evening'
    - Day names: 'monday', 'tuesday', etc.

    Returns:
        Formatted temporal search results
    """
    try:
        user_id = get_current_user_id()
        results = search_engine.temporal_search(
            temporal_query=temporal_query,
            user_id=user_id,
            semantic_query=semantic_query if semantic_query.strip() else None,
            limit=limit,
        )

        if not results:
            return f"🕒 No memories found for '{temporal_query}'{f' + "{semantic_query}"' if semantic_query else ''}."

        # Format results (like previous version)
        formatted_results = [
            f"🕒 Found {len(results)} memories for '{temporal_query}'{f' + "{semantic_query}"' if semantic_query else ''}:\n"
        ]

        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")

            # Add temporal context
            if result.get("temporal_data"):
                temporal_data = result["temporal_data"]
                time_context = []
                if temporal_data.get("day_of_week"):
                    time_context.append(f"{temporal_data['day_of_week'].title()}")
                if temporal_data.get("quarter"):
                    time_context.append(f"Q{temporal_data['quarter']}")
                if temporal_data.get("year"):
                    time_context.append(f"{temporal_data['year']}")
                if temporal_data.get("hour") is not None:
                    hour = temporal_data["hour"]
                    time_period = (
                        "Morning"
                        if 6 <= hour < 12
                        else "Afternoon"
                        if 12 <= hour < 18
                        else "Evening"
                    )
                    time_context.append(f"{time_period} ({hour}:00)")

                if time_context:
                    formatted_results.append(f"   🕒 {' | '.join(time_context)}")

            # Add other metadata
            metadata_parts = []
            if result.get("tags"):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get("topic_category"):
                metadata_parts.append(f"Topic: {result['topic_category']}")

            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")

            formatted_results.append("")  # Empty line

        return "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Temporal search failed via MCP: {str(e)}")
        return f"❌ Error: Temporal search failed - {str(e)}"

@mcp.tool()
async def search_by_tags(
    tags: Annotated[
        str, "Comma-separated tags to search for (e.g., 'work,meeting,project')"
    ],
    semantic_query: Annotated[
        str, "Optional semantic search query to combine with tag filtering"
    ] = "",
    match_all_tags: Annotated[
        bool, "Whether to match ALL tags (AND) or ANY tag (OR). Default: False (OR)"
    ] = False,
    limit: Annotated[int, "Maximum number of results (1-20, default: 5)"] = 5,
) -> str:
    """
    Search memories by tags with optional semantic filtering.

    Args:
        tags: Comma-separated tags to search for
        semantic_query: Optional semantic search to combine
        match_all_tags: Whether to match all tags (AND) or any tag (OR)
        limit: Maximum number of results

    Returns:
        Formatted tag search results
    """
    try:
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        if not tag_list:
            return "❌ Please provide at least one tag to search for."

        user_id = get_current_user_id()
        results = search_engine.tag_search(
            tags=tag_list,
            user_id=user_id,
            semantic_query=semantic_query if semantic_query.strip() else None,
            match_all_tags=match_all_tags,
            limit=limit,
        )

        if not results:
            match_type = "all" if match_all_tags else "any"
            return f"🏷️ No memories found with {match_type} of these tags: {', '.join(tag_list)}"

        # Format results (like previous version)
        match_type = "all" if match_all_tags else "any"
        formatted_results = [
            f"🏷️ Found {len(results)} memories with {match_type} of: {', '.join(tag_list)}\n"
        ]

        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")

            # Highlight matching tags
            if result.get("tags"):
                all_tags = result["tags"]
                matching_tags = [
                    tag for tag in all_tags if tag in [t.lower() for t in tag_list]
                ]
                other_tags = [tag for tag in all_tags if tag not in matching_tags]

                tag_display = []
                if matching_tags:
                    tag_display.append(f"✅ {', '.join(matching_tags)}")
                if other_tags:
                    tag_display.append(f"📋 {', '.join(other_tags)}")

                formatted_results.append(f"   🏷️ {' | '.join(tag_display)}")

            # Add other metadata
            metadata_parts = []
            if result.get("people_mentioned"):
                metadata_parts.append(
                    f"People: {', '.join(result['people_mentioned'])}"
                )
            if result.get("topic_category"):
                metadata_parts.append(f"Topic: {result['topic_category']}")

            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")

            formatted_results.append("")  # Empty line

        return "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Tag search failed via MCP: {str(e)}")
        return f"❌ Error: Tag search failed - {str(e)}"

@mcp.tool()
async def search_by_people(
    people: Annotated[
        str, "Comma-separated names of people to search for (e.g., 'John,Sarah,Mike')"
    ],
    semantic_query: Annotated[
        str, "Optional semantic search query to combine with people filtering"
    ] = "",
    limit: Annotated[int, "Maximum number of results (1-20, default: 5)"] = 5,
) -> str:
    """
    Search memories by people mentioned with optional semantic filtering.

    Args:
        people: Comma-separated names of people to search for
        semantic_query: Optional semantic search to combine
        limit: Maximum number of results

    Returns:
        Formatted people search results
    """
    try:
        people_list = [person.strip() for person in people.split(",") if person.strip()]
        if not people_list:
            return "❌ Please provide at least one person's name to search for."

        user_id = get_current_user_id()
        results = search_engine.people_search(
            people=people_list,
            user_id=user_id,
            semantic_query=semantic_query if semantic_query.strip() else None,
            limit=limit,
        )

        if not results:
            return f"👥 No memories found mentioning: {', '.join(people_list)}"

        # Format results (like previous version)
        formatted_results = [
            f"👥 Found {len(results)} memories mentioning: {', '.join(people_list)}\n"
        ]

        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")

            # Highlight mentioned people
            if result.get("people_mentioned"):
                all_people = result["people_mentioned"]
                matching_people = [
                    person for person in all_people if person in people_list
                ]
                other_people = [
                    person for person in all_people if person not in matching_people
                ]

                people_display = []
                if matching_people:
                    people_display.append(f"✅ {', '.join(matching_people)}")
                if other_people:
                    people_display.append(f"👤 {', '.join(other_people)}")

                formatted_results.append(f"   👥 {' | '.join(people_display)}")

            # Add other metadata
            metadata_parts = []
            if result.get("tags"):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get("topic_category"):
                metadata_parts.append(f"Topic: {result['topic_category']}")

            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")

            formatted_results.append("")  # Empty line

        return "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"People search failed via MCP: {str(e)}")
        return f"❌ Error: People search failed - {str(e)}"

@mcp.tool()
async def search_by_topic(
    topic_category: str = Field(
        ...,
        description="Topic category to search for (e.g., 'work', 'personal', 'learning', 'technology')",
    ),
    semantic_query: str = Field(
        "", description="Optional semantic search query to combine with topic filtering"
    ),
    limit: int = Field(5, description="Maximum number of results (1-20, default: 5)"),
) -> str:
    """
    Search memories by topic category with optional semantic filtering.

    Args:
        topic_category: Topic category to search for
        semantic_query: Optional semantic search to combine
        limit: Maximum number of results

    Returns:
        Formatted topic search results
    """
    try:
        if not topic_category.strip():
            return "❌ Please provide a topic category to search for."

        user_id = get_current_user_id()
        results = search_engine.topic_search(
            topic_category=topic_category.strip(),
            user_id=user_id,
            semantic_query=semantic_query if semantic_query.strip() else None,
            limit=limit,
        )

        if not results:
            return f"📂 No memories found in topic: '{topic_category}'"

        # Format results (like previous version)
        formatted_results = [
            f"📂 Found {len(results)} memories in topic: '{topic_category}'\n"
        ]

        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")

            # Add metadata
            metadata_parts = []
            if result.get("tags"):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get("people_mentioned"):
                metadata_parts.append(
                    f"People: {', '.join(result['people_mentioned'])}"
                )

            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")

            # Add temporal context
            if result.get("temporal_data"):
                temporal_data = result["temporal_data"]
                if temporal_data.get("day_of_week"):
                    formatted_results.append(
                        f"   🕒 {temporal_data['day_of_week'].title()}, Q{temporal_data.get('quarter', '?')} {temporal_data.get('year', '?')}"
                    )

            formatted_results.append("")  # Empty line

        return "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Topic search failed via MCP: {str(e)}")
        return f"❌ Error: Topic search failed - {str(e)}"

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided MCP server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        # Get Authorization header for API key authentication (like previous version)
        headers = dict(request.headers)
        auth_header = headers.get("authorization", "").strip()
        
        if not auth_header.startswith("Bearer "):
            logger.error("Missing or invalid Authorization header")
            raise ValueError("Authorization header with Bearer token required")
        
        api_key = auth_header.replace("Bearer ", "").strip()
        
        # Validate API key and get user_id (like previous version)
        user_manager = get_mongo_user_manager()
        user_id = user_manager.validate_api_key(api_key)
        
        if not user_id:
            logger.warning(f"Invalid API key in SSE connection: {api_key[:8]}...")
            raise ValueError(f"Invalid API key: {api_key[:8]}...")
        
        logger.info(f"SSE connection established for user: {user_id}")
        
        # Set user context (like previous version)
        set_current_user_id(user_id)
        
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),  # Only GET for SSE
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

if __name__ == "__main__":
    # Parse command line arguments (like previous version)
    parser = argparse.ArgumentParser(description='Run Enhanced MCP Memory Server with SSE')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on (default: 8080)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    # Initialize MongoDB user manager (CRITICAL FIX)
    try:
        initialize_mongo_user_manager()
        logger.info("MongoDB user manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB user manager: {e}")
        raise

    logger.info("Starting Enhanced MCP Memory Server with SSE transport...")
    logger.info(f"Server will be available at: http://{args.host}:{args.port}/sse")
    
    # Get the underlying MCP server (like previous version)
    mcp_server = mcp._mcp_server  # noqa: WPS437

    # Create Starlette app with SSE support
    starlette_app = create_starlette_app(mcp_server, debug=args.debug)

    # Run the server
    uvicorn.run(starlette_app, host=args.host, port=args.port, log_level="info")
