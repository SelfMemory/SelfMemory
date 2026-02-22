"""Memory payload encryption using Fernet (AES-128) with HKDF-derived keys."""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

SENSITIVE_FIELDS = ["data", "tags", "people_mentioned", "topic_category"]


def derive_encryption_key(master_key_b64: str, identifier: str) -> bytes:
    """Derive a Fernet-compatible key from master key + identifier using HKDF.

    Args:
        master_key_b64: Base64-encoded master key (from env var).
        identifier: Context identifier (project_id or user_id).

    Returns:
        Base64-encoded 32-byte key suitable for Fernet.
    """
    master_bytes = base64.urlsafe_b64decode(master_key_b64.encode())
    hkdf = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=None,
        info=identifier.encode(),
    )
    derived = hkdf.derive(master_bytes)
    return base64.urlsafe_b64encode(derived)


def _get_identifier(payload: dict) -> str:
    """Extract the encryption identifier from a payload.

    Uses project_id if present, otherwise falls back to user_id.
    """
    identifier = payload.get("project_id") or payload.get("user_id")
    if not identifier:
        raise ValueError("Payload must contain project_id or user_id for encryption")
    return str(identifier).strip()


def encrypt_payload(payload: dict, master_key: str) -> dict:
    """Encrypt sensitive fields in a memory payload before storage.

    Args:
        payload: Memory payload dict with plaintext fields.
        master_key: Base64-encoded master encryption key.

    Returns:
        New dict with sensitive fields encrypted and 'encrypted' flag set.
    """
    identifier = _get_identifier(payload)
    fernet_key = derive_encryption_key(master_key, identifier)
    fernet = Fernet(fernet_key)

    encrypted = payload.copy()

    for field in SENSITIVE_FIELDS:
        value = encrypted.get(field)
        if value:
            encrypted[field] = fernet.encrypt(str(value).encode()).decode()

    encrypted["encrypted"] = True
    return encrypted


def decrypt_payload(payload: dict, master_key: str) -> dict:
    """Decrypt sensitive fields in a memory payload after retrieval.

    Returns the payload as-is if it's not marked as encrypted.

    Args:
        payload: Memory payload dict (possibly encrypted).
        master_key: Base64-encoded master encryption key.

    Returns:
        New dict with sensitive fields decrypted.
    """
    if not payload.get("encrypted"):
        return payload

    identifier = _get_identifier(payload)
    fernet_key = derive_encryption_key(master_key, identifier)
    fernet = Fernet(fernet_key)

    decrypted = payload.copy()

    for field in SENSITIVE_FIELDS:
        value = decrypted.get(field)
        if value:
            try:
                decrypted[field] = fernet.decrypt(value.encode()).decode()
            except InvalidToken:
                logger.error("Decryption failed for field '%s'", field)
                raise

    return decrypted
