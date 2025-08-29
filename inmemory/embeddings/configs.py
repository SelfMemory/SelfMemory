from typing import Optional


class BaseEmbedderConfig:
    """
    Base configuration class for all embedding providers.
    
    This matches mem0's BaseEmbedderConfig pattern.
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        embedding_dims: Optional[int] = None,
        # Ollama specific
        ollama_base_url: Optional[str] = None,
        # Future providers can add their specific params here
        **kwargs
    ):
        self.model = model
        self.api_key = api_key
        self.embedding_dims = embedding_dims
        
        # Ollama specific
        self.ollama_base_url = ollama_base_url or "http://localhost:11434"
        
        # Store any additional kwargs for future extensibility
        for key, value in kwargs.items():
            setattr(self, key, value)


# Keep the dataclass version for backward compatibility if needed
from dataclasses import dataclass

@dataclass
class OllamaEmbedderConfig(BaseEmbedderConfig):
    """Configuration for Ollama embedding provider."""
    model: str = "nomic-embed-text"
    embedding_dims: Optional[int] = None
    ollama_base_url: str = "http://localhost:11434"
