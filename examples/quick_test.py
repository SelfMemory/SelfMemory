"""
Quick test to verify multi-user isolation works correctly.
"""

from inmemory import Memory


def test_user_isolation():
    """Quick test to verify user isolation is working."""

    print("🧪 Testing Multi-User Isolation...")

    # Create two users
    user1 = Memory(user_id="user1")
    user2 = Memory(user_id="user2")

    # Add different memories for each user
    user1.add("User 1's secret data")
    user2.add("User 2's private information")

    # Test isolation
    user1_memories = user1.get_all()
    user2_memories = user2.get_all()

    print(f"User 1 has {len(user1_memories['results'])} memories")
    print(f"User 2 has {len(user2_memories['results'])} memories")

    # Verify content isolation
    user1_content = [m["content"] for m in user1_memories["results"]]
    user2_content = [m["content"] for m in user2_memories["results"]]

    assert "User 1's secret data" in user1_content
    assert "User 1's secret data" not in user2_content
    assert "User 2's private information" in user2_content
    assert "User 2's private information" not in user1_content

    print("✅ User isolation test passed!")

    # Test search isolation
    user1_search = user1.search("secret")
    user2_search = user2.search("secret")

    assert len(user1_search["results"]) == 1
    assert len(user2_search["results"]) == 0

    print("✅ Search isolation test passed!")

    # Test delete isolation
    user1.delete_all()

    user1_after_delete = user1.get_all()
    user2_after_delete = user2.get_all()

    assert len(user1_after_delete["results"]) == 0
    assert len(user2_after_delete["results"]) == 1

    print("✅ Delete isolation test passed!")
    print("🎉 All tests passed - Multi-user isolation is working correctly!")


if __name__ == "__main__":
    test_user_isolation()
