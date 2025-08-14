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
from starlette.responses import PlainTextResponse, StreamingResponse, JSONResponse
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
api = FastAPI(title="InMemory MCP API", version="1.0.0", description="Enhanced Memory Management MCP HTTP API")

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

class TemporalSearchRequest(BaseModel):
    temporal_query: str
    semantic_query: str = ""
    limit: int = 5

class TagSearchRequest(BaseModel):
    tags: str
    semantic_query: str = ""
    match_all_tags: bool = False
    limit: int = 5

class PeopleSearchRequest(BaseModel):
    people: str
    semantic_query: str = ""
    limit: int = 5

class TopicSearchRequest(BaseModel):
    topic_category: str
    semantic_query: str = ""
    limit: int = 5

class DeleteMemoryRequest(BaseModel):
    memory_id: str

# Enhanced MCP Tools as HTTP endpoints
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
        
        # Handle new dictionary format from add_memory_enhanced
        if isinstance(result, dict):
            return {"result": result.get("message", "Memory processed successfully")}
        else:
            return {"result": result}
            
    except Exception as e:
        logger.error(f"Failed to add memory via MCP tool: {str(e)}")
        return {"result": f"❌ Error: Failed to add memory - {str(e)}"}

@api.post("/v1/tools/search_memories")
async def search_memories_tool(
    request: SearchMemoriesRequest,
    user_id: str = Depends(authenticate_api_key)
) -> dict:
    """Enhanced memory search tool for MCP."""
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

        # Format results with rich metadata
        formatted_results = [f"🧠 Found {len(results)} memories:\n"]
        for i, result in enumerate(results, 1):
            score_emoji = (
                "🎯" if result.get("score", 0) > 0.9
                else "✅" if result.get("score", 0) > 0.8
                else "📝"
            )
            formatted_results.append(f"{score_emoji} {i}. {result['memory']}")

            # Add metadata if available
            metadata_parts = []
            if result.get("tags"):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get("people_mentioned"):
                metadata_parts.append(f"People: {', '.join(result['people_mentioned'])}")
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

        return {"result": "\n".join(formatted_results)}
    except Exception as e:
        logger.error(f"Failed to search memories via MCP tool: {str(e)}")
        return {"result": f"❌ Error: Search failed - {str(e)}"}

