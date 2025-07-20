"""
Enhanced memory addition system with rich metadata, temporal data, and duplicate detection.
Handles comprehensive memory storage with all advanced features.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from qdrant_db import client
from generate_embeddings import get_embeddings
from qdrant_client.models import PointStruct
from constants import VectorConstants, MetadataConstants, DuplicateConstants
from src.shared.temporal_utils import TemporalProcessor
from src.shared.duplicate_detector import DuplicateDetector, DuplicateHandler

logger = logging.getLogger(__name__)

class EnhancedMemoryManager:
    """
    Enhanced memory manager with duplicate detection, rich metadata, and temporal processing.
    Follows Uncle Bob's Single Responsibility Principle.
    """
    
    def __init__(self):
        """Initialize the enhanced memory manager."""
        self.duplicate_detector = DuplicateDetector()
        self.temporal_processor = TemporalProcessor()
    
    def add_memory_with_metadata(
        self,
        memory_content: str,
        tags: List[str] = None,
        people_mentioned: List[str] = None,
        topic_category: str = None,
        check_duplicates: bool = True,
        duplicate_action: str = DuplicateConstants.DUPLICATE_ACTION_SKIP
    ) -> Dict[str, Any]:
        """
        Add a memory with rich metadata and duplicate detection.
        
        Args:
            memory_content: The memory text to store
            tags: List of tags to categorize the memory
            people_mentioned: List of people mentioned in the memory
            topic_category: Category/topic of the memory
            check_duplicates: Whether to check for duplicates before adding
            duplicate_action: Action to take if duplicates are found
            
        Returns:
            Dictionary with operation result and details
            
        Raises:
            ValueError: If memory content is empty
            Exception: If memory storage fails
        """
        if not memory_content or not memory_content.strip():
            raise ValueError("Memory content cannot be empty")
        
        try:
            logger.info(f"Adding enhanced memory: '{memory_content[:50]}...'")
            
            # Prepare metadata
            metadata = self._prepare_metadata(tags, people_mentioned, topic_category)
            
            # Check for duplicates if enabled
            if check_duplicates:
                is_duplicate, similar_memories = self.duplicate_detector.check_for_duplicates(
                    memory_content, metadata
                )
                
                if is_duplicate:
                    logger.info(f"Duplicate detected, applying action: {duplicate_action}")
                    duplicate_result = DuplicateHandler.handle_duplicate(
                        duplicate_action, memory_content, similar_memories, metadata
                    )
                    
                    # Always return duplicate result for skip and merge actions
                    if duplicate_action in [DuplicateConstants.DUPLICATE_ACTION_SKIP, DuplicateConstants.DUPLICATE_ACTION_MERGE]:
                        return duplicate_result
            
            # Generate temporal metadata
            current_time = datetime.now()
            temporal_data = self.temporal_processor.generate_temporal_metadata(current_time)
            
            # Create comprehensive payload
            payload = self._create_enhanced_payload(
                memory_content.strip(),
                current_time,
                temporal_data,
                metadata
            )
            
            # Generate embedding and store
            memory_id = str(uuid.uuid4())
            embedding_vector = get_embeddings(memory_content.strip())
            
            # Store in Qdrant
            client.upsert(
                collection_name=VectorConstants.COLLECTION_NAME,
                wait=True,
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=embedding_vector,
                        payload=payload
                    )
                ],
            )
            
            logger.info(f"Successfully added enhanced memory with ID: {memory_id}")
            
            return {
                'success': True,
                'action': 'added',
                'memory_id': memory_id,
                'message': f"Memory successfully added with rich metadata",
                'metadata': metadata,
                'temporal_data': temporal_data
            }
            
        except Exception as e:
            logger.error(f"Failed to add enhanced memory: {str(e)}")
            raise Exception(f"Enhanced memory storage failed: {str(e)}")
    
    def _prepare_metadata(
        self, 
        tags: List[str] = None, 
        people_mentioned: List[str] = None, 
        topic_category: str = None
    ) -> Dict[str, Any]:
        """
        Prepare and validate metadata for storage.
        
        Args:
            tags: List of tags
            people_mentioned: List of people mentioned
            topic_category: Topic category
            
        Returns:
            Dictionary of prepared metadata
        """
        metadata = {}
        
        if tags:
            # Clean and validate tags
            clean_tags = [tag.strip().lower() for tag in tags if tag.strip()]
            metadata[MetadataConstants.TAGS_FIELD] = clean_tags
        
        if people_mentioned:
            # Clean and validate people names
            clean_people = [person.strip() for person in people_mentioned if person.strip()]
            metadata[MetadataConstants.PEOPLE_FIELD] = clean_people
        
        if topic_category:
            # Validate and clean topic category
            clean_topic = topic_category.strip().lower()
            metadata[MetadataConstants.TOPIC_FIELD] = clean_topic
        
        return metadata
    
    def _create_enhanced_payload(
        self,
        memory_content: str,
        timestamp: datetime,
        temporal_data: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create comprehensive payload with all metadata.
        
        Args:
            memory_content: The memory text
            timestamp: Creation timestamp
            temporal_data: Rich temporal metadata
            metadata: Additional metadata (tags, people, etc.)
            
        Returns:
            Complete payload dictionary
        """
        payload = {
            MetadataConstants.MEMORY_FIELD: memory_content,
            MetadataConstants.TIMESTAMP_FIELD: timestamp.isoformat(),
            MetadataConstants.TEMPORAL_FIELD: temporal_data
        }
        
        # Add metadata fields if they exist
        for field in [MetadataConstants.TAGS_FIELD, MetadataConstants.PEOPLE_FIELD, MetadataConstants.TOPIC_FIELD]:
            if field in metadata:
                payload[field] = metadata[field]
        
        return payload

