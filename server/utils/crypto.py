"""
Cryptographic utilities for secure hashing.

This module provides secure password/secret hashing using Argon2id,
the winner of the Password Hashing Competition.

Following Uncle Bob's Clean Code principles:
- Single Responsibility: Only handles cryptographic operations
- No fallback mechanisms
- Clear error messages
- Simple and understandable
"""

import logging

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

logger = logging.getLogger(__name__)

# Use argon2-cffi's secure defaults:
# - time_cost=2 (number of iterations)
# - memory_cost=65536 (64 MiB memory usage)
# - parallelism=1 (number of parallel threads)
# - hash_len=32 (32 bytes output)
# - salt_len=16 (16 bytes salt)
_password_hasher = PasswordHasher()


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using Argon2id.

    Argon2id is the recommended algorithm for password/secret hashing.
    It is memory-hard and resistant to GPU/ASIC attacks.

    Args:
        api_key: The API key to hash

    Returns:
        str: The Argon2 hash (includes algorithm, parameters, salt, and hash)

    Raises:
        ValueError: If api_key is empty or invalid
    """
    if not api_key or not isinstance(api_key, str):
        raise ValueError("API key must be a non-empty string")

    try:
        return _password_hasher.hash(api_key)
    except Exception as e:
        logger.error("Failed to hash API key due to an internal error.")
        raise ValueError("Failed to hash API key due to an internal error.") from e


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against a stored Argon2 hash.

    Args:
        api_key: The API key to verify
        stored_hash: The Argon2 hash to verify against

    Returns:
        bool: True if the API key matches the hash, False otherwise

    Raises:
        ValueError: If inputs are invalid
    """
    if not api_key or not isinstance(api_key, str):
        raise ValueError("API key must be a non-empty string")

    if not stored_hash or not isinstance(stored_hash, str):
        raise ValueError("Stored hash must be a non-empty string")

    try:
        _password_hasher.verify(stored_hash, api_key)
        return True
    except (VerifyMismatchError, InvalidHashError):
        # Key doesn't match or hash is invalid
        return False
    except Exception as e:
        logger.error("Failed to verify API key")
        raise ValueError("Failed to verify API key") from e
