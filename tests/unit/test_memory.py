"""
Unit tests for the Memory class.

Tests the core functionality of the Memory SDK including:
- Basic memory operations (add, search, get, delete)
- Configuration handling
- Storage backend integration
- Error handling
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from inmemory import InMemoryConfig, Memory
from inmemory.stores import MemoryStoreInterface


class TestMemoryBasicFunctionality:
    """Test basic Memory class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_memory_initialization_default(self):
        """Test Memory initialization with default settings."""
        with patch("inmemory.memory.create_store") as mock_create_store:
            mock_store = Mock(spec=MemoryStoreInterface)
            mock_create_store.return_value = mock_store

            memory = Memory()

            assert memory is not None
            assert memory.config is not None
            assert memory.store is mock_store
            assert memory.default_user == "default"

    def test_memory_initialization_with_config(self):
        """Test Memory initialization with custom config."""
        config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "test_user"},
        )

        with patch("inmemory.memory.create_store") as mock_create_store:
            mock_store = Mock(spec=MemoryStoreInterface)
            mock_create_store.return_value = mock_store

            memory = Memory(config=config)

            assert memory.config == config
            assert memory.store is mock_store

    def test_memory_initialization_with_storage_type(self):
        """Test Memory initialization with explicit storage type."""
        with patch("inmemory.memory.create_store") as mock_create_store:
            mock_store = Mock(spec=MemoryStoreInterface)
            mock_create_store.return_value = mock_store

            memory = Memory(storage_type="file")

            assert memory.config.storage.type == "file"
            mock_create_store.assert_called_once()

    def test_memory_initialization_fallback_on_error(self):
        """Test Memory falls back to file storage on initialization error."""
        with patch("inmemory.memory.create_store") as mock_create_store:
            # First call fails, second call (fallback) succeeds
            mock_store = Mock(spec=MemoryStoreInterface)
            mock_create_store.side_effect = [Exception("Connection failed"), mock_store]

            memory = Memory()

            assert memory.store is mock_store
            assert mock_create_store.call_count == 2


