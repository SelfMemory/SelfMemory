# Repositories Module - Memory Documentation

## Overview
The `repositories` module contains the data access layer for the memory system. This follows the Repository pattern, abstracting database operations and providing clean interfaces for data persistence.

## Files

### `qdrant_db.py`
- **Purpose**: Qdrant vector database client and operations
- **Key Functions**:
  - `create_qdrant_client()`: Creates configured Qdrant client instance
  - `ensure_collection_exists()`: Ensures collection exists or creates it
  - `get_qdrant_client()`: Thread-safe client getter
  - `delete_memory_point()`: Deletes specific memory from collection
  - `delete_user_memory()`: High-level user memory deletion with validation
  - `ensure_user_collection_exists()`: User-specific collection management
- **Dependencies**: Uses common (constants), repositories (mongodb_user_manager)

### `mongodb_user_manager.py`
- **Purpose**: MongoDB user management and authentication
- **Key Classes**:
  - `MongoUserManager`: Main class for user operations
- **Key Functions**:
  - `validate_api_key()`: API key validation and user identification
  - `is_valid_user()`: User existence validation
  - `get_collection_name()`: User-specific Qdrant collection naming
  - `get_user_info()`: User information retrieval
  - `get_api_key_info()`: API key information and usage stats
- **Global Functions**:
  - `initialize_mongo_user_manager()`: Global manager initialization
  - `get_mongo_user_manager()`: Global manager getter
- **Dependencies**: Standard library and PyMongo only

## Data Access Patterns
- **Thread Safety**: New clients created for each operation
- **User Isolation**: Collection names based on user IDs
- **Error Handling**: Comprehensive error handling with logging
- **Connection Management**: Automatic cleanup and connection pooling

## Important Notes
- MongoDB stores user data and API keys
- Qdrant stores encrypted memory vectors and payloads
- Collection names follow pattern: `memories_{clean_user_id}`
- All database errors are logged and re-raised with context
