"""
Vector stores module for Qdrant vector database provider.

Provides a factory pattern for creating Qdrant vector store instances.
"""

from selfmemory.configs import SelfMemoryConfig
from selfmemory.vector_stores.base import VectorStoreBase


def get_vector_store_provider(
    provider: str,
    collection_name: str,
    embedding_model_dims: int,
    config: SelfMemoryConfig | None = None,
    **kwargs,
) -> VectorStoreBase:
    """
    Factory function to get Qdrant vector store provider instance.

    Args:
        provider (str): The vector store provider name (only 'qdrant' supported)
        collection_name (str): Name of the collection
        embedding_model_dims (int): Dimensions of the embedding model
        config (Optional[SelfMemoryConfig]): Configuration for the provider
        **kwargs: Additional provider-specific parameters

    Returns:
        VectorStoreBase: An instance of the Qdrant vector store provider

    Raises:
        ValueError: If the provider is not 'qdrant'
    """
    provider = provider.lower()

    if provider == "qdrant":
        from selfmemory.vector_stores.qdrant import Qdrant

        # Extract connection parameters from config if provided
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
            if "path" in vs_config:
                qdrant_params["path"] = vs_config["path"]
            if "on_disk" in vs_config:
                qdrant_params["on_disk"] = vs_config["on_disk"]

        return Qdrant(
            collection_name=collection_name,
            embedding_model_dims=embedding_model_dims,
            **qdrant_params,
        )

    raise ValueError(
        f"Unsupported vector store provider: {provider}. Only 'qdrant' is supported."
    )


__all__ = [
    "VectorStoreBase",
    "get_vector_store_provider",
]