class TestMemoryOperations:
    """Test Memory CRUD operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_store = Mock(spec=MemoryStoreInterface)
        self.mock_store.validate_user.return_value = True

        # Patch the create_store function to return our mock
        self.store_patcher = patch(
            "inmemory.memory.create_store", return_value=self.mock_store
        )
        self.store_patcher.start()

        # Patch the add_memory_enhanced function
        self.add_memory_patcher = patch("inmemory.memory.add_memory_enhanced")
        self.mock_add_memory = self.add_memory_patcher.start()

        # Patch the search engine
        self.search_patcher = patch("inmemory.memory.EnhancedSearchEngine")
        self.mock_search_engine_class = self.search_patcher.start()
        self.mock_search_engine = Mock()
        self.mock_search_engine_class.return_value = self.mock_search_engine

        self.memory = Memory()

    def teardown_method(self):
        """Clean up patches."""
        self.store_patcher.stop()
        self.add_memory_patcher.stop()
        self.search_patcher.stop()

    def test_add_memory_success(self):
        """Test successful memory addition."""
        self.mock_add_memory.return_value = {"memory_id": "test_id", "success": True}

        result = self.memory.add("Test memory content")

        assert result["memory_id"] == "test_id"
        assert result["success"] is True
        self.mock_store.validate_user.assert_called_with("default")
        self.mock_add_memory.assert_called_once()

    def test_add_memory_with_metadata(self):
        """Test memory addition with metadata."""
        self.mock_add_memory.return_value = {"memory_id": "test_id"}

        result = self.memory.add(
            "Test memory content",
            tags="test,memory",
            people_mentioned="Alice,Bob",
            topic_category="testing",
            metadata={"custom": "value"},
        )

        self.mock_add_memory.assert_called_with(
            memory_content="Test memory content",
            user_id="default",
            tags="test,memory",
            people_mentioned="Alice,Bob",
            topic_category="testing",
        )
        assert result["metadata"]["custom"] == "value"

    def test_add_memory_user_creation(self):
        """Test automatic user creation when user doesn't exist."""
        self.mock_store.validate_user.return_value = False
        self.mock_add_memory.return_value = {"memory_id": "test_id"}

        result = self.memory.add("Test memory content")

        self.mock_store.create_user.assert_called_with("default")
        assert "memory_id" in result

    def test_add_memory_error_handling(self):
        """Test error handling in memory addition."""
        self.mock_add_memory.side_effect = Exception("Addition failed")

        result = self.memory.add("Test memory content")

        assert result["success"] is False
        assert "error" in result

    def test_search_memories_success(self):
        """Test successful memory search."""
        expected_results = [
            {"memory": "Test memory 1", "score": 0.9},
            {"memory": "Test memory 2", "score": 0.8},
        ]
        self.mock_search_engine.search_memories.return_value = expected_results

        result = self.memory.search("test query")

        assert result["results"] == expected_results
        self.mock_search_engine.search_memories.assert_called_with(
            query="test query",
            user_id="default",
            limit=10,
            tags=None,
            people_mentioned=None,
            topic_category=None,
            temporal_filter=None,
        )

    def test_search_memories_with_filters(self):
        """Test memory search with filters."""
        self.mock_search_engine.search_memories.return_value = []

        result = self.memory.search(
            "test query",
            limit=5,
            tags=["work", "important"],
            people_mentioned=["Alice"],
            topic_category="project",
            temporal_filter="today",
        )

        self.mock_search_engine.search_memories.assert_called_with(
            query="test query",
            user_id="default",
            limit=5,
            tags=["work", "important"],
            people_mentioned=["Alice"],
            topic_category="project",
            temporal_filter="today",
        )

    def test_search_memories_with_threshold(self):
        """Test memory search with score threshold."""
        search_results = [
            {"memory": "High score", "score": 0.9},
            {"memory": "Low score", "score": 0.3},
        ]
        self.mock_search_engine.search_memories.return_value = search_results

        result = self.memory.search("test query", threshold=0.5)

        # Only high score result should remain
        assert len(result["results"]) == 1
        assert result["results"][0]["memory"] == "High score"

    def test_search_memories_user_not_found(self):
        """Test search when user doesn't exist."""
        self.mock_store.validate_user.return_value = False

        result = self.memory.search("test query")

        assert result["results"] == []

    def test_get_all_memories(self):
        """Test getting all memories."""
        expected_results = [{"memory": "Memory 1"}, {"memory": "Memory 2"}]
        self.mock_search_engine.search_memories.return_value = expected_results

        result = self.memory.get_all(limit=5)

        assert result["results"] == expected_results
        self.mock_search_engine.search_memories.assert_called_with(
            query="", user_id="default", limit=5
        )

    def test_get_all_memories_with_offset(self):
        """Test getting all memories with offset."""
        all_results = [
            {"memory": "Memory 1"},
            {"memory": "Memory 2"},
            {"memory": "Memory 3"},
        ]
        self.mock_search_engine.search_memories.return_value = all_results

        result = self.memory.get_all(limit=2, offset=1)

        # Should get 3 results (2 + 1 offset) and then apply offset
        assert len(result["results"]) == 2  # All results minus offset
        self.mock_search_engine.search_memories.assert_called_with(
            query="",
            user_id="default",
            limit=3,  # limit + offset
        )

    @patch("inmemory.memory.delete_user_memory")
    def test_delete_memory_success(self, mock_delete):
        """Test successful memory deletion."""
        mock_delete.return_value = True

        result = self.memory.delete("test_memory_id")

        assert result["success"] is True
        assert "deleted successfully" in result["message"]
        mock_delete.assert_called_with("default", "test_memory_id")

    @patch("inmemory.memory.delete_user_memory")
    def test_delete_memory_not_found(self, mock_delete):
        """Test memory deletion when memory not found."""
        mock_delete.return_value = False

        result = self.memory.delete("nonexistent_id")

        assert result["success"] is False
        assert "not found" in result["error"]

    @patch("inmemory.memory.delete_user_memory")
    def test_delete_memory_error(self, mock_delete):
        """Test error handling in memory deletion."""
        mock_delete.side_effect = Exception("Deletion failed")

        result = self.memory.delete("test_memory_id")

        assert result["success"] is False
        assert "error" in result


