#!/usr/bin/env python3
"""
SelfMemory Client Example - Managed Service Usage

This example demonstrates how to use the SelfMemoryClient for the managed/hosted
SelfMemory service. The client connects to a remote API server instead of running
everything locally.

Key Features Demonstrated:
- API authentication and connection
- Adding memories with rich metadata
- Various search methods (basic, tags, people, temporal)
- Error handling and best practices
- Context manager usage
- Real-world scenarios

Prerequisites:
- Valid SelfMemory API key (set INMEM_API_KEY environment variable)
- Access to SelfMemory API server

Usage:
    # Set your API key
    export INMEM_API_KEY="your_api_key_here"

    # Run the example
    python examples/selfmemory_client_example.py

For local development, you can also run the server locally:
    cd server && python main.py
    export SELFMEMORY_API_HOST="http://localhost:8081"
"""

import os
import time
from datetime import datetime

# Import SelfMemory Client
try:
    from selfmemory import SelfMemoryClient

    print("✅ SelfMemory Client imported successfully")
except ImportError as e:
    print(f"❌ Failed to import SelfMemory Client: {e}")
    print("Please install the selfmemory package: pip install selfmemory")
    exit(1)


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_subsection(title: str):
    """Print a formatted subsection header."""
    print(f"\n{'-' * 40}")
    print(f"  {title}")
    print(f"{'-' * 40}")


def basic_client_usage():
    """Demonstrate basic SelfMemoryClient usage."""
    print_section("BASIC SELFMEMORY CLIENT USAGE")

    # Get API credentials
    api_key = os.getenv("INMEM_API_KEY")
    api_host = os.getenv("SELFMEMORY_API_HOST")  # Optional, defaults to production

    if not api_key:
        print("❌ INMEM_API_KEY environment variable not set!")
        print("Please set your API key: export INMEM_API_KEY='your_api_key_here'")
        return False

    print(f"🔑 Using API key: {api_key[:8]}...")
    if api_host:
        print(f"🌐 Using custom API host: {api_host}")

    try:
        # Initialize the client
        print("\n1. Initializing SelfMemory Client...")
        if api_host:
            client = SelfMemoryClient(api_key=api_key, host=api_host)
        else:
            client = SelfMemoryClient(api_key=api_key)

        print("✅ Client initialized successfully")
        print(f"   Connected to: {client.host}")

        # Test connection with health check
        print("\n2. Testing connection...")
        health = client.health_check()
        print(f"   Health Status: {health.get('status', 'unknown')}")

        # Add some test memories
        print("\n3. Adding memories...")
        test_memories = [
            {
                "content": "Had a productive team meeting about the Q4 roadmap with Sarah and Mike",
                "tags": "work,meeting,planning",
                "people_mentioned": "Sarah,Mike",
                "topic_category": "work",
                "metadata": {"priority": "high", "quarter": "Q4"},
            },
            {
                "content": "Discovered an amazing new Italian restaurant downtown - the pasta was incredible!",
                "tags": "food,restaurant,personal",
                "people_mentioned": "",
                "topic_category": "personal",
                "metadata": {"rating": 5, "cuisine": "Italian", "location": "downtown"},
            },
            {
                "content": "Completed the machine learning course on neural networks. Great insights on deep learning.",
                "tags": "learning,ai,technology",
                "people_mentioned": "",
                "topic_category": "education",
                "metadata": {"course": "ML Fundamentals", "completion": 100},
            },
        ]

        memory_ids = []
        for i, memory in enumerate(test_memories, 1):
            result = client.add(
                memory["content"],
                tags=memory["tags"],
                people_mentioned=memory["people_mentioned"],
                topic_category=memory["topic_category"],
                metadata=memory["metadata"],
            )

            if result.get("success"):
                memory_ids.append(result.get("memory_id"))
                print(f"   ✅ Memory {i} added: {memory['content'][:50]}...")
            else:
                print(f"   ❌ Memory {i} failed: {result.get('error')}")

        # Search memories
        print("\n4. Searching memories...")

        # Basic search
        search_results = client.search("meeting")
        print(
            f"   📋 'meeting' search: {len(search_results.get('results', []))} results"
        )

        # Display first result if available
        if search_results.get("results"):
            first_result = search_results["results"][0]
            print(f"      Example: {first_result.get('content', '')[:60]}...")

        # Food-related search
        food_results = client.search("restaurant food")
        print(
            f"   🍕 'restaurant food' search: {len(food_results.get('results', []))} results"
        )

        # Get all memories
        print("\n5. Retrieving all memories...")
        all_memories = client.get_all()
        total_count = len(all_memories.get("results", []))
        print(f"   📚 Total memories: {total_count}")

        # Get statistics
        print("\n6. Getting statistics...")
        stats = client.get_stats()
        if "error" not in stats:
            print(f"   📊 Memory count: {stats.get('memory_count', 'N/A')}")
            print(f"   📊 Status: {stats.get('status', 'N/A')}")
        else:
            print(f"   ⚠️ Stats error: {stats.get('error')}")

        # Clean up (delete test memories)
        print("\n7. Cleaning up...")
        if memory_ids:
            deleted_count = 0
            for memory_id in memory_ids:
                if memory_id:
                    result = client.delete(memory_id)
                    if result.get("success"):
                        deleted_count += 1
            print(f"   🗑️ Deleted {deleted_count} test memories")

        # Close the client
        client.close()
        print("✅ Client closed successfully")

        return True

    except Exception as e:
        print(f"❌ Error during basic usage: {e}")
        return False


