#!/usr/bin/env python3
"""
InMemory SDK Quick Start - FIXED VERSION
This version ensures data persistence by setting on_disk=True
"""

# Install first: pip install inmemory
from inmemory import Memory


def main():
    print("🚀 InMemory SDK Quick Start - FIXED VERSION")

    # 1. Configure Memory with PERSISTENT storage (on_disk=True is crucial!)
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "my_memories",
                "path": "/tmp/qdrant_persistent",  # Different path to avoid conflicts
                "on_disk": True,  # THIS IS THE KEY FIX - enables persistence!
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

    # 2. Initialize Memory with persistent config
    memory = Memory(config=config)
    print("✅ Memory initialized with PERSISTENT storage")

    # 3. Add some memories
    memories = [
        "I had lunch with Sarah at the Italian restaurant downtown",
        "Team meeting about Q4 roadmap with Mike and Jennifer",
        "Finished reading 'Clean Code' book - great insights on refactoring",
    ]

    memory_ids = []
    for i, content in enumerate(memories, 1):
        result = memory.add(content, user_id="demo_user")
        if result.get("success"):
            memory_ids.append(result.get("memory_id"))
            print(f"✅ Memory {i} added: {result.get('memory_id')}")
        else:
            print(f"❌ Memory {i} failed: {result.get('error', 'Unknown error')}")

    # 4. Get all memories
    all_memories = memory.get_all(user_id="demo_user")
    print(f"\n📊 Total memories stored: {len(all_memories)}")

    if all_memories:
        print("📝 Stored memories:")
        for i, mem in enumerate(all_memories, 1):
            if isinstance(mem, str):
                print(f"   {i}. {mem[:50]}...")
            else:
                content = mem.get("content", str(mem))
                print(f"   {i}. {content[:50]}...")

    # 5. Search memories
    print("\n🔍 Searching memories:")
    results = memory.search("lunch", user_id="demo_user")
    print(f"Found {len(results)} results for 'lunch'")

    if results:
        print("🎯 Search results:")
        for i, result in enumerate(results, 1):
            if isinstance(result, str):
                print(f"   {i}. {result[:50]}...")
            else:
                content = result.get("content", str(result))
                print(f"   {i}. {content[:50]}...")

    # 6. Verify persistence path
    import os

    db_path = "/tmp/qdrant_persistent"
    if os.path.exists(db_path):
        print(f"\n💾 Database files exist at: {db_path}")
        files = os.listdir(db_path)
        print(f"   Files: {files}")
    else:
        print(f"\n❌ Database path not found: {db_path}")

    # 7. Clean up (but don't close - data should persist)
    memory.close()
    print("✅ Done! Data should now persist between runs.")
    print("💡 Run this script again to see if data persists!")


if __name__ == "__main__":
    main()
