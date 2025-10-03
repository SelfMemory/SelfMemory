"""
Rate Limiting Utility

Provides a shared rate limiter instance that can be imported by
main.py and router files for consistent rate limiting across the application.

Clean Code Principles:
- Single source of truth for rate limiter configuration
- No hardcoded values - uses config module
- Clear function names
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import config


def get_rate_limit_key(request: Request) -> str:
    """
    Generate rate limit key based on authenticated user or IP address.
    Prefer user-based rate limiting for authenticated requests.

    Args:
        request: FastAPI request object

    Returns:
        str: Rate limit key for the request
    """
    # Try to get user from auth context (if available)
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # For authenticated requests, use a user-based key
            # This is more accurate than IP-based for multi-user scenarios
            return f"user:{auth_header[:20]}"  # Use token prefix as identifier
    except Exception:
        pass

    # Fall back to IP-based rate limiting for unauthenticated requests
    return get_remote_address(request)


# Initialize shared rate limiter instance
limiter = Limiter(
    key_func=get_rate_limit_key,
    enabled=config.security.RATE_LIMIT_ENABLED,
    storage_uri=config.security.RATE_LIMIT_STORAGE_URL or "memory://",
    default_limits=[config.rate_limit.DEFAULT],
)