class TestMemoryAdvancedSearch:
    """Test advanced search functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_store = Mock(spec=MemoryStoreInterface)
        self.mock_store.validate_user.return_value = True

        with (
            patch("inmemory.memory.create_store", return_value=self.mock_store),
            patch("inmemory.memory.EnhancedSearchEngine") as mock_search_class,
        ):
            self.mock_search_engine = Mock()
            mock_search_class.return_value = self.mock_search_engine
            self.memory = Memory()

    def test_temporal_search(self):
        """Test temporal search functionality."""
        expected_results = [{"memory": "Yesterday's memory"}]
        self.mock_search_engine.temporal_search.return_value = expected_results

        result = self.memory.temporal_search("yesterday", semantic_query="meetings")

        assert result["results"] == expected_results
        self.mock_search_engine.temporal_search.assert_called_with(
            temporal_query="yesterday",
            user_id="default",
            semantic_query="meetings",
            limit=10,
        )

    def test_search_by_tags_string(self):
        """Test tag search with string input."""
        expected_results = [{"memory": "Work memory"}]
        self.mock_search_engine.tag_search.return_value = expected_results

        result = self.memory.search_by_tags("work,important", match_all=True)

        assert result["results"] == expected_results
        self.mock_search_engine.tag_search.assert_called_with(
            tags=["work", "important"],
            user_id="default",
            semantic_query=None,
            match_all_tags=True,
            limit=10,
        )

    def test_search_by_tags_list(self):
        """Test tag search with list input."""
        expected_results = [{"memory": "Tagged memory"}]
        self.mock_search_engine.tag_search.return_value = expected_results

        result = self.memory.search_by_tags(["work", "project"])

        self.mock_search_engine.tag_search.assert_called_with(
            tags=["work", "project"],
            user_id="default",
            semantic_query=None,
            match_all_tags=False,
            limit=10,
        )

    def test_search_by_people_string(self):
        """Test people search with string input."""
        expected_results = [{"memory": "Meeting with Alice"}]
        self.mock_search_engine.people_search.return_value = expected_results

        result = self.memory.search_by_people("Alice,Bob")

        assert result["results"] == expected_results
        self.mock_search_engine.people_search.assert_called_with(
            people=["Alice", "Bob"], user_id="default", semantic_query=None, limit=10
        )

    def test_search_by_people_list(self):
        """Test people search with list input."""
        expected_results = [{"memory": "Team meeting"}]
        self.mock_search_engine.people_search.return_value = expected_results

        result = self.memory.search_by_people(["Alice", "Bob"])

        self.mock_search_engine.people_search.assert_called_with(
            people=["Alice", "Bob"], user_id="default", semantic_query=None, limit=10
        )


class TestMemoryUserManagement:
    """Test user management functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_store = Mock(spec=MemoryStoreInterface)

        with (
            patch("inmemory.memory.create_store", return_value=self.mock_store),
            patch("inmemory.memory.EnhancedSearchEngine"),
        ):
            self.memory = Memory()

    def test_create_user_success(self):
        """Test successful user creation."""
        self.mock_store.create_user.return_value = True

        with patch("inmemory.memory.ensure_user_collection_exists") as mock_ensure:
            mock_ensure.return_value = "user_collection"

            result = self.memory.create_user("new_user", email="test@example.com")

            assert result["success"] is True
            assert result["user_id"] == "new_user"
            assert result["collection_name"] == "user_collection"
            self.mock_store.create_user.assert_called_with(
                "new_user", email="test@example.com"
            )

    def test_create_user_failure(self):
        """Test user creation failure."""
        self.mock_store.create_user.return_value = False

        result = self.memory.create_user("new_user")

        assert result["success"] is False
        assert "Failed to create user" in result["error"]

    def test_generate_api_key_success(self):
        """Test successful API key generation."""
        self.mock_store.store_api_key.return_value = True

        result = self.memory.generate_api_key("test_user", "my_app")

        assert result["success"] is True
        assert result["user_id"] == "test_user"
        assert result["name"] == "my_app"
        assert result["api_key"].startswith("im_")
        self.mock_store.store_api_key.assert_called_once()

    def test_generate_api_key_failure(self):
        """Test API key generation failure."""
        self.mock_store.store_api_key.return_value = False

        result = self.memory.generate_api_key("test_user")

        assert result["success"] is False
        assert "Failed to store API key" in result["error"]

    def test_list_api_keys(self):
        """Test listing API keys."""
        expected_keys = [{"name": "app1", "created": "2024-01-01"}]
        self.mock_store.list_user_api_keys.return_value = expected_keys

        result = self.memory.list_api_keys("test_user")

        assert result == expected_keys
        self.mock_store.list_user_api_keys.assert_called_with("test_user")

    def test_revoke_api_key_success(self):
        """Test successful API key revocation."""
        self.mock_store.revoke_api_key.return_value = True

        result = self.memory.revoke_api_key("test_api_key")

        assert result["success"] is True
        assert "revoked" in result["message"]

    def test_revoke_api_key_not_found(self):
        """Test API key revocation when key not found."""
        self.mock_store.revoke_api_key.return_value = False

        result = self.memory.revoke_api_key("nonexistent_key")

        assert result["success"] is False
        assert "not found" in result["error"]


class TestMemoryUtilities:
    """Test utility methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_store = Mock(spec=MemoryStoreInterface)

        with (
            patch("inmemory.memory.create_store", return_value=self.mock_store),
            patch("inmemory.memory.EnhancedSearchEngine"),
        ):
            self.memory = Memory()

    def test_get_config_safe(self):
        """Test getting configuration with sensitive data hidden."""
        result = self.memory.get_config()

        assert isinstance(result, dict)
        # Should not contain sensitive information
        if "storage" in result and "mongodb_uri" in result["storage"]:
            assert result["storage"]["mongodb_uri"] == "***HIDDEN***"

    def test_health_check_healthy(self):
        """Test health check when all components are healthy."""
        self.mock_store.get_stats.return_value = {"connections": 1}

        result = self.memory.health_check()

        assert result["status"] == "healthy"
        assert "storage_backend" in result
        assert "timestamp" in result
        assert result["storage"]["status"] == "healthy"

    def test_health_check_unhealthy(self):
        """Test health check when components fail."""
        self.mock_store.get_stats.side_effect = Exception("Connection failed")

        result = self.memory.health_check()

        assert result["status"] == "unhealthy"
        assert "error" in result

    def test_context_manager(self):
        """Test Memory as context manager."""
        with patch.object(self.memory, "close") as mock_close:
            with self.memory as m:
                assert m is self.memory
            mock_close.assert_called_once()

    def test_repr(self):
        """Test string representation."""
        result = repr(self.memory)
        assert "Memory(storage=" in result
        assert self.memory.config.storage.type in result


if __name__ == "__main__":
    pytest.main([__file__])