def advanced_search_features():
    """Demonstrate advanced search capabilities."""
    print_section("ADVANCED SEARCH FEATURES")

    api_key = os.getenv("INMEM_API_KEY")
    api_host = os.getenv("SELFMEMORY_API_HOST")

    if not api_key:
        print("❌ API key not available for advanced search demo")
        return

    try:
        # Initialize client
        client = (
            SelfMemoryClient(api_key=api_key, host=api_host)
            if api_host
            else SelfMemoryClient(api_key=api_key)
        )

        # Add diverse test data
        print("\n1. Adding diverse test data...")
        advanced_memories = [
            {
                "content": "Sprint planning meeting with the engineering team. Discussed user stories and sprint goals.",
                "tags": "work,sprint,planning,engineering",
                "people_mentioned": "Alice,Bob,Charlie",
                "topic_category": "work",
            },
            {
                "content": "Coffee chat with Emma from design team about user experience improvements.",
                "tags": "work,design,ux,informal",
                "people_mentioned": "Emma",
                "topic_category": "work",
            },
            {
                "content": "Weekend hiking trip to the mountains with friends. Beautiful weather and great views!",
                "tags": "personal,outdoor,hiking,weekend",
                "people_mentioned": "David,Lisa",
                "topic_category": "personal",
            },
            {
                "content": "Attended AI conference presentation on transformer models and their applications.",
                "tags": "learning,ai,conference,technology",
                "people_mentioned": "",
                "topic_category": "education",
            },
            {
                "content": "Team retrospective meeting. Identified process improvements and action items.",
                "tags": "work,retrospective,process,improvement",
                "people_mentioned": "Alice,Bob,Emma",
                "topic_category": "work",
            },
        ]

        memory_ids = []
        for memory in advanced_memories:
            result = client.add(
                memory["content"],
                tags=memory["tags"],
                people_mentioned=memory["people_mentioned"],
                topic_category=memory["topic_category"],
            )
            if result.get("success"):
                memory_ids.append(result.get("memory_id"))

        print(f"   ✅ Added {len(memory_ids)} memories for testing")

        # Test tag-based search
        print("\n2. Tag-based search...")

        # Single tag search
        work_results = client.search_by_tags("work")
        print(f"   🏷️ 'work' tag: {len(work_results.get('results', []))} results")

        # Multiple tags (OR search)
        multiple_tags_results = client.search_by_tags(["design", "ai"], match_all=False)
        print(
            f"   🏷️ 'design' OR 'ai' tags: {len(multiple_tags_results.get('results', []))} results"
        )

        # Multiple tags (AND search)
        and_tags_results = client.search_by_tags(["work", "meeting"], match_all=True)
        print(
            f"   🏷️ 'work' AND 'meeting' tags: {len(and_tags_results.get('results', []))} results"
        )

        # Test people-based search
        print("\n3. People-based search...")

        # Single person
        alice_results = client.search_by_people("Alice")
        print(
            f"   👤 Memories mentioning 'Alice': {len(alice_results.get('results', []))} results"
        )

        # Multiple people
        team_results = client.search_by_people(["Alice", "Bob", "Emma"])
        print(
            f"   👥 Memories mentioning team members: {len(team_results.get('results', []))} results"
        )

        # Test semantic search with filters
        print("\n4. Combined semantic + filter search...")

        # Search for meetings with specific tags
        meeting_work_results = client.search_by_tags(
            tags=["work", "meeting"],
            semantic_query="planning discussion",
            match_all=True,
        )
        print(
            f"   🔍 'planning discussion' in work meetings: {len(meeting_work_results.get('results', []))} results"
        )

        # Test temporal search (if supported)
        print("\n5. Temporal search...")
        try:
            recent_results = client.temporal_search("today", semantic_query="meeting")
            print(
                f"   📅 Today's meetings: {len(recent_results.get('results', []))} results"
            )
        except Exception as e:
            print(f"   ⚠️ Temporal search not available: {e}")

        # Clean up
        print("\n6. Cleaning up advanced search test data...")
        deleted_count = 0
        for memory_id in memory_ids:
            if memory_id:
                result = client.delete(memory_id)
                if result.get("success"):
                    deleted_count += 1
        print(f"   🗑️ Deleted {deleted_count} test memories")

        client.close()

    except Exception as e:
        print(f"❌ Error during advanced search demo: {e}")


