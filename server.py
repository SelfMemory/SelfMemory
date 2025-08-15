import logging
import os
from typing import Annotated
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.responses import PlainTextResponse
from starlette.datastructures import Headers
from starlette.types import Scope, Receive, Send
from mcp.server import Server
import uvicorn
import argparse

from add_memory_to_collection import add_memory_enhanced
from retrieve_memory_from_collection import (
    retrieve_memories,
    search_memories_with_filter,
)
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

mcp: FastMCP = FastMCP("InMemory", dependencies=["qdrant-client", "ollama", "pymongo"])

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

# FastAPI HTTP Endpoints
@api.post("/v1/memories")
async def add_memory_http(
    request: AddMemoryRequest,
    user_id: str = Depends(authenticate_api_key)
):
    """Add a new memory via HTTP API."""
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
        logger.error(f"Failed to add memory via HTTP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add memory: {str(e)}")

@api.get("/v1/memories")
async def get_memories_http(
    limit: int = 10,
    offset: int = 0,
    user_id: str = Depends(authenticate_api_key)
):
    """Get user's memories via HTTP API."""
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
                "tags": result.get("tags", []),
                "people_mentioned": result.get("people_mentioned", []),
                "topic_category": result.get("topic_category", ""),
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
        logger.error(f"Failed to get memories via HTTP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get memories: {str(e)}")

@api.post("/v1/search")
async def search_memories_http(
    request: SearchMemoriesRequest,
    user_id: str = Depends(authenticate_api_key)
):
    """Search memories via HTTP API."""
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
        
        return {
            "memories": results or [],
            "total": len(results) if results else 0
        }
    except Exception as e:
        logger.error(f"Failed to search memories via HTTP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}")

@api.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "InMemory MCP Server API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/v1/health",
            "memories": "/api/v1/memories",
            "search": "/api/v1/search"
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

# MCP Tools (existing functionality preserved)
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
        # Parse comma-separated filters
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

        # Format results
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

        # Format results
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

        # Format results
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

        # Format results
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

        # Format results
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

def create_combined_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a combined Starlette application that serves both MCP SSE and FastAPI HTTP endpoints."""
    sse = SseServerTransport("/messages/")

    class SSEHandler:
        """ASGI application class for handling SSE connections with API key authentication."""
        
        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            """
            ASGI application for handling SSE connections with API key authentication.
            """
            # Get Authorization header for API key authentication
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            
            if not auth_header.startswith("Bearer "):
                logger.error("Missing or invalid Authorization header")
                response = PlainTextResponse("Unauthorized: Bearer token required", status_code=401)
                await response(scope, receive, send)
                return
            
            api_key = auth_header.replace("Bearer ", "")
            user_manager = get_mongo_user_manager()
            user_id = user_manager.validate_api_key(api_key)
            
            if not user_id:
                logger.warning(f"Invalid API key in SSE connection: {api_key[:8]}...")
                response = PlainTextResponse("Unauthorized: Invalid API key", status_code=401)
                await response(scope, receive, send)
                return
            
            logger.info(f"SSE connection established for user: {user_id}")
            
            # Set user context for MCP tools
            set_current_user_id(user_id)
            
            try:
                async with sse.connect_sse(scope, receive, send) as (read_stream, write_stream):
                    await mcp_server.run(
                        read_stream,
                        write_stream,
                        {},  # Empty initialization options to avoid the subscript error
                    )
            except Exception as e:
                logger.error(f"SSE connection error for user {user_id}: {str(e)}")
                if scope["type"] == "http":
                    response = PlainTextResponse("Internal Server Error", status_code=500)
                    await response(scope, receive, send)

    return Starlette(
        debug=debug,
        routes=[
            Mount("/api", api),  # FastAPI routes
            Route("/", endpoint=SSEHandler()),  # MCP SSE endpoint at root path for mcp-remote compatibility
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run Enhanced MCP Memory Server with SSE and HTTP API')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on (default: 8080)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    logger.info("Starting Enhanced MCP Memory Server with SSE transport and HTTP API...")
    logger.info(f"Server will be available at:")
    logger.info(f"  MCP SSE: http://{args.host}:{args.port}/sse")
    logger.info(f"  HTTP API: http://{args.host}:{args.port}/api/v1/")
    logger.info(f"  Health Check: http://{args.host}:{args.port}/api/v1/health")
    
    # Get the underlying MCP server - fix the function access issue
    mcp_server = mcp._mcp_server  # It's already a Server object

    # Create combined Starlette app with both SSE and HTTP support
    combined_app = create_combined_app(mcp_server, debug=args.debug)

    # Run the server
    uvicorn.run(combined_app, host=args.host, port=args.port, log_level="info")
