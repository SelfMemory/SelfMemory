# mem-mcp Project Memory

## Project Overview
Enhanced Memory MCP Server with SSE (Server-Sent Events) transport support for remote client connections and multi-user functionality for alpha testing.

## Key Files and Purpose

### Core Server Files
- **server.py**
  - Main MCP server implementation with SSE transport
  - Contains all memory management tools (add_memory, search_memories, etc.)
  - Uses Starlette web framework for HTTP/SSE transport
  - Configurable host/port binding via command line arguments
  - Replaces FastAPI with proper SSE implementation

- **pyproject.toml**
  - Project configuration with SSE-specific dependencies
  - Key dependencies: mcp[cli], starlette, uvicorn, httpx
  - Supports Python 3.13+

### Memory Management Files
- **add_memory_to_collection.py**
  - Enhanced memory storage with metadata (tags, people, topics, temporal data)
  - Includes duplicate detection functionality
  - Function: `add_memory_enhanced()`

- **retrieve_memory_from_collection.py**
  - Basic memory retrieval functions
  - Functions: `retrieve_memories()`, `search_memories_with_filter()`

### Advanced Search Engine
- **src/search/enhanced_search_engine.py**
  - Comprehensive search capabilities with multiple filtering options
  - Supports semantic search, temporal filtering, tag/people/topic searches
  - Class: `EnhancedSearchEngine`

### Supporting Components
- **src/shared/duplicate_detector.py**
  - Prevents storing duplicate memories
  - Uses semantic similarity for detection

- **src/shared/temporal_utils.py**
  - Time-based filtering and search functionality
  - Handles temporal queries like "yesterday", "this_week", etc.

- **qdrant_db.py**
  - Vector database connection and operations
  - Handles embeddings and similarity search

- **generate_embeddings.py**
  - Text-to-vector embedding generation
  - Uses Ollama for local embedding models

## Important Functions

### Memory Tools (server.py)
1. **add_memory(memory_content, tags, people_mentioned, topic_category)**
   - Stores memory with rich metadata
   - Automatic temporal data extraction
   - Duplicate detection
   - Returns formatted result with memory ID

2. **search_memories(query, limit, tags, people_mentioned, topic_category, temporal_filter)**
   - Comprehensive semantic search with multiple filters
   - Supports combined filtering across all metadata types
   - Returns formatted results with metadata and similarity scores

3. **temporal_search(temporal_query, semantic_query, limit)**
   - Time-based memory search
   - Natural language time queries (yesterday, this_week, weekends, etc.)
   - Optional semantic filtering

4. **search_by_tags(tags, semantic_query, match_all_tags, limit)**
   - Tag-based filtering with AND/OR logic
   - Highlights matching vs other tags
   - Optional semantic search combination

5. **search_by_people(people, semantic_query, limit)**
   - Search by mentioned people
   - Highlights matching vs other people in results
   - Supports multiple people queries

6. **search_by_topic(topic_category, semantic_query, limit)**
   - Topic/category-based search
   - Optional semantic filtering within topic
   - Includes temporal context in results

## Recent Major Changes (SSE Implementation)

### 1. Transport Layer Conversion
- **Before:** Simple `mcp.run(transport="sse")` 
- **After:** Full Starlette web application with proper SSE routing
- **Benefits:** Remote connectivity, web service deployment, configurable binding

### 2. Server Architecture
- **Added:** `create_starlette_app()` function for SSE transport setup
- **Added:** Command line argument parsing (--host, --port, --debug)
- **Added:** Proper SSE endpoint routing (/sse, /messages/)
- **Enhanced:** Logging and startup information

### 3. Dependencies Updated
- **Added:** starlette, uvicorn, mcp[cli], httpx
- **Purpose:** Enable SSE transport and web server functionality
- **Maintains:** All existing functionality (qdrant-client, ollama, etc.)

## Multi-User Functionality (Alpha Testing)

### 4. Multi-User Support Implementation
- **Before:** Single collection for all memories (`test_collection_mcps`)
- **After:** User-specific collections (`memories_{user_id}`) for complete isolation

### User Management System
- **users.json**
  - Static list of approved alpha testers
  - Easy to add new users for testing
  - Format: `{"alpha_users": ["alice", "bob", "charlie", ...]}`

- **user_management.py**
  - `UserManager` class for user validation
  - `is_valid_user(user_id)` - validates against approved list
  - `get_collection_name(user_id)` - returns `memories_{user_id}`
  - `add_user(user_id)` - for future dynamic user addition

### URL Structure Changes
- **Before:** `https://inmemory.tailb75d54.ts.net/sse`
- **After:** `https://inmemory.tailb75d54.ts.net/{user_id}/sse`
- **Example:** `https://inmemory.tailb75d54.ts.net/alice/sse`

### Database Isolation
- **User-Specific Collections:** Each user gets their own Qdrant collection
- **Dynamic Creation:** Collections created automatically for valid users
- **Complete Isolation:** No cross-user data access or contamination

### Alpha Tester Onboarding
```bash
# Alice's setup
npx install-mcp https://inmemory.tailb75d54.ts.net/alice/sse --client claude

# Bob's setup  
npx install-mcp https://inmemory.tailb75d54.ts.net/bob/sse --client claude

# Charlie's setup
npx install-mcp https://inmemory.tailb75d54.ts.net/charlie/sse --client claude
```

### User Context Management
- **Global State:** `_current_user_id` variable for request context
- **Context Functions:** `get_current_user_id()` and `set_current_user_id()`
- **Transparent Operation:** Users don't see multi-user complexity
- **Same Experience:** All memory tools work identically for each user

## Usage Patterns

### Starting the Server
```bash
# Default (localhost:8080)
python server.py

# Custom configuration
python server.py --host 0.0.0.0 --port 3000 --debug

# Production deployment
python server.py --host 0.0.0.0 --port 8080
```

### Client Connection
- **SSE Endpoint:** `http://server-ip:port/sse`
- **Compatible with:** Claude Desktop, custom MCP clients
- **Transport:** HTTP Server-Sent Events (SSE)

## Project Structure
```
mem-mcp/
├── server.py              # Main SSE MCP server
├── pyproject.toml          # Dependencies with SSE support
├── plan.md                 # Implementation tracking
├── mem-mcp-Memory.md      # This documentation
├── add_memory_to_collection.py
├── retrieve_memory_from_collection.py
├── qdrant_db.py
├── generate_embeddings.py
├── constants.py
├── src/
│   ├── search/
│   │   └── enhanced_search_engine.py
│   └── shared/
│       ├── duplicate_detector.py
│       └── temporal_utils.py
└── mcp-sse/               # Reference SSE example
```

## Key Design Decisions
1. **SSE over stdio:** Enables remote client connections and web deployment
2. **Metadata-rich storage:** Tags, people, topics, temporal data for enhanced search
3. **Multiple search modes:** Semantic, temporal, tag/people/topic-based filtering
4. **Duplicate detection:** Prevents redundant memory storage
5. **Configurable deployment:** Command-line arguments for flexible hosting

## Dependencies Overview
- **mcp[cli]:** MCP protocol implementation with SSE transport
- **starlette:** Lightweight web framework for SSE endpoints
- **uvicorn:** ASGI server for running the web application
- **qdrant-client:** Vector database for similarity search
- **ollama:** Local language model for embeddings
- **pydantic:** Data validation and serialization
- **httpx:** Async HTTP client for external requests

## Next Development Areas
- Authentication/authorization for remote access
- Performance optimization for large memory collections  
- Additional metadata fields (location, context, etc.)
- Integration with external knowledge sources
- Memory categorization and organization features