# Legacy function for backward compatibility
def add_memory(memory_content: str) -> str:
    """
    Legacy add_memory function for backward compatibility.
    
    Args:
        memory_content: The text content to store as memory
        
    Returns:
        Success message string
        
    Raises:
        ValueError: If memory content is empty or invalid
        Exception: If database operation fails
    """
    try:
        manager = EnhancedMemoryManager()
        result = manager.add_memory_with_metadata(memory_content)
        
        if result['success']:
            return f"Memory added successfully with ID: {result['memory_id']}"
        else:
            return f"Memory operation result: {result['message']}"
            
    except Exception as e:
        logger.error(f"Legacy add_memory failed: {str(e)}")
        raise Exception(f"Failed to add memory: {str(e)}")

# Enhanced function for MCP tools
def add_memory_enhanced(
    memory_content: str,
    tags: str = "",
    people_mentioned: str = "",
    topic_category: str = "",
    check_duplicates: bool = True
) -> str:
    """
    Enhanced add_memory function with rich metadata support for MCP tools.
    
    Args:
        memory_content: The memory text to store
        tags: Comma-separated tags
        people_mentioned: Comma-separated people names
        topic_category: Category/topic of the memory
        check_duplicates: Whether to check for duplicates
        
    Returns:
        Formatted result message
    """
    try:
        # Parse comma-separated strings
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else None
        people_list = [person.strip() for person in people_mentioned.split(",") if person.strip()] if people_mentioned else None
        category = topic_category.strip() if topic_category else None
        
        manager = EnhancedMemoryManager()
        result = manager.add_memory_with_metadata(
            memory_content=memory_content,
            tags=tag_list,
            people_mentioned=people_list,
            topic_category=category,
            check_duplicates=check_duplicates
        )
        
        if result['success']:
            # Handle successful addition
            if result.get('action') == 'added':
                response_parts = [f"✅ Memory added successfully (ID: {result['memory_id']})"]
                
                if result.get('metadata'):
                    metadata = result['metadata']
                    if metadata.get('tags'):
                        response_parts.append(f"Tags: {', '.join(metadata['tags'])}")
                    if metadata.get('people_mentioned'):
                        response_parts.append(f"People: {', '.join(metadata['people_mentioned'])}")
                    if metadata.get('topic_category'):
                        response_parts.append(f"Topic: {metadata['topic_category']}")
                
                if result.get('temporal_data'):
                    temporal = result['temporal_data']
                    response_parts.append(f"Time: {temporal['day_of_week']}, Q{temporal['quarter']} {temporal['year']}")
                
                return "\n".join(response_parts)
            
            # Handle duplicate detection cases
            elif result.get('action') == 'skipped' and result.get('reason') == 'duplicate_detected':
                response_parts = [
                    f"🚫 Memory rejected due to duplicate detection",
                    f"📊 Similarity score: {result.get('similarity_score', 0):.3f} (threshold: {result.get('threshold', 0.90)})",
                    "",
                    f"💭 Existing similar memory:",
                    f"   {result.get('existing_memory', 'N/A')[:200]}{'...' if len(result.get('existing_memory', '')) > 200 else ''}"
                ]
                return "\n".join(response_parts)
            
            # Handle other success cases (merge, etc.)
            else:
                return f"✅ {result['message']}"
        else:
            return f"⚠️ {result['message']}"
            
    except Exception as e:
        logger.error(f"Enhanced add_memory failed: {str(e)}")
        return f"❌ Failed to add memory: {str(e)}"

if __name__ == "__main__":
    # Test enhanced memory addition
    manager = EnhancedMemoryManager()
    
    test_memory = "Learning about vector databases and their applications in AI systems"
    test_tags = ["learning", "ai", "databases"]
    test_people = ["John", "Sarah"]
    test_category = "technology"
    
    try:
        result = manager.add_memory_with_metadata(
            memory_content=test_memory,
            tags=test_tags,
            people_mentioned=test_people,
            topic_category=test_category,
            check_duplicates=True
        )
        
        print(f"Test result: {result}")
        
        # Test legacy function
        legacy_result = add_memory("This is a simple test memory")
        print(f"Legacy test: {legacy_result}")
        
    except Exception as e:
        print(f"Test failed: {e}")
