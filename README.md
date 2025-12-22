# SelfMemory

**Store AI memories for you and your agents**

It is a open-source universal memory engine where users can store and retrieve their AI conversations and context across different models. Users can add memories through MCP, SDK, or a website selfmemory.com Over time, this will evolve into a one-stop memory hub with note-taking and chatbot features. For B2B, it becomes a knowledge backbone, storing project context, organizational knowledge, documents, and data sources to power company-wide AI systems.

## 🚀 Quick Start

```bash
pip install selfmemory
```

```python
from selfmemory import SelfMemory

memory = SelfMemory()

# Add memories
memory.add("Can you find the nearest BMW car showroom for me.", user_id="user")

# Search memories
results = memory.search("Can you find a car washing service near me?", user_id="user")
print(results)
```

## 📚 Full Documentation

**Visit [docs.selfmemory.com](https://docs.selfmemory.com) for complete documentation, guides, and examples.**
**Changelog**: See [CHANGELOG.md](CHANGELOG.md) for a detailed list of changes and updates.

## 🤝 Contributing

We welcome contributions! [CONTRIBUTING.md](CONTRIBUTING.md).

## 🔗 Links

- **Discord**: [discord.com/invite/selfmemory](https://discord.com/invite/YypBvdUpcc)
- **Brand Assets** (Logos, Slides, etc.): [Storage Link](https://drive.google.com/drive/folders/1paB9DkpPGv58_MC3P5C1el_Bw7lzYh-3?usp=sharing)
