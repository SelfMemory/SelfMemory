---
sidebar_position: 1
---

# Quick Start Guide

Get started with SelfMemory in 5 minutes!

## Installation

```bash
pip install selfmemory
```

## Basic Usage with Qdrant + Ollama

This example shows the recommended setup using Qdrant for vector storage and Ollama for embeddings:

### 1. Start Required Services

```bash
# Start Qdrant (vector database)
docker run -p 6333:6333 qdrant/qdrant

# Start Ollama and pull embedding model
ollama serve
ollama pull nomic-embed-text
```

### 2. Configure SelfMemory

```python
from selfmemory import SelfMemory

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "new__memories",
            "embedding_model_dims": 768,
            "host": "localhost",
            "port": 6333  # Default Qdrant Docker port
        }
    },
    "embedding": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434"
        }
    }
}

memory = SelfMemory(config=config)
```

### 3. Add and Search Memories

```python
# Add memories
result = memory.add("I have a BMW bike.", user_id="demo")
result = memory.add("I live in Amazon", user_id="demo")

# Search memories
results = memory.search("bike", user_id="demo")
print(results)
```

## Zero-Config Usage

For quick testing, SelfMemory works without any configuration:

```python
from selfmemory import SelfMemory

# No config needed - uses defaults
memory = SelfMemory()

# Add memories with metadata
memory.add(
    "I love pizza but hate broccoli",
    user_id="demo",
    tags="food,preferences"
)

memory.add(
    "Meeting with Bob and Carol about Q4 planning tomorrow at 3pm",
    user_id="demo",
    tags="work,meeting",
    people_mentioned="Bob,Carol",
    topic_category="planning"
)

# Search memories
results = memory.search("pizza", user_id="demo")
for result in results["results"]:
    print(f"Memory: {result['content']}")
    print(f"Score: {result['score']}")

# Health check
health = memory.health_check()
print(f"Status: {health['status']}")
```

## Core Operations

### Adding Memories

```python
# Simple add
memory.add("Some memory content", user_id="user123")

# With metadata
memory.add(
    content="Product launch meeting next week",
    user_id="user123",
    tags="work,important",
    people_mentioned="Alice,Bob",
    topic_category="business"
)
```

### Searching Memories

```python
# Basic search
results = memory.search("meeting", user_id="user123")

# Search with limit
results = memory.search("meeting", user_id="user123", limit=5)

# Search by tags
results = memory.search_by_tags(
    ["work", "important"],
    user_id="user123",
    match_all=True
)

# Search by people
results = memory.search_by_people(
    ["Alice", "Bob"],
    user_id="user123"
)
```

### Getting All Memories

```python
# Get all memories for a user
memories = memory.get_all(user_id="user123", limit=100)
```

### Deleting Memories

```python
# Delete specific memory
result = memory.delete(memory_id="memory_123", user_id="user123")

# Delete all memories for a user
result = memory.delete_all(user_id="user123")
```

## Next Steps

- Learn about [Client Usage](./Client.md) for REST API integration
- Explore [Configuration Options](./Configuration.md) for advanced setups
- Check out [API Keys](../Platform/API%20Key%20page.md) for platform usage
