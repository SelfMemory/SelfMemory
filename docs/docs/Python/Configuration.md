---
sidebar_position: 3
---

# Configuration Guide

Learn how to configure SelfMemory for different use cases and environments.

## Configuration Methods

SelfMemory can be configured in three ways:

1. **Python Dictionary** - Pass config directly to `SelfMemory(config=...)`
2. **YAML File** - Create `~/.selfmemory/config.yaml`
3. **Environment Variables** - Set environment variables

## Complete Configuration Example

```python
from selfmemory import SelfMemory

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "my_memories",
            "embedding_model_dims": 768,
            "host": "localhost",
            "port": 6333
        }
    },
    "embedding": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434"
        }
    },
    "storage": {
        "type": "file",  # or "mongodb"
        "path": "~/.selfmemory/data"
    },
    "auth": {
        "type": "simple",  # or "oauth", "api_key"
        "default_user": "user123"
    }
}

memory = SelfMemory(config=config)
```

## Vector Store Configuration

### Qdrant (Recommended)

```python
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "memories",
            "embedding_model_dims": 768,  # nomic-embed-text dimension
            "host": "localhost",
            "port": 6333,
            "url": None,  # Optional: use URL instead of host:port
            "api_key": None  # Optional: for Qdrant Cloud
        }
    }
}
```

**Starting Qdrant:**
```bash
docker run -p 6333:6333 qdrant/qdrant
```

### ChromaDB

```python
config = {
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "memories",
            "persist_directory": "~/.selfmemory/chroma"
        }
    }
}
```

## Embedding Configuration

### Ollama (Recommended for Local)

```python
config = {
    "embedding": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434"
        }
    }
}
```

**Starting Ollama:**
```bash
ollama serve
ollama pull nomic-embed-text
```

**Available Models:**
- `nomic-embed-text` (768 dims) - Recommended
- `mxbai-embed-large` (1024 dims)
- `all-minilm` (384 dims) - Faster, smaller

### OpenAI

```python
config = {
    "embedding": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
            "api_key": "sk-..."  # Or set OPENAI_API_KEY env var
        }
    }
}
```

**Available Models:**
- `text-embedding-3-small` (1536 dims) - Recommended
- `text-embedding-3-large` (3072 dims) - More powerful
- `text-embedding-ada-002` (1536 dims) - Legacy

## Storage Configuration

### File-Based Storage (Default)

```python
config = {
    "storage": {
        "type": "file",
        "path": "~/.selfmemory/data"
    }
}
```

**Advantages:**
- Zero setup required
- Perfect for development and testing
- Easy to backup and migrate

### MongoDB Storage

```python
config = {
    "storage": {
        "type": "mongodb",
        "uri": "mongodb://localhost:27017/selfmemory"
    }
}
```

**Starting MongoDB:**
```bash
docker run -p 27017:27017 mongo:latest
```

**Advantages:**
- Multi-user support
- Better performance at scale
- Production-ready
- Built-in replication and backup

## Authentication Configuration

### Simple Auth (Development)

```python
config = {
    "auth": {
        "type": "simple",
        "default_user": "demo_user"
    }
}
```

### API Key Auth (Production)

```python
config = {
    "auth": {
        "type": "api_key",
        "require_api_key": True
    }
}
```

### OAuth (Dashboard Integration)

```python
config = {
    "auth": {
        "type": "oauth",
        "google_client_id": "your-client-id",
        "google_client_secret": "your-secret"
    }
}
```

## YAML Configuration File

Create `~/.selfmemory/config.yaml`:

```yaml
vector_store:
  provider: qdrant
  config:
    collection_name: memories
    embedding_model_dims: 768
    host: localhost
    port: 6333

embedding:
  provider: ollama
  config:
    model: nomic-embed-text
    ollama_base_url: http://localhost:11434

storage:
  type: file
  path: ~/.selfmemory/data

auth:
  type: simple
  default_user: user123
```

Then use it:

```python
from selfmemory import SelfMemory

# Automatically loads from ~/.selfmemory/config.yaml
memory = SelfMemory()
```

## Environment Variables

```bash
# Storage backend
export SELFMEMORY_STORAGE_TYPE="file"  # or "mongodb"
export SELFMEMORY_DATA_DIR="~/.selfmemory"
export MONGODB_URI="mongodb://localhost:27017/selfmemory"

# Qdrant settings
export QDRANT_HOST="localhost"
export QDRANT_PORT="6333"
export QDRANT_API_KEY=""  # Optional

# Ollama settings
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="nomic-embed-text"

# OpenAI settings
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="text-embedding-3-small"

# Server settings (when running REST API)
export SELFMEMORY_HOST="0.0.0.0"
export SELFMEMORY_PORT="8081"
```

## Configuration Priority

SelfMemory loads configuration in this order (later overrides earlier):

1. Default values
2. YAML config file (`~/.selfmemory/config.yaml`)
3. Environment variables
4. Python config dictionary passed to `SelfMemory(config=...)`

## Common Configuration Patterns

### Development Setup

```python
config = {
    "vector_store": {"provider": "qdrant"},
    "embedding": {"provider": "ollama"},
    "storage": {"type": "file"},
    "auth": {"type": "simple"}
}
```

### Production Setup

```python
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "url": "https://your-cluster.qdrant.cloud",
            "api_key": os.getenv("QDRANT_API_KEY")
        }
    },
    "embedding": {
        "provider": "openai",
        "config": {
            "api_key": os.getenv("OPENAI_API_KEY")
        }
    },
    "storage": {
        "type": "mongodb",
        "uri": os.getenv("MONGODB_URI")
    },
    "auth": {
        "type": "api_key"
    }
}
```

### Local Testing (Zero Config)

```python
# Uses all defaults - perfect for quick testing
memory = SelfMemory()
```

## Troubleshooting

### Connection Issues

```python
# Test Qdrant connection
import requests
response = requests.get("http://localhost:6333/health")
print(response.json())  # Should return {"status": "ok"}

# Test Ollama connection
response = requests.get("http://localhost:11434/api/tags")
print(response.json())  # Should list available models
```

### Dimension Mismatch

Ensure your vector store dimension matches your embedding model:

- `nomic-embed-text`: 768 dims
- `text-embedding-3-small`: 1536 dims
- `text-embedding-3-large`: 3072 dims

```python
config = {
    "vector_store": {
        "config": {
            "embedding_model_dims": 768  # Must match model!
        }
    }
}
```

## Next Steps

- Return to [Quick Start Guide](./QuickStart.md)
- Learn about [Client Usage](./Client.md)
- Explore [API Keys](../Platform/API%20Key%20page.md)
