# Embeddings Module Memory

## Purpose
This module provides a pluggable embeddings system that supports multiple embedding providers.

## Architecture
- **Factory Pattern**: Uses `get_embedding_provider()` to create provider instances
- **Provider-based**: Each provider implements the `EmbeddingBase` abstract class
- **Conditional Imports**: Providers are loaded only when requested, avoiding hard dependencies

## Files
- `base.py` - Abstract base class `EmbeddingBase` for all embedding providers
- `ollama.py` - Ollama embedding provider with conditional imports
- `openai.py` - OpenAI embedding provider with conditional imports
- `__init__.py` - Factory function and provider registration

## Key Functions

### base.py
- `EmbeddingBase.embed(text, memory_action)` - Abstract method for generating embeddings
- All providers must implement this method

### ollama.py
- `OllamaEmbedding.__init__(config)` - Initialize with configuration
- `OllamaEmbedding.embed(text)` - Generate embeddings using Ollama
- `_ensure_model_exists()` - Automatically pull model if not available

### openai.py
- `OpenAIEmbedding.__init__(config)` - Initialize with API key and configuration
- `OpenAIEmbedding.embed(text)` - Generate embeddings using OpenAI API
- Supports custom base URLs and dimension settings

### __init__.py
- `get_embedding_provider(provider, config)` - Factory function to create provider instances
- Supports: "ollama", "openai"

## Configuration
Providers are configured through `InMemoryConfig.embedding`:
```python
config.embedding.provider = "ollama"  # or "openai"
config.embedding.embedding_model = "nomic-embed-text"
config.embedding.embedding_dims = 512
config.embedding.ollama_base_url = "http://localhost:11434"
config.embedding.openai_api_key = "sk-..."
```

## Usage
```python
from inmemory.embeddings import get_embedding_provider
from inmemory.config.config import InMemoryConfig

config = InMemoryConfig()
provider = get_embedding_provider("ollama", config)
embeddings = provider.embed("Hello world")
```

## Benefits
- No hardcoded dependencies on specific providers
- Easy to add new embedding providers
- Users can choose their preferred provider
- Backward compatibility maintained through utils.embeddings
