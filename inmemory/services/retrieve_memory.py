import logging

from inmemory.common.constants import SearchConstants

# No longer using global MongoDB user manager - using storage abstraction
from inmemory.repositories.qdrant_db import get_qdrant_client
from inmemory.security.encryption import decrypt_memory_payload
from inmemory.utils.embeddings import get_embeddings

logger = logging.getLogger(__name__)


def retrieve_memories(
    query_text: str,
    user_id: str,
    keyword_filter: str | None = None,
    limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
) -> list[str]:
    """
    Retrieve memories from user's collection based on similarity to the query text.

    Args:
        query_text: The text to search for similar memories
        user_id: User ID to get the correct collection
        keyword_filter: Optional keyword to filter results (currently not fully implemented)
        limit: Maximum number of memories to retrieve (default: 3)

    Returns:
        List of memory strings that are most similar to the query

    Raises:
        ValueError: If query text is empty or user_id is invalid
        Exception: If database operation fails
    """
    if not query_text or not query_text.strip():
        raise ValueError("Query text cannot be empty")

    if not user_id:
        raise ValueError("User ID is required for memory retrieval")

    if limit <= 0 or limit > SearchConstants.MAX_SEARCH_LIMIT:
        raise ValueError(
            f"Limit must be between {SearchConstants.MIN_SEARCH_LIMIT} and {SearchConstants.MAX_SEARCH_LIMIT}"
        )

    try:
        logger.info(
            f"Retrieving memories for user {user_id}, query: '{query_text[:50]}...'"
        )

        # Get user-specific collection name (same logic as other components)
        clean_user_id = "".join(c for c in user_id if c.isalnum() or c == "_").lower()
        collection_name = f"memories_{clean_user_id}"

        query_vector = get_embeddings(query_text.strip())

        client = get_qdrant_client()
        search_result = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,  # Get all payload data
        ).points

        retrieved_memories = []
        for point in search_result:
            if "memory" in point.payload:
                # Decrypt the payload before extracting memory content
                try:
                    decrypted_payload = decrypt_memory_payload(point.payload, user_id)
                    retrieved_memories.append(decrypted_payload["memory"])
                except Exception as decrypt_error:
                    logger.error(
                        f"Failed to decrypt memory {point.id}: {str(decrypt_error)}"
                    )
                    # Skip this memory if decryption fails
                    continue
            else:
                logger.warning(f"Point {point.id} missing 'memory' in payload")

        logger.info(f"Retrieved {len(retrieved_memories)} memories")
        return retrieved_memories

    except Exception as e:
        logger.error(f"Failed to retrieve memories: {str(e)}")
        raise Exception(f"Memory retrieval failed: {str(e)}") from e


def search_memories_with_filter(
    query_text: str,
    user_id: str,
    keyword_filter: str,
    limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
) -> list[str]:
    """
    Search memories with keyword filtering (placeholder for future enhancement).

    Args:
        query_text: The text to search for similar memories
        user_id: User ID to get the correct collection
        keyword_filter: Keyword to filter results by
        limit: Maximum number of memories to retrieve

    Returns:
        List of filtered memory strings
    """
    # For now, this is a simple wrapper - can be enhanced to implement actual filtering
    print("limit", limit)
    memories = retrieve_memories(query_text, user_id, limit=limit)

    if keyword_filter:
        # Simple keyword filtering - can be enhanced with more sophisticated matching
        filtered_memories = [
            memory for memory in memories if keyword_filter.lower() in memory.lower()
        ]
        return filtered_memories

    return memories


if __name__ == "__main__":
    test_query = "This is a test memory."
    test_user_id = "test_user_123"  # Test user ID
    try:
        results = retrieve_memories(test_query, test_user_id)
        print(f"Found {len(results)} memories:")
        for i, memory in enumerate(results, 1):
            print(f"{i}. {memory}")
    except Exception as e:
        print(f"Error: {e}")