def context_manager_usage():
    """Demonstrate context manager usage for automatic cleanup."""
    print_section("CONTEXT MANAGER USAGE")

    api_key = os.getenv("INMEM_API_KEY")
    api_host = os.getenv("SELFMEMORY_API_HOST")

    if not api_key:
        print("❌ API key not available for context manager demo")
        return

    print("🔄 Using SelfMemoryClient as a context manager...")

    try:
        # Use client as context manager
        client_args = {"api_key": api_key}
        if api_host:
            client_args["host"] = api_host

        with SelfMemoryClient(**client_args) as client:
            print("✅ Client initialized in context manager")

            # Add a test memory
            result = client.add(
                "Context manager test: This memory will be cleaned up automatically",
                tags="test,context_manager",
                topic_category="test",
            )

            if result.get("success"):
                memory_id = result.get("memory_id")
                print(f"✅ Test memory added: {memory_id}")

                # Search for it
                search_results = client.search("context manager")
                print(f"🔍 Found {len(search_results.get('results', []))} results")

                # Delete it
                if memory_id:
                    delete_result = client.delete(memory_id)
                    if delete_result.get("success"):
                        print("🗑️ Test memory deleted")

            print("✅ Operations completed successfully")

        print("✅ Context manager automatically closed the client")

    except Exception as e:
        print(f"❌ Error in context manager demo: {e}")


