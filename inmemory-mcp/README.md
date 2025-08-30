# InMemory MCP Server

A modern MCP (Model Context Protocol) server for InMemory, providing memory management capabilities for AI agents and applications.

## Features

- **Modern FastMCP Implementation**: Built using FastMCP for clean, maintainable code
- **Lazy Initialization**: Safe initialization with proper error handling
- **Context Management**: Proper user and client context management using contextvars
- **Multiple Memory Operations**: Add, search, list, and delete memories
- **Flexible Configuration**: Support for multiple embedding providers (Ollama, OpenAI)
- **SSE Transport**: Server-Sent Events for real-time communication

## Installation

1. **Install Dependencies**:
   ```bash
   cd inmemory-core/inmemory-mcp
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start Required Services**:
   - **Qdrant**: Vector database for storing embeddings
     ```bash
     docker run -p 6333:6333 qdrant/qdrant
     ```
   - **Ollama** (if using Ollama embeddings):
     ```bash
     ollama serve
     ollama pull nomic-embed-text
     ```

## Usage

### Running the Server

```bash
python main.py
```

The server will start on `http://localhost:8080` by default.

### MCP Tools Available

1. **add_memory(text: str)** - Add a new memory
2. **search_memory(query: str, limit: int = 5)** - Search through memories
3. **list_memories(limit: int = 10)** - List all memories
4. **delete_memory(memory_id: str)** - Delete a specific memory
5. **delete_all_memories()** - Delete all memories

### MCP Client Configuration

To use with MCP clients, configure the SSE endpoint:

```
http://localhost:8080/mcp/{client_name}/sse/{user_id}
```

Example:
```
http://localhost:8080/mcp/claude/sse/user123
```

## Configuration

### Environment Variables

- `QDRANT_HOST`: Qdrant server host (default: localhost)
- `QDRANT_PORT`: Qdrant server port (default: 6333)
- `EMBEDDING_PROVIDER`: Embedding provider (ollama/openai)
- `EMBEDDING_MODEL`: Model name for embeddings
- `OLLAMA_HOST`: Ollama server URL
- `OPENAI_API_KEY`: OpenAI API key (if using OpenAI)

### Embedding Providers

#### Ollama (Default)
```env
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_HOST=http://localhost:11434
```

#### OpenAI
```env
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
```

## Architecture

The MCP server follows the mem0/openmemory pattern:

- **FastMCP**: Modern MCP implementation
- **Context Variables**: User and client context management
- **Lazy Loading**: Safe initialization of memory client
- **Error Handling**: Comprehensive error handling and logging
- **Monorepo Structure**: Direct imports from parent inmemory package

## API Endpoints

- `GET /` - Server information
- `GET /health` - Health check
- `GET /mcp/{client_name}/sse/{user_id}` - SSE connection for MCP
- `POST /mcp/messages/` - MCP message handling

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're running from the correct directory and the inmemory package is available
2. **Connection Errors**: Check that Qdrant and Ollama services are running
3. **Memory Client Initialization**: Check logs for specific error messages

### Logs

The server provides detailed logging. Check the console output for:
- Memory client initialization status
- Tool execution results
- Error messages and stack traces

## Development

### Project Structure
```
inmemory-core/
├── inmemory/              # Core package
└── inmemory-mcp/          # MCP server
    ├── main.py            # Main server implementation
    ├── requirements.txt   # Dependencies
    ├── .env.example       # Configuration template
    └── README.md          # This file
```

### Key Benefits of This Structure

- ✅ **No Import Errors**: Direct relative imports from parent package
- ✅ **Modern Implementation**: FastMCP with proper SSE transport
- ✅ **Robust Error Handling**: Graceful degradation when services unavailable
- ✅ **Easy Development**: Everything in one monorepo
- ✅ **Proven Pattern**: Following mem0's successful architecture
