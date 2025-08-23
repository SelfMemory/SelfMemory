# InMemory - Enhanced Memory Management for AI

<p align="center">
  <strong>🧠 Long-term memory for AI Agents with zero-setup simplicity</strong>
</p>

<p align="center">
  <strong>⚡ Zero Setup • 🚀 Instant Library • 💼 REST API Ready</strong>
</p>

## 🔥 Key Features

- **🚀 Zero Setup**: `pip install inmemory` and start using immediately
- **🏗️ Dual Architecture**: Local Memory class + Managed InmemoryClient
- **🔍 Advanced Search**: Semantic similarity with ChromaDB embeddings
- **🌐 Two Usage Modes**: Direct library usage OR REST API server
- **💼 Dashboard Ready**: MongoDB authentication + clean REST endpoints

## 🚀 Quick Start

### Zero-Setup Library Usage

```bash
pip install inmemory
```

```python
from inmemory import Memory

# Works immediately - no setup required!
memory = Memory()

# Add memories with metadata
memory.add(
    "I love pizza but hate broccoli",
    tags="food,preferences"
)

memory.add(
    "Meeting with Bob and Carol about Q4 planning tomorrow at 3pm",
    tags="work,meeting",
    people_mentioned="Bob,Carol",
    topic_category="planning"
)

# Search memories
results = memory.search("pizza")
for result in results["results"]:
    print(f"Memory: {result['content']}")
    print(f"Score: {result['score']}")

# Health check
health = memory.health_check()
print(f"Status: {health['status']}")
```

### Managed Client Usage (Dashboard Integration)

```python
from inmemory import InmemoryClient

# Connect to managed service
client = InmemoryClient(
    api_key="your_api_key",
    host="http://localhost:8081"
)

# Same API as Memory, but with authentication
client.add("Meeting notes from dashboard", tags="dashboard")
results = client.search("meeting notes")
```

### REST API Server Mode

```bash
# Start the server (from inmemory-core directory)
cd server/
python main.py

# Or with custom configuration
MONGODB_URI=mongodb://localhost:27017/inmemory python main.py
```

Server runs on http://localhost:8081 with endpoints:
- `POST /v1/memories` - Add memory
- `GET /v1/memories` - Get all memories
- `POST /v1/search` - Search memories
- `DELETE /v1/memories/{id}` - Delete memory

## 📦 Installation Options

| Mode | Command | Dependencies | Use Case |
|------|---------|--------------|----------|
| **Basic SDK** | `pip install inmemory` | Zero external deps | Development, testing, simple apps |
| **API Server** | `pip install inmemory[server]` | FastAPI, Uvicorn | Integration, dashboards |
| **Enterprise** | `pip install inmemory[enterprise]` | MongoDB, OAuth | Production, multi-user |
| **Full** | `pip install inmemory[full]` | Everything + MCP | Complete installation |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     InMemory Package                         │
├─────────────────────────────────────────────────────────────┤
│  SDK Layer    │ Memory Class (Primary Interface)            │
│  API Layer    │ FastAPI Server (Optional)                   │
│  Storage Layer│ File (Default) │ MongoDB (Enterprise)       │
│  Search Layer │ Enhanced Search Engine + Qdrant            │
└─────────────────────────────────────────────────────────────┘
```

## 💡 Core API Reference

### Memory Class

```python
from inmemory import Memory

# Initialize with different backends
memory = Memory()                        # Auto-detect (file by default)
memory = Memory(storage_type="file")     # Force file storage
memory = Memory(storage_type="mongodb")  # Force MongoDB (requires deps)

# Memory operations
result = memory.add(content, user_id, tags=None, people_mentioned=None, topic_category=None)
results = memory.search(query, user_id, limit=10, tags=None, temporal_filter=None)
memories = memory.get_all(user_id, limit=100)
result = memory.delete(memory_id, user_id)

