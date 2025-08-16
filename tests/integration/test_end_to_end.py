"""
Integration tests for InMemory package.

Tests the full end-to-end functionality with real storage backends,
ensuring all components work together correctly.
"""

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from inmemory import InMemoryConfig, Memory


class TestFileStorageIntegration:
    """Test end-to-end functionality with file storage."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "test_user"},
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_full_memory_lifecycle(self):
        """Test complete memory lifecycle: add, search, update, delete."""
        with Memory(config=self.config) as memory:
            # Add memories
            result1 = memory.add(
                "I had a great meeting with Alice about the new project",
                tags="work,meeting",
                people_mentioned="Alice",
                topic_category="project",
            )

            result2 = memory.add(
                "Pizza lunch with Bob and Carol was amazing",
                tags="food,social",
                people_mentioned="Bob,Carol",
                topic_category="social",
            )

            # Verify memories were added
            assert "memory_id" in result1 or "success" in result1
            assert "memory_id" in result2 or "success" in result2

            # Wait a bit for any async operations
            time.sleep(0.1)

            # Search for memories
            work_results = memory.search("meeting Alice")
            assert len(work_results["results"]) > 0

            food_results = memory.search("pizza")
            assert len(food_results["results"]) > 0

            # Test tag-based search
            work_memories = memory.search_by_tags(["work"])
            assert len(work_memories["results"]) > 0

            # Test people-based search
            alice_memories = memory.search_by_people(["Alice"])
            assert len(alice_memories["results"]) > 0

            # Get all memories
            all_memories = memory.get_all()
            assert len(all_memories["results"]) >= 2

    def test_multiple_users_isolation(self):
        """Test that users' memories are properly isolated."""
        # Create two users
        config1 = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "user1"},
        )

        config2 = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "user2"},
        )

        # Add memories for each user
        with Memory(config=config1) as memory1:
            memory1.add("User 1's private memory", tags="private")

        with Memory(config=config2) as memory2:
            memory2.add("User 2's private memory", tags="private")

        # Verify isolation
        with Memory(config=config1) as memory1:
            user1_memories = memory1.search("private")
            assert len(user1_memories["results"]) >= 1
            # Should only contain user1's memory
            for result in user1_memories["results"]:
                assert "User 1's" in result.get("memory", "")

        with Memory(config=config2) as memory2:
            user2_memories = memory2.search("private")
            assert len(user2_memories["results"]) >= 1
            # Should only contain user2's memory
            for result in user2_memories["results"]:
                assert "User 2's" in result.get("memory", "")

    def test_persistence_across_sessions(self):
        """Test that memories persist across different Memory instances."""
        # Add memory in first session
        with Memory(config=self.config) as memory1:
            result = memory1.add("Persistent memory test", tags="persistence")
            assert "memory_id" in result or "success" in result

        # Retrieve memory in second session
        with Memory(config=self.config) as memory2:
            results = memory2.search("persistent")
            assert len(results["results"]) > 0
            assert any(
                "Persistent memory test" in r.get("memory", "")
                for r in results["results"]
            )

    def test_error_handling_invalid_config(self):
        """Test error handling with invalid configuration."""
        # Invalid storage path
        invalid_config = InMemoryConfig(
            storage={"type": "file", "path": "/nonexistent/readonly/path"}
        )

        # Should not crash, should fall back gracefully
        try:
            with Memory(config=invalid_config) as memory:
                # Should still work with fallback
                result = memory.add("Test memory")
                assert isinstance(result, dict)
        except Exception as e:
            # If it does raise an exception, it should be informative
            assert "storage" in str(e).lower() or "path" in str(e).lower()