def error_handling_demo():
    """Demonstrate proper error handling."""
    print_section("ERROR HANDLING DEMONSTRATION")

    print("🚨 Testing various error scenarios...")

    # Test 1: Invalid API key
    print("\n1. Testing invalid API key...")
    try:
        invalid_client = SelfMemoryClient(api_key="invalid_key_12345")
        print("❌ Should have failed with invalid API key")
    except ValueError as e:
        print(f"✅ Properly caught invalid API key: {str(e)[:60]}...")
    except Exception as e:
        print(f"⚠️ Unexpected error type: {e}")

    # Test 2: Network connectivity (invalid host)
    print("\n2. Testing network connectivity...")
    try:
        network_client = SelfMemoryClient(
            api_key="test_key", host="http://invalid-host-that-does-not-exist.com"
        )
        print("❌ Should have failed with network error")
    except ValueError as e:
        print(f"✅ Properly caught network error: {str(e)[:60]}...")
    except Exception as e:
        print(f"⚠️ Unexpected error type: {e}")

    # Test 3: Graceful handling with valid client
    api_key = os.getenv("INMEM_API_KEY")
    if api_key:
        print("\n3. Testing graceful error handling with valid client...")
        try:
            api_host = os.getenv("SELFMEMORY_API_HOST")
            client_args = {"api_key": api_key}
            if api_host:
                client_args["host"] = api_host

            client = SelfMemoryClient(**client_args)

            # Test invalid memory deletion
            delete_result = client.delete("invalid_memory_id_12345")
            if not delete_result.get("success"):
                print("✅ Gracefully handled invalid memory deletion")
                print(
                    f"   Error: {delete_result.get('error', 'Unknown error')[:50]}..."
                )

            # Test empty search
            empty_results = client.search("")
            print(
                f"✅ Empty search handled: {len(empty_results.get('results', []))} results"
            )

            client.close()

        except Exception as e:
            print(f"❌ Unexpected error in graceful handling test: {e}")
    else:
        print("\n3. Skipping graceful error handling (no API key)")


def real_world_scenario():
    """Demonstrate a real-world usage scenario."""
    print_section("REAL-WORLD SCENARIO: PERSONAL KNOWLEDGE ASSISTANT")

    api_key = os.getenv("INMEM_API_KEY")
    api_host = os.getenv("SELFMEMORY_API_HOST")

    if not api_key:
        print("❌ API key not available for real-world scenario")
        return

    print("🤖 Simulating a personal knowledge assistant...")

    try:
        client_args = {"api_key": api_key}
        if api_host:
            client_args["host"] = api_host

        with SelfMemoryClient(**client_args) as assistant:
            # Scenario: User adds various types of information throughout the day
            print("\n📝 Adding daily information...")

            daily_info = [
                {
                    "content": "Doctor appointment scheduled for next Friday at 3 PM with Dr. Smith",
                    "tags": "appointment,health,doctor",
                    "people_mentioned": "Dr. Smith",
                    "topic_category": "personal",
                    "metadata": {
                        "type": "appointment",
                        "date": "next Friday",
                        "time": "3 PM",
                    },
                },
                {
                    "content": "Great book recommendation from colleague: 'Atomic Habits' by James Clear",
                    "tags": "books,recommendation,productivity",
                    "people_mentioned": "James Clear",
                    "topic_category": "personal",
                    "metadata": {
                        "type": "book",
                        "genre": "self-help",
                        "status": "to-read",
                    },
                },
                {
                    "content": "Team decided to use React for the new dashboard project. Migration starts next sprint.",
                    "tags": "work,technology,react,dashboard,migration",
                    "people_mentioned": "",
                    "topic_category": "work",
                    "metadata": {
                        "project": "dashboard",
                        "technology": "React",
                        "timeline": "next sprint",
                    },
                },
                {
                    "content": "Mom's birthday is coming up on March 15th. She mentioned wanting a new garden tool set.",
                    "tags": "family,birthday,gift,reminder",
                    "people_mentioned": "Mom",
                    "topic_category": "personal",
                    "metadata": {
                        "event": "birthday",
                        "date": "March 15th",
                        "gift_idea": "garden tools",
                    },
                },
                {
                    "content": "Learned about microservices architecture in today's tech talk. Key benefits: scalability and maintainability.",
                    "tags": "learning,architecture,microservices,tech_talk",
                    "people_mentioned": "",
                    "topic_category": "education",
                    "metadata": {
                        "topic": "microservices",
                        "type": "tech_talk",
                        "key_points": "scalability, maintainability",
                    },
                },
            ]

            memory_ids = []
            for info in daily_info:
                result = assistant.add(
                    info["content"],
                    tags=info["tags"],
                    people_mentioned=info["people_mentioned"],
                    topic_category=info["topic_category"],
                    metadata=info["metadata"],
                )
                if result.get("success"):
                    memory_ids.append(result.get("memory_id"))
                    print(f"   ✅ Added: {info['content'][:50]}...")

            # Scenario: User asks assistant various questions
            print("\n🔍 Assistant answering user queries...")

            queries = [
                ("appointment", "When is my next appointment?"),
                ("birthday", "What do I need to remember about birthdays?"),
                ("React dashboard", "What did we decide about the dashboard project?"),
                ("book recommendation", "What books were recommended to me?"),
                ("microservices", "What did I learn about microservices?"),
            ]

            for query, question in queries:
                print(f"\n   ❓ User: {question}")
                results = assistant.search(query, limit=3)

                if results.get("results"):
                    for i, result in enumerate(
                        results["results"][:2], 1
                    ):  # Show top 2 results
                        content = result.get("content", "")
                        score = result.get("score", 0)
                        print(
                            f"   🤖 Assistant: {content[:80]}... (relevance: {score:.2f})"
                        )
                else:
                    print("   🤖 Assistant: I don't have any information about that.")

            # Scenario: User wants to see all work-related items
            print("\n📋 User: Show me all my work-related notes")
            work_items = assistant.search_by_tags(["work"], match_all=False)
            work_count = len(work_items.get("results", []))
            print(f"   🤖 Assistant: I found {work_count} work-related items:")

            for item in work_items.get("results", [])[:3]:  # Show first 3
                content = item.get("content", "")
                print(f"      • {content[:60]}...")

            # Scenario: User wants reminders about people
            print("\n👥 User: What do I need to remember about people?")
            people_items = assistant.search_by_people(["Dr. Smith", "Mom"])
            people_count = len(people_items.get("results", []))
            print(
                f"   🤖 Assistant: I found {people_count} items mentioning specific people:"
            )

            for item in people_items.get("results", []):
                content = item.get("content", "")
                people = item.get("metadata", {}).get("people_mentioned", "")
                print(f"      • {content[:60]}...")

            # Clean up
            print("\n🧹 Cleaning up scenario data...")
            deleted_count = 0
            for memory_id in memory_ids:
                if memory_id:
                    result = assistant.delete(memory_id)
                    if result.get("success"):
                        deleted_count += 1
            print(f"   🗑️ Cleaned up {deleted_count} test memories")

            print("\n✅ Personal knowledge assistant scenario completed!")

    except Exception as e:
        print(f"❌ Error in real-world scenario: {e}")


