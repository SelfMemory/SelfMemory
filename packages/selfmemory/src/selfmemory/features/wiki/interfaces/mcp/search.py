"""Search tool output (MCP 2025-06-18 format, as ChatGPT deep research expects)."""

import json

from selfmemory.platform.mcp.config import config


def page_url(path: str) -> str:
    return f"{config.hydra.mcp_server_url}/wiki/{path}"


def format_search_results(results: list[dict]) -> dict:
    """Wiki search hits as ``{id, title, url}``; ``id`` is the page path,
    which ``fetch`` accepts."""
    formatted = [
        {
            "id": hit.get("path", ""),
            "title": hit.get("title") or hit.get("path", ""),
            "url": page_url(hit.get("path", "")),
            "snippet": hit.get("snippet", ""),
        }
        for hit in results
    ]
    response_obj = {"results": formatted}
    return {
        "content": [{"type": "text", "text": json.dumps(response_obj)}],
        "structuredContent": response_obj,
    }
