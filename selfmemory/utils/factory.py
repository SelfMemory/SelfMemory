"""
Factory pattern for creating provider instances using base.py abstractions.

This module provides clean factory classes that use only base.py interfaces,
making it easy to add new providers without changing the Memory class.

Based on selfmemory hybrid factory pattern - static core providers + dynamic plugins.
"""

import importlib
from typing import Any

from selfmemory.embeddings.base import EmbeddingBase
from selfmemory.vector_stores.base import VectorStoreBase


def load_class(class_path: str):
    """Dynamically load a class from a module path."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class EmbeddingFactory:
    """Factory for creating embedding provider instances with hybrid loading."""

    # Static provider mappings (always loaded for performance)
    _static_providers = {
        "ollama": "selfmemory.embeddings.ollama.OllamaEmbedding",
    }

    # Dynamic provider mappings (loaded on demand)
    _dynamic_providers = {
        "openai": "selfmemory.embeddings.openai.OpenAIEmbedding",
        "huggingface": "selfmemory.embeddings.huggingface.HuggingFaceEmbedding",
        "cohere": "selfmemory.embeddings.cohere.CohereEmbedding",
        "azure": "selfmemory.embeddings.azure.AzureEmbedding",
    }

    # Cache for loaded dynamic providers
    _loaded_providers: dict[str, str] = {}

    @classmethod
    def create(cls, provider_name: str, config=None) -> EmbeddingBase:
        """
        Create an embedding provider instance using hybrid loading.

        Args:
            provider_name: Provider name (e.g., 'ollama')
            config: Pydantic config object or dict with provider-specific configuration

        Returns:
            EmbeddingBase: Configured embedding provider instance

        Raises:
            ValueError: If provider is not supported
        """
        # Try static providers first (fast path)
        if provider_name in cls._static_providers:
            class_path = cls._static_providers[provider_name]

        # Try cached dynamic providers
        elif provider_name in cls._loaded_providers:
            class_path = cls._loaded_providers[provider_name]

        # Try dynamic providers (load on demand)
        elif provider_name in cls._dynamic_providers:
            class_path = cls._dynamic_providers[provider_name]
            # Cache for future use
            cls._loaded_providers[provider_name] = class_path

        else:
            raise ValueError(f"Unsupported embedding provider: {provider_name}")

        try:
            embedding_class = load_class(class_path)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Failed to load provider '{provider_name}': {e}")

        # Handle both Pydantic config objects and raw dicts
        if hasattr(config, "model_dump"):
            # Pydantic config object - convert to dict
            config_dict = config.model_dump()
        elif isinstance(config, dict):
            # Raw dict config
            config_dict = config
        elif config is None:
            # No config provided - use empty dict
            config_dict = {}
        else:
            raise ValueError(f"Invalid config type: {type(config)}")

        # Use BaseEmbedderConfig for compatibility
        from selfmemory.embeddings.configs import BaseEmbedderConfig

        base_config = BaseEmbedderConfig(**config_dict)
        return embedding_class(base_config)

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported embedding providers."""
        return list(cls._static_providers.keys()) + list(cls._dynamic_providers.keys())

    @classmethod
    def register_provider(cls, name: str, class_path: str, static: bool = False):
        """
        Register a new provider dynamically.

        Args:
            name: Provider name
            class_path: Full path to provider class
            static: Whether to load immediately (static) or on demand (dynamic)
        """
        if static:
            cls._static_providers[name] = class_path
        else:
            cls._dynamic_providers[name] = class_path

    @classmethod
    def validate_config(cls, provider_name: str, config) -> dict[str, Any]:
        """
        Validate configuration for a provider without creating instance.

        Args:
            provider_name: Provider name
            config: Configuration to validate

        Returns:
            Dict with validation results
        """
        try:
            # Create instance to trigger validation
            instance = cls.create(provider_name, config)

            # Test connection if config supports it
            if hasattr(instance.config, "test_connection"):
                connection_test = instance.config.test_connection()
                return {
                    "status": "valid",
                    "provider": provider_name,
                    "connection_test": connection_test,
                }
            return {
                "status": "valid",
                "provider": provider_name,
                "connection_test": {"status": "not_supported"},
            }

        except Exception as e:
            return {"status": "invalid", "provider": provider_name, "error": str(e)}

    @classmethod
    def get_provider_info(cls, provider_name: str) -> dict[str, Any]:
        """Get information about a provider."""
        if provider_name in cls._static_providers:
            return {
                "provider": provider_name,
                "type": "static",
                "class_path": cls._static_providers[provider_name],
                "loaded": True,
            }
        if provider_name in cls._dynamic_providers:
            return {
                "provider": provider_name,
                "type": "dynamic",
                "class_path": cls._dynamic_providers[provider_name],
                "loaded": provider_name in cls._loaded_providers,
            }
        return {"provider": provider_name, "type": "unknown", "supported": False}


