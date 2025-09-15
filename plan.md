Based on my analysis of the  memory management system, here's how they're managing memory:

## Architecture Overview

The  memory system uses a **hybrid multi-store architecture** that combines several storage mechanisms:

### 1. **Abstract Base Layer** (`base.py`)
- Defines a clean interface with core operations: `get`, `get_all`, `update`, `delete`, `history`
- Ensures consistent API across different implementations

### 2. **Core Memory Implementation** (`main.py`)
The main implementation uses a **three-tier storage system**:

**a) Vector Store (Primary Memory)**
- Stores memory content as embeddings for semantic similarity search
- Supports multiple vector databases (configurable)
- Handles the actual memory content and retrieval

**b) Graph Store (Relationship Memory)**
- Optional graph database integration (Neo4j, Kuzu, Memgraph)
- Stores entities and relationships extracted from conversations
- Enables contextual memory through entity connections
- Uses LLM to extract entities and relationships from text

**c) SQLite History Store**
- Tracks all memory operations (ADD, UPDATE, DELETE)
- Maintains audit trail with timestamps, actors, and roles
- Enables memory versioning and rollback capabilities

### 3. **Memory Processing Pipeline**

**Memory Addition Process:**
1. **Fact Extraction**: LLM extracts key facts from input messages
2. **Similarity Search**: Finds existing similar memories using embeddings
3. **Memory Operations**: LLM decides whether to ADD, UPDATE, or DELETE memories
4. **Dual Storage**: Stores in both vector store and graph store (if enabled)
5. **History Logging**: Records all operations in SQLite

**Key Features:**
- **Smart Deduplication**: Prevents storing duplicate information
- **Automatic Updates**: Updates existing memories when new information conflicts
- **Entity Relationships**: Tracks connections between people, places, concepts
- **Multi-tenancy**: Supports filtering by `user_id`, `agent_id`, `run_id`
- **Async Support**: Full async implementation for scalability

### 4. **Graph Memory Implementations**
Three different graph database backends:
- **Neo4j** (`graph_memory.py`): Enterprise-grade graph database
- **Kuzu** (`kuzu_memory.py`): Embedded graph database
- **Memgraph** (`memgraph_memory.py`): In-memory graph database

Each handles:
- Entity extraction and relationship mapping
- Vector similarity search within graph nodes
- Cypher query generation for graph operations

### 5. **Memory Types**
- **Conversational Memory**: Standard fact-based memories
- **Procedural Memory**: Step-by-step process memories
- **Raw Memory**: Direct storage without LLM processing (when `infer=False`)

## Key Innovations

1. **Intelligent Memory Management**: Uses LLM to decide memory operations rather than simple storage
2. **Hybrid Storage**: Combines vector similarity with graph relationships
3. **Automatic Conflict Resolution**: Updates conflicting information automatically
4. **Rich Metadata**: Tracks actors, roles, timestamps, and relationships
5. **Flexible Filtering**: Multi-dimensional filtering for different use cases

This architecture enables sophisticated memory capabilities like understanding context, avoiding duplicates, maintaining relationships, and providing intelligent retrieval based on both semantic similarity and entity connections.


--------------

Based on my analysis of the  memory management system, here's how they're managing memory:

### 1. **Abstract Base Layer** (`base.py`)
- Defines a clean interface with core operations:
- Ensures consistent API across different implementations

### 2. **Core Memory Implementation** (`main.py`)
The main implementation uses a **storage system**:

**a) Vector Store (Primary Memory)**
- Stores memory content as embeddings for semantic similarity search
- Supports multiple vector databases (configurable)
- Handles the actual memory content and retrieval

Perfect! Based on my investigation of  patterns and your requirements, here's our comprehensive plan for cleaning up memory.py:

## 🎯 **THE PLAN: Clean Memory.py Architecture**

### **Core Principle**: 
Memory class should NEVER directly import specific providers. It should only use base.py abstractions and get providers through factory pattern + config.

### **Phase 1: Create Factory Pattern (Following  approach)**
1. **Create `inmemory/utils/factory.py`** - Factory classes for providers
   - `EmbeddingFactory.create()` - Returns `EmbeddingBase` instances
   - `VectorStoreFactory.create()` - Returns `VectorStoreBase` instances
   - Uses dynamic imports like : `load_class("inmemory.embeddings.ollama.OllamaEmbedding")`

### **Phase 2: Simplify Memory Class Initialization**
Current memory.py has 150+ lines of complex initialization. We'll reduce it to:
```python
class Memory:
    def __init__(self, config: InMemoryConfig = None):
        self.config = config or InMemoryConfig()
        
        # Use factories - NO direct imports!
        self.embedding_provider = EmbeddingFactory.create(
            self.config.embedding.provider, 
            self.config.embedding.to_dict()
        )
        
        self.vector_store = VectorStoreFactory.create(
            self.config.vector_store.provider,
            collection_name="inmemory_memories", 
            embedding_model_dims=self.embedding_provider.embedding_dims,
            config=self.config.vector_store.to_dict()
        )
```

### **Phase 3: Delete Unwanted Code**
- Remove all broken imports (openai, azure_openai, huggingface, mock)
- Remove complex provider detection logic
- Remove fallback mechanisms
- Keep only Ollama + Qdrant paths

### **Phase 4: Consolidate Search Functions**
- Merge `search()`, `enhanced_search`, `retrieve_memory` into single `search()` method
- All search parameters become optional in one unified interface

### **Phase 5: Update Config Integration**
- Ensure config.py works seamlessly with factory pattern
- Default to Ollama + Qdrant in config
- Clean config validation

## 🏗️ **Architecture Benefits:**

### ✅ **Zero Code Changes for New Providers**
```python
# Tomorrow, to add OpenAI embedding:
# 1. Add to factory: "openai": "inmemory.embeddings.openai.OpenAIEmbedding"
# 2. Memory class stays EXACTLY the same!
```

### ✅ **Clean Separation of Concerns**
- Memory class: Business logic only
- Factory: Provider instantiation
- Config: Configuration management
- Base classes: Contracts/interfaces

### ✅ **Follows  Proven Pattern**
- Dynamic imports via `load_class()`
- Provider-to-class mappings
- Config-driven initialization

## 📋 **Implementation Steps:**

1. **Create factory.py** (following  exact pattern)
2. **Simplify memory.py initialization** (remove 100+ lines of complexity)
3. **Delete broken imports and fallbacks**
4. **Consolidate search methods**
5. **Test with existing examples**
6. **Update dependent files (client.py, server, etc.)**

This approach gives you the **exact architecture you wanted**: Memory class uses only base.py abstractions, gets providers through config, and adding new providers requires zero changes to Memory class.

Ready to implement this plan?



--------------------

Perfect! I've analyzed the codebase and you're absolutely right - there's significant redundancy and unused code that needs cleanup. Let me present a comprehensive cleanup plan based on what I found:

## 🔍 **Current State Analysis**

### **Major Redundancies Identified:**

1. **DUPLICATE CONFIG SYSTEMS** 📁
   - `inmemory/config/` (old system)
   - `inmemory/configs/` (new -aligned system) ✅
   - **Decision**: Keep `configs/`, remove `config/`

2. **REDUNDANT SEARCH FUNCTIONALITY** 🔍
   - `inmemory/search/enhanced_search_engine.py` (complex, feature-rich)
   - `inmemory/services/retrieve_memory.py` (simple retrieval)
   - `inmemory/memory/main.py` (consolidated search) ✅
   - **Decision**: Keep consolidated search in `main.py`, remove others

3. **UNUSED/QUESTIONABLE FOLDERS** 🗂️
   - `inmemory/api/` - Separate FastAPI server (unclear if used)
   - `inmemory/services/` - Old service layer (replaced by `memory/main.py`)
   - `inmemory/repositories/` - Direct DB access (bypassed by factory pattern)
   - `inmemory/stores/` - Alternative storage (unused)
   - `inmemory/common/` - Mixed utilities (some useful, some not)

## 📋 **Comprehensive Cleanup Plan**

### **Phase 1: Remove Duplicate Configs**
```
❌ DELETE: inmemory/config/ (entire folder)
✅ KEEP: inmemory/configs/ (new -aligned structure)
```

### **Phase 2: Consolidate Search & Services**
```
❌ DELETE: inmemory/search/ (functionality moved to memory/main.py)
❌ DELETE: inmemory/services/ (replaced by memory/main.py)
✅ KEEP: inmemory/memory/main.py (consolidated functionality)
```

### **Phase 3: Clean Up Storage Layer**
```
❌ DELETE: inmemory/stores/ (unused alternative storage)
❌ DELETE: inmemory/repositories/ (bypassed by factory pattern)
✅ KEEP: inmemory/vector_stores/ (used by factory)
```

### **Phase 4: Evaluate API & Common**
```
🤔 EVALUATE: inmemory/api/ (check if server/ folder makes this redundant)
🔧 CLEAN: inmemory/common/ (keep useful utilities, remove unused)
```

### **Phase 5: Update Dependencies**
```
🔄 UPDATE: All import statements
🔄 UPDATE: inmemory/__init__.py exports
🧪 TEST: Ensure functionality still works
```

## 🎯 **Recommended Actions**

### **IMMEDIATE DELETIONS (Safe)**
- `inmemory/config/` - Completely replaced
- `inmemory/search/` - Functionality consolidated
- `inmemory/services/` - Replaced by memory/main.py
- `inmemory/stores/` - Unused
- `inmemory/repositories/qdrant_db.py` - Bypassed by factory

### **KEEP & CONSOLIDATE**
- `inmemory/memory/main.py` - Core functionality ✅
- `inmemory/configs/` - New structure ✅
- `inmemory/vector_stores/` - Used by factory ✅
- `inmemory/embeddings/` - Used by factory ✅
- `inmemory/utils/factory.py` - Core architecture ✅

### **EVALUATE CASE-BY-CASE**
- `inmemory/api/` vs `server/` - Which one is actually used?
- `inmemory/common/constants.py` - May be needed
- `inmemory/security/encryption.py` - May be needed
- `inmemory/common/temporal_utils.py` - May be useful

## 🚀 **Benefits After Cleanup**

1. **Reduced Complexity**: ~50% fewer files
2. **Clear Architecture**: Single source of truth for each function
3. **Easier Maintenance**: No duplicate code to maintain
4. **Better Performance**: Less import overhead
5. **Cleaner API**: Simplified public interface

