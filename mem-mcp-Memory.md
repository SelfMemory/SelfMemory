# mem-mcp Project Memory

## Project Overview
MCP (Model Context Protocol) Memory Server - A vector-based memory storage system that allows storing and retrieving user memories using semantic search through embeddings.

## Project Structure

### Core Files and Their Purpose

#### `server.py`
- **Purpose**: Main MCP server entry point using FastMCP framework
- **Key Functions**:
  - `add_memory()`: MCP tool endpoint for adding memories to the collection
  - `retrieve_memory()`: MCP tool endpoint for retrieving memories based on similarity search
- **Dependencies**: FastMCP, logging, memory management modules
- **Notes**: Handles MCP protocol communication and provides clean error handling

#### `add_memory_to_collection.py`
- **Purpose**: Core functionality for adding memories to the vector database
- **Key Functions**:
  - `add_memory(memory_content: str) -> str`: Main function to store memory with validation and error handling
- **Important Features**:
  - UUID-based ID generation (replaced random integers)
  - Input validation for empty content
  - Proper error handling and logging
  - Clean content processing (strip whitespace)
- **Dependencies**: uuid, logging, qdrant_db, generate_embeddings, constants

#### `retrieve_memory_from_collection.py`
- **Purpose**: Core functionality for retrieving memories using semantic search
- **Key Functions**:
  - `retrieve_memories(query_text, keyword_filter=None, limit=3) -> List[str]`: Main memory retrieval function
  - `search_memories_with_filter(query_text, keyword_filter, limit=3) -> List[str]`: Enhanced search with keyword filtering
- **Important Features**:
  - Configurable search limits with validation
  - Semantic similarity search using embeddings
  - Optional keyword filtering
  - Comprehensive error handling and logging
- **Dependencies**: logging, typing, qdrant_db, generate_embeddings, constants

#### `generate_embeddings.py`
- **Purpose**: Handles embedding generation using Ollama
- **Key Functions**:
  - `generate_embeddings(text: str) -> dict`: Raw embedding generation
  - `get_embeddings(text: str) -> List[float]`: Extract embedding vector from response
- **Important Features**:
  - Input validation for empty text
  - Error handling for embedding generation failures
  - Clean separation of concerns (generation vs extraction)
  - Proper logging for debugging
- **Dependencies**: logging, typing, ollama, constants

#### `qdrant_db.py`
- **Purpose**: Database client configuration and collection management
- **Key Functions**:
  - `create_qdrant_client() -> QdrantClient`: Initialize Qdrant connection
  - `ensure_collection_exists(client, collection_name) -> bool`: Collection setup and validation
- **Important Features**:
  - Automatic collection creation if not exists
  - Connection error handling
  - Configurable timeout and connection parameters
  - Global client initialization
- **Dependencies**: logging, qdrant_client, constants

#### `constants.py`
- **Purpose**: Centralized configuration management
- **Key Classes**:
  - `EmbeddingConstants`: Model configuration
  - `VectorConstants`: Database and vector configuration
  - `SearchConstants`: Search operation limits and defaults
  - `DatabaseConstants`: Connection and timeout settings
  - `LoggingConstants`: Logging format and level configuration
- **Important Features**:
  - No magic numbers in code
  - Easy configuration management
  - Clear categorization of constants
  - Well-documented constant purposes

### Clean Code Principles Applied

#### 1. Meaningful Names
- `add_memorys` → `add_memory`
- `get_memorys` → `retrieve_memories`
- Variable `a` → `retrieved_memories`
- Clear function and parameter names throughout

#### 2. Single Responsibility Principle
- Each function has a clear, single purpose
- Separation of concerns between modules
- Database operations separated from business logic

#### 3. Error Handling
- Comprehensive try-catch blocks
- Input validation at function entry points
- Consistent error messages and logging
- Graceful failure handling

#### 4. Function Size and Complexity
- Small, focused functions
- Clear function signatures with type hints
- Comprehensive docstrings
- Logical parameter ordering

#### 5. Code Organization
- Proper imports organization
- Constants extracted to dedicated module
- Consistent code formatting
- Removal of dead code and unused imports

## Dependencies
- `mcp.server.fastmcp`: MCP protocol implementation
- `qdrant-client`: Vector database client
- `ollama`: Embedding generation
- `uuid`: Unique ID generation
- `logging`: Structured logging
- `typing`: Type hints

## Configuration
- Embedding Model: `mxbai-embed-large`
- Vector Dimensions: 1536
- Default Search Limit: 3
- Max Search Limit: 10
- Database URL: `http://localhost:6333`
- Collection Name: `test_collection_mcps`

## Usage
1. Ensure Qdrant is running on localhost:6333
2. Ensure Ollama is available with the mxbai-embed-large model
3. Run the MCP server: `python server.py`
4. Use MCP tools: `add_memory` and `retrieve_memory`

## Recent Changes (Clean Code Refactoring)
- Applied Uncle Bob's Clean Code principles
- Improved naming conventions throughout
- Added comprehensive error handling
- Implemented proper logging
- Extracted magic numbers to constants
- Added type hints and docstrings
- Simplified architecture (avoided over-engineering)
- Enhanced input validation
- Improved function organization and responsibilities

## Testing Status
- Manual testing pending for refactored code
- All core functions include basic test scenarios in `if __name__ == "__main__"` blocks
