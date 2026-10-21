"""Fetch tool output: one wiki page in full."""

import json

from selfmemory.features.wiki.interfaces.mcp.search import page_url


def format_fetch_result(page: dict) -> dict:
    path = page.get("path", "")
    text = page.get("content")
    if text is None:
        text = f"(binary file, {page.get('size', 0)} bytes)"
    title = path.rsplit("/", 1)[-1].removesuffix(".md")
    for line in text.splitlines():
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip("\"'") or title
            break
    response_obj = {
        "id": path,
        "title": title,
        "text": text,
        "url": page_url(path),
        "metadata": {"side": page.get("side")},
    }
    return {
        "content": [{"type": "text", "text": json.dumps(response_obj)}],
        "structuredContent": response_obj,
    }
