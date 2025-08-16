"""
Main Memory SDK class for InMemory.

This module provides the primary interface for InMemory functionality,
following the mem0 pattern with a clean, easy-to-use API that works
with any configured storage backend.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from .config import (
    InMemoryConfig,
    load_config,
    detect_deployment_mode,
    get_config_for_mode,
)
from .search.enhanced_search_engine import EnhancedSearchEngine
from .services.add_memory import add_memory_enhanced
from .stores import create_store, MemoryStoreInterface

logger = logging.getLogger(__name__)


class Memory:
    """
    Main Memory class providing the primary SDK interface.

    This class abstracts away storage backend complexity and provides
    a clean, consistent API regardless of whether file-based storage
    or enterprise MongoDB is used.

    Examples:
        Basic usage (zero setup):
        >>> memory = Memory()
        >>> memory.add("I love pizza", user_id="john")
        >>> results = memory.search("pizza", user_id="john")

        With custom configuration:
        >>> config = InMemoryConfig(storage={"type": "mongodb"})
        >>> memory = Memory(config=config)

        Auto-detected mode:
        >>> memory = Memory()  # Detects based on environment
    """

    def __init__(
        self,
        config: Optional[InMemoryConfig] = None,
        storage_type: Optional[str] = None,
        auto_detect: bool = True,
    ):
        """
        Initialize Memory with storage backend and configuration.

        Args:
            config: Optional configuration object
            storage_type: Force specific storage type ("file" or "mongodb")
            auto_detect: Whether to auto-detect deployment mode
        """
        # Load configuration
        if config is None:
            if auto_detect and not storage_type:
                mode = detect_deployment_mode()
                config = get_config_for_mode(mode)
                logger.info(f"Auto-detected deployment mode: {mode}")
            else:
                config = load_config()

        # Override storage type if explicitly provided
        if storage_type:
            config.storage.type = storage_type

        self.config = config

        # Initialize storage backend
        try:
            storage_config = config.storage.dict()
            self.store = create_store(**storage_config)
            logger.info(f"Memory initialized with {config.storage.type} storage")
        except Exception as e:
            logger.error(f"Failed to initialize storage backend: {e}")
            # Fallback to file-based storage
            logger.warning("Falling back to file-based storage")
            self.store = create_store("file")

        # Initialize search engine
        self.search_engine = EnhancedSearchEngine()

        logger.info("Memory SDK initialized successfully")

    def add(
        self,
        memory_content: str,
        user_id: str,
        tags: Optional[str] = None,
        people_mentioned: Optional[str] = None,
        topic_category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a new memory to storage.

        Args:
            memory_content: The memory text to store
            user_id: User identifier
            tags: Optional comma-separated tags
            people_mentioned: Optional comma-separated people names
            topic_category: Optional topic category
            metadata: Optional additional metadata

        Returns:
            Dict: Result information including memory_id and status

        Examples:
            >>> memory.add("Meeting notes from project discussion",
            ...           user_id="john",
            ...           tags="work,meeting",
            ...           people_mentioned="Sarah,Mike")
        """
        try:
            # Ensure user exists in storage backend
            if not self.store.validate_user(user_id):
                logger.info(f"Auto-creating user: {user_id}")
                self.store.create_user(user_id)

            # Use existing add_memory_enhanced logic
            result = add_memory_enhanced(
                memory_content=memory_content,
                user_id=user_id,
                tags=tags or "",
                people_mentioned=people_mentioned or "",
                topic_category=topic_category or "",
            )

            # Add any additional metadata
            if metadata and isinstance(result, dict):
                result.setdefault("metadata", {}).update(metadata)

            logger.info(f"Memory added for user {user_id}: {memory_content[:50]}...")
            return result if isinstance(result, dict) else {"message": result}

        except Exception as e:
            logger.error(f"Failed to add memory for user {user_id}: {e}")
            return {"success": False, "error": str(e)}

    def search(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        tags: Optional[List[str]] = None,
        people_mentioned: Optional[List[str]] = None,
        topic_category: Optional[str] = None,
        temporal_filter: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search memories with various filters.

        Args:
            query: Search query string
            user_id: User identifier
            limit: Maximum number of results
            tags: Optional list of tags to filter by
            people_mentioned: Optional list of people to filter by
            topic_category: Optional topic category filter
            temporal_filter: Optional temporal filter (e.g., "today", "this_week")
            threshold: Optional minimum similarity score

        Returns:
            Dict: Search results with "results" key containing list of memories

        Examples:
            >>> results = memory.search("pizza", user_id="john")
            >>> results = memory.search("meetings", user_id="john",
            ...                        tags=["work"], limit=5)
        """
        try:
            # Validate user
            if not self.store.validate_user(user_id):
                logger.warning(f"User not found: {user_id}")
                return {"results": []}

            # Use existing search engine
            results = self.search_engine.search_memories(
                query=query,
                user_id=user_id,
                limit=limit,
                tags=tags,
                people_mentioned=people_mentioned,
                topic_category=topic_category,
                temporal_filter=temporal_filter,
            )

            # Apply threshold filtering if specified
            if threshold and results:
                results = [r for r in results if r.get("score", 0) >= threshold]

            logger.info(
                f"Search completed for user {user_id}: {len(results or [])} results"
            )
            return {"results": results or []}

        except Exception as e:
            logger.error(f"Search failed for user {user_id}: {e}")
            return {"results": []}

    def get_all(
        self, user_id: str, limit: int = 100, offset: int = 0
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all memories for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of memories to return
            offset: Number of memories to skip

        Returns:
            Dict: All memories with "results" key

        Examples:
            >>> all_memories = memory.get_all("john")
            >>> recent_memories = memory.get_all("john", limit=10)
        """
        try:
            # Validate user
            if not self.store.validate_user(user_id):
                logger.warning(f"User not found: {user_id}")
                return {"results": []}

            # Use search with empty query to get all memories
            results = self.search_engine.search_memories(
                query="",  # Empty query gets most recent
                user_id=user_id,
                limit=limit + offset,
            )

            # Apply manual offset
            if results and offset > 0:
                results = results[offset:]

            logger.info(f"Retrieved {len(results or [])} memories for user {user_id}")
            return {"results": results or []}

        except Exception as e:
            logger.error(f"Failed to get memories for user {user_id}: {e}")
            return {"results": []}

    def delete(self, memory_id: str, user_id: str) -> Dict[str, Any]:
        """
        Delete a specific memory.

        Args:
            memory_id: Memory identifier to delete
            user_id: User identifier (for authorization)

        Returns:
            Dict: Deletion result
        """
        try:
            # Import deletion function
            from .repositories.qdrant_db import delete_user_memory

            success = delete_user_memory(user_id, memory_id)

            if success:
                logger.info(f"Memory {memory_id} deleted for user {user_id}")
                return {"success": True, "message": "Memory deleted successfully"}
            else:
                logger.warning(
                    f"Failed to delete memory {memory_id} for user {user_id}"
                )
                return {
                    "success": False,
                    "error": "Memory not found or deletion failed",
                }

        except Exception as e:
            logger.error(f"Error deleting memory {memory_id} for user {user_id}: {e}")
            return {"success": False, "error": str(e)}

    def delete_all(self, user_id: str) -> Dict[str, Any]:
        """
        Delete all memories for a user.

        Args:
            user_id: User identifier

        Returns:
            Dict: Deletion result with count of deleted memories
        """
        try:
            # Get all memories first
            all_memories = self.get_all(user_id, limit=10000)  # Large limit
            memory_ids = [m.get("id") for m in all_memories.get("results", [])]

            deleted_count = 0
            for memory_id in memory_ids:
                if memory_id:
                    result = self.delete(memory_id, user_id)
                    if result.get("success", False):
                        deleted_count += 1

            logger.info(f"Deleted {deleted_count} memories for user {user_id}")
            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Deleted {deleted_count} memories",
            }

        except Exception as e:
            logger.error(f"Failed to delete all memories for user {user_id}: {e}")
            return {"success": False, "error": str(e)}

    def temporal_search(
        self,
        temporal_query: str,
        user_id: str,
        semantic_query: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search memories using temporal queries.

        Args:
            temporal_query: Temporal query (e.g., "yesterday", "this_week")
            user_id: User identifier
            semantic_query: Optional semantic search query
            limit: Maximum number of results

        Returns:
            Dict: Search results
        """
        try:
            results = self.search_engine.temporal_search(
                temporal_query=temporal_query,
                user_id=user_id,
                semantic_query=semantic_query,
                limit=limit,
            )

            return {"results": results or []}

        except Exception as e:
            logger.error(f"Temporal search failed for user {user_id}: {e}")
            return {"results": []}

    def search_by_tags(
        self,
        tags: Union[str, List[str]],
        user_id: str,
        semantic_query: Optional[str] = None,
        match_all: bool = False,
        limit: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search memories by tags.

        Args:
            tags: Tags to search for (string or list)
            user_id: User identifier
            semantic_query: Optional semantic search query
            match_all: Whether all tags must match (AND) vs any tag (OR)
            limit: Maximum number of results

        Returns:
            Dict: Search results
        """
        try:
            if isinstance(tags, str):
                tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            else:
                tag_list = tags

            results = self.search_engine.tag_search(
                tags=tag_list,
                user_id=user_id,
                semantic_query=semantic_query,
                match_all_tags=match_all,
                limit=limit,
            )

            return {"results": results or []}

        except Exception as e:
            logger.error(f"Tag search failed for user {user_id}: {e}")
            return {"results": []}

    def search_by_people(
        self,
        people: Union[str, List[str]],
        user_id: str,
        semantic_query: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search memories by people mentioned.

        Args:
            people: People to search for (string or list)
            user_id: User identifier
            semantic_query: Optional semantic search query
            limit: Maximum number of results

        Returns:
            Dict: Search results
        """
        try:
            if isinstance(people, str):
                people_list = [
                    person.strip() for person in people.split(",") if person.strip()
                ]
            else:
                people_list = people

            results = self.search_engine.people_search(
                people=people_list,
                user_id=user_id,
                semantic_query=semantic_query,
                limit=limit,
            )

            return {"results": results or []}

        except Exception as e:
            logger.error(f"People search failed for user {user_id}: {e}")
            return {"results": []}

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics for a user's memories.

        Args:
            user_id: User identifier

        Returns:
            Dict: User statistics including memory count, storage info, etc.
        """
        try:
            # Get user info from store
            user_info = self.store.get_user_info(user_id)

            # Get memory count via search
            all_memories = self.get_all(user_id, limit=1000)  # Sample count
            memory_count = len(all_memories.get("results", []))

            # Get storage stats
            storage_stats = (
                self.store.get_stats() if hasattr(self.store, "get_stats") else {}
            )

            return {
                "user_id": user_id,
                "memory_count": memory_count,
                "user_info": user_info,
                "storage_backend": self.config.storage.type,
                "storage_stats": storage_stats,
            }

        except Exception as e:
            logger.error(f"Failed to get stats for user {user_id}: {e}")
            return {"user_id": user_id, "error": str(e)}

    def create_user(self, user_id: str, **user_data) -> Dict[str, Any]:
        """
        Create a new user with optional metadata.

        Args:
            user_id: User identifier
            **user_data: Additional user information

        Returns:
            Dict: Creation result
        """
        try:
            success = self.store.create_user(user_id, **user_data)

            if success:
                # Ensure Qdrant collection exists
                from .repositories.qdrant_db import ensure_user_collection_exists

                collection_name = ensure_user_collection_exists(user_id)

                logger.info(
                    f"User created: {user_id} with collection: {collection_name}"
                )
                return {
                    "success": True,
                    "user_id": user_id,
                    "collection_name": collection_name,
                }
            else:
                return {"success": False, "error": "Failed to create user"}

        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            return {"success": False, "error": str(e)}

    def generate_api_key(self, user_id: str, name: str = "default") -> Dict[str, Any]:
        """
        Generate a new API key for a user.

        Args:
            user_id: User identifier
            name: Optional name for the API key

        Returns:
            Dict: API key information
        """
        try:
            import secrets

            # Generate secure API key
            api_key = f"im_{secrets.token_urlsafe(32)}"

            # Store in backend
            success = self.store.store_api_key(
                user_id, api_key, name=name, created_via="sdk"
            )

            if success:
                logger.info(f"API key generated for user {user_id}")
                return {
                    "success": True,
                    "api_key": api_key,
                    "name": name,
                    "user_id": user_id,
                }
            else:
                return {"success": False, "error": "Failed to store API key"}

        except Exception as e:
            logger.error(f"Failed to generate API key for user {user_id}: {e}")
            return {"success": False, "error": str(e)}

    def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List API keys for a user.

        Args:
            user_id: User identifier

        Returns:
            List[Dict]: List of API key metadata (without actual keys)
        """
        try:
            return self.store.list_user_api_keys(user_id)
        except Exception as e:
            logger.error(f"Failed to list API keys for user {user_id}: {e}")
            return []

    def revoke_api_key(self, api_key: str) -> Dict[str, Any]:
        """
        Revoke an API key.

        Args:
            api_key: API key to revoke

        Returns:
            Dict: Revocation result
        """
        try:
            success = self.store.revoke_api_key(api_key)

            if success:
                return {"success": True, "message": "API key revoked"}
            else:
                return {"success": False, "error": "API key not found"}

        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            return {"success": False, "error": str(e)}

    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration (safe for external consumption).

        Returns:
            Dict: Current configuration without sensitive data
        """
        config_dict = self.config.to_dict()

        # Remove sensitive information
        if "mongodb_uri" in config_dict.get("storage", {}):
            config_dict["storage"]["mongodb_uri"] = "***HIDDEN***"
        if "google_client_secret" in config_dict.get("auth", {}):
            config_dict["auth"]["google_client_secret"] = "***HIDDEN***"

        return config_dict

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all components.

        Returns:
            Dict: Health check results
        """
        health = {
            "status": "healthy",
            "storage_backend": self.config.storage.type,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Check storage backend
            storage_stats = (
                self.store.get_stats() if hasattr(self.store, "get_stats") else {}
            )
            health["storage"] = {"status": "healthy", "stats": storage_stats}

            # Check search engine (basic test)
            # This could be expanded to test actual functionality
            health["search_engine"] = {"status": "healthy"}

            # Check Qdrant connectivity
            health["vector_db"] = {"status": "unknown"}  # Could test connection

        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
            logger.error(f"Health check failed: {e}")

        return health

    def close(self) -> None:
        """
        Close connections and cleanup resources.

        Should be called when Memory instance is no longer needed.
        """
        try:
            self.store.close_connection()
            logger.info("Memory SDK connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()

    def __repr__(self) -> str:
        """String representation of Memory instance."""
        return f"Memory(storage={self.config.storage.type})"
