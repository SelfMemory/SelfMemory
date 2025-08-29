"""
Ollama embedding configuration.

This module provides Ollama-specific configuration classes,
following mem0's configuration pattern.
"""

from typing import Optional

from pydantic import BaseModel, Field


class OllamaConfig(BaseModel):
    """
    Configuration for Ollama embedding provider.
    
    This matches the structure expected by our OllamaEmbedding class.
    """

    model: str = Field("nomic-embed-text", description="Ollama model name")
    embedding_dims: Optional[int] = Field(768, description="Dimensions of the embedding model")
    ollama_base_url: str = Field(
        "http://localhost:11434", 
        description="Base URL for Ollama server"
    )
    
    # Additional Ollama-specific options
    temperature: Optional[float] = Field(None, description="Temperature for model inference")
    top_p: Optional[float] = Field(None, description="Top-p sampling parameter")
    top_k: Optional[int] = Field(None, description="Top-k sampling parameter")
    
    model_config = {
        "extra": "forbid",  # Don't allow extra fields
    }