## ❓ **Questions for You**

1. **API Folder**: Do you use `inmemory/api/` or is `server/` the main FastAPI implementation?
2. **Security**: Do you need the encryption functionality in `inmemory/security/`?
3. **Common Utils**: Any specific utilities in `inmemory/common/` you want to preserve?

Would you like me to proceed with this cleanup plan? I can start with the safe deletions and then we can evaluate the questionable folders together.

**Ready to toggle to Act mode when you approve this plan!** 🎯





-----------------



Yes, I've thoroughly analyzed  testing approach by examining their test files, pyproject.toml configuration, and testing patterns. Here's my **phased implementation plan** for your inmemory testing suite:

## **Phase 1: Foundation Setup (Priority: HIGH)**
**Goal**: Establish basic testing infrastructure and core functionality tests

### **Phase 1A: Testing Infrastructure**
- Set up `pytest` configuration in `pyproject.toml`
- Create `tests/conftest.py` with shared fixtures
- Add testing dependencies to project configuration
- Create basic test structure and CI-ready setup

### **Phase 1B: Core Memory Class Tests**
- `tests/test_memory_main.py` - Test the main Memory class
  - Test `add()` method with various inputs
  - Test `search()` method with different queries
  - Test `get_all()`, `delete()`, `delete_all()` methods
  - Test error handling and edge cases
- Mock external dependencies (Ollama, Qdrant)

**Deliverables**: 
- Basic test runner working
- Core Memory class 80%+ test coverage
- Foundation for all future tests

---

## **Phase 2: Component Testing (Priority: HIGH)**
**Goal**: Test individual components in isolation

### **Phase 2A: Factory and Configuration Tests**
- `tests/test_utils/test_factory.py` - Test EmbeddingFactory, VectorStoreFactory
- `tests/test_configs/test_base_config.py` - Test InMemoryConfig class
- Test configuration validation and defaults

### **Phase 2B: Provider Tests**
- `tests/test_embeddings/test_ollama.py` - Test Ollama embedding provider
- `tests/test_vector_stores/test_qdrant.py` - Test Qdrant vector store
- Mock external service calls

**Deliverables**:
- All factory methods tested
- Configuration validation working
- Provider interfaces tested with mocks

---

## **Phase 3: Client and API Testing (Priority: MEDIUM)**
**Goal**: Test the managed service client and API interactions

### **Phase 3A: InmemoryClient Tests**
- `tests/test_client.py` - Test InmemoryClient class
- Mock HTTP responses using `responses` library
- Test all API methods (add, search, delete, etc.)
- Test authentication and error handling

### **Phase 3B: Security and Utilities**
- `tests/test_security/test_encryption.py` - Test encryption/decryption
- `tests/test_utils/` - Test utility functions
- Test edge cases and error conditions

**Deliverables**:
- Client API fully tested with mocked HTTP
- Security functions validated
- Utility functions covered

---

## **Phase 4: Integration Testing (Priority: MEDIUM)**
**Goal**: Test end-to-end workflows and component interactions

### **Phase 4A: End-to-End Workflows**
- `tests/test_integration/test_end_to_end.py`
- Test complete workflows: add → search → delete
- Test different provider combinations
- Test configuration switching

### **Phase 4B: Server Integration**
- `tests/test_integration/test_server_integration.py`
- Test FastAPI server endpoints (if needed)
- Test SDK + Server interaction

**Deliverables**:
- Complete user workflows tested
- Multi-component integration verified
- Server endpoints validated

---

## **Phase 5: Advanced Testing (Priority: LOW)**
**Goal**: Add advanced testing features and optimization

### **Phase 5A: Performance and Load Testing**
- Add performance benchmarks
- Test with large datasets
- Memory usage testing

### **Phase 5B: Coverage and Quality**
- Achieve 85%+ code coverage
- Add property-based testing (hypothesis)
- Add mutation testing for test quality

**Deliverables**:
- Performance benchmarks established
- High code coverage achieved
- Test quality validated

---

## **Detailed Phase 1 Implementation Plan**

Since you want to start immediately, here's what Phase 1 will include:

### **Files to Create/Modify:**

1. **Update `pyproject.toml`** - Add test dependencies and pytest config
2. **Create `tests/conftest.py`** - Shared fixtures and test utilities
3. **Create `tests/test_memory_main.py`** - Core Memory class tests
4. **Create `tests/__init__.py`** - Make tests a proper package

### **Test Coverage for Phase 1:**
- Memory initialization with different configs
- `add()` method: success cases, error handling, metadata
- `search()` method: various queries, filters, empty results
- `get_all()` method: pagination, filtering
- `delete()` and `delete_all()` methods
- `health_check()` and `get_stats()` methods
- Configuration validation and factory creation

### **Mocking Strategy:**
- Mock Ollama embedding calls
- Mock Qdrant vector store operations
- Mock external HTTP requests
- Use fixtures for consistent test data

**Estimated Time**: Phase 1 should take 1-2 hours to implement completely.

Would you like me to proceed with **Phase 1** implementation? I'm ready to start with the testing infrastructure and core Memory class tests, following the patterns I observed in  codebase.

Perfect! Let's create a detailed phase-by-phase implementation plan that exactly mirrors selfmemory's approach. Here's the comprehensive roadmap:

## Phase-by-Phase Implementation Plan: selfmemory-Style User Isolation

### **Phase 1: Add User Context to Memory Class**

**Current inmemory Memory class:**
```python
class Memory(MemoryBase):
    def __init__(self, config: InMemoryConfig | dict | None = None):
        # No user context
```

**Target selfmemory-style Memory class:**
```python
class Memory(MemoryBase):
    def __init__(self, user_id: str, agent_id: str = None, run_id: str = None, config: InMemoryConfig = None):
        # Add user context like selfmemory
        self.user_id = user_id
        self.agent_id = agent_id  
        self.run_id = run_id
        # ... rest of initialization
```

**Implementation Steps:**
1. **Modify `__init__` method signature**
2. **Add user context validation**
3. **Store user identifiers as instance variables**
4. **Update docstrings and examples**

---

### **Phase 2: Implement selfmemory's Metadata Filtering System**

**selfmemory's approach from their code:**
```python
# From selfmemory's _build_filters_and_metadata function
def _build_filters_and_metadata(
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None, 
    run_id: Optional[str] = None,
    input_metadata: Optional[Dict[str, Any]] = None,
    input_filters: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    # Returns (metadata_for_storage, filters_for_querying)
```

**Our implementation:**
```python
def _build_user_metadata_and_filters(self, additional_metadata: dict = None) -> tuple[dict, dict]:
    """Build metadata for storage and filters for querying (selfmemory style)"""
    
    # Base metadata for storage (like selfmemory)
    storage_metadata = {
        "user_id": self.user_id,
        "created_at": datetime.now().isoformat(),
    }
    
    # Add optional identifiers if provided
    if self.agent_id:
        storage_metadata["agent_id"] = self.agent_id
    if self.run_id:
        storage_metadata["run_id"] = self.run_id
        
    # Add any additional metadata
    if additional_metadata:
        storage_metadata.update(additional_metadata)
    
    # Query filters (same as storage metadata for filtering)
    query_filters = {
        "user_id": self.user_id
    }
    if self.agent_id:
        query_filters["agent_id"] = self.agent_id
    if self.run_id:
        query_filters["run_id"] = self.run_id
        
    return storage_metadata, query_filters
```

---

### **Phase 3: Update add() Method (selfmemory Style)**

**Current inmemory add():**
```python
def add(self, memory_content: str, tags: str = None, **kwargs):
    payload = {
        "data": memory_content,
        "tags": tags or "",
        # No user context!
    }
```

**Target selfmemory-style add():**
```python
def add(self, memory_content: str, tags: str = None, project_id: str = "default", **metadata):
    # Build user-scoped metadata (like selfmemory)
    storage_metadata, _ = self._build_user_metadata_and_filters(metadata)
    
    # Add memory-specific data
    storage_metadata.update({
        "data": memory_content,
        "tags": tags or "",
        "project_id": project_id,
    })
    
    # Generate embedding and store
    embedding = self.embedding_provider.embed(memory_content)
    memory_id = str(uuid.uuid4())
    
    self.vector_store.insert(
        vectors=[embedding],
        payloads=[storage_metadata],  # Now includes user context
        ids=[memory_id]
    )
    
    return {"success": True, "memory_id": memory_id}
```

---

### **Phase 4: Update search() Method (selfmemory Style)**

**Current inmemory search():**
```python
def search(self, query: str, limit: int = 10, **kwargs):
    # No user filtering!
    results = self.vector_store.search(query=query, vectors=embedding, limit=limit)
```

**Target selfmemory-style search():**
```python
def search(self, query: str, limit: int = 10, project_id: str = None, **kwargs):
    # Build user filters (like selfmemory)
    _, query_filters = self._build_user_metadata_and_filters()
    
    # Add project filter if specified
    if project_id:
        query_filters["project_id"] = project_id
    
    # Generate embedding
    query_embedding = self.embedding_provider.embed(query)
    
    # Execute search with user filtering (like selfmemory)
    results = self.vector_store.search(
        query=query,
        vectors=query_embedding,
        filters=query_filters,  # Automatic user isolation
        limit=limit
    )
    
    return {"results": self._format_results(results)}
```

---

### **Phase 5: Update get_all() Method (selfmemory Style)**

**Current inmemory get_all():**
```python
def get_all(self, limit: int = 100):
    # Returns ALL memories from ALL users!
    results = self.vector_store.list(filters=None, limit=limit)
```

**Target selfmemory-style get_all():**
```python
def get_all(self, limit: int = 100, project_id: str = None, **kwargs):
    # Build user filters (like selfmemory)
    _, query_filters = self._build_user_metadata_and_filters()
    
    # Add project filter if specified
    if project_id:
        query_filters["project_id"] = project_id
    
    # Get only user's memories (like selfmemory)
    results = self.vector_store.list(
        filters=query_filters,  # User isolation
        limit=limit
    )
    
    return {"results": self._format_results(results)}
```

---

### **Phase 6: Update delete() Method (selfmemory Style)**

**Current inmemory delete():**
```python
def delete(self, memory_id: str):
    # Can delete ANY memory regardless of user!
    success = self.vector_store.delete(memory_id)
```

