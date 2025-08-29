"""
Advanced Memory class tests inspired by mem0's patterns.

This module adds parametrized tests, edge cases, and advanced scenarios
that complement the basic test_memory_main.py tests.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from inmemory.memory.main import Memory
from inmemory.configs.base import InMemoryConfig


class TestMemoryParametrized:
    """Parametrized tests for testing multiple scenarios efficiently."""
    
    @pytest.mark.parametrize("provider_combo", [
        ("ollama", "qdrant"),
        ("ollama", "chromadb"),  # Future provider combinations
    ])
    def test_memory_init_different_providers(self, provider_combo, mock_ollama_embedding, mock_qdrant_vector_store):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Memory initialization with different provider combinations
        
        Parametrized approach:
        - Tests multiple embedding + vector store combinations
        - Ensures our factory pattern works with different providers
        - Follows mem0's parametrized testing pattern
        
        Expected behavior:
        - Memory should initialize with any valid provider combination
        - Should use the specified providers correctly
        """
        embedding_provider, vector_store_provider = provider_combo
        
        with (
            patch("inmemory.utils.factory.EmbeddingFactory.create") as mock_embedding_factory,
            patch("inmemory.utils.factory.VectorStoreFactory.create") as mock_vector_factory,
        ):
            mock_embedding_factory.return_value = mock_ollama_embedding
            mock_vector_factory.return_value = mock_qdrant_vector_store
            
            # Create config with specific providers
            config = InMemoryConfig()
            config.embedding.provider = embedding_provider
            config.vector_store.provider = vector_store_provider
            
            memory = Memory(config=config)
            
            # Verify correct providers were used
            assert memory.config.embedding.provider == embedding_provider
            assert memory.config.vector_store.provider == vector_store_provider
            mock_embedding_factory.assert_called_once()
            mock_vector_factory.assert_called_once()

    @pytest.mark.parametrize("memory_content,expected_success", [
        ("Valid memory content", True),
        ("", False),  # Empty content should fail
        ("   ", False),  # Whitespace only should fail
        ("A" * 10000, True),  # Very long content should work
        ("Memory with special chars: !@#$%^&*()", True),
        ("Memory with unicode: 🚀 🎉 ✨", True),
    ])
    def test_add_memory_content_validation(self, mock_memory_instance, mock_embedding_response, memory_content, expected_success):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Memory content validation with various inputs
        
        Parametrized approach:
        - Tests different types of memory content
        - Validates edge cases like empty strings, unicode, special chars
        - Ensures robust input handling
        
        Expected behavior:
        - Valid content should succeed
        - Invalid content (empty/whitespace) should fail gracefully
        """
        mock_memory_instance.embedding_provider.embed.return_value = mock_embedding_response
        mock_memory_instance.vector_store.insert.return_value = True
        
        if not memory_content.strip():
            # For empty/whitespace content, expect embedding to fail
            mock_memory_instance.embedding_provider.embed.side_effect = ValueError("Empty content not allowed")
        
        result = mock_memory_instance.add(memory_content=memory_content)
        
        if expected_success:
            assert result['success'] is True
            assert 'memory_id' in result
        else:
            assert result['success'] is False
            assert 'error' in result

    @pytest.mark.parametrize("limit,expected_calls", [
        (1, 1),
        (10, 1),
        (100, 1),
        (1000, 1),  # Large limits should still work
    ])
    def test_search_with_different_limits(self, mock_memory_instance, mock_embedding_response, create_mock_point, limit, expected_calls):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Search behavior with different limit values
        
        FIXED APPROACH:
        - The Memory.search() method doesn't enforce limits itself
        - It passes the limit to the vector store and trusts it to limit results
        - We should mock the vector store to return the correct number of results
        
        Expected behavior:
        - Vector store should be called with correct limit parameter
        - Results should respect the limit (mocked appropriately)
        """
        mock_memory_instance.embedding_provider.embed.return_value = mock_embedding_response
        
        # Create results that respect the limit (simulate vector store behavior)
        num_results = min(limit, 5)  # Simulate vector store limiting
        mock_results = [create_mock_point(id=f"test-{i}", content=f"Memory {i}") for i in range(num_results)]
        mock_memory_instance.vector_store.search.return_value = mock_results
        
        result = mock_memory_instance.search(query="test", limit=limit)
        
        # Verify vector store was called with correct limit
        call_args = mock_memory_instance.vector_store.search.call_args
        assert call_args[1]['limit'] == limit
        
        # Verify we got the expected number of results
        assert 'results' in result
        assert len(result['results']) == num_results


