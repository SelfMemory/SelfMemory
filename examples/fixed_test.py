"""
Fixed test with completely different content to verify user isolation.
"""

from selfmemory import Memory


def test_user_isolation_fixed():
    """Fixed test with non-overlapping content."""

    print("🧪 Testing Multi-User Isolation (Fixed)...")

    # Create two users
    user1 = Memory(user_id="user1")
    user2 = Memory(user_id="user2")

    # Add completely different memories with no semantic overlap
    print("\n📝 Adding completely different memories...")
    result1 = user1.add("I love eating pizza and pasta from Italy")
    result2 = user2.add("My favorite hobby is playing basketball on weekends")

    print(f"User1 add result: {result1}")
    print(f"User2 add result: {result2}")

    # Test isolation with completely different search terms
    print("\n🔍 Testing search isolation...")

    # User1 searches for "pizza" - should only find their own memory
    user1_pizza_search = user1.search("pizza")
    user2_pizza_search = user2.search("pizza")

    print(f"User1 search for 'pizza': {len(user1_pizza_search['results'])} results")
    for result in user1_pizza_search["results"]:
        print(f"  - Content: {result['content']}")
        print(f"  - User ID: {result['metadata']['user_id']}")

    print(f"User2 search for 'pizza': {len(user2_pizza_search['results'])} results")
    for result in user2_pizza_search["results"]:
        print(f"  - Content: {result['content']}")
        print(f"  - User ID: {result['metadata']['user_id']}")

    # User2 searches for "basketball" - should only find their own memory
    user1_basketball_search = user1.search("basketball")
    user2_basketball_search = user2.search("basketball")

    print(
        f"User1 search for 'basketball': {len(user1_basketball_search['results'])} results"
    )
    for result in user1_basketball_search["results"]:
        print(f"  - Content: {result['content']}")
        print(f"  - User ID: {result['metadata']['user_id']}")

    print(
        f"User2 search for 'basketball': {len(user2_basketball_search['results'])} results"
    )
    for result in user2_basketball_search["results"]:
        print(f"  - Content: {result['content']}")
        print(f"  - User ID: {result['metadata']['user_id']}")

    # Verify isolation
    print("\n✅ Verification:")

    # User1 should find pizza, not basketball
    user1_finds_pizza = len(user1_pizza_search["results"]) > 0
    user1_finds_basketball = len(user1_basketball_search["results"]) > 0

    # User2 should find basketball, not pizza
    user2_finds_pizza = len(user2_pizza_search["results"]) > 0
    user2_finds_basketball = len(user2_basketball_search["results"]) > 0

    print(f"User1 finds pizza: {user1_finds_pizza} (should be True)")
    print(f"User1 finds basketball: {user1_finds_basketball} (should be False)")
    print(f"User2 finds pizza: {user2_finds_pizza} (should be False)")
    print(f"User2 finds basketball: {user2_finds_basketball} (should be True)")

    # Test get_all isolation
    print("\n📋 Testing get_all isolation...")
    user1_all = user1.get_all()
    user2_all = user2.get_all()

    print(f"User1 total memories: {len(user1_all['results'])}")
    print(f"User2 total memories: {len(user2_all['results'])}")

    # Verify each user only sees their own content
    user1_contents = [m["content"] for m in user1_all["results"]]
    user2_contents = [m["content"] for m in user2_all["results"]]

    print(f"User1 sees pizza content: {'pizza' in str(user1_contents).lower()}")
    print(
        f"User1 sees basketball content: {'basketball' in str(user1_contents).lower()}"
    )
    print(f"User2 sees pizza content: {'pizza' in str(user2_contents).lower()}")
    print(
        f"User2 sees basketball content: {'basketball' in str(user2_contents).lower()}"
    )

    # Final verification
    isolation_working = (
        user1_finds_pizza
        and not user1_finds_basketball
        and not user2_finds_pizza
        and user2_finds_basketball
    )

    if isolation_working:
        print("\n🎉 SUCCESS: User isolation is working correctly!")
    else:
        print("\n❌ FAILURE: User isolation is not working properly!")

    return isolation_working


if __name__ == "__main__":
    test_user_isolation_fixed()
