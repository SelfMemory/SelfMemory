"""
Tests that validate README examples work correctly.

These tests ensure that all code examples in the README
are functional and produce expected results.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from inmemory import InMemoryConfig, Memory


class TestReadmeExamples:
    """Test examples from README.md."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_quick_start_example(self):
        """Test the main quick start example from README."""
        # Configure to use file storage for testing
        config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "alice"},
        )

        memory = Memory(config=config)

        # Add memories with rich metadata (from README example)
        result1 = memory.add("I love pizza but hate broccoli", tags="food,preferences")

        result2 = memory.add(
            "Meeting with Bob and Carol about Q4 planning tomorrow at 3pm",
            tags="work,meeting",
            people_mentioned="Bob,Carol",
            topic_category="planning",
        )

        # Verify memories were added successfully
        assert isinstance(result1, dict)
        assert isinstance(result2, dict)

        # Search memories (from README example)
        results = memory.search("pizza")
        assert len(results["results"]) > 0

        # Verify structure matches README expectation
        for result in results["results"]:
            assert "memory" in result
            assert "tags" in result
            assert "score" in result

        # Advanced searches (from README example)
        work_memories = memory.search_by_tags(["work"])
        assert len(work_memories["results"]) > 0

        people_memories = memory.search_by_people(["Bob"])
        assert len(people_memories["results"]) > 0

        # Verify the pizza memory contains expected content
        pizza_found = False
        for result in results["results"]:
            if "pizza" in result["memory"].lower():
                pizza_found = True
                if "tags" in result:
                    assert "food" in result["tags"] or "preferences" in result["tags"]
        assert pizza_found

    def test_personal_ai_assistant_example(self):
        """Test the PersonalAssistant example from README."""
        # Simplified version of the README example
        config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "assistant_user"},
        )

        class PersonalAssistant:
            def __init__(self):
                self.memory = Memory(config=config)

            def store_interaction(self, user_input: str, response: str) -> None:
                """Store conversation for context."""
                self.memory.add(f"User: {user_input}")
                self.memory.add(f"Assistant: {response}")

            def get_context(self, user_input: str, limit: int = 5) -> str:
                """Get relevant context from memory."""
                memories = self.memory.search(user_input, limit=limit)
                return "\n".join([m["memory"] for m in memories["results"]])

        # Test the assistant
        assistant = PersonalAssistant()

        # Store some interactions
        assistant.store_interaction(
            "What's my favorite food?",
            "Based on our previous conversations, you mentioned loving pizza.",
        )

        assistant.store_interaction(
            "Plan a team meeting",
            "I'll help you plan a meeting. What's the purpose and who should attend?",
        )

        # Test context retrieval
        context = assistant.get_context("food preferences")
        assert "pizza" in context.lower()

        context = assistant.get_context("meeting")
        assert "meeting" in context.lower()

    def test_customer_support_bot_example(self):
        """Test the SupportBot example from README."""
        config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "support"},
        )

        class SupportBot:
            def __init__(self):
                self.memory = Memory(config=config)

            def handle_ticket(self, customer_id: str, issue: str) -> dict:
                """Handle support ticket with memory context."""
                # Check customer history
                history = self.memory.search_by_people([customer_id])
                similar_issues = self.memory.search(issue, limit=3)

                # Store interaction
                self.memory.add(
                    f"Customer {customer_id} reported: {issue}",
                    tags="ticket,customer_support",
                    people_mentioned=customer_id,
                    topic_category="support",
                )

                return {
                    "customer_id": customer_id,
                    "issue": issue,
                    "history_count": len(history["results"]),
                    "similar_issues_count": len(similar_issues["results"]),
                }

        # Test the support bot
        bot = SupportBot()

        # Handle some tickets
        result1 = bot.handle_ticket("customer123", "Login issues with password reset")
        assert result1["customer_id"] == "customer123"
        assert result1["history_count"] >= 0

        result2 = bot.handle_ticket("customer123", "Still having login problems")
        assert result2["customer_id"] == "customer123"
        # Should now have history from previous ticket
        assert result2["history_count"] >= 1

        # Test similar issue detection
        result3 = bot.handle_ticket("customer456", "Cannot reset my password")
        assert (
            result3["similar_issues_count"] >= 1
        )  # Should find password-related issues

    def test_configuration_examples(self):
        """Test configuration examples from README."""
        # Custom configuration example
        config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "config_test_user"},
        )

        memory = Memory(config=config)

        # Test that configuration is applied
        assert memory.config.storage.type == "file"
        assert memory.default_user == "config_test_user"

        # Test basic functionality with custom config
        result = memory.add("Configuration test memory")
        assert isinstance(result, dict)

        search_result = memory.search("configuration")
        assert len(search_result["results"]) > 0

    def test_api_reference_examples(self):
        """Test Memory class API examples from README."""
        config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "api_test_user"},
        )

        memory = Memory(config=config)

        # Test all main API methods mentioned in README

        # Memory operations
        result = memory.add(
            "API test memory",
            tags="api,test",
            people_mentioned="TestUser",
            topic_category="testing",
        )
        assert isinstance(result, dict)

        results = memory.search("API test", limit=10)
        assert "results" in results
        assert isinstance(results["results"], list)

        memories = memory.get_all(limit=100)
        assert "results" in memories
        assert len(memories["results"]) >= 1

        # Advanced search methods
        tag_results = memory.search_by_tags(["api", "test"], match_all=True)
        assert "results" in tag_results

        people_results = memory.search_by_people(["TestUser"])
        assert "results" in people_results

        # Utility methods
        config_info = memory.get_config()
        assert isinstance(config_info, dict)

        health = memory.health_check()
        assert "status" in health
        assert isinstance(health["status"], str)

        # Test context manager usage
        with Memory(config=config) as mem:
            result = mem.add("Context manager test")
            assert isinstance(result, dict)

    def test_installation_modes_compatibility(self):
        """Test that basic installation (no optional deps) still works."""
        # This tests the "zero dependencies" promise from README

        config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "basic_user"},
        )

        # Should work with just core dependencies
        memory = Memory(config=config)

        # Basic functionality should work
        result = memory.add("Basic installation test")
        assert isinstance(result, dict)

        search_result = memory.search("basic")
        assert "results" in search_result

        all_memories = memory.get_all()
        assert "results" in all_memories
        assert len(all_memories["results"]) >= 1


