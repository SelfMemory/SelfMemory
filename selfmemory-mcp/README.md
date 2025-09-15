# SelfMemory MCP Server

A Model Context Protocol (MCP) server that provides memory management capabilities for SelfMemory with OAuth 2.1 authentication.

## Features

- 🔒 **OAuth 2.1 Authentication** - Secure authentication using existing SelfMemory API keys
- 🧠 **Memory Operations** - Add and search personal memories with metadata
- 🏷️ **Rich Metadata** - Support for tags, people, and categories
- ⚡ **High Performance** - Streamable HTTP transport with stateless operation
- 🔍 **Semantic Search** - Advanced search with filters and thresholds
- 🛡️ **User Isolation** - Per-request client creation for secure multi-user support

## Quick Start

### 1. Setup Environment

```bash
# Copy environment configuration
cp .env.example .env

# Edit .env to configure your setup
# SELFMEMORY_API_HOST=http://localhost:8081  # Your core server URL
# MCP_SERVER_PORT=8080                     # MCP server port
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install the local selfmemory package (from parent directory)
pip install -e ../.
```

### 3. Run the Server

```bash
# Start the MCP server
python main.py
```

The server will start on `http://localhost:8080/mcp` by default.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SELFMEMORY_API_HOST` | `http://localhost:8081` | Core SelfMemory server URL |
| `MCP_SERVER_HOST` | `0.0.0.0` | Host to bind the MCP server |
| `MCP_SERVER_PORT` | `8080` | Port for the MCP server |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DEBUG` | `false` | Enable debug mode |

## Tools

### `add_memory`

Store new memories with metadata.

**Parameters:**
- `content` (string, required): The memory content to store
- `tags` (string, optional): Comma-separated tags (e.g., "work,meeting,important")
- `people` (string, optional): Comma-separated people mentioned (e.g., "Alice,Bob")
- `category` (string, optional): Topic category (e.g., "work", "personal", "learning")

**Example:**
```json
{
  "content": "Had a great meeting about the new project",
  "tags": "work,meeting",
  "people": "Sarah,Mike",
  "category": "work"
}
```

### `search_memories`

Search memories using semantic search with optional filters.

**Parameters:**
- `query` (string, required): The search query
- `limit` (integer, optional): Maximum results (default: 10, max: 50)
- `tags` (array, optional): Filter by tags
- `people` (array, optional): Filter by people mentioned
- `category` (string, optional): Filter by category
- `threshold` (float, optional): Minimum similarity score (0.0 to 1.0)

**Example:**
```json
{
  "query": "project meeting",
  "limit": 5,
  "tags": ["work", "important"],
  "people": ["Sarah"],
  "threshold": 0.7
}
```

## Client Usage

### Connection Details

- **Server URL**: `http://localhost:8080/mcp`
- **Transport**: Streamable HTTP
- **Authentication**: Bearer token (SelfMemory API key)

### Example Client Configuration

For MCP clients that support remote servers:

```json
{
  "url": "http://localhost:8080/mcp",
  "headers": {
    "Authorization": "Bearer sk_im_your_api_key_here"
  }
}
```

### API Key Format

SelfMemory API keys can be in either format:
- `sk_im_...` (preferred format)

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │───▶│  SelfMemory MCP  │───▶│  Core Server    │
│                 │    │     Server       │    │  (port 8081)    │
│                 │    │  (port 8080)     │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │  Authentication  │
                       │   & User         │
                       │   Isolation      │
                       └──────────────────┘
```

## Authentication Flow

1. **Client Request**: MCP client sends request with Bearer token
2. **Token Validation**: MCP server validates token against core server using `SelfMemoryTokenVerifier`
3. **User Extraction**: User information is extracted from validated token
4. **Client Creation**: Per-request `SelfMemoryClient` is created with user's token
5. **Memory Operation**: Memory operation is performed with proper user isolation
6. **Response**: Results are returned to the MCP client

## Security Features

- **OAuth 2.1 Compliance**: Full OAuth 2.1 resource server implementation
- **Token Validation**: All tokens are validated against the core server
- **User Isolation**: Each request creates an isolated client session
- **Secure Transport**: HTTPS support for production deployments
- **Request Logging**: Comprehensive logging for security auditing

## Development

### Running in Development Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
export DEBUG=true

# Run the server
python main.py
```

### Testing with curl

```bash
# Test add_memory
curl -X POST http://localhost:8080/mcp \
  -H "Authorization: Bearer sk_im_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "add_memory",
      "arguments": {
        "content": "Test memory",
        "tags": "test",
        "category": "testing"
      }
    }
  }'

# Test search_memories
curl -X POST http://localhost:8080/mcp \
  -H "Authorization: Bearer sk_im_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_memories",
      "arguments": {
        "query": "test",
        "limit": 5
      }
    }
  }'
```

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Check that your API key is valid and active
   - Ensure the core server is running on the configured host
   - Verify the API key format (sk_im_... or inmem_sk_...)

2. **Connection Refused**
   - Check that the core server is running on the configured port
   - Verify the `SELFMEMORY_API_HOST` environment variable
   - Ensure no firewall blocking the connection

3. **Import Errors**
   - Install the selfmemory package: `pip install -e ../.`
   - Check that all dependencies are installed: `pip install -r requirements.txt`

4. **Memory Operations Fail**
   - Verify the core server has proper vector store configuration
   - Check server logs for detailed error messages
   - Ensure the user has proper permissions

### Logs

Server logs are written to stdout with the format:
```
YYYY-MM-DD HH:MM:SS - LEVEL - MESSAGE
```

For production deployments, redirect logs to a file:
```bash
python main.py >> /var/log/selfmemory-mcp.log 2>&1
```

## License

This project is part of the SelfMemory ecosystem and follows the same licensing terms.
