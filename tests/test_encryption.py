"""Unit tests for memory payload encryption."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from selfmemory.security.encryption import (
    decrypt_payload,
    derive_encryption_key,
    encrypt_payload,
)

MASTER_KEY = Fernet.generate_key().decode()


def _make_payload(
    data="secret memory",
    user_id="user_123",
    project_id=None,
    tags="work,personal",
    people_mentioned="Alice,Bob",
    topic_category="meeting",
):
    payload = {
        "data": data,
        "user_id": user_id,
        "tags": tags,
        "people_mentioned": people_mentioned,
        "topic_category": topic_category,
        "created_at": "2025-01-01T00:00:00Z",
    }
    if project_id:
        payload["project_id"] = project_id
    return payload


class TestDeriveEncryptionKey:
    def test_deterministic(self):
        key1 = derive_encryption_key(MASTER_KEY, "project_abc")
        key2 = derive_encryption_key(MASTER_KEY, "project_abc")
        assert key1 == key2

    def test_different_identifiers_produce_different_keys(self):
        key_a = derive_encryption_key(MASTER_KEY, "project_a")
        key_b = derive_encryption_key(MASTER_KEY, "project_b")
        assert key_a != key_b

    def test_returns_valid_fernet_key(self):
        key = derive_encryption_key(MASTER_KEY, "test_id")
        Fernet(key)


class TestEncryptPayload:
    def test_encrypt_decrypt_roundtrip(self):
        payload = _make_payload()
        encrypted = encrypt_payload(payload, MASTER_KEY)
        decrypted = decrypt_payload(encrypted, MASTER_KEY)

        assert decrypted["data"] == "secret memory"
        assert decrypted["tags"] == "work,personal"
        assert decrypted["people_mentioned"] == "Alice,Bob"
        assert decrypted["topic_category"] == "meeting"

    def test_encrypted_data_unreadable(self):
        payload = _make_payload()
        encrypted = encrypt_payload(payload, MASTER_KEY)

        assert encrypted["data"] != "secret memory"
        assert encrypted["tags"] != "work,personal"
        assert encrypted["people_mentioned"] != "Alice,Bob"
        assert encrypted["topic_category"] != "meeting"

    def test_encrypted_flag_set(self):
        payload = _make_payload()
        encrypted = encrypt_payload(payload, MASTER_KEY)
        assert encrypted["encrypted"] is True

    def test_non_sensitive_fields_unchanged(self):
        payload = _make_payload()
        encrypted = encrypt_payload(payload, MASTER_KEY)

        assert encrypted["user_id"] == "user_123"
        assert encrypted["created_at"] == "2025-01-01T00:00:00Z"

    def test_empty_fields_handled(self):
        payload = _make_payload(tags="", people_mentioned="", topic_category="")
        encrypted = encrypt_payload(payload, MASTER_KEY)
        decrypted = decrypt_payload(encrypted, MASTER_KEY)

        assert decrypted["tags"] == ""
        assert decrypted["people_mentioned"] == ""
        assert decrypted["topic_category"] == ""

    def test_with_project_id(self):
        payload = _make_payload(project_id="proj_xyz")
        encrypted = encrypt_payload(payload, MASTER_KEY)
        decrypted = decrypt_payload(encrypted, MASTER_KEY)

        assert decrypted["data"] == "secret memory"
        assert decrypted["project_id"] == "proj_xyz"

    def test_without_project_id_uses_user_id(self):
        payload = _make_payload(project_id=None)
        encrypted = encrypt_payload(payload, MASTER_KEY)
        decrypted = decrypt_payload(encrypted, MASTER_KEY)

        assert decrypted["data"] == "secret memory"


class TestDecryptPayload:
    def test_wrong_key_fails(self):
        payload = _make_payload()
        encrypted = encrypt_payload(payload, MASTER_KEY)

        wrong_key = Fernet.generate_key().decode()
        with pytest.raises(InvalidToken):
            decrypt_payload(encrypted, wrong_key)

    def test_skip_unencrypted_payload(self):
        payload = _make_payload()
        result = decrypt_payload(payload, MASTER_KEY)
        assert result is payload

    def test_project_isolation(self):
        payload_a = _make_payload(project_id="project_a")
        payload_b = _make_payload(project_id="project_b")

        encrypted_a = encrypt_payload(payload_a, MASTER_KEY)
        encrypted_b = encrypt_payload(payload_b, MASTER_KEY)

        assert encrypted_a["data"] != encrypted_b["data"]

    def test_missing_identifier_raises(self):
        payload = {"data": "test", "encrypted": True}
        with pytest.raises(ValueError, match="project_id or user_id"):
            decrypt_payload(payload, MASTER_KEY)

    def test_does_not_mutate_original(self):
        payload = _make_payload()
        original_data = payload["data"]
        encrypted = encrypt_payload(payload, MASTER_KEY)
        decrypt_payload(encrypted, MASTER_KEY)

        assert payload["data"] == original_data
        assert "encrypted" not in payload