class VectorStoreFactory:
    """Factory for creating vector store provider instances with hybrid loading."""

    # Static provider mappings (always loaded for performance)
    _static_providers = {
        "qdrant": "selfmemory.vector_stores.qdrant.Qdrant",
    }

    # Dynamic provider mappings (loaded on demand)
    _dynamic_providers = {
        "chroma": "selfmemory.vector_stores.chroma.ChromaDB",
        "chromadb": "selfmemory.vector_stores.chroma.ChromaDB",
        "pinecone": "selfmemory.vector_stores.pinecone.PineconeDB",
        "weaviate": "selfmemory.vector_stores.weaviate.WeaviateDB",
    }

    # Cache for loaded dynamic providers
    _loaded_providers: dict[str, str] = {}

    @classmethod
    def create(cls, provider_name: str, config) -> VectorStoreBase:
        """
        Create a vector store provider instance using hybrid loading.

        Args:
            provider_name: Provider name (e.g., 'qdrant')
            config: Pydantic config object or dict with provider-specific configuration

        Returns:
            VectorStoreBase: Configured vector store provider instance

        Raises:
            ValueError: If provider is not supported
        """
        # Try static providers first (fast path)
        if provider_name in cls._static_providers:
            class_path = cls._static_providers[provider_name]

        # Try cached dynamic providers
        elif provider_name in cls._loaded_providers:
            class_path = cls._loaded_providers[provider_name]

        # Try dynamic providers (load on demand)
        elif provider_name in cls._dynamic_providers:
            class_path = cls._dynamic_providers[provider_name]
            # Cache for future use
            cls._loaded_providers[provider_name] = class_path

        else:
            raise ValueError(f"Unsupported vector store provider: {provider_name}")

        try:
            vector_store_class = load_class(class_path)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Failed to load provider '{provider_name}': {e}")

        # Handle both Pydantic config objects and raw dicts
        if hasattr(config, "model_dump"):
            # Pydantic config object - convert to dict
            config_dict = config.model_dump()
        elif isinstance(config, dict):
            # Raw dict config
            config_dict = config
        else:
            raise ValueError(f"Invalid config type: {type(config)}")

        # Pass config directly to vector store constructor
        return vector_store_class(**config_dict)

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported vector store providers."""
        return list(cls._static_providers.keys()) + list(cls._dynamic_providers.keys())

    @classmethod
    def register_provider(cls, name: str, class_path: str, static: bool = False):
        """
        Register a new provider dynamically.

        Args:
            name: Provider name
            class_path: Full path to provider class
            static: Whether to load immediately (static) or on demand (dynamic)
        """
        if static:
            cls._static_providers[name] = class_path
        else:
            cls._dynamic_providers[name] = class_path

    @classmethod
    def validate_config(cls, provider_name: str, config) -> dict[str, Any]:
        """
        Validate configuration for a provider without creating instance.

        Args:
            provider_name: Provider name
            config: Configuration to validate

        Returns:
            Dict with validation results
        """
        try:
            # Create instance to trigger validation
            instance = cls.create(provider_name, config)

            # Test connection if config supports it
            if hasattr(instance, "test_connection"):
                connection_test = instance.test_connection()
                return {
                    "status": "valid",
                    "provider": provider_name,
                    "connection_test": connection_test,
                }
            return {
                "status": "valid",
                "provider": provider_name,
                "connection_test": {"status": "not_supported"},
            }

        except Exception as e:
            return {"status": "invalid", "provider": provider_name, "error": str(e)}

    @classmethod
    def get_provider_info(cls, provider_name: str) -> dict[str, Any]:
        """Get information about a provider."""
        if provider_name in cls._static_providers:
            return {
                "provider": provider_name,
                "type": "static",
                "class_path": cls._static_providers[provider_name],
                "loaded": True,
            }
        if provider_name in cls._dynamic_providers:
            return {
                "provider": provider_name,
                "type": "dynamic",
                "class_path": cls._dynamic_providers[provider_name],
                "loaded": provider_name in cls._loaded_providers,
            }
        return {"provider": provider_name, "type": "unknown", "supported": False}