class TestAdvancedExamples:
    """Test more advanced usage patterns."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_memory_with_rich_metadata(self):
        """Test memory storage with comprehensive metadata."""
        config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "metadata_user"},
        )

        memory = Memory(config=config)

        # Add memory with all possible metadata
        result = memory.add(
            "Comprehensive team retrospective meeting covered sprint velocity, "
            "blockers, and action items for next quarter",
            tags="work,meeting,retrospective,planning",
            people_mentioned="Sarah,Mike,Jennifer,David",
            topic_category="project_management",
            metadata={
                "meeting_type": "retrospective",
                "duration": "2 hours",
                "location": "Conference Room A",
                "action_items": 5,
                "priority": "high",
            },
        )

        assert isinstance(result, dict)

        # Test that we can search using different aspects of the metadata
        tag_search = memory.search_by_tags(
            ["retrospective", "planning"], match_all=True
        )
        assert len(tag_search["results"]) > 0

        people_search = memory.search_by_people(["Sarah", "Mike"])
        assert len(people_search["results"]) > 0

        semantic_search = memory.search("sprint velocity blockers")
        assert len(semantic_search["results"]) > 0

    def test_multi_user_scenario(self):
        """Test realistic multi-user scenario."""
        # Create configurations for different users
        configs = {
            "project_manager": InMemoryConfig(
                storage={"type": "file", "path": str(self.temp_dir)},
                auth={"type": "simple", "default_user": "pm_user"},
            ),
            "developer": InMemoryConfig(
                storage={"type": "file", "path": str(self.temp_dir)},
                auth={"type": "simple", "default_user": "dev_user"},
            ),
            "designer": InMemoryConfig(
                storage={"type": "file", "path": str(self.temp_dir)},
                auth={"type": "simple", "default_user": "design_user"},
            ),
        }

        # Each user adds their own memories
        with Memory(config=configs["project_manager"]) as pm_memory:
            pm_memory.add(
                "Sprint planning meeting scheduled for Monday with dev team",
                tags="planning,sprint,management",
                people_mentioned="dev_team",
                topic_category="project_management",
            )

        with Memory(config=configs["developer"]) as dev_memory:
            dev_memory.add(
                "Fixed authentication bug in user login module",
                tags="development,bug_fix,authentication",
                topic_category="development",
            )

        with Memory(config=configs["designer"]) as design_memory:
            design_memory.add(
                "Created new wireframes for mobile app dashboard",
                tags="design,wireframes,mobile,ui",
                topic_category="design",
            )

        # Verify user isolation
        with Memory(config=configs["project_manager"]) as pm_memory:
            pm_results = pm_memory.search("sprint planning")
            assert len(pm_results["results"]) > 0

            # Should not find developer's memories
            dev_results = pm_memory.search("authentication bug")
            assert len(dev_results["results"]) == 0

        with Memory(config=configs["developer"]) as dev_memory:
            dev_results = dev_memory.search("authentication")
            assert len(dev_results["results"]) > 0

            # Should not find PM's memories
            pm_results = dev_memory.search("sprint planning")
            assert len(pm_results["results"]) == 0

    def test_temporal_and_contextual_search(self):
        """Test advanced search capabilities."""
        config = InMemoryConfig(
            storage={"type": "file", "path": str(self.temp_dir)},
            auth={"type": "simple", "default_user": "search_test_user"},
        )

        memory = Memory(config=config)

        # Add memories with different contexts
        memories = [
            {
                "content": "Daily standup with team about sprint progress",
                "tags": "work,standup,daily",
                "people": "team",
                "category": "meeting",
            },
            {
                "content": "Weekend hiking trip to Mount Wilson with friends",
                "tags": "personal,outdoor,recreation",
                "people": "friends",
                "category": "personal",
            },
            {
                "content": "Code review session for new feature implementation",
                "tags": "work,code_review,development",
                "people": "development_team",
                "category": "development",
            },
            {
                "content": "Birthday dinner at Italian restaurant with family",
                "tags": "personal,celebration,food",
                "people": "family",
                "category": "personal",
            },
        ]

        for mem in memories:
            memory.add(
                mem["content"],
                tags=mem["tags"],
                people_mentioned=mem["people"],
                topic_category=mem["category"],
            )

        # Test different search strategies

        # Semantic search
        work_context = memory.search("team meeting development")
        assert len(work_context["results"]) >= 2  # Should find work-related memories

        # Tag-based filtering
        personal_memories = memory.search_by_tags(["personal"])
        assert len(personal_memories["results"]) >= 2

        work_memories = memory.search_by_tags(["work"])
        assert len(work_memories["results"]) >= 2

        # People-based search
        team_memories = memory.search_by_people(["team"])
        assert len(team_memories["results"]) >= 1

        # Combined search
        work_team_results = memory.search("progress", tags=["work"])
        assert len(work_team_results["results"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__])
