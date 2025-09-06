# InMemory Server

A multi-user FastAPI REST API server for InMemory following the mem0 pattern with complete user isolation.

## Overview

This server provides REST endpoints for the InMemory memory management system with full multi-user support:

- **Multi-User Architecture**: Complete user isolation with user-scoped Memory instances
- **User Context Required**: All operations require `user_id` for memory isolation
- **Environment Configuration**: All settings via environment variables
- **mem0 Compatible API**: Follows mem0's multi-user API patterns
- **SDK Integration**: Uses the `inmemory` library directly with user isolation

## Quick Start

### 1. Install Dependencies

```bash
# From the server/ directory
pip install -r requirements.txt

# Install the inmemory library in development mode
cd .. && pip install -e . && cd server/
```

### 2. Configure Environment

```bash
# Copy and edit environment file
cp .env.example .env
# Edit .env with your Qdrant and Ollama settings
```

### 3. Start Required Services

```bash
# Start Qdrant (if not running)
docker run -p 6333:6333 qdrant/qdrant

# Start Ollama (if not running)
ollama serve
ollama pull nomic-embed-text
```

### 4. Run the Server

```bash
# Method 1: Direct execution
python main.py

# Method 2: Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8081 --reload

# Method 3: With custom environment
QDRANT_HOST=localhost OLLAMA_HOST=http://localhost:11434 python main.py
```

The server will start on http://localhost:8081

## API Endpoints

### Health Check
```bash
curl http://localhost:8081/health
```

### Add Memory (Multi-User)
```bash
curl -X POST http://localhost:8081/memories \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I love pizza"}
    ],
    "user_id": "alice",
    "metadata": {"tags": "food,personal"}
  }'
```

### Search Memories (Multi-User)
```bash
curl -X POST http://localhost:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "pizza",
    "user_id": "alice",
    "limit": 10
  }'
```

### Get All Memories (Multi-User)
```bash
curl "http://localhost:8081/memories?user_id=alice&limit=10"
```

### Get Specific Memory (Multi-User)
```bash
curl "http://localhost:8081/memories/memory_id_here?user_id=alice"
```

### Delete Memory (Multi-User)
```bash
curl -X DELETE "http://localhost:8081/memories/memory_id_here?user_id=alice"
```

### Delete All Memories (Multi-User)
```bash
curl -X DELETE "http://localhost:8081/memories?user_id=alice"
```

### Reset User Memories
```bash
curl -X POST "http://localhost:8081/reset?user_id=alice"
```

### Get Statistics
```bash
curl http://localhost:8081/stats
```

### Configure Server
```bash
curl -X POST http://localhost:8081/configure \
  -H "Content-Type: application/json" \
  -d '{
    "embedding": {
      "provider": "ollama",
      "config": {"model": "nomic-embed-text"}
    },
    "vector_store": {
      "provider": "qdrant",
      "config": {"host": "localhost", "port": 6333}
    }
  }'
```

## Architecture

### Multi-User Design (Following mem0)
- **User-Scoped Instances**: Each request creates `Memory(user_id=user_id)` for complete isolation
- **No Global State**: No shared memory instances between users
- **Environment Configuration**: All settings via environment variables
- **Direct SDK Usage**: Uses `inmemory.Memory` class with user isolation
- **Ownership Validation**: Users can only access their own memories
- **mem0 API Compatibility**: Follows mem0's multi-user patterns

### Configuration
```python
DEFAULT_CONFIG = {
    "embedding": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434"
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "localhost",
            "port": 6333,
            "collection_name": "inmemory_memories"
        }
    }
}
```

### Multi-User Isolation

Each user gets completely isolated memory:

```python
# User Alice's memories
alice_memory = Memory(user_id="alice")
alice_memory.add("I love pizza")

# User Bob's memories  
bob_memory = Memory(user_id="bob")
bob_memory.add("I love sushi")

# Users can only see their own memories
alice_results = alice_memory.search("food")  # Only Alice's memories
bob_results = bob_memory.search("food")      # Only Bob's memories
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INMEMORY_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `INMEMORY_SERVER_PORT` | `8081` | Server port |
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant server port |
| `QDRANT_COLLECTION` | `inmemory_memories` | Qdrant collection name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |
| `LOG_LEVEL` | `INFO` | Logging level |

## Development

### Local Development
```bash
# Install in development mode
cd .. && pip install -e . && cd server/

# Run with hot reload
uvicorn main:app --reload --port 8081
```

### Testing
```bash
# Test the API endpoints
curl http://localhost:8081/health
curl http://localhost:8081/docs  # OpenAPI documentation
```

### Docker Support (Future)
```bash
# Build and run (when Dockerfile is added)
docker build -t inmemory-server .
docker run -p 8081:8081 inmemory-server
```

## Key Differences from Old Server

### Removed
- ❌ MongoDB authentication complexity
- ❌ User management and API keys
- ❌ Multiple initialization patterns
- ❌ Hardcoded configurations
- ❌ Complex dashboard compatibility layers

### Added
- ✅ Single global Memory instance (mem0 pattern)
- ✅ Environment-based configuration
- ✅ Clean Pydantic models
- ✅ Direct Memory class usage
- ✅ Proper error handling
- ✅ Configuration endpoint
- ✅ Simple, maintainable code

## Dashboard Integration

Your dashboard can connect to this server using either endpoint format:

```javascript
// Standard endpoints
const response = await fetch('http://localhost:8081/memories', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    memory_content: 'User message',
    tags: 'dashboard',
    topic_category: 'conversation'
  })
});

// v1 endpoints (for compatibility)
const response = await fetch('http://localhost:8081/v1/memories', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    memory_content: 'User message',
    tags: 'dashboard'
  })
});
```

## Next Steps

1. **Test the server**: `python main.py`
2. **Update dashboard**: Point to `http://localhost:8081` 
3. **Add authentication**: If needed, add API key middleware
4. **Scale**: Add load balancing, monitoring as needed
5. **Deploy**: Use this server in production

## Documentation

- **API Docs**: http://localhost:8081/docs (Swagger UI)
- **ReDoc**: http://localhost:8081/redoc (Alternative docs)
- **Health**: http://localhost:8081/health (Health check)
