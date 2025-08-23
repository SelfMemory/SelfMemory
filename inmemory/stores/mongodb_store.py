"""
MongoDB storage backend for InMemory.

This implementation wraps the existing MongoDB user management functionality
into the storage interface, providing enterprise-grade user management
with MongoDB and OAuth integration capabilities.
"""

import logging
import os
from datetime import datetime
from typing import Any

# Import existing MongoDB functionality
from ..repositories.mongodb_user_manager import MongoUserManager
from .base import MemoryStoreInterface

logger = logging.getLogger(__name__)


class MongoDBStore(MemoryStoreInterface):
    """
    MongoDB storage backend using existing MongoUserManager.

    This implementation wraps the current MongoDB user management functionality
    to conform to the MemoryStoreInterface, providing enterprise features
    like OAuth integration and scalable user management.
    """

    def __init__(self, mongodb_uri: str | None = None, **config):
        """
        Initialize MongoDB storage backend.

        Args:
            mongodb_uri: MongoDB connection string (defaults to MONGODB_URI env var)
            **config: Additional configuration options
        """
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        if not self.mongodb_uri:
            raise ValueError(
                "MongoDB URI is required. Set MONGODB_URI environment variable or "
                "pass mongodb_uri parameter. Install with: pip install inmemory[mongodb]"
            )

        try:
            # Initialize existing MongoDB user manager
            self.mongo_manager = MongoUserManager(self.mongodb_uri)
            logger.info("MongoDBStore initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB connection: {e}")
            raise

    def validate_user(self, user_id: str) -> bool:
        """
        Check if user exists in MongoDB users collection.

        Args:
            user_id: User identifier to validate

        Returns:
            bool: True if user exists and is valid
        """
        try:
            return self.mongo_manager.is_valid_user(user_id)
        except Exception as e:
            logger.error(f"Error validating user {user_id}: {e}")
            return False

    def get_collection_name(self, user_id: str) -> str:
        """
        Get Qdrant collection name for user using existing MongoDB logic.

        Args:
            user_id: User identifier

        Returns:
            str: Collection name for this user

        Raises:
            ValueError: If user is invalid or unauthorized
        """
        return self.mongo_manager.get_collection_name(user_id)

    def validate_api_key(self, api_key: str) -> str | None:
        """
        Validate API key using existing MongoDB logic.

        Args:
            api_key: API key to validate

        Returns:
            Optional[str]: User ID if valid, None if invalid
        """
        return self.mongo_manager.validate_api_key(api_key)

    def store_api_key(self, user_id: str, api_key: str, **metadata) -> bool:
        """
        Store API key in MongoDB.

        Args:
            user_id: User identifier
            api_key: API key to store
            **metadata: Additional metadata (name, permissions, etc.)

        Returns:
            bool: True if stored successfully
        """
        try:
            # Ensure user exists
            if not self.validate_user(user_id):
                self.create_user(user_id)

            # Store in MongoDB api_keys collection
            api_key_record = {
                "api_key": api_key,
                "user_id": user_id,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "last_used": None,
                **metadata,
            }

            result = self.mongo_manager.api_keys.insert_one(api_key_record)

            if result.inserted_id:
                logger.info(f"API key stored for user: {user_id}")
                return True
            logger.warning(f"Failed to insert API key for user: {user_id}")
            return False

        except Exception as e:
            logger.error(f"Error storing API key for user {user_id}: {e}")
            return False

    def get_user_info(self, user_id: str) -> dict[str, Any] | None:
        """
        Get user information from MongoDB using existing logic.

        Args:
            user_id: User identifier

        Returns:
            Optional[Dict]: User information if found
        """
        return self.mongo_manager.get_user_info(user_id)

    def list_user_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        """
        List all API keys for a user from MongoDB.

        Args:
            user_id: User identifier

        Returns:
            list[Dict]: List of API key information (without actual keys)
        """
        try:
            # Query MongoDB for user's API keys
            api_keys = list(
                self.mongo_manager.api_keys.find(
                    {"user_id": user_id},
                    {"api_key": 0},  # Exclude actual API key for security
                )
            )

            # Convert ObjectIds to strings and format for response
            formatted_keys = []
            for key_record in api_keys:
                key_record["_id"] = str(key_record["_id"])
                if "created_at" in key_record:
                    key_record["created_at"] = key_record["created_at"].isoformat()
                if "last_used" in key_record and key_record["last_used"]:
                    key_record["last_used"] = key_record["last_used"].isoformat()
                formatted_keys.append(key_record)

            return formatted_keys

        except Exception as e:
            logger.error(f"Error listing API keys for user {user_id}: {e}")
            return []

    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke API key in MongoDB.

        Args:
            api_key: API key to revoke

        Returns:
            bool: True if revoked successfully
        """
        try:
            result = self.mongo_manager.api_keys.update_one(
                {"api_key": api_key},
                {"$set": {"is_active": False, "revoked_at": datetime.utcnow()}},
            )

            if result.modified_count > 0:
                logger.info(f"API key revoked: {api_key[:8]}...")
                return True
            logger.warning(f"API key not found for revocation: {api_key[:8]}...")
            return False

        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return False

    def create_user(self, user_id: str, **user_data) -> bool:
        """
        Create user in MongoDB users collection.

        Args:
            user_id: User identifier
            **user_data: Additional user information

        Returns:
            bool: True if created successfully
        """
        try:
            # Check if user already exists
            if self.validate_user(user_id):
                logger.info(f"User already exists: {user_id}")
                return True

            # Create user record
            user_record = {
                "id": user_id,
                "created_at": datetime.utcnow(),
                "last_accessed": None,
                **user_data,
            }

            result = self.mongo_manager.users.insert_one(user_record)

            if result.inserted_id:
                logger.info(f"User created in MongoDB: {user_id}")
                return True
            logger.warning(f"Failed to create user in MongoDB: {user_id}")
            return False

        except Exception as e:
            logger.error(f"Error creating user {user_id}: {e}")
            return False

    def update_user_info(self, user_id: str, **updates) -> bool:
        """
        Update user information in MongoDB.

        Args:
            user_id: User identifier
            **updates: Fields to update

        Returns:
            bool: True if updated successfully
        """
        try:
            # Add timestamp to updates
            updates["updated_at"] = datetime.utcnow()

            result = self.mongo_manager.users.update_one(
                {"id": user_id}, {"$set": updates}
            )

            if result.modified_count > 0:
                logger.info(f"User updated in MongoDB: {user_id}")
                return True
            logger.warning(f"No user found to update: {user_id}")
            return False

        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """
        Delete user and all associated API keys from MongoDB.

        Args:
            user_id: User identifier

        Returns:
            bool: True if deleted successfully
        """
        try:
            # Delete from users collection
            user_result = self.mongo_manager.users.delete_one({"id": user_id})

            # Delete associated API keys
            keys_result = self.mongo_manager.api_keys.delete_many({"user_id": user_id})

            logger.info(
                f"User deleted from MongoDB: {user_id} "
                f"(removed {keys_result.deleted_count} API keys)"
            )
            return user_result.deleted_count > 0

        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

    def close_connection(self) -> None:
        """
        Close MongoDB connections using existing logic.
        """
        try:
            self.mongo_manager.close_connection()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")

    def get_stats(self) -> dict[str, Any]:
        """
        Get MongoDB storage statistics.

        Returns:
            Dict: Storage statistics including user and API key counts
        """
        try:
            users_count = self.mongo_manager.users.count_documents({})
            total_keys_count = self.mongo_manager.api_keys.count_documents({})
            active_keys_count = self.mongo_manager.api_keys.count_documents(
                {"is_active": True}
            )

            return {
                "storage_type": "mongodb",
                "mongodb_uri": self.mongodb_uri,
                "database_name": self.mongo_manager.db.name,
                "total_users": users_count,
                "total_api_keys": total_keys_count,
                "active_api_keys": active_keys_count,
            }

        except Exception as e:
            logger.error(f"Error getting MongoDB stats: {e}")
            return {"storage_type": "mongodb", "error": str(e)}

    def get_api_key_info(self, api_key: str) -> dict[str, Any] | None:
        """
        Get detailed API key information (MongoDB-specific method).

        Args:
            api_key: API key to lookup

        Returns:
            Optional[Dict]: API key information if found
        """
        return self.mongo_manager.get_api_key_info(api_key)
