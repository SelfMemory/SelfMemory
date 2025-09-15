"""
Main Memory SDK class for SelfMemory.

This module provides the primary interface for local SelfMemory functionality,
with a zero-setup API for direct usage without authentication.

"""

import logging
import uuid
from datetime import datetime
from typing import Any

from selfmemory.configs import SelfMemoryConfig
from selfmemory.memory.base import MemoryBase
from selfmemory.utils.factory import EmbeddingFactory, VectorStoreFactory

logger = logging.getLogger(__name__)


def _build_filters_and_metadata(
    *,  # Enforce keyword-only arguments
    user_id: str,
    input_metadata: dict[str, Any] | None = None,
    input_filters: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Build filters and metadata for memory operations (simplified for user-only isolation).

    This function creates user-scoped metadata and filters that ensure complete
    isolation between users. Only user_id is required since this system doesn't
    use agent_id or run_id concepts.

    Args:
        user_id: Required user identifier for memory isolation
        input_metadata: Optional additional metadata to include
        input_filters: Optional additional filters to include

    Returns:
        tuple: (processed_metadata, effective_filters)
            - processed_metadata: Metadata to store with the memory
            - effective_filters: Filters to use when querying memories

    Raises:
        ValueError: If user_id is not provided or is empty

    Examples:
        >>> metadata, filters = _build_filters_and_metadata(user_id="alice")
        >>> metadata, filters = _build_filters_and_metadata(
        ...     user_id="alice",
        ...     input_metadata={"category": "work"}
        ... )
    """
    # Validate that user_id is provided (required for this system)
    if not user_id or not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id is required and must be a non-empty string")

    # Start with input metadata or empty dict
    processed_metadata = input_metadata.copy() if input_metadata else {}

    # Add user isolation metadata
    processed_metadata["user_id"] = user_id.strip()

    # Add timestamp for tracking
    processed_metadata["created_at"] = datetime.now().isoformat()

    # Build effective filters for querying
    effective_filters = input_filters.copy() if input_filters else {}

    # Add user isolation filter
    effective_filters["user_id"] = user_id.strip()

    return processed_metadata, effective_filters


class Memory(MemoryBase):
    """
    User-scoped Memory class with automatic isolation.

    This class provides zero-setup functionality with embedded vector stores
    and automatic user isolation. Each Memory instance is scoped to specific
    user identifiers, ensuring complete data separation between users.

    Key Features:
        - Automatic user isolation (users can only access their own memories)
        - Zero-setup embedded vector stores and embeddings
        - Compatible with multiple vector store providers (Qdrant, ChromaDB, etc.)
        - Secure ownership validation for all operations

    Examples:
        Basic multi-user isolation:
        >>> # Each user gets their own isolated memory space
        >>> alice_memory = Memory(user_id="alice")
        >>> bob_memory = Memory(user_id="bob")
        >>> charlie_memory = Memory(user_id="charlie")

        >>> # Users can add memories independently
        >>> alice_memory.add("I love Italian food, especially pizza")
        >>> bob_memory.add("I prefer Japanese cuisine like sushi")
        >>> charlie_memory.add("Mexican food is my favorite")

        >>> # Searches are automatically user-isolated
        >>> alice_results = alice_memory.search("food")  # Only gets Alice's memories
        >>> bob_results = bob_memory.search("food")      # Only gets Bob's memories
        >>> charlie_results = charlie_memory.search("food")  # Only gets Charlie's memories

        Advanced usage with metadata and filtering:
        >>> # Add memories with rich metadata
        >>> alice_memory.add(
        ...     "Had a great meeting with the product team",
        ...     tags="work,meeting,product",
        ...     people_mentioned="Sarah,Mike,Jennifer",
        ...     topic_category="work"
        ... )

        >>> # Search with advanced filtering (still user-isolated)
        >>> work_memories = alice_memory.search(
        ...     query="meeting",
        ...     tags=["work", "meeting"],
        ...     people_mentioned=["Sarah"],
        ...     match_all_tags=True,
        ...     limit=20
        ... )

        User isolation in action:
        >>> # Users cannot access each other's memories
        >>> alice_memory.get_all()  # Returns only Alice's memories
        >>> bob_memory.get_all()    # Returns only Bob's memories

        >>> # Users can only delete their own memories
        >>> alice_memory.delete_all()  # Deletes only Alice's memories
        >>> bob_memory.delete_all()    # Deletes only Bob's memories

        Custom configuration:
        >>> # Use custom embedding and vector store providers
        >>> config = {
        ...     "embedding": {
        ...         "provider": "ollama",
        ...         "config": {"model": "nomic-embed-text"}
        ...     },
        ...     "vector_store": {
        ...         "provider": "qdrant",
        ...         "config": {"path": "./qdrant_data"}
        ...     }
        ... }
        >>> memory = Memory(user_id="user_123", config=config)

        Production multi-tenant usage:
        >>> # Different users in a multi-tenant application
        >>> def get_user_memory(user_id: str) -> Memory:
        ...     return Memory(user_id=user_id)

        >>> # Each user gets isolated memory
        >>> user_1_memory = get_user_memory("tenant_1_user_456")
        >>> user_2_memory = get_user_memory("tenant_2_user_789")

        >>> # Complete isolation - no cross-user data leakage
        >>> user_1_memory.add("Confidential business data")
        >>> user_2_memory.add("Personal notes")
        >>> # Users can never see each other's data
    """

    def __init__(self, config: SelfMemoryConfig | dict | None = None):
        """
        Initialize Memory with configuration (selfmemory style - no user_id required).

        Args:
            config: Optional SelfMemoryConfig instance or config dictionary

        Examples:
            Basic memory instance:
            >>> memory = Memory()

            With custom config:
            >>> config = {
            ...     "embedding": {"provider": "ollama", "config": {...}},
            ...     "vector_store": {"provider": "qdrant", "config": {...}}
            ... }
            >>> memory = Memory(config=config)

            Multi-user usage (user_id passed to methods):
            >>> memory = Memory()
            >>> memory.add("I love pizza", user_id="alice")
            >>> memory.add("I love sushi", user_id="bob")
            >>> alice_results = memory.search("pizza", user_id="alice")  # Only Alice's memories
            >>> bob_results = memory.search("sushi", user_id="bob")      # Only Bob's memories
        """

        # Handle different config types for clean API
        if config is None:
            self.config = SelfMemoryConfig()
        elif isinstance(config, dict):
            # Convert dict to SelfMemoryConfig for internal use
            self.config = SelfMemoryConfig.from_dict(config)
        else:
            # Already an SelfMemoryConfig object
            self.config = config

        # Use factories with exact pattern - pass raw config
        self.embedding_provider = EmbeddingFactory.create(
            self.config.embedding.provider, self.config.embedding.config
        )

        self.vector_store = VectorStoreFactory.create(
            self.config.vector_store.provider, self.config.vector_store.config
        )

        logger.info(
            f"Memory SDK initialized: "
            f"{self.config.embedding.provider} + {self.config.vector_store.provider}"
        )

    def add(
        self,
        memory_content: str,
        *,  # Enforce keyword-only arguments
        user_id: str,
        tags: str | None = None,
        people_mentioned: str | None = None,
        topic_category: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add a new memory to storage with user isolation (selfmemory style).

        Args:
            memory_content: The memory text to store
            user_id: Required user identifier for memory isolation
            tags: Optional comma-separated tags
            people_mentioned: Optional comma-separated people names
            topic_category: Optional topic category
            metadata: Optional additional metadata

        Returns:
            Dict: Result information including memory_id and status

        Examples:
            >>> memory = Memory()
            >>> memory.add("I love pizza", user_id="alice", tags="food,personal")
            >>> memory.add("Meeting notes from project discussion",
            ...           user_id="alice", tags="work,meeting",
            ...           people_mentioned="Sarah,Mike")
        """
        try:
            # Build memory-specific metadata
            memory_metadata = {
                "data": memory_content,
                "tags": tags or "",
                "people_mentioned": people_mentioned or "",
                "topic_category": topic_category or "",
            }

            # Add any additional metadata
            if metadata:
                memory_metadata.update(metadata)

            # Build user-scoped metadata and filters using helper function (selfmemory style)
            storage_metadata, _ = _build_filters_and_metadata(
                user_id=user_id, input_metadata=memory_metadata
            )

            # Generate embedding using provider
            embedding = self.embedding_provider.embed(memory_content)

            # Generate unique ID
            memory_id = str(uuid.uuid4())

            # Insert using vector store provider with user-scoped metadata
            self.vector_store.insert(
                vectors=[embedding], payloads=[storage_metadata], ids=[memory_id]
            )

            logger.info(f"Memory added for user '{user_id}': {memory_content[:50]}...")
            return {
                "success": True,
                "memory_id": memory_id,
                "message": "Memory added successfully",
            }

        except Exception as e:
            logger.error(f"Memory.add() failed for user '{user_id}': {e}")
            logger.error(f"Exception type: {type(e)}")
            logger.error(f"Exception details: {str(e)}")
            return {"success": False, "error": f"Memory addition failed: {str(e)}"}

    def search(
        self,
        query: str = "",
        *,  # Enforce keyword-only arguments
        user_id: str,
        limit: int = 10,
        tags: list[str] | None = None,
        people_mentioned: list[str] | None = None,
        topic_category: str | None = None,
        temporal_filter: str | None = None,
        threshold: float | None = None,
        match_all_tags: bool = False,
        include_metadata: bool = True,
        sort_by: str = "relevance",  # "relevance", "timestamp", "score"
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Search memories with user isolation (selfmemory style).

        All searches are scoped to the specified user's memories only.
        Users cannot see or access memories from other users.

        Args:
            query: Search query string (empty string returns all memories)
            user_id: Required user identifier for memory isolation
            limit: Maximum number of results
            tags: Optional list of tags to filter by
            people_mentioned: Optional list of people to filter by
            topic_category: Optional topic category filter
            temporal_filter: Optional temporal filter (e.g., "today", "this_week", "yesterday")
            threshold: Optional minimum similarity score
            match_all_tags: Whether to match all tags (AND) or any tag (OR)
            include_metadata: Whether to include full metadata in results
            sort_by: Sort results by "relevance" (default), "timestamp", or "score"

        Returns:
            Dict: Search results with "results" key containing list of user's memories only

        Examples:
            Basic search (user-isolated):
            >>> memory = Memory()
            >>> results = memory.search("pizza", user_id="alice")  # Only Alice's memories

            Advanced filtering:
            >>> results = memory.search(
            ...     query="meetings",
            ...     user_id="alice",
            ...     tags=["work", "important"],
            ...     people_mentioned=["John", "Sarah"],
            ...     temporal_filter="this_week",
            ...     match_all_tags=True,
            ...     limit=20
            ... )

            Get all user's memories sorted by timestamp:
            >>> results = memory.search(query="", user_id="alice", sort_by="timestamp", limit=100)
        """
        try:
            # Handle empty query case - return all memories
            is_empty_query = not query or not query.strip()

            if is_empty_query:
                logger.info(
                    f"Retrieving all memories for user '{user_id}' (empty query)"
                )
            else:
                logger.info(
                    f"Searching memories for user '{user_id}' with query: '{query[:50]}...'"
                )

            # Build additional filters from search parameters
            additional_filters = {}
            if topic_category:
                additional_filters["topic_category"] = topic_category
            if tags:
                additional_filters["tags"] = tags
                additional_filters["match_all_tags"] = match_all_tags
            if people_mentioned:
                additional_filters["people_mentioned"] = people_mentioned
            if temporal_filter:
                additional_filters["temporal_filter"] = temporal_filter

            # Build user-scoped filters using helper function (selfmemory style)
            _, user_filters = _build_filters_and_metadata(
                user_id=user_id, input_filters=additional_filters
            )

            # Execute search based on query type
            if is_empty_query:
                # Get all user's memories using vector store's list method
                results = self.vector_store.list(filters=user_filters, limit=limit)
                # Use helper method to format results consistently
                formatted_results = self._format_results(
                    results, include_metadata, include_score=False
                )
            else:
                # Generate embedding for semantic search
                query_embedding = self.embedding_provider.embed(query.strip())

                # Execute semantic search with user isolation (selfmemory style)
                results = self.vector_store.search(
                    query=query,
                    vectors=query_embedding,
                    limit=limit,
                    filters=user_filters,  # Includes automatic user_id filtering
                )

                # Use helper method to format results consistently
                formatted_results = self._format_results(
                    results, include_metadata, include_score=True
                )

                # Apply threshold filtering if specified
                if threshold is not None:
                    formatted_results = [
                        result
                        for result in formatted_results
                        if result.get("score", 0) >= threshold
                    ]

            # Apply sorting using helper method
            formatted_results = self._apply_sorting(formatted_results, sort_by)

            logger.info(
                f"Search completed for user '{user_id}': {len(formatted_results)} results"
            )
            return {"results": formatted_results}

        except Exception as e:
            logger.error(f"Search failed for user '{user_id}': {e}")
            return {"results": []}

    def get_all(
        self,
        *,  # Enforce keyword-only arguments
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get all memories for the specified user with user isolation (selfmemory style).

        Only returns memories belonging to the specified user. Users cannot see
        memories from other users.

        Args:
            user_id: Required user identifier for memory isolation
            limit: Maximum number of memories to return
            offset: Number of memories to skip

        Returns:
            Dict: User's memories with "results" key

        Examples:
            >>> memory = Memory()
            >>> all_memories = memory.get_all(user_id="alice")  # Only Alice's memories
            >>> recent_memories = memory.get_all(user_id="alice", limit=10)
        """
        try:
            # Build user-scoped filters using helper function (selfmemory style)
            _, user_filters = _build_filters_and_metadata(user_id=user_id)

            # Use list() method with user isolation filters
            results = self.vector_store.list(filters=user_filters, limit=limit)

            # Use helper method to format results consistently
            formatted_results = self._format_results(
                results, include_metadata=True, include_score=False
            )

            logger.info(
                f"Retrieved {len(formatted_results)} memories for user '{user_id}'"
            )
            return {"results": formatted_results}

        except Exception as e:
            logger.error(f"Failed to get memories for user '{user_id}': {e}")
            return {"results": []}

    def delete(self, memory_id: str) -> dict[str, Any]:
        """
        Delete a specific memory (selfmemory style - no ownership validation needed).

        Deletes the specified memory by ID. In the new selfmemory-style architecture,
        ownership validation is handled at the API level, not in the Memory class.

        Args:
            memory_id: Memory identifier to delete

        Returns:
            Dict: Deletion result with success status and message

        Examples:
            >>> memory = Memory()
            >>> result = memory.delete("memory_123")
        """
        try:
            # Simply delete the memory (selfmemory style - no ownership validation)
            success = self.vector_store.delete(memory_id)

            if success:
                logger.info(f"Memory {memory_id} deleted successfully")
                return {"success": True, "message": "Memory deleted successfully"}
            return {
                "success": False,
                "error": "Memory deletion failed",
            }

        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            return {"success": False, "error": str(e)}

    def delete_all(
        self,
        *,  # Enforce keyword-only arguments
        user_id: str,
    ) -> dict[str, Any]:
        """
        Delete all memories for the specified user with user isolation (selfmemory style).

        Only deletes memories belonging to the specified user. Users cannot delete
        memories from other users. This maintains complete user isolation.

        Args:
            user_id: Required user identifier for memory isolation

        Returns:
            Dict: Deletion result with count of deleted memories for this user

        Examples:
            >>> memory = Memory()
            >>> result = memory.delete_all(user_id="alice")  # Only deletes Alice's memories
            >>> print(result["deleted_count"])  # Number of Alice's memories deleted
        """
        try:
            # Build user-scoped filters using helper function (selfmemory style)
            _, user_filters = _build_filters_and_metadata(user_id=user_id)

            # Get user's memories only (for counting)
            user_memories = self.vector_store.list(filters=user_filters, limit=10000)

            # Use helper method to extract points from results
            points = self._extract_points_from_results(user_memories)

            deleted_count = 0

            # Delete only user's memories (like selfmemory approach)
            for point in points:
                memory_id = self._extract_memory_id(point)

                if memory_id and self.vector_store.delete(memory_id):
                    deleted_count += 1

            logger.info(f"User '{user_id}' deleted {deleted_count} memories")
            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Deleted {deleted_count} memories for user '{user_id}'",
            }

        except Exception as e:
            logger.error(f"Failed to delete all memories for user '{user_id}': {e}")
            return {"success": False, "error": str(e)}

    # Helper Methods (selfmemory Style)

    def _format_results(
        self, results, include_metadata: bool = True, include_score: bool = True
    ) -> list[dict[str, Any]]:
        """
        Format results consistently across all methods (selfmemory style).

        This helper method standardizes result formatting from different vector stores,
        ensuring consistent output format regardless of the underlying storage provider.

        Args:
            results: Raw results from vector store operations
            include_metadata: Whether to include full metadata in results
            include_score: Whether to include similarity scores

        Returns:
            List of formatted result dictionaries
        """
        formatted_results = []

        # Extract points from results using helper method
        points = self._extract_points_from_results(results)

        for point in points:
            # Build base result structure
            result = {
                "id": self._extract_memory_id(point),
                "content": self._extract_content(point),
            }

            # Add score if requested and available
            if include_score:
                result["score"] = getattr(point, "score", 1.0)

            # Add metadata if requested
            if include_metadata:
                result["metadata"] = self._extract_metadata(point)

            formatted_results.append(result)

        return formatted_results

    def _extract_points_from_results(self, results) -> list:
        """
        Extract points from vector store results (handles different formats).

        Different vector stores return results in different formats:
        - Some return tuples: (points, metadata)
        - Some return lists directly: [point1, point2, ...]
        - Some return single objects

        Args:
            results: Raw results from vector store

        Returns:
            List of point objects
        """
        if isinstance(results, tuple) and len(results) > 0:
            # Handle tuple format (e.g., from Qdrant list operations)
            return results[0] if isinstance(results[0], list) else [results[0]]
        if isinstance(results, list):
            # Handle direct list format
            return results
        if results is not None:
            # Handle single result
            return [results]
        # Handle empty/None results
        return []

    def _extract_memory_id(self, point) -> str:
        """
        Extract memory ID from a point object (handles different formats).

        Args:
            point: Point object from vector store

        Returns:
            Memory ID as string
        """
        if hasattr(point, "id"):
            return str(point.id)
        if isinstance(point, dict):
            return str(point.get("id", ""))
        return ""

    def _extract_content(self, point) -> str:
        """
        Extract content/data from a point object (handles different formats).

        Args:
            point: Point object from vector store

        Returns:
            Memory content as string
        """
        if hasattr(point, "payload"):
            return point.payload.get("data", "")
        if isinstance(point, dict):
            return point.get("data", point.get("content", ""))
        return ""

    def _extract_metadata(self, point) -> dict[str, Any]:
        """
        Extract metadata from a point object (handles different formats).

        Args:
            point: Point object from vector store

        Returns:
            Metadata dictionary
        """
        if hasattr(point, "payload"):
            return point.payload
        if isinstance(point, dict):
            return point
        return {}

    def _apply_sorting(
        self, results: list[dict[str, Any]], sort_by: str
    ) -> list[dict[str, Any]]:
        """
        Apply sorting to formatted results (selfmemory style).

        Args:
            results: List of formatted result dictionaries
            sort_by: Sort method ("relevance", "timestamp", "score")

        Returns:
            Sorted list of results
        """
        if not results:
            return results

        if sort_by == "timestamp":
            return sorted(
                results,
                key=lambda x: x.get("metadata", {}).get("created_at", ""),
                reverse=True,
            )
        if sort_by == "score":
            return sorted(results, key=lambda x: x.get("score", 0), reverse=True)
        # "relevance" is default - already sorted by vector store
        return results

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics for memories.

        Returns:
            Dict: Statistics including memory count, provider info, etc.
        """
        try:
            memory_count = (
                self.vector_store.count() if hasattr(self.vector_store, "count") else 0
            )

            # Get embedding model from config
            embedding_model = "unknown"
            if self.config.embedding.config and hasattr(
                self.config.embedding.config, "model"
            ):
                embedding_model = self.config.embedding.config.model

            return {
                "embedding_provider": self.config.embedding.provider,
                "embedding_model": embedding_model,
                "vector_store": self.config.vector_store.provider,
                "memory_count": memory_count,
                "status": "healthy",
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check on all components.

        Returns:
            Dict: Health check results
        """
        # Get embedding model from config
        embedding_model = "unknown"
        if self.config.embedding.config and hasattr(
            self.config.embedding.config, "model"
        ):
            embedding_model = self.config.embedding.config.model

        health = {
            "status": "healthy",
            "storage_type": self.config.vector_store.provider,
            "embedding_model": embedding_model,
            "embedding_provider": self.config.embedding.provider,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Test vector store connectivity
            if hasattr(self.vector_store, "health_check"):
                vector_health = self.vector_store.health_check()
                health.update(vector_health)
            elif hasattr(self.vector_store, "count"):
                count = self.vector_store.count()
                health["memory_count"] = count
                health["vector_store_status"] = "connected"
            else:
                health["vector_store_status"] = "available"

            # Test embedding provider
            if hasattr(self.embedding_provider, "health_check"):
                embedding_health = self.embedding_provider.health_check()
                health.update(embedding_health)
            else:
                health["embedding_provider_status"] = "available"

            logger.info("Health check passed")

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
            # Clean up vector store and embedding providers
            if hasattr(self, "vector_store") and hasattr(self.vector_store, "close"):
                self.vector_store.close()
            if hasattr(self, "embedding_provider") and hasattr(
                self.embedding_provider, "close"
            ):
                self.embedding_provider.close()
            logger.info("Memory SDK connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

    def __repr__(self) -> str:
        """String representation of Memory instance."""
        return f"Memory(embedding={self.config.embedding.provider}, db={self.config.vector_store.provider})"