@api.post("/v1/tools/temporal_search")
async def temporal_search_tool(
    request: TemporalSearchRequest,
    user_id: str = Depends(authenticate_api_key)
) -> dict:
    """Temporal search tool for MCP."""
    try:
        set_current_user_id(user_id)
        results = search_engine.temporal_search(
            temporal_query=request.temporal_query,
            user_id=user_id,
            semantic_query=request.semantic_query if request.semantic_query.strip() else None,
            limit=request.limit,
        )

        if not results:
            return {"result": f"🕒 No memories found for '{request.temporal_query}'{f' + \"{request.semantic_query}\"' if request.semantic_query else ''}."}

        # Format results
        formatted_results = [
            f"🕒 Found {len(results)} memories for '{request.temporal_query}'{f' + \"{request.semantic_query}\"' if request.semantic_query else ''}:\n"
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

                if time_context:
                    formatted_results.append(f"   🕒 {' | '.join(time_context)}")

            formatted_results.append("")  # Empty line

        return {"result": "\n".join(formatted_results)}
    except Exception as e:
        logger.error(f"Failed to do temporal search via MCP tool: {str(e)}")
        return {"result": f"❌ Error: Temporal search failed - {str(e)}"}

@api.post("/v1/tools/search_by_tags")
async def search_by_tags_tool(
    request: TagSearchRequest,
    user_id: str = Depends(authenticate_api_key)
) -> dict:
    """Tag search tool for MCP."""
    try:
        set_current_user_id(user_id)
        tag_list = [tag.strip() for tag in request.tags.split(",") if tag.strip()]
        if not tag_list:
            return {"result": "❌ Please provide at least one tag to search for."}

        results = search_engine.tag_search(
            tags=tag_list,
            user_id=user_id,
            semantic_query=request.semantic_query if request.semantic_query.strip() else None,
            match_all_tags=request.match_all_tags,
            limit=request.limit,
        )

        if not results:
            match_type = "all" if request.match_all_tags else "any"
            return {"result": f"🏷️ No memories found with {match_type} of these tags: {', '.join(tag_list)}"}

        # Format results
        match_type = "all" if request.match_all_tags else "any"
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

            formatted_results.append("")  # Empty line

        return {"result": "\n".join(formatted_results)}
    except Exception as e:
        logger.error(f"Failed to search by tags via MCP tool: {str(e)}")
        return {"result": f"❌ Error: Tag search failed - {str(e)}"}

@api.post("/v1/tools/search_by_people")
async def search_by_people_tool(
    request: PeopleSearchRequest,
    user_id: str = Depends(authenticate_api_key)
) -> dict:
    """People search tool for MCP."""
    try:
        set_current_user_id(user_id)
        people_list = [person.strip() for person in request.people.split(",") if person.strip()]
        if not people_list:
            return {"result": "❌ Please provide at least one person's name to search for."}

        results = search_engine.people_search(
            people=people_list,
            user_id=user_id,
            semantic_query=request.semantic_query if request.semantic_query.strip() else None,
            limit=request.limit,
        )

        if not results:
            return {"result": f"👥 No memories found mentioning: {', '.join(people_list)}"}

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

            formatted_results.append("")  # Empty line

        return {"result": "\n".join(formatted_results)}
    except Exception as e:
        logger.error(f"Failed to search by people via MCP tool: {str(e)}")
        return {"result": f"❌ Error: People search failed - {str(e)}"}

@api.post("/v1/tools/search_by_topic")
async def search_by_topic_tool(
    request: TopicSearchRequest,
    user_id: str = Depends(authenticate_api_key)
) -> dict:
    """Topic search tool for MCP."""
    try:
        set_current_user_id(user_id)
        if not request.topic_category.strip():
            return {"result": "❌ Please provide a topic category to search for."}

        results = search_engine.topic_search(
            topic_category=request.topic_category.strip(),
            user_id=user_id,
            semantic_query=request.semantic_query if request.semantic_query.strip() else None,
            limit=request.limit,
        )

        if not results:
            return {"result": f"📂 No memories found in topic: '{request.topic_category}'"}

        # Format results
        formatted_results = [
            f"📂 Found {len(results)} memories in topic: '{request.topic_category}'\n"
        ]

        for i, result in enumerate(results, 1):
            formatted_results.append(f"📝 {i}. {result['memory']}")

            # Add metadata
            metadata_parts = []
            if result.get("tags"):
                metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
            if result.get("people_mentioned"):
                metadata_parts.append(f"People: {', '.join(result['people_mentioned'])}")

            if metadata_parts:
                formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")

            formatted_results.append("")  # Empty line

        return {"result": "\n".join(formatted_results)}
    except Exception as e:
        logger.error(f"Failed to search by topic via MCP tool: {str(e)}")
        return {"result": f"❌ Error: Topic search failed - {str(e)}"}

@api.post("/v1/tools/delete_memory")
async def delete_memory_tool(
    request: DeleteMemoryRequest,
    user_id: str = Depends(authenticate_api_key)
) -> dict:
    """Delete memory tool for MCP."""
    try:
        set_current_user_id(user_id)
        if not request.memory_id or not request.memory_id.strip():
            return {"result": "❌ Error: Memory ID is required for deletion"}
        
        # Import deletion function
        from qdrant_db import delete_user_memory
        
        # Delete the memory
        success = delete_user_memory(user_id, request.memory_id.strip())
        
        if success:
            logger.info(f"Successfully deleted memory {request.memory_id} for user {user_id}")
            return {"result": f"✅ Memory deleted successfully (ID: {request.memory_id})"}
        else:
            return {"result": f"❌ Error: Failed to delete memory {request.memory_id}"}
            
    except Exception as e:
        logger.error(f"Failed to delete memory via MCP tool: {str(e)}")
        return {"result": f"❌ Error: Failed to delete memory - {str(e)}"}

@api.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Enhanced InMemory MCP Server API",
        "version": "1.0.0",
        "tools": [
            "add_memory",
            "search_memories", 
            "temporal_search",
            "search_by_tags",
            "search_by_people",
            "search_by_topic",
            "delete_memory"
        ],
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
        "service": "Enhanced InMemory MCP Server",
        "version": "1.0.0",
        "tools_count": 7
    }

