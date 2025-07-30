# Enhanced Memory MCP Server with SSE Support

A powerful memory management MCP (Model Context Protocol) server that supports remote connections via Server-Sent Events (SSE) transport. Store, search, and retrieve memories with rich metadata including tags, people mentions, topic categories, and temporal data.

## Features

- 🌐 **SSE Transport**: Remote client connectivity (Claude Desktop, custom clients)
- 🧠 **Rich Memory Storage**: Metadata with tags, people, topics, temporal data
- 🔍 **Advanced Search**: Semantic, temporal, tag-based, and people-based filtering
- 🚫 **Duplicate Detection**: Prevents storing similar memories
- ⚙️ **Configurable**: Host/port binding, debug mode
- 🚀 **Scalable**: Web service deployment ready

## Quick Start

### 1. Installation

```bash
# Install dependencies
uv sync
# or
pip install -e .
```

### 2. Start the Server

```bash
# Default configuration (localhost:8080)
python server.py

# Custom host and port
python server.py --host 0.0.0.0 --port 3000

# Debug mode
python server.py --debug
```

### 3. Connect Clients

- **SSE Endpoint**: `http://your-server-ip:port/sse`
- **Example**: `http://localhost:8080/sse`

## Memory Management Tools

### 🧠 Add Memory
Store memories with rich metadata:
```
add_memory(
    memory_content="Meeting notes from project discussion",
    tags="work,meeting,project-alpha",
    people_mentioned="John,Sarah",
    topic_category="work"
)
```

### 🔍 Search Memories
Comprehensive search with multiple filters:
```
search_memories(
    query="project updates",
    limit=5,
    tags="work,meeting",
    people_mentioned="John",
    topic_category="work",
    temporal_filter="this_week"
)
```

### ⏰ Temporal Search
Time-based memory retrieval:
```
temporal_search(
    temporal_query="yesterday",
    semantic_query="meeting notes",
    limit=3
)
```

### 🏷️ Search by Tags
Tag-based filtering:
```
search_by_tags(
    tags="work,project",
    match_all_tags=True,  # AND logic
    semantic_query="updates"
)
```

### 👥 Search by People
Find memories mentioning specific people:
```
search_by_people(
    people="John,Sarah",
    semantic_query="project discussion"
)
```

### 📂 Search by Topic
Topic category filtering:
```
search_by_topic(
    topic_category="work",
    semantic_query="meeting outcomes"
)
```

## Supported Temporal Queries

- **Days**: `today`, `yesterday`
- **Weeks**: `this_week`, `weekends`, `weekdays`
- **Quarters**: `q1`, `q2`, `q3`, `q4`
- **Time of day**: `morning`, `afternoon`, `evening`
- **Days of week**: `monday`, `tuesday`, etc.

## Configuration Options

### Command Line Arguments

```bash
python server.py [OPTIONS]

Options:
  --host TEXT         Host to bind to (default: 0.0.0.0)
  --port INTEGER      Port to listen on (default: 8080)
  --debug             Enable debug mode
  --help              Show help message
```

### Environment Requirements

- **Python**: 3.13+
- **Qdrant**: Vector database for similarity search
- **Ollama**: Local embeddings model

## Client Integration

### Claude Desktop Configuration

Add to your MCP settings:
```json
{
  "servers": {
    "memory-server": {
      "transport": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

### Custom Client Example

Check `mcp-sse/client.py` for a reference implementation of connecting to the SSE endpoint.

## Architecture

```
┌─────────────────┐    HTTP/SSE    ┌──────────────────┐
│   MCP Client    │◄──────────────►│   Memory Server  │
│ (Claude Desktop)│                │   (Starlette)    │
└─────────────────┘                └──────────────────┘
                                           │
                                           ▼
                                   ┌──────────────────┐
                                   │  Enhanced Search │
                                   │     Engine       │
                                   └──────────────────┘
                                           │
                                           ▼
                                   ┌──────────────────┐
                                   │  Qdrant Vector   │
                                   │    Database      │
                                   └──────────────────┘
```

## Key Files

- **`server.py`**: Main SSE MCP server implementation
- **`pyproject.toml`**: Project dependencies and configuration
- **`add_memory_to_collection.py`**: Memory storage with metadata
- **`src/search/enhanced_search_engine.py`**: Advanced search capabilities
- **`src/shared/duplicate_detector.py`**: Duplicate prevention
- **`src/shared/temporal_utils.py`**: Time-based filtering

## Development

### Running Tests
```bash
# Test basic functionality
python server.py --debug

# Monitor logs
tail -f server.log
```

### Adding New Features
1. Add new tools as `@mcp.tool()` decorated functions in `server.py`
2. Implement business logic in separate modules
3. Update documentation and tests

## Deployment

### Local Development
```bash
python server.py --host localhost --port 8080 --debug
```

### Production Deployment
```bash
# Bind to all interfaces
python server.py --host 0.0.0.0 --port 8080

# Using process manager (systemd, supervisor, etc.)
ExecStart=python /path/to/server.py --host 0.0.0.0 --port 8080
```

### Docker Deployment
```bash
# Build image
docker build -t memory-mcp-server .

# Run container
docker run -p 8080:8080 memory-mcp-server
```

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   python server.py --port 8081
   ```

2. **Cannot connect from remote client**
   ```bash
   python server.py --host 0.0.0.0 --port 8080
   ```

3. **Qdrant connection issues**
   - Ensure Qdrant is running
   - Check connection settings in `qdrant_db.py`

4. **Ollama embedding errors**
   - Verify Ollama is installed and running
   - Check model availability

### Logs and Debugging

Enable debug mode for detailed logging:
```bash
python server.py --debug
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Update documentation
5. Submit pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- 📖 Documentation: Check `mem-mcp-Memory.md` for detailed implementation notes
- 🐛 Issues: Report bugs via GitHub issues
- 💡 Features: Suggest enhancements via GitHub discussions
