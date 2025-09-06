# Simple InMemory MCP Server

A simplified, easy-to-understand MCP (Model Context Protocol) server for memory management.

## What Was Simplified

The original MCP server files were complex and hard to understand. Here's what we simplified:

### Before (Complex)
- **main.py**: 300+ lines with complex error handling, multiple global variables, and intricate SSE setup
- **server.py**: 600+ lines with 7 different tools, complex search engines, and multiple service dependencies

### After (Simple)
- **main.py**: ~200 lines with clear structure, simple authentication, and 2 core tools
- **server.py**: ~400 lines with straightforward HTTP API and basic MCP protocol support

## Key Improvements

### 1. **Cleaner Code Structure**
- Removed complex imports and dependencies
- Simplified authentication using only `InmemoryClient`
- Clear separation of concerns

### 2. **Easier to Understand**
- Simple function names and clear documentation
- Reduced from 7 tools to 3 essential tools
- Straightforward error handling

### 3. **Better Comments**
- Every function has a clear docstring
- Code comments explain what's happening
- Examples in function documentation

### 4. **Simplified Tools**

#### main.py (FastMCP + SSE)
- `add_memory` - Store memories with metadata
- `search_memory` - Find relevant memories

#### server.py (HTTP API + MCP Protocol)  
- `add_memory` - HTTP endpoint for adding memories
- `search_memories` - HTTP endpoint for searching
- `delete_memory` - Placeholder for future deletion

## Usage

### Start the FastMCP Server (main.py)
```bash
cd inmemory-mcp
python3 main.py --host 0.0.0.0 --port 8080
```

### Start the HTTP API Server (server.py)
```bash
cd inmemory-mcp/src
python3 server.py --host 0.0.0.0 --port 8080
```

## What Makes It "Grandparent-Friendly"

1. **Simple Language**: No technical jargon in comments
2. **Clear Structure**: Each file has a clear purpose
3. **Easy to Follow**: Code flows logically from top to bottom
4. **Minimal Dependencies**: Uses only essential imports
5. **Good Examples**: Function docstrings include usage examples

## Files

- `main.py` - Simple MCP server using FastMCP with SSE transport
- `src/server.py` - HTTP API server with MCP protocol support
- `README.md` - This documentation

## Authentication

Both servers use simple Bearer token authentication:
```
Authorization: Bearer <your-api-key>
```

The API key is validated using the existing `InmemoryClient`.

## Next Steps

The simplified code maintains all core functionality while being much easier to:
- Read and understand
- Modify and extend
- Debug when issues arise
- Onboard new developers

Perfect for anyone who wants to understand how MCP servers work without getting lost in complexity!
