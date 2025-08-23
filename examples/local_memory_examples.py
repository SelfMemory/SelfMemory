"""
Comprehensive examples for fully local InMemory usage.

This demonstrates the simplified Memory API with different embedding and vector store configurations.
All examples run entirely locally without any external APIs (except for OpenAI embeddings).
"""

import os

from inmemory import Memory


def example_1_default_ollama_qdrant():
    """Example 1: Default setup with Ollama + Qdrant (requires local services)."""
    print("=== Example 1: Ollama + Qdrant (Default) ===")

    try:
        # Simple initialization with defaults
        memory = Memory(
            embedding={
                "provider": "ollama",
                "model": "nomic-embed-text",
                "url": "http://localhost:11434",
            },
            db={"provider": "qdrant", "url": "http://localhost:6333"},
        )

        # Add memories - Clean API, no user_id needed!
        result = memory.add(
            memory_content="I am shrijayan, a software engineer working on AI projects",
            tags="personal,introduction,work",
            people_mentioned="shrijayan",
            topic_category="introduction",
            metadata={"age": 30, "location": "USA"},
        )
        print(f"Added memory: {result}")

        # Add another memory
        result = memory.add(
            memory_content="Had lunch with Sarah at the Italian restaurant downtown",
            tags="food,social,restaurant",
            people_mentioned="Sarah",
            topic_category="social",
            metadata={"meal": "lunch", "cuisine": "Italian"},
        )
        print(f"Added memory: {result}")

        # Search memories with semantic understanding
        results = memory.search("what is my name?")
        print(f"Search results for 'what is my name?': {len(results['results'])} found")
        for result in results["results"]:
            print(f"  - {result.get('content', 'N/A')[:60]}...")

        # Search by tags
        tag_results = memory.search_by_tags("work", limit=5)
        print(f"Tag search results: {len(tag_results['results'])} found")

        # Get all memories
        all_memories = memory.get_all(limit=10)
        print(f"Total memories: {len(all_memories['results'])}")

        # Get stats
        stats = memory.get_stats()
        print(f"Memory stats: {stats}")

        print("✅ Ollama + Qdrant example completed!\n")

    except Exception as e:
        print(f"❌ Example failed: {e}")
        print("Requirements:")
        print("  - Ollama running on http://localhost:11434")
        print("  - Qdrant running on http://localhost:6333")
        print("  - Model 'nomic-embed-text' available in Ollama")
        print()


def example_2_openai_chroma():
    """Example 2: OpenAI embeddings + ChromaDB local storage."""
    print("=== Example 2: OpenAI + ChromaDB (Local Storage) ===")

    # Check if OpenAI API key is available
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY='your-openai-key'")
        print()
        return

    try:
        # OpenAI + ChromaDB configuration
        memory = Memory(
            embedding={
                "provider": "openai",
                "model": "text-embedding-3-small",
                "api_key": api_key,
            },
            db={
                "provider": "chroma",
                "path": "/tmp/chroma_openai",  # Local storage
            },
        )

        # Add memories
        result = memory.add(
            memory_content="Completed the quarterly AI project review with excellent feedback",
            tags="work,project,ai,review",
            people_mentioned="team,manager",
            topic_category="work",
            metadata={"quarter": "Q3", "rating": "excellent"},
        )
        print(f"Added memory: {result}")

        result = memory.add(
            memory_content="Learning about vector databases and embeddings for AI applications",
            tags="learning,ai,vectors,databases",
            topic_category="education",
            metadata={"subject": "vector databases", "status": "in-progress"},
        )
        print(f"Added memory: {result}")

        # Search with semantic understanding
        results = memory.search("AI projects and work")
        print(f"Search results: {len(results['results'])} found")
        for result in results["results"]:
            print(f"  - {result.get('content', 'N/A')[:60]}...")

        # Search by people
        people_results = memory.search_by_people("team", limit=5)
        print(f"People search results: {len(people_results['results'])} found")

        print("✅ OpenAI + ChromaDB example completed!\n")

    except Exception as e:
        print(f"❌ Example failed: {e}")
        print("Requirements:")
        print("  - Valid OPENAI_API_KEY environment variable")
        print("  - ChromaDB package installed (pip install chromadb)")
        print()


def example_3_embedded_qdrant():
    """Example 3: Ollama + Embedded Qdrant (no server needed)."""
    print("=== Example 3: Ollama + Embedded Qdrant ===")

    try:
        # Embedded Qdrant configuration (no server needed)
        memory = Memory(
            embedding={
                "provider": "ollama",
                "model": "nomic-embed-text",
                "url": "http://localhost:11434",
            },
            db={
                "provider": "qdrant",
                "path": "/tmp/qdrant_embedded",  # Local embedded storage
            },
        )

        # Add memories
        result = memory.add(
            memory_content="Experimenting with different vector database configurations",
            tags="databases,vectors,experiments",
            topic_category="technical",
            metadata={"database": "qdrant", "mode": "embedded"},
        )
        print(f"Added memory: {result}")

        # Search
        results = memory.search("vector database")
        print(f"Search results: {len(results['results'])} found")

        print("✅ Ollama + Embedded Qdrant example completed!\n")

    except Exception as e:
        print(f"❌ Example failed: {e}")
        print("Requirements:")
        print("  - Ollama running on http://localhost:11434")
        print("  - Model 'nomic-embed-text' available in Ollama")
        print()