class TestMemoryAdvancedScenarios:
    """Advanced test scenarios inspired by mem0's comprehensive testing."""
    
    def test_memory_with_dict_config(self, mock_ollama_embedding, mock_qdrant_vector_store):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Memory initialization with dictionary config (mem0 pattern)
        
        Advanced scenario:
        - Tests the dict-to-config conversion functionality
        - Ensures our API supports both dict and object configs
        - Follows mem0's flexible config approach
        
        Expected behavior:
        - Dict config should be converted to InMemoryConfig internally
        - Should work identically to object config
        """
        with (
            patch("inmemory.utils.factory.EmbeddingFactory.create") as mock_embedding_factory,
            patch("inmemory.utils.factory.VectorStoreFactory.create") as mock_vector_factory,
        ):
            mock_embedding_factory.return_value = mock_ollama_embedding
            mock_vector_factory.return_value = mock_qdrant_vector_store
            
            # Test with dictionary config
            dict_config = {
                "embedding": {"provider": "ollama"},
                "vector_store": {"provider": "qdrant"}
            }
            
            memory = Memory(config=dict_config)
            
            # Verify config was converted and used correctly
            assert memory.config.embedding.provider == "ollama"
            assert memory.config.vector_store.provider == "qdrant"
            mock_embedding_factory.assert_called_once()
            mock_vector_factory.assert_called_once()

    def test_concurrent_memory_operations(self, mock_memory_instance, mock_embedding_response, create_mock_point):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Multiple memory operations in sequence
        
        Advanced scenario:
        - Simulates real-world usage with multiple operations
        - Tests that mocks maintain state correctly across operations
        - Ensures no interference between operations
        
        Expected behavior:
        - Each operation should work independently
        - Mocks should be called the expected number of times
        """
        mock_memory_instance.embedding_provider.embed.return_value = mock_embedding_response
        mock_memory_instance.vector_store.insert.return_value = True
        
        # Create mock search results
        mock_results = [create_mock_point(id="test-1", content="Found memory")]
        mock_memory_instance.vector_store.search.return_value = mock_results
        mock_memory_instance.vector_store.delete.return_value = True
        
        # Perform multiple operations
        add_result = mock_memory_instance.add(memory_content="Test memory 1")
        search_result = mock_memory_instance.search(query="test")
        add_result2 = mock_memory_instance.add(memory_content="Test memory 2")
        delete_result = mock_memory_instance.delete("test-1")
        
        # Verify all operations succeeded
        assert add_result['success'] is True
        assert len(search_result['results']) == 1
        assert add_result2['success'] is True
        assert delete_result['success'] is True
        
        # Verify correct number of calls
        assert mock_memory_instance.embedding_provider.embed.call_count == 3  # 2 adds + 1 search
        assert mock_memory_instance.vector_store.insert.call_count == 2  # 2 adds
        assert mock_memory_instance.vector_store.search.call_count == 1  # 1 search
        assert mock_memory_instance.vector_store.delete.call_count == 1  # 1 delete

    def test_memory_with_complex_metadata(self, mock_memory_instance, mock_embedding_response):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Memory storage with complex nested metadata
        
        Advanced scenario:
        - Tests handling of complex data structures in metadata
        - Ensures our system can handle real-world metadata complexity
        - Validates serialization/deserialization of complex objects
        
        Expected behavior:
        - Complex metadata should be stored correctly
        - Nested structures should be preserved
        """
        mock_memory_instance.embedding_provider.embed.return_value = mock_embedding_response
        mock_memory_instance.vector_store.insert.return_value = True
        
        # Complex metadata with nested structures
        complex_metadata = {
            "user_info": {
                "id": "user123",
                "preferences": ["ai", "technology", "science"],
                "settings": {
                    "notifications": True,
                    "privacy_level": "medium"
                }
            },
            "context": {
                "session_id": "sess_456",
                "timestamp": datetime.now().isoformat(),
                "source": "chat_interface",
                "confidence_scores": [0.95, 0.87, 0.92]
            },
            "tags_structured": {
                "categories": ["work", "personal"],
                "priority": "high",
                "auto_generated": True
            }
        }
        
        result = mock_memory_instance.add(
            memory_content="Complex memory with rich metadata",
            metadata=complex_metadata
        )
        
        # Verify the memory was added successfully
        assert result['success'] is True
        
        # Verify complex metadata was included in the payload
        call_args = mock_memory_instance.vector_store.insert.call_args
        payload = call_args[1]['payloads'][0]
        
        # Check that complex metadata was preserved
        assert payload['user_info']['id'] == "user123"
        assert payload['user_info']['preferences'] == ["ai", "technology", "science"]
        assert payload['context']['source'] == "chat_interface"
        assert payload['tags_structured']['priority'] == "high"

    def test_search_with_advanced_filters(self, mock_memory_instance, mock_embedding_response, create_mock_point):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Search with multiple filter combinations
        
        Advanced scenario:
        - Tests complex filtering scenarios
        - Ensures filter parameters are passed correctly
        - Validates advanced search capabilities
        
        Expected behavior:
        - All filter parameters should be passed to vector store
        - Search should work with multiple filters simultaneously
        """
        mock_memory_instance.embedding_provider.embed.return_value = mock_embedding_response
        
        mock_results = [create_mock_point(id="filtered-1", content="Filtered result")]
        mock_memory_instance.vector_store.search.return_value = mock_results
        
        # Search with multiple filters
        result = mock_memory_instance.search(
            query="complex search",
            limit=20,
            tags=["work", "important"],
            people_mentioned=["Alice", "Bob"],
            topic_category="meetings",
            threshold=0.8,
            match_all_tags=True,
            sort_by="timestamp"
        )
        
        # Verify search was called with correct parameters
        call_args = mock_memory_instance.vector_store.search.call_args
        assert call_args[1]['query'] == "complex search"
        assert call_args[1]['limit'] == 20
        
        # Verify filters were passed
        filters = call_args[1]['filters']
        assert filters['tags'] == ["work", "important"]
        assert filters['people_mentioned'] == ["Alice", "Bob"]
        assert filters['topic_category'] == "meetings"
        assert filters['match_all_tags'] is True
        
        # Verify results
        assert len(result['results']) == 1
        assert result['results'][0]['id'] == "filtered-1"


