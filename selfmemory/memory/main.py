"""
Main Memory SDK class for SelfMemory.

This module provides the primary interface for local SelfMemory functionality,
with a zero-setup API for direct usage without authentication.

"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from selfmemory.configs.base import SelfMemoryConfig
from selfmemory.memory.base import MemoryBase
from selfmemory.memory.utils import (
    audit_memory_access,
    build_add_metadata,
    build_search_filters,
    validate_isolation_context,
)
from selfmemory.utils.factory import EmbedderFactory, VectorStoreFactory

logger = logging.getLogger(__name__)


class SelfMemory(MemoryBase):
    """
    User-scoped Memory class with automatic isolation.

    This class provides zero-setup functionality with embedded vector stores
    and automatic user isolation. Each Memory instance is scoped to specific
    user identifiers, ensuring complete data separation between users.

    Key Features:
        - Automatic user isolation (users can only access their own memories)
        - Zero-setup embedded vector stores and embeddings
        - Compatible with multiple vector store providers (Qdrant, ChromaDB, etc.)
        - Secure ownership validation for all operations

    Examples:
        Basic multi-user isolation:
        >>> # Each user gets their own isolated memory space
        >>> alice_memory = Memory(user_id="alice")
        >>> bob_memory = Memory(user_id="bob")
        >>> charlie_memory = Memory(user_id="charlie")

        >>> # Users can add memories independently
        >>> alice_memory.add("I love Italian food, especially pizza")
        >>> bob_memory.add("I prefer Japanese cuisine like sushi")
        >>> charlie_memory.add("Mexican food is my favorite")

        >>> # Searches are automatically user-isolated
        >>> alice_results = alice_memory.search("food")  # Only gets Alice's memories
        >>> bob_results = bob_memory.search("food")      # Only gets Bob's memories
        >>> charlie_results = charlie_memory.search("food")  # Only gets Charlie's memories

        Advanced usage with metadata and filtering:
        >>> # Add memories with rich metadata
        >>> alice_memory.add(
        ...     "Had a great meeting with the product team",
        ...     tags="work,meeting,product",
        ...     people_mentioned="Sarah,Mike,Jennifer",
        ...     topic_category="work"
        ... )

        >>> # Search with advanced filtering (still user-isolated)
        >>> work_memories = alice_memory.search(
        ...     query="meeting",
        ...     tags=["work", "meeting"],
        ...     people_mentioned=["Sarah"],
        ...     match_all_tags=True,
        ...     limit=20
        ... )

        User isolation in action:
        >>> # Users cannot access each other's memories
        >>> alice_memory.get_all()  # Returns only Alice's memories
        >>> bob_memory.get_all()    # Returns only Bob's memories

        >>> # Users can only delete their own memories
        >>> alice_memory.delete_all()  # Deletes only Alice's memories
        >>> bob_memory.delete_all()    # Deletes only Bob's memories

        Custom configuration:
        >>> # Use custom embedding and vector store providers
        >>> config = {
        ...     "embedding": {
        ...         "provider": "ollama",
        ...         "config": {"model": "nomic-embed-text"}
        ...     },
        ...     "vector_store": {
        ...         "provider": "qdrant",
        ...         "config": {"path": "./qdrant_data"}
        ...     }
        ... }
        >>> memory = Memory(user_id="user_123", config=config)

        Production multi-tenant usage:
        >>> # Different users in a multi-tenant application
        >>> def get_user_memory(user_id: str) -> Memory:
        ...     return Memory(user_id=user_id)

        >>> # Each user gets isolated memory
        >>> user_1_memory = get_user_memory("tenant_1_user_456")
        >>> user_2_memory = get_user_memory("tenant_2_user_789")

        >>> # Complete isolation - no cross-user data leakage
        >>> user_1_memory.add("Confidential business data")
        >>> user_2_memory.add("Personal notes")
        >>> # Users can never see each other's data
    """

    def __init__(self, config: SelfMemoryConfig | dict | None = None):
        """
        Initialize Memory with configuration (selfmemory style - no user_id required).

        Args:
            config: Optional SelfMemoryConfig instance or config dictionary

        Examples:
            Basic memory instance:
            >>> memory = Memory()

            With custom config:
            >>> config = {
            ...     "embedding": {"provider": "ollama", "config": {...}},
            ...     "vector_store": {"provider": "qdrant", "config": {...}}
            ... }
            >>> memory = Memory(config=config)

            Multi-user usage (user_id passed to methods):
            >>> memory = Memory()
            >>> memory.add("I love pizza", user_id="alice")
            >>> memory.add("I love sushi", user_id="bob")
            >>> alice_results = memory.search("pizza", user_id="alice")  # Only Alice's memories
            >>> bob_results = memory.search("sushi", user_id="bob")      # Only Bob's memories
        """

        # Handle different config types for clean API
        if config is None:
            self.config = SelfMemoryConfig()
        elif isinstance(config, dict):
            # Convert dict to SelfMemoryConfig for internal use
            self.config = SelfMemoryConfig.from_dict(config)
        else:
            # Already an SelfMemoryConfig object
            self.config = config

        # Use factories with exact pattern - pass raw config
        self.embedding_provider = EmbedderFactory.create(
            self.config.embedding.provider,
            self.config.embedding.config,
            self.config.vector_store.config,
        )

        self.vector_store = VectorStoreFactory.create(
            self.config.vector_store.provider, self.config.vector_store.config
        )

        # Initialize LLM
        if self.config.llm:
            from selfmemory.utils.factory import LlmFactory

            self.llm = LlmFactory.create(
                self.config.llm.provider, self.config.llm.config
            )
            self.enable_llm = True
            logger.info(
                f"Memory SDK initialized: "
                f"{self.config.embedding.provider} + {self.config.vector_store.provider} + LLM({self.config.llm.provider})"
            )
        else:
            self.llm = None
            self.enable_llm = False
            logger.info(
                f"Memory SDK initialized: "
                f"{self.config.embedding.provider} + {self.config.vector_store.provider}"
            )

    def add(
        self,
        messages,  # Can be string, dict, or list of dicts
        *,  # Enforce keyword-only arguments
        user_id: str,
        tags: str | None = None,
        people_mentioned: str | None = None,
        topic_category: str | None = None,
        project_id: str | None = None,
        organization_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        infer: bool = True,  # Whether to use LLM for fact extraction
    ) -> dict[str, Any]:
        """
        Add memory(ies) to storage with optional LLM-based fact extraction.

        Supports both simple string input and message lists (mem0-style).
        When LLM is configured and infer=True, uses intelligent fact extraction.

        Args:
            messages: String, dict, or list of message dicts (e.g., [{"role": "user", "content": "..."}])
            user_id: Required user identifier for memory isolation
            tags: Optional comma-separated tags
            people_mentioned: Optional comma-separated people names
            topic_category: Optional topic category
            project_id: Optional project identifier for project-level isolation
            organization_id: Optional organization identifier for org-level isolation
            metadata: Optional additional metadata
            infer: Whether to use LLM for intelligent fact extraction (default: True)

        Returns:
            Dict: Result information

        Examples:
            Simple string (backward compatible):
            >>> memory = SelfMemory()
            >>> memory.add("I love pizza", user_id="alice")

            Message list (mem0-style):
            >>> messages = [
            ...     {"role": "user", "content": "I love horror movies"},
            ...     {"role": "assistant", "content": "Got it!"}
            ... ]
            >>> memory.add(messages, user_id="alice")
        """
        # Handle different message formats
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, dict):
            messages = [messages]
        elif not isinstance(messages, list):
            raise ValueError("messages must be string, dict, or list of dicts")

        # Use LLM-based processing if enabled and infer=True
        if self.enable_llm and infer:
            return self._add_with_llm(
                messages=messages,
                user_id=user_id,
                tags=tags,
                people_mentioned=people_mentioned,
                topic_category=topic_category,
                project_id=project_id,
                organization_id=organization_id,
                metadata=metadata,
            )
        return self._add_without_llm(
            messages=messages,
            user_id=user_id,
            tags=tags,
            people_mentioned=people_mentioned,
            topic_category=topic_category,
            project_id=project_id,
            organization_id=organization_id,
            metadata=metadata,
        )

    def _add_without_llm(
        self,
        messages: list,
        user_id: str,
        tags: str | None = None,
        people_mentioned: str | None = None,
        topic_category: str | None = None,
        project_id: str | None = None,
        organization_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add memory without LLM processing (original behavior).

        Stores the first user message content as-is.
        """
        try:
            # STRICT ISOLATION VALIDATION
            validate_isolation_context(
                user_id=user_id,
                project_id=project_id,
                organization_id=organization_id,
                operation="memory_add",
            )

            # Extract content from first user message
            memory_content = ""
            for msg in messages:
                if msg.get("role") == "user" and msg.get("content"):
                    memory_content = msg["content"]
                    break

            if not memory_content:
                return {"success": False, "error": "No user message content found"}

            # Build memory-specific metadata
            memory_metadata = {
                "data": memory_content,
                "tags": tags or "",
                "people_mentioned": people_mentioned or "",
                "topic_category": topic_category or "",
            }

            # Merge custom metadata if provided
            if metadata:
                memory_metadata.update(metadata)

            # Build user-scoped metadata
            storage_metadata = build_add_metadata(
                user_id=user_id,
                input_metadata=memory_metadata,
                project_id=project_id,
                organization_id=organization_id,
            )

            # Generate embedding
            embedding = self.embedding_provider.embed(memory_content)

            # Generate unique ID
            memory_id = str(uuid.uuid4())

            # Insert into vector store
            self.vector_store.insert(
                vectors=[embedding], payloads=[storage_metadata], ids=[memory_id]
            )

            # AUDIT
            audit_memory_access(
                operation="memory_add",
                user_id=user_id,
                project_id=project_id,
                organization_id=organization_id,
                memory_id=memory_id,
                success=True,
            )

            context_info = f"user='{user_id}'"
            if project_id and organization_id:
                context_info += f", project='{project_id}', org='{organization_id}'"

            logger.info(f"Memory added ({context_info}): {memory_content[:50]}...")
            return {
                "success": True,
                "memory_id": memory_id,
                "message": "Memory added successfully",
            }

        except Exception as e:
            # AUDIT
            audit_memory_access(
                operation="memory_add",
                user_id=user_id,
                project_id=project_id,
                organization_id=organization_id,
                success=False,
                error=str(e),
            )

            logger.error(f"Memory.add() failed: {e}")
            return {"success": False, "error": f"Memory addition failed: {str(e)}"}

    def _add_with_llm(
        self,
        messages: list,
        user_id: str,
        tags: str | None = None,
        people_mentioned: str | None = None,
        topic_category: str | None = None,
        project_id: str | None = None,
        organization_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add memory with LLM-based fact extraction (mem0-style).

        Uses LLM to extract facts and intelligently ADD/UPDATE/DELETE memories.
        Adapted from mem0's _add_to_vector_store method.
        """
        import json

        from selfmemory.configs.prompts import get_update_memory_messages
        from selfmemory.memory.utils import (
            extract_json,
            get_fact_retrieval_messages,
            parse_messages,
            remove_code_blocks,
        )

        try:
            # Validate isolation
            validate_isolation_context(
                user_id=user_id,
                project_id=project_id,
                organization_id=organization_id,
                operation="memory_add_llm",
            )

            # Parse messages for LLM processing
            parsed_messages = parse_messages(messages)

            # Step 1: Extract facts from conversation using LLM
            system_prompt, user_prompt = get_fact_retrieval_messages(
                parsed_messages, is_agent_memory=False
            )

            print(
                "LLM Fact Extraction Prompts:",
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            response = self.llm.generate_response(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            print("LLM Fact Extraction Response:", response)

            try:
                response = remove_code_blocks(response)
                print("After removing code blocks:", response)
                if not response.strip():
                    new_facts = []
                    extracted_tags = []
                    extracted_category = None
                    extracted_people = []
                else:
                    # Clean the response - remove leading/trailing whitespace and newlines
                    response = response.strip()

                    # Try to parse as JSON directly first
                    try:
                        response_json = json.loads(response)
                        # Check if this is the new structured format with "output" array
                        if (
                            isinstance(response_json, dict)
                            and "output" in response_json
                        ):
                            # Extract memory operations from the new format
                            if (
                                len(response_json["output"]) > 1
                                and "content" in response_json["output"][1]
                                and len(response_json["output"][1]["content"]) > 0
                            ):
                                memory_text = response_json["output"][1]["content"][
                                    0
                                ].get("text", "")
                                if memory_text.strip():
                                    # Parse the memory operations JSON
                                    memory_operations = json.loads(memory_text)
                                    print(
                                        "Parsed new format memory operations:",
                                        memory_operations,
                                    )

                                    # Skip to Step 5: Execute memory operations directly
                                    # Set variables to skip intermediate steps
                                    new_facts = []  # Skip fact extraction since we have operations
                                    extracted_tags = []
                                    extracted_category = None
                                    extracted_people = []

                                    # Jump directly to executing operations
                                    returned_memories = []
                                    for op in memory_operations.get("memory", []):
                                        try:
                                            action_text = op.get("text")
                                            if not action_text:
                                                continue

                                            event_type = op.get("event")

                                            if event_type == "ADD":
                                                # Create new memory with default metadata
                                                memory_id = self._create_memory_with_embedding(
                                                    data=action_text,
                                                    existing_embeddings={},  # No precomputed embeddings
                                                    user_id=user_id,
                                                    tags=tags,  # Use user-provided metadata
                                                    people_mentioned=people_mentioned,
                                                    topic_category=topic_category,
                                                    project_id=project_id,
                                                    organization_id=organization_id,
                                                    metadata=metadata,
                                                )
                                                returned_memories.append(
                                                    {
                                                        "id": memory_id,
                                                        "memory": action_text,
                                                        "event": event_type,
                                                    }
                                                )

                                            elif event_type == "UPDATE":
                                                # For UPDATE, we need to find existing memory
                                                # This is a simplified version - in practice you might need more complex logic
                                                search_filters = build_search_filters(
                                                    user_id=user_id,
                                                    project_id=project_id,
                                                    organization_id=organization_id,
                                                )
                                                existing_memories = (
                                                    self.vector_store.search(
                                                        query=action_text,
                                                        limit=1,
                                                        filters=search_filters,
                                                    )
                                                )
                                                if existing_memories:
                                                    old_id = self._extract_memory_id(
                                                        existing_memories[0]
                                                    )
                                                    self._update_memory_with_embedding(
                                                        memory_id=old_id,
                                                        data=action_text,
                                                        existing_embeddings={},
                                                    )
                                                    returned_memories.append(
                                                        {
                                                            "id": old_id,
                                                            "memory": action_text,
                                                            "event": event_type,
                                                            "previous_memory": op.get(
                                                                "old_memory"
                                                            ),
                                                        }
                                                    )

                                            elif event_type == "DELETE":
                                                # For DELETE, we need to find existing memory
                                                search_filters = build_search_filters(
                                                    user_id=user_id,
                                                    project_id=project_id,
                                                    organization_id=organization_id,
                                                )
                                                existing_memories = (
                                                    self.vector_store.search(
                                                        query=action_text,
                                                        limit=1,
                                                        filters=search_filters,
                                                    )
                                                )
                                                if existing_memories:
                                                    old_id = self._extract_memory_id(
                                                        existing_memories[0]
                                                    )
                                                    self.vector_store.delete(old_id)
                                                    returned_memories.append(
                                                        {
                                                            "id": old_id,
                                                            "memory": action_text,
                                                            "event": event_type,
                                                        }
                                                    )

                                        except Exception as e:
                                            logger.error(
                                                f"Error processing memory operation {op}: {e}"
                                            )

                                    logger.info(
                                        f"LLM memory processing complete (new format): {len(returned_memories)} operations"
                                    )
                                    return {"results": returned_memories}
                        else:
                            # Fall back to old format parsing
                            new_facts = response_json.get("facts", [])
                            extracted_tags = response_json.get("tags", [])
                            extracted_category = response_json.get("topic_category")
                            extracted_people = response_json.get("people_mentioned", [])
                    except json.JSONDecodeError:
                        # Try extracting JSON from text if direct parsing failed
                        try:
                            extracted_json = extract_json(response)
                            response_json = json.loads(extracted_json)
                            new_facts = response_json.get("facts", [])
                            extracted_tags = response_json.get("tags", [])
                            extracted_category = response_json.get("topic_category")
                            extracted_people = response_json.get("people_mentioned", [])
                        except (json.JSONDecodeError, AttributeError):
                            # If all parsing attempts fail, log and fall back to empty
                            logger.error(
                                f"Failed to parse LLM response as JSON: {response[:200]}..."
                            )
                            new_facts = []
                            extracted_tags = []
                            extracted_category = None
                            extracted_people = []
            except Exception as e:
                logger.error(f"Error extracting facts and metadata: {e}")
                new_facts = []
                extracted_tags = []
                extracted_category = None
                extracted_people = []

            # Use LLM-extracted metadata, fallback to user-provided if not extracted
            final_tags = ",".join(extracted_tags) if extracted_tags else (tags or "")
            final_category = (
                extracted_category if extracted_category else topic_category
            )
            final_people = (
                ",".join(extracted_people)
                if extracted_people
                else (people_mentioned or "")
            )

            logger.info(
                f"LLM extracted: {len(new_facts)} facts, {len(extracted_tags)} tags, category={extracted_category}, {len(extracted_people)} people"
            )

            if not new_facts:
                logger.debug(
                    "No new facts retrieved from input. Skipping memory update LLM call."
                )
                # Return empty results - this is a valid scenario (same as mem0)
                return {"results": []}

            # Step 2: Search for existing memories
            retrieved_old_memory = []
            new_message_embeddings = {}

            # Build search filters
            search_filters = build_search_filters(
                user_id=user_id,
                project_id=project_id,
                organization_id=organization_id,
            )

            for new_fact in new_facts:
                fact_embedding = self.embedding_provider.embed(new_fact)
                new_message_embeddings[new_fact] = fact_embedding

                existing_memories = self.vector_store.search(
                    query=new_fact,
                    vectors=fact_embedding,
                    limit=5,
                    filters=search_filters,
                )

                for mem in existing_memories:
                    retrieved_old_memory.append(
                        {"id": mem.id, "text": mem.payload.get("data", "")}
                    )

            # Deduplicate by ID
            unique_memories = {}
            for item in retrieved_old_memory:
                unique_memories[item["id"]] = item
            retrieved_old_memory = list(unique_memories.values())

            logger.info(
                f"Found {len(retrieved_old_memory)} existing memories to compare against"
            )

            # Step 3: Create ID mapping (handles UUID hallucinations)
            temp_uuid_mapping = {}
            for idx, item in enumerate(retrieved_old_memory):
                temp_uuid_mapping[str(idx)] = item["id"]
                retrieved_old_memory[idx]["id"] = str(idx)

            # Step 4: Use LLM to decide ADD/UPDATE/DELETE
            # NOTE: This step is skipped when using the new LLM format since operations are already provided
            if new_facts:
                update_prompt = get_update_memory_messages(
                    retrieved_old_memory, new_facts
                )

                try:
                    logger.info(
                        f"Sending update prompt to LLM (length: {len(update_prompt)})"
                    )
                    # Use higher max_tokens for memory operations to avoid truncation
                    response = self.llm.generate_response(
                        messages=[{"role": "user", "content": update_prompt}],
                        response_format={"type": "json_object"},
                        max_tokens=3192,  # Higher limit for memory operations JSON
                    )
                    logger.info(
                        f"LLM Memory Operations Response received (length: {len(response) if response else 0})"
                    )

                    # Save full response to file for debugging
                    with open("/tmp/llm_response_debug.txt", "w") as f:
                        f.write(f"Full response:\n{response}\n")
                        f.write(
                            f"Response length: {len(response) if response else 0}\n"
                        )

                except Exception as e:
                    logger.error(f"Error getting memory operations from LLM: {e}")
                    response = ""

                try:
                    if not response or not response.strip():
                        memory_operations = {}
                    else:
                        original_response = response
                        response = remove_code_blocks(response)
                        logger.info(
                            f"After remove_code_blocks (length: {len(response)})"
                        )

                        # Log first 1000 chars and last 500 chars to see structure
                        logger.info(f"Response start: {repr(response[:1000])}")
                        if len(response) > 1500:
                            logger.info(f"Response end: {repr(response[-500:])}")

                        memory_operations = json.loads(response)
                except Exception as e:
                    logger.error(f"Invalid JSON from LLM: {e}")
                    logger.error(f"Original response length: {len(original_response)}")
                    logger.error(f"Cleaned response length: {len(response)}")
                    logger.error(
                        f"Original response start: {repr(original_response[:500])}..."
                    )
                    logger.error(f"Cleaned response start: {repr(response[:500])}...")
                    memory_operations = {}
            else:
                memory_operations = {}

            # Step 5: Execute memory operations
            returned_memories = []

            for op in memory_operations.get("memory", []):
                try:
                    action_text = op.get("text")
                    if not action_text:
                        continue

                    event_type = op.get("event")

                    if event_type == "ADD":
                        # Create new memory with LLM-extracted metadata
                        memory_id = self._create_memory_with_embedding(
                            data=action_text,
                            existing_embeddings=new_message_embeddings,
                            user_id=user_id,
                            tags=final_tags,
                            people_mentioned=final_people,
                            topic_category=final_category,
                            project_id=project_id,
                            organization_id=organization_id,
                            metadata=metadata,
                        )
                        returned_memories.append(
                            {
                                "id": memory_id,
                                "memory": action_text,
                                "event": event_type,
                            }
                        )

                    elif event_type == "UPDATE":
                        # Update existing memory
                        old_id = temp_uuid_mapping[op.get("id")]
                        self._update_memory_with_embedding(
                            memory_id=old_id,
                            data=action_text,
                            existing_embeddings=new_message_embeddings,
                        )
                        returned_memories.append(
                            {
                                "id": old_id,
                                "memory": action_text,
                                "event": event_type,
                                "previous_memory": op.get("old_memory"),
                            }
                        )

                    elif event_type == "DELETE":
                        # Delete memory
                        old_id = temp_uuid_mapping[op.get("id")]
                        self.vector_store.delete(old_id)
                        returned_memories.append(
                            {"id": old_id, "memory": action_text, "event": event_type}
                        )

                    elif event_type == "NONE":
                        # No operation needed - this is a valid scenario (same as mem0)
                        logger.info("NOOP for Memory - no changes required")
                        # Don't add to returned_memories as no actual change occurred

                except Exception as e:
                    logger.error(f"Error processing memory operation {op}: {e}")

            logger.info(
                f"LLM memory processing complete: {len(returned_memories)} operations"
            )
            return {"results": returned_memories}

        except Exception as e:
            logger.error(f"_add_with_llm failed: {e}")
            return {"success": False, "error": "An internal error occurred."}

    def _create_memory_with_embedding(
        self,
        data: str,
        existing_embeddings: dict,
        user_id: str,
        tags: str | None = None,
        people_mentioned: str | None = None,
        topic_category: str | None = None,
        project_id: str | None = None,
        organization_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new memory with precomputed embeddings."""
        # Get or create embedding
        if data in existing_embeddings:
            embedding = existing_embeddings[data]
        else:
            embedding = self.embedding_provider.embed(data)

        # Build metadata
        memory_metadata = {
            "data": data,
            "hash": hashlib.md5(data.encode()).hexdigest(),
            "tags": tags or "",
            "people_mentioned": people_mentioned or "",
            "topic_category": topic_category or "",
        }

        if metadata:
            memory_metadata.update(metadata)

        storage_metadata = build_add_metadata(
            user_id=user_id,
            input_metadata=memory_metadata,
            project_id=project_id,
            organization_id=organization_id,
        )

        # Generate ID and insert
        memory_id = str(uuid.uuid4())
        self.vector_store.insert(
            vectors=[embedding], payloads=[storage_metadata], ids=[memory_id]
        )

        return memory_id

    def _update_memory_with_embedding(
        self,
        memory_id: str,
        data: str,
        existing_embeddings: dict,
    ):
        """Update an existing memory with new data and embedding."""
        # Get existing memory
        existing_memory = self.vector_store.get(vector_id=memory_id)

        # Get or create embedding
        if data in existing_embeddings:
            embedding = existing_embeddings[data]
        else:
            embedding = self.embedding_provider.embed(data)

        # Update metadata
        new_metadata = existing_memory.payload.copy()
        new_metadata["data"] = data
        new_metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
        new_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Update in vector store
        self.vector_store.update(
            vector_id=memory_id,
            vector=embedding,
            payload=new_metadata,
        )

        logger.info(f"Updated memory {memory_id}")

    def search(
        self,
        query: str = "",
        *,  # Enforce keyword-only arguments
        user_id: str,
        limit: int = 10,
        tags: list[str] | None = None,
        people_mentioned: list[str] | None = None,
        topic_category: str | None = None,
        temporal_filter: str | None = None,
        threshold: float | None = None,
        match_all_tags: bool = False,
        include_metadata: bool = True,
        sort_by: str = "relevance",  # "relevance", "timestamp", "score"
        project_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Search memories with multi-tenant isolation (selfmemory style).

        All searches are scoped to the specified user's memories, and optionally
        to specific projects and organizations. Users cannot see or access
        memories from other users, projects, or organizations.

        Args:
            query: Search query string (empty string returns all memories)
            user_id: Required user identifier for memory isolation
            limit: Maximum number of results
            tags: Optional list of tags to filter by
            people_mentioned: Optional list of people to filter by
            topic_category: Optional topic category filter
            temporal_filter: Optional temporal filter (e.g., "today", "this_week", "yesterday")
            threshold: Optional minimum similarity score
            match_all_tags: Whether to match all tags (AND) or any tag (OR)
            include_metadata: Whether to include full metadata in results
            sort_by: Sort results by "relevance" (default), "timestamp", or "score"
            project_id: Optional project identifier for project-level isolation
            organization_id: Optional organization identifier for org-level isolation

        Returns:
            Dict: Search results with "results" key containing list of memories within context

        Examples:
            Basic search (user-isolated, backward compatible):
            >>> memory = Memory()
            >>> results = memory.search("pizza", user_id="alice")  # Only Alice's memories

            Multi-tenant search:
            >>> results = memory.search("pizza", user_id="alice",
            ...                        project_id="proj_123", organization_id="org_456")

            Advanced filtering with multi-tenant context:
            >>> results = memory.search(
            ...     query="meetings",
            ...     user_id="alice",
            ...     project_id="proj_123",
            ...     organization_id="org_456",
            ...     tags=["work", "important"],
            ...     people_mentioned=["John", "Sarah"],
            ...     temporal_filter="this_week",
            ...     match_all_tags=True,
            ...     limit=20
            ... )
        """
        try:
            # STRICT ISOLATION VALIDATION: Validate isolation context before proceeding
            validate_isolation_context(
                user_id=user_id,
                project_id=project_id,
                organization_id=organization_id,
                operation="memory_search",
            )

            context_info = f"user='{user_id}'"
            if project_id and organization_id:
                context_info += f", project='{project_id}', org='{organization_id}'"

            # Log search operation
            if not query or not query.strip():
                logger.info(f"Retrieving all memories ({context_info}) (empty query)")
            else:
                logger.info(
                    f"Searching memories ({context_info}) with query: '{query[:50]}...'"
                )

            # Build additional filters from search parameters
            additional_filters = {}
            if topic_category:
                additional_filters["topic_category"] = topic_category
            if tags:
                additional_filters["tags"] = tags
                additional_filters["match_all_tags"] = match_all_tags
            if people_mentioned:
                additional_filters["people_mentioned"] = people_mentioned
            if temporal_filter:
                additional_filters["temporal_filter"] = temporal_filter

            # Build multi-tenant filters using specialized function for search operations
            # Now supports project/organization context
            user_filters = build_search_filters(
                user_id=user_id,
                input_filters=additional_filters,
                project_id=project_id,
                organization_id=organization_id,
            )

            logger.info(
                f"🔍 Memory.search: Built filters for isolation: {user_filters}"
            )

            # Generate embedding for search (vector stores handle empty queries)
            query_embedding = self.embedding_provider.embed(
                query.strip() if query else ""
            )

            # Build filters for vector store (exclude people_mentioned for post-filtering)
            vector_store_filters = {
                k: v for k, v in user_filters.items() if k != "people_mentioned"
            }

            # Execute semantic search with multi-tenant isolation
            logger.info(
                f"🔍 Memory.search: Calling vector_store.search with filters: {vector_store_filters}"
            )
            results = self.vector_store.search(
                query=query,
                vectors=query_embedding,
                limit=limit * 2
                if people_mentioned
                else limit,  # Get more results if we need to filter
                filters=vector_store_filters,  # Includes automatic user_id + project_id + org_id filtering
            )
            logger.info(
                f"🔍 Memory.search: Received {len(results) if results else 0} raw results from vector store"
            )

            # Use helper method to format results consistently
            formatted_results = self._format_results(
                results, include_metadata, include_score=True
            )

            # Apply people_mentioned filtering (case-insensitive substring match)
            if people_mentioned:
                logger.info(
                    f"🔍 Memory.search: Applying people_mentioned filter: {people_mentioned}"
                )
                filtered_results = []
                for result in formatted_results:
                    metadata = result.get("metadata", {})
                    stored_people = metadata.get("people_mentioned", "").lower()
                    # Check if any of the search terms are contained in the stored people string
                    if any(
                        search_person.lower() in stored_people
                        for search_person in people_mentioned
                    ):
                        filtered_results.append(result)
                formatted_results = filtered_results
                logger.info(
                    f"🔍 Memory.search: After people_mentioned filtering: {len(formatted_results)} results"
                )

            # Apply threshold filtering if specified
            if threshold is not None:
                formatted_results = [
                    result
                    for result in formatted_results
                    if result.get("score", 0) >= threshold
                ]

            # Apply limit after filtering
            formatted_results = formatted_results[:limit]

            # Apply sorting using helper method
            formatted_results = self._apply_sorting(formatted_results, sort_by)

            # AUDIT: Log successful search operation
            audit_memory_access(
                operation="memory_search",
                user_id=user_id,
                project_id=project_id,
                organization_id=organization_id,
                memory_count=len(formatted_results),
                success=True,
            )

            logger.info(
                f"Search completed ({context_info}): {len(formatted_results)} results"
            )
            return {"results": formatted_results}

        except Exception as e:
            # AUDIT: Log failed search operation
            audit_memory_access(
                operation="memory_search",
                user_id=user_id,
                project_id=project_id,
                organization_id=organization_id,
                success=False,
                error=str(e),
            )

            context_info = f"user='{user_id}'"
            if project_id and organization_id:
                context_info += f", project='{project_id}', org='{organization_id}'"
            logger.error(f"Search failed ({context_info}): {e}")
            return {"results": []}

    def get_all(
        self,
        *,  # Enforce keyword-only arguments
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        project_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get all memories with multi-tenant isolation (selfmemory style).

        Only returns memories belonging to the specified user, and optionally
        filtered by project and organization. Users cannot see memories from
        other users, projects, or organizations.

        Args:
            user_id: Required user identifier for memory isolation
            limit: Maximum number of memories to return
            offset: Number of memories to skip
            project_id: Optional project identifier for project-level isolation
            organization_id: Optional organization identifier for org-level isolation

        Returns:
            Dict: Memories within context with "results" key

        Examples:
            Basic user isolation (backward compatible):
            >>> memory = Memory()
            >>> all_memories = memory.get_all(user_id="alice")  # Only Alice's memories
            >>> recent_memories = memory.get_all(user_id="alice", limit=10)

            Multi-tenant isolation:
            >>> project_memories = memory.get_all(user_id="alice",
            ...                                  project_id="proj_123",
            ...                                  organization_id="org_456")
        """
        try:
            context_info = f"user='{user_id}'"
            if project_id and organization_id:
                context_info += f", project='{project_id}', org='{organization_id}'"

            # Build multi-tenant filters using specialized function for search operations
            # Now supports project/organization context
            user_filters = build_search_filters(
                user_id=user_id, project_id=project_id, organization_id=organization_id
            )

            # Use list() method with multi-tenant isolation filters
            results = self.vector_store.list(filters=user_filters, limit=limit + offset)

            # Use helper method to format results consistently
            formatted_results = self._format_results(
                results, include_metadata=True, include_score=False
            )

            # Apply offset by slicing results
            paginated_results = formatted_results[offset : offset + limit]

            logger.info(
                f"Retrieved {len(paginated_results)} memories ({context_info}) (offset={offset}, limit={limit})"
            )
            return {"results": paginated_results}

        except Exception as e:
            context_info = f"user='{user_id}'"
            if project_id and organization_id:
                context_info += f", project='{project_id}', org='{organization_id}'"
            logger.error(f"Failed to get memories ({context_info}): {e}")
            return {"results": []}

    def delete(self, memory_id: str) -> dict[str, Any]:
        """
        Delete a specific memory (selfmemory style - no ownership validation needed).

        Deletes the specified memory by ID. In the new selfmemory-style architecture,
        ownership validation is handled at the API level, not in the Memory class.

        Args:
            memory_id: Memory identifier to delete

        Returns:
            Dict: Deletion result with success status and message

        Examples:
            >>> memory = Memory()
            >>> result = memory.delete("memory_123")
        """
        try:
            # Simply delete the memory (selfmemory style - no ownership validation)
            success = self.vector_store.delete(memory_id)

            if success:
                logger.info(f"Memory {memory_id} deleted successfully")
                return {"success": True, "message": "Memory deleted successfully"}
            return {
                "success": False,
                "error": "Memory deletion failed",
            }

        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            return {"success": False, "error": str(e)}

    def delete_all(
        self,
        *,  # Enforce keyword-only arguments
        user_id: str,
        project_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete all memories with multi-tenant isolation (selfmemory style).

        Only deletes memories belonging to the specified user, and optionally
        filtered by project and organization. Users cannot delete memories from
        other users, projects, or organizations.

        Args:
            user_id: Required user identifier for memory isolation
            project_id: Optional project identifier for project-level isolation
            organization_id: Optional organization identifier for org-level isolation

        Returns:
            Dict: Deletion result with count of deleted memories within context

        Examples:
            Basic user isolation (backward compatible):
            >>> memory = Memory()
            >>> result = memory.delete_all(user_id="alice")  # Only deletes Alice's memories
            >>> print(result["deleted_count"])  # Number of Alice's memories deleted

            Multi-tenant isolation:
            >>> result = memory.delete_all(user_id="alice",
            ...                           project_id="proj_123",
            ...                           organization_id="org_456")
            >>> print(result["deleted_count"])  # Number deleted within project context
        """
        try:
            context_info = f"user='{user_id}'"
            if project_id and organization_id:
                context_info += f", project='{project_id}', org='{organization_id}'"

            # Build multi-tenant filters using specialized function for search operations
            # Now supports project/organization context
            user_filters = build_search_filters(
                user_id=user_id, project_id=project_id, organization_id=organization_id
            )

            # Get memories within context only (for counting)
            user_memories = self.vector_store.list(filters=user_filters, limit=10000)

            # Use helper method to extract points from results
            points = self._extract_points_from_results(user_memories)

            deleted_count = 0

            # Delete only memories within the specified context
            for point in points:
                memory_id = self._extract_memory_id(point)

                if memory_id and self.vector_store.delete(memory_id):
                    deleted_count += 1

            logger.info(f"Deleted {deleted_count} memories ({context_info})")
            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Deleted {deleted_count} memories ({context_info})",
            }

        except Exception as e:
            context_info = f"user='{user_id}'"
            if project_id and organization_id:
                context_info += f", project='{project_id}', org='{organization_id}'"
            logger.error(f"Failed to delete all memories ({context_info}): {e}")
            return {"success": False, "error": str(e)}

    def _format_results(
        self, results, include_metadata: bool = True, include_score: bool = True
    ) -> list[dict[str, Any]]:
        """
        Format results consistently across all methods (selfmemory style).

        This helper method standardizes result formatting from different vector stores,
        ensuring consistent output format regardless of the underlying storage provider.

        Args:
            results: Raw results from vector store operations
            include_metadata: Whether to include full metadata in results
            include_score: Whether to include similarity scores

        Returns:
            List of formatted result dictionaries
        """
        formatted_results = []

        # Extract points from results using helper method
        points = self._extract_points_from_results(results)

        for point in points:
            # Build base result structure
            result = {
                "id": self._extract_memory_id(point),
                "content": self._extract_content(point),
            }

            # Add score if requested and available
            if include_score:
                result["score"] = getattr(point, "score", 1.0)

            # Add metadata if requested
            if include_metadata:
                result["metadata"] = self._extract_metadata(point)

            formatted_results.append(result)

        return formatted_results

    def _extract_points_from_results(self, results) -> list:
        """
        Extract points from vector store results (handles different formats).

        Different vector stores return results in different formats:
        - Some return tuples: (points, metadata)
        - Some return lists directly: [point1, point2, ...]
        - Some return single objects

        Args:
            results: Raw results from vector store

        Returns:
            List of point objects
        """
        if isinstance(results, tuple) and len(results) > 0:
            # Handle tuple format (e.g., from Qdrant list operations)
            return results[0] if isinstance(results[0], list) else [results[0]]
        if isinstance(results, list):
            # Handle direct list format
            return results
        if results is not None:
            # Handle single result
            return [results]
        # Handle empty/None results
        return []

    def _extract_memory_id(self, point) -> str:
        """
        Extract memory ID from a point object (handles different formats).

        Args:
            point: Point object from vector store

        Returns:
            Memory ID as string
        """
        if hasattr(point, "id"):
            return str(point.id)
        if isinstance(point, dict):
            return str(point.get("id", ""))
        return ""

    def _extract_content(self, point) -> str:
        """
        Extract content/data from a point object (handles different formats).

        Args:
            point: Point object from vector store

        Returns:
            Memory content as string
        """
        if hasattr(point, "payload"):
            return point.payload.get("data", "")
        if isinstance(point, dict):
            return point.get("data", point.get("content", ""))
        return ""

    def _extract_metadata(self, point) -> dict[str, Any]:
        """
        Extract metadata from a point object (handles different formats).

        Args:
            point: Point object from vector store

        Returns:
            Metadata dictionary
        """
        if hasattr(point, "payload"):
            return point.payload
        if isinstance(point, dict):
            return point
        return {}

    def _apply_sorting(
        self, results: list[dict[str, Any]], sort_by: str
    ) -> list[dict[str, Any]]:
        """
        Apply sorting to formatted results (selfmemory style).

        Args:
            results: List of formatted result dictionaries
            sort_by: Sort method ("relevance", "timestamp", "score")

        Returns:
            Sorted list of results
        """
        if not results:
            return results

        if sort_by == "timestamp":
            return sorted(
                results,
                key=lambda x: x.get("metadata", {}).get("created_at", ""),
                reverse=True,
            )
        if sort_by == "score":
            return sorted(results, key=lambda x: x.get("score", 0), reverse=True)
        # "relevance" is default - already sorted by vector store
        return results

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics for memories.

        Returns:
            Dict: Statistics including memory count, provider info, etc.
        """
        try:
            memory_count = (
                self.vector_store.count() if hasattr(self.vector_store, "count") else 0
            )

            # Get embedding model from config
            embedding_model = "unknown"
            if self.config.embedding.config and hasattr(
                self.config.embedding.config, "model"
            ):
                embedding_model = self.config.embedding.config.model

            return {
                "embedding_provider": self.config.embedding.provider,
                "embedding_model": embedding_model,
                "vector_store": self.config.vector_store.provider,
                "memory_count": memory_count,
                "status": "healthy",
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check on all components.

        Returns:
            Dict: Health check results
        """
        # Get embedding model from config
        embedding_model = "unknown"
        if self.config.embedding.config and hasattr(
            self.config.embedding.config, "model"
        ):
            embedding_model = self.config.embedding.config.model

        health = {
            "status": "healthy",
            "storage_type": self.config.vector_store.provider,
            "embedding_model": embedding_model,
            "embedding_provider": self.config.embedding.provider,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Test vector store connectivity
            if hasattr(self.vector_store, "health_check"):
                vector_health = self.vector_store.health_check()
                health.update(vector_health)
            elif hasattr(self.vector_store, "count"):
                count = self.vector_store.count()
                health["memory_count"] = count
                health["vector_store_status"] = "connected"
            else:
                health["vector_store_status"] = "available"

            # Test embedding provider
            if hasattr(self.embedding_provider, "health_check"):
                embedding_health = self.embedding_provider.health_check()
                health.update(embedding_health)
            else:
                health["embedding_provider_status"] = "available"

            logger.info("Health check passed")

        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
            logger.error(f"Health check failed: {e}")

        return health

    def close(self) -> None:
        """
        Close connections and cleanup resources.

        Should be called when Memory instance is no longer needed.
        """
        try:
            # Clean up vector store and embedding providers
            if hasattr(self, "vector_store") and hasattr(self.vector_store, "close"):
                self.vector_store.close()
            if hasattr(self, "embedding_provider") and hasattr(
                self.embedding_provider, "close"
            ):
                self.embedding_provider.close()
            logger.info("Memory SDK connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

    def __repr__(self) -> str:
        """String representation of Memory instance."""
        return f"Memory(embedding={self.config.embedding.provider}, db={self.config.vector_store.provider})"
