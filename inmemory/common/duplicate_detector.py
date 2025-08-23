"""
Duplicate detection system for memory management.
Prevents storing similar memories and provides options for handling duplicates.
"""

import logging
from typing import Any

# No longer using global MongoDB user manager - using storage abstraction
from qdrant_client.models import FieldCondition, Filter, MatchValue

from inmemory.common.constants import (
    DuplicateConstants,
    MetadataConstants,
    SearchConstants,
)
from inmemory.repositories.qdrant_db import get_qdrant_client
from inmemory.utils.embeddings import get_embeddings

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """
    Handles detection of duplicate memories based on semantic similarity.
    Follows Uncle Bob's Single Responsibility Principle.
    """

    def __init__(self, similarity_threshold: float = None):
        """
        Initialize duplicate detector with configurable threshold.

        Args:
            similarity_threshold: Threshold for considering memories as duplicates
        """
        self.similarity_threshold = (
            similarity_threshold or DuplicateConstants.SIMILARITY_THRESHOLD
        )

    def check_for_duplicates(
        self, memory_content: str, user_id: str, metadata: dict[str, Any] = None
    ) -> tuple[bool, list[dict[str, Any]]]:
        """
        Check if a memory is similar to existing memories for a specific user.

        Args:
            memory_content: The memory text to check for duplicates
            user_id: User ID to get the correct collection
            metadata: Optional metadata for enhanced duplicate detection

        Returns:
            Tuple of (is_duplicate: bool, similar_memories: List[Dict])

        Raises:
            ValueError: If memory content is empty or user_id is invalid
            Exception: If duplicate detection fails
        """
        if not memory_content or not memory_content.strip():
            raise ValueError("Memory content cannot be empty")

        if not user_id:
            raise ValueError("User ID is required for duplicate detection")

        try:
            logger.info(f"Checking for duplicates for user: {user_id}")

            # Generate embedding for the new memory
            query_vector = get_embeddings(memory_content.strip())

            # Search for similar memories in user's collection
            similar_memories = self._find_similar_memories(
                query_vector, memory_content, user_id, metadata
            )

            # Check if any memory exceeds the similarity threshold
            is_duplicate = any(
                memory["score"] >= self.similarity_threshold
                for memory in similar_memories
            )

            logger.info(
                f"Duplicate check result: {is_duplicate}, found {len(similar_memories)} similar memories"
            )
            return is_duplicate, similar_memories

        except Exception as e:
            logger.error(f"Failed to check for duplicates: {str(e)}")
            raise Exception(f"Duplicate detection failed: {str(e)}") from e

    def _find_similar_memories(
        self,
        query_vector: list[float],
        memory_content: str,
        user_id: str,
        metadata: dict[str, Any] = None,
    ) -> list[dict[str, Any]]:
        """
        Find memories similar to the query vector in user's collection.

        Args:
            query_vector: Embedding vector of the memory to check
            memory_content: Original memory content for comparison
            user_id: User ID to get the correct collection
            metadata: Optional metadata for enhanced filtering

        Returns:
            List of similar memories with scores and details
        """
        try:
            # Get user-specific collection name (same logic as other components)
            clean_user_id = "".join(
                c for c in user_id if c.isalnum() or c == "_"
            ).lower()
            collection_name = f"memories_{clean_user_id}"

            # Build filter conditions if metadata is provided
            # query_filter = self._build_duplicate_filter(metadata) if metadata else None

            # Search for similar memories in user's collection
            client = get_qdrant_client()
            search_result = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=DuplicateConstants.MAX_DUPLICATE_CHECK_LIMIT,
                score_threshold=SearchConstants.DEFAULT_SCORE_THRESHOLD,
                # query_filter=query_filter,
                with_payload=True,
            ).points

            similar_memories = []
            for point in search_result:
                if MetadataConstants.MEMORY_FIELD in point.payload:
                    memory_data = {
                        "id": point.id,
                        "score": point.score,
                        "memory": point.payload[MetadataConstants.MEMORY_FIELD],
                        "timestamp": point.payload.get(
                            MetadataConstants.TIMESTAMP_FIELD
                        ),
                        "metadata": {
                            "tags": point.payload.get(MetadataConstants.TAGS_FIELD, []),
                            "people_mentioned": point.payload.get(
                                MetadataConstants.PEOPLE_FIELD, []
                            ),
                            "topic_category": point.payload.get(
                                MetadataConstants.TOPIC_FIELD
                            ),
                        },
                    }
                    similar_memories.append(memory_data)

            # Sort by similarity score (descending)
            similar_memories.sort(key=lambda x: x["score"], reverse=True)
            return similar_memories

        except Exception as e:
            logger.error(f"Failed to find similar memories: {str(e)}")
            return []

    def _build_duplicate_filter(self, metadata: dict[str, Any]) -> Filter:
        """
        Build filter conditions to enhance duplicate detection.

        Args:
            metadata: Metadata to use for filtering

        Returns:
            Qdrant Filter object for enhanced duplicate detection
        """
        conditions = []

        try:
            # Filter by topic category if provided
            if metadata.get(MetadataConstants.TOPIC_FIELD):
                conditions.append(
                    FieldCondition(
                        key=MetadataConstants.TOPIC_FIELD,
                        match=MatchValue(value=metadata[MetadataConstants.TOPIC_FIELD]),
                    )
                )

            # Filter by tags if provided
            if metadata.get(MetadataConstants.TAGS_FIELD):
                for tag in metadata[MetadataConstants.TAGS_FIELD]:
                    conditions.append(
                        FieldCondition(
                            key=f"{MetadataConstants.TAGS_FIELD}[]",
                            match=MatchValue(value=tag),
                        )
                    )

            return Filter(must=conditions) if conditions else None

        except Exception as e:
            logger.warning(f"Failed to build duplicate filter: {str(e)}")
            return None