**Target selfmemory-style delete():**
```python
def delete(self, memory_id: str):
    # Validate user owns this memory (like selfmemory's approach)
    memory = self.vector_store.get(vector_id=memory_id)
    if not memory:
        return {"success": False, "error": "Memory not found"}
    
    # Check ownership (selfmemory style validation)
    if memory.payload.get("user_id") != self.user_id:
        return {"success": False, "error": "Access denied"}
    
    # Delete only if user owns it
    success = self.vector_store.delete(memory_id)
    return {"success": success}
```

---

### **Phase 7: Update delete_all() Method (selfmemory Style)**

**Current inmemory delete_all():**
```python
def delete_all(self):
    # Deletes ALL memories from ALL users!
    success = self.vector_store.delete_all()
```

**Target selfmemory-style delete_all():**
```python
def delete_all(self, project_id: str = None):
    # Build user filters (like selfmemory)
    _, query_filters = self._build_user_metadata_and_filters()
    
    # Add project filter if specified
    if project_id:
        query_filters["project_id"] = project_id
    
    # Get user's memories only
    memories = self.vector_store.list(filters=query_filters)
    deleted_count = 0
    
    # Delete only user's memories (like selfmemory)
    for memory in memories[0] if isinstance(memories, tuple) else memories:
        if self.vector_store.delete(memory.id):
            deleted_count += 1
    
    return {"success": True, "deleted_count": deleted_count}
```

---

### **Phase 8: Add Helper Methods (selfmemory Style)**

```python
def _format_results(self, results):
    """Format results consistently (like selfmemory)"""
    formatted_results = []
    
    # Handle different result formats from vector stores
    if isinstance(results, tuple) and len(results) > 0:
        points = results[0]
    else:
        points = results if isinstance(results, list) else []
    
    for point in points:
        if hasattr(point, 'id') and hasattr(point, 'payload'):
            formatted_results.append({
                "id": str(point.id),
                "content": point.payload.get("data", ""),
                "score": getattr(point, 'score', 1.0),
                "metadata": point.payload,
            })
    
    return formatted_results

def _validate_user_access(self, memory_id: str) -> bool:
    """Validate user can access memory (selfmemory style)"""
    memory = self.vector_store.get(vector_id=memory_id)
    if not memory:
        return False
    return memory.payload.get("user_id") == self.user_id
```

---

### **Phase 9: Update Usage Examples**

**Current usage:**
```python
# No user context - BROKEN for multi-user
memory = Memory()
memory.add("I love pizza")
```

**Target selfmemory-style usage:**
```python
# User-scoped memory instances (like selfmemory)
user1_memory = Memory(user_id="user_123")
user2_memory = Memory(user_id="user_456")

# Each user gets isolated memories
user1_memory.add("I love pizza", project_id="personal")
user2_memory.add("I love sushi", project_id="personal")

# Searches are automatically isolated
user1_results = user1_memory.search("food")  # Only gets "pizza"
user2_results = user2_memory.search("food")  # Only gets "sushi"
```

---

### **Phase 10: Testing & Validation**

**Test Cases to Implement:**
1. **User Isolation Test:** Verify users can't see each other's memories
2. **Project Filtering Test:** Verify project-level organization works
3. **Access Control Test:** Verify users can't delete others' memories
4. **Migration Test:** Verify existing memories can be migrated
5. **Performance Test:** Verify filtering doesn't impact performance

---

## **Implementation Order:**

1. **Phase 1-2:** Add user context and metadata system
2. **Phase 3-4:** Update add() and search() methods  
3. **Phase 5-7:** Update get_all(), delete(), delete_all() methods
4. **Phase 8:** Add helper methods
5. **Phase 9:** Update documentation and examples
6. **Phase 10:** Comprehensive testing

This gives you **exactly selfmemory's approach** with:
- ✅ Single embedding model per instance
- ✅ User isolation via metadata filtering  
- ✅ Clean separation of concerns
- ✅ Production-ready architecture

Ready to start implementation? We can begin with Phase 1!









---------------------------------------


Perfect! Now I have a complete understanding of your current architecture. Here's the __EXTREMELY DETAILED IMPLEMENTATION PLAN__ broken down into the smallest possible steps:

# 🚀 __COMPREHENSIVE IMPLEMENTATION PLAN__

## __📋 OVERVIEW OF CHANGES__

__3 Major Changes Required:__

1. __Hybrid Dynamic Import System__ (inmemory/configs/base.py + inmemory/utils/factory.py)
2. __Server Architecture Fix__ (server/main.py - remove global instance, add per-request instances)
3. __API Key Authentication__ (server/main.py - implement selfmemory-style auth)

---

## __🔧 PHASE 1: HYBRID DYNAMIC IMPORT SYSTEM__

### __Step 1.1: Update inmemory/configs/base.py__

__Current Issues:__

- Dynamic imports are risky for future expansion
- No caching mechanism
- No static imports for core providers

__Changes Required:__

__File: `inmemory/configs/base.py`__

__Step 1.1.1: Add Static Imports at Top__

```python
# Add these imports at the top of the file (after existing imports)
import importlib
from typing import Dict, Type, Optional

# Static imports for core providers (always loaded)
from inmemory.configs.embeddings.ollama import OllamaConfig
from inmemory.configs.vector_stores.qdrant import QdrantConfig
```

__Step 1.1.2: Update VectorStoreConfig Class__

```python
class VectorStoreConfig(BaseModel):
    """Configuration for vector store providers following pattern."""

    provider: str = Field(default="qdrant", description="Vector store provider")
    config: dict | None = Field(
        default=None, 
        description="Provider-specific configuration dictionary"
    )

    # Static registry for core providers (NEW)
    _static_providers: Dict[str, Type] = {
        "qdrant": QdrantConfig,
    }
    
    # Dynamic registry for future providers (NEW)
    _dynamic_providers: Dict[str, str] = {
        "chroma": "inmemory.configs.vector_stores.chroma.ChromaConfig",
        "pinecone": "inmemory.configs.vector_stores.pinecone.PineconeConfig",
        # Add more as you expand
    }

    _provider_configs = {
        "qdrant": "QdrantConfig",
        "chroma": "ChromaConfig",
        "chromadb": "ChromaConfig",
    }

    @validator("provider")
    def validate_provider(cls, v):
        supported_providers = ["qdrant", "chroma", "chromadb"]
        if v not in supported_providers:
            raise ValueError(
                f"Vector store provider must be one of: {supported_providers}"
            )
        return v

    @model_validator(mode="after")
    def validate_and_create_config(self) -> "VectorStoreConfig":
        """Create provider-specific config object following hybrid pattern."""
        provider = self.provider
        config = self.config

        # Try static first (fast path)
        if provider in self._static_providers:
            config_class = self._static_providers[provider]
        
        # Try dynamic (plugin path)
        elif provider in self._dynamic_providers:
            try:
                module_path = self._dynamic_providers[provider]
                module_name, class_name = module_path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                config_class = getattr(module, class_name)
                
                # Cache for future use (NEW)
                self._static_providers[provider] = config_class
                
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Provider '{provider}' not available: {e}")
        
        # Fallback to old method for backward compatibility
        elif provider in self._provider_configs:
            if provider == "qdrant":
                config_class = QdrantConfig
            else:
                try:
                    module = __import__(
                        f"inmemory.configs.vector_stores.{provider}",
                        fromlist=[self._provider_configs[provider]],
                    )
                    config_class = getattr(module, self._provider_configs[provider])
                except (ImportError, AttributeError) as e:
                    raise ValueError(f"Provider '{provider}' not available: {e}")
        else:
            raise ValueError(f"Unsupported vector store provider: {provider}")

        if config is None:
            config = {}

        if not isinstance(config, dict):
            if not isinstance(config, config_class):
                raise ValueError(f"Invalid config type for provider {provider}")
            return self

        # Create provider-specific config object with defaults
        self.config = config_class(**config)
        return self
```

__Step 1.1.3: Update EmbeddingConfig Class (Same Pattern)__

```python
class EmbeddingConfig(BaseModel):
    """Configuration for embedding providers following pattern."""

    provider: str = Field(default="ollama", description="Embedding provider")
    config: dict | None = Field(
        default=None,
        description="Provider-specific configuration dictionary"
    )

    # Static registry for core providers (NEW)
    _static_providers: Dict[str, Type] = {
        "ollama": OllamaConfig,
    }
    
    # Dynamic registry for future providers (NEW)
    _dynamic_providers: Dict[str, str] = {
        "openai": "inmemory.configs.embeddings.openai.OpenAIConfig",
        "huggingface": "inmemory.configs.embeddings.huggingface.HuggingFaceConfig",
        "cohere": "inmemory.configs.embeddings.cohere.CohereConfig",
    }

    _provider_configs = {
        "ollama": "OllamaConfig",
        "openai": "OpenAIConfig",
    }

    @validator("provider")
    def validate_provider(cls, v):
        supported_providers = ["ollama", "openai"]
        if v not in supported_providers:
            raise ValueError(
                f"Embedding provider must be one of: {supported_providers}"
            )
        return v

    @model_validator(mode="after")
    def validate_and_create_config(self) -> "EmbeddingConfig":
        """Create provider-specific config object following hybrid pattern."""
        provider = self.provider
        config = self.config

        # Try static first (fast path)
        if provider in self._static_providers:
            config_class = self._static_providers[provider]
        
        # Try dynamic (plugin path)
        elif provider in self._dynamic_providers:
            try:
                module_path = self._dynamic_providers[provider]
                module_name, class_name = module_path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                config_class = getattr(module, class_name)
                
                # Cache for future use (NEW)
                self._static_providers[provider] = config_class
                
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Provider '{provider}' not available: {e}")
        
        # Fallback to old method for backward compatibility
        elif provider in self._provider_configs:
            if provider == "ollama":
                config_class = OllamaConfig
            else:
                try:
                    module = __import__(
                        f"inmemory.configs.embeddings.{provider}",
                        fromlist=[self._provider_configs[provider]],
                    )
                    config_class = getattr(module, self._provider_configs[provider])
                except (ImportError, AttributeError) as e:
                    raise ValueError(f"Provider '{provider}' not available: {e}")
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")

        if config is None:
            config = {}

        if not isinstance(config, dict):
            if not isinstance(config, config_class):
                raise ValueError(f"Invalid config type for provider {provider}")
            return self

        # Create provider-specific config object with defaults
        self.config = config_class(**config)
        return self
```

