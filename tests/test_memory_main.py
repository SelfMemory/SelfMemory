"""
Unit tests for the main Memory class.

Each test is explained with:
1. What we're testing
2. What mocks we use
3. What the expected behavior is
4. How the test validates the behavior
"""

from unittest.mock import Mock, patch

from inmemory.configs.base import InMemoryConfig
from inmemory.memory.main import Memory


class TestMemoryInitialization:
    """Test Memory class initialization with different configurations."""

    def test_memory_init_with_default_config(
        self, mock_ollama_embedding, mock_qdrant_vector_store
    ):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Memory class initialization with default config

        Mocks used:
        - mock_ollama_embedding: Returns fake embeddings instead of calling Ollama API
        - mock_qdrant_vector_store: Returns fake responses instead of connecting to Qdrant

        Expected behavior:
        - Memory should initialize successfully with default Ollama + Qdrant config
        - Factories should be called to create embedding and vector store providers
        - Memory instance should have the correct provider references

        How the test works:
        1. Patch the factory methods to return our mocks
        2. Create Memory instance (should use default config)
        3. Verify factories were called with correct parameters
        4. Verify Memory instance has correct attributes
        """
        with (
            patch(
                "inmemory.utils.factory.EmbeddingFactory.create"
            ) as mock_embedding_factory,
            patch(
                "inmemory.utils.factory.VectorStoreFactory.create"
            ) as mock_vector_factory,
        ):
            # Configure what our mocks should return
            mock_embedding_factory.return_value = mock_ollama_embedding
            mock_vector_factory.return_value = mock_qdrant_vector_store

            # Create Memory instance - this should trigger factory calls
            memory = Memory()

            # Verify the factories were called with default config
            mock_embedding_factory.assert_called_once()
            mock_vector_factory.assert_called_once()

            # Verify Memory has correct provider references
            assert memory.embedding_provider == mock_ollama_embedding
            assert memory.vector_store == mock_qdrant_vector_store

            # Verify config defaults
            assert memory.config.embedding.provider == "ollama"
            assert memory.config.vector_store.provider == "qdrant"

    def test_memory_init_with_custom_config(
        self, mock_ollama_embedding, mock_qdrant_vector_store
    ):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Memory initialization with custom configuration

        Mocks used:
        - Same mocks as above, but we pass custom config

        Expected behavior:
        - Memory should accept custom InMemoryConfig object
        - Should use the custom config settings instead of defaults

        How the test works:
        1. Create custom config with specific settings
        2. Pass it to Memory constructor
        3. Verify Memory uses the custom config
        """
        with (
            patch(
                "inmemory.utils.factory.EmbeddingFactory.create"
            ) as mock_embedding_factory,
            patch(
                "inmemory.utils.factory.VectorStoreFactory.create"
            ) as mock_vector_factory,
        ):
            mock_embedding_factory.return_value = mock_ollama_embedding
            mock_vector_factory.return_value = mock_qdrant_vector_store

            # Create custom config
            custom_config = InMemoryConfig()
            custom_config.embedding.provider = "ollama"
            custom_config.vector_store.provider = "qdrant"

            # Create Memory with custom config
            memory = Memory(config=custom_config)

            # Verify Memory uses our custom config
            assert memory.config == custom_config
            assert memory.config.embedding.provider == "ollama"


