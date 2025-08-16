# InMemory Storage Layer Documentation

## Purpose
The storage layer provides a unified interface for different storage backends, enabling InMemory to work with file-based storage (default) or enterprise backends like MongoDB without requiring external dependencies.

## Architecture

### Storage Interface (MemoryStoreInterface)
- **File**: `base.py`
- **Purpose**: Abstract base class defining the interface all storage backends must implement
- **Key Methods**:
  - `validate_user()`: Check if user exists and is valid
  - `get_collection_name()`: Generate Qdrant collection name for user
  - `validate_api_key()`: Authenticate API keys and return user_id
  - `store_api_key()`: Store API keys with metadata
  - `create_user()`: Create new users with metadata
  - `list_user_api_keys()`: List user's API keys (without exposing actual keys)
  - `revoke_api_key()`: Deactivate API keys
  - `close_connection()`: Cleanup connections

### File-Based Storage (FileBasedStore)
- **File**: `file_store.py` 
- **Purpose**: Zero-dependency storage using JSON files in ~/.inmemory/
- **Key Features**:
  - Thread-safe operations with RLock
  - Atomic file writes using temporary files
  - Auto-creates users and API keys as needed
  - Backup and statistics capabilities
  - Perfect for development and single-user scenarios
- **Storage Files**:
  - `~/.inmemory/users.json`: User metadata
  - `~/.inmemory/api_keys.json`: API key management
- **Important Functions**:
  - `ensure_user_with_key()`: Convenience method for development setups
  - `backup_data()`: Create backups of all data files
  - `get_stats()`: Get storage statistics

### MongoDB Storage (MongoDBStore)  
- **File**: `mongodb_store.py`
- **Purpose**: Enterprise-grade storage using MongoDB
- **Key Features**:
  - Wraps existing mongodb_user_manager.py functionality
  - Provides MongoDB collections for users and API keys
  - Supports OAuth integration
  - Scalable multi-user architecture
- **Dependencies**: Requires `pymongo` (installed with `inmemory[mongodb]`)
- **Important Functions**:
  - `migrate_from_file_store()`: Migrate data from FileBasedStore
  - `get_api_key_info()`: MongoDB-specific detailed API key lookup
  - `get_stats()`: MongoDB collection statistics

### Factory Pattern (create_store)
- **File**: `__init__.py`
- **Purpose**: Factory function to create storage backend instances
- **Key Features**:
  - Auto-detects available dependencies
  - Provides helpful error messages for missing dependencies
  - Graceful fallbacks and imports
- **Usage**:
  ```python
  from inmemory.stores import create_store
  
  # File-based (default)
  store = create_store("file")
  
  # MongoDB (requires inmemory[mongodb])  
  store = create_store("mongodb", mongodb_uri="mongodb://localhost:27017")
  ```

## Usage Patterns

### Direct Storage Usage
```python
from inmemory.stores import FileBasedStore, create_store

# Direct usage
file_store = FileBasedStore(data_dir="/custom/path")
file_store.create_user("alice")
api_key = file_store.ensure_user_with_key("alice")

# Factory usage
store = create_store("file", path="/custom/path")
```

### Through Memory SDK
```python
from inmemory import Memory

# SDK automatically uses storage layer
memory = Memory(storage_type="file")  # Uses FileBasedStore
memory = Memory(storage_type="mongodb")  # Uses MongoDBStore
```

### Configuration Integration
```python
from inmemory.config import InMemoryConfig
from inmemory import Memory

config = InMemoryConfig(
    storage={"type": "file", "path": "/custom/data"}
)
memory = Memory(config=config)
```

## Thread Safety
All storage implementations are thread-safe:
- **FileBasedStore**: Uses `threading.RLock()` for file operations
- **MongoDBStore**: MongoDB client handles concurrent connections

## Error Handling
- Graceful fallbacks when dependencies are missing
- Detailed error messages with installation hints
- Automatic recovery from corrupted data files
- Connection failure handling with fallback modes

## Migration Support
Storage backends support data migration:
```python
# File to MongoDB migration
mongo_store.migrate_from_file_store(file_store)

# Configuration-based migration
# Change INMEMORY_STORAGE_TYPE environment variable
```

## Extension Points
The interface allows for future storage backends:
- PostgreSQL support (planned)
- SQLite backend  
- Cloud storage (S3, GCS)
- Redis backend for caching
- Custom implementations

## Best Practices

### File-Based Storage
- Use for development, testing, single-user scenarios
- Default data directory is ~/.inmemory/
- Automatic backup functionality available
- Thread-safe for concurrent access

### MongoDB Storage  
- Use for production, multi-user scenarios
- Requires proper MongoDB setup and security
- Supports OAuth integration for dashboards
- Provides detailed statistics and monitoring

### Configuration Management
- Use environment variables for deployment flexibility
- YAML configs for complex setups
- Auto-detection for development convenience
- Validation ensures proper setup

## Important Notes

### Security Considerations
- API keys are stored securely but not encrypted in file storage
- MongoDB storage inherits security from MongoDB setup
- File permissions should be properly configured
- Consider encryption for sensitive data

### Performance
- File storage is optimized for small to medium datasets
- MongoDB storage scales to large multi-user deployments
- Thread-safe operations ensure data consistency
- Qdrant handles the heavy vector operations

### Backwards Compatibility
- Existing mongodb_user_manager.py functionality preserved
- All current API endpoints continue working
- Smooth migration path from current setup
- No breaking changes for existing dashboards
