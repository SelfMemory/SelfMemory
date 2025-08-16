# Services Module - Memory Documentation

## Overview
The `services` module contains the business logic layer for memory operations. This follows clean architecture principles where services orchestrate the core business workflows.

## Files

### `add_memory.py`
- **Purpose**: Enhanced memory addition with metadata, temporal data, and duplicate detection
- **Key Classes**:
  - `EnhancedMemoryManager`: Main class for memory addition operations
- **Key Functions**:
  - `add_memory_enhanced()`: Main entry point for adding memories with rich metadata
  - `add_memory_with_metadata()`: Core business logic for memory addition
  - `_prepare_metadata()`: Validates and cleans metadata (tags, people, topics)
  - `_create_enhanced_payload()`: Creates encrypted payload for storage
- **Dependencies**: Uses repositories (qdrant_db, mongodb_user_manager), utils (embeddings), common (constants, temporal_utils, duplicate_detector), security (encryption)

### `retrieve_memory.py`
- **Purpose**: Basic memory retrieval functionality using semantic similarity
- **Key Functions**:
  - `retrieve_memories()`: Main function for retrieving similar memories
  - `search_memories_with_filter()`: Retrieval with keyword filtering
- **Dependencies**: Uses repositories (qdrant_db, mongodb_user_manager), utils (embeddings), common (constants), security (encryption)

## Business Logic Flow
1. **Memory Addition**: EnhancedMemoryManager → validate metadata → check duplicates → generate temporal data → encrypt → store
2. **Memory Retrieval**: generate embedding → search Qdrant → decrypt results → format response

## Important Notes
- All memories are encrypted before storage
- Duplicate detection is optional but enabled by default
- Temporal metadata is automatically generated
- User isolation enforced through collection naming