def example_4_context_manager():
    """Example 4: Using Memory with context manager for proper cleanup."""
    print("=== Example 4: Context Manager Usage ===")

    try:
        # Use context manager for automatic cleanup
        with Memory(
            embedding={"provider": "ollama", "model": "nomic-embed-text"},
            db={"provider": "chroma", "path": "/tmp/chroma_context"},
        ) as memory:
            # Add memory
            result = memory.add(
                memory_content="Using context managers for proper resource management",
                tags="programming,best-practices,python",
                topic_category="technical",
            )
            print(f"Added memory: {result}")

            # Search
            results = memory.search("context manager")
            print(f"Search results: {len(results['results'])} found")

            # Resources automatically cleaned up when exiting context

        print("✅ Context manager example completed!\n")

    except Exception as e:
        print(f"❌ Example failed: {e}")
        print()


def example_5_health_check():
    """Example 5: Health check and configuration inspection."""
    print("=== Example 5: Health Check & Configuration ===")

    try:
        memory = Memory(
            embedding={"provider": "ollama", "model": "nomic-embed-text"},
            db={"provider": "chroma", "path": "/tmp/chroma_health"},
        )

        # Health check
        health = memory.health_check()
        print(f"Health status: {health}")

        # Get statistics
        stats = memory.get_stats()
        print(f"Statistics: {stats}")

        # Show configuration
        print(f"Memory configuration: {memory}")

        print("✅ Health check example completed!\n")

    except Exception as e:
        print(f"❌ Example failed: {e}")
        print()


def show_installation_instructions():
    """Show installation instructions for different setups."""
    print("=== Installation Instructions ===")

    print("1. Base Installation (Full Featured):")
    print("   pip install inmemory")
    print("   Includes: Vector databases + Server + Embeddings")
    print()

    print("2. Enterprise Add-on:")
    print("   pip install inmemory[enterprise]")
    print("   Adds: MongoDB + OAuth + Multi-user + MCP")
    print()

    print("3. Local Service Requirements:")
    print("   For Ollama:")
    print("   - Install Ollama: https://ollama.ai")
    print("   - Run: ollama serve")
    print("   - Pull model: ollama pull nomic-embed-text")
    print()

    print("   For Qdrant:")
    print("   - Docker: docker run -p 6333:6333 qdrant/qdrant")
    print("   - Or use embedded mode (no server needed)")
    print()

    print("   For OpenAI:")
    print("   - Set: export OPENAI_API_KEY='your-api-key'")
    print()

    print("   For ChromaDB:")
    print("   - Automatic local storage (no server needed)")
    print()


def compare_with_managed():
    """Compare local vs managed service usage."""
    print("=== Local vs Managed Comparison ===")

    print("Local Memory (this file):")
    print("```python")
    print("from inmemory import Memory")
    print("")
    print("memory = Memory(")
    print("    embedding={'provider': 'ollama', 'model': 'nomic-embed-text'},")
    print("    db={'provider': 'qdrant', 'url': 'http://localhost:6333'}")
    print(")")
    print("result = memory.add('I am shrijayan', tags='personal')")
    print("results = memory.search('what is my name?')")
    print("```")
    print()

    print("Managed Service:")
    print("```python")
    print("from inmemory import Inmemory")
    print("")
    print("inmemory = Inmemory(api_key='im_62a0b611121d8e4881af922057ed4063')")
    print("result = inmemory.add('I am shrijayan', tags='personal')")
    print("results = inmemory.search('what is my name?')")
    print("```")
    print()

    print("Key Differences:")
    print("- Local: Full control, runs on your infrastructure")
    print("- Managed: No setup needed, just API key")
    print("- Both: Identical clean API (no user_id needed!)")
    print()


if __name__ == "__main__":
    """Run all examples."""
    print("🚀 InMemory Local Examples")
    print("=" * 50)

    # Show installation instructions first
    show_installation_instructions()

    # Run examples
    example_1_default_ollama_qdrant()
    example_2_openai_chroma()
    example_3_embedded_qdrant()
    example_4_context_manager()
    example_5_health_check()

    # Show comparison
    compare_with_managed()

    print("🎉 All examples completed!")
    print()
    print("Next steps:")
    print("1. Choose your preferred embedding provider (Ollama/OpenAI)")
    print("2. Choose your preferred vector database (Qdrant/ChromaDB)")
    print("3. Start building with the clean Memory API!")
