"""
Multi-User Isolation Demo for InMemory Memory SDK

This example demonstrates the mem0-style user isolation capabilities
of the InMemory Memory class, showing how different users can have
completely isolated memory spaces.
"""

from inmemory import Memory


def main():
    """Demonstrate multi-user isolation with the Memory SDK."""

    print("🚀 InMemory Multi-User Isolation Demo")
    print("=" * 50)

    # Create separate memory instances for different users
    print("\n1. Creating user-scoped memory instances...")
    alice_memory = Memory(user_id="alice")
    bob_memory = Memory(user_id="bob")
    charlie_memory = Memory(user_id="charlie")

    print("✅ Created memory instances for Alice, Bob, and Charlie")

    # Each user adds their own memories
    print("\n2. Users adding their personal memories...")

    # Alice's memories
    alice_memory.add("I love Italian food, especially pizza and pasta")
    alice_memory.add(
        "Had a great meeting with the product team today",
        tags="work,meeting,product",
        people_mentioned="Sarah,Mike,Jennifer",
    )
    alice_memory.add(
        "Planning a trip to Rome next month",
        tags="travel,personal",
        topic_category="travel",
    )

    # Bob's memories
    bob_memory.add("I prefer Japanese cuisine like sushi and ramen")
    bob_memory.add(
        "Working on the new authentication system",
        tags="work,development,security",
        topic_category="work",
    )
    bob_memory.add(
        "Learning to play guitar in my free time", tags="hobby,music,personal"
    )

    # Charlie's memories
    charlie_memory.add("Mexican food is my absolute favorite")
    charlie_memory.add(
        "Completed the quarterly financial review",
        tags="work,finance,quarterly",
        people_mentioned="David,Lisa",
    )
    charlie_memory.add(
        "Started training for the marathon",
        tags="fitness,running,personal",
        topic_category="health",
    )

    print("✅ Each user added 3 memories to their isolated space")

    # Demonstrate user isolation in searches
    print("\n3. Testing user isolation with searches...")

    # Search for "food" - each user only sees their own food preferences
    print("\n🔍 Searching for 'food' across all users:")

    alice_food = alice_memory.search("food")
    bob_food = bob_memory.search("food")
    charlie_food = charlie_memory.search("food")

    print(f"Alice's food memories: {len(alice_food['results'])} results")
    for result in alice_food["results"]:
        print(f"  - {result['content']}")

    print(f"Bob's food memories: {len(bob_food['results'])} results")
    for result in bob_food["results"]:
        print(f"  - {result['content']}")

    print(f"Charlie's food memories: {len(charlie_food['results'])} results")
    for result in charlie_food["results"]:
        print(f"  - {result['content']}")

    # Search for work-related memories
    print("\n🔍 Searching for 'work' across all users:")

    alice_work = alice_memory.search("work", tags=["work"])
    bob_work = bob_memory.search("work", tags=["work"])
    charlie_work = charlie_memory.search("work", tags=["work"])

    print(f"Alice's work memories: {len(alice_work['results'])} results")
    print(f"Bob's work memories: {len(bob_work['results'])} results")
    print(f"Charlie's work memories: {len(charlie_work['results'])} results")

    # Demonstrate get_all() isolation
    print("\n4. Testing get_all() user isolation...")

    alice_all = alice_memory.get_all()
    bob_all = bob_memory.get_all()
    charlie_all = charlie_memory.get_all()

    print(f"Alice's total memories: {len(alice_all['results'])}")
    print(f"Bob's total memories: {len(bob_all['results'])}")
    print(f"Charlie's total memories: {len(charlie_all['results'])}")

    # Demonstrate secure deletion
    print("\n5. Testing secure deletion (user isolation)...")

    # Each user deletes their own memories
    alice_delete_result = alice_memory.delete_all()
    bob_delete_result = bob_memory.delete_all()

    print(f"Alice deleted {alice_delete_result['deleted_count']} memories")
    print(f"Bob deleted {bob_delete_result['deleted_count']} memories")

    # Charlie's memories should still exist
    charlie_remaining = charlie_memory.get_all()
    print(
        f"Charlie still has {len(charlie_remaining['results'])} memories (unaffected)"
    )

    # Advanced usage example
    print("\n6. Advanced multi-tenant usage example...")

    def get_user_memory(user_id: str) -> Memory:
        """Factory function for creating user-scoped memory instances."""
        return Memory(user_id=user_id)

    # Simulate multi-tenant application
    tenant_1_user = get_user_memory("tenant_1_user_456")
    tenant_2_user = get_user_memory("tenant_2_user_789")

    # Add confidential data for each tenant
    tenant_1_user.add("Confidential business strategy for Q4")
    tenant_2_user.add("Personal notes about family vacation")

    # Verify complete isolation
    tenant_1_memories = tenant_1_user.get_all()
    tenant_2_memories = tenant_2_user.get_all()

    print(f"Tenant 1 user has {len(tenant_1_memories['results'])} memories")
    print(f"Tenant 2 user has {len(tenant_2_memories['results'])} memories")
    print("✅ Complete tenant isolation maintained")

    # Custom configuration example
    print("\n7. Custom configuration example...")

    custom_config = {
        "embedding": {
            "provider": "sentence_transformers",
            "config": {"model": "all-MiniLM-L6-v2"},
        },
        "vector_store": {
            "provider": "chroma",
            "config": {"path": "./custom_chroma_db"},
        },
    }

    try:
        custom_memory = Memory(user_id="custom_user", config=custom_config)
        custom_memory.add("Testing custom configuration")
        print("✅ Custom configuration works successfully")
    except Exception as e:
        print(f"⚠️  Custom config not available (expected in demo): {e}")

    print("\n🎉 Multi-User Isolation Demo Complete!")
    print("=" * 50)
    print("\nKey Features Demonstrated:")
    print("✅ Complete user isolation - users can only see their own memories")
    print("✅ Secure operations - users can only modify their own data")
    print("✅ Multi-tenant ready - perfect for production applications")
    print("✅ Zero-setup - works out of the box with embedded providers")
    print("✅ Flexible configuration - supports custom embedding and vector stores")


if __name__ == "__main__":
    main()
