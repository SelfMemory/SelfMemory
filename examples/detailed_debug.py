"""
Detailed debug to understand exactly what's happening with filtering.
"""

from selfmemory import Memory


def detailed_debug():
    """Detailed debug to see exactly what's happening."""

    print("🔍 Detailed Debug of User Isolation...")

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

    # Let's check what filters are being built
    print("\n🔧 Checking filter building...")

    # Test the _build_user_metadata_and_filters method directly
    user1_storage_metadata, user1_query_filters = (
        user1._build_user_metadata_and_filters()
    )
    user2_storage_metadata, user2_query_filters = (
        user2._build_user_metadata_and_filters()
    )

    print(f"User1 query filters: {user1_query_filters}")
    print(f"User2 query filters: {user2_query_filters}")

    # Now let's see what happens when we search
    print("\n🔍 Testing search with detailed logging...")

    # Let's manually check what the vector store returns without our helper methods
    print("\n--- User1 searching for 'secret' ---")
    user1_embedding = user1.embedding_provider.embed("secret")
    user1_raw_results = user1.vector_store.search(
        query="secret", vectors=user1_embedding, limit=10, filters=user1_query_filters
    )
    print(f"User1 raw search results: {len(user1_raw_results)} items")
    for i, result in enumerate(user1_raw_results):
        print(f"  {i + 1}. ID: {result.id}")
        print(f"      Content: {result.payload.get('data', 'N/A')}")
        print(f"      User ID: {result.payload.get('user_id', 'N/A')}")

    print("\n--- User2 searching for 'secret' ---")
    user2_embedding = user2.embedding_provider.embed("secret")
    user2_raw_results = user2.vector_store.search(
        query="secret", vectors=user2_embedding, limit=10, filters=user2_query_filters
    )
    print(f"User2 raw search results: {len(user2_raw_results)} items")
    for i, result in enumerate(user2_raw_results):
        print(f"  {i + 1}. ID: {result.id}")
        print(f"      Content: {result.payload.get('data', 'N/A')}")
        print(f"      User ID: {result.payload.get('user_id', 'N/A')}")

    # Let's also test without any filters to see all data
    print("\n--- Searching without filters (should see all data) ---")
    all_results = user1.vector_store.search(
        query="secret",
        vectors=user1_embedding,
        limit=10,
        filters=None,  # No filters
    )
    print(f"Search without filters: {len(all_results)} items")
    for i, result in enumerate(all_results):
        print(f"  {i + 1}. ID: {result.id}")
        print(f"      Content: {result.payload.get('data', 'N/A')}")
        print(f"      User ID: {result.payload.get('user_id', 'N/A')}")


if __name__ == "__main__":
    detailed_debug()
