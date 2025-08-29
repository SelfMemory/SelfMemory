"""
Main Memory SDK class for InMemory.

This module provides the primary interface for local InMemory functionality,
with a zero-setup API for direct usage without authentication.

"""

import logging
import uuid
from datetime import datetime
from typing import Any

from inmemory.memory.base import MemoryBase
from inmemory.configs import InMemoryConfig
from inmemory.utils.factory import EmbeddingFactory, VectorStoreFactory

logger = logging.getLogger(__name__)


class Memory(MemoryBase):
    """
    Local Memory class for direct usage without authentication.

    This class provides zero-setup functionality with embedded vector stores.
    No API keys, no user management, no external database setup required.
    Perfect for development, testing, and privacy-focused applications.

    Examples:
        Zero-setup usage (works immediately):
        >>> memory = Memory()
        >>> memory.add("I love pizza")
        >>> results = memory.search("pizza")

        Custom configuration:
        >>> config = InMemoryConfig()
        >>> config.embedding.provider = "ollama"
        >>> config.vector_store.provider = "qdrant"
        >>> memory = Memory(config=config)
    """

    def __init__(self, config: InMemoryConfig | dict | None = None):
        """
        Initialize Memory with clean factory pattern.

        Args:
            config: Optional InMemoryConfig instance or config dictionary

        Examples:
            Zero setup:
            >>> memory = Memory()  # Uses default Ollama + Qdrant

            With config dict (clean API):
            >>> config = {
            ...     "embedding": {"provider": "ollama", "config": {...}},
            ...     "vector_store": {"provider": "qdrant", "config": {...}}
            ... }
            >>> memory = Memory(config=config)

            With config object (legacy):
            >>> config = InMemoryConfig()
            >>> memory = Memory(config=config)
        """
        # Handle different config types for clean API
        if config is None:
            self.config = InMemoryConfig()
        elif isinstance(config, dict):
            # Convert dict to InMemoryConfig for internal use
            self.config = InMemoryConfig.from_dict(config)
        else:
            # Already an InMemoryConfig object
            self.config = config
        
        # Use factories with clean config passing (following mem0's pattern)
        self.embedding_provider = EmbeddingFactory.create(
            self.config.embedding.provider,
            self.config.embedding.get_config_with_defaults()
        )
        
        self.vector_store = VectorStoreFactory.create(
            self.config.vector_store.provider,
            self.config.vector_store.get_config_with_defaults()
        )

        # Store config for backward compatibility
        self.embedding_config = {
            "provider": self.config.embedding.provider,
            **self.config.embedding.get_config_with_defaults()
        }
        self.db_config = {
            "provider": self.config.vector_store.provider,
            **self.config.vector_store.get_config_with_defaults()
        }

        logger.info(f"Memory SDK initialized: {embedding_provider} + {vector_store_provider}")

    def add(
        self,
        memory_content: str,
        tags: str | None = None,
        people_mentioned: str | None = None,
        topic_category: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add a new memory to storage.

        Args:
            memory_content: The memory text to store
            tags: Optional comma-separated tags
            people_mentioned: Optional comma-separated people names
            topic_category: Optional topic category
            metadata: Optional additional metadata

        Returns:
            Dict: Result information including memory_id and status

        Examples:
            >>> memory = Memory()
            >>> memory.add("I love pizza", tags="food,personal")
            >>> memory.add("Meeting notes from project discussion",
            ...           tags="work,meeting",
            ...           people_mentioned="Sarah,Mike")
        """
        try:
            # Generate embedding using provider
            embedding = self.embedding_provider.embed(memory_content)

            # Prepare payload for vector store
            payload = {
                "data": memory_content,
                "tags": tags or "",
                "people_mentioned": people_mentioned or "",
                "topic_category": topic_category or "",
                "created_at": datetime.now().isoformat(),
            }

            # Add custom metadata if provided
            if metadata:
                payload.update(metadata)

            # Generate unique ID
            memory_id = str(uuid.uuid4())

            # Insert using vector store provider
            self.vector_store.insert(
                vectors=[embedding], payloads=[payload], ids=[memory_id]
            )

            logger.info(f"Memory added: {memory_content[:50]}...")
            return {
                "success": True,
                "memory_id": memory_id,
                "message": "Memory added successfully",
            }

        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return {"success": False, "error": str(e)}

    def search(
        self,
        query: str = "",
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
        Unified search interface with comprehensive filtering and sorting options.
        
        Consolidates functionality from retrieve_memory.py and enhanced_search_engine.py
        into a single, powerful search method.

        Args:
            query: Search query string (empty string returns all memories)
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
            Dict: Search results with "results" key containing list of memories

        Examples:
            Basic search:
            >>> memory = Memory()
            >>> results = memory.search("pizza")
            
            Advanced filtering:
            >>> results = memory.search(
            ...     query="meetings",
            ...     tags=["work", "important"],
            ...     people_mentioned=["John", "Sarah"],
            ...     temporal_filter="this_week",
            ...     match_all_tags=True,
            ...     limit=20
            ... )
            
            Get all memories sorted by timestamp:
            >>> results = memory.search(query="", sort_by="timestamp", limit=100)
        """
        try:
            # Handle empty query case - return all memories
            is_empty_query = not query or not query.strip()
            
            if is_empty_query:
                logger.info("Retrieving all memories (empty query)")
            else:
                logger.info(f"Searching memories with query: '{query[:50]}...'")

            # Build comprehensive filters for vector store
            filters = {}
            
            # Add metadata filters
            if topic_category:
                filters["topic_category"] = topic_category
            if tags:
                filters["tags"] = tags
                filters["match_all_tags"] = match_all_tags
            if people_mentioned:
                filters["people_mentioned"] = people_mentioned
            if temporal_filter:
                filters["temporal_filter"] = temporal_filter

            # Execute search based on query type
            if is_empty_query:
                # Get all memories using vector store's list method (following mem0 pattern)
                results = self.vector_store.list(filters=filters, limit=limit)
                # Handle the tuple format returned by list() method
                if isinstance(results, tuple) and len(results) > 0:
                    points = results[0]  # First element contains the points
                else:
                    points = results if isinstance(results, list) else []
                
                # Convert to expected format for consistency
                formatted_results = []
                for point in points:
                    if hasattr(point, 'id') and hasattr(point, 'payload'):
                        # Handle point objects from Qdrant
                        formatted_results.append({
                            "id": str(point.id),
                            "content": point.payload.get("data", ""),
                            "score": 1.0,  # No relevance score for list
                            "metadata": point.payload,
                        })
                    elif isinstance(point, dict):
                        # Handle dict format
                        formatted_results.append({
                            "id": point.get("id", ""),
                            "content": point.get("data", point.get("content", "")),
                            "score": 1.0,
                            "metadata": point,
                        })
            else:
                # Generate embedding for semantic search
                query_embedding = self.embedding_provider.embed(query.strip())

                # Execute semantic search using vector store provider
                results = self.vector_store.search(
                    query=query, 
                    vectors=query_embedding, 
                    limit=limit, 
                    filters=filters
                )

                # Format results to match expected structure
                formatted_results = []
                if results:
                    for point in results:
                        result = {
                            "id": str(point.id),
                            "content": point.payload.get("data", ""),
                            "score": getattr(point, 'score', 0.0),
                            "metadata": point.payload if include_metadata else {},
                        }

                        # Apply threshold filtering if specified
                        if threshold is None or result["score"] >= threshold:
                            formatted_results.append(result)

            # Apply sorting
            if sort_by == "timestamp" and formatted_results:
                formatted_results.sort(
                    key=lambda x: x.get("metadata", {}).get("created_at", ""), 
                    reverse=True
                )
            elif sort_by == "score" and formatted_results:
                formatted_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            # "relevance" is default - already sorted by vector store

            logger.info(f"Search completed: {len(formatted_results)} results")
            return {"results": formatted_results}

        except Exception as e:
            logger.error(f"Unified search failed: {e}")
            return {"results": []}

    def get_all(
        self, limit: int = 100, offset: int = 0
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get all memories.

        Args:
            limit: Maximum number of memories to return
            offset: Number of memories to skip

        Returns:
            Dict: All memories with "results" key

        Examples:
            >>> memory = Memory()
            >>> all_memories = memory.get_all()
            >>> recent_memories = memory.get_all(limit=10)
        """
        try:
            # Use list() method following mem0 pattern
            results = self.vector_store.list(filters=None, limit=limit)
            
            # Handle the tuple format returned by list() method
            if isinstance(results, tuple) and len(results) > 0:
                points = results[0]  # First element contains the points
            else:
                points = results if isinstance(results, list) else []
            
            # Format results to match expected structure
            formatted_results = []
            for point in points:
                if hasattr(point, 'id') and hasattr(point, 'payload'):
                    # Handle point objects from Qdrant
                    formatted_results.append({
                        "id": str(point.id),
                        "content": point.payload.get("data", ""),
                        "metadata": point.payload,
                    })
                elif isinstance(point, dict):
                    # Handle dict format
                    formatted_results.append({
                        "id": point.get("id", ""),
                        "content": point.get("data", point.get("content", "")),
                        "metadata": point,
                    })
            
            logger.info(f"Retrieved {len(formatted_results)} memories")
            return {"results": formatted_results}

        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return {"results": []}

    def delete(self, memory_id: str) -> dict[str, Any]:
        """
        Delete a specific memory.

        Args:
            memory_id: Memory identifier to delete

        Returns:
            Dict: Deletion result
        """
        try:
            success = self.vector_store.delete(memory_id)

            if success:
                logger.info(f"Memory {memory_id} deleted")
                return {"success": True, "message": "Memory deleted successfully"}
            return {
                "success": False,
                "error": "Memory not found or deletion failed",
            }

        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            return {"success": False, "error": str(e)}

    def delete_all(self) -> dict[str, Any]:
        """
        Delete all memories.

        Returns:
            Dict: Deletion result with count of deleted memories
        """
        try:
            # Get current count before deletion
            current_memories = self.get_all(limit=10000)
            memory_count = len(current_memories.get("results", []))

            # Delete all using vector store provider
            success = self.vector_store.delete_all()

            if success:
                logger.info(f"Deleted {memory_count} memories")
                return {
                    "success": True,
                    "deleted_count": memory_count,
                    "message": f"Deleted {memory_count} memories",
                }
            return {"success": False, "error": "Delete all operation failed"}

        except Exception as e:
            logger.error(f"Failed to delete all memories: {e}")
            return {"success": False, "error": str(e)}

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

            return {
                "embedding_provider": self.embedding_config["provider"],
                "embedding_model": self.embedding_config.get("model", "unknown"),
                "vector_store": self.db_config["provider"],
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
        health = {
            "status": "healthy",
            "storage_type": self.db_config.get("provider", "unknown"),
            "embedding_model": self.embedding_config.get("model", "unknown"),
            "embedding_provider": self.embedding_config.get("provider", "unknown"),
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
        return f"Memory(embedding={self.embedding_config['provider']}, db={self.db_config['provider']})"
