import logging
from typing import List, Optional

from qdrant_db import client
from generate_embeddings import get_embeddings
from constants import VectorConstants, SearchConstants

logger = logging.getLogger(__name__)


def retrieve_memories(
    query_text: str,
    keyword_filter: Optional[str] = None,
    limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
) -> List[str]:
    """
    Retrieve memories from the collection based on similarity to the query text.

    Args:
        query_text: The text to search for similar memories
        keyword_filter: Optional keyword to filter results (currently not fully implemented)
        limit: Maximum number of memories to retrieve (default: 3)

    Returns:
        List of memory strings that are most similar to the query

    Raises:
        ValueError: If query text is empty
        Exception: If database operation fails
    """
    if not query_text or not query_text.strip():
        raise ValueError("Query text cannot be empty")

    if limit <= 0 or limit > SearchConstants.MAX_SEARCH_LIMIT:
        raise ValueError(
            f"Limit must be between {SearchConstants.MIN_SEARCH_LIMIT} and {SearchConstants.MAX_SEARCH_LIMIT}"
        )

    try:
        logger.info(f"Retrieving memories for query: '{query_text[:50]}...'")

        query_vector = get_embeddings(query_text.strip())

        search_result = client.query_points(
            collection_name=VectorConstants.COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            with_payload=True,  # Get all payload data
        ).points

        retrieved_memories = []
        for point in search_result:
            if "memory" in point.payload:
                retrieved_memories.append(point.payload["memory"])
            else:
                logger.warning(f"Point {point.id} missing 'memory' in payload")

        logger.info(f"Retrieved {len(retrieved_memories)} memories")
        return retrieved_memories

    except Exception as e:
        logger.error(f"Failed to retrieve memories: {str(e)}")
        raise Exception(f"Memory retrieval failed: {str(e)}")


def search_memories_with_filter(
    query_text: str,
    keyword_filter: str,
    limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
) -> List[str]:
    """
    Search memories with keyword filtering (placeholder for future enhancement).

    Args:
        query_text: The text to search for similar memories
        keyword_filter: Keyword to filter results by
        limit: Maximum number of memories to retrieve

    Returns:
        List of filtered memory strings
    """
    # For now, this is a simple wrapper - can be enhanced to implement actual filtering
    print("limit", limit)
    memories = retrieve_memories(query_text, limit=limit)

    if keyword_filter:
        # Simple keyword filtering - can be enhanced with more sophisticated matching
        filtered_memories = [
            memory for memory in memories if keyword_filter.lower() in memory.lower()
        ]
        return filtered_memories

    return memories


if __name__ == "__main__":
    test_query = "This is a test memory."
    try:
        results = retrieve_memories(test_query)
        print(f"Found {len(results)} memories:")
        for i, memory in enumerate(results, 1):
            print(f"{i}. {memory}")
    except Exception as e:
        print(f"Error: {e}")
