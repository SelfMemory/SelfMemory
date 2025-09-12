#!/usr/bin/env python3
"""
InMemory Client Quick Start - Copy & Paste Ready

Simple example showing how to use the InmemoryClient for the managed/hosted
InMemory service.

Prerequisites:
- Set INMEM_API_KEY environment variable
- Optionally set INMEMORY_API_HOST for local development

Usage:
    export INMEM_API_KEY="your_api_key_here"
    python examples/inmemory_client_quickstart.py
"""

import os

from inmemory import InmemoryClient


def main():
    print("🚀 InMemory Client Quick Start")

    # 1. Get API credentials
    api_key = os.getenv("INMEM_API_KEY")
    api_host = os.getenv("INMEMORY_API_HOST")  # Optional for local development

    if not api_key:
        print("❌ Please set INMEM_API_KEY environment variable")
        print("   export INMEM_API_KEY='your_api_key_here'")
        return

    # 2. Initialize client
    try:
        if api_host:
            client = InmemoryClient(api_key=api_key, host=api_host)
            print(f"✅ Connected to: {api_host}")
        else:
            client = InmemoryClient(api_key=api_key)
            print("✅ Connected to production API")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # 3. Add some memories
    print("\n📝 Adding memories...")
    memories = [
        {
            "content": "Had lunch with Sarah at the Italian restaurant downtown",
            "tags": "food,personal,restaurant",
            "people_mentioned": "Sarah",
            "topic_category": "personal",
        },
        {
            "content": "Team meeting about Q4 roadmap with Mike and Jennifer",
            "tags": "work,meeting,planning",
            "people_mentioned": "Mike,Jennifer",
            "topic_category": "work",
        },
        {
            "content": "Finished reading 'Clean Code' book - great insights on refactoring",
            "tags": "learning,books,programming",
            "people_mentioned": "",
            "topic_category": "education",
        },
    ]

    memory_ids = []
    for i, memory in enumerate(memories, 1):
        result = client.add(
            memory["content"],
            tags=memory["tags"],
            people_mentioned=memory["people_mentioned"],
            topic_category=memory["topic_category"],
        )

        if result.get("success"):
            memory_ids.append(result.get("memory_id"))
            print(f"✅ Memory {i} added")
        else:
            print(f"❌ Memory {i} failed: {result.get('error')}")

    # 4. Search memories
    print("\n🔍 Searching memories:")

    # Basic search
    results = client.search("lunch")
    print(f"Found {len(results.get('results', []))} results for 'lunch'")

    # Tag-based search
    work_results = client.search_by_tags(["work"])
    print(f"Found {len(work_results.get('results', []))} work-related memories")

    # People-based search
    people_results = client.search_by_people(["Sarah", "Mike"])
    print(f"Found {len(people_results.get('results', []))} memories mentioning people")

    # 5. Get all memories
    all_memories = client.get_all()
    print(f"\nTotal memories: {len(all_memories.get('results', []))}")

    # 6. Get statistics
    stats = client.get_stats()
    if "error" not in stats:
        print(f"Memory count: {stats.get('memory_count', 'N/A')}")
        print(f"Status: {stats.get('status', 'N/A')}")

    # 7. Clean up test memories
    print("\n🧹 Cleaning up...")
    deleted_count = 0
    for memory_id in memory_ids:
        if memory_id:
            result = client.delete(memory_id)
            if result.get("success"):
                deleted_count += 1
    print(f"Deleted {deleted_count} test memories")

    # 8. Close client
    client.close()
    print("✅ Done!")


if __name__ == "__main__":
    main()
