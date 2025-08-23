"""
Embeddings utilities - now uses the pluggable embeddings system.

This module provides backward compatibility for existing code while
using the new pluggable embeddings architecture.
"""

import logging

from inmemory.config.config import load_config
from inmemory.embeddings import get_embedding_provider

logger = logging.getLogger(__name__)

# Global embedding provider instance
_embedding_provider = None


def _get_embedding_provider():
    """Get or create the global embedding provider."""
    global _embedding_provider
    if _embedding_provider is None:
        config = load_config()
        _embedding_provider = get_embedding_provider(
            provider=config.embedding.provider, config=config
        )
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
