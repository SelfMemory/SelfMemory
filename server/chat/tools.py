"""
Chat tool definitions for LLM function calling

CHAT-201: Define search_memories Tool Schema
"""

from typing import Any

from pydantic import BaseModel, Field


class SearchMemoriesParams(BaseModel):
    """Parameters for the search_memories tool"""

    query: str = Field(
        ...,
        description="The search query to find relevant memories. Use natural language based on what the user is asking about.",
    )
    limit: int = Field(
        default=5,
        description="Maximum number of memories to return. Default is 5.",
        ge=1,
        le=20,
    )


class AddMemoryParams(BaseModel):
    """Parameters for the add_memory tool (Phase 3)"""

    content: str = Field(
        ..., description="The information to save as a memory. Be concise but complete."
    )
    tags: list[str] | None = Field(
        default=None,
        description='Relevant tags for categorizing the memory (e.g., "marketing", "q2", "feature-request")',
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata like category and people mentioned",
    )


# Tool definitions in OpenAI function calling format
SEARCH_MEMORIES_TOOL = {
    "type": "function",
    "function": {
        "name": "search_memories",
        "description": (
            "Search for relevant memories based on a query. Use this when the user asks about "
            "past information, previous conversations, or anything that might have been discussed "
            "or saved before. The search uses semantic similarity to find the most relevant memories."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant memories. Use natural language based on what the user is asking about.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of memories to return. Default is 5.",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        },
    },
}

ADD_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "add_memory",
        "description": (
            "Save important information as a memory for future reference. Use this when the user "
            "shares information that should be remembered, such as decisions, preferences, facts, "
            "ideas, or important details."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The information to save as a memory. Be concise but complete.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": 'Relevant tags for categorizing the memory (e.g., "marketing", "q2", "feature-request")',
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata like category and people mentioned",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": 'Category like "meeting", "decision", "preference", "idea", "fact"',
                        },
                        "people": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of people mentioned in the memory",
                        },
                    },
                },
            },
            "required": ["content"],
        },
    },
}

# All available tools
AVAILABLE_TOOLS = [
    SEARCH_MEMORIES_TOOL,
    ADD_MEMORY_TOOL,  # Phase 3: Memory addition enabled
]
