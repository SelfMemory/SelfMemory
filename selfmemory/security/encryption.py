"""
Simple AES encryption/decryption for memory content.
Follows Uncle Bob's clean code principles - single responsibility, simple functions.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class MemoryEncryption:
    """
    Simple encryption class for memory content.
    Uses Fernet (AES 128) for symmetric encryption.
    """

    def __init__(self, user_id: str):
        """
        Initialize encryption for a specific user.

        Args:
            user_id: User identifier for key derivation
        """
        self.user_id = user_id
        self._fernet = self._create_fernet_key()

    def _create_fernet_key(self) -> Fernet:
        """
        Create Fernet encryption key from user_id.
        Uses deterministic key derivation for consistency.

        Returns:
            Fernet encryption instance
        """
        # Simple salt for key derivation (constant for consistency)
        salt = b"mem_mcp_salt_2024"

        # Derive key from user_id + salt
        key_material = f"{self.user_id}{salt.decode()}".encode()
        key_hash = hashlib.sha256(key_material).digest()

        # Fernet requires base64-encoded 32-byte key
        fernet_key = base64.urlsafe_b64encode(key_hash)

        return Fernet(fernet_key)

    def encrypt_text(self, text: str) -> str:
        """
        Encrypt a text string.

        Args:
            text: Plain text to encrypt

        Returns:
            Base64-encoded encrypted text

        Raises:
            Exception: If encryption fails
        """
        if not text:
            return ""

        try:
            encrypted_bytes = self._fernet.encrypt(text.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
        except Exception as e:
            logger.error(f"Encryption failed for user {self.user_id}: {str(e)}")
            raise Exception(f"Encryption failed: {str(e)}") from e

    def decrypt_text(self, encrypted_text: str) -> str:
        """
        Decrypt an encrypted text string.

        Args:
            encrypted_text: Base64-encoded encrypted text

        Returns:
            Plain text string

        Raises:
            Exception: If decryption fails
        """
        if not encrypted_text:
            return ""

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Decryption failed for user {self.user_id}: {str(e)}")
            raise Exception(f"Decryption failed: {str(e)}") from e

    def encrypt_list(self, text_list: list[str]) -> list[str]:
        """
        Encrypt a list of strings.

        Args:
            text_list: List of plain text strings

        Returns:
            List of encrypted strings
        """
        if not text_list:
            return []

        return [self.encrypt_text(text) for text in text_list if text]

    def decrypt_list(self, encrypted_list: list[str]) -> list[str]:
        """
        Decrypt a list of encrypted strings.

        Args:
            encrypted_list: List of encrypted strings

        Returns:
            List of plain text strings
        """
        if not encrypted_list:
            return []

        return [self.decrypt_text(text) for text in encrypted_list if text]


def get_user_encryption(user_id: str) -> MemoryEncryption:
    """
    Get encryption instance for a user.
    Factory function for clean interface.

    Args:
        user_id: User identifier

    Returns:
        MemoryEncryption instance for the user
    """
    return MemoryEncryption(user_id)


def encrypt_memory_payload(payload: dict, user_id: str) -> dict:
    """
    Encrypt sensitive fields in memory payload.

    Args:
        payload: Memory payload dictionary
        user_id: User identifier

    Returns:
        Payload with encrypted sensitive fields
    """
    logger.info(f"🔐 encrypt_memory_payload called for user: {user_id}")
    logger.info(f"🔐 Payload fields to encrypt: {list(payload.keys())}")

    try:
        logger.info(f"🔐 Creating encryption instance for user: {user_id}")
        encryption = get_user_encryption(user_id)
        logger.info("🔐 ✅ Encryption instance created successfully")

        encrypted_payload = payload.copy()

        # Encrypt main memory content
        if "memory" in payload:
            original_memory = payload["memory"]
            logger.info(
                f"🔐 Encrypting main memory content (length: {len(original_memory)})"
            )
            logger.info(f"🔐 Original memory preview: '{original_memory[:50]}...'")

            encrypted_memory = encryption.encrypt_text(original_memory)
            encrypted_payload["memory"] = encrypted_memory

            logger.info(
                f"🔐 ✅ Memory content encrypted (new length: {len(encrypted_memory)})"
            )
            logger.info(f"🔐 Encrypted memory preview: '{encrypted_memory[:50]}...'")
        else:
            logger.warning("🔐 ⚠️ No 'memory' field found in payload")

        # Encrypt metadata fields
        if "tags" in payload and payload["tags"]:
            logger.info(f"🔐 Encrypting tags: {payload['tags']}")
            encrypted_payload["tags"] = encryption.encrypt_list(payload["tags"])
            logger.info("🔐 ✅ Tags encrypted")

        if "people_mentioned" in payload and payload["people_mentioned"]:
            logger.info(
                f"🔐 Encrypting people_mentioned: {payload['people_mentioned']}"
            )
            encrypted_payload["people_mentioned"] = encryption.encrypt_list(
                payload["people_mentioned"]
            )
            logger.info("🔐 ✅ People mentioned encrypted")

        if "topic_category" in payload and payload["topic_category"]:
            logger.info(f"🔐 Encrypting topic_category: '{payload['topic_category']}'")
            encrypted_payload["topic_category"] = encryption.encrypt_text(
                payload["topic_category"]
            )
            logger.info("🔐 ✅ Topic category encrypted")

        logger.info("🔐 ✅ encrypt_memory_payload completed successfully")
        return encrypted_payload

    except Exception as e:
        logger.error(f"🔐 ❌ CRITICAL: encrypt_memory_payload failed: {str(e)}")
        logger.error(f"🔐 ❌ Exception type: {type(e).__name__}")
        logger.error(
            "🔐 ❌ This is a SECURITY ISSUE - payload will be returned unencrypted!"
        )
        # Re-raise the exception so the caller knows encryption failed
        raise e


def decrypt_memory_payload(payload: dict, user_id: str) -> dict:
    """
    Decrypt sensitive fields in memory payload.

    Args:
        payload: Memory payload with encrypted fields
        user_id: User identifier

    Returns:
        Payload with decrypted readable fields
    """
    encryption = get_user_encryption(user_id)
    decrypted_payload = payload.copy()

    # Decrypt main memory content
    if "memory" in payload:
        decrypted_payload["memory"] = encryption.decrypt_text(payload["memory"])

    # Decrypt metadata fields
    if "tags" in payload and payload["tags"]:
        decrypted_payload["tags"] = encryption.decrypt_list(payload["tags"])

    if "people_mentioned" in payload and payload["people_mentioned"]:
        decrypted_payload["people_mentioned"] = encryption.decrypt_list(
            payload["people_mentioned"]
        )

    if "topic_category" in payload and payload["topic_category"]:
        decrypted_payload["topic_category"] = encryption.decrypt_text(
            payload["topic_category"]
        )

    return decrypted_payload


if __name__ == "__main__":
    # Simple test
    test_user_id = "test_user_123"
    encryption = get_user_encryption(test_user_id)

    test_text = "This is my secret memory"
    encrypted = encryption.encrypt_text(test_text)
    decrypted = encryption.decrypt_text(encrypted)

    print(f"Original: {test_text}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_text == decrypted}")
