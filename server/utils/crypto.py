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
import os

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Argon2 hasher for one-way hashing (auth verification)
_password_hasher = PasswordHasher()

# Fernet for reversible encryption (API key storage)
_encryption_key = os.getenv("MASTER_ENCRYPTION_KEY")
_fernet = Fernet(_encryption_key.encode()) if _encryption_key else None


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


def encrypt_api_key(api_key: str) -> str | None:
    """Encrypt an API key for reversible storage. Returns None if encryption is not configured."""
    if not _fernet:
        return None
    return _fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str | None:
    """Decrypt a stored API key. Returns None if decryption fails or is not configured."""
    if not _fernet or not encrypted_key:
        return None
    try:
        return _fernet.decrypt(encrypted_key.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt API key - invalid token or wrong key")
        return None
