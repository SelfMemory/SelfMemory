"""
Database Utilities

Utility functions for database operations with proper error handling.

Clean Code Principles:
- Explicit error handling (no silent failures)
- Clear function names
- Single responsibility
"""

import logging

from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)


def safe_insert_member(
    collection, member_doc: dict, entity_type: str
) -> tuple[str | None, bool]:
    """
    Safely insert a member document, handling duplicates gracefully.

    This function attempts to insert a member document and returns whether
    it was successful or if the member already existed.

    Args:
        collection: MongoDB collection to insert into
        member_doc: Document to insert
        entity_type: Type for logging ("organization_member" or "project_member")

    Returns:
        tuple: (inserted_id, already_existed)
            - inserted_id: String ID of inserted document or None if duplicate
            - already_existed: True if member already existed

    Example:
        member_id, existed = safe_insert_member(
            mongo_db.project_members,
            member_doc,
            "project_member"
        )
        if existed:
            logger.info("Member was already added by another request")
    """
    try:
        result = collection.insert_one(member_doc)
        inserted_id = str(result.inserted_id)
        logger.debug(f"✅ Inserted {entity_type}: {inserted_id}")
        return inserted_id, False

    except DuplicateKeyError:
        # Member already exists (race condition or retry)
        # This is acceptable - the unique index did its job
        user_id = member_doc.get("userId")
        logger.info(
            f"ℹ️ {entity_type} already exists for user {user_id}. "
            "Likely concurrent request or retry."
        )
        return None, True
