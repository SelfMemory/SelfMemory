"""
Pytest configuration and shared fixtures for InMemory tests.

This module provides common fixtures and utilities used across all test modules,
following  testing patterns with comprehensive mocking strategies.
"""

import os
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

import pytest

from inmemory.configs.base import InMemoryConfig
from inmemory.memory.main import Memory


@pytest.fixture(autouse=True)
def mock_environment():
    """Auto-use fixture to set up clean test environment."""
    # Set test environment variables
    os.environ["INMEMORY_TEST_MODE"] = "true"
    # Ensure no real API keys are used in tests
    if "OLLAMA_API_KEY" in os.environ:
        del os.environ["OLLAMA_API_KEY"]
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
    yield
    # Cleanup after tests
    if "INMEMORY_TEST_MODE" in os.environ:
        del os.environ["INMEMORY_TEST_MODE"]


@pytest.fixture
def mock_embedding_response():
    """Mock embedding response data."""
    return [0.1, 0.2, 0.3, 0.4, 0.5] * 153  # 765 dimensions (common size)


@pytest.fixture
def mock_memory_data():
    """Sample memory data for testing."""
    return {
        "id": "test-memory-123",
        "content": "I love pizza and Italian food",
        "tags": "food,personal",
        "people_mentioned": "John,Sarah",
        "topic_category": "food",
        "created_at": "2024-01-01T12:00:00",
        "metadata": {"source": "test", "confidence": 0.95},
    }


@pytest.fixture
def mock_search_results(mock_memory_data):
    """Mock search results from vector store."""
    return [
        Mock(
            id=mock_memory_data["id"],
            payload={
                "data": mock_memory_data["content"],
                "tags": mock_memory_data["tags"],
                "people_mentioned": mock_memory_data["people_mentioned"],
                "topic_category": mock_memory_data["topic_category"],
                "created_at": mock_memory_data["created_at"],
                **mock_memory_data["metadata"],
            },
            score=0.95,
        )
    ]


@pytest.fixture
def mock_ollama_embedding():
    """Mock Ollama embedding provider."""
    mock_embedding = Mock()
    mock_embedding.embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5] * 153
    mock_embedding.health_check.return_value = {"status": "healthy"}
    return mock_embedding


@pytest.fixture
def mock_qdrant_vector_store():
    """Mock Qdrant vector store."""
    mock_store = Mock()
    mock_store.insert.return_value = True
    mock_store.search.return_value = []
    mock_store.list.return_value = ([], None)
    mock_store.delete.return_value = True
    mock_store.delete_all.return_value = True
    mock_store.count.return_value = 0
    mock_store.health_check.return_value = {"status": "healthy", "memory_count": 0}
    return mock_store


@pytest.fixture
def mock_config():
    """Mock InMemoryConfig with default settings."""
    config = InMemoryConfig()
    # Ensure we have valid default configurations
    config.embedding.provider = "ollama"
    config.vector_store.provider = "qdrant"
    return config


@pytest.fixture
def mock_memory_instance(mock_config, mock_ollama_embedding, mock_qdrant_vector_store):
    """
    Mock Memory instance with all dependencies mocked.

    This fixture provides a fully mocked Memory instance that can be used
    for testing without requiring actual external services.
    """
    with (
        patch(
            "inmemory.utils.factory.EmbeddingFactory.create"
        ) as mock_embedding_factory,
        patch(
            "inmemory.utils.factory.VectorStoreFactory.create"
        ) as mock_vector_factory,
    ):
        # Configure factory mocks
        mock_embedding_factory.return_value = mock_ollama_embedding
        mock_vector_factory.return_value = mock_qdrant_vector_store

        # Create Memory instance
        memory = Memory(config=mock_config)

        # Ensure mocked components are properly attached
        memory.embedding_provider = mock_ollama_embedding
        memory.vector_store = mock_qdrant_vector_store

        yield memory


@pytest.fixture
def sample_memories():
    """Sample memory data for testing multiple memories."""
    return [
        {
            "content": "I love pizza and Italian food",
            "tags": "food,personal",
            "people_mentioned": "John",
            "topic_category": "food",
        },
        {
            "content": "Meeting with Sarah about the project deadline",
            "tags": "work,meeting",
            "people_mentioned": "Sarah",
            "topic_category": "work",
        },
        {
            "content": "Watched a great movie last night",
            "tags": "entertainment,personal",
            "people_mentioned": "",
            "topic_category": "entertainment",
        },
    ]


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for testing InmemoryClient."""
    mock_client = Mock()
    mock_client.get.return_value = Mock(
        status_code=200, json=lambda: {"status": "healthy"}
    )
    mock_client.post.return_value = Mock(
        status_code=200, json=lambda: {"success": True, "memory_id": str(uuid.uuid4())}
    )
    mock_client.delete.return_value = Mock(
        status_code=200,
        json=lambda: {"success": True, "message": "Deleted successfully"},
    )
    return mock_client


class MockPoint:
    """Mock point object for vector store responses."""

    def __init__(self, id: str, payload: dict[str, Any], score: float = 1.0):
        self.id = id
        self.payload = payload
        self.score = score


@pytest.fixture
def create_mock_point():
    """Factory fixture for creating mock points."""

    def _create_point(
        id: str = None, content: str = "test content", score: float = 1.0, **kwargs
    ):
        if id is None:
            id = str(uuid.uuid4())

        payload = {
            "data": content,
            "tags": kwargs.get("tags", ""),
            "people_mentioned": kwargs.get("people_mentioned", ""),
            "topic_category": kwargs.get("topic_category", ""),
            "created_at": kwargs.get("created_at", datetime.now().isoformat()),
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ["tags", "people_mentioned", "topic_category", "created_at"]
            },
        }

        return MockPoint(id=id, payload=payload, score=score)

    return _create_point


# Test markers for categorizing tests
pytestmark = [
    pytest.mark.unit,  # Default marker for unit tests
]


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "network: Tests requiring network access")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        # Mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark network tests
        if "network" in item.name or "client" in str(item.fspath):
            item.add_marker(pytest.mark.network)

        # Mark slow tests
        if "slow" in item.name or "load" in item.name:
            item.add_marker(pytest.mark.slow)
