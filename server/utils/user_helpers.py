"""
User management helper functions
"""

import logging

from pymongo.database import Database

from ..utils.datetime_helpers import utc_now

logger = logging.getLogger(__name__)


def ensure_user_exists(db: Database, kratos_id: str, email: str | None = None) -> dict:
    """
    Ensure user record exists in database, create if missing.

    This is critical for OAuth flows where users may not have a
    database record created yet, but need to accept invitations
    or access organizations.

    Args:
        db: MongoDB database instance
        kratos_id: Ory Kratos user UUID
        email: User's email address (optional, but recommended)

    Returns:
        dict: User document

    Raises:
        ValueError: If user cannot be found or created
    """
    # Try to find existing user by Kratos ID
    user = db.users.find_one({"kratosId": kratos_id})

    if user:
        # Update last seen
        db.users.update_one({"_id": user["_id"]}, {"$set": {"lastLogin": utc_now()}})
        logger.debug(f"Found existing user: kratosId={kratos_id}")
        return user

    # User doesn't exist - create new record
    now = utc_now()
    user_doc = {
        "kratosId": kratos_id,
        "createdAt": now,
        "lastLogin": now,
    }

    # Add email if provided
    if email:
        user_doc["email"] = email.lower().strip()

    result = db.users.insert_one(user_doc)
    logger.info(f"✅ Created user record: kratosId={kratos_id}, email={email or 'N/A'}")

    # Return the newly created user
    user = db.users.find_one({"_id": result.inserted_id})
    if not user:
        raise ValueError(f"Failed to create user record for kratosId={kratos_id}")

    return user


def get_or_create_user(db: Database, kratos_id: str, email: str | None = None) -> dict:
    """
    Alias for ensure_user_exists() for better semantic clarity.
    Use when you expect the user might not exist.
    """
    return ensure_user_exists(db, kratos_id, email)
