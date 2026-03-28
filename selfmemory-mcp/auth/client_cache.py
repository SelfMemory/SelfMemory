"""SelfMemoryClient caching to reduce connection overhead and improve performance.

This module implements a TTL-based cache for SelfMemoryClient instances
to avoid creating new HTTP connections on every request. This significantly
improves performance by reusing TCP connections and TLS sessions.

Performance Impact:
- Local: Reduces latency from ~0.8s to ~0.3s
- Production: Reduces latency from ~3s to ~0.8s (avoids TLS handshake)
"""

import hashlib
import logging
import threading

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Cache for SelfMemoryClient instances (10 minute TTL)
# Key: api_key hash, Value: SelfMemoryClient instance
_client_cache = TTLCache(maxsize=100, ttl=600)
_client_lock = threading.Lock()


def _hash_api_key(api_key: str) -> str:
    """Create a hash of the API key for cache key lookup using SHA256.

    Tokens and API keys are already high-entropy cryptographic strings,
    so PBKDF2 password-stretching is unnecessary overhead for cache keys.

    Args:
        api_key: The API key string to hash

    Returns:
        SHA256 hash of the API key (hex)
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_client_from_cache(api_key: str):
    """Retrieve cached SelfMemoryClient instance.

    Args:
        api_key: API key string

    Returns:
        Cached SelfMemoryClient instance if found, None otherwise
    """
    key_hash = _hash_api_key(api_key)
    with _client_lock:
        cached = _client_cache.get(key_hash)

    if cached:
        logger.info(
            f"💾 CLIENT CACHE HIT: Reusing connection (cache size: {len(_client_cache)})"
        )
        return cached

    logger.info(
        f"🔍 CLIENT CACHE MISS: Creating new client (cache size: {len(_client_cache)})"
    )
    return None


def set_client_in_cache(api_key: str, client) -> None:
    """Store SelfMemoryClient instance in cache.

    Args:
        api_key: API key string
        client: SelfMemoryClient instance to cache
    """
    key_hash = _hash_api_key(api_key)
    with _client_lock:
        _client_cache[key_hash] = client
    logger.info(
        f"💾 CACHED: SelfMemoryClient "
        f"[TTL: 10min, size: {len(_client_cache)}/{_client_cache.maxsize}]"
    )


def clear_cache() -> None:
    """Clear client cache (useful for testing or forced refresh)."""
    # Close all cached clients before clearing
    for client in _client_cache.values():
        try:
            if hasattr(client, "close"):
                client.close()
        except Exception as e:
            logger.warning(f"Error closing cached client: {e}")

    _client_cache.clear()
    logger.info("🧹 Cleared client cache")


def get_or_create_client(cache_key: str, factory_fn):
    """Get cached client or create new one using factory function.

    This eliminates DRY violations by centralizing the cache-check-create-store pattern.

    Args:
        cache_key: Key to use for caching (API key or OAuth token)
        factory_fn: Callable that creates a new client instance

    Returns:
        SelfMemoryClient instance (either cached or newly created)
    """
    cached = get_client_from_cache(cache_key)
    if cached:
        return cached

    client = factory_fn()
    set_client_in_cache(cache_key, client)
    return client


def get_cache_stats() -> dict:
    """Get cache statistics for monitoring.

    Returns:
        Dict with cache size and TTL info
    """
    return {
        "client_cache": {
            "size": len(_client_cache),
            "maxsize": _client_cache.maxsize,
            "ttl": _client_cache.ttl,
        },
    }
