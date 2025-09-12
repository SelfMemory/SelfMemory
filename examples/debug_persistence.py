#!/usr/bin/env python3
"""
Debug script to identify persistence issues
"""

import os
import shutil

from selfmemory import Memory


def debug_qdrant_creation():
    print("🔍 Debugging Qdrant Vector Store Creation")

    # Clean up any existing database
    db_path = "/tmp/qdrant_debug"
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
        print(f"🧹 Cleaned up existing database at {db_path}")

    # Test config
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "debug_memories",
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

    print("📋 Config being used:")
    print(f"   Collection: {config['vector_store']['config']['collection_name']}")
    print(f"   Path: {config['vector_store']['config']['path']}")
    print(f"   On Disk: {config['vector_store']['config']['on_disk']}")

    # Initialize Memory
    memory = Memory(config=config)
    print("✅ Memory initialized")

    # Check what actually got created
    print("\n🔍 Checking vector store configuration:")
    print(f"   Vector Store Type: {type(memory.vector_store)}")
    print(f"   Collection Name: {memory.vector_store.collection_name}")
    print(f"   On Disk Setting: {memory.vector_store.on_disk}")
    print(f"   Is Local: {memory.vector_store.is_local}")

    # Check if database path exists
    print("\n💾 Database path check:")
    if os.path.exists(db_path):
        print(f"   ✅ Path exists: {db_path}")
        files = os.listdir(db_path)
        print(f"   📁 Files: {files}")
    else:
        print(f"   ❌ Path does not exist: {db_path}")

    # Add a test memory
    print("\n📝 Adding test memory...")
    result = memory.add("Test memory for debugging persistence", user_id="debug_user")
    print(f"   Add result: {result}")

    # Check database after adding
    print("\n💾 Database after adding memory:")
    if os.path.exists(db_path):
        print(f"   ✅ Path exists: {db_path}")
        files = os.listdir(db_path)
        print(f"   📁 Files: {files}")

        # Check collection directory
        collection_path = os.path.join(db_path, "collection")
        if os.path.exists(collection_path):
            print("   📂 Collection directory exists")
            collection_files = os.listdir(collection_path)
            print(f"   📄 Collection files: {collection_files}")
        else:
            print("   ❌ Collection directory missing")
    else:
        print(f"   ❌ Path does not exist: {db_path}")

    # Get all memories
    all_memories = memory.get_all(user_id="debug_user")
    print(f"\n📊 Retrieved memories: {len(all_memories.get('results', []))}")

    # Close memory
    memory.close()
    print("🔒 Memory closed")

    # Check persistence after closing
    print("\n💾 Database after closing:")
    if os.path.exists(db_path):
        print(f"   ✅ Path still exists: {db_path}")
        files = os.listdir(db_path)
        print(f"   📁 Files: {files}")
    else:
        print("   ❌ Path disappeared after closing!")

    # Test persistence by creating new instance
    print("\n🔄 Testing persistence with new Memory instance...")
    memory2 = Memory(config=config)
    all_memories2 = memory2.get_all(user_id="debug_user")
    print(f"📊 Memories from new instance: {len(all_memories2.get('results', []))}")

    if len(all_memories2.get("results", [])) > 0:
        print("✅ PERSISTENCE WORKING!")
    else:
        print("❌ PERSISTENCE FAILED!")

    memory2.close()


if __name__ == "__main__":
    debug_qdrant_creation()
