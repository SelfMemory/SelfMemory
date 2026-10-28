"""Utility functions for SelfMemory MCP Server.

Clean, modular helper functions following DRY principle.
"""

import json
import logging
from collections.abc import Callable
from functools import wraps

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def handle_tool_errors(func: Callable) -> Callable:
    """Decorator to handle tool errors and return proper MCP error format.

    Args:
        func: Tool function to wrap

    Returns:
        Wrapped function with error handling
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTP exceptions (auth failures)
            raise
        except Exception as e:
            logger.error(f"Tool {func.__name__} failed: {e}")
            return create_tool_error(str(e))

    return wrapper


def create_tool_error(error_message: str) -> dict:
    """Create standardized tool error response.

    Args:
        error_message: Error message to return

    Returns:
        Dict with MCP error format
    """
    error_obj = {"error": error_message}

    return {
        "content": [{"type": "text", "text": json.dumps(error_obj)}],
        "isError": True,
    }


def create_tool_success(data: dict) -> dict:
    """Create standardized tool success response with structured content.

    Args:
        data: Success data dictionary

    Returns:
        Dict with both text content and structured content
    """
    return {
        "content": [{"type": "text", "text": json.dumps(data)}],
        "structuredContent": data,
    }