def performance_comparison():
    """Compare performance characteristics of the managed client."""
    print_section("PERFORMANCE CHARACTERISTICS")

    api_key = os.getenv("INMEM_API_KEY")
    api_host = os.getenv("SELFMEMORY_API_HOST")

    if not api_key:
        print("❌ API key not available for performance testing")
        return

    print("⚡ Testing managed client performance...")

    try:
        client_args = {"api_key": api_key}
        if api_host:
            client_args["host"] = api_host

        client = SelfMemoryClient(**client_args)

        # Test 1: Add operation timing
        print("\n1. Add operation performance...")
        add_times = []
        memory_ids = []

        for i in range(5):
            start_time = time.time()
            result = client.add(
                f"Performance test memory {i}: Testing add operation latency and throughput.",
                tags="performance,test",
                topic_category="test",
            )
            end_time = time.time()

            add_time = end_time - start_time
            add_times.append(add_time)

            if result.get("success"):
                memory_ids.append(result.get("memory_id"))
                print(f"   Add {i + 1}: {add_time:.3f}s")

        avg_add_time = sum(add_times) / len(add_times)
        print(f"   Average add time: {avg_add_time:.3f}s")

        # Test 2: Search operation timing
        print("\n2. Search operation performance...")
        search_times = []

        for i in range(3):
            start_time = time.time()
            results = client.search("performance test")
            end_time = time.time()

            search_time = end_time - start_time
            search_times.append(search_time)
            result_count = len(results.get("results", []))
            print(f"   Search {i + 1}: {search_time:.3f}s ({result_count} results)")

        avg_search_time = sum(search_times) / len(search_times)
        print(f"   Average search time: {avg_search_time:.3f}s")

        # Test 3: Get all operation timing
        print("\n3. Get all operation performance...")
        start_time = time.time()
        all_results = client.get_all()
        end_time = time.time()

        get_all_time = end_time - start_time
        total_memories = len(all_results.get("results", []))
        print(f"   Get all: {get_all_time:.3f}s ({total_memories} total memories)")

        # Performance summary
        print("\n📊 Performance Summary:")
        print(f"   Average Add Time: {avg_add_time:.3f}s")
        print(f"   Average Search Time: {avg_search_time:.3f}s")
        print(f"   Get All Time: {get_all_time:.3f}s")
        print(f"   Total Memories: {total_memories}")

        # Clean up
        deleted_count = 0
        for memory_id in memory_ids:
            if memory_id:
                result = client.delete(memory_id)
                if result.get("success"):
                    deleted_count += 1
        print(f"\n🧹 Cleaned up {deleted_count} performance test memories")

        client.close()

    except Exception as e:
        print(f"❌ Error in performance testing: {e}")