### __Step 1.2: Update inmemory/utils/factory.py__

__Current Issues:__

- No caching for dynamic imports
- Limited error handling
- No static provider registry

__Changes Required:__

__File: `inmemory/utils/factory.py`__

__Step 1.2.1: Add Static Imports and Caching__

```python
"""
Factory pattern for creating provider instances using base.py abstractions.

This module provides clean factory classes that use only base.py interfaces,
making it easy to add new providers without changing the Memory class.

Based on hybrid factory pattern - static core providers + dynamic plugins.
"""

import importlib
from typing import Any, Dict, Optional, Type

from inmemory.embeddings.base import EmbeddingBase
from inmemory.vector_stores.base import VectorStoreBase

# Static imports for core providers
from inmemory.configs.embeddings.ollama import OllamaConfig
from inmemory.configs.vector_stores.qdrant import QdrantConfig


def load_class(class_path: str):
    """Dynamically load a class from a module path."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class EmbeddingFactory:
    """Factory for creating embedding provider instances with hybrid loading."""
    
    # Static provider mappings (always loaded)
    _static_providers = {
        "ollama": "inmemory.embeddings.ollama.OllamaEmbedding",
    }
    
    # Dynamic provider mappings (loaded on demand)
    _dynamic_providers = {
        "openai": "inmemory.embeddings.openai.OpenAIEmbedding",
        "huggingface": "inmemory.embeddings.huggingface.HuggingFaceEmbedding",
        "cohere": "inmemory.embeddings.cohere.CohereEmbedding",
    }
    
    # Cache for loaded dynamic providers
    _loaded_providers: Dict[str, str] = {}
    
    @classmethod
    def create(cls, provider_name: str, config=None) -> EmbeddingBase:
        """
        Create an embedding provider instance using hybrid loading.
        
        Args:
            provider_name: Provider name (e.g., 'ollama')
            config: Pydantic config object or dict with provider-specific configuration
            
        Returns:
            EmbeddingBase: Configured embedding provider instance
            
        Raises:
            ValueError: If provider is not supported
        """
        # Try static providers first (fast path)
        if provider_name in cls._static_providers:
            class_path = cls._static_providers[provider_name]
        
        # Try cached dynamic providers
        elif provider_name in cls._loaded_providers:
            class_path = cls._loaded_providers[provider_name]
        
        # Try dynamic providers (load on demand)
        elif provider_name in cls._dynamic_providers:
            class_path = cls._dynamic_providers[provider_name]
            # Cache for future use
            cls._loaded_providers[provider_name] = class_path
        
        else:
            raise ValueError(f"Unsupported embedding provider: {provider_name}")
        
        try:
            embedding_class = load_class(class_path)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Failed to load provider '{provider_name}': {e}")
        
        # Handle both Pydantic config objects and raw dicts
        if hasattr(config, 'model_dump'):
            # Pydantic config object - convert to dict
            config_dict = config.model_dump()
        elif isinstance(config, dict):
            # Raw dict config
            config_dict = config
        elif config is None:
            # No config provided - use empty dict
            config_dict = {}
        else:
            raise ValueError(f"Invalid config type: {type(config)}")
        
        # Use BaseEmbedderConfig for compatibility
        from inmemory.embeddings.configs import BaseEmbedderConfig
        base_config = BaseEmbedderConfig(**config_dict)
        return embedding_class(base_config)
    
    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported embedding providers."""
        return list(cls._static_providers.keys()) + list(cls._dynamic_providers.keys())
    
    @classmethod
    def register_provider(cls, name: str, class_path: str, static: bool = False):
        """
        Register a new provider dynamically.
        
        Args:
            name: Provider name
            class_path: Full path to provider class
            static: Whether to load immediately (static) or on demand (dynamic)
        """
        if static:
            cls._static_providers[name] = class_path
        else:
            cls._dynamic_providers[name] = class_path


class VectorStoreFactory:
    """Factory for creating vector store provider instances with hybrid loading."""
    
    # Static provider mappings (always loaded)
    _static_providers = {
        "qdrant": "inmemory.vector_stores.qdrant.Qdrant",
    }
    
    # Dynamic provider mappings (loaded on demand)
    _dynamic_providers = {
        "chroma": "inmemory.vector_stores.chroma.ChromaDB",
        "pinecone": "inmemory.vector_stores.pinecone.PineconeDB",
        "weaviate": "inmemory.vector_stores.weaviate.WeaviateDB",
    }
    
    # Cache for loaded dynamic providers
    _loaded_providers: Dict[str, str] = {}
    
    @classmethod
    def create(cls, provider_name: str, config) -> VectorStoreBase:
        """
        Create a vector store provider instance using hybrid loading.
        
        Args:
            provider_name: Provider name (e.g., 'qdrant')
            config: Pydantic config object or dict with provider-specific configuration
            
        Returns:
            VectorStoreBase: Configured vector store provider instance
            
        Raises:
            ValueError: If provider is not supported
        """
        # Try static providers first (fast path)
        if provider_name in cls._static_providers:
            class_path = cls._static_providers[provider_name]
        
        # Try cached dynamic providers
        elif provider_name in cls._loaded_providers:
            class_path = cls._loaded_providers[provider_name]
        
        # Try dynamic providers (load on demand)
        elif provider_name in cls._dynamic_providers:
            class_path = cls._dynamic_providers[provider_name]
            # Cache for future use
            cls._loaded_providers[provider_name] = class_path
        
        else:
            raise ValueError(f"Unsupported vector store provider: {provider_name}")
        
        try:
            vector_store_class = load_class(class_path)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Failed to load provider '{provider_name}': {e}")
        
        # Handle both Pydantic config objects and raw dicts
        if hasattr(config, 'model_dump'):
            # Pydantic config object - convert to dict
            config_dict = config.model_dump()
        elif isinstance(config, dict):
            # Raw dict config
            config_dict = config
        else:
            raise ValueError(f"Invalid config type: {type(config)}")
        
        # Pass config directly to vector store constructor
        return vector_store_class(**config_dict)
    
    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported vector store providers."""
        return list(cls._static_providers.keys()) + list(cls._dynamic_providers.keys())
    
    @classmethod
    def register_provider(cls, name: str, class_path: str, static: bool = False):
        """
        Register a new provider dynamically.
        
        Args:
            name: Provider name
            class_path: Full path to provider class
            static: Whether to load immediately (static) or on demand (dynamic)
        """
        if static:
            cls._static_providers[name] = class_path
        else:
            cls._dynamic_providers[name] = class_path
```

---

## __🔧 PHASE 2: SERVER ARCHITECTURE FIX__

### __Step 2.1: Analyze Current Server Issues__

__Current Problems in server/main.py:__

1. __Line 25__: `MEMORY_INSTANCE = Memory(config=DEFAULT_CONFIG)` - Missing required user_id
2. __Global Instance__: All users share same memory instance
3. __No User Isolation__: Users can see each other's memories
4. __No Authentication__: Anyone can access the API

### __Step 2.2: Complete Server Rewrite__

__File: `server/main.py`__

__Step 2.2.1: Remove Global Instance and Add Imports__

```python
import logging
import os
import hashlib  # NEW - for user_id generation
from typing import Any, Dict, List, Optional
from copy import deepcopy

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends  # NEW - Add Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from inmemory import Memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load environment variables
load_dotenv()

# Environment configuration (following selfmemory pattern)
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = os.environ.get("QDRANT_PORT", "6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "inmemory_memories")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

# Default configuration (selfmemory style)
DEFAULT_CONFIG = {
    "embedding": {
        "provider": "ollama",
        "config": {
            "model": EMBEDDING_MODEL,
            "ollama_base_url": OLLAMA_HOST,
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": QDRANT_HOST,
            "port": int(QDRANT_PORT),
            "collection_name": QDRANT_COLLECTION,
        }
    }
}

# REMOVE THIS LINE - NO MORE GLOBAL INSTANCE
# MEMORY_INSTANCE = Memory(config=DEFAULT_CONFIG)  # DELETE THIS
```

__Step 2.2.2: Add Authentication Function__

```python
def authenticate_api_key(authorization: str = Header(None)) -> str:
    """
    Authenticate API key and return user_id following selfmemory pattern.
    
    Args:
        authorization: Authorization header with Bearer token
        
    Returns:
        str: User ID if valid
        
    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        raise HTTPException(
            status_code=401, 
            detail="Authorization header required. Use: Authorization: Bearer inmem_sk_..."
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, 
            detail="Invalid authorization format. Use: Bearer inmem_sk_..."
        )
    
    api_key = authorization.replace("Bearer ", "")
    
    # Validate API key format
    if not api_key.startswith("inmem_sk_") or len(api_key) < 20:
        raise HTTPException(
            status_code=401, 
            detail="Invalid API key format. Must start with 'inmem_sk_' and be at least 20 characters"
        )
    
    # Generate deterministic user_id from API key (like selfmemory)
    user_id = hashlib.md5(api_key.encode()).hexdigest()
    
    logging.info(f"API key authenticated for user: {user_id[:8]}...")
    return user_id


def _create_user_memory_instance(user_id: str) -> Memory:
    """
    Create a user-scoped Memory instance following selfmemory patterns.
    
    Args:
        user_id: Required user identifier for memory isolation
        
    Returns:
        Memory: User-scoped memory instance
        
    Raises:
        ValueError: If user_id is invalid
    """
    if not user_id:
        raise ValueError("user_id is required for memory operations")
    
    return Memory(user_id=user_id, config=DEFAULT_CONFIG)
```

__Step 2.2.3: Update Pydantic Models__

```python
# Pydantic models (adapted for selfmemory-style multi-user support)
class Message(BaseModel):
    role: str = Field(..., description="Role of the message (user or assistant).")
    content: str = Field(..., description="Message content.")


class MemoryCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to store.")
    metadata: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    limit: int = Field(100, description="Maximum number of results")
    filters: Optional[Dict[str, Any]] = None
    threshold: Optional[float] = None
```

__Step 2.2.4: Update All Endpoints with Authentication__

