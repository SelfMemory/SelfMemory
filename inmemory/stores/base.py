"""
Base storage interface for InMemory storage backends.

This module defines the abstract interface that all storage backends
must implement to provide user management and authentication capabilities.
"""

from abc import ABC, abstractmethod
from typing import Any


class MemoryStoreInterface(ABC):
    """
    Abstract interface for memory storage backends.

    All storage implementations (file-based, MongoDB, PostgreSQL, etc.)
    must implement this interface to provide consistent user management
    and authentication capabilities across different deployment modes.
    """

    @abstractmethod
    def validate_user(self, user_id: str) -> bool:
        """
        Check if user_id exists and is valid.

        Args:
            user_id: User identifier to validate

        Returns:
            bool: True if user exists and is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_collection_name(self, user_id: str) -> str:
        """
        Get the Qdrant collection name for the specified user.

        Args:
            user_id: User identifier

        Returns:
            str: Collection name for this user's memories

        Raises:
            ValueError: If user is invalid or unauthorized
        """
        pass

    @abstractmethod
    def validate_api_key(self, api_key: str) -> str | None:
        """
        Validate API key and return associated user_id if valid.

        Args:
            api_key: API key to validate

        Returns:
            Optional[str]: User ID if valid, None if invalid
        """
        pass

    @abstractmethod
    def store_api_key(self, user_id: str, api_key: str, **metadata) -> bool:
        """
        Store an API key for a user with optional metadata.

        Args:
            user_id: User identifier
            api_key: API key to store
            **metadata: Additional metadata (name, permissions, etc.)

        Returns:
            bool: True if stored successfully, False otherwise
        """
        pass

    @abstractmethod
    def get_user_info(self, user_id: str) -> dict[str, Any] | None:
        """
        Get user information and metadata.

        Args:
            user_id: User identifier

        Returns:
            Optional[Dict]: User information if found, None otherwise
        """
        pass

    @abstractmethod
    def list_user_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        """
        List all API keys for a user.

        Args:
            user_id: User identifier

        Returns:
            list[Dict]: List of API key information (without actual keys)
        """
        pass

    @abstractmethod
    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke/deactivate an API key.

        Args:
            api_key: API key to revoke

        Returns:
            bool: True if revoked successfully, False otherwise
        """
        pass

    @abstractmethod
    def create_user(self, user_id: str, **user_data) -> bool:
        """
        Create a new user with optional metadata.

        Args:
            user_id: User identifier
            **user_data: Additional user information

        Returns:
            bool: True if created successfully, False otherwise
        """
        pass

    @abstractmethod
    def update_user_info(self, user_id: str, **updates) -> bool:
        """
        Update user information and metadata.

        Args:
            user_id: User identifier
            **updates: Fields to update

        Returns:
            bool: True if updated successfully, False otherwise
        """
        pass

    @abstractmethod
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user and all associated data.

        Args:
            user_id: User identifier

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        pass

    @abstractmethod
    def close_connection(self) -> None:
        """
        Close any persistent connections (databases, files, etc.).

        This method should be called when the storage backend is no longer needed
        to clean up resources properly.
        """
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        self.close_connection()
