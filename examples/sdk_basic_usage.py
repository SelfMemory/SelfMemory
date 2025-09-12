#!/usr/bin/env python3
"""
SelfMemory SDK Basic Usage Examples

This script demonstrates basic usage patterns for the SelfMemory SDK.
Perfect for getting started with the SDK quickly.

Usage:
    python examples/sdk_basic_usage.py

Requirements:
    - Ollama server running on localhost:11434 with nomic-embed-text model
"""

import os
from datetime import datetime

# Import SelfMemory SDK
from selfmemory import Memory, SelfMemoryClient


def example_local_memory_sdk():
    """Demonstrate basic usage of the local Memory SDK."""
    print("=" * 60)
    print("  LOCAL MEMORY SDK - BASIC USAGE")
    print("=" * 60)

    # 1. Initialize Memory with default configuration
    print("\n1. Initializing Memory SDK...")
    memory = Memory()
    print(f"✅ Memory initialized: {memory}")

    # 2. Add some memories
    print("\n2. Adding memories...")

    memories_to_add = [
        {
            "content": "I had lunch with Sarah at the Italian restaurant downtown. The pasta was amazing!",
            "user_id": "alice",
            "tags": "food,lunch,restaurant",
            "people_mentioned": "Sarah",
            "topic_category": "personal",
        },
        {
            "content": "Team meeting about the Q4 roadmap. Discussed new features and timeline.",
            "user_id": "alice",
            "tags": "work,meeting,roadmap",
            "people_mentioned": "Mike,Jennifer",
            "topic_category": "work",
        },
        {
            "content": "Finished reading 'Clean Code' by Robert Martin. Great insights on software development.",
            "user_id": "alice",
            "tags": "books,programming,learning",
            "people_mentioned": "",
            "topic_category": "education",
        },
    ]

    memory_ids = []
    for i, mem in enumerate(memories_to_add, 1):
        result = memory.add(
            mem["content"],
            user_id=mem["user_id"],
            tags=mem["tags"],
            people_mentioned=mem["people_mentioned"],
            topic_category=mem["topic_category"],
        )

        if result.get("success"):
            memory_ids.append(result.get("memory_id"))
            print(f"   Memory {i}: ✅ Added successfully")
        else:
            print(f"   Memory {i}: ❌ Failed - {result.get('error')}")

    # 3. Search memories
    print("\n3. Searching memories...")

    search_queries = [
        ("restaurant", "Food-related memories"),
        ("meeting", "Work meetings"),
        ("Sarah", "Memories mentioning Sarah"),
        ("", "All memories (empty query)"),
    ]

    for query, description in search_queries:
        results = memory.search(query, user_id="alice", limit=5)
        count = len(results.get("results", []))
        print(f"   {description}: {count} results")

        # Show first result if available
        if results.get("results"):
            first_result = results["results"][0]
            content = first_result.get("content", "")[:50] + "..."
            print(f"      Example: {content}")

    # 4. Get all memories
    print("\n4. Getting all memories...")
    all_memories = memory.get_all(user_id="alice")
    total_count = len(all_memories.get("results", []))
    print(f"   Total memories for Alice: {total_count}")

    # 5. Advanced search with filters
    print("\n5. Advanced search with filters...")

    # Search by topic category (simpler approach)
    try:
        work_memories = memory.search(
            query="meeting", user_id="alice", topic_category="work"
        )
        print(f"   Work-related memories: {len(work_memories.get('results', []))}")
    except Exception as e:
        print(f"   Work search error: {e}")
        # Fallback to basic search
        work_memories = memory.search("work", user_id="alice")
        print(
            f"   Work-related memories (fallback): {len(work_memories.get('results', []))}"
        )

    # Search by content mentioning people (simpler approach)
    try:
        sarah_memories = memory.search("Sarah", user_id="alice")
        print(f"   Memories mentioning Sarah: {len(sarah_memories.get('results', []))}")
    except Exception as e:
        print(f"   Sarah search error: {e}")

    # 6. Delete a specific memory
    print("\n6. Deleting a memory...")
    if memory_ids:
        delete_result = memory.delete(memory_ids[0])
        if delete_result.get("success"):
            print("   ✅ Memory deleted successfully")
        else:
            print(f"   ❌ Delete failed: {delete_result.get('error')}")

    # 7. Get statistics
    print("\n7. Getting statistics...")
    stats = memory.get_stats()
    print(f"   Embedding Provider: {stats.get('embedding_provider', 'unknown')}")
    print(f"   Vector Store: {stats.get('vector_store', 'unknown')}")
    print(f"   Status: {stats.get('status', 'unknown')}")

    # 8. Health check
    print("\n8. Health check...")
    health = memory.health_check()
    print(f"   Health Status: {health.get('status', 'unknown')}")

    # 9. Cleanup
    print("\n9. Cleaning up...")
    cleanup_result = memory.delete_all(user_id="alice")
    deleted_count = cleanup_result.get("deleted_count", 0)
    print(f"   Deleted {deleted_count} memories")

    # Close the memory instance
    memory.close()
    print("   ✅ Memory instance closed")


