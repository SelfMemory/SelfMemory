"""
Debug test to understand what's happening with user isolation.
"""

from inmemory import Memory


def debug_user_isolation():
    """Debug test to see what's happening with user isolation."""

    print("🔍 Debugging Multi-User Isolation...")

    # Create two users
    user1 = Memory(user_id="user1")
    user2 = Memory(user_id="user2")

    print(f"User1 ID: {user1.user_id}")
    print(f"User2 ID: {user2.user_id}")

    # Add different memories for each user
    print("\n📝 Adding memories...")
    result1 = user1.add("User 1's secret data")
    result2 = user2.add("User 2's private information")

    print(f"User1 add result: {result1}")
    print(f"User2 add result: {result2}")

    # Check what each user sees
    print("\n📋 Getting all memories...")
    user1_memories = user1.get_all()
    user2_memories = user2.get_all()

    print(f"User1 memories: {len(user1_memories['results'])}")
    for i, mem in enumerate(user1_memories["results"]):
        print(f"  {i + 1}. Content: {mem['content']}")
        print(f"     Metadata: {mem.get('metadata', {})}")

    print(f"User2 memories: {len(user2_memories['results'])}")
    for i, mem in enumerate(user2_memories["results"]):
        print(f"  {i + 1}. Content: {mem['content']}")
        print(f"     Metadata: {mem.get('metadata', {})}")

    # Test search isolation
    print("\n🔍 Testing search isolation...")
    user1_search = user1.search("secret")
    user2_search = user2.search("secret")

    print(f"User1 search for 'secret': {len(user1_search['results'])} results")
    for i, result in enumerate(user1_search["results"]):
        print(f"  {i + 1}. Content: {result['content']}")
        print(f"     Metadata: {result.get('metadata', {})}")

    print(f"User2 search for 'secret': {len(user2_search['results'])} results")
    for i, result in enumerate(user2_search["results"]):
        print(f"  {i + 1}. Content: {result['content']}")
        print(f"     Metadata: {result.get('metadata', {})}")

    # Check if the issue is with the vector store itself
    print("\n🔧 Checking vector store behavior...")

    # Let's see what the vector store actually contains
    try:
        # This is a debug check - we'll try to access the vector store directly
        print(f"Vector store type: {type(user1.vector_store)}")
        if hasattr(user1.vector_store, "count"):
            total_count = user1.vector_store.count()
            print(f"Total items in vector store: {total_count}")
    except Exception as e:
        print(f"Error checking vector store: {e}")


if __name__ == "__main__":
    debug_user_isolation()
