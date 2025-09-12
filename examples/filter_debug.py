"""
Debug the filtering issue specifically.
"""

from inmemory import Memory


def debug_filtering():
    """Debug why filtering isn't working in search."""

    print("🔍 Debugging Filtering Issue...")

    # Create two users
    user1 = Memory(user_id="user1")
    user2 = Memory(user_id="user2")

    # Add different memories
    print("\n📝 Adding memories...")
    result1 = user1.add("I love eating pizza and pasta from Italy")
    result2 = user2.add("My favorite hobby is playing basketball on weekends")

    print(f"User1 add result: {result1}")
    print(f"User2 add result: {result2}")

    # Check what filters are being built
    print("\n🔧 Checking filters...")
    _, user1_filters = user1._build_user_metadata_and_filters()
    _, user2_filters = user2._build_user_metadata_and_filters()

    print(f"User1 filters: {user1_filters}")
    print(f"User2 filters: {user2_filters}")

    # Test raw vector store search with filters
    print("\n🔍 Testing raw vector store search...")

    # Get embeddings
    pizza_embedding = user1.embedding_provider.embed("pizza")

    # Test User1's vector store with User1's filters
    print("--- User1 vector store with User1 filters ---")
    user1_raw = user1.vector_store.search(
        query="pizza", vectors=pizza_embedding, limit=10, filters=user1_filters
    )
    print(f"Results: {len(user1_raw)}")
    for result in user1_raw:
        print(f"  - Content: {result.payload.get('data')}")
        print(f"  - User ID: {result.payload.get('user_id')}")

    # Test User1's vector store with User2's filters
    print("--- User1 vector store with User2 filters ---")
    user1_raw_with_user2_filters = user1.vector_store.search(
        query="pizza", vectors=pizza_embedding, limit=10, filters=user2_filters
    )
    print(f"Results: {len(user1_raw_with_user2_filters)}")
    for result in user1_raw_with_user2_filters:
        print(f"  - Content: {result.payload.get('data')}")
        print(f"  - User ID: {result.payload.get('user_id')}")

    # Test User2's vector store with User1's filters
    print("--- User2 vector store with User1 filters ---")
    user2_raw_with_user1_filters = user2.vector_store.search(
        query="pizza", vectors=pizza_embedding, limit=10, filters=user1_filters
    )
    print(f"Results: {len(user2_raw_with_user1_filters)}")
    for result in user2_raw_with_user1_filters:
        print(f"  - Content: {result.payload.get('data')}")
        print(f"  - User ID: {result.payload.get('user_id')}")

    # Check if they're using the same vector store instance
    print("\n🔧 Vector store instances:")
    print(f"User1 vector store: {id(user1.vector_store)}")
    print(f"User2 vector store: {id(user2.vector_store)}")
    print(f"Same instance? {user1.vector_store is user2.vector_store}")


if __name__ == "__main__":
    debug_filtering()
