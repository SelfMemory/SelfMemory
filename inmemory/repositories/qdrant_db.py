"""
Qdrant database client configuration and initialization.
Handles the connection to the Qdrant vector database.
"""

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from inmemory.common.constants import DatabaseConstants, VectorConstants

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
        raise Exception(f"Database connection failed: {str(e)}") from e


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
        raise Exception(f"Collection management failed: {str(e)}") from e


def get_qdrant_client() -> QdrantClient:
    """
    Get a Qdrant client instance. Creates new client each time for thread safety.

    Returns:
        QdrantClient: Qdrant client instance
    """
    return create_qdrant_client()


def delete_memory_point(
    client: QdrantClient, collection_name: str, point_id: str
) -> bool:
    """
    Delete a specific memory point from Qdrant collection.

    Args:
        client: Qdrant client instance
        collection_name: Name of the collection
        point_id: ID of the point to delete

    Returns:
        bool: True if deletion was successful

    Raises:
        Exception: If deletion fails
    """
    try:
        logger.info(
            f"🗑️ Attempting to delete memory point {point_id} from collection {collection_name}"
        )

        # First, check if the point exists
        try:
            existing_points = client.retrieve(
                collection_name=collection_name, ids=[point_id], with_payload=False
            )
            logger.info(f"🔍 Found {len(existing_points)} points with ID {point_id}")

            if not existing_points:
                logger.warning(
                    f"❌ Memory point {point_id} not found in collection {collection_name}"
                )
                raise Exception("Memory not found")

        except Exception as retrieve_error:
            logger.error(f"❌ Failed to check if memory exists: {str(retrieve_error)}")
            raise Exception("Memory not found") from retrieve_error

        # Delete the specific point using Qdrant's delete API
        result = client.delete(
            collection_name=collection_name,
            points_selector=[point_id],  # Delete by point ID
        )

        logger.info(f"✅ Delete result: {result}")
        logger.info(
            f"Successfully deleted memory point {point_id} from collection {collection_name}"
        )
        return True

    except Exception as e:
        logger.error(f"❌ Failed to delete memory point {point_id}: {str(e)}")
        raise Exception(f"Memory deletion failed: {str(e)}") from e


def delete_user_memory(user_id: str, memory_id: str) -> bool:
    """
    Delete a memory for a specific user.

    Args:
        user_id: User identifier
        memory_id: Memory ID to delete

    Returns:
        bool: True if deletion was successful

    Raises:
        Exception: If deletion fails or user is invalid
    """
    # Clean user_id for collection name (alphanumeric and underscore only)
    clean_user_id = "".join(c for c in user_id if c.isalnum() or c == "_").lower()
    collection_name = f"memories_{clean_user_id}"

    # Create client and delete the memory point
    client = get_qdrant_client()
    result = delete_memory_point(client, collection_name, memory_id)

    logger.info(f"Successfully deleted memory {memory_id} for user {user_id}")
    return result


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
    # Generate collection name directly (same logic as stores)
    clean_user_id = "".join(c for c in user_id if c.isalnum() or c == "_").lower()
    collection_name = f"memories_{clean_user_id}"

    # Create client and ensure collection exists
    client = get_qdrant_client()
    ensure_collection_exists(client, collection_name)

    logger.info(f"Ensured Qdrant collection exists: {collection_name}")
    return collection_name


# Initialize the global client for basic operations
try:
    client = create_qdrant_client()
    logger.info("Qdrant client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Qdrant database: {str(e)}")
    raise
