"""
Embeddings module for various embedding providers.

Provides a factory pattern for creating embedding instances.
"""

from inmemory.config.config import InMemoryConfig
from inmemory.embeddings.base import EmbeddingBase


def get_embedding_provider(
    provider: str, config: InMemoryConfig | None = None
) -> EmbeddingBase:
    """
    Factory function to get embedding provider instance.

    Args:
        provider (str): The embedding provider name ('ollama', 'openai', etc.)
        config (Optional[InMemoryConfig]): Configuration for the provider

    Returns:
        EmbeddingBase: An instance of the specified embedding provider

    Raises:
        ValueError: If the provider is not supported
    """
    provider = provider.lower()

    if provider == "ollama":
        from inmemory.embeddings.ollama import OllamaEmbedding

        return OllamaEmbedding(config)
    if provider == "openai":
        from inmemory.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding(config)
    raise ValueError(f"Unsupported embedding provider: {provider}")


__all__ = [
    "EmbeddingBase",
    "get_embedding_provider",
]
