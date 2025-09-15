# Example usage of OllamaEmbedding and its functions
from selfmemory.embeddings.configs import OllamaEmbedderConfig
from selfmemory.embeddings.ollama import OllamaEmbedding


def main():
    # Initialize config (customize if needed)
    config = OllamaEmbedderConfig(
        model="nomic-embed-text",  # or another supported model
        embedding_dims=768,
        ollama_base_url="http://localhost:11434",
    )

    # Initialize OllamaEmbedding
    embedder = OllamaEmbedding(config)

    # Ensure model exists (calls _ensure_model_exists)
    embedder._ensure_model_exists()

    # Test embedding for different memory actions
    text = "Hello, this is a test sentence for embedding."
    for action in [None, "add", "search", "update"]:
        embedding = embedder.embed(text, memory_action=action)
        print(f"Embedding for action '{action}':\n", embedding)


if __name__ == "__main__":
    main()
