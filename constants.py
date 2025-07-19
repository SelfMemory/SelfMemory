"""
Constants for the MCP Memory Server.
Contains configuration values for embeddings, vector database, and application settings.
"""

class EmbeddingConstants:
    """Constants related to embedding generation."""
    EMBEDDING_MODEL = "mxbai-embed-large"

class VectorConstants:
    """Constants related to vector database operations."""
    VECTOR_DIMENSION = 1024  # Dimension of the embedding vectors
    VECTOR_TYPE = "float"  # Type of the vector, typically 'float' for embeddings
    VECTOR_NAME = "embedding"  # Name of the vector field in the database
    COLLECTION_NAME = "test_collection_mcps"  # Name of the collection in the database

class SearchConstants:
    """Constants related to memory search operations."""
    DEFAULT_SEARCH_LIMIT = 3  # Default number of memories to retrieve
    MAX_SEARCH_LIMIT = 10  # Maximum number of memories allowed in one search
    MIN_SEARCH_LIMIT = 1  # Minimum number of memories required

class DatabaseConstants:
    """Constants related to database configuration."""
    DEFAULT_QDRANT_URL = "http://localhost:6333"
    CONNECTION_TIMEOUT = 30  # seconds
    RETRY_ATTEMPTS = 3

class LoggingConstants:
    """Constants related to logging configuration."""
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DEFAULT_LOG_LEVEL = "INFO"
