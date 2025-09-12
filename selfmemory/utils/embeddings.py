"""
Embeddings utilities - now uses the new embeddings architecture.

This module provides backward compatibility for existing code while
using the new direct import embeddings architecture.
"""

import logging
import os

from selfmemory.configs import SelfMemoryConfig

logger = logging.getLogger(__name__)

# Global embedding provider instance
_embedding_provider = None


def _get_embedding_provider():
    """Get or create the global embedding provider using new architecture."""
    global _embedding_provider
    if _embedding_provider is None:
        config = SelfMemoryConfig()

        # Determine provider from config or environment
        provider = getattr(config.embedding, "provider", "ollama").lower()

        # Use direct imports based on provider
        if provider == "openai":
            from selfmemory.embeddings.configs import OpenAIEmbedderConfig
            from selfmemory.embeddings.openai import OpenAIEmbedding

            embedding_config = OpenAIEmbedderConfig(
                api_key=getattr(
                    config.embedding, "api_key", os.getenv("OPENAI_API_KEY")
                ),
                model=getattr(config.embedding, "model", "text-embedding-3-small"),
            )
            _embedding_provider = OpenAIEmbedding(embedding_config)

        elif provider == "azure_openai":
            from selfmemory.embeddings.azure_openai import AzureOpenAIEmbedding
            from selfmemory.embeddings.configs import AzureOpenAIEmbedderConfig

            embedding_config = AzureOpenAIEmbedderConfig(
                api_key=getattr(
                    config.embedding, "api_key", os.getenv("AZURE_OPENAI_API_KEY")
                ),
                azure_endpoint=getattr(
                    config.embedding,
                    "azure_endpoint",
                    os.getenv("AZURE_OPENAI_ENDPOINT"),
                ),
                model=getattr(config.embedding, "model", "text-embedding-3-small"),
                deployment_name=getattr(config.embedding, "deployment_name", None),
            )
            _embedding_provider = AzureOpenAIEmbedding(embedding_config)

        elif provider == "huggingface":
            from selfmemory.embeddings.configs import HuggingFaceEmbedderConfig
            from selfmemory.embeddings.huggingface import HuggingFaceEmbedding

            embedding_config = HuggingFaceEmbedderConfig(
                model=getattr(
                    config.embedding, "model", "sentence-transformers/all-MiniLM-L6-v2"
                ),
                api_key=getattr(
                    config.embedding, "api_key", os.getenv("HUGGINGFACE_API_KEY")
                ),
                use_local=getattr(config.embedding, "use_local", True),
            )
            _embedding_provider = HuggingFaceEmbedding(embedding_config)

        elif provider == "mock":
            from selfmemory.embeddings.configs import MockEmbedderConfig
            from selfmemory.embeddings.mock import MockEmbedding

            embedding_config = MockEmbedderConfig(
                embedding_dims=getattr(config.embedding, "embedding_dims", 768)
            )
            _embedding_provider = MockEmbedding(embedding_config)

        else:  # Default to ollama
            from selfmemory.embeddings.configs import OllamaEmbedderConfig
            from selfmemory.embeddings.ollama import OllamaEmbedding

            embedding_config = OllamaEmbedderConfig(
                model=getattr(config.embedding, "model", "nomic-embed-text"),
                ollama_base_url=getattr(
                    config.embedding, "ollama_base_url", "http://localhost:11434"
                ),
            )
            _embedding_provider = OllamaEmbedding(embedding_config)

    return _embedding_provider


def get_embeddings(text: str) -> list[float]:
    """
    Get embeddings vector for the given text using the configured provider.

    Args:
        text: The input text to get embeddings for

    Returns:
        List of float values representing the embedding vector

    Raises:
        ValueError: If text is empty
        Exception: If embedding generation fails
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    try:
        provider = _get_embedding_provider()
        return provider.embed(text.strip())
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {str(e)}")
        raise Exception(f"Embedding generation failed: {str(e)}") from e


def generate_embeddings(text: str) -> dict:
    """
    Generate embeddings for the given text using the configured provider.

    This function is kept for backward compatibility.

    Args:
        text: The input text to generate embeddings for

    Returns:
        Dictionary containing embeddings and metadata

    Raises:
        Exception: If embedding generation fails
    """
    try:
        logger.debug(f"Generating embeddings for text of length {len(text)}")
        embeddings = get_embeddings(text)
        return {"embeddings": [embeddings]}
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {str(e)}")
        raise Exception(f"Embedding generation failed: {str(e)}") from e


# Backwards compatibility functions
def get_embedding_client():
    """Get the embedding provider instance for backward compatibility."""
    return _get_embedding_provider()


if __name__ == "__main__":
    test_text = "Hello, this is a test."
    try:
        embedding_vector = get_embeddings(test_text)
        print(f"Generated embedding vector with {len(embedding_vector)} dimensions")
        print(f"First 5 values: {embedding_vector[:5]}")
    except Exception as e:
        print(f"Error: {e}")