```python
# API Endpoints (following selfmemory multi-user pattern)

@app.post("/configure", summary="Configure InMemory")
def set_config(config: Dict[str, Any], user_id: str = Depends(authenticate_api_key)):
    """Set memory configuration (updates config for new instances)."""
    global DEFAULT_CONFIG
    DEFAULT_CONFIG.update(config)
    return {"message": "Configuration set successfully", "user_id": user_id[:8] + "..."}


@app.post("/memories", summary="Create memories")
def add_memory(memory_create: MemoryCreate, user_id: str = Depends(authenticate_api_key)):
    """Store new memories with user isolation."""
    try:
        # Create user-scoped Memory instance
        memory_instance = _create_user_memory_instance(user_id)
        
        # Convert messages to memory content (take first user message)
        memory_content = ""
        for message in memory_create.messages:
            if message.role == "user":
                memory_content = message.content
                break
        
        if not memory_content:
            # If no user message, take the first message content
            memory_content = memory_create.messages[0].content if memory_create.messages else ""
        
        if not memory_content:
            raise HTTPException(status_code=400, detail="No valid message content found")
        
        # Add memory using user-scoped instance
        response = memory_instance.add(
            memory_content=memory_content,
            metadata=memory_create.metadata
        )
        
        # Format response to match selfmemory style
        if response.get("success"):
            return JSONResponse(content={
                "results": [{
                    "id": response.get("memory_id"),
                    "memory": memory_content,
                    "event": "ADD"
                }]
            })
        else:
            raise HTTPException(status_code=500, detail=response.get("error", "Failed to add memory"))
            
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories", summary="Get memories")
def get_all_memories(
    limit: int = 100,
    user_id: str = Depends(authenticate_api_key)
):
    """Retrieve stored memories for a specific user."""
    try:
        # Create user-scoped Memory instance
        memory_instance = _create_user_memory_instance(user_id)
        
        # Get user's memories
        response = memory_instance.get_all(limit=limit)
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}", summary="Get a memory")
def get_memory(memory_id: str, user_id: str = Depends(authenticate_api_key)):
    """Retrieve a specific memory by ID with user validation."""
    try:
        # Create user-scoped Memory instance
        memory_instance = _create_user_memory_instance(user_id)
        
        # Validate user owns this memory
        if not memory_instance._validate_user_access(memory_id):
            raise HTTPException(status_code=404, detail="Memory not found or access denied")
        
        # Get all memories and filter by ID
        all_memories = memory_instance.get_all(limit=10000)
        for memory in all_memories.get("results", []):
            if memory.get("id") == memory_id:
                return JSONResponse(content=memory)
        
        raise HTTPException(status_code=404, detail="Memory not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", summary="Search memories")
def search_memories(search_req: SearchRequest, user_id: str = Depends(authenticate_api_key)):
    """Search for memories based on a query with user isolation."""
    try:
        # Create user-scoped Memory instance
        memory_instance = _create_user_memory_instance(user_id)
        
        # Search user's memories
        response = memory_instance.search(
            query=search_req.query,
            limit=search_req.limit,
            threshold=search_req.threshold
        )
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories/{memory_id}", summary="Delete a memory")
def delete_memory(memory_id: str, user_id: str = Depends(authenticate_api_key)):
    """Delete a specific memory by ID with user validation."""
    try:
        # Create user-scoped Memory instance
        memory_instance = _create_user_memory_instance(user_id)
        
        # Delete memory (includes ownership validation)
        response = memory_instance.delete(memory_id)
        
        if response.get("success"):
            return {"message": "Memory deleted successfully"}
        else:
            error_msg = response.get("error", "Memory not found or deletion failed")
            if "Access denied" in error_msg:
                raise HTTPException(status_code=403, detail=error_msg)
            else:
                raise HTTPException(status_code=404, detail=error_msg)
                
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in delete_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories", summary="Delete all memories")
def delete_all_memories(user_id: str = Depends(authenticate_api_key)):
    """Delete all memories for a specific user."""
    try:
        # Create user-scoped Memory instance
        memory_instance = _create_user_memory_instance(user_id)
        
        # Delete all user's memories
        response = memory_instance.delete_all()
        
        if response.get("success"):
            return {"message": f"All memories deleted for user '{user_id[:8]}...'. Count: {response.get('deleted_count', 0)}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete all memories")
            
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in delete_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", summary="Health check")
def health_check():
    """Perform health check on all components."""
    try:
        # Create a temporary memory instance for health check
        temp_memory = Memory(user_id="health_check", config=DEFAULT_CONFIG)
        health = temp_memory.health_check()
        temp_memory.close()
        return JSONResponse(content=health)
    except Exception as e:
        logging.exception("Error in health_check:")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "service": "inmemory"
            }
        )


@app.get("/stats", summary="Get statistics")
def get_stats(user_id: str = Depends(authenticate_api_key)):
    """Get statistics for memories."""
    try:
        # Create a temporary memory instance for stats
        temp_memory = Memory(user_id=user_id, config=DEFAULT_CONFIG)
        stats = temp_memory.get_stats()
        temp_memory.close()
        return JSONResponse(content=stats)
    except Exception as e:
        logging.exception("Error in get_stats:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset", summary="Reset all memories")
def reset_memory(user_id: str = Depends(authenticate_api_key)):
    """Reset all memories for a specific user (same as delete_all)."""
    try:
        # Create user-scoped Memory instance
        memory_instance = _create_user_memory_instance(user_id)
        
        # Delete all user's memories
        response = memory_instance.delete_all()
        
        if response.get("success"):
            return {"message": f"All memories reset for user '{user_id[:8]}...'. Count: {response.get('deleted_count', 0)}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reset memories")
            
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in reset_memory:")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## __🔧 PHASE 3: ADD CONFIG VALIDATION__

### __Step 3.1: Enhance Ollama Config Validation__

__File: `inmemory/configs/embeddings/ollama.py`__

__Step 3.1.1: Add Comprehensive Validators__

```python
"""
Ollama embedding configuration following pattern.
"""

from typing import Any, Dict, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator, validator


