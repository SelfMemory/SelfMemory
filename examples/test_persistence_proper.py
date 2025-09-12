#!/usr/bin/env python3
"""
Proper persistence test - waits for lock release
"""

import os
import shutil
import time

from inmemory import Memory


def test_persistence():
    print("🔍 Testing Qdrant Persistence Properly")

    # Clean up any existing database
    db_path = "/tmp/qdrant_persistence_test"
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
        print(f"🧹 Cleaned up existing database at {db_path}")

    # Test config
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "persistence_test",
                "path": db_path,
                "on_disk": True,
                "embedding_model_dims": 768,
            },
        },
        "embedding": {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text",
                "ollama_base_url": "http://localhost:11434",
            },
        },
    }

    print("📝 Step 1: Create Memory and add data")
    memory = Memory(config=config)

    # Add test memories
    memories = [
        "I had lunch with Sarah at the Italian restaurant",
        "Team meeting about Q4 roadmap with Mike",
        "Finished reading Clean Code book",
    ]

    for i, content in enumerate(memories, 1):
        result = memory.add(content, user_id="test_user")
        if result.get("success"):
            print(f"   ✅ Memory {i} added: {result.get('memory_id')}")
        else:
            print(f"   ❌ Memory {i} failed")

    # Verify data is there
    all_memories = memory.get_all(user_id="test_user")
    print(f"   📊 Memories stored: {len(all_memories.get('results', []))}")

    # Close the memory instance to release the lock
    memory.close()
    print("🔒 Memory closed - lock should be released")

    # Wait a moment for the lock to be fully released
    time.sleep(2)

    print("\n📝 Step 2: Create new Memory instance to test persistence")

    try:
        # Create new instance
        memory2 = Memory(config=config)
        print("✅ New Memory instance created successfully")

        # Check if data persisted
        all_memories2 = memory2.get_all(user_id="test_user")
        persisted_count = len(all_memories2.get("results", []))
        print(f"📊 Memories found in new instance: {persisted_count}")

        if persisted_count > 0:
            print("🎉 SUCCESS: Data persisted between instances!")
            print("📝 Persisted memories:")
            for i, mem in enumerate(all_memories2.get("results", []), 1):
                if isinstance(mem, str):
                    content = mem[:50] + "..." if len(mem) > 50 else mem
                else:
                    content = str(mem)[:50] + "..." if len(str(mem)) > 50 else str(mem)
                print(f"   {i}. {content}")
        else:
            print("❌ FAILED: No data found in new instance")

        # Test search on persisted data
        if persisted_count > 0:
            search_results = memory2.search("lunch", user_id="test_user")
            print(f"🔍 Search results: {len(search_results.get('results', []))}")

        memory2.close()

    except Exception as e:
        print(f"❌ Error creating new instance: {e}")

    # Check database files
    print("\n💾 Final database state:")
    if os.path.exists(db_path):
        print(f"   ✅ Database exists: {db_path}")
        files = os.listdir(db_path)
        print(f"   📁 Files: {files}")

        # Check collection
        collection_path = os.path.join(db_path, "collection")
        if os.path.exists(collection_path):
            collection_files = os.listdir(collection_path)
            print(f"   📂 Collection files: {collection_files}")
    else:
        print(f"   ❌ Database missing: {db_path}")


if __name__ == "__main__":
    test_persistence()
