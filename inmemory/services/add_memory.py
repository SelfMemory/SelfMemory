"""
Enhanced memory addition system with rich metadata, temporal data, and duplicate detection.
Handles comprehensive memory storage with all advanced features.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field
from qdrant_client.models import PointStruct

from inmemory.common.constants import DuplicateConstants, MetadataConstants
from inmemory.common.duplicate_detector import DuplicateDetector
from inmemory.common.temporal_utils import TemporalProcessor
from inmemory.repositories.qdrant_db import (
    ensure_user_collection_exists,
    get_qdrant_client,
)
from inmemory.security.encryption import encrypt_memory_payload
from inmemory.utils.embeddings import get_embeddings

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
        user_id: str,
        tags: list[str] = None,
        people_mentioned: list[str] = None,
        topic_category: str = None,
        check_duplicates: bool = True,
        duplicate_action: str = DuplicateConstants.DUPLICATE_ACTION_SKIP,
    ) -> dict[str, Any]:
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
            logger.info("Adding memory...'")

            # Prepare metadata
            metadata = self._prepare_metadata(tags, people_mentioned, topic_category)

            # Check for duplicates if enabled
            if check_duplicates:
                is_duplicate, similar_memories = (
                    self.duplicate_detector.check_for_duplicates(
                        memory_content, user_id, metadata
                    )
                )

                # if is_duplicate:
                #     logger.info(
                #         f"Duplicate detected, applying action: {duplicate_action}"
                #     )
                #     duplicate_result = DuplicateHandler.handle_duplicate(
                #         duplicate_action, memory_content, similar_memories, metadata
                #     )

                #     # Always return duplicate result for skip and merge actions
                #     if duplicate_action in [
                #         DuplicateConstants.DUPLICATE_ACTION_SKIP,
                #         DuplicateConstants.DUPLICATE_ACTION_MERGE,
                #     ]:
                #         return duplicate_result

            # Generate temporal metadata
            current_time = datetime.now()
            temporal_data = self.temporal_processor.generate_temporal_metadata(
                current_time
            )

            # Create comprehensive payload
            payload = self._create_enhanced_payload(
                memory_content.strip(), current_time, temporal_data, metadata, user_id
            )

            # Ensure user collection exists and get collection name
            collection_name = ensure_user_collection_exists(user_id)

            # Generate embedding and store
            memory_id = str(uuid.uuid4())
            embedding_vector = get_embeddings(memory_content.strip())

            # Get client and store in user-specific collection
            client = get_qdrant_client()
            client.upsert(
                collection_name=collection_name,
                wait=True,
                points=[
                    PointStruct(id=memory_id, vector=embedding_vector, payload=payload)
                ],
            )

            logger.info("I just discovered something new about you!")

            return {
                "success": True,
                "action": "added",
                "memory_id": memory_id,
                "message": "Memory successfully added with rich metadata",
                "metadata": metadata,
                "temporal_data": temporal_data,
            }

        except Exception as e:
            logger.error(f"Failed to add enhanced memory: {str(e)}")
            raise Exception("Our bad, we missed it. Could you say it again?") from e

    def _prepare_metadata(
        self,
        tags: list[str] = None,
        people_mentioned: list[str] = None,
        topic_category: str = None,
    ) -> dict[str, Any]:
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
            clean_people = [
                person.strip() for person in people_mentioned if person.strip()
            ]
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
        temporal_data: dict[str, Any],
        metadata: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """
        Create comprehensive payload with all metadata and encryption.

        Args:
            memory_content: The memory text
            timestamp: Creation timestamp
            temporal_data: Rich temporal metadata
            metadata: Additional metadata (tags, people, etc.)
            user_id: User identifier for encryption

        Returns:
            Complete payload dictionary with encrypted sensitive fields
        """
        logger.info(f"🔐 Creating payload for encryption - user: {user_id}")
        logger.info(f"🔐 Memory content length: {len(memory_content)} chars")
        logger.info(
            f"🔐 Metadata fields: {list(metadata.keys()) if metadata else 'None'}"
        )

        payload = {
            MetadataConstants.MEMORY_FIELD: memory_content,
            MetadataConstants.TIMESTAMP_FIELD: timestamp.isoformat(),
            MetadataConstants.TEMPORAL_FIELD: temporal_data,
        }

        # Add metadata fields if they exist
        for field in [
            MetadataConstants.TAGS_FIELD,
            MetadataConstants.PEOPLE_FIELD,
            MetadataConstants.TOPIC_FIELD,
        ]:
            if field in metadata:
                payload[field] = metadata[field]

        logger.info(f"🔐 Payload before encryption: {list(payload.keys())}")
        logger.info(f"🔐 Starting encryption for user: {user_id}")

        try:
            # Encrypt sensitive fields before storage
            encrypted_payload = encrypt_memory_payload(payload, user_id)
            logger.info("🔐 ✅ Encryption completed successfully")
            logger.info(f"🔐 Encrypted payload keys: {list(encrypted_payload.keys())}")

            # Verify encryption worked by checking if content changed
            original_memory = payload.get(MetadataConstants.MEMORY_FIELD, "")
            encrypted_memory = encrypted_payload.get(MetadataConstants.MEMORY_FIELD, "")

            if original_memory == encrypted_memory:
                logger.error(
                    "🔐 ❌ WARNING: Memory content appears UNENCRYPTED! Original==Encrypted"
                )
                logger.error(f"🔐 ❌ Original: '{original_memory[:50]}...'")
                logger.error(f"🔐 ❌ Encrypted: '{encrypted_memory[:50]}...'")
            else:
                logger.info(
                    "🔐 ✅ Memory content successfully encrypted (content changed)"
                )
                logger.info(
                    f"🔐 Original length: {len(original_memory)}, Encrypted length: {len(encrypted_memory)}"
                )

            return encrypted_payload

        except Exception as e:
            logger.error(f"🔐 ❌ ENCRYPTION FAILED: {str(e)}")
            logger.error(f"🔐 ❌ Exception type: {type(e)}")
            logger.error(
                "🔐 ❌ Returning UNENCRYPTED payload - THIS IS A SECURITY ISSUE!"
            )
            return payload  # Return unencrypted as fallback but log the issue


# # Legacy function for backward compatibility
# def add_memory(memory_content: str) -> str:
#     """
#     Legacy add_memory function for backward compatibility.