class OllamaConfig(BaseModel):
    """
    Configuration for Ollama embedding provider.
    
    Follows embedding config pattern with enhanced validation.
    """
    
    model: str = Field("nomic-embed-text", description="Ollama model name")
    embedding_dims: Optional[int] = Field(768, description="Dimensions of the embedding model")
    ollama_base_url: str = Field("http://localhost:11434", description="Ollama server base URL")
    timeout: int = Field(30, description="Request timeout in seconds")

    @validator("model")
    def validate_model(cls, v):
        """Validate model name is not empty."""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        return v.strip()

    @validator("embedding_dims")
    def validate_embedding_dims(cls, v):
        """Validate embedding dimensions are reasonable."""
        if v is not None and (v <= 0 or v > 10000):
            raise ValueError("Embedding dimensions must be between 1 and 10000")
        return v

    @validator("ollama_base_url")
    def validate_ollama_url(cls, v):
        """Validate Ollama URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Ollama URL must start with http:// or https://")
        
        try:
            result = urlparse(v)
```
Perfect! I'll continue from where we left off in __Step 3.1.1: Add Comprehensive Validators__ for the OllamaConfig class. Let me complete the extremely detailed implementation plan:

---

## __🔧 PHASE 3: ADD CONFIG VALIDATION (CONTINUED)__

### __Step 3.1: Enhance Ollama Config Validation (CONTINUED)__

__File: `inmemory/configs/embeddings/ollama.py`__

__Step 3.1.1: Add Comprehensive Validators (CONTINUED)__

```python
"""
Ollama embedding configuration following pattern.
"""

from typing import Any, Dict, Optional
from urllib.parse import urlparse
import requests
import logging

from pydantic import BaseModel, Field, model_validator, validator

logger = logging.getLogger(__name__)


class OllamaConfig(BaseModel):
    """
    Configuration for Ollama embedding provider.
    
    Follows embedding config pattern with enhanced validation.
    """
    
    model: str = Field("nomic-embed-text", description="Ollama model name")
    embedding_dims: Optional[int] = Field(768, description="Dimensions of the embedding model")
    ollama_base_url: str = Field("http://localhost:11434", description="Ollama server base URL")
    timeout: int = Field(30, description="Request timeout in seconds")
    verify_ssl: bool = Field(True, description="Verify SSL certificates")
    max_retries: int = Field(3, description="Maximum number of retries")

    @validator("model")
    def validate_model(cls, v):
        """Validate model name is not empty and follows naming conventions."""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        
        model_name = v.strip()
        
        # Check for valid characters (alphanumeric, hyphens, underscores, dots)
        if not all(c.isalnum() or c in '-_.' for c in model_name):
            raise ValueError("Model name can only contain alphanumeric characters, hyphens, underscores, and dots")
        
        # Check length
        if len(model_name) > 100:
            raise ValueError("Model name cannot exceed 100 characters")
            
        return model_name

    @validator("embedding_dims")
    def validate_embedding_dims(cls, v):
        """Validate embedding dimensions are reasonable."""
        if v is not None:
            if v <= 0:
                raise ValueError("Embedding dimensions must be positive")
            if v > 10000:
                raise ValueError("Embedding dimensions cannot exceed 10000 (too large)")
            if v < 50:
                raise ValueError("Embedding dimensions should be at least 50 for meaningful embeddings")
        return v

    @validator("ollama_base_url")
    def validate_ollama_url(cls, v):
        """Validate Ollama URL format and accessibility."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Ollama URL must start with http:// or https://")
        
        try:
            result = urlparse(v)
            if not result.netloc:
                raise ValueError("Invalid URL: missing host")
            
            # Remove trailing slash for consistency
            return v.rstrip('/')
            
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")

    @validator("timeout")
    def validate_timeout(cls, v):
        """Validate timeout is reasonable."""
        if v <= 0:
            raise ValueError("Timeout must be positive")
        if v > 300:  # 5 minutes max
            raise ValueError("Timeout cannot exceed 300 seconds")
        return v

    @validator("max_retries")
    def validate_max_retries(cls, v):
        """Validate max retries is reasonable."""
        if v < 0:
            raise ValueError("Max retries cannot be negative")
        if v > 10:
            raise ValueError("Max retries cannot exceed 10")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that no extra fields are provided."""
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

    @model_validator(mode="after")
    def validate_connection(self) -> "OllamaConfig":
        """Validate connection to Ollama server (optional - can be disabled)."""
        # Only validate connection if explicitly requested via environment variable
        import os
        if os.getenv("INMEMORY_VALIDATE_CONNECTIONS", "false").lower() == "true":
            try:
                response = requests.get(
                    f"{self.ollama_base_url}/api/tags",
                    timeout=5,
                    verify=self.verify_ssl
                )
                if response.status_code != 200:
                    logger.warning(f"Ollama server at {self.ollama_base_url} returned status {response.status_code}")
                else:
                    # Check if model exists
                    models = response.json().get("models", [])
                    model_names = [model.get("name", "") for model in models]
                    if self.model not in model_names:
                        logger.warning(f"Model '{self.model}' not found in Ollama. Available models: {model_names}")
                        
            except requests.RequestException as e:
                logger.warning(f"Could not connect to Ollama server at {self.ollama_base_url}: {e}")
            except Exception as e:
                logger.warning(f"Error validating Ollama connection: {e}")
        
        return self

    model_config = {
        "arbitrary_types_allowed": True,
        "validate_assignment": True,
        "extra": "forbid"
    }

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Ollama server and return status."""
        try:
            response = requests.get(
                f"{self.ollama_base_url}/api/tags",
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]
                
                return {
                    "status": "connected",
                    "server_url": self.ollama_base_url,
                    "available_models": model_names,
                    "model_exists": self.model in model_names,
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            else:
                return {
                    "status": "error",
                    "server_url": self.ollama_base_url,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except requests.RequestException as e:
            return {
                "status": "connection_failed",
                "server_url": self.ollama_base_url,
                "error": str(e)
            }
        except Exception as e:
            return {
                "status": "unknown_error",
                "server_url": self.ollama_base_url,
                "error": str(e)
            }
```

### __Step 3.2: Enhance Qdrant Config Validation__

__File: `inmemory/configs/vector_stores/qdrant.py`__

__Step 3.2.1: Add Enhanced Validators__

```python
"""
Qdrant vector store configuration following pattern.
"""

from typing import Any, ClassVar, Dict, Optional
import os
import requests
from pathlib import Path

from pydantic import BaseModel, Field, model_validator, validator


class QdrantConfig(BaseModel):
    """
    Configuration for Qdrant vector store.

    Follows QdrantConfig pattern with enhanced validation.
    """

    collection_name: str = Field("inmemory_memories", description="Name of the collection")
    embedding_model_dims: Optional[int] = Field(768, description="Dimensions of the embedding model")
    host: Optional[str] = Field(None, description="Host address for Qdrant server")
    port: Optional[int] = Field(None, description="Port for Qdrant server")
    path: Optional[str] = Field(None, description="Path for local Qdrant database")
    url: Optional[str] = Field(None, description="Full URL for Qdrant server")
    api_key: Optional[str] = Field(None, description="API key for Qdrant cloud")
    timeout: int = Field(30, description="Request timeout in seconds")
    https: Optional[bool] = Field(None, description="Use HTTPS connection")
    on_disk: bool = Field(False, description="Store vectors on disk")
    prefer_grpc: bool = Field(True, description="Prefer gRPC over HTTP")

    @validator("collection_name")
    def validate_collection_name(cls, v):
        """Validate collection name follows Qdrant naming rules."""
        if not v or not v.strip():
            raise ValueError("Collection name cannot be empty")
        
        name = v.strip()
        
        # Qdrant collection name rules
        if len(name) > 255:
            raise ValueError("Collection name cannot exceed 255 characters")
        
        # Must start with letter or underscore
        if not (name[0].isalpha() or name[0] == '_'):
            raise ValueError("Collection name must start with a letter or underscore")
        
        # Can only contain alphanumeric, underscores, and hyphens
        if not all(c.isalnum() or c in '_-' for c in name):
            raise ValueError("Collection name can only contain letters, numbers, underscores, and hyphens")
            
        return name

    @validator("embedding_model_dims")
    def validate_embedding_dims(cls, v):
        """Validate embedding dimensions."""
        if v is not None:
            if v <= 0:
                raise ValueError("Embedding dimensions must be positive")
            if v > 65536:  # Qdrant limit
                raise ValueError("Embedding dimensions cannot exceed 65536 (Qdrant limit)")
            if v < 50:
                raise ValueError("Embedding dimensions should be at least 50")
        return v

    @validator("host")
    def validate_host(cls, v):
        """Validate host format."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Basic hostname validation
            if len(v) > 253:
                raise ValueError("Host name too long")
        return v

    @validator("port")
    def validate_port(cls, v):
        """Validate port number."""
        if v is not None:
            if v <= 0 or v > 65535:
                raise ValueError("Port must be between 1 and 65535")
        return v

    @validator("path")
    def validate_path(cls, v):
        """Validate local database path."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            
            # Expand user home directory
            expanded_path = os.path.expanduser(v)
            
            # Check if parent directory exists or can be created
            parent_dir = Path(expanded_path).parent
            if not parent_dir.exists():
                try:
                    parent_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise ValueError(f"Cannot create directory {parent_dir}: {e}")
            
            return expanded_path
        return v

    @validator("url")
    def validate_url(cls, v):
        """Validate Qdrant server URL."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            
            if not v.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
            
            # Remove trailing slash
            return v.rstrip('/')
        return v

    @validator("api_key")
    def validate_api_key(cls, v):
        """Validate API key format."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            
            if len(v) < 10:
                raise ValueError("API key too short (minimum 10 characters)")
            if len(v) > 500:
                raise ValueError("API key too long (maximum 500 characters)")
        return v

    @validator("timeout")
    def validate_timeout(cls, v):
        """Validate timeout value."""
        if v <= 0:
            raise ValueError("Timeout must be positive")
        if v > 300:
            raise ValueError("Timeout cannot exceed 300 seconds")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_connection_params(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate connection parameter combinations."""
        path = values.get("path")
        host = values.get("host")
        port = values.get("port")
        url = values.get("url")
        api_key = values.get("api_key")

        # Count connection methods
        connection_methods = sum([
            bool(path),
            bool(host and port),
            bool(url)
        ])

        if connection_methods == 0:
            # Set default path if no connection method specified
            values["path"] = "/tmp/qdrant"
        elif connection_methods > 1:
            raise ValueError(
                "Only one connection method allowed: either 'path' for local, "
                "'host'+'port' for server, or 'url' for full URL"
            )

        # Validate cloud configuration
        if url and api_key:
            if not url.startswith("https://"):
                raise ValueError("Cloud Qdrant (with API key) requires HTTPS URL")

        return values

    @model_validator(mode="after")
    def validate_connection(self) -> "QdrantConfig":
        """Test connection to Qdrant server if requested."""
        import os
        if os.getenv("INMEMORY_VALIDATE_CONNECTIONS", "false").lower() == "true":
            connection_info = self.test_connection()
            if connection_info["status"] != "connected":
                logger.warning(f"Qdrant connection test failed: {connection_info.get('error', 'Unknown error')}")
        
        return self

    model_config = {
        "arbitrary_types_allowed": True,
        "validate_assignment": True,
        "extra": "forbid"
    }

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Qdrant and return status."""
        try:
            if self.path:
                # Local file-based Qdrant
                path_obj = Path(self.path)
                if path_obj.exists():
                    return {
                        "status": "connected",
                        "connection_type": "local_file",
                        "path": str(path_obj),
                        "writable": os.access(path_obj.parent, os.W_OK)
                    }
                else:
                    return {
                        "status": "path_not_exists",
                        "connection_type": "local_file",
                        "path": str(path_obj),
                        "can_create": os.access(path_obj.parent, os.W_OK) if path_obj.parent.exists() else False
                    }
            
            elif self.url:
                # URL-based connection
                test_url = f"{self.url}/collections"
                headers = {}
                if self.api_key:
                    headers["api-key"] = self.api_key
                
                response = requests.get(test_url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    return {
                        "status": "connected",
                        "connection_type": "url",
                        "server_url": self.url,
                        "response_time_ms": response.elapsed.total_seconds() * 1000,
                        "collections": len(response.json().get("result", {}).get("collections", []))
                    }
                else:
                    return {
                        "status": "error",
                        "connection_type": "url",
                        "server_url": self.url,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
            
            elif self.host and self.port:
                # Host + port connection
                protocol = "https" if self.https else "http"
                test_url = f"{protocol}://{self.host}:{self.port}/collections"
                
                response = requests.get(test_url, timeout=5)
                
                if response.status_code == 200:
                    return {
                        "status": "connected",
                        "connection_type": "host_port",
                        "server_url": f"{protocol}://{self.host}:{self.port}",
                        "response_time_ms": response.elapsed.total_seconds() * 1000,
                        "collections": len(response.json().get("result", {}).get("collections", []))
                    }
                else:
                    return {
                        "status": "error",
                        "connection_type": "host_port",
                        "server_url": f"{protocol}://{self.host}:{self.port}",
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
            
            else:
                return {
                    "status": "no_connection_method",
                    "error": "No valid connection method configured"
                }
                
        except requests.RequestException as e:
            return {
                "status": "connection_failed",
                "error": str(e)
            }
        except Exception as e:
            return {
                "status": "unknown_error",
                "error": str(e)
            }
```

### __Step 3.3: Add Factory Validation__

__File: `inmemory/utils/factory.py` (Additional Methods)__

__Step 3.3.1: Add Validation Methods to Factories__

```python
# Add these methods to the existing EmbeddingFactory class

class EmbeddingFactory:
    # ... existing code ...
    
    @classmethod
    def validate_config(cls, provider_name: str, config) -> Dict[str, Any]:
        """
        Validate configuration for a provider without creating instance.
        
        Args:
            provider_name: Provider name
            config: Configuration to validate
            
        Returns:
            Dict with validation results
        """
        try:
            # Create instance to trigger validation
            instance = cls.create(provider_name, config)
            
            # Test connection if config supports it
            if hasattr(instance.config, 'test_connection'):
                connection_test = instance.config.test_connection()
                return {
                    "status": "valid",
                    "provider": provider_name,
                    "connection_test": connection_test
                }
            else:
                return {
                    "status": "valid",
                    "provider": provider_name,
                    "connection_test": {"status": "not_supported"}
                }
                
        except Exception as e:
            return {
                "status": "invalid",
                "provider": provider_name,
                "error": str(e)
            }
    
    @classmethod
    def get_provider_info(cls, provider_name: str) -> Dict[str, Any]:
        """Get information about a provider."""
        if provider_name in cls._static_providers:
            return {
                "provider": provider_name,
                "type": "static",
                "class_path": cls._static_providers[provider_name],
                "loaded": True
            }
        elif provider_name in cls._dynamic_providers:
            return {
                "provider": provider_name,
                "type": "dynamic",
                "class_path": cls._dynamic_providers[provider_name],
                "loaded": provider_name in cls._loaded_providers
            }
        else:
            return {
                "provider": provider_name,
                "type": "unknown",
                "supported": False
            }


# Add these methods to the existing VectorStoreFactory class

class VectorStoreFactory:
    # ... existing code ...
    
    @classmethod
    def validate_config(cls, provider_name: str, config) -> Dict[str, Any]:
        """
        Validate configuration for a provider without creating instance.
        
        Args:
            provider_name: Provider name
            config: Configuration to validate
            
        Returns:
            Dict with validation results
        """
        try:
            # Create instance to trigger validation
            instance = cls.create(provider_name, config)
            
            # Test connection if config supports it
            if hasattr(instance, 'test_connection'):
                connection_test = instance.test_connection()
                return {
                    "status": "valid",
                    "provider": provider_name,
                    "connection_test": connection_test
                }
            else:
                return {
                    "status": "valid",
                    "provider": provider_name,
                    "connection_test": {"status": "not_supported"}
                }
                
        except Exception as e:
            return {
                "status": "invalid",
                "provider": provider_name,
                "error": str(e)
            }
    
    @classmethod
    def get_provider_info(cls, provider_name: str) -> Dict[str, Any]:
        """Get information about a provider."""
        if provider_name in cls._static_providers:
            return {
                "provider": provider_name,
                "type": "static",
                "class_path": cls._static_providers[provider_name],
                "loaded": True
            }
        elif provider_name in cls._dynamic_providers:
            return {
                "provider": provider_name,
                "type": "dynamic",
                "class_path": cls._dynamic_providers[provider_name],
                "loaded": provider_name in cls._loaded_providers
            }
        else:
            return {
                "provider": provider_name,
                "type": "unknown",
                "supported": False
            }
```

---

## __🧪 PHASE 4: TESTING AND VALIDATION__

### __Step 4.1: Create Test Scripts__

__Step 4.1.1: Create Config Validation Test__

__File: `tests/test_enhanced_configs.py`__

```python
"""
Test enhanced configuration validation.
"""

import pytest
from inmemory.configs.embeddings.ollama import OllamaConfig
from inmemory.configs.vector_stores.qdrant import QdrantConfig
from inmemory.utils.factory import EmbeddingFactory, VectorStoreFactory


class TestOllamaConfig:
    """Test OllamaConfig validation."""
    
    def test_valid_config(self):
        """Test valid configuration."""
        config = OllamaConfig(
            model="nomic-embed-text",
            embedding_dims=768,
            ollama_base_url="http://localhost:11434"
        )
        assert config.model == "nomic-embed-text"
        assert config.embedding_dims == 768
        assert config.ollama_base_url == "http://localhost:11434"
    
    def test_invalid_model_name(self):
        """Test invalid model name."""
        with pytest.raises(ValueError, match="Model name cannot be empty"):
            OllamaConfig(model="")
    
    def test_invalid_embedding_dims(self):
        """Test invalid embedding dimensions."""
        with pytest.raises(ValueError, match="Embedding dimensions must be positive"):
            OllamaConfig(embedding_dims=-1)
        
        with pytest.raises(ValueError, match="cannot exceed 10000"):
            OllamaConfig(embedding_dims=20000)
    
    def test_invalid_url(self):
        """Test invalid URL."""
        with pytest.raises(ValueError, match="must start with http"):
            OllamaConfig(ollama_base_url="localhost:11434")
    
    def test_extra_fields(self):
        """Test extra fields rejection."""
        with pytest.raises(ValueError, match="Extra fields not allowed"):
            OllamaConfig(model="test", invalid_field="value")


class TestQdrantConfig:
    """Test QdrantConfig validation."""
    
    def test_valid_local_config(self):
        """Test valid local configuration."""
        config = QdrantConfig(path="/tmp/qdrant")
        assert config.path == "/tmp/qdrant"
    
    def test_valid_server_config(self):
        """Test valid server configuration."""
        config = QdrantConfig(host="localhost", port=6333)
        assert config.host == "localhost"
        assert config.port == 6333
    
    def test_valid_url_config(self):
        """Test valid URL configuration."""
        config = QdrantConfig(url="https://xyz.qdrant.io", api_key="test-key")
        assert config.url == "https://xyz.qdrant.io"
        assert config.api_key == "test-key"
    
    def test_multiple_connection_methods(self):
        """Test rejection of multiple connection methods."""
        with pytest.raises(ValueError, match="Only one connection method allowed"):
            QdrantConfig(path="/tmp/qdrant", host="localhost", port=6333)
    
    def test_invalid_collection_name(self):
        """Test invalid collection name."""
        with pytest.raises(ValueError, match="must start with a letter"):
            QdrantConfig(collection_name="123invalid")


class TestFactoryValidation:
    """Test factory validation methods."""
    
    def test_embedding_factory_validation(self):
        """Test embedding factory validation."""
        config = {"model": "nomic-embed-text", "ollama_base_url": "http://localhost:11434"}
        result = EmbeddingFactory.validate_config("ollama", config)
        assert result["status"] in ["valid", "invalid"]
    
    def test_vector_store_factory_validation(self):
        """Test vector store factory validation."""
        config = {"path": "/tmp/qdrant"}
        result = VectorStoreFactory.validate_config("qdrant", config)
        assert result["status"] in ["valid", "invalid"]
    
    def test_provider_info(self):
        """Test provider info retrieval."""
        info = EmbeddingFactory.get_provider_info("ollama")
        assert info["provider"] == "ollama"
        assert info["type"] in ["static", "dynamic"]
```

### __Step 4.2: Create Integration Test__

__Step 4.2.1: Create Server Integration Test__

__File: `tests/test_server_integration.py`__

```python
"""
Test server integration with new architecture.
"""

import pytest
from fastapi.testclient import TestClient
from server.main import app


class TestServerIntegration:
    """Test server with user isolation."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Create auth headers."""
        return {"Authorization": "Bearer inmem_sk_test_key_12345678901234567890"}
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_add_memory_without_auth(self, client):
        """Test adding memory without authentication."""
        response = client.post("/memories", json={
            "messages": [{"role": "user", "content": "Test memory"}]
        })
        assert response.status_code == 401
    
    def test_add_memory_with_auth(self, client, auth_headers):
        """Test adding memory with authentication."""
        response = client.post("/memories", json={
            "messages": [{"role": "user", "content": "Test memory"}]
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
    
    def test_user_isolation(self, client):
        """Test that users cannot see each other's memories."""
        # User 1 adds memory
        headers1 = {"Authorization": "Bearer inmem_sk_user1_12345678901234567890"}
        response1 = client.post("/memories", json={
            "messages": [{"role": "user", "content": "User 1 memory"}]
        }, headers=headers1)
        assert response1.status_code == 200
        
        # User 2 adds memory
        headers2 = {"Authorization": "Bearer inmem_sk_user2_12345678901234567890"}
        response2 = client.post("/memories", json={
            "messages": [{"role": "user", "content": "User 2 memory"}]
        }, headers=headers2)
        assert response2.status_code == 200
        
        # User 1 gets memories (should only see their own)
        response1_get = client.get("/memories", headers=headers1)
        assert response1_get.status_code == 200
        memories1 = response1_get.json()["results"]
        
        # User 2 gets memories (should only see their own)
        response2_get = client.get("/memories", headers=headers2)
        assert response2_get.status_code == 200
        memories2 = response2_get.json()["results"]
        
        # Verify isolation
        user1_contents = [m["content"] for m in memories1]
        user2_contents = [m["content"] for m in memories2]
        
        assert "User 1 memory" in user1_contents
        assert "User 1 memory" not in user2_contents
        assert "User 2 memory" in user2_contents
        assert "User 2 memory" not in user1_contents
```

---

## __📋 IMPLEMENTATION CHECKLIST__

### __Phase 1: Hybrid Dynamic Import System__

- [ ] __Step 1.1.1__: Add static imports to `inmemory/configs/base.py`
- [ ] __Step 1.1.2__: Update `VectorStoreConfig` with hybrid loading
- [ ] __Step 1.1.3__: Update `EmbeddingConfig` with hybrid loading
- [ ] __Step 1.2.1__: Update `inmemory/utils/factory.py` with caching

### __Phase 2: Server Architecture Fix__

- [ ] __Step 2.2.1__: Remove global Memory instance from `server/main.py`
- [ ] __Step 2.2.2__: Add authentication function with API key → user_id mapping
- [ ] __Step 2.2.3__: Update Pydantic models for selfmemory compatibility
- [ ] __Step 2.2.4__: Update all endpoints with user authentication and isolation

### __Phase 3: Config Validation__

- [ ] __Step 3.1.1__: Add comprehensive validators to `OllamaConfig`
- [ ] __Step 3.2.1__: Add enhanced validators to `QdrantConfig`
- [ ] __Step 3.3.1__: Add validation methods to factory classes

### __Phase 4: Testing__

- [ ] __Step 4.1.1__: Create config validation tests
- [ ] __Step 4.2.1__: Create server integration tests
- [ ] __Step 4.3__: Run all tests and verify functionality

---

## __🚀 EXECUTION ORDER__

1. __Start with Phase 1__ (Hybrid Dynamic Import System) - Foundation
2. __Then Phase 2__ (Server Architecture Fix) - Critical for functionality
3. __Then Phase 3__ (Config Validation) - Quality and robustness
4. __Finally Phase 4__ (Testing) - Verification

__Each phase should be completed and tested before moving to the next phase.__

This completes the extremely detailed implementation plan! Would you like me to help you implement any specific phase, or do you have questions about any of the steps?










------------------------------------


Perfect! After analyzing selfmemory's codebase, I can now see exactly what they have in their closed source platform. Here's what selfmemory likely has in their `api.selfmemory.ai` service that's missing from open source:

## **What selfmemory's Closed Source Platform Contains**

Based on the code analysis, here's what they have behind `api.selfmemory.ai`:

### **1. Multi-Tenant Architecture**
- **Organizations & Projects**: Full org/project hierarchy with member management
- **User Management**: User accounts, profiles, authentication
- **Role-Based Access Control**: READER/OWNER roles, project permissions
- **API Key Management**: Generation, validation, usage tracking

### **2. Enterprise Features**
- **Team Collaboration**: Project members, role assignments
- **Access Control Lists**: Memory-level permissions
- **Audit Logging**: Memory access logs, status history
- **Data Export/Import**: Backup and migration tools

### **3. SaaS Infrastructure**
- **Billing & Usage Tracking**: API usage monitoring
- **Analytics Dashboard**: Memory statistics, usage patterns
- **Rate Limiting**: Per-user/org quotas
- **Multi-Region Support**: Global deployment

### **4. Advanced Memory Features**
- **Memory Categorization**: AI-powered content classification
- **Memory Status Management**: Active/deleted/archived states
- **Memory Relationships**: Cross-references and linking
- **Advanced Search**: Filtering, sorting, pagination

## **Phase-by-Phase Implementation Plan**

### **Phase 1: Foundation (Weeks 1-2)**
**Goal**: Basic multi-tenant architecture

```
inmemory-cloud/
├── app/
│   ├── auth/
│   │   ├── models.py          # User, Organization, Project models
│   │   ├── api_keys.py        # API key generation/validation
│   │   └── middleware.py      # Authentication middleware
│   ├── core/
│   │   ├── database.py        # PostgreSQL setup
│   │   └── config.py          # Environment configuration
│   └── main.py               # FastAPI app
├── migrations/               # Alembic migrations
└── requirements.txt
```

**Features**:
- ✅ User registration/login
- ✅ API key generation (`inmem_sk_*` format)
- ✅ Basic authentication middleware
- ✅ PostgreSQL database setup

### **Phase 2: Organizations & Projects (Weeks 3-4)**
**Goal**: Multi-tenant project structure

**Features**:
- ✅ Organization creation/management
- ✅ Project creation within orgs
- ✅ Project member management (READER/OWNER roles)
- ✅ Project-scoped API keys
- ✅ Memory isolation by project

### **Phase 3: Enhanced Memory Management (Weeks 5-6)**
**Goal**: Advanced memory features

**Features**:
- ✅ Memory categorization (AI-powered)
- ✅ Memory status management (active/deleted/archived)
- ✅ Memory access control lists
- ✅ Advanced search with filters
- ✅ Memory relationships/linking

### **Phase 4: Analytics & Monitoring (Weeks 7-8)**
**Goal**: Usage tracking and insights

**Features**:
- ✅ API usage tracking
- ✅ Memory analytics dashboard
- ✅ User activity monitoring
- ✅ Performance metrics
- ✅ Audit logging

### **Phase 5: Enterprise Features (Weeks 9-10)**
**Goal**: Enterprise-ready capabilities

**Features**:
- ✅ Rate limiting per user/org
- ✅ Data export/import tools
- ✅ Backup and restore
- ✅ SSO integration (optional)
- ✅ Advanced RBAC

### **Phase 6: Billing & SaaS (Weeks 11-12)**
**Goal**: Revenue generation

**Features**:
- ✅ Stripe integration
- ✅ Usage-based billing
- ✅ Subscription management
- ✅ Invoice generation
- ✅ Payment webhooks

## **Technical Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Client   │───▶│  inmemory-cloud │───▶│ inmemory-core   │
│                 │    │   (Auth Layer)  │    │  (Open Source)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   PostgreSQL    │
                       │ (Users/Orgs/etc)│
                       └─────────────────┘
```

## **Database Schema Preview**

```sql
-- Core entities (like selfmemory's openmemory)
users (id, user_id, email, name, created_at)
organizations (id, name, owner_id, created_at)
projects (id, org_id, name, container_tag, created_at)
api_keys (id, user_id, project_id, key_hash, created_at)
project_members (id, project_id, user_id, role)

-- Memory management
memory_access_logs (id, memory_id, user_id, accessed_at)
memory_status_history (id, memory_id, old_state, new_state, changed_by)
```

This mirrors exactly what selfmemory has built but keeps it closed source for competitive advantage. Should we start with Phase 1?




--------------------------------------


Yes, let me create a much more detailed plan with specific technical details for each phase. Let me examine the current server implementations first to give you precise details.

## Detailed Phase-by-Phase Integration Plan

### **Phase 1: Fix Current Proxy & Basic Integration** 
**Duration**: 1-2 hours | **Risk**: Low | **Impact**: Get basic functionality working

#### **Current State Analysis**
- **inmemory-core/server/main.py**: FastAPI server with memory endpoints
- **inmemory-core/inmemory-mcp/main.py**: MCP server for AI agent integration  
- **proxy/proxy_server.py**: Routes `/mcp/*` → port 8080, `/*` → port 8081
- **dashboard**: Static Next.js app with no API integration
- **start.sh**: Has incorrect port assignments causing conflicts

#### **Specific Issues to Fix**:
1. **Port Conflict**: `start.sh` runs MCP server on 8080, but inmemory-cloud also wants 8080
2. **Missing API Client**: Dashboard has no way to call backend APIs
3. **Broken Service Chain**: Services don't know about each other

#### **Phase 1 Detailed Changes**:

**1.1 Fix Port Assignments** (5 minutes)
- Update `start.sh` to run MCP server on port 8080 (as proxy expects)
- Ensure inmemory-core server runs on port 8081 (as proxy expects)
- Remove inmemory-cloud from startup temporarily

**1.2 Add Dashboard API Client** (30 minutes)
- Create `dashboard/src/lib/api-client.ts` with methods:
  - `addMemory(content, tags, metadata)`
  - `searchMemories(query, filters)`
  - `getMemories(limit, offset)`
  - `deleteMemory(id)`
- Configure API base URL to use proxy (port 8000)

**1.3 Add Memory Management Pages** (45 minutes)
- Create `dashboard/src/app/memories/page.tsx` - memory list/search interface
- Create `dashboard/src/app/memories/add/page.tsx` - add memory form
- Add navigation links in dashboard layout

**1.4 Test Basic Flow** (15 minutes)
- Start all services via updated `start.sh`
- Test: Add memory via dashboard → should save to inmemory-core
- Test: Search memories via dashboard → should query inmemory-core
- Test: MCP integration still works for AI agents

#### **Phase 1 Success Criteria**:
✅ Dashboard can add/search memories through proxy  
✅ MCP server accessible for AI agents  
✅ All services start without port conflicts  
✅ Basic memory operations work end-to-end  

---

### **Phase 2: Integrate inmemory-cloud Multi-tenant Layer**
**Duration**: 2-3 hours | **Risk**: Medium | **Impact**: Add user management & organizations

#### **Current State After Phase 1**:
- Basic memory operations working through dashboard
- MCP server functional for AI agents
- No user authentication or multi-tenancy

#### **Phase 2 Detailed Changes**:

**2.1 Configure inmemory-cloud Integration** (45 minutes)
- Update `inmemory-cloud/app/main.py` to run on port 8082
- Configure inmemory-cloud to use inmemory-core SDK properly
- Set up shared MongoDB connection between services
- Add inmemory-cloud to startup script

**2.2 Update Proxy Routing** (30 minutes)
- Add new routes in `proxy/proxy_server.py`:
  - `/api/v1/auth/*` → inmemory-cloud (port 8082)
  - `/api/v1/organizations/*` → inmemory-cloud (port 8082)  
  - `/api/v1/projects/*` → inmemory-cloud (port 8082)
  - `/api/v1/memories/*` → inmemory-core (port 8081) [for now]

**2.3 Add Authentication to Dashboard** (90 minutes)
- Install NextAuth.js in dashboard
- Create `dashboard/src/app/auth/signin/page.tsx` - login page
- Create `dashboard/src/app/auth/signup/page.tsx` - registration page
- Add authentication middleware and protected routes
- Update API client to handle JWT tokens

**2.4 Add Organization Management** (45 minutes)
- Create `dashboard/src/app/organizations/page.tsx` - org list/create
- Create `dashboard/src/app/organizations/[id]/page.tsx` - org details
- Create `dashboard/src/app/projects/page.tsx` - project management
- Update navigation to include org/project context

#### **Phase 2 Success Criteria**:
✅ Users can register/login through dashboard  
✅ Users can create organizations and projects  
✅ Memory operations still work (through inmemory-core)  
✅ MCP server still functional  
✅ Basic multi-tenancy in place  

---

### **Phase 3: Unified Architecture & Full Integration**
**Duration**: 3-4 hours | **Risk**: High | **Impact**: Complete unified system

#### **Current State After Phase 2**:
- User authentication and organizations working
- Memory operations still going directly to inmemory-core
- No project-based memory isolation

#### **Phase 3 Detailed Changes**:

**3.1 Move Memory Operations Through inmemory-cloud** (60 minutes)
- Update proxy to route `/api/v1/memories/*` → inmemory-cloud (port 8082)
- Configure inmemory-cloud to use project-specific container tags
- Ensure memory isolation between projects
- Update dashboard API client to use new endpoints

**3.2 Implement Project-based Memory Isolation** (45 minutes)
- Add project context to all memory operations
- Update MCP server to support project-scoped operations
- Add project selection UI in dashboard
- Ensure memories are properly isolated by project

**3.3 Add Advanced Features** (90 minutes)
- API key management for projects
- Advanced search filters (tags, people, time)
- Memory analytics and insights
- Bulk operations and export/import

**3.4 Production Hardening** (45 minutes)
- Add proper error handling and logging
- Implement rate limiting
- Add health checks for all services
- Create comprehensive monitoring

#### **Phase 3 Success Criteria**:
✅ Complete multi-tenant memory isolation  
✅ Project-based API key management  
✅ Advanced search and filtering  
✅ Production-ready monitoring  
✅ Full feature parity across all interfaces  

---

## **Implementation Strategy**

**Start with Phase 1** - This gets you a working system quickly with minimal risk.

**Each phase builds on the previous** - No breaking changes, only additions.

**Rollback plan** - Each phase can be reverted independently.

**Testing at each phase** - Ensure functionality before moving forward.

Would you like me to start with Phase 1 implementation? I can begin with the port fixes and basic dashboard integration.