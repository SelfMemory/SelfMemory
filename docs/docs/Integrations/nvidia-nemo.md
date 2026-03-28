---
sidebar_position: 1
slug: /integrations/nvidia-nemo
---

# NVIDIA NeMo Agent Toolkit

SelfMemory integrates with the [NVIDIA NeMo Agent Toolkit](https://github.com/NVIDIA/NeMo-Agent-Toolkit) memory module, giving you access to NeMo's memory providers (Mem0, Redis, Zep) as alternative backends for your SelfMemory instance.

## Overview

The NeMo Agent Toolkit is NVIDIA's open-source framework for building teams of AI agents. Its memory subsystem stores and retrieves conversation history, user preferences, and long-term context across agent interactions.

SelfMemory's NeMo adapter wraps NeMo's async `MemoryEditor` interface behind the standard `MemoryBase` API, so you can swap between native SelfMemory and NeMo-backed memory with a config change.

### Supported NeMo Memory Providers

| Provider | Package | Description |
|----------|---------|-------------|
| **Mem0** | `nvidia-nat-mem0ai` | Self-improving memory with semantic understanding |
| **Redis** | `nvidia-nat-redis` | Fast in-memory operations with vector search |
| **Zep** | `nvidia-nat-zep-cloud` | Cloud-hosted conversation memory |

## Installation

```bash
# Install SelfMemory with NeMo support
pip install selfmemory[nemo]
```

This installs `nvidia-nat` and its dependencies. You also need the specific provider plugin:

```bash
# For Mem0 backend
pip install nvidia-nat-mem0ai

# For Redis backend
pip install nvidia-nat-redis

# For Zep backend
pip install nvidia-nat-zep-cloud
```

## Quick Start

### Using the Memory Factory

```python
from selfmemory.utils.factory import MemoryFactory

# Create a NeMo Mem0-backed memory instance
memory = MemoryFactory.create("nemo_mem0", {
    "api_key": "your-mem0-api-key",
})

# Use it like any SelfMemory instance
memory.add("I love Italian food", user_id="alice")
results = memory.search("food preferences", user_id="alice")
```

### Using Configuration

```python
from selfmemory import SelfMemory
from selfmemory.configs.base import SelfMemoryConfig
from selfmemory.configs.nemo import NemoMemoryConfig
from selfmemory.memory.nemo_adapter import NemoMemoryAdapter

config = NemoMemoryConfig(
    provider="mem0",
    config={
        "api_key": "your-mem0-api-key",
    },
)

memory = NemoMemoryAdapter(config)
memory.add("Meeting with Sarah at 3pm", user_id="bob")
```

### Using YAML Configuration

Add to your `~/.selfmemory/config.yaml`:

```yaml
nemo_memory:
  provider: mem0
  config:
    api_key: ${NEMO_MEMORY_API_KEY}
```

## Provider Configuration

### Mem0

```python
from selfmemory.utils.factory import MemoryFactory

memory = MemoryFactory.create("nemo_mem0", {
    "api_key": "your-mem0-api-key",
    "organization": "your-org",
    "project": "your-project",
})
```

**Environment Variables:**

```bash
export NEMO_MEMORY_API_KEY="your-mem0-api-key"
```

### Redis

```python
from selfmemory.utils.factory import MemoryFactory

memory = MemoryFactory.create("nemo_redis", {
    "host": "localhost",
    "port": 6379,
    "password": "your-redis-password",
})
```

**Starting Redis with vector search:**

```bash
docker run -p 6379:6379 redis/redis-stack:latest
```

### Zep

```python
from selfmemory.utils.factory import MemoryFactory

memory = MemoryFactory.create("nemo_zep", {
    "api_key": "your-zep-api-key",
    "base_url": "https://api.getzep.com",
})
```

## API Reference

The NeMo adapter implements the full `MemoryBase` interface. All operations work identically to native SelfMemory.

### add()

```python
memory.add(
    "I prefer dark mode in all my apps",
    user_id="alice",
    tags="preferences,ui",
    people_mentioned="Alice",
    topic_category="preferences",
    metadata={"source": "chat"},
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `messages` | `str`, `dict`, or `list[dict]` | Memory content (string, single message, or conversation) |
| `user_id` | `str` | Required. User identifier for isolation |
| `tags` | `str` | Optional. Comma-separated tags |
| `people_mentioned` | `str` | Optional. Comma-separated names |
| `topic_category` | `str` | Optional. Topic category |
| `metadata` | `dict` | Optional. Additional key-value metadata |

### search()

```python
results = memory.search(
    "ui preferences",
    user_id="alice",
    limit=5,
    tags=["preferences"],
    topic_category="preferences",
)

for result in results["results"]:
    print(f"{result['content']} (id: {result['id']})")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | `""` | Search query |
| `user_id` | `str` | required | User identifier |
| `limit` | `int` | `10` | Max results |
| `tags` | `list[str]` | `None` | Filter by tags |
| `people_mentioned` | `list[str]` | `None` | Filter by people |
| `topic_category` | `str` | `None` | Filter by category |
| `threshold` | `float` | `None` | Min similarity score |

**Response:**

```json
{
  "results": [
    {
      "id": "mem_abc123",
      "content": "I prefer dark mode in all my apps",
      "metadata": {
        "data": "I prefer dark mode in all my apps",
        "user_id": "alice",
        "tags": "preferences,ui",
        "topic_category": "preferences"
      }
    }
  ]
}
```

### delete()

```python
memory.delete("mem_abc123")
```

### delete_all()

```python
memory.delete_all(user_id="alice")
```

### get_all()

```python
results = memory.get_all(user_id="alice", limit=50)
```

### health_check()

```python
status = memory.health_check()
# {"status": "healthy", "provider": "nemo_mem0"}
```

## Data Model Mapping

SelfMemory automatically converts between its data format and NeMo's `MemoryItem` model:

| SelfMemory | NeMo MemoryItem | Direction |
|------------|-----------------|-----------|
| `messages` (str/list) | `memory` + `conversation` | SelfMemory -> NeMo |
| `user_id` | `user_id` | Bidirectional |
| `tags` (comma-separated) | `tags` (list) | Bidirectional |
| `metadata` (dict) | `metadata` (dict) | Bidirectional |
| `people_mentioned` | `metadata.people_mentioned` | SelfMemory -> NeMo |
| `topic_category` | `metadata.topic_category` | SelfMemory -> NeMo |

## Architecture

```
+---------------------+      +-------------------+      +------------------+
|   Your Application  | ---> | NemoMemoryAdapter | ---> | NeMo MemoryEditor|
|                     |      | (MemoryBase)      |      | (async)          |
+---------------------+      +-------------------+      +------------------+
                                      |                         |
                              sync-to-async bridge       +------+------+
                              (asyncio.to_thread /       |      |      |
                               ThreadPoolExecutor)     Mem0  Redis   Zep
```

The adapter handles:

- **Sync-to-async bridging** — NeMo's `MemoryEditor` is fully async. The adapter runs async operations via `asyncio.run()` or `ThreadPoolExecutor` when inside an existing event loop (e.g., FastAPI).
- **Data model translation** — Converts between SelfMemory's string-based tags and NeMo's list-based tags, maps metadata fields, and extracts content from conversation lists.
- **User isolation** — Passes `user_id` to all NeMo operations, maintaining SelfMemory's per-user memory isolation.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NEMO_MEMORY_API_KEY` | API key for the NeMo memory provider |
| `NEMO_MEMORY_HOST` | Host URL for the memory provider |

These are used as fallbacks when not specified in the config dict.

## Python Version Requirements

- SelfMemory core: Python 3.10+
- NeMo integration: Python 3.11+ (required by `nvidia-nat`)

The NeMo adapter is an optional dependency. Projects on Python 3.10 can use all other SelfMemory features.

## Comparison with Native SelfMemory

| Feature | Native SelfMemory | NeMo Adapter |
|---------|-------------------|--------------|
| Vector stores | 29 providers (Qdrant, Chroma, Pinecone, etc.) | Depends on NeMo provider |
| Embeddings | 15+ providers (Ollama, OpenAI, etc.) | Managed by NeMo provider |
| Setup complexity | Configure vector store + embeddings separately | Single provider config |
| Async support | Sync API | Sync API (wraps NeMo's async internally) |
| Encryption | Built-in Fernet encryption | Depends on provider |
| LLM extraction | Optional fact extraction via LLM | Depends on provider |

**When to use NeMo adapter:**

- You are building agents with NVIDIA's NeMo Agent Toolkit
- You want a managed memory service (Mem0 Cloud, Zep Cloud)
- You need Redis-based memory for high-throughput scenarios
- You want to evaluate different memory backends quickly

**When to use native SelfMemory:**

- You need fine-grained control over vector stores and embeddings
- You want to use local/self-hosted infrastructure
- You need built-in encryption
- You want LLM-based intelligent fact extraction

## Troubleshooting

### ImportError: No module named 'nat'

```bash
pip install selfmemory[nemo]
```

The `nvidia-nat` package is required. Make sure you're on Python 3.11+.

### Provider-specific import errors

Each NeMo provider requires its own package:

```bash
# Missing Mem0
pip install nvidia-nat-mem0ai

# Missing Redis
pip install nvidia-nat-redis

# Missing Zep
pip install nvidia-nat-zep-cloud
```

### Event loop errors in FastAPI

The adapter automatically handles this by detecting running event loops and using a `ThreadPoolExecutor` fallback. If you still encounter issues, ensure you're using the latest version of SelfMemory.

## Next Steps

- [Getting Started](../getting-started.md) — Set up SelfMemory
- [Configuration Guide](../Python/Configuration.md) — Learn about all config options
- [API Reference](../api-reference.md) — Full REST API documentation
- [NeMo Agent Toolkit Docs](https://docs.nvidia.com/nemo/agent-toolkit/latest/) — NVIDIA's official documentation
