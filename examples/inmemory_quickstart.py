#!/usr/bin/env python3
"""
SelfMemory SDK Quick Start - Copy & Paste Ready
FIXED VERSION with persistent storage
"""

# Install first: pip install selfmemory
from selfmemory import Memory


def main():
    print("🚀 SelfMemory SDK Quick Start")

    # 1. Configure Memory to connect to Docker Qdrant
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "shrijayan_memories",
                "embedding_model_dims": 768,
                "host": "localhost",
                "port": 6333,  # Default Qdrant Docker port
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

    # 2. Initialize Memory
    memory = Memory(config=config)
    print("✅ Memory initialized")

    # 3. Add some memories
    memories = [
        "I had lunch with Sarah at the Italian restaurant downtown",
        "Team meeting about Q4 roadmap with Mike and Jennifer",
        "Finished reading 'Clean Code' book - great insights on refactoring",
    ]

    for i, content in enumerate(memories, 1):
        result = memory.add(content, user_id="demo_user")
        if result.get("success"):
            print(f"✅ Memory {i} added")
        else:
            print(f"❌ Memory {i} failed")

    # 4. Search memories
    print("\n🔍 Searching memories:")
    results = memory.search("lunch", user_id="demo_user")
    print(f"Found {len(results['results'])} results for 'lunch'")

    # 5. Get all memories
    all_memories = memory.get_all(user_id="demo_user")
    print(f"Total memories: {len(all_memories['results'])}")

    # 6. Clean up
    memory.close()
    print("✅ Done!")


if __name__ == "__main__":
    main()
