import logging
import uuid
from typing import Optional

from qdrant_db import client
from generate_embeddings import get_embeddings
from qdrant_client.models import PointStruct
from constants import VectorConstants

logger = logging.getLogger(__name__)

def add_memory(memory_content: str) -> str:
    """
    Add a memory to the collection with proper validation and error handling.
    
    Args:
        memory_content: The text content to store as memory
        
    Returns:
        Success message string
        
    Raises:
        ValueError: If memory content is empty or invalid
        Exception: If database operation fails
    """
    if not memory_content or not memory_content.strip():
        raise ValueError("Memory content cannot be empty")
    
    cleaned_content = memory_content.strip()
    memory_id = str(uuid.uuid4())
    
    try:
        logger.info(f"Adding memory with ID: {memory_id}")
        embedding_vector = get_embeddings(cleaned_content)
        
        client.upsert(
            collection_name=VectorConstants.COLLECTION_NAME,
            wait=True,
            points=[
                PointStruct(
                    id=memory_id, 
                    vector=embedding_vector, 
                    payload={"memory": cleaned_content}
                )
            ],
        )
        
        logger.info(f"Successfully added memory with ID: {memory_id}")
        return "Memory added successfully!"
        
    except Exception as e:
        logger.error(f"Failed to add memory: {str(e)}")
        raise Exception(f"Failed to add memory: {str(e)}")

if __name__ == "__main__":
    test_memory = "This is a test memory."
    try:
        result = add_memory(test_memory)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
