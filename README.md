# SelfMemory

**Long-term memory for AI Agents with zero-setup simplicity**

It is a open-source universal memory engine where users can store and retrieve their AI conversations and context across different models. Users can add memories through MCP, SDK, or a website selfmemory.com Over time, this will evolve into a one-stop memory hub with note-taking and chatbot features. For B2B, it becomes a knowledge backbone, storing project context, organizational knowledge, documents, and data sources to power company-wide AI systems.

## 🚀 Quick Start

```bash
pip install selfmemory
```

```python
from selfmemory import SelfMemory

memory = SelfMemory()

# Add memories
memory.add("I have a BMW bike.", user_id="demo")

# Search memories
results = memory.search("bike", user_id="demo")
print(results)
```

## 📚 Full Documentation

**Visit [docs.selfmemory.com](https://docs.selfmemory.com) for complete documentation, guides, and examples.**
**Changelog**: See [CHANGELOG.md](CHANGELOG.md) for a detailed list of changes and updates.

## 🔗 Links

- **Documentation**: [docs.selfmemory.com](https://docs.selfmemory.com)
- **GitHub**: [github.com/selfmemory/selfmemory](https://github.com/selfmemory/selfmemory)
- **Discord**: [discord.com/invite/YypBvdUpcc](https://discord.com/invite/YypBvdUpcc)
- **Brand Assets** (Logos, Slides, etc.): [Google Drive](https://drive.google.com/drive/folders/1paB9DkpPGv58_MC3P5C1el_Bw7lzYh-3?usp=sharing)

## 📄 License

Apache 2.0 License - see [LICENSE](LICENSE.txt)
