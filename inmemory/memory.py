"""
Main Memory SDK class for InMemory.

This module provides the primary interface for local InMemory functionality,
with a zero-setup API for direct usage without authentication.

This follows the mem0 pattern: Memory (local) vs Inmemory (managed).
"""

import logging
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import InMemoryConfig
from .embeddings import get_embedding_provider
from .vector_stores import get_vector_store_provider

logger = logging.getLogger(__name__)


class Memory:
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
        >>> memory = Memory(
        ...     embedding={"provider": "ollama", "model": "nomic-embed-text"},
        ...     db={"provider": "chroma", "path": "/tmp/my_memories"}
        ... )
    """

    def __init__(
        self,
        config: InMemoryConfig | None = None,
        embedding: dict[str, Any] | None = None,
        db: dict[str, Any] | None = None,
    ):
        """
        Initialize Memory with zero-setup defaults or custom configuration.

        Args:
            config: Optional InMemoryConfig instance for full configuration
            embedding: Optional embedding configuration. Defaults to embedded mode.
            db: Optional database configuration. Defaults to embedded ChromaDB.

        Examples:
            Zero setup:
            >>> memory = Memory()  # Uses embedded ChromaDB + local embeddings

            With config:
            >>> config = InMemoryConfig(vector_store="qdrant", embedding="ollama")
            >>> memory = Memory(config=config)

            Custom providers (legacy):
            >>> memory = Memory(
            ...     embedding={"provider": "ollama", "model": "nomic-embed-text"},
            ...     db={"provider": "qdrant", "host": "localhost", "port": 6333}
            ... )
        """
        # Load configuration (priority: config param > legacy params > defaults)
        if config:
            self.config = config
        else:
            # Create config from legacy parameters or defaults
            self.config = InMemoryConfig()
            if embedding:
                self.config.embedding = embedding
            if db:
                self.config.vector_store = db

        # Set up zero-setup defaults if no config provided
        if not embedding and not db and not config:
            # Zero setup mode - use ChromaDB embedded
            embedding_provider = "chroma"
            vector_store_provider = "chroma"
            collection_name = "inmemory_memories"
        else:
            # Use configured providers - handle both dict and Pydantic model
            if isinstance(self.config.embedding, dict):
                embedding_provider = self.config.embedding.get("provider", "ollama")
            else:
                embedding_provider = getattr(
                    self.config.embedding, "provider", "ollama"
                )

            if isinstance(self.config.vector_store, dict):
                vector_store_provider = self.config.vector_store.get(
                    "provider", "qdrant"
                )
                # Use collection_name from config if provided
                collection_name = self.config.vector_store.get(
                    "collection_name", "inmemory_memories"
                )
            else:
                vector_store_provider = getattr(
                    self.config.vector_store, "provider", "qdrant"
                )
                collection_name = getattr(
                    self.config.vector_store, "collection_name", "inmemory_memories"
                )

        # Store config for reference - convert to dict for backward compatibility
        if isinstance(self.config.embedding, dict):
            self.embedding_config = self.config.embedding
        elif hasattr(self.config.embedding, "model_dump"):
            self.embedding_config = self.config.embedding.model_dump()
        else:
            self.embedding_config = self.config.embedding.__dict__

        if isinstance(self.config.vector_store, dict):
            self.db_config = self.config.vector_store
        elif hasattr(self.config.vector_store, "model_dump"):
            self.db_config = self.config.vector_store.model_dump()
        else:
            self.db_config = self.config.vector_store.__dict__

        # Initialize using factory pattern (like mem0) - NO FALLBACKS
        # Initialize embedding provider first
        self.embedding_provider = get_embedding_provider(
            embedding_provider, self.config
        )

        # Get actual embedding dimensions from provider
        if hasattr(self.embedding_provider, "embedding_dims"):
            embedding_dims = self.embedding_provider.embedding_dims
        elif hasattr(self.embedding_provider, "model_dims"):
            embedding_dims = self.embedding_provider.model_dims
        else:
            # Test with a sample text to get dimensions
            try:
                test_embedding = self.embedding_provider.embed("test")
                embedding_dims = len(test_embedding)
            except Exception:
                embedding_dims = 768  # Default for nomic-embed-text

        logger.info(f"Using embedding dimensions: {embedding_dims}")

        # Initialize vector store provider with correct dimensions
        self.vector_store = get_vector_store_provider(
            provider=vector_store_provider,
            collection_name=collection_name,
            embedding_model_dims=embedding_dims,
            config=self.config,
        )

        logger.info(
            f"Memory SDK initialized: {embedding_provider} + {vector_store_provider}"
        )
        logger.info("Memory SDK initialized successfully")

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

            logger.info(f"Memory added via factory providers: {memory_content[:50]}...")
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
        query: str,
        limit: int = 10,
        tags: list[str] | None = None,
        people_mentioned: list[str] | None = None,
        topic_category: str | None = None,
        temporal_filter: str | None = None,
        threshold: float | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
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

        Examples:
            >>> memory = Memory()
            >>> results = memory.search("pizza")
            >>> results = memory.search("meetings", limit=5)
        """
        try:
            # Generate embedding for query
            query_embedding = self.embedding_provider.embed(query)

            # Build filters for vector store
            filters = {}
            if topic_category:
                filters["topic_category"] = topic_category
            if tags:
                filters["tags"] = tags
            if people_mentioned:
                filters["people_mentioned"] = people_mentioned

            # Search using vector store provider (match Qdrant API)
            results = self.vector_store.search(
                query=query, vectors=query_embedding, limit=limit, filters=filters
            )

            # Format Qdrant results to match expected structure
            formatted_results = []
            if results:
                for point in results:
                    result = {
                        "id": str(point.id),
                        "content": point.payload.get("data", ""),
                        "score": point.score,
                        "metadata": point.payload,
                    }

                    # Apply threshold filtering if specified
                    if threshold is None or result["score"] >= threshold:
                        formatted_results.append(result)

            logger.info(
                f"Search completed via factory providers: {len(formatted_results)} results"
            )
            return {"results": formatted_results}

        except Exception as e:
            logger.error(f"Search failed: {e}")
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
            # Get all memories from vector store provider - NO FALLBACKS
            results = self.vector_store.get_all(limit=limit, offset=offset)

            logger.info(f"Retrieved {len(results)} memories via factory providers")
            return {"results": results}

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
            # Delete using vector store provider - NO FALLBACKS
            success = self.vector_store.delete(memory_id)

            if success:
                logger.info(f"Memory {memory_id} deleted via factory providers")
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

            # Delete all using vector store provider - NO FALLBACKS
            success = self.vector_store.delete_all()

            if success:
                logger.info(f"Deleted {memory_count} memories via factory providers")
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
            # Get count from vector store provider - NO FALLBACKS
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
            # Test vector store connectivity - NO FALLBACKS
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

            logger.info("Health check passed via factory providers")

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

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()

    def __repr__(self) -> str:
        """String representation of Memory instance."""
        return f"Memory(embedding={self.embedding_config['provider']}, db={self.db_config['provider']})"


