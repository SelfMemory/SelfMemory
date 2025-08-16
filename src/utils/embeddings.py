import logging

import ollama

from src.common.constants import EmbeddingConstants

logger = logging.getLogger(__name__)
embedding_client = ollama.Client()


def generate_embeddings(text: str) -> dict:
    """
    Generate embeddings for the given text using Ollama.

    Args:
        text: The input text to generate embeddings for

    Returns:
        Dictionary containing embeddings and metadata

    Raises:
        Exception: If embedding generation fails
    """
    try:
        logger.debug(f"Generating embeddings for text of length {len(text)}")
        return ollama.embed(
            model=EmbeddingConstants.EMBEDDING_MODEL,
            input=text,
        )
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {str(e)}")
        raise Exception(f"Embedding generation failed: {str(e)}")


def get_embeddings(text: str) -> list[float]:
    """
    Get embeddings vector for the given text.

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
        embeddings_response = generate_embeddings(text.strip())
        return embeddings_response["embeddings"][0]
    except Exception as e:
        logger.error(f"Failed to extract embeddings: {str(e)}")
        raise


if __name__ == "__main__":
    test_text = "Hello, this is a test."
    try:
        embedding_vector = get_embeddings(test_text)
        print(f"Generated embedding vector with {len(embedding_vector)} dimensions")
        print(f"First 5 values: {embedding_vector[:5]}")
    except Exception as e:
        print(f"Error: {e}")
