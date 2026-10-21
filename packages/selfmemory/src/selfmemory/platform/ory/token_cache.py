"""Token validation caching for Core server.

Reduces repeated Hydra introspection and Kratos session validation calls.
Uses TTL-based in-memory cache — same pattern as selfmemory-mcp/auth/token_cache.py.
"""

import hashlib
import logging
import threading

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Hydra token validation cache (5 minute TTL)
_hydra_token_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)
_hydra_lock = threading.Lock()

# Kratos session validation cache (5 minute TTL)
_kratos_session_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)
_kratos_lock = threading.Lock()


def _hash_key(key: str) -> str:
    """SHA256 hash for cache key lookup."""
    return hashlib.sha256(key.encode()).hexdigest()


def get_cached_hydra_token(access_token: str):
    """Return cached HydraToken or None on miss."""
    with _hydra_lock:
        return _hydra_token_cache.get(_hash_key(access_token))


def cache_hydra_token(access_token: str, hydra_token) -> None:
    """Store validated HydraToken in cache."""
    with _hydra_lock:
        _hydra_token_cache[_hash_key(access_token)] = hydra_token
    logger.debug(
        f"Cached Hydra token [size: {len(_hydra_token_cache)}/{_hydra_token_cache.maxsize}]"
    )


def get_cached_kratos_session(session_cookie: str):
    """Return cached KratosSession or None on miss."""
    with _kratos_lock:
        return _kratos_session_cache.get(_hash_key(session_cookie))


def cache_kratos_session(session_cookie: str, kratos_session) -> None:
    """Store validated KratosSession in cache."""
    with _kratos_lock:
        _kratos_session_cache[_hash_key(session_cookie)] = kratos_session
    logger.debug(
        f"Cached Kratos session [size: {len(_kratos_session_cache)}/{_kratos_session_cache.maxsize}]"
    )
