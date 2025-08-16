# File Reorganization Plan

## Overview
Reorganizing Python files from root directory into the `src/` folder structure following clean architecture principles.

## Target Structure
```
Root Level:
- main.py (renamed from api_server.py) - Primary API server entry point
- enhanced_mcp_server.py (stays in root) - MCP server
- proxy_server.py (stays in root) - Reverse proxy server

src/
├── inmemory/
│   ├── backends/                   # Database connections
│   │   ├── qdrant_db.py           # moved from root
│   │   └── mongodb_user_manager.py # moved from root
│   ├── core/                       # Core business logic
│   │   ├── add_memory.py          # renamed from add_memory_to_collection.py
│   │   └── retrieve_memory.py     # renamed from retrieve_memory_from_collection.py
│   └── utils/                      # Utilities
│       └── embeddings.py         # renamed from generate_embeddings.py
├── shared/                         # Shared utilities
│   ├── constants.py               # moved from root
│   ├── duplicate_detector.py      # existing
│   └── temporal_utils.py          # existing
├── search/                         # Search functionality
│   └── enhanced_search_engine.py  # existing
└── security/                       # Security
    └── encryption.py               # existing
```

## File Movement Plan

### Phase 1: Create new directories
- [x] Create src/inmemory/backends/
- [x] Create src/inmemory/core/
- [x] Create src/inmemory/utils/

### Phase 2: Move and rename files
- [ ] api_server.py → main.py (rename only, stay in root)
- [ ] qdrant_db.py → src/inmemory/backends/qdrant_db.py
- [ ] mongodb_user_manager.py → src/inmemory/backends/mongodb_user_manager.py
- [ ] add_memory_to_collection.py → src/inmemory/core/add_memory.py
- [ ] retrieve_memory_from_collection.py → src/inmemory/core/retrieve_memory.py
- [ ] generate_embeddings.py → src/inmemory/utils/embeddings.py
- [ ] constants.py → src/shared/constants.py

### Phase 3: Update imports in all files
- [ ] Update main.py imports
- [ ] Update enhanced_mcp_server.py imports
- [ ] Update proxy_server.py imports
- [ ] Update all moved files' internal imports
- [ ] Update search/enhanced_search_engine.py imports
- [ ] Update security/encryption.py imports if needed

### Phase 4: Create/Update Memory.md files
- [ ] Create src/inmemory/inmemory-Memory.md
- [ ] Create src/inmemory/backends/backends-Memory.md
- [ ] Create src/inmemory/core/core-Memory.md
- [ ] Create src/inmemory/utils/utils-Memory.md
- [ ] Update src/shared/shared-Memory.md
- [ ] Update src/search/search-Memory.md
- [ ] Update src/security/security-Memory.md

### Phase 5: Testing
- [ ] Verify all imports work
- [ ] Test that servers can start
- [ ] Ensure no broken dependencies

## Files Staying in Root
- enhanced_mcp_server.py (MCP server entry point)
- proxy_server.py (Reverse proxy entry point)
- Configuration files (.env.example, pyproject.toml, etc.)
- Documentation (README.md)

## Benefits
1. **Clear separation of concerns** - Database, core logic, utilities separated
2. **Better maintainability** - Related files grouped together
3. **Clean architecture** - Dependencies flow inward
4. **Uncle Bob's principles** - Single responsibility, proper organization
