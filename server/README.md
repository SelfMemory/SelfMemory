# InMemory Server

A FastAPI REST API server for InMemory that uses the `inmemory` library internally.

## Overview

This server provides REST endpoints for the InMemory memory management system, following the mem0 architecture pattern:

- **Library First**: Uses the `inmemory` library (from parent directory) internally
- **Clean Separation**: Server logic separate from library logic
- **Dashboard Ready**: Provides endpoints for dashboard integration
- **Zero Setup**: Uses embedded ChromaDB for storage

## Quick Start

### 1. Install Dependencies

```bash
# From the server/ directory
pip install -r requirements.txt

# OR install the inmemory library in development mode
cd .. && pip install -e . && cd server/
```

### 2. Configure Environment

```bash
# Copy and edit environment file
cp .env.example .env
# Edit .env with your MongoDB URI and other settings
```

### 3. Run the Server

```bash
# Method 1: Direct execution
python main.py

# Method 2: Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8081 --reload

# Method 3: With environment variables
MONGODB_URI=mongodb://localhost:27017/inmemory python main.py
```

The server will start on http://localhost:8081

## API Endpoints

### Health Check
```bash
curl http://localhost:8081/v1/health
```

### Authentication
```bash
curl -H "Authorization: Bearer your_api_key" \
     http://localhost:8081/v1/auth/validate
```

### Add Memory
```bash
curl -X POST http://localhost:8081/v1/memories \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "memory_content": "I love pizza",
    "tags": "food,personal",
    "people_mentioned": "Sarah",
    "topic_category": "preferences"
  }'
```

### Search Memories
```bash
curl -X POST http://localhost:8081/v1/search \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "pizza",
    "limit": 10
  }'
```

### Get All Memories
```bash
curl -H "Authorization: Bearer your_api_key" \
     "http://localhost:8081/v1/memories?limit=10&offset=0"
```

### Delete Memory
```bash
curl -X DELETE \
  -H "Authorization: Bearer your_api_key" \
  http://localhost:8081/v1/memories/memory_id_here
```

## Architecture Benefits

### 1. Clean Separation
- **Server**: FastAPI app with REST endpoints
- **Library**: Core inmemory logic (Memory, InmemoryClient classes)
- **Storage**: Embedded ChromaDB (zero external dependencies)

### 2. Dashboard Integration
- **Authentication**: MongoDB-based API key validation
- **Compatible**: Same endpoints as original main.py
- **Reliable**: Uses library's zero-setup Memory class internally

### 3. Development Friendly
- **Hot Reload**: `uvicorn --reload` for development
- **Library Import**: `from inmemory import Memory`
- **Zero Setup**: No complex configuration required

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
# Test the API
pytest test_server.py  # (create tests as needed)

# Manual testing
curl http://localhost:8081/v1/health
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URI` | `mongodb://localhost:27017/inmemory` | MongoDB connection for auth |
| `INMEMORY_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `INMEMORY_SERVER_PORT` | `8081` | Server port |
| `CHROMA_DB_PATH` | `/tmp/inmemory/chromadb` | ChromaDB storage path |
| `LOG_LEVEL` | `INFO` | Logging level |

### Authentication

The server uses MongoDB for API key validation (shared with dashboard):

1. Dashboard creates API keys → MongoDB
2. Server validates API keys → MongoDB
3. Memory operations → Local ChromaDB

## Comparison with mem0

| Feature | mem0/server | inmemory/server |
|---------|-------------|-----------------|
| **Library Import** | `from mem0 import Memory` | `from inmemory import Memory` |
| **Server Pattern** | Separate server/ folder | Separate server/ folder |
| **Storage** | PostgreSQL/Neo4j | ChromaDB (embedded) |
| **Authentication** | Built-in | MongoDB (shared) |
| **Zero Setup** | ✅ | ✅ |

## Dashboard Integration

Your dashboard should connect to this server instead of the old main.py:

```javascript
// Dashboard API calls
const response = await fetch('http://localhost:8081/v1/memories', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    memory_content: 'User message',
    tags: 'dashboard',
    topic_category: 'conversation'
  })
});
```

## Next Steps

1. **Test the server**: `python main.py`
2. **Update dashboard**: Point to `http://localhost:8081` instead of old endpoints
3. **Deploy**: Use this server in production
4. **Scale**: Add load balancing, monitoring as needed
