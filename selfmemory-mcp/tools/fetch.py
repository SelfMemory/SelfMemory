"""Fetch tool for retrieving complete memory documents (MCP 2025-06-18 format)."""

import json

from config import config


def format_fetch_result(memory: dict) -> dict:
    """Format memory for ChatGPT.
    
    Args:
        memory: Memory document from SelfMemory API
        
    Returns:
        Dict with content array and structuredContent
    """
    response_obj = {
        "id": memory.get("id", ""),
        "title": memory.get("content", "")[:100],
        "text": memory.get("content", ""),
        "url": f"{config.hydra.mcp_server_url}/memories/{memory.get('id', '')}",
        "metadata": memory.get("metadata", {})
    }

    return {
        "content": [{"type": "text", "text": json.dumps(response_obj)}],
        "structuredContent": response_obj
    }


# Output schema for validation
FETCH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "Memory ID"},
        "title": {"type": "string", "description": "Memory title"},
        "text": {"type": "string", "description": "Full memory content"},
        "url": {"type": "string", "description": "Memory URL"},
        "metadata": {"type": "object", "description": "Additional metadata"}
    },
    "required": ["id", "title", "text", "url"]
}
