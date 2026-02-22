---
sidebar_position: 2
slug: /getting-started
---

# Getting Started

Get up and running with SelfMemory in under 5 minutes.

## Installation

```bash
pip install selfmemory
```

## Option 1: Direct Library Usage

Use SelfMemory directly in your Python code — no server needed.

### Zero-Config (Quickest)

```python
from selfmemory import SelfMemory

memory = SelfMemory()

# Add memories
memory.add("I love pizza but hate broccoli", user_id="demo")
memory.add("Meeting with Bob tomorrow at 3pm", user_id="demo")

# Search memories
results = memory.search("pizza", user_id="demo")
for result in results["results"]:
    print(f"{result['content']} (score: {result['score']})")
```

### With Qdrant + Ollama (Recommended)

For production use, run Qdrant for vector storage and Ollama for local embeddings:

```bash
# Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# Start Ollama and pull an embedding model
ollama serve
ollama pull nomic-embed-text
```

```python
from selfmemory import SelfMemory

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "memories",
            "embedding_model_dims": 768,
            "host": "localhost",
            "port": 6333
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

## Option 2: Client + Server Mode

For multi-user apps, dashboards, and production deployments, run the SelfMemory server and connect via the client.

### Start the Server

```bash
cd selfmemory-core/server/
python main.py
```

The server runs on `http://localhost:8081` by default.

### Connect with the Python Client

```python
from selfmemory import SelfMemoryClient

client = SelfMemoryClient(
    api_key="your-api-key",
    host="http://localhost:8081"
)

# Search memories
results = client.search("meeting notes")

# Get all memories
all_memories = client.get_all()

# Close when done
client.close()
```

### Connect with the TypeScript Client

```typescript
import { SelfMemoryClient } from '@selfmemory/client'

const client = new SelfMemoryClient({
  apiKey: 'your-api-key',
  host: 'http://localhost:8081'
})

// Add a memory
await client.add(
  [{ role: 'user', content: 'Remember this for me' }],
  { metadata: { tags: 'important' } }
)

// Search
const results = await client.search('what should I remember?')
```

## Get Your API Key

1. Sign up at [selfmemory.com](https://selfmemory.com)
2. Create a project in the dashboard
3. Go to **API Keys** and generate a new key
4. Use it in your client initialization

See the [API Keys documentation](./Platform/API%20Key%20page.md) for details.

## Next Steps

- **[Python SDK → QuickStart](./Python/QuickStart.md)** — Full walkthrough with code examples
- **[Python SDK → Client](./Python/Client.md)** — REST API client usage
- **[Python SDK → Configuration](./Python/Configuration.md)** — Advanced configuration
- **[API Reference](/api-reference)** — Complete REST API documentation
- **[SDKs](/sdks)** — All available SDKs
