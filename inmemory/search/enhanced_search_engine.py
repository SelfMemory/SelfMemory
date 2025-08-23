"""
Enhanced search engine for memory retrieval with comprehensive filtering capabilities.
Supports semantic similarity, temporal filtering, metadata search, and hybrid queries.
"""

import logging
from typing import Any

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from inmemory.common.constants import (
    MetadataConstants,
    SearchConstants,
)
from inmemory.common.temporal_utils import TemporalFilter, TemporalProcessor
from inmemory.repositories.qdrant_db import (
    ensure_user_collection_exists,
    get_qdrant_client,
)
from inmemory.security.encryption import decrypt_memory_payload
from inmemory.utils.embeddings import get_embeddings

logger = logging.getLogger(__name__)


class EnhancedSearchEngine:
    """
    Comprehensive search engine with all advanced memory retrieval capabilities.
    Follows Uncle Bob's Single Responsibility and Open/Closed Principles.
    """

    def __init__(self):
        """Initialize the enhanced search engine."""
        self.temporal_processor = TemporalProcessor()
        self.temporal_filter = TemporalFilter()

    def search_memories(
        self,
        query: str,
        user_id: str,
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
        score_threshold: float = SearchConstants.DEFAULT_SCORE_THRESHOLD,
        tags: list[str] = None,
        people_mentioned: list[str] = None,
        topic_category: str = None,
        temporal_filter: str = None,
        include_payload: bool = True,
        include_vectors: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Enhanced memory search with comprehensive filtering options.

        Args:
            query: Semantic search query
            limit: Maximum number of results to return
            score_threshold: Minimum similarity score threshold
            tags: Filter by specific tags
            people_mentioned: Filter by people mentioned
            topic_category: Filter by topic category
            temporal_filter: Temporal filter (e.g., "yesterday", "this_week")
            include_payload: Whether to include payload data
            include_vectors: Whether to include vector data

        Returns:
            List of matching memories with metadata

        Raises:
            ValueError: If query is empty or parameters are invalid
            Exception: If search fails
        """
        # Handle empty query case - return all memories sorted by timestamp
        is_empty_query = not query or not query.strip()

        try:
            if is_empty_query:
                logger.info("Getting all memories (empty query) for user")
            else:
                logger.info("Searching memories with query")

            # Build comprehensive filter
            search_filter = self._build_comprehensive_filter(
                tags=tags,
                people_mentioned=people_mentioned,
                topic_category=topic_category,
                temporal_filter=temporal_filter,
            )

            # Get user collection name and client
            collection_name = ensure_user_collection_exists(user_id)
            client = get_qdrant_client()

            if is_empty_query:
                # For empty queries, use pagination to get ALL memories
                # This is much more scalable than limiting to just first batch
                search_result = self._get_all_memories_paginated(
                    client=client,
                    collection_name=collection_name,
                    search_filter=search_filter,
                    max_memories=limit
                    * 10,  # Allow up to 10x the requested limit for all memories
                    include_payload=include_payload,
                    include_vectors=include_vectors,
                )

                # Sort by timestamp in Python (newest first)
                if search_result:
                    search_result = sorted(
                        search_result,
                        key=lambda x: x.payload.get(
                            MetadataConstants.TIMESTAMP_FIELD, ""
                        ),
                        reverse=True,  # Most recent first
                    )

                # Apply the original limit after sorting
                search_result = search_result[:limit]
            else:
                # Generate query embedding for semantic search
                query_vector = get_embeddings(query.strip())

                # Execute semantic search
                search_result = client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=limit,
                    score_threshold=score_threshold,
                    query_filter=search_filter,
                    with_payload=include_payload,
                    with_vectors=include_vectors,
                ).points

            # Format results
            formatted_results = self._format_search_results(search_result, user_id)

            logger.info(f"Found {len(formatted_results)} memories matching criteria")
            return formatted_results

        except Exception as e:
            logger.error(f"Enhanced search failed: {str(e)}")
            raise Exception(f"Memory search failed: {str(e)}") from e

    def temporal_search(
        self,
        temporal_query: str,
        user_id: str,
        semantic_query: str = None,
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
    ) -> list[dict[str, Any]]:
        """
        Search memories based on temporal criteria with optional semantic filtering.

        Args:
            temporal_query: Natural language temporal query (e.g., "yesterday", "weekends")
            semantic_query: Optional semantic search query
            limit: Maximum number of results

        Returns:
            List of temporally filtered memories
        """
        try:
            logger.info(
                f"Temporal search: '{temporal_query}' + semantic: '{semantic_query}'"
            )

            # Parse temporal query
            temporal_filters = self.temporal_processor.parse_temporal_query(
                temporal_query
            )

            if not temporal_filters:
                logger.warning(f"Could not parse temporal query: '{temporal_query}'")
                return []

            # Build temporal filter conditions
            filter_conditions = self.temporal_filter.build_temporal_conditions(
                temporal_filters
            )

            # Get user collection name and client
            collection_name = ensure_user_collection_exists(user_id)
            client = get_qdrant_client()

            if semantic_query:
                # Hybrid search: temporal + semantic
                query_vector = get_embeddings(semantic_query.strip())
                search_result = client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=limit,
                    query_filter=Filter(**filter_conditions)
                    if filter_conditions
                    else None,
                    with_payload=True,
                ).points
            else:
                # Pure temporal search (scroll with filter)
                search_result = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=Filter(**filter_conditions)
                    if filter_conditions
                    else None,
                    limit=limit,
                    with_payload=True,
                )[0]  # scroll returns (points, next_page_offset)

            formatted_results = self._format_search_results(search_result, user_id)
            logger.info(f"Temporal search found {len(formatted_results)} memories")
            return formatted_results

        except Exception as e:
            logger.error(f"Temporal search failed: {str(e)}")
            raise Exception(f"Temporal search failed: {str(e)}") from e

    def tag_search(
        self,
        tags: list[str],
        user_id: str,
        semantic_query: str = None,
        match_all_tags: bool = False,
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
    ) -> list[dict[str, Any]]:
        """
        Search memories by tags with optional semantic filtering.

        Args:
            tags: List of tags to search for
            semantic_query: Optional semantic search query
            match_all_tags: Whether to match all tags (AND) or any tag (OR)
            limit: Maximum number of results

        Returns:
            List of tag-filtered memories
        """
        try:
            logger.info(f"Tag search: {tags} (match_all: {match_all_tags})")

            # Build tag filter
            tag_conditions = []
            for tag in tags:
                tag_conditions.append(
                    FieldCondition(
                        key=f"{MetadataConstants.TAGS_FIELD}[]",
                        match=MatchValue(value=tag.lower().strip()),
                    )
                )

            # Use must (AND) or should (OR) based on match_all_tags
            if match_all_tags:
                tag_filter = Filter(must=tag_conditions)
            else:
                tag_filter = Filter(should=tag_conditions)

            # Get user collection name and client
            collection_name = ensure_user_collection_exists(user_id)
            client = get_qdrant_client()

            if semantic_query:
                # Hybrid: semantic + tag filtering
                query_vector = get_embeddings(semantic_query.strip())
                search_result = client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=limit,
                    query_filter=tag_filter,
                    with_payload=True,
                ).points
            else:
                # Pure tag search
                search_result = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=tag_filter,
                    limit=limit,
                    with_payload=True,
                )[0]

            formatted_results = self._format_search_results(search_result, user_id)
            logger.info(f"Tag search found {len(formatted_results)} memories")
            return formatted_results

        except Exception as e:
            logger.error(f"Tag search failed: {str(e)}")
            raise Exception(f"Tag search failed: {str(e)}") from e

    def people_search(
        self,
        people: list[str],
        user_id: str,
        semantic_query: str = None,
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
    ) -> list[dict[str, Any]]:
        """
        Search memories by people mentioned.

        Args:
            people: List of people names to search for
            semantic_query: Optional semantic search query
            limit: Maximum number of results

        Returns:
            List of people-filtered memories
        """
        try:
            logger.info(f"People search: {people}")

            # Build people filter
            people_conditions = []
            for person in people:
                people_conditions.append(
                    FieldCondition(
                        key=f"{MetadataConstants.PEOPLE_FIELD}[]",
                        match=MatchValue(value=person.strip()),
                    )
                )

            people_filter = Filter(should=people_conditions)  # OR logic for people

            # Get user collection name and client
            collection_name = ensure_user_collection_exists(user_id)
            client = get_qdrant_client()

            if semantic_query:
                query_vector = get_embeddings(semantic_query.strip())
                search_result = client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=limit,
                    query_filter=people_filter,
                    with_payload=True,
                ).points
            else:
                search_result = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=people_filter,
                    limit=limit,
                    with_payload=True,
                )[0]

            formatted_results = self._format_search_results(search_result, user_id)
            logger.info(f"People search found {len(formatted_results)} memories")
            return formatted_results

        except Exception as e:
            logger.error(f"People search failed: {str(e)}")
            raise Exception(f"People search failed: {str(e)}") from e

    def topic_search(
        self,
        topic_category: str,
        user_id: str,
        semantic_query: str = None,
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
    ) -> list[dict[str, Any]]:
        """
        Search memories by topic category.

        Args:
            topic_category: Topic category to search for
            semantic_query: Optional semantic search query
            limit: Maximum number of results

        Returns:
            List of topic-filtered memories
        """
        try:
            logger.info(f"Topic search: '{topic_category}'")

            # Build topic filter
            topic_filter = Filter(
                must=[
                    FieldCondition(
                        key=MetadataConstants.TOPIC_FIELD,
                        match=MatchValue(value=topic_category.lower().strip()),
                    )
                ]
            )

            # Get user collection name and client
            collection_name = ensure_user_collection_exists(user_id)
            client = get_qdrant_client()

            if semantic_query:
                query_vector = get_embeddings(semantic_query.strip())
                search_result = client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=limit,
                    query_filter=topic_filter,
                    with_payload=True,
                ).points
            else:
                search_result = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=topic_filter,
                    limit=limit,
                    with_payload=True,
                )[0]

            formatted_results = self._format_search_results(search_result, user_id)
            logger.info(f"Topic search found {len(formatted_results)} memories")
            return formatted_results

        except Exception as e:
            logger.error(f"Topic search failed: {str(e)}")
            raise Exception(f"Topic search failed: {str(e)}") from e

    def _build_comprehensive_filter(
        self,
        tags: list[str] = None,
        people_mentioned: list[str] = None,
        topic_category: str = None,
        temporal_filter: str = None,
    ) -> Filter | None:
        """
        Build comprehensive Qdrant filter from multiple criteria.

        Args:
            tags: Filter by tags
            people_mentioned: Filter by people mentioned
            topic_category: Filter by topic category
            temporal_filter: Temporal filter string

        Returns:
            Qdrant Filter object or None if no filters
        """
        conditions = []

        try:
            # Add tag conditions
            if tags:
                for tag in tags:
                    conditions.append(
                        FieldCondition(
                            key=f"{MetadataConstants.TAGS_FIELD}[]",
                            match=MatchAny(value=tag.lower().strip()),
                        )
                    )

            # Add people conditions
            if people_mentioned:
                people_conditions = []
                for person in people_mentioned:
                    people_conditions.append(
                        FieldCondition(
                            key=f"{MetadataConstants.PEOPLE_FIELD}[]",
                            match=MatchAny(value=person.strip()),
                        )
                    )
                # Use should (OR) for people - match any of the mentioned people
                if people_conditions:
                    conditions.extend(people_conditions)

            # Add topic condition
            if topic_category:
                conditions.append(
                    FieldCondition(
                        key=MetadataConstants.TOPIC_FIELD,
                        match=MatchAny(value=topic_category.lower().strip()),
                    )
                )

            # Add temporal conditions
            if temporal_filter:
                temporal_filters = self.temporal_processor.parse_temporal_query(
                    temporal_filter
                )
                if temporal_filters:
                    temporal_conditions = (
                        self.temporal_filter.build_temporal_conditions(temporal_filters)
                    )
                    if temporal_conditions.get("must"):
                        conditions.extend(temporal_conditions["must"])

            return Filter(must=conditions) if conditions else None

        except Exception as e:
            logger.warning(f"Failed to build comprehensive filter: {str(e)}")
            return None

    def _get_all_memories_paginated(
        self,
        client,
        collection_name: str,
        search_filter: Filter | None = None,
        max_memories: int = 1000,
        batch_size: int = 100,
        include_payload: bool = True,
        include_vectors: bool = False,
    ) -> list:
        """
        Get all memories using pagination (based on user's suggested approach).
        This is much more scalable than loading everything at once.

        Args:
            client: Qdrant client instance
            collection_name: Name of the collection
            search_filter: Optional filter to apply
            max_memories: Maximum memories to retrieve (safety limit)
            batch_size: Number of memories per batch
            include_payload: Whether to include payload data
            include_vectors: Whether to include vector data

        Returns:
            List of all memory points
        """
        all_memories = []
        offset = None
        retrieved_count = 0

        try:
            logger.info(
                f"Starting paginated retrieval of all memories (max: {max_memories})"
            )

            while retrieved_count < max_memories:
                response = client.scroll(
                    collection_name=collection_name,
                    limit=min(batch_size, max_memories - retrieved_count),
                    offset=offset,
                    scroll_filter=search_filter,
                    with_payload=include_payload,
                    with_vectors=include_vectors,
                )

                points, next_offset = response[0], response[1]

                if not points:
                    logger.info(
                        f"No more memories found. Total retrieved: {retrieved_count}"
                    )
                    break

                all_memories.extend(points)
                retrieved_count += len(points)
                offset = next_offset

                logger.debug(
                    f"Retrieved batch of {len(points)} memories (total: {retrieved_count})"
                )

                # If next_offset is None, we've reached the end
                if next_offset is None:
                    logger.info(
                        f"Reached end of collection. Total retrieved: {retrieved_count}"
                    )
                    break

            logger.info(f"Paginated retrieval complete: {len(all_memories)} memories")
            return all_memories

        except Exception as e:
            logger.error(f"Paginated memory retrieval failed: {str(e)}")
            # Return whatever we managed to get
            return all_memories

    def _format_search_results(
        self, search_points: list, user_id: str
    ) -> list[dict[str, Any]]:
        """
        Format search results into consistent structure with decryption.

        Args:
            search_points: Raw search results from Qdrant
            user_id: User identifier for decryption

        Returns:
            Formatted search results with decrypted content
        """
        formatted_results = []

        for point in search_points:
            if (
                not hasattr(point, "payload")
                or MetadataConstants.MEMORY_FIELD not in point.payload
            ):
                continue

            try:
                # Decrypt the payload before extracting data
                decrypted_payload = decrypt_memory_payload(point.payload, user_id)

                # Get timestamp with fallback for older memories
                timestamp = decrypted_payload.get(MetadataConstants.TIMESTAMP_FIELD)

                # Handle missing timestamps for older memories
                if not timestamp:
                    logger.warning(
                        f"Memory {point.id} missing timestamp, using fallback"
                    )
                    # Use a fallback date for memories without timestamps
                    timestamp = (
                        "2024-01-01T00:00:00.000000"  # Fallback for older memories
                    )

                result = {
                    "id": point.id,
                    "score": getattr(point, "score", None),
                    "memory": decrypted_payload[MetadataConstants.MEMORY_FIELD],
                    "timestamp": timestamp,
                    "tags": decrypted_payload.get(MetadataConstants.TAGS_FIELD, []),
                    "people_mentioned": decrypted_payload.get(
                        MetadataConstants.PEOPLE_FIELD, []
                    ),
                    "topic_category": decrypted_payload.get(
                        MetadataConstants.TOPIC_FIELD
                    ),
                    "temporal_data": decrypted_payload.get(
                        MetadataConstants.TEMPORAL_FIELD, {}
                    ),
                }

                formatted_results.append(result)

            except Exception as decrypt_error:
                logger.error(
                    f"Failed to decrypt memory {point.id}: {str(decrypt_error)}"
                )
                # Skip this memory if decryption fails
                continue

        return formatted_results


if __name__ == "__main__":
    # Test enhanced search engine
    search_engine = EnhancedSearchEngine()

    try:
        # Test basic semantic search
        results = search_engine.search_memories("python programming", limit=3)
        print(f"Semantic search found {len(results)} results")

        # Test temporal search
        temporal_results = search_engine.temporal_search("yesterday", "meetings")
        print(f"Temporal search found {len(temporal_results)} results")

        # Test tag search
        tag_results = search_engine.tag_search(["programming", "learning"])
        print(f"Tag search found {len(tag_results)} results")

    except Exception as e:
        print(f"Search engine test failed: {e}")
