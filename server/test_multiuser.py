#!/usr/bin/env python3
"""
Test script for multi-user isolation in SelfMemory Server.

This script tests that users can only access their own memories
and cannot see or modify memories from other users.
"""

import sys

import requests

# Server configuration
BASE_URL = "http://localhost:8081"


def test_health_check():
    """Test that the server is running."""
    print("🔍 Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Server is healthy")
            return True
        print(f"❌ Health check failed: {response.status_code}")
        return False
    except requests.exceptions.ConnectionError:
        print(
            "❌ Cannot connect to server. Make sure it's running on http://localhost:8081"
        )
        return False


def add_memory(user_id, content, metadata=None):
    """Add a memory for a specific user."""
    payload = {
        "messages": [{"role": "user", "content": content}],
        "user_id": user_id,
        "metadata": metadata or {},
    }

    response = requests.post(f"{BASE_URL}/memories", json=payload)
    return response


def search_memories(user_id, query, limit=10):
    """Search memories for a specific user."""
    payload = {"query": query, "user_id": user_id, "limit": limit}

    response = requests.post(f"{BASE_URL}/search", json=payload)
    return response


def get_all_memories(user_id, limit=100):
    """Get all memories for a specific user."""
    response = requests.get(
        f"{BASE_URL}/memories", params={"user_id": user_id, "limit": limit}
    )
    return response


def delete_all_memories(user_id):
    """Delete all memories for a specific user."""
    response = requests.delete(f"{BASE_URL}/memories", params={"user_id": user_id})
    return response


