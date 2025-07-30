"""
Enhanced search engine for memory retrieval with comprehensive filtering capabilities.
Supports semantic similarity, temporal filtering, metadata search, and hybrid queries.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range, MatchAny

from constants import (
    VectorConstants,
    MetadataConstants,
    SearchConstants,
    TemporalConstants,
    SearchFilters,
)
from qdrant_db import client
from generate_embeddings import get_embeddings
from src.shared.temporal_utils import TemporalProcessor, TemporalFilter

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
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
        score_threshold: float = SearchConstants.DEFAULT_SCORE_THRESHOLD,
        tags: List[str] = None,
        people_mentioned: List[str] = None,
        topic_category: str = None,
        temporal_filter: str = None,
        include_payload: bool = True,
        include_vectors: bool = False,
    ) -> List[Dict[str, Any]]:
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
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        # if not (
        #     SearchConstants.MIN_SEARCH_LIMIT
        #     <= limit
        #     <= SearchConstants.MAX_SEARCH_LIMIT
        # ):
        #     raise ValueError(
        #         f"Limit must be between {SearchConstants.MIN_SEARCH_LIMIT} and {SearchConstants.MAX_SEARCH_LIMIT}"
        #     )

        try:
            logger.info(f"Searching memories with query")

            # Generate query embedding
            query_vector = get_embeddings(query.strip())

            # Build comprehensive filter
            search_filter = self._build_comprehensive_filter(
                tags=tags,
                people_mentioned=people_mentioned,
                topic_category=topic_category,
                temporal_filter=temporal_filter,
            )

            # Execute search
            search_result = client.query_points(
                collection_name=VectorConstants.COLLECTION_NAME,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=search_filter,
                with_payload=include_payload,
                with_vectors=include_vectors,
            ).points

            # Format results
            formatted_results = self._format_search_results(search_result)

            logger.info(f"Found {len(formatted_results)} memories matching criteria")
            return formatted_results

        except Exception as e:
            logger.error(f"Enhanced search failed: {str(e)}")
            raise Exception(f"Memory search failed: {str(e)}")

    def temporal_search(
        self,
        temporal_query: str,
        semantic_query: str = None,
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
    ) -> List[Dict[str, Any]]:
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

            if semantic_query:
                # Hybrid search: temporal + semantic
                query_vector = get_embeddings(semantic_query.strip())
                search_result = client.query_points(
                    collection_name=VectorConstants.COLLECTION_NAME,
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
                    collection_name=VectorConstants.COLLECTION_NAME,
                    scroll_filter=Filter(**filter_conditions)
                    if filter_conditions
                    else None,
                    limit=limit,
                    with_payload=True,
                )[0]  # scroll returns (points, next_page_offset)

            formatted_results = self._format_search_results(search_result)
            logger.info(f"Temporal search found {len(formatted_results)} memories")
            return formatted_results

        except Exception as e:
            logger.error(f"Temporal search failed: {str(e)}")
            raise Exception(f"Temporal search failed: {str(e)}")

    def tag_search(
        self,
        tags: List[str],
        semantic_query: str = None,
        match_all_tags: bool = False,
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
    ) -> List[Dict[str, Any]]:
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

            if semantic_query:
                # Hybrid: semantic + tag filtering
                query_vector = get_embeddings(semantic_query.strip())
                search_result = client.query_points(
                    collection_name=VectorConstants.COLLECTION_NAME,
                    query=query_vector,
                    limit=limit,
                    query_filter=tag_filter,
                    with_payload=True,
                ).points
            else:
                # Pure tag search
                search_result = client.scroll(
                    collection_name=VectorConstants.COLLECTION_NAME,
                    scroll_filter=tag_filter,
                    limit=limit,
                    with_payload=True,
                )[0]

            formatted_results = self._format_search_results(search_result)
            logger.info(f"Tag search found {len(formatted_results)} memories")
            return formatted_results

        except Exception as e:
            logger.error(f"Tag search failed: {str(e)}")
            raise Exception(f"Tag search failed: {str(e)}")

    def people_search(
        self,
        people: List[str],
        semantic_query: str = None,
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
    ) -> List[Dict[str, Any]]:
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

            if semantic_query:
                query_vector = get_embeddings(semantic_query.strip())
                search_result = client.query_points(
                    collection_name=VectorConstants.COLLECTION_NAME,
                    query=query_vector,
                    limit=limit,
                    query_filter=people_filter,
                    with_payload=True,
                ).points
            else:
                search_result = client.scroll(
                    collection_name=VectorConstants.COLLECTION_NAME,
                    scroll_filter=people_filter,
                    limit=limit,
                    with_payload=True,
                )[0]

            formatted_results = self._format_search_results(search_result)
            logger.info(f"People search found {len(formatted_results)} memories")
            return formatted_results

        except Exception as e:
            logger.error(f"People search failed: {str(e)}")
            raise Exception(f"People search failed: {str(e)}")

    def topic_search(
        self,
        topic_category: str,
        semantic_query: str = None,
        limit: int = SearchConstants.DEFAULT_SEARCH_LIMIT,
    ) -> List[Dict[str, Any]]:
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

            if semantic_query:
                query_vector = get_embeddings(semantic_query.strip())
                search_result = client.query_points(
                    collection_name=VectorConstants.COLLECTION_NAME,
                    query=query_vector,
                    limit=limit,
                    query_filter=topic_filter,
                    with_payload=True,
                ).points
            else:
                search_result = client.scroll(
                    collection_name=VectorConstants.COLLECTION_NAME,
                    scroll_filter=topic_filter,
                    limit=limit,
                    with_payload=True,
                )[0]

            formatted_results = self._format_search_results(search_result)
            logger.info(f"Topic search found {len(formatted_results)} memories")
            return formatted_results

        except Exception as e:
            logger.error(f"Topic search failed: {str(e)}")
            raise Exception(f"Topic search failed: {str(e)}")

    def _build_comprehensive_filter(
        self,
        tags: List[str] = None,
        people_mentioned: List[str] = None,
        topic_category: str = None,
        temporal_filter: str = None,
    ) -> Optional[Filter]:
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

    def _format_search_results(self, search_points: List) -> List[Dict[str, Any]]:
        """
        Format search results into consistent structure.

        Args:
            search_points: Raw search results from Qdrant

        Returns:
            Formatted search results
        """
        formatted_results = []

        for point in search_points:
            if (
                not hasattr(point, "payload")
                or MetadataConstants.MEMORY_FIELD not in point.payload
            ):
                continue

            result = {
                "id": point.id,
                "score": getattr(point, "score", None),
                "memory": point.payload[MetadataConstants.MEMORY_FIELD],
                "timestamp": point.payload.get(MetadataConstants.TIMESTAMP_FIELD),
                "tags": point.payload.get(MetadataConstants.TAGS_FIELD, []),
                "people_mentioned": point.payload.get(
                    MetadataConstants.PEOPLE_FIELD, []
                ),
                "topic_category": point.payload.get(MetadataConstants.TOPIC_FIELD),
                "temporal_data": point.payload.get(
                    MetadataConstants.TEMPORAL_FIELD, {}
                ),
            }

            formatted_results.append(result)

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