class DuplicateHandler:
    """
    Handles different actions when duplicates are detected.
    Separates duplicate detection from duplicate handling logic.
    """

    @staticmethod
    def handle_duplicate(
        action: str,
        new_memory: str,
        existing_memories: list[dict[str, Any]],
        new_metadata: dict[str, Any] = None,
    ) -> dict[str, Any]:
        """
        Handle detected duplicates based on the specified action.

        Args:
            action: Action to take (skip, merge, add)
            new_memory: New memory content
            existing_memories: List of existing similar memories
            new_metadata: Metadata for the new memory

        Returns:
            Dictionary with action result and details
        """
        try:
            if action == DuplicateConstants.DUPLICATE_ACTION_SKIP:
                return DuplicateHandler._skip_duplicate(existing_memories)

            if action == DuplicateConstants.DUPLICATE_ACTION_MERGE:
                return DuplicateHandler._merge_duplicate(
                    new_memory, existing_memories, new_metadata
                )

            if action == DuplicateConstants.DUPLICATE_ACTION_ADD:
                return DuplicateHandler._add_anyway(new_memory, existing_memories)

            logger.warning(f"Unknown duplicate action: {action}")
            return {
                "action": "error",
                "message": f"Unknown action: {action}",
                "success": False,
            }

        except Exception as e:
            logger.error(f"Failed to handle duplicate: {str(e)}")
            return {
                "action": "error",
                "message": f"Duplicate handling failed: {str(e)}",
                "success": False,
            }

    @staticmethod
    def _skip_duplicate(existing_memories: list[dict[str, Any]]) -> dict[str, Any]:
        """Skip adding the duplicate memory."""
        most_similar = existing_memories[0] if existing_memories else {}
        similarity_score = most_similar.get("score", 0)
        existing_content = most_similar.get("memory", "")

        return {
            "action": "skipped",
            "message": f"Memory rejected due to duplicate detection (similarity: {similarity_score:.3f} >= {DuplicateConstants.SIMILARITY_THRESHOLD}). A very similar memory already exists.",
            "existing_memory": existing_content,
            "similarity_score": similarity_score,
            "threshold": DuplicateConstants.SIMILARITY_THRESHOLD,
            "reason": "duplicate_detected",
            "success": True,
        }

    @staticmethod
    def _merge_duplicate(
        new_memory: str,
        existing_memories: list[dict[str, Any]],
        new_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge the new memory with the most similar existing memory."""
        if not existing_memories:
            return {
                "action": "error",
                "message": "No existing memories to merge with",
                "success": False,
            }

        most_similar = existing_memories[0]
        merged_content = (
            f"{most_similar['memory']}\n\n[Additional context: {new_memory}]"
        )

        # Note: Actual merging would require updating the existing point in Qdrant
        # This is a placeholder for the merge logic
        return {
            "action": "merged",
            "message": "Memory merged with existing similar memory",
            "merged_content": merged_content,
            "original_id": most_similar["id"],
            "success": True,
        }

    @staticmethod
    def _add_anyway(
        new_memory: str, existing_memories: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Add the memory despite similarity to existing memories."""
        most_similar = existing_memories[0] if existing_memories else {}
        return {
            "action": "added",
            "message": f"Memory added despite similarity (similarity: {most_similar.get('score', 0):.3f})",
            "similar_memory": most_similar.get("memory", ""),
            "success": True,
        }


if __name__ == "__main__":
    # Test duplicate detection
    detector = DuplicateDetector()

    test_memory = "This is a test memory about Python programming"
    test_user_id = "test_user_123"  # Test user ID
    test_metadata = {"tags": ["programming", "python"], "topic_category": "learning"}

    try:
        is_duplicate, similar_memories = detector.check_for_duplicates(
            test_memory, test_user_id, test_metadata
        )
        print(f"Is duplicate: {is_duplicate}")
        print(f"Similar memories found: {len(similar_memories)}")

        for memory in similar_memories[:3]:  # Show top 3
            print(
                f"  - Score: {memory['score']:.3f}, Content: {memory['memory'][:50]}..."
            )

    except Exception as e:
        print(f"Test failed: {e}")
