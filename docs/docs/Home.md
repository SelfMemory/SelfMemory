---
sidebar_position: 1
slug: /
---

# SelfMemory Documentation

**Long-term memory for AI Agents with zero-setup simplicity**

## 🚀 Quick Start

Install SelfMemory with a single command:

```bash
pip install selfmemory
```

Start using it immediately:

```python
from selfmemory import SelfMemory

# Works out of the box!
memory = SelfMemory()

# Add memories
memory.add("I love pizza but hate broccoli", user_id="demo")
memory.add("Meeting with Bob tomorrow at 3pm", user_id="demo")

# Search memories
results = memory.search("pizza", user_id="demo")
print(results)
```

## 🔥 Key Features

- **Zero Setup**: Install and start using immediately - no configuration required
- **Dual Architecture**: Direct library usage OR managed client with REST API
- **Advanced Search**: Semantic similarity with vector embeddings
- **Flexible Storage**: File-based or MongoDB backend
- **Production Ready**: Authentication, API keys, and dashboard integration

## 📚 Documentation Sections

### For Developers

- **[Quick Start Guide](./Python/QuickStart.md)**: Get started with SelfMemory in 5 minutes
- **[Client Usage](./Python/Client.md)**: Using SelfMemoryClient with the REST API
- **[Configuration](./Python/Configuration.md)**: Advanced configuration options

### For Platform Users

- **[API Keys](./Platform/API%20Key%20page.md)**: Managing your API keys

## 🏗️ Architecture

SelfMemory provides two usage modes:

1. **Direct Library Usage**: Import and use the `SelfMemory` class directly in your Python code
2. **Client/Server Mode**: Run a REST API server and connect with `SelfMemoryClient`

Both modes support:
- Semantic search with embeddings (Ollama, OpenAI)
- Vector storage (Qdrant, ChromaDB)
- Metadata and tagging
- User isolation

## 💡 Use Cases

- **Personal AI Assistants**: Remember user preferences and conversation history
- **Customer Support Bots**: Maintain customer interaction history
- **Research Tools**: Store and retrieve research notes
- **Team Collaboration**: Shared memory across AI agents

## 🔗 Quick Links

- [GitHub Repository](https://github.com/selfmemory/selfmemory)
- [Discord Community](https://discord.com/invite/YypBvdUpcc)
- [X/Twitter](https://x.com/selfmemoryai)

## 🤝 Contributing

We welcome contributions! Check out our [GitHub repository](https://github.com/selfmemory/selfmemory) to get started.

## 📄 License

SelfMemory is licensed under the Apache 2.0 License.
