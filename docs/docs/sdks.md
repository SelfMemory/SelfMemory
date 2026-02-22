---
sidebar_position: 7
slug: /sdks
---

# SDKs

SelfMemory provides official SDKs for Python and TypeScript/JavaScript.

## Python SDK

The Python SDK is the primary client library. It supports both direct library usage and REST API client mode.

### Installation

```bash
pip install selfmemory
```

### Direct Usage (No Server)

```python
from selfmemory import SelfMemory

memory = SelfMemory()

memory.add("I prefer dark mode for all apps", user_id="user_1")
results = memory.search("UI preferences", user_id="user_1")
```

### Client Mode (REST API)

```python
from selfmemory import SelfMemoryClient

client = SelfMemoryClient(
    api_key="sk_im_your_key_here",
    host="http://localhost:8081"
)

# Add memory
client.add(
    memory_content="Sprint planning is every Monday at 10am",
    tags="work,recurring",
    metadata={"type": "schedule"}
)

# Search
results = client.search("when is sprint planning?")

# Get all memories
all_memories = client.get_all()

# Delete a memory
client.delete(memory_id="mem_abc123")

# Close the client
client.close()
```

### Key Classes

| Class | Purpose |
|-------|---------|
| `SelfMemory` | Direct library usage — no server required |
| `SelfMemoryClient` | REST API client — connects to a running server |

### Resources

- [Quick Start Guide](/Python/QuickStart)
- [Client Usage Guide](/Python/Client)
- [Configuration Options](/Python/Configuration)
- [PyPI Package](https://pypi.org/project/selfmemory/)

---

## TypeScript / JavaScript SDK

The TypeScript SDK is available for Node.js and browser environments.

### Installation

```bash
npm install @selfmemory/client
```

### Usage

```typescript
import { SelfMemoryClient } from '@selfmemory/client'

const client = new SelfMemoryClient({
  apiKey: 'sk_im_your_key_here',
  host: 'http://localhost:8081'
})

// Health check
await client.ping()

// Add a memory
await client.add(
  [{ role: 'user', content: 'Remember to review the PR by Friday' }],
  { metadata: { tags: 'work,code-review' } }
)

// Search memories
const results = await client.search('pending code reviews')

// Get all memories
const allMemories = await client.get_all()
```

### Key Methods

| Method | Description |
|--------|-------------|
| `ping()` | Health check |
| `add(messages, options)` | Store a new memory |
| `search(query, options)` | Semantic search across memories |
| `get_all(options)` | Retrieve all memories |

### Resources

- [npm Package](https://www.npmjs.com/package/@selfmemory/client)
- [GitHub Repository](https://github.com/SelfMemory/SelfMemory)

---

## MCP Integration

SelfMemory supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), allowing AI assistants like Claude, Cursor, and others to read and write memories directly.

### Setup

Add SelfMemory as an MCP server in your AI tool's configuration:

```json
{
  "mcpServers": {
    "selfmemory": {
      "url": "http://localhost:8081/mcp",
      "headers": {
        "Authorization": "Bearer sk_im_your_key_here"
      }
    }
  }
}
```

### Resources

- [MCP Setup Guide](https://docs.selfmemory.com)
- [Model Context Protocol Spec](https://modelcontextprotocol.io)

---

## REST API

All SDKs are thin wrappers around the SelfMemory REST API. If your language isn't covered, you can call the API directly.

```bash
# Add a memory
curl -X POST http://localhost:8081/api/memories \
  -H "Authorization: Bearer sk_im_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "My favorite color is blue"}],
    "metadata": {"tags": "personal,preferences"}
  }'

# Search memories
curl -X POST http://localhost:8081/api/memories/search \
  -H "Authorization: Bearer sk_im_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "favorite color"}'
```

See the full [API Reference](/api-reference) for all available endpoints.
