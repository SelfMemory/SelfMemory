# InMemory API Server

This directory contains the managed solution for InMemory, providing a REST API server for hosted memory management.

## Overview

The InMemory API server provides a hosted solution where users can:
- Authenticate using API keys
- Store and search memories via REST API
- Manage their data through a dashboard
- Access the same functionality as the self-hosted solution but through HTTP endpoints

## Architecture

```
Client (Inmry) → HTTP API → InMemory Core → Storage Backend
```

### Components

- **`server.py`**: Main FastAPI application with all endpoints
- **`__init__.py`**: Package initialization and exports
- **Authentication**: Bearer token authentication using API keys
- **Storage**: Uses the same storage backends as self-hosted (file, MongoDB)

## API Endpoints

### Authentication
- `GET /v1/ping/` - Health check (no auth)
- `GET /v1/health/` - Detailed health check (no auth) 
- `POST /v1/auth/generate-key/` - Generate new API key
- `DELETE /v1/auth/revoke-key/` - Revoke current API key

### Memory Operations
- `POST /v1/memories/` - Add a new memory
- `POST /v1/memories/search/` - Search memories
- `GET /v1/memories/` - Get all memories for a user
- `DELETE /v1/memories/{id}` - Delete specific memory
- `DELETE /v1/memories/` - Delete all memories for a user

### Advanced Search
- `POST /v1/memories/temporal-search/` - Temporal search
- `POST /v1/memories/tag-search/` - Search by tags
- `POST /v1/memories/people-search/` - Search by people mentioned

### User Management
- `GET /v1/users/{user_id}/stats` - Get user statistics
- `GET /v1/users/current` - Get current user info

## Usage

### Starting the Server

```python
from inmemory.api import create_app
import uvicorn

app = create_app()
uvicorn.run(app, host="0.0.0.0", port=8000)
```

Or directly:
```python
from inmemory.api.server import run_server

run_server(host="0.0.0.0", port=8000, debug=True)
```

### Client Usage

```python
import os
from inmemory import Inmry

# Set your API key
os.environ["INMEM_API_KEY"] = "your-api-key"

# Initialize client
inmry = Inmry()

# Use the same interface as self-hosted
result = inmry.add("I love pizza", user_id="john")
results = inmry.search("pizza", user_id="john")
```

## Authentication

The API uses Bearer token authentication. Include your API key in the Authorization header:

```
Authorization: Bearer your-api-key
```

API keys are generated with the format: `im_<random-string>`

## Configuration

The API server uses the same configuration system as the self-hosted solution. It will:
1. Auto-detect deployment mode
2. Use appropriate storage backend (file-based for development, MongoDB for production)
3. Initialize with default settings if no config is provided

## Security Considerations

- API keys are hashed before storage
- CORS is configured (update for production)
- Rate limiting should be added for production use
- Use HTTPS in production
- Validate user permissions for cross-user operations

## Production Deployment

1. **Environment Variables**:
   ```bash
   export INMEMORY_STORAGE_TYPE=mongodb
   export INMEMORY_MONGODB_URI=mongodb://...
   ```

2. **Run with Gunicorn**:
   ```bash
   gunicorn inmemory.api.server:create_app --workers 4 --worker-class uvicorn.workers.UvicornWorker
   ```

3. **Docker**:
   ```dockerfile
   FROM python:3.11
   COPY . /app
   WORKDIR /app
   RUN pip install -r requirements.txt
   CMD ["python", "-m", "inmemory.api.server"]
   ```

## Monitoring

- Health check endpoint: `GET /v1/health/`
- API documentation: `/docs` (Swagger UI)
- User analytics through user stats endpoints

## Differences from Self-Hosted

| Feature | Self-Hosted | Managed API |
|---------|-------------|-------------|
| Authentication | None | API Key required |
| Network | Local only | HTTP/REST API |
| Deployment | Single process | Scalable web service |
| User Management | File-based | API key system |
| Monitoring | Local logging | HTTP metrics + logging |

## Error Handling

The API returns standard HTTP status codes:
- `200`: Success
- `400`: Bad Request (validation errors)
- `401`: Unauthorized (invalid/missing API key)
- `404`: Not Found (memory/user not found)
- `500`: Internal Server Error

Error responses include details:
```json
{
  "detail": "Error message",
  "success": false,
  "error": "Detailed error description"
}
