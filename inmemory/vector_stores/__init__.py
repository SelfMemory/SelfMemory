"""
Vector stores module for various vector database providers.

Provides a factory pattern for creating vector store instances.
"""

from inmemory.config.config import InMemoryConfig
from inmemory.vector_stores.base import VectorStoreBase


def get_vector_store_provider(
    provider: str,
    collection_name: str,
    embedding_model_dims: int,
    config: InMemoryConfig | None = None,
    **kwargs,
) -> VectorStoreBase:
    """
    Factory function to get vector store provider instance.

    Args:
        provider (str): The vector store provider name ('qdrant', 'chroma', etc.)
        collection_name (str): Name of the collection
        embedding_model_dims (int): Dimensions of the embedding model
        config (Optional[InMemoryConfig]): Configuration for the provider
        **kwargs: Additional provider-specific parameters

    Returns:
        VectorStoreBase: An instance of the specified vector store provider

    Raises:
        ValueError: If the provider is not supported
    """
    provider = provider.lower()

    if provider == "qdrant":
        from inmemory.vector_stores.qdrant import Qdrant

        # Extract connection parameters from config if it's from Memory class dict config
        qdrant_params = kwargs.copy()

        if config and hasattr(config, "vector_store"):
            # Extract from config object
            if isinstance(config.vector_store, dict):
                vs_config = config.vector_store
            else:
                vs_config = (
                    config.vector_store.model_dump()
                    if hasattr(config.vector_store, "model_dump")
                    else config.vector_store.__dict__
                )

            # Pass connection parameters directly
            if "host" in vs_config:
                qdrant_params["host"] = vs_config["host"]
            if "port" in vs_config:
                qdrant_params["port"] = vs_config["port"]
            if "url" in vs_config:
                qdrant_params["url"] = vs_config["url"]
            if "api_key" in vs_config:
                qdrant_params["api_key"] = vs_config["api_key"]

        return Qdrant(
            collection_name=collection_name,
            embedding_model_dims=embedding_model_dims,
            config=config,
            **qdrant_params,
        )
    if provider == "chroma" or provider == "chromadb":
        from inmemory.vector_stores.chroma import ChromaDB

        return ChromaDB(
            collection_name=collection_name,
            embedding_model_dims=embedding_model_dims,
            config=config,
            **kwargs,
        )
    raise ValueError(f"Unsupported vector store provider: {provider}")


__all__ = [
    "VectorStoreBase",
    "get_vector_store_provider",
]
