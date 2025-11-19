"""Token validation caching to reduce repeated validation overhead.

This module implements a TTL-based cache for both OAuth tokens and API keys
to avoid hitting Hydra or Core server on every request.
"""

import hashlib
import logging

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Cache for OAuth token validation results (5 minute TTL)
# Key: token hash, Value: TokenContext dict
_oauth_token_cache = TTLCache(maxsize=1000, ttl=300)

# Cache for API key validation results (10 minute TTL)
# Key: api key hash, Value: TokenContext dict
_api_key_cache = TTLCache(maxsize=1000, ttl=600)


def _hash_token(token: str) -> str:
    """Create a secure hash of the token for cache key.

    Args:
        token: The token string to hash

    Returns:
        SHA256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def get_oauth_token_from_cache(token: str) -> dict | None:
    """Retrieve cached OAuth token validation result.

    Args:
        token: OAuth token string

    Returns:
        Cached TokenContext dict if found, None otherwise
    """
    token_hash = _hash_token(token)
    cached = _oauth_token_cache.get(token_hash)

    if cached:
        logger.info(
            f"💾 CACHE HIT: OAuth token for user {cached.get('user_id')} (cache size: {len(_oauth_token_cache)})"
        )
        return cached

    logger.info(
        f"🔍 CACHE MISS: OAuth token needs validation (cache size: {len(_oauth_token_cache)})"
    )
    return None


def set_oauth_token_in_cache(token: str, token_context: dict) -> None:
    """Store OAuth token validation result in cache.

    Args:
        token: OAuth token string
        token_context: TokenContext dict to cache
    """
    token_hash = _hash_token(token)
    _oauth_token_cache[token_hash] = token_context
    logger.info(
        f"💾 CACHED: OAuth token for user {token_context.get('user_id')} "
        f"[TTL: 5min, size: {len(_oauth_token_cache)}/{_oauth_token_cache.maxsize}]"
    )


def get_api_key_from_cache(api_key: str) -> dict | None:
    """Retrieve cached API key validation result.

    Args:
        api_key: API key string

    Returns:
        Cached TokenContext dict if found, None otherwise
    """
    key_hash = _hash_token(api_key)
    cached = _api_key_cache.get(key_hash)

    if cached:
        logger.info(
            f"💾 CACHE HIT: API key for user {cached.get('user_id')} (cache size: {len(_api_key_cache)})"
        )
        return cached

    logger.info(
        f"🔍 CACHE MISS: API key needs validation (cache size: {len(_api_key_cache)})"
    )
    return None


def set_api_key_in_cache(api_key: str, token_context: dict) -> None:
    """Store API key validation result in cache.

    Args:
        api_key: API key string
        token_context: TokenContext dict to cache
    """
    key_hash = _hash_token(api_key)
    _api_key_cache[key_hash] = token_context
    logger.info(
        f"💾 CACHED: API key for user {token_context.get('user_id')} "
        f"[TTL: 10min, size: {len(_api_key_cache)}/{_api_key_cache.maxsize}]"
    )


def clear_caches() -> None:
    """Clear all token caches (useful for testing or forced refresh)."""
    _oauth_token_cache.clear()
    _api_key_cache.clear()
    logger.info("🧹 Cleared all token caches")


def get_cache_stats() -> dict:
    """Get cache statistics for monitoring.

    Returns:
        Dict with cache sizes and TTL info
    """
    return {
        "oauth_cache": {
            "size": len(_oauth_token_cache),
            "maxsize": _oauth_token_cache.maxsize,
            "ttl": _oauth_token_cache.ttl,
        },
        "api_key_cache": {
            "size": len(_api_key_cache),
            "maxsize": _api_key_cache.maxsize,
            "ttl": _api_key_cache.ttl,
        },
    }
