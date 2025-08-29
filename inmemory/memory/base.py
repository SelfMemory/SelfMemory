"""
Abstract base class for memory implementations.

This module defines the interface that all memory implementations must follow,
ensuring consistent behavior across different memory types.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MemoryBase(ABC):
    """
    Abstract base class for all memory implementations.
    
    This class defines the core interface that all memory implementations
    must implement, ensuring consistent behavior and making it easy to
    swap between different memory backends or add new functionality.
    
    All memory implementations should inherit from this class and implement
    all abstract methods.
    """

    @abstractmethod
    def add(
        self,
        memory_content: str,
        tags: Optional[str] = None,
        people_mentioned: Optional[str] = None,
        topic_category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 10,
        tags: Optional[List[str]] = None,
        people_mentioned: Optional[List[str]] = None,
        topic_category: Optional[str] = None,
        temporal_filter: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search memories with semantic similarity.

        Args:
            query: Search query string
            limit: Maximum number of results
            tags: Optional list of tags to filter by
            people_mentioned: Optional list of people to filter by
            topic_category: Optional topic category filter
            temporal_filter: Optional temporal filter (e.g., "today", "this_week")
            threshold: Optional minimum similarity score

        Returns:
            Dict: Search results with "results" key containing list of memories
        """
        pass

    @abstractmethod
    def get_all(
        self, limit: int = 100, offset: int = 0
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all memories.

        Args:
            limit: Maximum number of memories to return
            offset: Number of memories to skip

        Returns:
            Dict: All memories with "results" key
        """
        pass

    @abstractmethod
    def delete(self, memory_id: str) -> Dict[str, Any]:
        """
        Delete a specific memory.

        Args:
            memory_id: Memory identifier to delete

        Returns:
            Dict: Deletion result
        """
        pass

    @abstractmethod
    def delete_all(self) -> Dict[str, Any]:
        """
        Delete all memories.

        Returns:
            Dict: Deletion result with count of deleted memories
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics for memories.

        Returns:
            Dict: Statistics including memory count, provider info, etc.
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all components.

        Returns:
            Dict: Health check results
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close connections and cleanup resources.

        Should be called when Memory instance is no longer needed.
        """
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()