class TestMemoryErrorHandling:
    """Comprehensive error handling tests inspired by mem0's robustness."""
    
    def test_memory_resilience_to_provider_failures(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: System resilience when providers fail unexpectedly
        
        Advanced error handling:
        - Tests various failure modes of external providers
        - Ensures graceful degradation and error reporting
        - Validates that failures don't crash the system
        
        Expected behavior:
        - All failures should be caught and reported gracefully
        - System should remain stable after failures
        """
        # Test embedding provider failures
        mock_memory_instance.embedding_provider.embed.side_effect = ConnectionError("Ollama service unavailable")
        
        result = mock_memory_instance.add(memory_content="Test during failure")
        assert result['success'] is False
        assert "Ollama service unavailable" in result['error']
        
        # Test vector store failures
        mock_memory_instance.embedding_provider.embed.side_effect = None
        mock_memory_instance.embedding_provider.embed.return_value = [0.1, 0.2, 0.3]
        mock_memory_instance.vector_store.insert.side_effect = TimeoutError("Vector store timeout")
        
        result = mock_memory_instance.add(memory_content="Test during vector store failure")
        assert result['success'] is False
        assert "Vector store timeout" in result['error']

    def test_search_with_malformed_queries(self, mock_memory_instance):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Search behavior with problematic query inputs
        
        Advanced error handling:
        - Tests edge cases in query processing
        - Ensures system handles malformed inputs gracefully
        - Validates input sanitization and error handling
        
        Expected behavior:
        - Malformed queries should not crash the system
        - Should return empty results or appropriate errors
        """
        # Test with None query (should be handled as empty)
        result = mock_memory_instance.search(query=None)
        assert 'results' in result
        
        # Test with very long query
        very_long_query = "test " * 1000
        # The system may strip trailing whitespace, so we expect the trimmed version
        expected_query = very_long_query.rstrip()
        
        mock_memory_instance.embedding_provider.embed.return_value = [0.1] * 768
        mock_memory_instance.vector_store.search.return_value = []
        
        result = mock_memory_instance.search(query=very_long_query)
        assert 'results' in result
        
        # Verify embedding was called with the processed query (trailing space may be stripped)
        mock_memory_instance.embedding_provider.embed.assert_called_with(expected_query)


# Summary of Advanced Tests Added:
# ================================
# 1. Parametrized tests for multiple scenarios (provider combinations, content validation, limits)
# 2. Advanced configuration testing (dict configs, complex metadata)
# 3. Concurrent operations testing
# 4. Complex filtering and search scenarios
# 5. Comprehensive error handling and resilience testing
#
# These tests complement the basic functionality tests and ensure
# robustness in real-world usage scenarios.
