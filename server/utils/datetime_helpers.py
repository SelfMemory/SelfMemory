"""
UTC Datetime Helper Functions

This module provides standardized datetime utilities that ensure all datetime
objects in the application are UTC-based and timezone-aware.

Following Uncle Bob's Clean Code principles:
- Single responsibility: Each function does one thing well
- Explicit and clear naming
- No magic numbers - all configurations externalized
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Get current datetime in UTC with timezone awareness.

    Returns:
        datetime: Current UTC datetime with timezone info

    Example:
        >>> now = utc_now()
        >>> now.tzinfo == timezone.utc
        True
    """
    return datetime.now(timezone.utc)


def utc_from_timestamp(timestamp: float) -> datetime:
    """
    Convert Unix timestamp to UTC datetime with timezone awareness.

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        datetime: UTC datetime with timezone info

    Example:
        >>> dt = utc_from_timestamp(1609459200.0)
        >>> dt.year
        2021
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def utc_to_iso(dt: datetime) -> str:
    """
    Convert datetime to ISO 8601 string format.

    Args:
        dt: Datetime object (will be converted to UTC if not already)

    Returns:
        str: ISO 8601 formatted string

    Example:
        >>> dt = utc_now()
        >>> iso_str = utc_to_iso(dt)
        >>> 'T' in iso_str and 'Z' in iso_str
        True
    """
    # Ensure datetime is in UTC
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)

    return dt.isoformat()


def is_expired(expires_at: datetime) -> bool:
    """
    Check if a datetime has expired (is in the past).

    Args:
        expires_at: Expiration datetime to check

    Returns:
        bool: True if expired, False otherwise

    Example:
        >>> from datetime import timedelta
        >>> past = utc_now() - timedelta(hours=1)
        >>> is_expired(past)
        True
        >>> future = utc_now() + timedelta(hours=1)
        >>> is_expired(future)
        False
    """
    # Ensure both datetimes are timezone-aware for proper comparison
    now = utc_now()

    # Handle naive datetime by assuming UTC
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return now > expires_at
