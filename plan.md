# Memory MCP Server SSE Implementation Plan

## Task: Convert Memory MCP Server to Support SSE Transport

### Requirements:
- [x] Change the current memory MCP to support SSE transport
- [x] Enable remote client connections (like Claude Desktop)
- [x] Make server deployable as a web service
- [x] Maintain all existing memory functionality

## Completed Tasks:

### ✅ 1. Updated Dependencies (pyproject.toml)
- Added required SSE transport dependencies:
  - `mcp[cli]>=1.2.1` - MCP server with SSE support
  - `starlette>=0.45.0` - Web application framework
  - `uvicorn>=0.34.0` - ASGI server
  - `httpx>=0.28.0` - HTTP client for async operations
- Updated project description to reflect SSE support

### ✅ 2. Modified Server Implementation (server.py)
- **Added SSE Transport Imports:**
  - `starlette.applications.Starlette`
  - `mcp.server.sse.SseServerTransport`
  - `starlette.requests.Request`
  - `starlette.routing.Mount, Route`
  - `mcp.server.Server`
  - `uvicorn`
  - `argparse`

- **Implemented SSE Web Server:**
  - Added `create_starlette_app()` function
  - Set up SSE transport with `/messages/` endpoint
  - Created routes for `/sse` endpoint and `/messages/` mount
  - Proper request/response streaming for SSE connections

- **Enhanced Server Startup:**
  - Added command-line argument parsing (--host, --port, --debug)
  - Replaced simple `mcp.run()` with proper web server setup
  - Used uvicorn to run the Starlette application
  - Added informative logging for server startup

### ✅ 3. Preserved All Memory Functionality
- All existing memory tools remain unchanged:
  - `add_memory()` - Enhanced memory storage with metadata
  - `search_memories()` - Comprehensive search with filters
  - `temporal_search()` - Time-based memory search
  - `search_by_tags()` - Tag-based filtering
  - `search_by_people()` - People-mentioned filtering
  - `search_by_topic()` - Topic category filtering

## Usage Instructions:

### Starting the Server:
```bash
# Basic usage
python server.py

# Custom host and port
python server.py --host 0.0.0.0 --port 8080

# With debug mode
python server.py --host localhost --port 3000 --debug
```

### Client Connection:
- **SSE Endpoint:** `http://your-server-ip:port/sse`
- **Example:** `http://localhost:8080/sse`

### Benefits Achieved:
1. **Remote Connectivity:** Clients can connect from anywhere
2. **Scalability:** Deployable as a proper web service
3. **Flexibility:** Configurable host/port binding
4. **Standard Transport:** HTTP/SSE instead of stdio pipes
5. **Cross-platform:** Works with Claude Desktop and custom clients

## Multi-User Alpha Testing Implementation:

### ✅ 4. Multi-User Support Added
- **Created User Management System:**
  - `users.json` - Static list of approved alpha testers
  - `user_management.py` - UserManager class for validation and collection naming
  - User validation against approved list
  - Dynamic collection naming: `memories_{user_id}`

- **Updated URL Routing:**
  - Changed from `/sse` to `/{user_id}/sse` 
  - User ID extraction from URL path parameters
  - User validation middleware in SSE handler
  - User context management with global state

- **Modified Database Operations:**
  - `qdrant_db.py` - Added user-specific collection functions
  - `ensure_user_collection_exists()` for dynamic collection creation
  - All database operations now use user-specific collections

- **Updated Memory Functions:**
  - `add_memory_to_collection.py` - Added user_id parameter
  - `src/search/enhanced_search_engine.py` - All search methods support user_id
  - User-isolated memory storage and retrieval

- **Enhanced MCP Tools:**
  - All MCP tools now use current user context
  - `get_current_user_id()` function for context access
  - Transparent user isolation (users don't see multi-user complexity)

### Alpha Tester URLs:
- Alice: `npx install-mcp https://memory.tailb75d54.ts.net/alice/sse --client claude`
- Bob: `npx install-mcp https://memory.tailb75d54.ts.net/bob/sse --client claude`
- Charlie: `npx install-mcp https://memory.tailb75d54.ts.net/charlie/sse --client claude`
- Diana: `npx install-mcp https://memory.tailb75d54.ts.net/diana/sse --client claude`
- Test User: `npx install-mcp https://memory.tailb75d54.ts.net/test_user/sse --client claude`

## Next Steps:
- [ ] Test the multi-user server with actual clients
- [ ] Add new alpha testers to users.json as needed
- [ ] Monitor user-specific collections in Qdrant
- [ ] Future: Create web-based user registration system
- [ ] Future: Add proper authentication and authorization

## Files Modified:
- `pyproject.toml` - Updated dependencies for SSE support
- `server.py` - Converted from simple MCP to SSE web server + multi-user support
- `users.json` - Static alpha testers list
- `user_management.py` - User validation and collection management
- `qdrant_db.py` - User-specific collection support
- `add_memory_to_collection.py` - User-aware memory storage
- `src/search/enhanced_search_engine.py` - User-aware search operations
- `plan.md` - Updated tracking document
