"""
Transaction Management Utilities

This module provides utilities for managing MongoDB transactions to ensure
data consistency and prevent race conditions.

Clean Code Principles:
- Explicit error handling (no silent failures)
- Clear function names
- Single responsibility
"""

import logging
from collections.abc import Callable
from contextlib import contextmanager
from typing import TypeVar

from pymongo.client_session import ClientSession
from pymongo.errors import DuplicateKeyError

from ..database import mongo_client

logger = logging.getLogger(__name__)

T = TypeVar("T")


@contextmanager
def transaction_context():
    """
    Context manager for MongoDB transactions.

    Provides automatic session management, transaction commit/rollback,
    and proper cleanup.

    Usage:
        with transaction_context() as session:
            db.collection.insert_one(doc, session=session)
            db.collection.update_one(filter, update, session=session)

    Yields:
        ClientSession: MongoDB client session for transaction operations

    Raises:
        OperationFailure: If transaction cannot be started or committed
    """
    session: ClientSession = mongo_client.start_session()

    try:
        session.start_transaction(
            read_concern={"level": "majority"},
            write_concern={"w": "majority"},
            read_preference="primary",
        )

        logger.debug("🔄 Transaction started")

        yield session

        # Commit if no exceptions occurred
        session.commit_transaction()
        logger.debug("✅ Transaction committed")

    except Exception as e:
        # Rollback on any error
        logger.warning(f"⚠️ Transaction rolled back due to error: {e}")
        session.abort_transaction()
        raise

    finally:
        session.end_session()
        logger.debug("🔚 Transaction session ended")


def execute_with_transaction(operation: Callable[[ClientSession], T]) -> T:
    """
    Execute a database operation within a transaction.

    This is a convenience wrapper around transaction_context for operations
    that can be encapsulated in a single function.

    Args:
        operation: Function that takes a ClientSession and returns a result

    Returns:
        T: Result from the operation

    Raises:
        Exception: Any exception from the operation (transaction will be rolled back)

    Example:
        def add_member(session):
            db.members.insert_one(doc, session=session)
            return doc["_id"]

        member_id = execute_with_transaction(add_member)
    """
    with transaction_context() as session:
        return operation(session)


def handle_duplicate_key_error(
    operation: Callable[[], T], entity_type: str, identifier: str
) -> tuple[T | None, bool]:
    """
    Execute an operation and handle duplicate key errors gracefully.

    This utility is useful for idempotent operations where duplicate key
    errors indicate that the desired state already exists.

    Args:
        operation: Function to execute (should raise DuplicateKeyError if duplicate)
        entity_type: Type of entity for logging (e.g., "organization_member")
        identifier: Identifier for logging (e.g., user email or ID)

    Returns:
        tuple: (result, was_duplicate)
            - result: Result from operation or None if duplicate
            - was_duplicate: True if duplicate key error occurred

    Example:
        result, is_duplicate = handle_duplicate_key_error(
            lambda: db.members.insert_one(doc),
            "project_member",
            user_email
        )
        if is_duplicate:
            logger.info("Member already exists")
    """
    try:
        result = operation()
        return result, False

    except DuplicateKeyError:
        logger.info(
            f"ℹ️ {entity_type} already exists for {identifier}. "
            "This is expected in concurrent scenarios."
        )
        return None, True


def safe_insert_member(
    collection, member_doc: dict, entity_type: str, session: ClientSession | None = None
) -> tuple[str | None, bool]:
    """
    Safely insert a member document, handling duplicates gracefully.

    This function attempts to insert a member document and returns whether
    it was successful or if the member already existed.

    Args:
        collection: MongoDB collection to insert into
        member_doc: Document to insert
        entity_type: Type for logging ("organization_member" or "project_member")
        session: Optional transaction session

    Returns:
        tuple: (inserted_id, already_existed)
            - inserted_id: String ID of inserted document or None if duplicate
            - already_existed: True if member already existed

    Example:
        member_id, existed = safe_insert_member(
            mongo_db.project_members,
            member_doc,
            "project_member",
            session=session
        )
        if existed:
            logger.info("Member was already added by another request")
    """
    try:
        result = collection.insert_one(member_doc, session=session)
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
