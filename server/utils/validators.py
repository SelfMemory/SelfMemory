"""
Input validation utilities for the SelfMemory server.

Following Uncle Bob's Clean Code principles:
- ZERO fallback mechanisms
- Explicit error handling
- Clear, descriptive function names
- Single responsibility per function
"""

import logging
import re
from typing import Any

from bson import ObjectId
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ObjectId validation pattern: exactly 24 hexadecimal characters
OBJECTID_PATTERN = re.compile(r"^[0-9a-fA-F]{24}$")


def validate_object_id(value: Any, field_name: str = "ID") -> ObjectId:
    """
    Validate and convert a string to MongoDB ObjectId.

    This function prevents ObjectId injection attacks by:
    1. Checking for None/empty values
    2. Validating the format (24 hex characters)
    3. Attempting conversion with explicit error handling
    4. Returning generic error messages to users
    5. Logging detailed errors for debugging

    Args:
        value: The value to validate (should be a string)
        field_name: Name of the field being validated (for error messages)

    Returns:
        ObjectId: Valid MongoDB ObjectId

    Raises:
        HTTPException: 400 Bad Request with generic error message

    Examples:
        >>> validate_object_id("507f1f77bcf86cd799439011", "user_id")
        ObjectId('507f1f77bcf86cd799439011')

        >>> validate_object_id("invalid", "project_id")
        HTTPException(400, "Invalid project_id format")

        >>> validate_object_id(None, "org_id")
        HTTPException(400, "Invalid org_id format")
    """
    # Check for None or empty values
    if value is None or value == "":
        logger.warning(f"ObjectId validation failed: {field_name} is None or empty")
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")

    # Convert to string if not already
    value_str = str(value)

    # Validate format using regex (24 hex characters)
    if not OBJECTID_PATTERN.match(value_str):
        logger.warning(
            f"ObjectId validation failed: {field_name}='{value_str}' does not match "
            f"expected format (24 hexadecimal characters)"
        )
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")

    # Attempt conversion to ObjectId
    try:
        obj_id = ObjectId(value_str)
        return obj_id
    except Exception as e:
        # Log detailed error for debugging (not exposed to user)
        logger.error(
            f"ObjectId conversion failed: {field_name}='{value_str}', "
            f"error_type={type(e).__name__}, error={str(e)}"
        )
        # Return generic error to user (no system information leakage)
        raise HTTPException(
            status_code=400, detail=f"Invalid {field_name} format"
        ) from e


def validate_multiple_object_ids(
    values: list[str], field_name: str = "IDs"
) -> list[ObjectId]:
    """
    Validate and convert multiple strings to MongoDB ObjectIds.

    This is useful for endpoints that accept arrays of IDs.

    Args:
        values: List of string values to validate
        field_name: Name of the field being validated (for error messages)

    Returns:
        list[ObjectId]: List of valid MongoDB ObjectIds

    Raises:
        HTTPException: 400 Bad Request if any ID is invalid

    Examples:
        >>> validate_multiple_object_ids(
        ...     ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"],
        ...     "project_ids"
        ... )
        [ObjectId('507f1f77bcf86cd799439011'), ObjectId('507f1f77bcf86cd799439012')]
    """
    if not values:
        return []

    validated_ids = []
    for i, value in enumerate(values):
        try:
            obj_id = validate_object_id(value, f"{field_name}[{i}]")
            validated_ids.append(obj_id)
        except HTTPException as err:
            # Re-raise with more context
            raise HTTPException(
                status_code=400, detail=f"Invalid {field_name} format at index {i}"
            ) from err

    return validated_ids