# MCP Protocol Tools Implementation
TOOLS_DEFINITIONS = [
    {
        "name": "add_memory",
        "description": "Add memory with rich metadata including tags, people mentioned, topic category, and automatic temporal data. Includes duplicate detection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_content": {"type": "string", "description": "The memory text to store"},
                "tags": {"type": "string", "description": "Comma-separated tags", "default": ""},
                "people_mentioned": {"type": "string", "description": "Comma-separated names", "default": ""},
                "topic_category": {"type": "string", "description": "Category or topic", "default": ""}
            },
            "required": ["memory_content"]
        }
    },
    {
        "name": "search_memories",
        "description": "Enhanced memory search with comprehensive filtering options including semantic similarity, metadata filtering, and temporal constraints.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Semantic search query to find relevant memories"},
                "limit": {"type": "integer", "description": "Maximum number of results", "default": 5},
                "tags": {"type": "string", "description": "Filter by comma-separated tags", "default": ""},
                "people_mentioned": {"type": "string", "description": "Filter by people names", "default": ""},
                "topic_category": {"type": "string", "description": "Filter by topic category", "default": ""},
                "temporal_filter": {"type": "string", "description": "Temporal filter", "default": ""}
            },
            "required": ["query"]
        }
    },
    {
        "name": "temporal_search",
        "description": "Search memories based on time/temporal criteria with optional semantic filtering.",
        "inputSchema": {
            "type": "object", 
            "properties": {
                "temporal_query": {"type": "string", "description": "Natural language time query (e.g., 'yesterday', 'this_week', 'weekends', 'q3', 'morning')"},
                "semantic_query": {"type": "string", "description": "Optional semantic search query", "default": ""},
                "limit": {"type": "integer", "description": "Maximum number of results", "default": 5}
            },
            "required": ["temporal_query"]
        }
    },
    {
        "name": "search_by_tags",
        "description": "Search memories by tags with optional semantic filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tags": {"type": "string", "description": "Comma-separated tags to search for"},
                "semantic_query": {"type": "string", "description": "Optional semantic search query", "default": ""},
                "match_all_tags": {"type": "boolean", "description": "Whether to match ALL tags (AND) or ANY tag (OR)", "default": False},
                "limit": {"type": "integer", "description": "Maximum number of results", "default": 5}
            },
            "required": ["tags"]
        }
    },
    {
        "name": "search_by_people",
        "description": "Search memories by people mentioned with optional semantic filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "people": {"type": "string", "description": "Comma-separated names of people to search for"},
                "semantic_query": {"type": "string", "description": "Optional semantic search query", "default": ""},
                "limit": {"type": "integer", "description": "Maximum number of results", "default": 5}
            },
            "required": ["people"]
        }
    },
    {
        "name": "search_by_topic",
        "description": "Search memories by topic category with optional semantic filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic_category": {"type": "string", "description": "Topic category to search for"},
                "semantic_query": {"type": "string", "description": "Optional semantic search query", "default": ""},
                "limit": {"type": "integer", "description": "Maximum number of results", "default": 5}
            },
            "required": ["topic_category"]
        }
    },
    {
        "name": "delete_memory",
        "description": "Delete a memory by its ID with proper user authentication.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "The ID of the memory to delete"}
            },
            "required": ["memory_id"]
        }
    }
]

