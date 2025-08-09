# InMemory Split Architecture - All in MCP Folder

This document describes the clean split architecture for the InMemory MCP server, with all components organized within the `mcp/` folder.

## Architecture Overview

```
┌─────────────────┐    HTTP    ┌─────────────────┐
│   LLM Clients   │◄──────────►│   MCP Server    │
│ (Claude, etc.)  │    SSE     │   (Port 8080)   │
└─────────────────┘            └─────────────────┘
                                        │
                                        │ HTTP API
                                        ▼
┌─────────────────┐            ┌─────────────────┐
│   Dashboard     │◄──────────►│   Core API      │
│   (Port 3000)   │    HTTP    │   (Port 8081)   │
└─────────────────┘            └─────────────────┘
                                        │
                                        │ Direct Access
                                        ▼
                               ┌─────────────────┐
                               │ Business Logic  │
                               │ (Same Folder)   │
                               └─────────────────┘
```

## File Organization (All in `mcp/` folder)

### Split Architecture Files:
- **`mcp_server.py`** - Pure MCP tools server (Port 8080)
- **`api_server.py`** - Core FastAPI server (Port 8081)
- **`requirements_mcp.txt`** - Minimal deps for MCP server
- **`requirements_api.txt`** - Full deps for API server

### Existing Business Logic (Unchanged):
- **`add_memory_to_collection.py`** - Memory storage with metadata
- **`src/search/enhanced_search_engine.py`** - All search functionality
- **`mongodb_user_manager.py`** - User authentication
- **`qdrant_db.py`** - Vector database operations
- **`.env`** - Shared configuration

### Legacy File (Backup):
- **`server.py`** - Your original combined server (kept as backup)

## Benefits

✅ **No New Folders** - Everything stays in familiar `mcp/` directory
✅ **Clean Separation** - MCP tools separate from FastAPI logic
✅ **No Import Issues** - All business logic files stay in same directory
✅ **Easy Migration** - Simple to switch between old and new servers
✅ **Framework Isolation** - No more FastAPI + MCP conflicts

## Quick Start

### Option 1: Individual Services (Development)

#### Terminal 1: Start Core API
```bash
cd mcp

# Install full dependencies
pip install -r requirements_api.txt

# Start API server
python api_server.py --host 0.0.0.0 --port 8081 --debug
```

#### Terminal 2: Start MCP Server
```bash
cd mcp

# Install minimal dependencies  
pip install -r requirements_mcp.txt

# Start MCP server
python mcp_server.py --host 0.0.0.0 --port 8080 --debug --core-api-url http://localhost:8081
```

#### Terminal 3: Install for LLMs
```bash
npx install-mcp http://localhost:8080 --client claude --header "Authorization: Bearer YOUR_API_KEY"
```

### Option 2: Docker Compose (if you have Docker)

```bash
# From project root directory
docker-compose up --build

# Services will be available at:
# - MCP Server: http://localhost:8080
# - Core API: http://localhost:8081
# - API Documentation: http://localhost:8081/docs
```

## Configuration

### Environment Variables (existing `.env` file):
```bash
# Database Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=inmemory

# API Configuration  
CORE_API_URL=http://localhost:8081
```

### API Keys
Use your existing API keys - both servers authenticate the same way:
```bash
Authorization: Bearer YOUR_API_KEY
```

## API Endpoints

### Core API (Port 8081)
- `GET /` - Service info and endpoint list
- `GET /v1/health` - Health check
- `GET /v1/auth/validate` - Validate API key
- `POST /v1/memories` - Add memory
- `GET /v1/memories` - Get memories with pagination
- `POST /v1/search` - Enhanced semantic search
- `POST /v1/temporal-search` - Time-based search
- `POST /v1/search-by-tags` - Tag filtering
- `POST /v1/search-by-people` - People filtering
- `POST /v1/search-by-topic` - Topic filtering

### MCP Server (Port 8080)
- `GET /` - SSE endpoint for MCP clients
- `POST /messages/` - MCP message handling

## MCP Tools (All Your Existing Tools)

1. **add_memory** - Add memory with metadata
2. **search_memories** - Enhanced search with filters
3. **temporal_search** - Time-based search
4. **search_by_tags** - Tag-based filtering
5. **search_by_people** - People-mentioned search
6. **search_by_topic** - Topic category search

## Testing

