---
sidebar_position: 2
---

# Client Usage Guide

Learn how to use `SelfMemoryClient` to connect to a SelfMemory REST API server.

## Overview

`SelfMemoryClient` allows you to connect to a running SelfMemory server with authentication and API key management. This is ideal for:

- Dashboard integrations
- Multi-user applications
- Remote memory access
- Production deployments

## Installation

```bash
pip install selfmemory
```

## Starting the Server

First, start the SelfMemory server (from selfmemory-core directory):

```bash
cd server/
python main.py
```

The server will run on `http://localhost:8081` by default.

## Basic Client Usage

### Initialize the Client

```python
from selfmemory import SelfMemoryClient

# Connect to the server
client = SelfMemoryClient(
    api_key="sk_im_dxNssuz8hFLfEl6vYofXgbTO9m8awbPCT8C9xWlR",
    host="http://localhost:8081"
)
```

### Understanding the Message Format

The server expects memories in a specific format with `messages` structure. Here's the correct way to add memories:

```python
#!/usr/bin/env python3
"""
Fixed SelfMemory Client Example

A working example that matches the server's expected data format.
The server expects 'messages' format, so we convert our memory content accordingly.
"""

import os
from selfmemory import SelfMemoryClient

def main():
    # Initialize client with explicit host to avoid discovery issues
    client = SelfMemoryClient(
        api_key="sk_im_dxNssuz8hFLfEl6vYofXgbTO9m8awbPCT8C9xWlR",
        host="http://localhost:8081"
    )

    print("🚀 Starting SelfMemory Client Example with Fixed Format")
    print("=" * 60)

    # Add memories using the correct format that the server expects
    print("\n📝 Adding memories...")

    # Memory 1: BMW bike
    memory1_data = {
        "messages": [
            {
                "role": "user",
                "content": "I have a BMW bike."
            }
        ],
        "metadata": {
            "tags": "personal,vehicle",
            "people_mentioned": "",
            "topic_category": "personal"
        }
    }

    # Use the client's underlying httpx client to send the correct format
    try:
        response1 = client.client.post("/api/memories", json=memory1_data)
        response1.raise_for_status()
        result1 = response1.json()
        print(f"✅ Added memory 1: {result1.get('message', 'Success')}")
    except Exception as e:
        print(f"❌ Failed to add memory 1: {e}")

    # Memory 2: Amazon location
    memory2_data = {
        "messages": [
            {
                "role": "user",
                "content": "I live in Amazon"
            }
        ],
        "metadata": {
            "tags": "personal,location",
            "people_mentioned": "",
            "topic_category": "personal"
        }
    }

    try:
        response2 = client.client.post("/api/memories", json=memory2_data)
        response2.raise_for_status()
        result2 = response2.json()
        print(f"✅ Added memory 2: {result2.get('message', 'Success')}")
    except Exception as e:
        print(f"❌ Failed to add memory 2: {e}")

    # Search memories using the client's search method
    print("\n🔍 Searching memories...")
    try:
        search_results = client.search("bike")
        print(f"📋 Search results for 'bike': {len(search_results.get('results', []))} found")

        if search_results.get('results'):
            for i, result in enumerate(search_results['results'][:2], 1):
                content = result.get('content', result.get('memory_content', 'No content'))
                score = result.get('score', 'N/A')
                print(f"   {i}. {content}... (score: {score})")
        else:
            print("   No results found")

    except Exception as e:
        print(f"❌ Search failed: {e}")

    # Get all memories
    print("\n📚 Getting all memories...")
    try:
        all_memories = client.get_all()
        total_count = len(all_memories.get('results', []))
        print(f"📊 Total memories: {total_count}")

        if all_memories.get('results'):
            for i, memory in enumerate(all_memories['results'][:3], 1):
                content = memory.get('content', memory.get('memory_content', 'No content'))
                print(f"   {i}. {content}...")

    except Exception as e:
        print(f"❌ Failed to get memories: {e}")

    # Test search with different queries
    print("\n🔍 Testing additional searches...")
    test_queries = ["Amazon", "personal", "location"]

    for query in test_queries:
        try:
            results = client.search(query)
            count = len(results.get('results', []))
            print(f"   '{query}': {count} results")
        except Exception as e:
            print(f"   '{query}': Error - {e}")

    # Clean up (optional)
    print("\n🧹 Cleanup options:")
    print("   Uncomment the line below to delete all memories")
    # client.delete_all()

    # Close client
    client.close()
    print("\n✅ Client closed successfully")
    print("🎉 Example completed!")

if __name__ == "__main__":
    main()
```

## Helper Functions

You can create helper functions to make memory creation easier:

```python
def create_memory_with_messages_format(content: str, tags: str = "", people: str = "", category: str = ""):
    """Helper function to create memory data in the server's expected format."""
    return {
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "metadata": {
            "tags": tags,
            "people_mentioned": people,
            "topic_category": category
        }
    }

def add_memory_direct(client, content: str, tags: str = "", people: str = "", category: str = ""):
    """Helper function to add memory using the correct server format."""
    memory_data = create_memory_with_messages_format(content, tags, people, category)

    try:
        response = client.client.post("/api/memories", json=memory_data)
        response.raise_for_status()
        result = response.json()
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## Client Operations

### Searching Memories

```python
# Basic search
results = client.search("meeting notes")

# Process results
for result in results.get('results', []):
    content = result.get('content', result.get('memory_content'))
    score = result.get('score')
    print(f"Memory: {content} (Score: {score})")
```

### Getting All Memories

```python
# Get all memories
all_memories = client.get_all()

# Iterate through memories
for memory in all_memories.get('results', []):
    print(memory.get('content'))
```

### Deleting Memories

```python
# Delete all memories
client.delete_all()
```

### Closing the Client

```python
# Always close the client when done
client.close()
```

## API Key Management

To get your API key:

1. Log in to the SelfMemory dashboard
2. Navigate to the API Keys page
3. Generate a new API key
4. Copy and use it in your client initialization

See the [API Keys documentation](../Platform/API%20Key%20page.md) for more details.

## Error Handling

Always wrap client operations in try-except blocks:

```python
try:
    results = client.search("query")
    print(f"Found {len(results.get('results', []))} results")
except Exception as e:
    print(f"Error: {e}")
```

## Next Steps

- Explore [Configuration Options](./Configuration.md) for advanced setups
- Learn about [API Key Management](../Platform/API%20Key%20page.md)
- Return to [Quick Start Guide](./QuickStart.md) for basic usage