class TestMemoryAdd:
    """Test the Memory.add() method for storing memories."""

    def test_add_memory_success(self, mock_memory_instance, mock_embedding_response):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Successfully adding a memory to storage

        Mocks used:
        - mock_memory_instance: Fully mocked Memory with fake embedding/vector store
        - mock_embedding_response: Fake embedding vector [0.1, 0.2, 0.3...]

        Expected behavior:
        1. Memory.add() should call embedding provider to convert text to vector
        2. Should call vector store to insert the vector with metadata
        3. Should return success response with memory_id

        How the test works:
        1. Configure embedding mock to return fake vector
        2. Configure vector store mock to return success
        3. Call memory.add() with test data
        4. Verify embedding provider was called with correct text
        5. Verify vector store was called with correct vector and metadata
        6. Verify response format is correct
        """
        # Configure what our mocks should return
        mock_memory_instance.embedding_provider.embed.return_value = (
            mock_embedding_response
        )
        mock_memory_instance.vector_store.insert.return_value = True

        # Test data
        test_content = "I love pizza and Italian food"
        test_tags = "food,personal"

        # Call the method we're testing
        result = mock_memory_instance.add(
            memory_content=test_content,
            tags=test_tags,
            people_mentioned="John",
            topic_category="food",
        )

        # Verify embedding provider was called correctly
        mock_memory_instance.embedding_provider.embed.assert_called_once_with(
            test_content
        )

        # Verify vector store insert was called
        mock_memory_instance.vector_store.insert.assert_called_once()

        # Get the actual call arguments to verify them
        call_args = mock_memory_instance.vector_store.insert.call_args
        vectors, payloads, ids = (
            call_args[1]["vectors"],
            call_args[1]["payloads"],
            call_args[1]["ids"],
        )

        # Verify the vector is our mock embedding
        assert vectors == [mock_embedding_response]

        # Verify payload contains our data
        payload = payloads[0]
        assert payload["data"] == test_content
        assert payload["tags"] == test_tags
        assert payload["people_mentioned"] == "John"
        assert payload["topic_category"] == "food"
        assert "created_at" in payload

        # Verify response format
        assert result["success"] is True
        assert "memory_id" in result
        assert result["message"] == "Memory added successfully"

    def test_add_memory_with_metadata(
        self, mock_memory_instance, mock_embedding_response
    ):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Adding memory with custom metadata

        Expected behavior:
        - Custom metadata should be included in the stored payload
        - Should merge with default fields (data, tags, etc.)
        """
        mock_memory_instance.embedding_provider.embed.return_value = (
            mock_embedding_response
        )
        mock_memory_instance.vector_store.insert.return_value = True

        # Test with custom metadata
        custom_metadata = {"source": "test", "confidence": 0.95, "user_id": "test_user"}

        result = mock_memory_instance.add(
            memory_content="Test memory", metadata=custom_metadata
        )

        # Verify custom metadata was included
        call_args = mock_memory_instance.vector_store.insert.call_args
        payload = call_args[1]["payloads"][0]

        assert payload["source"] == "test"
        assert payload["confidence"] == 0.95
        assert payload["user_id"] == "test_user"
        assert result["success"] is True

    def test_add_memory_embedding_failure(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Error handling when embedding generation fails

        Mocks used:
        - Configure embedding provider to raise an exception

        Expected behavior:
        - Should catch the exception and return error response
        - Should not call vector store if embedding fails
        """
        # Configure embedding to fail
        mock_memory_instance.embedding_provider.embed.side_effect = Exception(
            "Embedding service unavailable"
        )

        result = mock_memory_instance.add(memory_content="Test memory")

        # Verify error handling
        assert result["success"] is False
        assert "Embedding service unavailable" in result["error"]

        # Verify vector store was not called
        mock_memory_instance.vector_store.insert.assert_not_called()


class TestMemorySearch:
    """Test the Memory.search() method for retrieving memories."""

    def test_search_with_query(
        self, mock_memory_instance, mock_embedding_response, create_mock_point
    ):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Searching memories with a text query

        Mocks used:
        - mock_embedding_response: Fake query embedding
        - create_mock_point: Factory to create fake search results

        Expected behavior:
        1. Should convert query text to embedding
        2. Should search vector store with the embedding
        3. Should return formatted results

        How the test works:
        1. Configure embedding mock to return fake vector for query
        2. Configure vector store to return fake search results
        3. Call memory.search() with test query
        4. Verify embedding was generated for query
        5. Verify vector store search was called correctly
        6. Verify results are formatted correctly
        """
        # Configure mocks
        mock_memory_instance.embedding_provider.embed.return_value = (
            mock_embedding_response
        )

        # Create fake search results
        mock_results = [
            create_mock_point(
                id="test-1",
                content="I love pizza",
                score=0.95,
                tags="food",
                people_mentioned="John",
            )
        ]
        mock_memory_instance.vector_store.search.return_value = mock_results

        # Test search
        query = "pizza food"
        result = mock_memory_instance.search(query=query, limit=5)

        # Verify embedding was generated for query
        mock_memory_instance.embedding_provider.embed.assert_called_once_with(query)

        # Verify vector store search was called
        mock_memory_instance.vector_store.search.assert_called_once()

        # Verify search parameters
        call_args = mock_memory_instance.vector_store.search.call_args
        assert call_args[1]["query"] == query
        assert call_args[1]["vectors"] == mock_embedding_response
        assert call_args[1]["limit"] == 5

        # Verify result format
        assert "results" in result
        assert len(result["results"]) == 1

        search_result = result["results"][0]
        assert search_result["id"] == "test-1"
        assert search_result["content"] == "I love pizza"
        assert search_result["score"] == 0.95

    def test_search_empty_query_returns_all(
        self, mock_memory_instance, create_mock_point
    ):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Empty query should return all memories

        Expected behavior:
        - Empty query should call vector_store.list() instead of search()
        - Should not generate embedding for empty query
        """
        # Configure mock for list operation
        mock_results = [
            create_mock_point(id="test-1", content="Memory 1"),
            create_mock_point(id="test-2", content="Memory 2"),
        ]
        mock_memory_instance.vector_store.list.return_value = (mock_results, None)

        # Test empty query
        result = mock_memory_instance.search(query="", limit=10)

        # Verify list was called instead of search
        mock_memory_instance.vector_store.list.assert_called_once()
        mock_memory_instance.vector_store.search.assert_not_called()

        # Verify embedding was not generated
        mock_memory_instance.embedding_provider.embed.assert_not_called()

        # Verify results
        assert len(result["results"]) == 2


class TestMemoryGetAll:
    """Test the Memory.get_all() method for retrieving all memories."""

    def test_get_all_memories(self, mock_memory_instance, create_mock_point):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Getting all memories from storage

        Mocks used:
        - mock_memory_instance: Memory with mocked vector store
        - create_mock_point: Factory for creating fake memory points

        Expected behavior:
        - Should call vector_store.list() to get all memories
        - Should format results consistently with search results
        - Should handle empty results gracefully

        How the test works:
        1. Configure vector store to return fake memories
        2. Call memory.get_all()
        3. Verify vector store list was called
        4. Verify results are formatted correctly
        """
        # Create fake memories
        mock_results = [
            create_mock_point(id="mem-1", content="Memory 1", tags="tag1"),
            create_mock_point(id="mem-2", content="Memory 2", tags="tag2"),
        ]
        mock_memory_instance.vector_store.list.return_value = (mock_results, None)

        # Test get_all
        result = mock_memory_instance.get_all(limit=50)

        # Verify vector store list was called
        mock_memory_instance.vector_store.list.assert_called_once_with(
            filters=None, limit=50
        )

        # Verify results format
        assert "results" in result
        assert len(result["results"]) == 2

        # Verify first result
        first_result = result["results"][0]
        assert first_result["id"] == "mem-1"
        assert first_result["content"] == "Memory 1"
        assert "metadata" in first_result

    def test_get_all_empty_results(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: get_all() with no memories in storage

        Expected behavior:
        - Should return empty results list
        - Should not crash or throw errors
        """
        # Configure empty results
        mock_memory_instance.vector_store.list.return_value = ([], None)

        result = mock_memory_instance.get_all()

        # Verify empty results
        assert result["results"] == []


class TestMemoryDelete:
    """Test the Memory.delete() method for removing memories."""

    def test_delete_memory_success(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Successfully deleting a memory by ID

        Mocks used:
        - Configure vector store delete to return True (success)

        Expected behavior:
        - Should call vector_store.delete() with memory ID
        - Should return success response

        How the test works:
        1. Configure vector store delete to succeed
        2. Call memory.delete() with test ID
        3. Verify vector store delete was called correctly
        4. Verify success response format
        """
        # Configure successful deletion
        mock_memory_instance.vector_store.delete.return_value = True

        test_id = "test-memory-123"
        result = mock_memory_instance.delete(test_id)

        # Verify vector store delete was called
        mock_memory_instance.vector_store.delete.assert_called_once_with(test_id)

        # Verify success response
        assert result["success"] is True
        assert result["message"] == "Memory deleted successfully"

    def test_delete_memory_not_found(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Deleting a memory that doesn't exist

        Expected behavior:
        - Should return failure response when memory not found
        - Should handle the case gracefully
        """
        # Configure deletion failure (memory not found)
        mock_memory_instance.vector_store.delete.return_value = False

        result = mock_memory_instance.delete("nonexistent-id")

        # Verify failure response
        assert result["success"] is False
        assert "Memory not found or deletion failed" in result["error"]

    def test_delete_memory_exception(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Error handling when delete operation fails

        Expected behavior:
        - Should catch exceptions and return error response
        - Should not crash the application
        """
        # Configure delete to raise exception
        mock_memory_instance.vector_store.delete.side_effect = Exception(
            "Database connection failed"
        )

        result = mock_memory_instance.delete("test-id")

        # Verify error handling
        assert result["success"] is False
        assert "Database connection failed" in result["error"]


class TestMemoryDeleteAll:
    """Test the Memory.delete_all() method for clearing all memories."""

    def test_delete_all_success(self, mock_memory_instance, create_mock_point):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Successfully deleting all memories

        FIXED APPROACH:
        - Instead of mocking get_all method, mock the underlying vector store operations
        - The delete_all method calls get_all internally, so we mock vector_store.list

        Expected behavior:
        1. Should first get count of existing memories via get_all()
        2. Should call vector_store.delete_all()
        3. Should return count of deleted memories
        """
        # Configure vector store to return fake memories for counting
        mock_memories = [
            create_mock_point(id="mem-1", content="Memory 1"),
            create_mock_point(id="mem-2", content="Memory 2"),
        ]
        # Mock the underlying list operation that get_all uses
        mock_memory_instance.vector_store.list.return_value = (mock_memories, None)
        mock_memory_instance.vector_store.delete_all.return_value = True

        result = mock_memory_instance.delete_all()

        # Verify delete_all was called
        mock_memory_instance.vector_store.delete_all.assert_called_once()

        # Verify success response with count
        assert result["success"] is True
        assert result["deleted_count"] == 2
        assert "Deleted 2 memories" in result["message"]

    def test_delete_all_failure(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: delete_all() operation failure

        FIXED APPROACH:
        - Mock vector store operations instead of Memory methods
        """
        # Configure empty results for counting
        mock_memory_instance.vector_store.list.return_value = ([], None)
        mock_memory_instance.vector_store.delete_all.return_value = False

        result = mock_memory_instance.delete_all()

        assert result["success"] is False
        assert "Delete all operation failed" in result["error"]


class TestMemoryUtilityMethods:
    """Test utility methods like get_stats() and health_check()."""

    def test_get_stats(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Getting statistics about the memory system

        Expected behavior:
        - Should return provider information
        - Should return memory count
        - Should return system status

        How the test works:
        1. Configure vector store count method
        2. Call memory.get_stats()
        3. Verify stats include all expected fields
        """
        # Configure memory count
        mock_memory_instance.vector_store.count.return_value = 42

        result = mock_memory_instance.get_stats()

        # Verify stats content
        assert result["embedding_provider"] == "ollama"
        assert result["vector_store"] == "qdrant"
        assert result["memory_count"] == 42
        assert result["status"] == "healthy"

    def test_health_check_success(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: System health check when all components are healthy

        Expected behavior:
        - Should check vector store health
        - Should check embedding provider health
        - Should return overall healthy status
        """
        # Configure healthy components
        mock_memory_instance.vector_store.count.return_value = 10

        result = mock_memory_instance.health_check()

        # Verify health check results
        assert result["status"] == "healthy"
        assert result["storage_type"] == "qdrant"
        assert result["embedding_provider"] == "ollama"
        assert "timestamp" in result

    def test_health_check_failure(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Health check when components fail

        FIXED APPROACH:
        - The health_check method tries multiple approaches before failing
        - It first checks for health_check method, then count method, then falls back
        - We need to make ALL approaches fail to trigger the exception handling

        Expected behavior:
        - Should catch exceptions from component health checks
        - Should return unhealthy status with error details
        """
        # Configure ALL health check approaches to fail
        # Remove health_check method so it tries count()
        if hasattr(mock_memory_instance.vector_store, "health_check"):
            delattr(mock_memory_instance.vector_store, "health_check")

        # Make count() method fail
        mock_memory_instance.vector_store.count.side_effect = Exception(
            "Vector store unavailable"
        )

        # Also make embedding provider fail if it has health_check
        if hasattr(mock_memory_instance.embedding_provider, "health_check"):
            mock_memory_instance.embedding_provider.health_check.side_effect = (
                Exception("Embedding provider unavailable")
            )

        result = mock_memory_instance.health_check()

        # Verify failure handling
        assert result["status"] == "unhealthy"
        assert "Vector store unavailable" in result["error"]

    def test_memory_close(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Proper cleanup when closing Memory instance

        Expected behavior:
        - Should call close() on vector store if available
        - Should call close() on embedding provider if available
        - Should handle cases where close() methods don't exist
        """
        # Add close methods to mocks
        mock_memory_instance.vector_store.close = Mock()
        mock_memory_instance.embedding_provider.close = Mock()

        # Test close
        mock_memory_instance.close()

        # Verify cleanup was called
        mock_memory_instance.vector_store.close.assert_called_once()
        mock_memory_instance.embedding_provider.close.assert_called_once()

    def test_memory_repr(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: String representation of Memory instance

        Expected behavior:
        - Should return readable string with provider information
        """
        result = str(mock_memory_instance)

        # Verify string representation
        assert "Memory(" in result
        assert "embedding=ollama" in result
        assert "db=qdrant" in result


# Summary of what we've tested:
# =============================
# 1. Memory initialization (default and custom configs)
# 2. Adding memories (success, with metadata, error handling)
# 3. Searching memories (with query, empty query)
# 4. Getting all memories (success, empty results)
# 5. Deleting memories (success, not found, exceptions)
# 6. Deleting all memories (success, failure)
# 7. Utility methods (stats, health check, close, repr)
#
# This covers all major functionality of the Memory class with comprehensive
# error handling and edge case testing.
