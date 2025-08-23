"""
MongoDB-based User Management for Multi-User Memory MCP Server.
Replaces the JSON-based user management with MongoDB integration.
"""

import contextlib
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Conditional import of pymongo
try:
    from pymongo import MongoClient

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    MongoClient = None


class MongoUserManager:
    """Manages user validation and collection naming using MongoDB."""

    def __init__(self, mongodb_uri: str = None):
        """
        Initialize MongoDB user manager.

        Args:
            mongodb_uri: MongoDB connection string (defaults to MONGODB_URI env var)
        """
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        if not self.mongodb_uri:
            raise ValueError("MONGODB_URI environment variable is required")

        self.client = MongoClient(self.mongodb_uri)
        self.db = self.client.get_default_database()

        # Collections
        self.users = self.db.users
        self.api_keys = self.db.api_keys

        logger.info("MongoDB user manager initialized")

    def validate_api_key(self, api_key: str) -> str | None:
        """
        Validate API key and return user_id if valid.

        Args:
            api_key: API key to validate

        Returns:
            str: User ID if valid, None if invalid
        """
        if not api_key or not isinstance(api_key, str):
            return None

        try:
            # Find active API key record
            api_record = self.api_keys.find_one({"api_key": api_key, "is_active": True})

            if api_record:
                # Update last_used timestamp
                self.api_keys.update_one(
                    {"_id": api_record["_id"]},
                    {"$set": {"last_used": datetime.utcnow()}},
                )

                logger.info(f"Valid API key used by user: {api_record['user_id']}")
                return api_record["user_id"]
            logger.warning(f"Invalid or inactive API key: {api_key[:8]}...")
            return None

        except Exception as e:
            logger.error(f"Error validating API key: {str(e)}")
            return None

    def is_valid_user(self, user_id: str) -> bool:
        """
        Check if user_id exists in MongoDB users collection.

        Args:
            user_id: User identifier to validate (can be ObjectId or string)

        Returns:
            bool: True if user exists and is valid
        """
        if not user_id or not isinstance(user_id, str):
            return False

        try:
            # Check if user exists in users collection by both _id and id fields
            # MongoDB ObjectId format: 24-character hex string
            from bson import ObjectId

            user = None
            if len(user_id) == 24:
                with contextlib.suppress(Exception):
                    # Try as ObjectId first (NextAuth MongoDB adapter stores _id as ObjectId)
                    user = self.users.find_one({"_id": ObjectId(user_id)})

            # If not found by ObjectId, try by string id field
            if not user:
                user = self.users.find_one({"id": user_id})

            is_valid = user is not None

            if not is_valid:
                logger.warning(f"User not found in database: {user_id}")
            else:
                logger.info(f"User validated successfully: {user_id}")

            return is_valid

        except Exception as e:
            logger.error(f"Error validating user {user_id}: {str(e)}")
            return False

    def get_user_info(self, user_id: str) -> dict[str, Any] | None:
        """
        Get user information from MongoDB.

        Args:
            user_id: User identifier

        Returns:
            Dict: User information if found
        """
        try:
            user = self.users.find_one({"id": user_id})
            if user:
                # Convert MongoDB ObjectId to string for JSON serialization
                user["_id"] = str(user["_id"])
                return user
            return None

        except Exception as e:
            logger.error(f"Error getting user info for {user_id}: {str(e)}")
            return None

    def get_collection_name(self, user_id: str) -> str:
        """
        Get Qdrant collection name for user.

        Args:
            user_id: User identifier

        Returns:
            str: Collection name for this user

        Raises:
            ValueError: If user is invalid
        """
        if not self.is_valid_user(user_id):
            raise ValueError(f"Invalid or unauthorized user_id: {user_id}")

        # Clean user_id for collection name (alphanumeric and underscore only)
        clean_user_id = "".join(c for c in user_id if c.isalnum() or c == "_").lower()
        return f"memories_{clean_user_id}"

    def get_api_key_info(self, api_key: str) -> dict[str, Any] | None:
        """
        Get API key information including usage stats.

        Args:
            api_key: API key to lookup

        Returns:
            Dict: API key information if found
        """
        try:
            api_record = self.api_keys.find_one({"api_key": api_key, "is_active": True})

            if api_record:
                # Convert ObjectId to string
                api_record["_id"] = str(api_record["_id"])
                return api_record
            return None

        except Exception as e:
            logger.error(f"Error getting API key info: {str(e)}")
            return None

    def close_connection(self):
        """Close MongoDB connection."""
        try:
            self.client.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {str(e)}")


# Global user manager instance
# Will be initialized when the server starts
mongo_user_manager: MongoUserManager | None = None


def initialize_mongo_user_manager(mongodb_uri: str = None) -> MongoUserManager:
    """
    Initialize the global MongoDB user manager.

    Args:
        mongodb_uri: MongoDB connection string

    Returns:
        MongoUserManager: Initialized user manager
    """
    global mongo_user_manager
    mongo_user_manager = MongoUserManager(mongodb_uri)
    return mongo_user_manager


def get_mongo_user_manager() -> MongoUserManager:
    """
    Get the global MongoDB user manager.

    Returns:
        MongoUserManager: User manager instance

    Raises:
        RuntimeError: If user manager not initialized
    """
    if mongo_user_manager is None:
        raise RuntimeError(
            "MongoDB user manager not initialized. Call initialize_mongo_user_manager() first."
        )
    return mongo_user_manager