async def execute_tool_call(tool_name: str, arguments: dict) -> str:
    """Execute a tool call and return the result."""
    try:
        if tool_name == "add_memory":
            result = add_memory_enhanced(
                memory_content=arguments.get("memory_content", ""),
                user_id=get_current_user_id(),
                tags=arguments.get("tags", ""),
                people_mentioned=arguments.get("people_mentioned", ""),
                topic_category=arguments.get("topic_category", ""),
            )
            if isinstance(result, dict):
                return result.get("message", "Memory processed successfully")
            return result
            
        elif tool_name == "search_memories":
            # Parse filters
            tag_list = [tag.strip() for tag in arguments.get("tags", "").split(",") if tag.strip()] or None
            people_list = [person.strip() for person in arguments.get("people_mentioned", "").split(",") if person.strip()] or None
            category = arguments.get("topic_category", "").strip() or None
            temporal = arguments.get("temporal_filter", "").strip() or None

            results = search_engine.search_memories(
                query=arguments.get("query", ""),
                user_id=get_current_user_id(),
                limit=arguments.get("limit", 5),
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
                score_emoji = "🎯" if result.get("score", 0) > 0.9 else "✅" if result.get("score", 0) > 0.8 else "📝"
                formatted_results.append(f"{score_emoji} {i}. {result['memory']}")
                
                # Add metadata
                metadata_parts = []
                if result.get("tags"):
                    metadata_parts.append(f"Tags: {', '.join(result['tags'])}")
                if result.get("people_mentioned"):
                    metadata_parts.append(f"People: {', '.join(result['people_mentioned'])}")
                if result.get("topic_category"):
                    metadata_parts.append(f"Topic: {result['topic_category']}")
                    
                if metadata_parts:
                    formatted_results.append(f"   📊 {' | '.join(metadata_parts)}")
                if result.get("score"):
                    formatted_results.append(f"   🎯 Similarity: {result['score']:.3f}")
                formatted_results.append("")
                
            return "\n".join(formatted_results)
            
        elif tool_name == "temporal_search":
            results = search_engine.temporal_search(
                temporal_query=arguments.get("temporal_query", ""),
                user_id=get_current_user_id(),
                semantic_query=arguments.get("semantic_query", "").strip() or None,
                limit=arguments.get("limit", 5),
            )
            
            if not results:
                return f"🕒 No memories found for '{arguments.get('temporal_query', '')}'."
                
            formatted_results = [f"🕒 Found {len(results)} memories for '{arguments.get('temporal_query', '')}':\n"]
            for i, result in enumerate(results, 1):
                formatted_results.append(f"📝 {i}. {result['memory']}")
                formatted_results.append("")
            return "\n".join(formatted_results)
            
        elif tool_name == "search_by_tags":
            tag_list = [tag.strip() for tag in arguments.get("tags", "").split(",") if tag.strip()]
            if not tag_list:
                return "❌ Please provide at least one tag to search for."
                
            results = search_engine.tag_search(
                tags=tag_list,
                user_id=get_current_user_id(),
                semantic_query=arguments.get("semantic_query", "").strip() or None,
                match_all_tags=arguments.get("match_all_tags", False),
                limit=arguments.get("limit", 5),
            )
            
            if not results:
                match_type = "all" if arguments.get("match_all_tags", False) else "any"
                return f"🏷️ No memories found with {match_type} of these tags: {', '.join(tag_list)}"
                
            match_type = "all" if arguments.get("match_all_tags", False) else "any"
            formatted_results = [f"🏷️ Found {len(results)} memories with {match_type} of: {', '.join(tag_list)}\n"]
            for i, result in enumerate(results, 1):
                formatted_results.append(f"📝 {i}. {result['memory']}")
                formatted_results.append("")
            return "\n".join(formatted_results)
            
        elif tool_name == "search_by_people":
            people_list = [person.strip() for person in arguments.get("people", "").split(",") if person.strip()]
            if not people_list:
                return "❌ Please provide at least one person's name to search for."
                
            results = search_engine.people_search(
                people=people_list,
                user_id=get_current_user_id(),
                semantic_query=arguments.get("semantic_query", "").strip() or None,
                limit=arguments.get("limit", 5),
            )
            
            if not results:
                return f"👥 No memories found mentioning: {', '.join(people_list)}"
                
            formatted_results = [f"👥 Found {len(results)} memories mentioning: {', '.join(people_list)}\n"]
            for i, result in enumerate(results, 1):
                formatted_results.append(f"📝 {i}. {result['memory']}")
                formatted_results.append("")
            return "\n".join(formatted_results)
            
        elif tool_name == "search_by_topic":
            topic = arguments.get("topic_category", "").strip()
            if not topic:
                return "❌ Please provide a topic category to search for."
                
            results = search_engine.topic_search(
                topic_category=topic,
                user_id=get_current_user_id(),
                semantic_query=arguments.get("semantic_query", "").strip() or None,
                limit=arguments.get("limit", 5),
            )
            
            if not results:
                return f"📂 No memories found in topic: '{topic}'"
                
            formatted_results = [f"📂 Found {len(results)} memories in topic: '{topic}'\n"]
            for i, result in enumerate(results, 1):
                formatted_results.append(f"📝 {i}. {result['memory']}")
                formatted_results.append("")
            return "\n".join(formatted_results)
            
        elif tool_name == "delete_memory":
            memory_id = arguments.get("memory_id", "").strip()
            if not memory_id:
                return "❌ Error: Memory ID is required for deletion"
                
            from qdrant_db import delete_user_memory
            success = delete_user_memory(get_current_user_id(), memory_id)
            
            if success:
                return f"✅ Memory deleted successfully (ID: {memory_id})"
            else:
                return f"❌ Error: Failed to delete memory {memory_id}"
                
        else:
            return f"❌ Error: Unknown tool '{tool_name}'"
            
    except Exception as e:
        logger.error(f"Tool execution failed for {tool_name}: {str(e)}")
        return f"❌ Error: Tool execution failed - {str(e)}"

async def handle_mcp_post(request: Request):
    """Handle MCP protocol POST requests."""
    # Authentication
    headers = dict(request.headers)
    auth_header = headers.get("authorization", "")
    
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"error": "Unauthorized: Bearer token required"}, status_code=401)
    
    api_key = auth_header.replace("Bearer ", "")
    user_manager = get_mongo_user_manager()
    user_id = user_manager.validate_api_key(api_key)
    
    if not user_id:
        return JSONResponse({"error": "Unauthorized: Invalid API key"}, status_code=401)
    
    set_current_user_id(user_id)
    
    # Parse MCP message
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        msg_id = body.get("id")
        
        logger.info(f"MCP message: {method} for user {user_id}")
        
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {"listChanged": True}
                    },
                    "serverInfo": {
                        "name": "Enhanced InMemory",
                        "version": "1.0.0"
                    }
                }
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": TOOLS_DEFINITIONS
                }
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            result = await execute_tool_call(tool_name, arguments)
            
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result
                        }
                    ]
                }
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            
        return JSONResponse(response)
        
    except Exception as e:
        logger.error(f"MCP protocol error: {str(e)}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": body.get("id") if 'body' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }, status_code=500)