# Advanced search
results = memory.search_by_tags(["work", "important"], user_id, match_all=True)
results = memory.search_by_people(["Alice", "Bob"], user_id)
results = memory.temporal_search("yesterday", user_id, semantic_query="meetings")

# User management
result = memory.create_user(user_id, email="user@example.com")
api_key = memory.generate_api_key(user_id, name="my-app")
keys = memory.list_api_keys(user_id)
stats = memory.get_user_stats(user_id)
```

### Configuration

```python
from inmemory import InMemoryConfig, Memory

# Custom configuration
config = InMemoryConfig(
    storage={
        "type": "file",           # or "mongodb"
        "path": "~/my-memories"   # for file storage
    },
    auth={
        "type": "simple",         # or "oauth", "api_key"
        "default_user": "my_user"
    },
    qdrant={
        "host": "localhost",
        "port": 6333
    }
)

memory = Memory(config=config)
```

## 🌐 REST API Endpoints

When running in server mode (`inmemory serve`), these endpoints are available:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/memories` | Add new memory |
| `GET` | `/v1/memories` | Get user's memories |
| `DELETE` | `/v1/memories/{id}` | Delete specific memory |
| `POST` | `/v1/search` | Search memories |
| `POST` | `/v1/temporal-search` | Temporal search |
| `POST` | `/v1/search-by-tags` | Tag-based search |
| `POST` | `/v1/search-by-people` | People-based search |
| `GET` | `/v1/health` | Health check |

## 🔧 Configuration Options

### Environment Variables

```bash
# Storage backend
export INMEMORY_STORAGE_TYPE="file"           # or "mongodb"
export INMEMORY_DATA_DIR="~/.inmemory"        # for file storage
export MONGODB_URI="mongodb://localhost:27017/inmemory" # for mongodb

# Server settings
export INMEMORY_HOST="0.0.0.0"
export INMEMORY_PORT="8081"

# Qdrant settings
export QDRANT_HOST="localhost"
export QDRANT_PORT="6333"
```

### YAML Configuration

Create `~/.inmemory/config.yaml`:

```yaml
storage:
  type: "file"              # or "mongodb"
  path: "~/.inmemory/data"

auth:
  type: "simple"            # or "oauth", "api_key"
  default_user: "user123"

qdrant:
  host: "localhost"
  port: 6333

embedding:
  provider: "ollama"
  model: "nomic-embed-text"
  ollama_host: "http://localhost:11434"
```

## 🚀 Deployment

### Single File Deployment
```bash
# Just run the server - file storage included
inmemory serve --port 8080
```

### Docker Deployment
```bash
# Simple mode (file storage)
docker run -p 8080:8080 -v inmemory-data:/root/.inmemory inmemory:latest

# Enterprise mode (MongoDB)
docker-compose up  # Uses provided docker-compose.yml
```

### Production Deployment
```bash
# Enterprise mode with MongoDB
export MONGODB_URI="mongodb://prod-mongo:27017/inmemory"
export GOOGLE_CLIENT_ID="your-prod-client-id"
export GOOGLE_CLIENT_SECRET="your-prod-client-secret"

inmemory serve --host 0.0.0.0 --port 8080
```

## 🔄 Migration Between Modes

Easily migrate from simple file storage to enterprise MongoDB:

```python
from inmemory.stores import FileBasedStore, MongoDBStore

# Initialize both backends
file_store = FileBasedStore()
mongo_store = MongoDBStore(mongodb_uri="mongodb://localhost:27017")

# Migrate all data
success = mongo_store.migrate_from_file_store(file_store)
print(f"Migration {'successful' if success else 'failed'}!")
```

## 🧪 Development & Testing

```bash
# Install with development tools
pip install inmemory[dev]

# Run tests
inmemory test

# Check configuration
inmemory config

# View storage statistics
inmemory stats

# Initialize with sample data
inmemory init
```

## 🤝 Integration Examples

