"""
User Helper Functions

Utility functions for user lookups and operations following DRY principles.
Eliminates code duplication in user lookup patterns across routes.
"""

import logging
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException
from pymongo.database import Database

logger = logging.getLogger(__name__)


def get_user_by_id(
    db: Database, user_id: ObjectId | str, error_if_missing: bool = True
) -> Optional[dict]:
    """
    Get user by MongoDB ObjectId with optional error handling.

    Args:
        db: MongoDB database instance
        user_id: MongoDB ObjectId or string representation
        error_if_missing: If True, raise HTTPException when user not found

    Returns:
        User document or None if not found (when error_if_missing=False)

    Raises:
        HTTPException: If user not found and error_if_missing=True
    """
    try:
        # Convert string to ObjectId if needed
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)

        user = db.users.find_one({"_id": user_id})

        if not user and error_if_missing:
            logger.error(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except Exception as e:
        if error_if_missing:
            logger.error(f"Error fetching user: {e}")
            raise HTTPException(status_code=500, detail="Error fetching user")
        return None


def require_user_by_id(db: Database, user_id: ObjectId | str) -> dict:
    """
    Get user by MongoDB ObjectId, raise HTTPException if not found.

    This is a convenience function that always raises on missing user.

    Args:
        db: MongoDB database instance
        user_id: MongoDB ObjectId or string representation

    Returns:
        User document

    Raises:
        HTTPException: If user not found
    """
    return get_user_by_id(db, user_id, error_if_missing=True)


def verify_user_active(db: Database, user_id: ObjectId | str) -> dict:
    """
    Get user and verify they are active.

    Args:
        db: MongoDB database instance
        user_id: MongoDB ObjectId or string representation

    Returns:
        User document

    Raises:
        HTTPException: If user not found or inactive
    """
    user = require_user_by_id(db, user_id)

    if not user.get("isActive", True):
        logger.warning(f"Inactive user attempted access: {user_id}")
        raise HTTPException(status_code=401, detail="User account inactive")

    return user