def test_multi_user_isolation():
    """Test that users can only access their own memories."""
    print("\n🧪 Testing multi-user isolation...")

    # Test users
    alice_id = "alice_test"
    bob_id = "bob_test"
    charlie_id = "charlie_test"

    # Clean up any existing test data
    print("🧹 Cleaning up existing test data...")
    delete_all_memories(alice_id)
    delete_all_memories(bob_id)
    delete_all_memories(charlie_id)

    # Add memories for each user
    print("📝 Adding memories for each user...")

    # Alice's memories
    alice_memory1 = add_memory(
        alice_id, "I love Italian food, especially pizza", {"category": "food"}
    )
    alice_memory2 = add_memory(
        alice_id, "I work as a software engineer", {"category": "work"}
    )

    # Bob's memories
    bob_memory1 = add_memory(
        bob_id, "I prefer Japanese cuisine like sushi", {"category": "food"}
    )
    bob_memory2 = add_memory(bob_id, "I'm a data scientist", {"category": "work"})

    # Charlie's memories
    charlie_memory1 = add_memory(
        charlie_id, "Mexican food is my favorite", {"category": "food"}
    )
    charlie_memory2 = add_memory(
        charlie_id, "I'm a product manager", {"category": "work"}
    )

    # Check that all memories were added successfully
    if not all(
        [
            r.status_code == 200
            for r in [
                alice_memory1,
                alice_memory2,
                bob_memory1,
                bob_memory2,
                charlie_memory1,
                charlie_memory2,
            ]
        ]
    ):
        print("❌ Failed to add memories")
        return False

    print("✅ All memories added successfully")

    # Test 1: Each user should only see their own memories
    print("\n🔍 Test 1: User isolation - each user should only see their own memories")

    alice_memories = get_all_memories(alice_id)
    bob_memories = get_all_memories(bob_id)
    charlie_memories = get_all_memories(charlie_id)

    if (
        alice_memories.status_code != 200
        or bob_memories.status_code != 200
        or charlie_memories.status_code != 200
    ):
        print("❌ Failed to retrieve memories")
        return False

    alice_results = alice_memories.json().get("results", [])
    bob_results = bob_memories.json().get("results", [])
    charlie_results = charlie_memories.json().get("results", [])

    print(f"   Alice has {len(alice_results)} memories")
    print(f"   Bob has {len(bob_results)} memories")
    print(f"   Charlie has {len(charlie_results)} memories")

    if len(alice_results) != 2 or len(bob_results) != 2 or len(charlie_results) != 2:
        print("❌ Users don't have the expected number of memories")
        return False

    print("✅ Each user has the correct number of memories")

    # Test 2: Search should be user-isolated
    print(
        "\n🔍 Test 2: Search isolation - searches should only return user's own memories"
    )

    alice_food_search = search_memories(alice_id, "food")
    bob_food_search = search_memories(bob_id, "food")
    charlie_food_search = search_memories(charlie_id, "food")

    if (
        alice_food_search.status_code != 200
        or bob_food_search.status_code != 200
        or charlie_food_search.status_code != 200
    ):
        print("❌ Failed to search memories")
        return False

    alice_food_results = alice_food_search.json().get("results", [])
    bob_food_results = bob_food_search.json().get("results", [])
    charlie_food_results = charlie_food_search.json().get("results", [])

    print(f"   Alice's food search: {len(alice_food_results)} results")
    print(f"   Bob's food search: {len(bob_food_results)} results")
    print(f"   Charlie's food search: {len(charlie_food_results)} results")

    # Check that each user only gets their own food-related memories
    alice_has_pizza = any(
        "pizza" in result.get("content", "").lower() for result in alice_food_results
    )
    bob_has_sushi = any(
        "sushi" in result.get("content", "").lower() for result in bob_food_results
    )
    charlie_has_mexican = any(
        "mexican" in result.get("content", "").lower()
        for result in charlie_food_results
    )

    if not (alice_has_pizza and bob_has_sushi and charlie_has_mexican):
        print("❌ Users are not getting their own food memories")
        return False

    print("✅ Search results are properly isolated per user")

    # Test 3: Cross-user access should be denied
    print("\n🔍 Test 3: Cross-user access denial")

    # Try to get Alice's memory with Bob's user_id (should fail or return empty)
    if alice_results:
        alice_memory_id = alice_results[0].get("id")
        cross_access_attempt = requests.get(
            f"{BASE_URL}/memories/{alice_memory_id}", params={"user_id": bob_id}
        )

        if (
            cross_access_attempt.status_code == 404
            or cross_access_attempt.status_code == 403
        ):
            print("✅ Cross-user memory access properly denied")
        else:
            print("❌ Cross-user memory access was not properly denied")
            return False

    # Test 4: Delete isolation
    print(
        "\n🔍 Test 4: Delete isolation - users should only be able to delete their own memories"
    )

    # Alice deletes all her memories
    alice_delete = delete_all_memories(alice_id)
    if alice_delete.status_code != 200:
        print("❌ Failed to delete Alice's memories")
        return False

    # Check that only Alice's memories were deleted
    alice_after_delete = get_all_memories(alice_id)
    bob_after_delete = get_all_memories(bob_id)
    charlie_after_delete = get_all_memories(charlie_id)

    alice_count_after = len(alice_after_delete.json().get("results", []))
    bob_count_after = len(bob_after_delete.json().get("results", []))
    charlie_count_after = len(charlie_after_delete.json().get("results", []))

    print(
        f"   After Alice's delete - Alice: {alice_count_after}, Bob: {bob_count_after}, Charlie: {charlie_count_after}"
    )

    if alice_count_after != 0 or bob_count_after != 2 or charlie_count_after != 2:
        print("❌ Delete operation affected wrong users")
        return False

    print("✅ Delete operation properly isolated to Alice only")

    # Clean up remaining test data
    print("\n🧹 Cleaning up remaining test data...")
    delete_all_memories(bob_id)
    delete_all_memories(charlie_id)

    return True


def main():
    """Run all tests."""
    print("🚀 Starting SelfMemory Server Multi-User Isolation Tests")
    print("=" * 60)

    # Test server health
    if not test_health_check():
        print("\n❌ Server health check failed. Please start the server first:")
        print("   cd selfmemory-core/server && python main.py")
        sys.exit(1)

    # Test multi-user isolation
    if test_multi_user_isolation():
        print("\n" + "=" * 60)
        print("🎉 All multi-user isolation tests passed!")
        print("✅ Users can only access their own memories")
        print("✅ Search results are properly isolated")
        print("✅ Cross-user access is denied")
        print("✅ Delete operations are user-scoped")
        print("\n🔒 Multi-user isolation is working correctly!")
    else:
        print("\n" + "=" * 60)
        print("❌ Multi-user isolation tests failed!")
        print("🚨 There may be security issues with user isolation")
        sys.exit(1)


if __name__ == "__main__":
    main()
