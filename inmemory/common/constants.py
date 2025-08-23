"""
Enhanced Constants for the MCP Memory Server.
Contains configuration values for embeddings, vector database, search capabilities, and temporal metadata.
"""


class EmbeddingConstants:
    """Constants related to embedding generation."""

    EMBEDDING_MODEL = "mxbai-embed-large"


class VectorConstants:
    """Constants related to vector database operations."""

    VECTOR_DIMENSION = 768  # Dimension of the embedding vectors
    VECTOR_TYPE = "float"  # Type of the vector, typically 'float' for embeddings
    VECTOR_NAME = "embedding"  # Name of the vector field in the database
    # Collection names are now per-user via mongodb_user_manager.get_collection_name(user_id)
    # Format: "memories_{user_id}"


class SearchConstants:
    """Constants related to memory search operations."""

    DEFAULT_SEARCH_LIMIT = 5  # Default number of memories to retrieve
    MAX_SEARCH_LIMIT = 20  # Maximum number of memories allowed in one search
    MIN_SEARCH_LIMIT = 1  # Minimum number of memories required
    DEFAULT_SCORE_THRESHOLD = 0.5  # Minimum similarity score for relevant results


class DuplicateConstants:
    """Constants related to duplicate detection and prevention."""

    SIMILARITY_THRESHOLD = 0.90  # Threshold for considering memories as duplicates
    MAX_DUPLICATE_CHECK_LIMIT = 100  # Maximum memories to check for duplicates
    DUPLICATE_ACTION_SKIP = "skip"  # Skip adding duplicate memory
    DUPLICATE_ACTION_MERGE = "merge"  # Merge with existing memory
    DUPLICATE_ACTION_ADD = "add"  # Add anyway despite similarity


class TemporalConstants:
    """Constants related to temporal metadata and time-based queries."""

    # Time periods for natural language queries
    TEMPORAL_PERIODS = {
        "today": 0,
        "yesterday": 1,
        "this_week": 7,
        "last_week": 14,
        "this_month": 30,
        "last_month": 60,
        "this_quarter": 90,
        "last_quarter": 180,
    }

    # Day names for filtering
    WEEKDAYS = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    # Quarter definitions
    QUARTERS = {
        1: [1, 2, 3],  # Q1: Jan-Mar
        2: [4, 5, 6],  # Q2: Apr-Jun
        3: [7, 8, 9],  # Q3: Jul-Sep
        4: [10, 11, 12],  # Q4: Oct-Dec
    }


class MetadataConstants:
    """Constants related to memory metadata fields."""

    # Core metadata fields
    MEMORY_FIELD = "memory"
    TIMESTAMP_FIELD = "timestamp"
    TEMPORAL_FIELD = "temporal"
    TAGS_FIELD = "tags"
    PEOPLE_FIELD = "people_mentioned"
    TOPIC_FIELD = "topic_category"

    # Temporal sub-fields
    TEMPORAL_FIELDS = [
        "day",
        "hour",
        "year",
        "month",
        "minute",
        "quarter",
        "is_weekend",
        "day_of_week",
        "day_of_year",
        "week_of_year",
    ]

    # Default topic categories
    DEFAULT_TOPICS = [
        "work",
        "personal",
        "learning",
        "health",
        "finance",
        "technology",
        "family",
        "friends",
        "projects",
        "ideas",
    ]


class SearchFilters:
    """Constants for different types of search filters."""

    # Filter types
    SEMANTIC_FILTER = "semantic"
    TEMPORAL_FILTER = "temporal"
    TAG_FILTER = "tags"
    PEOPLE_FILTER = "people"
    TOPIC_FILTER = "topic"
    SCORE_FILTER = "score"

    # Temporal filter operators
    TEMPORAL_OPERATORS = {
        "equals": "=",
        "greater_than": ">",
        "less_than": "<",
        "in_range": "between",
        "in_list": "in",
    }


class DatabaseConstants:
    """Constants related to database configuration."""

    DEFAULT_QDRANT_URL = "http://localhost:6333"
    CONNECTION_TIMEOUT = 30  # seconds
    RETRY_ATTEMPTS = 3


class EncryptionConstants:
    """Constants related to memory encryption."""

    ENCRYPTION_SALT = "mem_mcp_salt_2024"
    ENCRYPTED_FIELDS = ["memory", "tags", "people_mentioned", "topic_category"]


class APIConstants:
    """Constants related to API client configuration."""

    DEFAULT_API_HOST = "https://inmemory.tailb75d54.ts.net"
    DEFAULT_TIMEOUT = 300
    CONNECTION_TIMEOUT = 30
    RETRY_ATTEMPTS = 3
    API_KEY_PREFIX = "im_"


class LoggingConstants:
    """Constants related to logging configuration."""

    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DEFAULT_LOG_LEVEL = "INFO"
