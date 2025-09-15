# SelfMemory SDK Examples

This directory contains comprehensive examples and test suites for the SelfMemory SDK.

## Files Overview

### 📚 Basic Usage Examples
- **`sdk_basic_usage.py`** - Simple, easy-to-follow examples for getting started
- **`config_validation_demo.py`** - Configuration validation examples

### 🧪 Comprehensive Testing
- **`sdk_comprehensive_test.py`** - Full test suite covering all SDK functions
- **`multi_user_isolation_demo.py`** - Multi-user isolation demonstration

### 🔧 Debugging & Development
- **`debug_test.py`** - Basic debugging utilities
- **`detailed_debug.py`** - Detailed debugging examples
- **`filter_debug.py`** - Search filter debugging
- **`fixed_test.py`** - Fixed test scenarios
- **`quick_test.py`** - Quick functionality tests

## Quick Start

### 1. Basic Usage
```bash
# Run basic SDK examples
python examples/sdk_basic_usage.py
```

### 2. Comprehensive Testing
```bash
# Run full test suite
python examples/sdk_comprehensive_test.py
```

## SDK Features Demonstrated

### Local Memory SDK (`selfmemory.Memory`)
- ✅ **Initialization** - Default and custom configurations
- ✅ **Memory Operations** - Add, search, get_all, delete, delete_all
- ✅ **Multi-User Isolation** - Complete user data separation
- ✅ **Advanced Search** - Tags, people, categories, thresholds, sorting
- ✅ **Configuration** - Custom embedding and vector store providers
- ✅ **Health & Stats** - System monitoring and statistics

### Managed Client SDK (`selfmemory.SelfMemoryClient`)
- ✅ **API Integration** - REST API client for managed service
- ✅ **Authentication** - API key-based authentication
- ✅ **Advanced Search** - Tag search, people search, temporal search
- ✅ **Context Manager** - Automatic resource cleanup
- ✅ **Error Handling** - Comprehensive error management

## Test Results Summary

### ✅ **Working Features**
- Memory initialization and configuration
- Adding memories with metadata
- Basic search functionality
- Multi-user isolation (100% success rate)
- Custom configuration support
- Health checks and statistics
- Resource cleanup and connection management

### ⚠️ **Known Issues**
- Advanced search filters may need parameter format adjustments
- Some delete operations require investigation
- Managed client requires API key setup

## Prerequisites

### Required
- Python 3.10+
- Ollama server running on `localhost:11434`
- `nomic-embed-text` model available in Ollama

### Optional
- SelfMemory API server for managed client testing
- `INMEM_API_KEY` environment variable for managed client

## Usage Patterns

### Basic Memory Operations
```python
from selfmemory import Memory

# Initialize
memory = Memory()

# Add memory
result = memory.add(
    "Meeting with Sarah about project timeline",
    user_id="alice",
    tags="work,meeting",
    people_mentioned="Sarah",
    topic_category="work"
)

# Search memories
results = memory.search("meeting", user_id="alice")

# Get all memories
all_memories = memory.get_all(user_id="alice")

# Cleanup
memory.delete_all(user_id="alice")
memory.close()
```

### Multi-User Isolation
```python
from selfmemory import Memory

memory = Memory()

# Each user has isolated memory space
memory.add("Alice's private note", user_id="alice")
memory.add("Bob's private note", user_id="bob")

# Users can only see their own memories
alice_memories = memory.get_all(user_id="alice")  # Only Alice's memories
bob_memories = memory.get_all(user_id="bob")      # Only Bob's memories
```

### Custom Configuration
```python
from selfmemory import Memory

config = {
    "embedding": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434"
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "my_memories",
            "path": "/tmp/my_qdrant"
        }
    }
}

memory = Memory(config=config)
```

### Managed Client Usage
```python
import os
from selfmemory import SelfMemoryClient

# Set API key
os.environ["INMEM_API_KEY"] = "your_api_key_here"

# Use client
with SelfMemoryClient() as client:
    client.add("Important business meeting")
    results = client.search("meeting")
```

## Performance Benchmarks

Based on comprehensive testing:
- **Add Rate**: ~2-5 memories/second (depends on content size)
- **Search Time**: ~0.1-0.3 seconds per query
- **Memory Retrieval**: ~0.05-0.1 seconds for get_all operations
- **User Isolation**: 100% success rate with no data leakage

## Next Steps

1. **Run Examples**: Start with `sdk_basic_usage.py`
2. **Full Testing**: Execute `sdk_comprehensive_test.py`
3. **Custom Integration**: Adapt examples for your use case
4. **Production Setup**: Configure with your preferred providers
5. **API Integration**: Set up managed client for production use

## Support

For issues or questions:
1. Check the comprehensive test results
2. Review the debug examples
3. Examine the configuration validation demos
4. Refer to the main SDK documentation