class TestSearchFunctionality:
    """Test advanced search functionality end-to-end."""

    def setup_method(self):
        """Set up test fixtures with sample data."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "search_test_user"},
        )

        # Add sample memories
        with Memory(config=self.config) as memory:
            # Work memories
            memory.add(
                "Team standup meeting with Alice and Bob about sprint planning",
                tags="work,meeting,sprint",
                people_mentioned="Alice,Bob",
                topic_category="work",
            )

            memory.add(
                "Code review session with Carol for the authentication module",
                tags="work,code-review",
                people_mentioned="Carol",
                topic_category="development",
            )

            # Personal memories
            memory.add(
                "Had dinner with Alice at the new Italian restaurant",
                tags="personal,food,restaurant",
                people_mentioned="Alice",
                topic_category="social",
            )

            memory.add(
                "Weekend hiking trip to the mountains with Bob and Dave",
                tags="personal,outdoor,hiking",
                people_mentioned="Bob,Dave",
                topic_category="recreation",
            )

            # Learning memories
            memory.add(
                "Completed Python advanced course on machine learning",
                tags="learning,python,ml",
                people_mentioned="",
                topic_category="education",
            )

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_semantic_search(self):
        """Test semantic search functionality."""
        with Memory(config=self.config) as memory:
            # Search for work-related content
            work_results = memory.search("team meeting planning")
            assert len(work_results["results"]) > 0

            # Search for food-related content
            food_results = memory.search("restaurant dinner")
            assert len(food_results["results"]) > 0

            # Search for learning content
            learning_results = memory.search("course education")
            assert len(learning_results["results"]) > 0

    def test_tag_based_search(self):
        """Test tag-based search with different combinations."""
        with Memory(config=self.config) as memory:
            # Single tag search
            work_memories = memory.search_by_tags(["work"])
            assert len(work_memories["results"]) >= 2

            # Multiple tags (OR search)
            outdoor_or_food = memory.search_by_tags(
                ["outdoor", "food"], match_all=False
            )
            assert len(outdoor_or_food["results"]) >= 2

            # Multiple tags (AND search)
            work_and_meeting = memory.search_by_tags(
                ["work", "meeting"], match_all=True
            )
            assert len(work_and_meeting["results"]) >= 1

    def test_people_based_search(self):
        """Test people-based search functionality."""
        with Memory(config=self.config) as memory:
            # Search for memories involving Alice
            alice_memories = memory.search_by_people(["Alice"])
            assert len(alice_memories["results"]) >= 2

            # Search for memories involving Bob
            bob_memories = memory.search_by_people(["Bob"])
            assert len(bob_memories["results"]) >= 2

            # Search for memories involving multiple people
            multiple_people = memory.search_by_people(["Alice", "Bob"])
            assert len(multiple_people["results"]) >= 1

    def test_combined_search_filters(self):
        """Test combining different search filters."""
        with Memory(config=self.config) as memory:
            # Semantic query with tag filter
            results = memory.search("meeting", tags=["work"])
            assert len(results["results"]) >= 1

            # Semantic query with people filter
            results = memory.search("dinner", people_mentioned=["Alice"])
            assert len(results["results"]) >= 1

    def test_search_result_scoring(self):
        """Test that search results are properly scored."""
        with Memory(config=self.config) as memory:
            results = memory.search("team meeting")

            # Check that results have scores
            for result in results["results"]:
                assert "score" in result
                assert isinstance(result["score"], (int, float))
                assert 0 <= result["score"] <= 1

            # Check that results are sorted by score (if multiple results)
            if len(results["results"]) > 1:
                scores = [r["score"] for r in results["results"]]
                assert scores == sorted(scores, reverse=True)


class TestConfigurationIntegration:
    """Test configuration system integration."""

    def test_auto_detection(self):
        """Test automatic configuration detection."""
        # Test with environment variables
        old_env = os.environ.copy()
        try:
            os.environ["INMEMORY_STORAGE_TYPE"] = "file"
            os.environ["INMEMORY_USER"] = "env_user"

            memory = Memory(auto_detect=True)
            assert memory.config.storage.type == "file"
            assert memory.default_user == "env_user"

        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_configuration_validation(self):
        """Test configuration validation."""
        # Valid file config
        valid_config = InMemoryConfig(
            storage={"type": "file", "path": "/tmp/test"}, auth={"type": "simple"}
        )
        assert valid_config.storage.type == "file"

        # Test that invalid configs raise appropriate errors
        with pytest.raises((ValueError, TypeError)):
            InMemoryConfig(storage={"type": "invalid_type"})


class TestErrorHandlingIntegration:
    """Test error handling in integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_graceful_degradation(self):
        """Test graceful degradation when components fail."""
        config = InMemoryConfig(storage={"type": "file", "path": str(self.temp_dir)})

        with Memory(config=config) as memory:
            # Add a memory first
            memory.add("Test memory for error handling")

            # Simulate storage failure by removing directory
            shutil.rmtree(self.temp_dir)

            # Operations should not crash, but return error responses
            result = memory.add("Another test memory")
            assert isinstance(result, dict)
            # Should indicate failure
            if "success" in result:
                assert result["success"] is False

    def test_invalid_memory_operations(self):
        """Test handling of invalid memory operations."""
        config = InMemoryConfig(storage={"type": "file", "path": str(self.temp_dir)})

        with Memory(config=config) as memory:
            # Try to delete non-existent memory
            result = memory.delete("nonexistent_id")
            assert result["success"] is False
            assert "error" in result

            # Try to search with invalid parameters
            result = memory.search("")  # Empty query
            assert isinstance(result, dict)
            assert "results" in result


if __name__ == "__main__":
    pytest.main([__file__])