### Test Core API
```bash
# Health check
curl http://localhost:8081/v1/health

# API key validation
curl http://localhost:8081/v1/auth/validate \
  -H "Authorization: Bearer YOUR_API_KEY"

# Add memory
curl -X POST http://localhost:8081/v1/memories \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"memory_content": "Test memory", "tags": "test", "topic_category": "testing"}'

# Search memories
curl -X POST http://localhost:8081/v1/search \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'
```

### Test MCP Server
```bash
# Check SSE endpoint
curl http://localhost:8080/ \
  -H "Authorization: Bearer YOUR_API_KEY"

# Should return SSE connection info
```

### Test Dashboard Integration
Your existing dashboard should work by updating its API calls to point to `http://localhost:8081` instead of the combined server.

## Migration from Combined Server

### Stop Old Server
```bash
# Find and kill your existing server process
pkill -f "python.*server.py"
```

### Start New Split Services
```bash
cd mcp

# Terminal 1: Core API
python api_server.py --port 8081 &

# Terminal 2: MCP Server
python mcp_server.py --port 8080 --core-api-url http://localhost:8081 &
```

### Verify MCP Client Still Works
Your MCP client configuration remains the same:
- URL: `http://localhost:8080`
- API Key: Same as before
- All tools work identically

## Development Workflow

### Adding New Memory Tools
1. Add API endpoint in `api_server.py`
2. Add corresponding MCP tool in `mcp_server.py`
3. MCP tool calls the API endpoint via HTTP

### Modifying Business Logic
- Edit files like `add_memory_to_collection.py` as before
- Both servers will use the updated logic immediately
- No import path changes needed

### Debugging
- **MCP Issues**: Check MCP server logs (port 8080)
- **Business Logic Issues**: Check API server logs (port 8081)
- **Database Issues**: Check API server logs and database connectivity

## Dependencies

### MCP Server (`requirements_mcp.txt`)
- **Minimal**: Only MCP, HTTP client, and basic web server
- **Purpose**: Just handle MCP tools and call Core API
- **Size**: Small footprint for MCP-only deployment

### Core API (`requirements_api.txt`)
- **Full Stack**: FastAPI, databases, search engines, etc.
- **Purpose**: All business logic and data operations
- **Size**: Complete but organized in one service

## File Structure
```
mcp/
├── mcp_server.py              # Pure MCP server (NEW)
├── api_server.py              # Core FastAPI server (NEW)
├── requirements_mcp.txt       # MCP dependencies (NEW)
├── requirements_api.txt       # API dependencies (NEW)
├── server.py                  # Original combined server (BACKUP)
├── add_memory_to_collection.py    # Existing business logic
├── src/search/enhanced_search_engine.py    # Existing
├── mongodb_user_manager.py    # Existing
├── qdrant_db.py              # Existing
├── .env                      # Existing configuration
└── ... all other existing files
```

## Troubleshooting

### MCP Tools Not Working
1. Check Core API is running: `curl http://localhost:8081/v1/health`
2. Check MCP server can reach API: Look for HTTP errors in MCP server logs
3. Verify API key: `curl http://localhost:8081/v1/auth/validate -H "Authorization: Bearer YOUR_KEY"`

### Performance Issues
- Core API handles heavy database operations
- MCP server just formats responses for LLMs
- Each service can be scaled independently

### Import Errors
- All business logic stays in same `mcp/` folder
- No import path changes needed
- If you get import errors, make sure you're running from `mcp/` directory

## Production Deployment

### Using PM2 (Process Manager)
```bash
cd mcp

# Install PM2 globally
npm install -g pm2

# Start both services
pm2 start api_server.py --name core-api --interpreter python3 -- --port 8081
pm2 start mcp_server.py --name mcp-server --interpreter python3 -- --port 8080 --core-api-url http://localhost:8081

# Save PM2 configuration
pm2 save
pm2 startup
```

### Using Systemd Services
```bash
# Create service files for both servers
sudo systemctl create inmemory-api.service
sudo systemctl create inmemory-mcp.service

# Enable and start services
sudo systemctl enable inmemory-api inmemory-mcp
sudo systemctl start inmemory-api inmemory-mcp
```

## Next Steps

- [ ] Test all MCP tools work with split architecture
- [ ] Update dashboard to use Core API on port 8081
- [ ] Monitor both services for performance and errors
- [ ] Consider adding health check endpoints for monitoring
- [ ] Plan scaling strategy for high-load scenarios

---

This split architecture gives you the same functionality as before, but with clean separation and no framework conflicts, all organized within your familiar `mcp/` directory structure.
