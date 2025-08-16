# Utils Module - Memory Documentation

## Overview
The `utils` module contains utility functions and helpers that support the core memory operations. These are reusable components that don't contain business logic but provide essential functionality.

## Files

### `embeddings.py`
- **Purpose**: Ollama embedding generation and management for text vectorization
- **Key Functions**:
  - `generate_embeddings(text)`: Generates embeddings using Ollama API
  - `get_embeddings(text)`: Simplified interface to get embedding vectors
- **Key Variables**:
  - `embedding_client`: Ollama client instance for embedding operations
- **Dependencies**: Uses common (constants) for model configuration
- **Model**: Uses `mxbai-embed-large` model via Ollama
- **Output**: Returns 1024-dimensional float vectors

## Usage Patterns
- Thread-safe embedding generation
- Error handling with descriptive messages
- Text validation and preprocessing
- Consistent vector format for Qdrant storage

## Important Notes
- Requires Ollama server running locally
- Vector dimensions must match Qdrant collection configuration
- Empty text validation prevents errors downstream
- Embedding model configured in common/constants.py
