"""
Qdrant database client configuration and initialization.
Handles the connection to the Qdrant vector database.
"""

import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, CollectionStatus
from qdrant_client.http.exceptions import UnexpectedResponse

from constants import DatabaseConstants, VectorConstants

logger = logging.getLogger(__name__)


def create_qdrant_client() -> QdrantClient:
    """
    Create and return a configured Qdrant client.

    Returns:
        QdrantClient: Configured Qdrant client instance

    Raises:
        Exception: If connection to Qdrant fails
    """
    try:
        client = QdrantClient(
            url=DatabaseConstants.DEFAULT_QDRANT_URL,
            timeout=DatabaseConstants.CONNECTION_TIMEOUT,
        )
        logger.info(f"Connected to Qdrant at {DatabaseConstants.DEFAULT_QDRANT_URL}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {str(e)}")
        raise Exception(f"Database connection failed: {str(e)}")


def ensure_collection_exists(client: QdrantClient, collection_name: str) -> bool:
    """
    Ensure that the specified collection exists, create it if it doesn't.

    Args:
        client: Qdrant client instance
        collection_name: Name of the collection to check/create

    Returns:
        bool: True if collection exists or was created successfully

    Raises:
        Exception: If collection creation fails
    """
    try:
        # Check if collection exists
        collections = client.get_collections().collections
        existing_collection = next(
            (col for col in collections if col.name == collection_name), None
        )

        if existing_collection:
            logger.info(f"Collection '{collection_name}' already exists")
            return True

        # Create collection if it doesn't exist
        logger.info(f"Creating collection '{collection_name}'")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=VectorConstants.VECTOR_DIMENSION, distance=Distance.COSINE
            ),
        )
        logger.info(f"Successfully created collection '{collection_name}'")
        return True

    except Exception as e:
        logger.error(f"Failed to ensure collection exists: {str(e)}")
        raise Exception(f"Collection management failed: {str(e)}")


def get_qdrant_client() -> QdrantClient:
    """
    Get a Qdrant client instance. Creates new client each time for thread safety.
    
    Returns:
        QdrantClient: Qdrant client instance
    """
    return create_qdrant_client()


def ensure_user_collection_exists(user_id: str) -> str:
    """
    Ensure that the user-specific collection exists, create it if it doesn't.
    
    Args:
        user_id: User identifier to create collection for
        
    Returns:
        str: Name of the user's collection
        
    Raises:
        Exception: If collection creation fails
    """
    from user_management import user_manager
    
    # Validate user and get collection name
    if not user_manager.is_valid_user(user_id):
        raise ValueError(f"Invalid or unauthorized user_id: {user_id}")
    
    collection_name = user_manager.get_collection_name(user_id)
    
    # Create client and ensure collection exists
    client = get_qdrant_client()
    ensure_collection_exists(client, collection_name)
    
    return collection_name


# Initialize the global client for basic operations
try:
    client = create_qdrant_client()
    logger.info("Qdrant client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Qdrant database: {str(e)}")
    raise