#     Args:
#         memory_content: The text content to store as memory

#     Returns:
#         Success message string

#     Raises:
#         ValueError: If memory content is empty or invalid
#         Exception: If database operation fails
#     """
#     try:
#         manager = EnhancedMemoryManager()
#         result = manager.add_memory_with_metadata(memory_content)

#         if result["success"]:
#             return f"Memory added successfully with ID: {result['memory_id']}"
#         else:
#             return f"Memory operation result: {result['message']}"

#     except Exception as e:
#         logger.error(f"Legacy add_memory failed: {str(e)}")
#         raise Exception(f"Failed to add memory: {str(e)}")


# Enhanced function for MCP tools
def add_memory_enhanced(
    memory_content: str = Field(..., description="Memory text content to store"),
    user_id: str = Field(..., description="User identifier for memory isolation"),
    tags: str = Field("", description="Comma-separated tags (e.g., 'project,meeting')"),
    people_mentioned: str = Field("", description="Comma-separated names"),
    topic_category: str = Field("", description="Category or topic"),
    check_duplicates: bool = Field(
        True, description="Check for duplicates (default: True)"
    ),
) -> dict[str, Any]:
    """
    Enhanced add_memory function with rich metadata support for MCP tools.

    Returns:
        Dictionary with operation result, memory_id, and formatted message
    """
    try:
        # Parse comma-separated strings
        tag_list = (
            [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else None
        )
        people_list = (
            [person.strip() for person in people_mentioned.split(",") if person.strip()]
            if people_mentioned
            else None
        )
        category = topic_category.strip() if topic_category else None

        manager = EnhancedMemoryManager()
        result = manager.add_memory_with_metadata(
            memory_content=memory_content,
            user_id=user_id,
            tags=tag_list,
            people_mentioned=people_list,
            topic_category=category,
            check_duplicates=check_duplicates,
        )

        if result["success"]:
            # Handle successful addition
            if result.get("action") == "added":
                response_parts = ["I just discovered something new about you!"]

                if result.get("metadata"):
                    metadata = result["metadata"]
                    if metadata.get("tags"):
                        response_parts.append(f"Tags: {', '.join(metadata['tags'])}")
                    if metadata.get("people_mentioned"):
                        response_parts.append(
                            f"People: {', '.join(metadata['people_mentioned'])}"
                        )
                    if metadata.get("topic_category"):
                        response_parts.append(f"Topic: {metadata['topic_category']}")

                formatted_message = "\n".join(response_parts)

                # **CRITICAL FIX**: Return structured data including memory_id
                return {
                    "success": True,
                    "memory_id": result.get(
                        "memory_id"
                    ),  # Include the actual memory ID
                    "message": formatted_message,
                    "action": result.get("action"),
                    "metadata": result.get("metadata", {}),
                    "temporal_data": result.get("temporal_data", {}),
                }

            # Handle duplicate detection cases
            if (
                result.get("action") == "skipped"
                and result.get("reason") == "duplicate_detected"
            ):
                response_parts = [
                    "Got it, I already knew this one!",
                    # "",
                    # f"💭 Existing similar memory:",
                    # f"   {result.get('existing_memory', 'N/A')[:200]}{'...' if len(result.get('existing_memory', '')) > 200 else ''}",
                ]
                formatted_message = "\n".join(response_parts)

                return {
                    "success": True,
                    "memory_id": None,  # No new memory created for duplicates
                    "message": formatted_message,
                    "action": result.get("action"),
                    "reason": result.get("reason"),
                }

            # Handle other success cases (merge, etc.)
            return {
                "success": True,
                "memory_id": result.get("memory_id"),
                "message": f"✅ {result['message']}",
                "action": result.get("action"),
            }
        return {
            "success": False,
            "memory_id": None,
            "message": f"⚠️ {result['message']}",
            "error": result.get("error"),
        }

    except Exception as e:
        logger.error(f"Enhanced add_memory failed: {str(e)}")
        return {
            "success": False,
            "memory_id": None,
            "message": f"❌ Failed to add memory: {str(e)}",
            "error": str(e),
        }


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
            check_duplicates=True,
        )

        print(f"Test result: {result}")

        # Test legacy function
        # legacy_result = add_memory("This is a simple test memory")
        # print(f"Legacy test: {legacy_result}")

    except Exception as e:
        print(f"Test failed: {e}")