async def handle_mcp_get(request: Request):
    """Handle MCP protocol GET requests (for info/testing)."""
    # Authentication
    headers = dict(request.headers)
    auth_header = headers.get("authorization", "")
    
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"error": "Unauthorized: Bearer token required"}, status_code=401)
    
    api_key = auth_header.replace("Bearer ", "")
    user_manager = get_mongo_user_manager()
    user_id = user_manager.validate_api_key(api_key)
    
    if not user_id:
        return JSONResponse({"error": "Unauthorized: Invalid API key"}, status_code=401)
    
    # Return server info and tools for testing
    return JSONResponse({
        "jsonrpc": "2.0",
        "result": {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {"listChanged": True}},
            "serverInfo": {"name": "Enhanced InMemory", "version": "1.0.0"},
            "tools": TOOLS_DEFINITIONS
        }
    })

def create_app(*, debug: bool = False) -> Starlette:
    """Create a Starlette application that serves both MCP and FastAPI HTTP endpoints."""
    return Starlette(
        debug=debug,
        routes=[
            Mount("/api", api),  # FastAPI routes
            Route("/", endpoint=handle_mcp_post, methods=["POST"]),  # MCP POST protocol
            Route("/", endpoint=handle_mcp_get, methods=["GET"]),  # MCP GET info
        ],
    )

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run Enhanced MCP Memory Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on (default: 8080)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    logger.info("Starting Enhanced MCP Memory Server...")
    logger.info(f"Server will be available at:")
    logger.info(f"  MCP: http://{args.host}:{args.port}/")
    logger.info(f"  HTTP API: http://{args.host}:{args.port}/api/v1/")
    logger.info(f"  Health Check: http://{args.host}:{args.port}/api/v1/health")
    logger.info(f"  Tools: 7 advanced memory tools available")
    
    # Create app
    app = create_app(debug=args.debug)

    # Run the server
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
