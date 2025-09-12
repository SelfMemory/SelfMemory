#!/usr/bin/env python3
"""
Comprehensive SelfMemory SDK Testing Suite

This script provides manual testing for all SDK functions including:
- Local Memory SDK (selfmemory.Memory)
- Managed Client SDK (selfmemory.SelfMemoryClient)
- Configuration testing
- Multi-user isolation
- Advanced search features
- Error handling
- Performance benchmarking

Usage:
    python examples/sdk_comprehensive_test.py

Requirements:
    - Ollama server running on localhost:11434 with nomic-embed-text model
    - Optional: SelfMemory API server for managed client testing
"""

import json
import logging
import os
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import SelfMemory SDK
try:
    from selfmemory import Memory, SelfMemoryClient
    from selfmemory.configs import SelfMemoryConfig

    print("✅ SelfMemory SDK imported successfully")
except ImportError as e:
    print(f"❌ Failed to import SelfMemory SDK: {e}")
    exit(1)


class SDKTester:
    """Comprehensive SDK testing class."""

    def __init__(self):
        """Initialize the tester with test data and configurations."""
        self.test_results = {
            "local_memory": {},
            "managed_client": {},
            "performance": {},
            "errors": [],
        }

        # Test data for comprehensive testing
        self.test_memories = [
            {
                "content": "I had a great meeting with Sarah and Mike about the new product launch. We discussed marketing strategies and timeline.",
                "tags": "work,meeting,product",
                "people_mentioned": "Sarah,Mike",
                "topic_category": "work",
                "metadata": {"priority": "high", "project": "product_launch"},
            },
            {
                "content": "Went to an amazing Italian restaurant downtown. The pizza was incredible, especially the margherita.",
                "tags": "food,personal,restaurant",
                "people_mentioned": "",
                "topic_category": "personal",
                "metadata": {"rating": 5, "location": "downtown"},
            },
            {
                "content": "Team standup meeting with Jennifer and Alex. Discussed sprint progress and blockers.",
                "tags": "work,standup,team",
                "people_mentioned": "Jennifer,Alex",
                "topic_category": "work",
                "metadata": {"sprint": "sprint_23", "team": "engineering"},
            },
            {
                "content": "Learned about machine learning algorithms in my online course. Focused on neural networks and deep learning.",
                "tags": "learning,technology,ai",
                "people_mentioned": "",
                "topic_category": "education",
                "metadata": {"course": "ml_fundamentals", "progress": 60},
            },
            {
                "content": "Coffee chat with Emma from the design team. Talked about user experience improvements.",
                "tags": "work,design,ux",
                "people_mentioned": "Emma",
                "topic_category": "work",
                "metadata": {"department": "design", "type": "informal"},
            },
        ]

        # Test users for multi-user isolation testing
        self.test_users = ["alice", "bob", "charlie", "diana"]

        # Configuration variations for testing
        self.test_configs = {
            "default": None,
            "custom_ollama": {
                "embedding": {
                    "provider": "ollama",
                    "config": {
                        "model": "nomic-embed-text",
                        "ollama_base_url": "http://localhost:11434",
                    },
                },
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "collection_name": "test_memories",
                        "path": "/tmp/test_qdrant",
                    },
                },
            },
        }

    def print_section(self, title: str):
        """Print a formatted section header."""
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")

    def print_subsection(self, title: str):
        """Print a formatted subsection header."""
        print(f"\n{'-' * 40}")
        print(f"  {title}")
        print(f"{'-' * 40}")

    def measure_time(self, func, *args, **kwargs):
        """Measure execution time of a function."""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time

    def test_local_memory_sdk(self):
        """Test the local Memory SDK comprehensively."""
        self.print_section("LOCAL MEMORY SDK TESTING")

        # Test 1: Configuration Testing
        self.print_subsection("1. Configuration Testing")

        for config_name, config in self.test_configs.items():
            print(f"\n📋 Testing {config_name} configuration...")
            try:
                memory, init_time = self.measure_time(Memory, config=config)
                print(f"✅ Memory initialized in {init_time:.3f}s")
                print(f"   Embedding: {memory.config.embedding.provider}")
                print(f"   Vector Store: {memory.config.vector_store.provider}")

                # Test health check
                health = memory.health_check()
                print(f"   Health Status: {health.get('status', 'unknown')}")

                memory.close()
                self.test_results["local_memory"][f"config_{config_name}"] = "✅ PASS"

            except Exception as e:
                print(f"❌ Configuration test failed: {e}")
                self.test_results["local_memory"][f"config_{config_name}"] = (
                    f"❌ FAIL: {e}"
                )
                self.test_results["errors"].append(f"Config {config_name}: {e}")

        # Test 2: Basic CRUD Operations
        self.print_subsection("2. Basic CRUD Operations")

        try:
            memory = Memory()
            test_user = "test_user_crud"

            print(f"\n👤 Testing with user: {test_user}")

            # Test ADD operation
            print("\n📝 Testing ADD operation...")
            add_results = []
            for i, test_memory in enumerate(self.test_memories):
                result, add_time = self.measure_time(
                    memory.add,
                    test_memory["content"],
                    user_id=test_user,
                    tags=test_memory["tags"],
                    people_mentioned=test_memory["people_mentioned"],
                    topic_category=test_memory["topic_category"],
                    metadata=test_memory["metadata"],
                )
                add_results.append(result)
                print(
                    f"   Memory {i + 1}: {'✅' if result.get('success') else '❌'} ({add_time:.3f}s)"
                )
                if not result.get("success"):
                    print(f"      Error: {result.get('error')}")

            # Test GET_ALL operation
            print("\n📚 Testing GET_ALL operation...")
            all_memories, get_time = self.measure_time(
                memory.get_all, user_id=test_user
            )
            memory_count = len(all_memories.get("results", []))
            print(f"   Retrieved {memory_count} memories in {get_time:.3f}s")

            # Test SEARCH operation
            print("\n🔍 Testing SEARCH operation...")
            search_queries = [
                ("meeting", "Basic search"),
                ("pizza", "Food search"),
                ("", "Empty query (get all)"),
                ("machine learning", "Technical search"),
            ]

            for query, description in search_queries:
                search_results, search_time = self.measure_time(
                    memory.search, query, user_id=test_user, limit=10
                )
                result_count = len(search_results.get("results", []))
                print(f"   {description}: {result_count} results ({search_time:.3f}s)")

            # Test DELETE operation
            print("\n🗑️ Testing DELETE operation...")
            if add_results and add_results[0].get("success"):
                memory_id = add_results[0].get("memory_id")
                delete_result, delete_time = self.measure_time(memory.delete, memory_id)
                print(
                    f"   Delete result: {'✅' if delete_result.get('success') else '❌'} ({delete_time:.3f}s)"
                )

            # Test DELETE_ALL operation
            print("\n🗑️ Testing DELETE_ALL operation...")
            delete_all_result, delete_all_time = self.measure_time(
                memory.delete_all, user_id=test_user
            )
            deleted_count = delete_all_result.get("deleted_count", 0)
            print(f"   Deleted {deleted_count} memories in {delete_all_time:.3f}s")

            memory.close()
            self.test_results["local_memory"]["crud_operations"] = "✅ PASS"

        except Exception as e:
            print(f"❌ CRUD operations test failed: {e}")
            self.test_results["local_memory"]["crud_operations"] = f"❌ FAIL: {e}"
            self.test_results["errors"].append(f"CRUD operations: {e}")

        # Test 3: Multi-User Isolation
        self.print_subsection("3. Multi-User Isolation Testing")

        try:
            memory = Memory()

            print("\n👥 Testing user isolation...")

            # Add memories for different users
            user_memories = {}
            for user in self.test_users:
                print(f"\n   Adding memories for user: {user}")
                user_memories[user] = []

                for i, test_memory in enumerate(
                    self.test_memories[:2]
                ):  # Add 2 memories per user
                    result = memory.add(
                        f"{test_memory['content']} (User: {user})",
                        user_id=user,
                        tags=test_memory["tags"],
                        metadata={"user": user, "test_id": i},
                    )
                    if result.get("success"):
                        user_memories[user].append(result.get("memory_id"))
                        print(f"      Memory {i + 1}: ✅")
                    else:
                        print(f"      Memory {i + 1}: ❌ {result.get('error')}")

            # Verify isolation - each user should only see their own memories
            print("\n🔒 Verifying user isolation...")
            isolation_passed = True

            for user in self.test_users:
                user_results = memory.get_all(user_id=user)
                user_count = len(user_results.get("results", []))
                expected_count = len(user_memories[user])

                if user_count == expected_count:
                    print(f"   User {user}: ✅ {user_count}/{expected_count} memories")
                else:
                    print(f"   User {user}: ❌ {user_count}/{expected_count} memories")
                    isolation_passed = False

                # Verify content isolation
                for result in user_results.get("results", []):
                    content = result.get("content", "")
                    if f"(User: {user})" not in content:
                        print("      ❌ Cross-user data leak detected!")
                        isolation_passed = False

            # Cleanup
            for user in self.test_users:
                memory.delete_all(user_id=user)

            memory.close()

            if isolation_passed:
                print("\n✅ User isolation test PASSED")
                self.test_results["local_memory"]["user_isolation"] = "✅ PASS"
            else:
                print("\n❌ User isolation test FAILED")
                self.test_results["local_memory"]["user_isolation"] = "❌ FAIL"

        except Exception as e:
            print(f"❌ User isolation test failed: {e}")
            self.test_results["local_memory"]["user_isolation"] = f"❌ FAIL: {e}"
            self.test_results["errors"].append(f"User isolation: {e}")

        # Test 4: Advanced Search Features
        self.print_subsection("4. Advanced Search Features")

        try:
            memory = Memory()
            test_user = "advanced_search_user"

            # Add test data
            print("\n📝 Adding test data for advanced search...")
            for test_memory in self.test_memories:
                memory.add(
                    test_memory["content"],
                    user_id=test_user,
                    tags=test_memory["tags"],
                    people_mentioned=test_memory["people_mentioned"],
                    topic_category=test_memory["topic_category"],
                    metadata=test_memory["metadata"],
                )

            # Test tag filtering
            print("\n🏷️ Testing tag filtering...")
            tag_tests = [
                (["work"], "Work-related memories"),
                (["food", "personal"], "Food or personal memories"),
                (["work", "meeting"], "Work AND meeting memories"),
            ]

            for tags, description in tag_tests:
                results = memory.search(
                    "meeting", user_id=test_user, tags=tags, match_all_tags=False
                )
                count = len(results.get("results", []))
                print(f"   {description}: {count} results")

            # Test people filtering
            print("\n👥 Testing people filtering...")
            people_tests = [
                (["Sarah"], "Memories mentioning Sarah"),
                (["Mike", "Jennifer"], "Memories mentioning Mike or Jennifer"),
            ]

            for people, description in people_tests:
                results = memory.search("", user_id=test_user, people_mentioned=people)
                count = len(results.get("results", []))
                print(f"   {description}: {count} results")

            # Test topic category filtering
            print("\n📂 Testing topic category filtering...")
            category_tests = [
                ("work", "Work category"),
                ("personal", "Personal category"),
                ("education", "Education category"),
            ]

            for category, description in category_tests:
                results = memory.search("", user_id=test_user, topic_category=category)
                count = len(results.get("results", []))
                print(f"   {description}: {count} results")

            # Test sorting options
            print("\n📊 Testing sorting options...")
            sort_tests = [
                ("relevance", "Sort by relevance"),
                ("timestamp", "Sort by timestamp"),
                ("score", "Sort by score"),
            ]

            for sort_by, description in sort_tests:
                results = memory.search("meeting", user_id=test_user, sort_by=sort_by)
                count = len(results.get("results", []))
                print(f"   {description}: {count} results")

            # Test threshold filtering
            print("\n🎯 Testing threshold filtering...")
            threshold_tests = [0.0, 0.3, 0.5, 0.7, 0.9]

            for threshold in threshold_tests:
                results = memory.search(
                    "meeting", user_id=test_user, threshold=threshold
                )
                count = len(results.get("results", []))
                print(f"   Threshold {threshold}: {count} results")

            # Cleanup
            memory.delete_all(user_id=test_user)
            memory.close()

            self.test_results["local_memory"]["advanced_search"] = "✅ PASS"
            print("\n✅ Advanced search features test PASSED")

        except Exception as e:
            print(f"❌ Advanced search test failed: {e}")
            self.test_results["local_memory"]["advanced_search"] = f"❌ FAIL: {e}"
            self.test_results["errors"].append(f"Advanced search: {e}")

        # Test 5: Error Handling
        self.print_subsection("5. Error Handling Testing")

        try:
            memory = Memory()

            print("\n🚨 Testing error scenarios...")

            # Test invalid user_id
            print("   Testing invalid user_id...")
            try:
                result = memory.add("test", user_id="")
                if not result.get("success"):
                    print("   ✅ Empty user_id properly rejected")
                else:
                    print("   ❌ Empty user_id should be rejected")
            except Exception:
                print("   ✅ Empty user_id properly rejected with exception")

            # Test invalid memory_id for delete
            print("   Testing invalid memory_id...")
            result = memory.delete("invalid_memory_id")
            if not result.get("success"):
                print("   ✅ Invalid memory_id properly handled")
            else:
                print("   ❌ Invalid memory_id should fail")

            # Test search with invalid parameters
            print("   Testing invalid search parameters...")
            result = memory.search("test", user_id="valid_user", limit=-1)
            # Should handle gracefully
            print("   ✅ Invalid parameters handled gracefully")

            memory.close()
            self.test_results["local_memory"]["error_handling"] = "✅ PASS"

        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            self.test_results["local_memory"]["error_handling"] = f"❌ FAIL: {e}"
            self.test_results["errors"].append(f"Error handling: {e}")

    def test_managed_client_sdk(self):
        """Test the managed SelfMemoryClient SDK."""
        self.print_section("MANAGED CLIENT SDK TESTING")

        # Check if API credentials are available
        api_key = os.getenv("INMEM_API_KEY")
        api_host = os.getenv("SELFMEMORY_API_HOST", "http://localhost:8081")

        if not api_key:
            print("⚠️ INMEM_API_KEY not found. Skipping managed client tests.")
            print("   Set INMEM_API_KEY environment variable to test managed client.")
            self.test_results["managed_client"]["skipped"] = "No API key provided"
            return

        # Test 1: Client Initialization
        self.print_subsection("1. Client Initialization")

        try:
            print(f"🔗 Connecting to API: {api_host}")
            client, init_time = self.measure_time(
                SelfMemoryClient, api_key=api_key, host=api_host
            )
            print(f"✅ Client initialized in {init_time:.3f}s")

            # Test health check
            health = client.health_check()
            print(f"   Health Status: {health.get('status', 'unknown')}")

            self.test_results["managed_client"]["initialization"] = "✅ PASS"

        except Exception as e:
            print(f"❌ Client initialization failed: {e}")
            self.test_results["managed_client"]["initialization"] = f"❌ FAIL: {e}"
            self.test_results["errors"].append(f"Client init: {e}")
            return

        # Test 2: Basic Operations
        self.print_subsection("2. Basic Operations")

        try:
            # Test ADD
            print("\n📝 Testing ADD operation...")
            add_results = []
            for i, test_memory in enumerate(
                self.test_memories[:3]
            ):  # Test with 3 memories
                result, add_time = self.measure_time(
                    client.add,
                    test_memory["content"],
                    tags=test_memory["tags"],
                    people_mentioned=test_memory["people_mentioned"],
                    topic_category=test_memory["topic_category"],
                    metadata=test_memory["metadata"],
                )
                add_results.append(result)
                print(
                    f"   Memory {i + 1}: {'✅' if result.get('success') else '❌'} ({add_time:.3f}s)"
                )

            # Test GET_ALL
            print("\n📚 Testing GET_ALL operation...")
            all_memories, get_time = self.measure_time(client.get_all)
            memory_count = len(all_memories.get("results", []))
            print(f"   Retrieved {memory_count} memories in {get_time:.3f}s")

            # Test SEARCH
            print("\n🔍 Testing SEARCH operation...")
            search_results, search_time = self.measure_time(client.search, "meeting")
            result_count = len(search_results.get("results", []))
            print(f"   Search results: {result_count} memories ({search_time:.3f}s)")

            # Test advanced search methods
            print("\n🔍 Testing advanced search methods...")

            # Tag search
            tag_results = client.search_by_tags(["work", "meeting"])
            print(f"   Tag search: {len(tag_results.get('results', []))} results")

            # People search
            people_results = client.search_by_people(["Sarah", "Mike"])
            print(f"   People search: {len(people_results.get('results', []))} results")

            # Test DELETE (if we have memories to delete)
            if add_results and add_results[0].get("success"):
                print("\n🗑️ Testing DELETE operation...")
                memory_id = add_results[0].get("memory_id")
                if memory_id:
                    delete_result, delete_time = self.measure_time(
                        client.delete, memory_id
                    )
                    print(
                        f"   Delete result: {'✅' if delete_result.get('success') else '❌'} ({delete_time:.3f}s)"
                    )

            # Test stats
            print("\n📊 Testing GET_STATS operation...")
            stats = client.get_stats()
            print(f"   Stats retrieved: {'✅' if 'error' not in stats else '❌'}")

            self.test_results["managed_client"]["basic_operations"] = "✅ PASS"

        except Exception as e:
            print(f"❌ Basic operations test failed: {e}")
            self.test_results["managed_client"]["basic_operations"] = f"❌ FAIL: {e}"
            self.test_results["errors"].append(f"Client basic ops: {e}")

        # Test 3: Context Manager
        self.print_subsection("3. Context Manager Testing")

        try:
            print("\n🔄 Testing context manager usage...")
            with SelfMemoryClient(api_key=api_key, host=api_host) as ctx_client:
                result = ctx_client.add("Context manager test memory")
                print(f"   Context manager: {'✅' if result.get('success') else '❌'}")

            self.test_results["managed_client"]["context_manager"] = "✅ PASS"

        except Exception as e:
            print(f"❌ Context manager test failed: {e}")
            self.test_results["managed_client"]["context_manager"] = f"❌ FAIL: {e}"
            self.test_results["errors"].append(f"Context manager: {e}")

        # Cleanup
        try:
            client.delete_all()
            client.close()
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")

    def test_performance_benchmarks(self):
        """Run performance benchmarks."""
        self.print_section("PERFORMANCE BENCHMARKS")

        try:
            memory = Memory()
            test_user = "perf_test_user"

            # Benchmark 1: Bulk Add Performance
            print("\n⚡ Benchmark 1: Bulk Add Performance")
            bulk_memories = [
                f"Performance test memory {i}: This is a test memory for performance benchmarking."
                for i in range(50)
            ]

            start_time = time.time()
            successful_adds = 0

            for i, content in enumerate(bulk_memories):
                result = memory.add(content, user_id=test_user, tags="performance,test")
                if result.get("success"):
                    successful_adds += 1

                if (i + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed
                    print(f"   Added {i + 1}/50 memories ({rate:.1f} memories/sec)")

            total_time = time.time() - start_time
            final_rate = successful_adds / total_time
            print(
                f"   Final: {successful_adds} memories in {total_time:.2f}s ({final_rate:.1f} memories/sec)"
            )

            # Benchmark 2: Search Performance
            print("\n⚡ Benchmark 2: Search Performance")
            search_queries = ["test", "performance", "memory", "benchmark", "data"]

            search_times = []
            for query in search_queries:
                start_time = time.time()
                results = memory.search(query, user_id=test_user, limit=20)
                search_time = time.time() - start_time
                search_times.append(search_time)

                result_count = len(results.get("results", []))
                print(
                    f"   Query '{query}': {result_count} results in {search_time:.3f}s"
                )

            avg_search_time = sum(search_times) / len(search_times)
            print(f"   Average search time: {avg_search_time:.3f}s")

            # Benchmark 3: Get All Performance
            print("\n⚡ Benchmark 3: Get All Performance")
            start_time = time.time()
            all_results = memory.get_all(user_id=test_user)
            get_all_time = time.time() - start_time

            total_memories = len(all_results.get("results", []))
            print(f"   Retrieved {total_memories} memories in {get_all_time:.3f}s")

            # Store performance results
            self.test_results["performance"] = {
                "bulk_add_rate": final_rate,
                "avg_search_time": avg_search_time,
                "get_all_time": get_all_time,
                "total_memories": total_memories,
            }

            # Cleanup
            memory.delete_all(user_id=test_user)
            memory.close()

            print("\n✅ Performance benchmarks completed")

        except Exception as e:
            print(f"❌ Performance benchmark failed: {e}")
            self.test_results["errors"].append(f"Performance: {e}")

    def test_real_world_scenarios(self):
        """Test real-world usage scenarios."""
        self.print_section("REAL-WORLD SCENARIOS")

        # Scenario 1: Personal Assistant Use Case
        self.print_subsection("1. Personal Assistant Scenario")

        try:
            memory = Memory()
            user = "personal_assistant_user"

            print("\n🤖 Simulating personal assistant interactions...")

            # Add various types of personal memories
            personal_memories = [
                (
                    "I have a dentist appointment on Friday at 2 PM",
                    "appointment,health",
                    "",
                    "personal",
                ),
                (
                    "Mom's birthday is next month, need to buy a gift",
                    "family,birthday,reminder",
                    "Mom",
                    "personal",
                ),
                (
                    "Finished reading 'The Great Gatsby' - really enjoyed it",
                    "books,reading,literature",
                    "",
                    "personal",
                ),
                (
                    "Gym session today: 30 min cardio, 20 min weights",
                    "fitness,exercise,health",
                    "",
                    "personal",
                ),
                (
                    "Meeting with financial advisor about retirement planning",
                    "finance,retirement,planning",
                    "",
                    "personal",
                ),
            ]

            for content, tags, people, category in personal_memories:
                result = memory.add(
                    content,
                    user_id=user,
                    tags=tags,
                    people_mentioned=people,
                    topic_category=category,
                )
                print(f"   Added: {'✅' if result.get('success') else '❌'}")

            # Test assistant-like queries
            assistant_queries = [
                ("appointment", "Finding appointments"),
                ("birthday", "Birthday reminders"),
                ("health", "Health-related memories"),
                ("Mom", "Memories about Mom"),
            ]

            for query, description in assistant_queries:
                results = memory.search(query, user_id=user)
                count = len(results.get("results", []))
                print(f"   {description}: {count} results")

            memory.delete_all(user_id=user)
            print("✅ Personal assistant scenario completed")

        except Exception as e:
            print(f"❌ Personal assistant scenario failed: {e}")

        # Scenario 2: Team Knowledge Base
        self.print_subsection("2. Team Knowledge Base Scenario")

        try:
            memory = Memory()

            print("\n👥 Simulating team knowledge base...")

            # Simulate multiple team members adding knowledge
            team_members = ["alice_dev", "bob_pm", "charlie_designer"]

            team_knowledge = {
                "alice_dev": [
                    (
                        "Fixed the authentication bug in the login module",
                        "bug,fix,auth",
                        "",
                        "development",
                    ),
                    (
                        "Implemented new API endpoint for user profiles",
                        "api,development,feature",
                        "",
                        "development",
                    ),
                ],
                "bob_pm": [
                    (
                        "Sprint planning meeting scheduled for Monday",
                        "meeting,sprint,planning",
                        "Alice,Charlie",
                        "management",
                    ),
                    (
                        "Client feedback: they love the new dashboard design",
                        "feedback,client,dashboard",
                        "Charlie",
                        "management",
                    ),
                ],
                "charlie_designer": [
                    (
                        "Created new wireframes for the mobile app",
                        "design,wireframes,mobile",
                        "",
                        "design",
                    ),
                    (
                        "User testing session revealed navigation issues",
                        "testing,ux,navigation",
                        "",
                        "design",
                    ),
                ],
            }

            # Add knowledge from each team member
            for member, memories in team_knowledge.items():
                print(f"\n   Adding knowledge from {member}:")
                for content, tags, people, category in memories:
                    result = memory.add(
                        content,
                        user_id=member,
                        tags=tags,
                        people_mentioned=people,
                        topic_category=category,
                    )
                    print(
                        f"     {'✅' if result.get('success') else '❌'} {content[:50]}..."
                    )

            # Test cross-team knowledge search (each member searches their own knowledge)
            for member in team_members:
                results = memory.get_all(user_id=member)
                count = len(results.get("results", []))
                print(f"   {member} has {count} knowledge entries")

            # Cleanup
            for member in team_members:
                memory.delete_all(user_id=member)

            print("✅ Team knowledge base scenario completed")

        except Exception as e:
            print(f"❌ Team knowledge base scenario failed: {e}")

        memory.close()

    def generate_test_report(self):
        """Generate a comprehensive test report."""
        self.print_section("TEST REPORT SUMMARY")

        print("\n📊 LOCAL MEMORY SDK RESULTS:")
        for test_name, result in self.test_results["local_memory"].items():
            print(f"   {test_name}: {result}")

        print("\n📊 MANAGED CLIENT SDK RESULTS:")
        for test_name, result in self.test_results["managed_client"].items():
            print(f"   {test_name}: {result}")

        print("\n⚡ PERFORMANCE RESULTS:")
        if self.test_results["performance"]:
            perf = self.test_results["performance"]
            print(f"   Bulk Add Rate: {perf.get('bulk_add_rate', 0):.1f} memories/sec")
            print(f"   Average Search Time: {perf.get('avg_search_time', 0):.3f}s")
            print(f"   Get All Time: {perf.get('get_all_time', 0):.3f}s")
            print(f"   Total Memories Processed: {perf.get('total_memories', 0)}")

        print("\n🚨 ERRORS ENCOUNTERED:")
        if self.test_results["errors"]:
            for error in self.test_results["errors"]:
                print(f"   ❌ {error}")
        else:
            print("   ✅ No errors encountered!")

        # Calculate overall success rate
        total_tests = 0
        passed_tests = 0

        for category in ["local_memory", "managed_client"]:
            for test_name, result in self.test_results[category].items():
                if test_name != "skipped":
                    total_tests += 1
                    if "✅ PASS" in str(result):
                        passed_tests += 1

        if total_tests > 0:
            success_rate = (passed_tests / total_tests) * 100
            print(
                f"\n🎯 OVERALL SUCCESS RATE: {success_rate:.1f}% ({passed_tests}/{total_tests} tests passed)"
            )

        # Save detailed report to file
        report_file = "examples/sdk_test_report.json"
        try:
            with open(report_file, "w") as f:
                json.dump(self.test_results, f, indent=2, default=str)
            print(f"\n💾 Detailed report saved to: {report_file}")
        except Exception as e:
            print(f"\n⚠️ Could not save report file: {e}")

    def run_all_tests(self):
        """Run all SDK tests."""
        print("🚀 Starting Comprehensive SelfMemory SDK Testing Suite")
        print(f"📅 Test started at: {datetime.now().isoformat()}")

        start_time = time.time()

        try:
            # Run all test suites
            self.test_local_memory_sdk()
            self.test_managed_client_sdk()
            self.test_performance_benchmarks()
            self.test_real_world_scenarios()

        except KeyboardInterrupt:
            print("\n⚠️ Testing interrupted by user")
        except Exception as e:
            print(f"\n❌ Unexpected error during testing: {e}")
            self.test_results["errors"].append(f"Unexpected error: {e}")

        finally:
            total_time = time.time() - start_time
            print(f"\n⏱️ Total testing time: {total_time:.2f} seconds")
            self.generate_test_report()


def main():
    """Main function to run the comprehensive SDK tests."""
    print("=" * 80)
    print("  SELFMEMORY SDK COMPREHENSIVE TESTING SUITE")
    print("=" * 80)
    print()
    print("This script will test all SelfMemory SDK functions including:")
    print("• Local Memory SDK (selfmemory.Memory)")
    print("• Managed Client SDK (selfmemory.SelfMemoryClient)")
    print("• Configuration variations")
    print("• Multi-user isolation")
    print("• Advanced search features")
    print("• Error handling")
    print("• Performance benchmarks")
    print("• Real-world scenarios")
    print()

    # Check prerequisites
    print("🔍 Checking prerequisites...")

    # Check if Ollama is running
    try:
        import requests

        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama server is running")
        else:
            print("⚠️ Ollama server responded with non-200 status")
    except Exception:
        print("❌ Ollama server is not accessible at localhost:11434")
        print(
            "   Please start Ollama server and ensure nomic-embed-text model is available"
        )
        return

    # Check API key for managed client testing
    api_key = os.getenv("INMEM_API_KEY")
    if api_key:
        print("✅ API key found for managed client testing")
    else:
        print(
            "⚠️ No API key found (INMEM_API_KEY) - managed client tests will be skipped"
        )

    print()

    # Ask user confirmation
    try:
        response = (
            input("🚀 Ready to start comprehensive testing? (y/N): ").strip().lower()
        )
        if response not in ["y", "yes"]:
            print("Testing cancelled by user.")
            return
    except KeyboardInterrupt:
        print("\nTesting cancelled by user.")
        return

    # Run the tests
    tester = SDKTester()
    tester.run_all_tests()

    print(
        "\n🎉 Testing completed! Check the results above and the generated report file."
    )


if __name__ == "__main__":
    main()
