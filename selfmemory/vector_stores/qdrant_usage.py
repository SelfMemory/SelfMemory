"""
Demo and test script for Qdrant vector store.
Initializes Qdrant and exercises all public methods.
"""

import random

from selfmemory.vector_stores.qdrant import Qdrant


def main():
    # Settings
    collection_name = "test_collection"
    embedding_model_dims = 8
    # Use local Qdrant (no host/port/url/api_key)
    qdrant = Qdrant(
        collection_name=collection_name,
        embedding_model_dims=embedding_model_dims,
        on_disk=False,
    )

    # 1. Create collection (already done in __init__)
    print("Created collection:", collection_name)

    # 2. Insert vectors
    vectors = [[random.random() for _ in range(embedding_model_dims)] for _ in range(5)]
    payloads = [{"data": f"memory {i}", "user_id": f"user_{i}"} for i in range(5)]
    ids = [i + 1 for i in range(5)]
    qdrant.insert(vectors, payloads=payloads, ids=ids)
    print("Inserted vectors.")

    # 3. List all collections
    cols = qdrant.list_cols()
    print("Collections:", [c.name for c in cols.collections])

    # 4. Get collection info
    info = qdrant.col_info()
    print("Collection info:", info)

    # 5. List vectors (scroll)
    listed = qdrant.list(limit=10)
    print("Listed vectors:", listed)

    # 6. Get all (formatted)
    all_memories = qdrant.get_all(limit=10)
    print("All memories:", all_memories)

    # 7. Search for similar vectors
    query_vector = vectors[0]
    results = qdrant.search(query="", vectors=[query_vector], limit=3)
    print("Search results:", results)

    # 8. Get by ID
    got = qdrant.get(vector_id=ids[0])
    print("Get by ID:", got)

    # 9. Update a vector
    new_vector = [random.random() for _ in range(embedding_model_dims)]
    new_payload = {"data": "updated memory", "user_id": "user_0"}
    qdrant.update(vector_id=ids[0], vector=new_vector, payload=new_payload)
    print("Updated vector.")

    # 10. Count
    count = qdrant.count()
    print("Count:", count)

    # 11. Delete a vector
    qdrant.delete(vector_id=ids[1])
    print(f"Deleted vector with ID {ids[1]}")

    # 12. Delete all vectors (reset)
    qdrant.delete_all()
    print("Deleted all vectors (reset collection).")

    # 13. Delete collection
    qdrant.delete_col()
    print("Deleted collection.")


if __name__ == "__main__":
    main()
