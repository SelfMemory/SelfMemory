"""
Factory pattern for creating provider instances using base.py abstractions.

This module provides clean factory classes that use only base.py interfaces,
making it easy to add new providers without changing the Memory class.

Based on mem0's factory pattern but simplified for Ollama + Qdrant only.
"""

import importlib
from typing import Any, Dict, Optional

from inmemory.embeddings.base import EmbeddingBase
from inmemory.vector_stores.base import VectorStoreBase


def load_class(class_path: str):
    """Dynamically load a class from a module path."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class EmbeddingFactory:
    """Factory for creating embedding provider instances."""
    
    # Provider mappings - only Ollama for now
    provider_to_class = {
        "ollama": "inmemory.embeddings.ollama.OllamaEmbedding",
    }
    
    @classmethod
    def create(cls, provider_name: str, config: Optional[Dict[str, Any]] = None) -> EmbeddingBase:
        """
        Create an embedding provider instance.
        
        Args:
            provider_name: Provider name (e.g., 'ollama')
            config: Configuration dictionary
            
        Returns:
            EmbeddingBase: Configured embedding provider instance
            
        Raises:
            ValueError: If provider is not supported
        """
        if provider_name not in cls.provider_to_class:
            raise ValueError(f"Unsupported embedding provider: {provider_name}")
            
        class_path = cls.provider_to_class[provider_name]
        embedding_class = load_class(class_path)
        
        # Follow mem0's approach: use BaseEmbedderConfig directly
        from inmemory.embeddings.configs import BaseEmbedderConfig
        
        config_dict = config or {}
            
        base_config = BaseEmbedderConfig(**config_dict)
        return embedding_class(base_config)
    
    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported embedding providers."""
        return list(cls.provider_to_class.keys())


class VectorStoreFactory:
    """Factory for creating vector store provider instances."""
    
    # Provider mappings - only Qdrant for now
    provider_to_class = {
        "qdrant": "inmemory.vector_stores.qdrant.Qdrant",
    }
    
    @classmethod
    def create(cls, provider_name: str, config: Dict[str, Any]) -> VectorStoreBase:
        """
        Create a vector store provider instance.
        
        Args:
            provider_name: Provider name (e.g., 'qdrant')
            config: Configuration dictionary
            
        Returns:
            VectorStoreBase: Configured vector store provider instance
            
        Raises:
            ValueError: If provider is not supported
        """
        if provider_name not in cls.provider_to_class:
            raise ValueError(f"Unsupported vector store provider: {provider_name}")
            
        class_path = cls.provider_to_class[provider_name]
        vector_store_class = load_class(class_path)
        
        # Follow mem0's approach: pass config directly
        if not isinstance(config, dict):
            config = config.model_dump()
            
        return vector_store_class(**config)
    
    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported vector store providers."""
        return list(cls.provider_to_class.keys())
