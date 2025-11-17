"""
SelfMemory Client - Managed solution for SelfMemory.

This module provides the client interface for the managed SelfMemory service,
similar to how  provides MemoryClient for their hosted solution.
"""

import logging
from typing import Any

import httpx

from ..common.constants import APIConstants

logger = logging.getLogger(__name__)


class SelfMemoryClient:
    """Client for interacting with the managed SelfMemory API.

    This class provides methods to create, retrieve, search, and delete
    memories using the hosted SelfMemory service.

    Attributes:
        api_key (str): The API key for authenticating with the SelfMemory API.
        host (str): The base URL for the SelfMemory API.
        client (httpx.Client): The HTTP client used for making API requests.
    """

    def __init__(
        self,
        api_key: str | None = None,
        oauth_token: str | None = None,
        host: str | None = None,
        client: httpx.Client | None = None,
    ):
        """Initialize the SelfMemory client.

        Args:
            api_key: Legacy API key for authentication (deprecated, use oauth_token)
            oauth_token: OAuth 2.1 token for authentication
            host: The base URL for the SelfMemory API (required)
            client: A custom httpx.Client instance (optional)

        Raises:
            ValueError: If no authentication token provided or host not specified
        """
        # Get authentication token (prefer OAuth token over legacy API key)
        auth_token = oauth_token or api_key

        if not auth_token:
            raise ValueError(
                "Authentication required. Provide either oauth_token or api_key parameter."
            )

        if not host:
            raise ValueError(
                "Host is required. Provide the host parameter with the API base URL."
            )

        self.host = host

        if client is not None:
            self.client = client
            self.client.base_url = httpx.URL(self.host)
            self.client.headers.update(
                {
                    "Authorization": f"Bearer {auth_token}",
                    "Content-Type": "application/json",
                }
            )
        else:
            self.client = httpx.Client(
                base_url=self.host,
                headers={
                    "Authorization": f"Bearer {auth_token}",
                    "Content-Type": "application/json",
                },
                timeout=APIConstants.DEFAULT_TIMEOUT,
            )

        logger.info(f"SelfMemory client initialized with host: {self.host}")

    def add(
        self,
        memory_content: str,
        tags: str | None = None,
        people_mentioned: str | None = None,
        topic_category: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add a new memory to the managed service.

        Args:
            memory_content: The memory text to store
            tags: Optional comma-separated tags
            people_mentioned: Optional comma-separated people names
            topic_category: Optional topic category
            metadata: Optional additional metadata

        Returns:
            Dict: Result information including memory_id and status

        Examples:
            >>> selfmemory = SelfMemory()
            >>> selfmemory.add("Meeting notes from project discussion",
            ...           tags="work,meeting",
            ...           people_mentioned="Sarah,Mike")
        """
        try:
            payload = {
                "memory_content": memory_content,
                "tags": tags or "",
                "people_mentioned": people_mentioned or "",
                "topic_category": topic_category or "",
                "metadata": metadata or {},
            }

            response = self.client.post("/api/memories", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Memory added: {memory_content[:50]}...")
            return result

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            logger.error(f"Failed to add memory: {error_message}")
            return {
                "success": False,
                "error": "An internal error occurred while adding a new memory.",
            }
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return {
                "success": False,
                "error": "An internal error occurred while adding a new memory.",
            }

    def search(
        self,
        query: str,
        limit: int = 10,
        tags: list[str] | None = None,
        people_mentioned: list[str] | None = None,
        topic_category: str | None = None,
        temporal_filter: str | None = None,
        threshold: float | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search memories with various filters.

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

        Examples:
            >>> selfmemory = SelfMemory()
            >>> results = selfmemory.search("pizza")
            >>> results = selfmemory.search("meetings", tags=["work"], limit=5)
        """
        try:
            payload = {
                "query": query,
                "limit": limit,
                "tags": ",".join(tags) if tags else "",
                "people_mentioned": ",".join(people_mentioned)
                if people_mentioned
                else "",
                "topic_category": topic_category or "",
                "temporal_filter": temporal_filter or "",
                "threshold": threshold or 0.0,
            }

            response = self.client.post("/api/memories/search", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Search completed: {len(result.get('results', []))} results")
            return result

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            logger.error(f"Search failed: {error_message}")
            return {"results": [], "error": error_message}
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"results": [], "error": str(e)}

    def get_all(
        self, limit: int = 100, offset: int = 0
    ) -> dict[str, list[dict[str, Any]]]:
        """Get all memories.

        Args:
            limit: Maximum number of memories to return
            offset: Number of memories to skip

        Returns:
            Dict: All memories with "results" key

        Examples:
            >>> selfmemory = SelfMemory()
            >>> all_memories = selfmemory.get_all()
            >>> recent_memories = selfmemory.get_all(limit=10)
        """
        try:
            params = {
                "limit": limit,
                "offset": offset,
            }

            response = self.client.get("/api/memories", params=params)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Retrieved {len(result.get('results', []))} memories")
            return result

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            logger.error(f"Failed to get memories: {error_message}")
            return {"results": [], "error": error_message}
        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return {"results": [], "error": str(e)}

    def delete(self, memory_id: str) -> dict[str, Any]:
        """Delete a specific memory.

        Args:
            memory_id: Memory identifier to delete

        Returns:
            Dict: Deletion result
        """
        try:
            response = self.client.delete(f"/api/memories/{memory_id}")
            response.raise_for_status()

            result = response.json()
            logger.info(f"Memory {memory_id} deleted")
            return result

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            logger.error(f"Error deleting memory {memory_id}: {error_message}")
            return {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            return {"success": False, "error": str(e)}

    def delete_all(self) -> dict[str, Any]:
        """Delete all memories.

        Returns:
            Dict: Deletion result with count of deleted memories
        """
        try:
            response = self.client.delete("/api/memories")
            response.raise_for_status()

            result = response.json()
            logger.info("All memories deleted")
            return result

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            logger.error(f"Failed to delete all memories: {error_message}")
            return {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Failed to delete all memories: {e}")
            return {"success": False, "error": str(e)}

    def temporal_search(
        self,
        temporal_query: str,
        semantic_query: str | None = None,
        limit: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search memories using temporal queries.

        Args:
            temporal_query: Temporal query (e.g., "yesterday", "this_week")
            semantic_query: Optional semantic search query
            limit: Maximum number of results

        Returns:
            Dict: Search results
        """
        try:
            payload = {
                "temporal_query": temporal_query,
                "semantic_query": semantic_query,
                "limit": limit,
            }

            response = self.client.post("/v1/memories/temporal-search/", json=payload)
            response.raise_for_status()

            result = response.json()
            return result

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            logger.error(f"Temporal search failed: {error_message}")
            return {"results": [], "error": error_message}
        except Exception as e:
            logger.error(f"Temporal search failed: {e}")
            return {"results": [], "error": str(e)}

    def search_by_tags(
        self,
        tags: str | list[str],
        semantic_query: str | None = None,
        match_all: bool = False,
        limit: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search memories by tags.

        Args:
            tags: Tags to search for (string or list)
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

            payload = {
                "tags": tag_list,
                "semantic_query": semantic_query,
                "match_all": match_all,
                "limit": limit,
            }

            response = self.client.post("/v1/memories/tag-search/", json=payload)
            response.raise_for_status()

            result = response.json()
            return result

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            logger.error(f"Tag search failed: {error_message}")
            return {"results": [], "error": error_message}
        except Exception as e:
            logger.error(f"Tag search failed: {e}")
            return {"results": [], "error": str(e)}

    def search_by_people(
        self,
        people: str | list[str],
        semantic_query: str | None = None,
        limit: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search memories by people mentioned.

        Args:
            people: People to search for (string or list)
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

            payload = {
                "people": people_list,
                "semantic_query": semantic_query,
                "limit": limit,
            }

            response = self.client.post("/v1/memories/people-search/", json=payload)
            response.raise_for_status()

            result = response.json()
            return result

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            logger.error(f"People search failed: {error_message}")
            return {"results": [], "error": error_message}
        except Exception as e:
            logger.error(f"People search failed: {e}")
            return {"results": [], "error": str(e)}

    def get_stats(self) -> dict[str, Any]:
        """Get statistics for memories.

        Returns:
            Dict: Statistics including memory count, usage info, etc.
        """
        try:
            response = self.client.get("/v1/stats")
            response.raise_for_status()

            result = response.json()
            return result

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            logger.error(f"Failed to get stats: {error_message}")
            return {"error": error_message}
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def health_check(self) -> dict[str, Any]:
        """Perform health check on the managed service.

        Returns:
            Dict: Health check results
        """
        try:
            response = self.client.get("/v1/health")
            response.raise_for_status()

            result = response.json()
            return result

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "service": "managed",
            }

    def close(self) -> None:
        """Close the HTTP client connection.

        Should be called when SelfMemory instance is no longer needed.
        """
        try:
            self.client.close()
            logger.info("SelfMemory client connection closed")
        except Exception as e:
            logger.error(f"Error closing client connection: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()

    def __repr__(self) -> str:
        """String representation of SelfMemoryClient instance."""
        return f"SelfMemoryClient(host={self.host})"