class AsyncMemory:
    """
    Async version of the local Memory class for direct usage without authentication.

    This class provides the same zero-setup functionality as Memory but with
    async/await support for non-blocking operations.

    Examples:
        Async zero-setup usage:
        >>> async with AsyncMemory() as memory:
        ...     await memory.add("I love pizza")
        ...     results = await memory.search("pizza")
    """

    def __init__(
        self,
        embedding: dict[str, Any] | None = None,
        db: dict[str, Any] | None = None,
    ):
        """
        Initialize AsyncMemory with zero-setup defaults or custom configuration.

        Args:
            embedding: Optional embedding configuration. Defaults to embedded mode.
            db: Optional database configuration. Defaults to embedded ChromaDB.
        """
        # Create inmemory directory similar to mem0's approach
        self.inmemory_dir = Path(tempfile.gettempdir()) / "inmemory"
        self.inmemory_dir.mkdir(parents=True, exist_ok=True)

        # Set up zero-setup defaults with embedded storage
        self.embedding_config = embedding or {
            "provider": "chroma",  # ChromaDB has built-in embeddings
            "model": "all-MiniLM-L6-v2",  # Default sentence-transformers model
        }

        self.db_config = db or {
            "provider": "chroma",
            "path": str(self.inmemory_dir / "vector_store"),
        }

        # Initialize ChromaDB with embedded embeddings (zero-setup)
        try:
            import chromadb

            # Create embedded ChromaDB client
            self.chroma_client = chromadb.PersistentClient(
                path=self.db_config.get("path", str(self.inmemory_dir / "chroma_db"))
            )

            # Get or create collection
            collection_name = "inmemory_memories"
            try:
                self.collection = self.chroma_client.get_collection(collection_name)
            except Exception:
                # Collection doesn't exist, create it
                self.collection = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={"description": "InMemory local storage"},
                )

            logger.info("ChromaDB initialized successfully (embedded mode)")

        except ImportError:
            logger.error("ChromaDB not installed. Install with: pip install chromadb")
            raise ValueError(
                "ChromaDB required for local Memory. Install with: pip install chromadb"
            ) from None
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise ValueError(f"Failed to initialize ChromaDB: {e}") from e

        logger.info("AsyncMemory SDK initialized successfully (zero-setup mode)")

    async def add(
        self,
        memory_content: str,
        tags: str | None = None,
        people_mentioned: str | None = None,
        topic_category: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Async add a new memory to storage.

        Args:
            memory_content: The memory text to store
            tags: Optional comma-separated tags
            people_mentioned: Optional comma-separated people names
            topic_category: Optional topic category
            metadata: Optional additional metadata

        Returns:
            Dict: Result information including memory_id and status
        """
        try:
            # Generate unique ID
            memory_id = str(uuid.uuid4())

            # Prepare metadata for ChromaDB
            chroma_metadata = {
                "tags": tags or "",
                "people_mentioned": people_mentioned or "",
                "topic_category": topic_category or "",
                "created_at": datetime.now().isoformat(),
            }

            # Add custom metadata fields if provided
            if metadata:
                for key, value in metadata.items():
                    # ChromaDB metadata values must be strings, ints, floats, or bools
                    if isinstance(value, str | int | float | bool) or value is None:
                        chroma_metadata[f"custom_{key}"] = value

            # Add to ChromaDB collection (uses built-in embeddings)
            # Note: ChromaDB operations are sync, we're just providing async interface
            self.collection.add(
                documents=[memory_content], metadatas=[chroma_metadata], ids=[memory_id]
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

    async def search(
        self,
        query: str,
        limit: int = 10,
        tags: list[str] | None = None,
        people_mentioned: list[str] | None = None,
        topic_category: str | None = None,
        temporal_filter: str | None = None,
        threshold: float | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Async search memories with semantic similarity.

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
        try:
            # Build ChromaDB where filters
            where_filters = {}
            if topic_category:
                where_filters["topic_category"] = topic_category

            # Search in ChromaDB collection
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_filters if where_filters else None,
            )

            # Format results to match expected structure
            formatted_results = []
            if results and results.get("ids") and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    result = {
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "score": 1.0
                        - results["distances"][0][
                            i
                        ],  # Convert distance to similarity score
                        "metadata": results["metadatas"][0][i]
                        if results.get("metadatas")
                        else {},
                    }

                    # Apply threshold filtering if specified
                    if threshold is None or result["score"] >= threshold:
                        formatted_results.append(result)

            logger.info(f"Search completed: {len(formatted_results)} results")
            return {"results": formatted_results}

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"results": []}

    async def get_all(
        self, limit: int = 100, offset: int = 0
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Async get all memories.

        Args:
            limit: Maximum number of memories to return
            offset: Number of memories to skip

        Returns:
            Dict: All memories with "results" key
        """
        try:
            # Get all memories from ChromaDB collection
            results = self.collection.get(limit=limit, offset=offset)

            # Format results
            formatted_results = []
            if results and results.get("ids"):
                for i in range(len(results["ids"])):
                    result = {
                        "id": results["ids"][i],
                        "content": results["documents"][i]
                        if results.get("documents")
                        else "",
                        "metadata": results["metadatas"][i]
                        if results.get("metadatas")
                        else {},
                    }
                    formatted_results.append(result)

            logger.info(f"Retrieved {len(formatted_results)} memories")
            return {"results": formatted_results}

        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return {"results": []}

    async def delete(self, memory_id: str) -> dict[str, Any]:
        """
        Async delete a specific memory.

        Args:
            memory_id: Memory identifier to delete

        Returns:
            Dict: Deletion result
        """
        try:
            # Delete from ChromaDB collection
            self.collection.delete(ids=[memory_id])

            logger.info(f"Memory {memory_id} deleted")
            return {"success": True, "message": "Memory deleted successfully"}

        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            return {"success": False, "error": str(e)}

    async def delete_all(self) -> dict[str, Any]:
        """
        Async delete all memories.

        Returns:
            Dict: Deletion result with count of deleted memories
        """
        try:
            # Get current count before deletion
            current_memories = await self.get_all(limit=10000)
            memory_count = len(current_memories.get("results", []))

            # Delete the collection and recreate it
            collection_name = "inmemory_memories"
            self.chroma_client.delete_collection(collection_name)

            # Recreate the collection
            self.collection = self.chroma_client.create_collection(
                name=collection_name, metadata={"description": "InMemory local storage"}
            )

            logger.info(f"Deleted {memory_count} memories")
            return {
                "success": True,
                "deleted_count": memory_count,
                "message": f"Deleted {memory_count} memories",
            }

        except Exception as e:
            logger.error(f"Failed to delete all memories: {e}")
            return {"success": False, "error": str(e)}

    async def get_stats(self) -> dict[str, Any]:
        """
        Async get statistics for memories.

        Returns:
            Dict: Statistics including memory count, provider info, etc.
        """
        try:
            # Get memory count
            all_memories = await self.get_all(limit=1)  # Just get count

            return {
                "embedding_provider": self.embedding_config["provider"],
                "embedding_model": self.embedding_config.get("model", "unknown"),
                "vector_store": self.db_config["provider"],
                "memory_count": len(all_memories.get("results", [])),
                "status": "healthy",
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    async def health_check(self) -> dict[str, Any]:
        """
        Async perform health check on all components.

        Returns:
            Dict: Health check results
        """
        health = {
            "status": "healthy",
            "storage_type": "embedded_chromadb",
            "embedding_model": self.embedding_config.get("model", "built-in"),
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Test ChromaDB connectivity
            count = self.collection.count()
            health["memory_count"] = count
            health["collection_name"] = "inmemory_memories"
            health["storage_path"] = self.db_config.get("path")

            logger.info("Health check passed")

        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
            logger.error(f"Health check failed: {e}")

        return health

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.close()

    async def close(self) -> None:
        """
        Close connections and cleanup resources.

        Should be called when AsyncMemory instance is no longer needed.
        """
        try:
            # ChromaDB handles cleanup automatically
            logger.info("AsyncMemory SDK connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

    def __repr__(self) -> str:
        """String representation of AsyncMemory instance."""
        return f"AsyncMemory(embedding={self.embedding_config['provider']}, db={self.db_config['provider']})"
