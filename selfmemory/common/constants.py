"""
Essential constants for basic selfmemory operations.
Simplified version focusing on core memory functionality.
"""


class VectorConstants:
    """Constants for vector operations."""

    VECTOR_DIMENSION = 768  # Dimension of the embedding vectors
    VECTOR_NAME = "embedding"  # Name of the vector field in the database


class SearchConstants:
    """Constants for search operations."""

    DEFAULT_SEARCH_LIMIT = 5  # Default number of memories to retrieve
    MAX_SEARCH_LIMIT = 20  # Maximum number of memories allowed in one search
    MIN_SEARCH_LIMIT = 1  # Minimum number of memories required
    DEFAULT_SCORE_THRESHOLD = 0.5  # Minimum similarity score for relevant results


class MetadataConstants:
    """Constants for memory metadata fields."""

    # Core metadata fields
    MEMORY_FIELD = "memory"  # Field name for storing memory content
    TIMESTAMP_FIELD = "timestamp"  # Field name for storing creation time


class APIConstants:
    """Constants for API client configuration."""

    DEFAULT_TIMEOUT = 300
    DEFAULT_API_HOST = "http://localhost:8081"