def example_multi_user_isolation():
    """Demonstrate multi-user isolation."""
    print("\n" + "=" * 60)
    print("  MULTI-USER ISOLATION DEMO")
    print("=" * 60)

    memory = Memory()

    # Add memories for different users
    users = ["alice", "bob", "charlie"]

    print("\n1. Adding memories for different users...")
    for user in users:
        result = memory.add(
            f"This is a private memory for {user}. Contains sensitive information.",
            user_id=user,
            tags="private,personal",
            topic_category="personal",
        )
        print(f"   {user}: {'✅' if result.get('success') else '❌'}")

    # Verify isolation
    print("\n2. Verifying user isolation...")
    for user in users:
        user_memories = memory.get_all(user_id=user)
        count = len(user_memories.get("results", []))
        print(f"   {user} can see {count} memories (should be 1)")

        # Verify content
        if user_memories.get("results"):
            content = user_memories["results"][0].get("content", "")
            if user in content:
                print(f"      ✅ Content belongs to {user}")
            else:
                print("      ❌ Content leak detected!")

    # Cleanup
    print("\n3. Cleaning up...")
    for user in users:
        memory.delete_all(user_id=user)

    memory.close()


def example_custom_configuration():
    """Demonstrate custom configuration."""
    print("\n" + "=" * 60)
    print("  CUSTOM CONFIGURATION DEMO")
    print("=" * 60)

    # Custom configuration
    custom_config = {
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
                "collection_name": "custom_memories",
                "path": "/tmp/custom_qdrant",
            },
        },
    }

    print("\n1. Initializing with custom configuration...")
    memory = Memory(config=custom_config)
    print("   ✅ Custom Memory initialized")
    print(f"   Embedding: {memory.config.embedding.provider}")
    print(f"   Vector Store: {memory.config.vector_store.provider}")

    # Test basic functionality
    print("\n2. Testing with custom config...")
    result = memory.add(
        "Testing custom configuration setup", user_id="test_user", tags="test,config"
    )
    print(f"   Add result: {'✅' if result.get('success') else '❌'}")

    # Search
    search_results = memory.search("configuration", user_id="test_user")
    print(f"   Search results: {len(search_results.get('results', []))}")

    # Cleanup
    memory.delete_all(user_id="test_user")
    memory.close()


def example_managed_client_sdk():
    """Demonstrate managed SelfMemoryClient SDK (if API key available)."""
    print("\n" + "=" * 60)
    print("  MANAGED CLIENT SDK - BASIC USAGE")
    print("=" * 60)

    # Check for API key
    api_key = os.getenv("INMEM_API_KEY")
    if not api_key:
        print("⚠️ INMEM_API_KEY not found. Skipping managed client demo.")
        print("   Set INMEM_API_KEY environment variable to test managed client.")
        return

    try:
        # 1. Initialize client
        print("\n1. Initializing SelfMemoryClient...")
        client = SelfMemoryClient(api_key=api_key)
        print(f"✅ Client initialized: {client}")

        # 2. Add memories
        print("\n2. Adding memories...")
        memories = [
            {
                "content": "Client meeting with potential investors went well",
                "tags": "business,meeting,investors",
                "topic_category": "business",
            },
            {
                "content": "Completed the quarterly financial report",
                "tags": "finance,report,quarterly",
                "topic_category": "work",
            },
        ]

        for i, mem in enumerate(memories, 1):
            result = client.add(
                mem["content"], tags=mem["tags"], topic_category=mem["topic_category"]
            )
            print(f"   Memory {i}: {'✅' if result.get('success') else '❌'}")

        # 3. Search memories
        print("\n3. Searching memories...")
        search_results = client.search("meeting")
        print(f"   Search results: {len(search_results.get('results', []))}")

        # 4. Advanced search methods
        print("\n4. Advanced search methods...")

        # Tag search
        tag_results = client.search_by_tags(["business", "meeting"])
        print(f"   Tag search results: {len(tag_results.get('results', []))}")

        # 5. Get all memories
        print("\n5. Getting all memories...")
        all_memories = client.get_all()
        print(f"   Total memories: {len(all_memories.get('results', []))}")

        # 6. Get statistics
        print("\n6. Getting statistics...")
        stats = client.get_stats()
        print(f"   Stats: {'✅' if 'error' not in stats else '❌'}")

        # 7. Health check
        print("\n7. Health check...")
        health = client.health_check()
        print(f"   Health: {health.get('status', 'unknown')}")

        # 8. Context manager usage
        print("\n8. Context manager usage...")
        with SelfMemoryClient(api_key=api_key) as ctx_client:
            result = ctx_client.add("Context manager test")
            print(f"   Context manager: {'✅' if result.get('success') else '❌'}")

        # 9. Cleanup
        print("\n9. Cleaning up...")
        client.delete_all()
        client.close()
        print("   ✅ Cleanup completed")

    except Exception as e:
        print(f"❌ Managed client demo failed: {e}")


def main():
    """Run all basic usage examples."""
    print("🚀 SelfMemory SDK Basic Usage Examples")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Run examples
        example_local_memory_sdk()
        example_multi_user_isolation()
        example_custom_configuration()
        example_managed_client_sdk()

        print("\n" + "=" * 60)
        print("  ALL EXAMPLES COMPLETED SUCCESSFULLY! 🎉")
        print("=" * 60)
        print()
        print("Next steps:")
        print(
            "• Run the comprehensive test suite: python examples/sdk_comprehensive_test.py"
        )
        print("• Check out the configuration examples in examples/")
        print("• Read the documentation for advanced features")

    except KeyboardInterrupt:
        print("\n⚠️ Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
