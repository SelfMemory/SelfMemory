"""
File-based storage backend for InMemory.

This implementation provides a zero-dependency storage backend using JSON files
in the user's home directory. Perfect for development, single-user setups,
and situations where external databases are not desired.
"""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .base import MemoryStoreInterface

logger = logging.getLogger(__name__)


class FileBasedStore(MemoryStoreInterface):
    """
    File-based storage backend using JSON files.

    Stores user data and API keys in JSON files within a specified directory.
    Thread-safe operations ensure data consistency in concurrent environments.
    """

    def __init__(self, data_dir: str = "~/.inmemory"):
        """
        Initialize file-based storage.

        Args:
            data_dir: Directory to store data files (default: ~/.inmemory)
        """
        self.data_dir = Path(data_dir).expanduser()
        self.users_file = self.data_dir / "users.json"
        self.api_keys_file = self.data_dir / "api_keys.json"

        # Thread safety for concurrent file operations
        self._lock = threading.RLock()

        # Ensure directory structure exists
        self._ensure_directory()

        # Initialize files if they don't exist
        self._ensure_files()

        logger.info(f"FileBasedStore initialized with data directory: {self.data_dir}")

    def _ensure_directory(self) -> None:
        """Create the data directory if it doesn't exist."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create data directory {self.data_dir}: {e}")
            raise

    def _ensure_files(self) -> None:
        """Initialize JSON files with empty structures if they don't exist."""
        with self._lock:
            # Initialize users file
            if not self.users_file.exists():
                self._write_json(self.users_file, {})

            # Initialize API keys file
            if not self.api_keys_file.exists():
                self._write_json(self.api_keys_file, {})

    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        """
        Safely read JSON file with error handling.

        Args:
            file_path: Path to JSON file

        Returns:
            Dict: Parsed JSON data, empty dict if file doesn't exist or is invalid
        """
        try:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}. Returning empty data.")
        return {}

    def _write_json(self, file_path: Path, data: Dict[str, Any]) -> None:
        """
        Safely write JSON file with atomic operations.

        Args:
            file_path: Path to JSON file
            data: Data to write
        """
        temp_file = file_path.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Atomic move (on most systems)
            temp_file.replace(file_path)
        except Exception as e:
            logger.error(f"Failed to write {file_path}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise

    def validate_user(self, user_id: str) -> bool:
        """
        Check if user exists in the users file.

        Args:
            user_id: User identifier to validate

        Returns:
            bool: True if user exists, False otherwise
        """
        if not user_id or not isinstance(user_id, str):
            return False

        with self._lock:
            users = self._read_json(self.users_file)
            exists = user_id in users

        logger.debug(f"User validation for {user_id}: {exists}")
        return exists

    def get_collection_name(self, user_id: str) -> str:
        """
        Generate Qdrant collection name for user.

        Args:
            user_id: User identifier

        Returns:
            str: Collection name for this user

        Raises:
            ValueError: If user is invalid
        """
        if not self.validate_user(user_id):
            # For file-based storage, auto-create users
            self.create_user(user_id)

        # Clean user_id for collection name (alphanumeric and underscore only)
        clean_user_id = "".join(c for c in user_id if c.isalnum() or c == "_").lower()
        collection_name = f"memories_{clean_user_id}"

        logger.debug(f"Collection name for user {user_id}: {collection_name}")
        return collection_name

    def validate_api_key(self, api_key: str) -> Optional[str]:
        """
        Validate API key and return associated user_id.

        Args:
            api_key: API key to validate

        Returns:
            Optional[str]: User ID if valid, None if invalid
        """
        if not api_key or not isinstance(api_key, str):
            return None

        with self._lock:
            api_keys = self._read_json(self.api_keys_file)

            # Find active API key
            for key_data in api_keys.values():
                if key_data.get("api_key") == api_key and key_data.get(
                    "is_active", False
                ):
                    user_id = key_data.get("user_id")

                    # Update last used timestamp
                    key_data["last_used"] = datetime.utcnow().isoformat()
                    self._write_json(self.api_keys_file, api_keys)

                    logger.info(f"Valid API key used by user: {user_id}")
                    return user_id

        logger.warning(f"Invalid or inactive API key: {api_key[:8]}...")
        return None

    def store_api_key(self, user_id: str, api_key: str, **metadata) -> bool:
        """
        Store API key for user with metadata.

        Args:
            user_id: User identifier
            api_key: API key to store
            **metadata: Additional metadata (name, permissions, etc.)

        Returns:
            bool: True if stored successfully
        """
        try:
            with self._lock:
                # Ensure user exists
                if not self.validate_user(user_id):
                    self.create_user(user_id)

                # Load existing API keys
                api_keys = self._read_json(self.api_keys_file)

                # Create API key record
                key_id = f"{user_id}_{len(api_keys) + 1}"
                api_keys[key_id] = {
                    "api_key": api_key,
                    "user_id": user_id,
                    "is_active": True,
                    "created_at": datetime.utcnow().isoformat(),
                    "last_used": None,
                    **metadata,
                }

                # Save updated data
                self._write_json(self.api_keys_file, api_keys)

            logger.info(f"API key stored for user: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store API key for user {user_id}: {e}")
            return False

    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from users file.

        Args:
            user_id: User identifier

        Returns:
            Optional[Dict]: User information if found
        """
        with self._lock:
            users = self._read_json(self.users_file)
            return users.get(user_id)

    def list_user_api_keys(self, user_id: str) -> list[Dict[str, Any]]:
        """
        List all API keys for a user (without exposing actual keys).

        Args:
            user_id: User identifier

        Returns:
            list[Dict]: List of API key metadata
        """
        with self._lock:
            api_keys = self._read_json(self.api_keys_file)

            user_keys = []
            for key_id, key_data in api_keys.items():
                if key_data.get("user_id") == user_id:
                    # Return metadata without actual API key
                    safe_data = {k: v for k, v in key_data.items() if k != "api_key"}
                    safe_data["key_id"] = key_id
                    safe_data["key_preview"] = f"{key_data.get('api_key', '')[:8]}..."
                    user_keys.append(safe_data)

        return user_keys

    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key by marking it inactive.

        Args:
            api_key: API key to revoke

        Returns:
            bool: True if revoked successfully
        """
        try:
            with self._lock:
                api_keys = self._read_json(self.api_keys_file)

                # Find and deactivate the key
                for key_data in api_keys.values():
                    if key_data.get("api_key") == api_key:
                        key_data["is_active"] = False
                        key_data["revoked_at"] = datetime.utcnow().isoformat()

                        self._write_json(self.api_keys_file, api_keys)
                        logger.info(f"API key revoked: {api_key[:8]}...")
                        return True

            logger.warning(f"API key not found for revocation: {api_key[:8]}...")
            return False

        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            return False

    def create_user(self, user_id: str, **user_data) -> bool:
        """
        Create a new user in the users file.

        Args:
            user_id: User identifier
            **user_data: Additional user information

        Returns:
            bool: True if created successfully
        """
        try:
            with self._lock:
                users = self._read_json(self.users_file)

                if user_id not in users:
                    users[user_id] = {
                        "id": user_id,
                        "created_at": datetime.utcnow().isoformat(),
                        "last_accessed": None,
                        **user_data,
                    }

                    self._write_json(self.users_file, users)
                    logger.info(f"User created: {user_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            return False

    def update_user_info(self, user_id: str, **updates) -> bool:
        """
        Update user information.

        Args:
            user_id: User identifier
            **updates: Fields to update

        Returns:
            bool: True if updated successfully
        """
        try:
            with self._lock:
                users = self._read_json(self.users_file)

                if user_id in users:
                    users[user_id].update(updates)
                    users[user_id]["updated_at"] = datetime.utcnow().isoformat()

                    self._write_json(self.users_file, users)
                    logger.info(f"User updated: {user_id}")
                    return True
                else:
                    logger.warning(f"Cannot update non-existent user: {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {e}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """
        Delete user and all associated API keys.

        Args:
            user_id: User identifier

        Returns:
            bool: True if deleted successfully
        """
        try:
            with self._lock:
                # Remove from users
                users = self._read_json(self.users_file)
                if user_id in users:
                    del users[user_id]
                    self._write_json(self.users_file, users)

                # Remove associated API keys
                api_keys = self._read_json(self.api_keys_file)
                keys_to_remove = [
                    key_id
                    for key_id, key_data in api_keys.items()
                    if key_data.get("user_id") == user_id
                ]

                for key_id in keys_to_remove:
                    del api_keys[key_id]

                if keys_to_remove:
                    self._write_json(self.api_keys_file, api_keys)

            logger.info(
                f"User deleted: {user_id} (removed {len(keys_to_remove)} API keys)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            return False

    def close_connection(self) -> None:
        """
        Close connections (no-op for file-based storage).

        File-based storage doesn't maintain persistent connections,
        so this is a no-op implementation for interface compatibility.
        """
        logger.debug("FileBasedStore connection closed (no-op)")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics (useful for debugging/monitoring).

        Returns:
            Dict: Storage statistics
        """
        with self._lock:
            users = self._read_json(self.users_file)
            api_keys = self._read_json(self.api_keys_file)

            active_keys = sum(
                1 for key_data in api_keys.values() if key_data.get("is_active", False)
            )

        return {
            "storage_type": "file",
            "data_directory": str(self.data_dir),
            "total_users": len(users),
            "total_api_keys": len(api_keys),
            "active_api_keys": active_keys,
            "users_file_size": self.users_file.stat().st_size
            if self.users_file.exists()
            else 0,
            "api_keys_file_size": self.api_keys_file.stat().st_size
            if self.api_keys_file.exists()
            else 0,
        }

    def backup_data(self, backup_dir: str) -> bool:
        """
        Create a backup of all data files.

        Args:
            backup_dir: Directory to store backup files

        Returns:
            bool: True if backup successful
        """
        try:
            backup_path = Path(backup_dir).expanduser()
            backup_path.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

            with self._lock:
                # Backup users file
                if self.users_file.exists():
                    users_backup = backup_path / f"users_{timestamp}.json"
                    users_backup.write_bytes(self.users_file.read_bytes())

                # Backup API keys file
                if self.api_keys_file.exists():
                    keys_backup = backup_path / f"api_keys_{timestamp}.json"
                    keys_backup.write_bytes(self.api_keys_file.read_bytes())

            logger.info(f"Data backup created in: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False

    def _generate_default_api_key(self, user_id: str) -> str:
        """
        Generate a default API key for a user (for development/testing).

        Args:
            user_id: User identifier

        Returns:
            str: Generated API key
        """
        import hashlib
        import secrets

        # Generate a deterministic but secure key based on user_id and timestamp
        salt = secrets.token_hex(16)
        key_data = f"{user_id}_{datetime.utcnow().isoformat()}_{salt}"
        api_key = hashlib.sha256(key_data.encode()).hexdigest()[:32]

        return f"file_{api_key}"

    def ensure_user_with_key(self, user_id: str) -> str:
        """
        Ensure user exists and has at least one API key.
        Convenience method for development setups.

        Args:
            user_id: User identifier

        Returns:
            str: An active API key for the user
        """
        with self._lock:
            # Create user if needed
            if not self.validate_user(user_id):
                self.create_user(user_id)

            # Check for existing active API keys
            user_keys = self.list_user_api_keys(user_id)
            active_keys = [k for k in user_keys if k.get("is_active", False)]

            if active_keys:
                # Return existing key (we can't return actual key for security)
                # In practice, the user should know their key
                logger.info(f"User {user_id} has {len(active_keys)} active API keys")
                return "existing_key_found"
            else:
                # Generate new API key
                new_key = self._generate_default_api_key(user_id)
                self.store_api_key(
                    user_id,
                    new_key,
                    name="auto_generated",
                    description="Auto-generated API key for file-based storage",
                )
                logger.info(f"Generated new API key for user: {user_id}")
                return new_key