### Personal AI Assistant
```python
from inmemory import Memory
from openai import OpenAI

class PersonalAssistant:
    def __init__(self):
        self.memory = Memory()
        self.llm = OpenAI()

    def chat(self, user_input: str, user_id: str) -> str:
        # Get relevant memories
        memories = self.memory.search(user_input, user_id=user_id, limit=5)
        context = "\n".join([m['memory'] for m in memories['results']])

        # Generate response with context
        response = self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Context: {context}"},
                {"role": "user", "content": user_input}
            ]
        )

        # Store conversation
        self.memory.add(f"User: {user_input}", user_id=user_id)
        self.memory.add(f"Assistant: {response.choices[0].message.content}", user_id=user_id)

        return response.choices[0].message.content
```

### Customer Support Bot
```python
from inmemory import Memory

class SupportBot:
    def __init__(self):
        self.memory = Memory()

    def handle_ticket(self, customer_id: str, issue: str):
        # Check customer history
        history = self.memory.search_by_people([customer_id], user_id="support")
        similar_issues = self.memory.search(issue, user_id="support", limit=3)

        # Generate contextual response based on history
        response = self.generate_response(issue, history, similar_issues)

        # Store interaction
        self.memory.add(
            f"Customer {customer_id} reported: {issue}",
            user_id="support",
            tags="ticket,customer_support",
            people_mentioned=customer_id,
            topic_category="support"
        )

        return response
```

## 📚 Documentation

- **[Installation Guide](docs/installation-guide.md)**: Detailed installation and usage
- **[Architecture Plan](docs/open-source-architecture-plan.md)**: Technical architecture details
- **[API Reference](http://localhost:8081/docs)**: Interactive API documentation (when server running)

## 🏢 Enterprise Features

For enterprise deployments, InMemory provides:

- **Multi-user Support**: MongoDB backend with user isolation
- **OAuth Integration**: Google OAuth for dashboard authentication
- **Scalable Storage**: MongoDB collections per user
- **API Key Management**: Secure key generation and management
- **Dashboard Ready**: REST API for your private dashboard integration

## 🤖 MCP Server Integration

InMemory works seamlessly with MCP (Model Context Protocol) for AI agent integration:

```bash
# Separate repository for MCP server
git clone https://github.com/you/inmemory-mcp
cd inmemory-mcp
pip install -e .

# Configure to connect to any InMemory API
export INMEMORY_API_URL="http://localhost:8080"
python src/server.py
```

## 🛠️ Requirements

### Minimal Installation
- **Python**: 3.10+ (supports Python 3.10, 3.11, 3.12, 3.13)
- **Qdrant**: Vector database for embeddings
- **Ollama**: Local embeddings (or OpenAI API key)

### Enterprise Installation
- **MongoDB**: User management and authentication
- **Google OAuth**: Dashboard authentication

## 🎯 Roadmap

- [x] **Storage Abstraction**: File-based and MongoDB backends
- [x] **CLI Tools**: Easy server management
- [ ] **PostgreSQL Backend**: Alternative to MongoDB
- [ ] **TypeScript SDK**: Cross-language support
- [ ] **More Vector DBs**: Chroma, Pinecone integration
- [ ] **Cloud Storage**: S3, GCS backends

## 🤝 Contributing

We welcome contributions! Please see:

- **Issues**: Report bugs and request features
- **Pull Requests**: Follow our coding standards (ruff, pre-commit)
- **Documentation**: Help improve our guides

```bash
# Development setup
git clone https://github.com/you/inmemory
cd inmemory
pip install -e .[dev]
pre-commit install

# Run tests
inmemory test
pytest
```

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE.txt) file for details.

## 🙏 Acknowledgments

- **FastAPI**: Excellent API framework
- **Qdrant**: High-performance vector database
- **Pydantic**: Data validation and configuration

---

<p align="center">
  <strong>Start simple. Scale seamlessly. 🚀</strong>
</p>
