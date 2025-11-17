"""Search tool for ChatGPT deep research (MCP 2025-06-18 format)."""

import json

from config import config


def format_search_results(results: list[dict]) -> dict:
    """Format search results for ChatGPT.

    Args:
        results: List of memory search results

    Returns:
        Dict with content array and structuredContent
    """
    formatted_results = [
        {
            "id": memory.get("id", ""),
            "title": memory.get("content", "")[:100],
            "url": f"{config.hydra.mcp_server_url}/memories/{memory.get('id', '')}",
        }
        for memory in results
    ]

    response_obj = {"results": formatted_results}

    return {
        "content": [{"type": "text", "text": json.dumps(response_obj)}],
        "structuredContent": response_obj,
    }


# Output schema for validation
SEARCH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Memory ID"},
                    "title": {"type": "string", "description": "Memory title"},
                    "url": {"type": "string", "description": "Memory URL"},
                },
                "required": ["id", "title", "url"],
            },
        }
    },
    "required": ["results"],
}