def main():
    """Main function to run all SelfMemoryClient examples."""
    print("🚀 SelfMemory Client Example Suite")
    print(f"📅 Started at: {datetime.now().isoformat()}")
    print("=" * 60)

    # Check prerequisites
    api_key = os.getenv("INMEM_API_KEY")
    if not api_key:
        print("\n❌ INMEM_API_KEY environment variable not set!")
        print("\nTo use this example, you need to:")
        print("1. Get an API key from SelfMemory service")
        print("2. Set the environment variable: export INMEM_API_KEY='your_key_here'")
        print(
            "3. Optionally set custom host: export SELFMEMORY_API_HOST='http://localhost:8081'"
        )
        print("\nFor local development:")
        print("1. Start the server: cd server && python main.py")
        print("2. Set host: export SELFMEMORY_API_HOST='http://localhost:8081'")
        return

    print(f"✅ API Key found: {api_key[:8]}...")

    api_host = os.getenv("SELFMEMORY_API_HOST")
    if api_host:
        print(f"🌐 Using custom API host: {api_host}")
    else:
        print("🌐 Using default production API host")

    # Run all examples
    examples = [
        ("Basic Client Usage", basic_client_usage),
        ("Advanced Search Features", advanced_search_features),
        ("Context Manager Usage", context_manager_usage),
        ("Error Handling", error_handling_demo),
        ("Real-World Scenario", real_world_scenario),
        ("Performance Testing", performance_comparison),
    ]

    results = {}

    for name, func in examples:
        try:
            print(f"\n🔄 Running: {name}")
            start_time = time.time()

            if func == basic_client_usage:
                success = func()
                results[name] = "✅ PASS" if success else "❌ FAIL"
            else:
                func()
                results[name] = "✅ PASS"

            end_time = time.time()
            print(f"⏱️ Completed in {end_time - start_time:.2f}s")

        except KeyboardInterrupt:
            print(f"\n⚠️ {name} interrupted by user")
            results[name] = "⚠️ INTERRUPTED"
            break
        except Exception as e:
            print(f"\n❌ {name} failed: {e}")
            results[name] = f"❌ FAIL: {str(e)[:50]}"

    # Print summary
    print_section("EXAMPLE RESULTS SUMMARY")

    for name, result in results.items():
        print(f"   {name}: {result}")

    total_examples = len(results)
    passed_examples = sum(1 for r in results.values() if "✅ PASS" in r)

    print(
        f"\n🎯 Overall Success Rate: {passed_examples}/{total_examples} examples passed"
    )

    print("\n" + "=" * 60)
    print("🎉 SelfMemory Client examples completed!")
    print("\nNext steps:")
    print("• Integrate SelfMemoryClient into your application")
    print("• Explore the API documentation for advanced features")
    print("• Check out the comprehensive test suite for more examples")
    print("• Consider using the local Memory SDK for offline usage")


if __name__ == "__main__":
    main()
