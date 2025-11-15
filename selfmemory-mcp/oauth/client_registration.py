"""OAuth 2.0 Dynamic Client Registration (RFC 7591) utilities.

This module provides sanitization functions for client registration requests
and responses, ensuring compatibility between MCP clients (like Cursor/VS Code)
and Hydra's strict validation requirements.

Following Uncle Bob's Clean Code:
- Single responsibility per function
- Small, focused functions
- No duplication
- Clear naming
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def sanitize_registration_request(registration_data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize client registration request for Hydra compatibility.

    Removes invalid or problematic fields that MCP clients may send but
    Hydra will reject. Handles common issues like:
    - Invalid URL fields (null, empty, non-HTTP)
    - Invalid contacts array
    - Malformed metadata

    Args:
        registration_data: Raw registration request from client

    Returns:
        Sanitized registration data safe for Hydra
    """
    # Work on a copy to avoid mutating original
    sanitized = registration_data.copy()

    # Remove invalid URL fields
    sanitized = _remove_invalid_url_fields(sanitized)

    # Clean contacts array
    sanitized = _clean_contacts_field(sanitized)

    logger.info("✨ Sanitized registration data ready for Hydra")
    return sanitized


def _remove_invalid_url_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Remove invalid optional URL metadata fields.

    Cursor/VS Code MCP client sends invalid URL fields that fail Hydra validation.
    Remove any URL field that is null, empty, or not a valid HTTP(S) URL.

    Args:
        data: Registration data

    Returns:
        Data with invalid URL fields removed
    """
    url_fields = ["client_uri", "logo_uri", "tos_uri", "policy_uri"]

    for field in url_fields:
        if field in data:
            value = data[field]
            # Remove if null, empty, or not HTTP(S)
            if value is None or (
                isinstance(value, str)
                and (not value or not value.startswith(("http://", "https://")))
            ):
                logger.info(f"🧹 Removing invalid {field}: {repr(value)}")
                del data[field]

    return data


def _clean_contacts_field(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and clean contacts array.

    Contacts must be valid email addresses. Remove field entirely if:
    - It's null or not an array
    - It contains no valid emails

    Args:
        data: Registration data

    Returns:
        Data with cleaned contacts field
    """
    if "contacts" not in data:
        return data

    contacts = data["contacts"]

    # Remove if invalid type
    if contacts is None or not isinstance(contacts, list) or len(contacts) == 0:
        logger.info(f"🧹 Removing invalid contacts field: {repr(contacts)}")
        del data["contacts"]
        return data

    # Filter to valid emails only
    valid_contacts = [c for c in contacts if c and isinstance(c, str) and "@" in c]

    if len(valid_contacts) == 0:
        logger.info("🧹 Removing contacts with no valid emails")
        del data["contacts"]
    elif len(valid_contacts) < len(contacts):
        logger.info(f"🧹 Filtered contacts: {len(contacts)} -> {len(valid_contacts)}")
        data["contacts"] = valid_contacts

    return data


def inject_memory_scopes(
    current_scopes: str | list[str], memory_scopes: list[str]
) -> str:
    """Inject required memory scopes into client registration.

    Ensures client can request the configured memory scopes from config.
    Also normalizes offline/offline_access scope naming to support both variants.

    Args:
        current_scopes: Current scope string or list from registration
        memory_scopes: Memory scopes from config (e.g., ["memories:read", "memories:write"])

    Returns:
        Space-separated scope string with memory scopes injected
    """
    # Normalize to list
    if isinstance(current_scopes, str):
        scope_list = current_scopes.split()
    elif isinstance(current_scopes, list):
        scope_list = current_scopes.copy()
    else:
        # Fallback to defaults if unexpected type
        scope_list = ["openid", "offline_access"]

    # Normalize offline scope handling
    # Keep BOTH 'offline' and 'offline_access' so Hydra accepts either
    # This fixes: "Client is not allowed to request scope 'offline'"
    scope_list = _normalize_offline_scopes(scope_list)

    # Add memory scopes from config if not present
    for scope in memory_scopes:
        if scope not in scope_list:
            scope_list.append(scope)

    result = " ".join(scope_list)
    logger.info(f"✨ Injected memory scopes: {result}")

    return result


def _normalize_offline_scopes(scopes: list[str]) -> list[str]:
    """Normalize offline scope to support both variants.

    Some clients request 'offline', others 'offline_access'.
    We register BOTH so Hydra accepts either variant in authorization requests.

    Args:
        scopes: List of scope strings

    Returns:
        Scopes with both offline variants if either was present
    """
    has_offline = "offline" in scopes
    has_offline_access = "offline_access" in scopes

    # Remove both variants first
    scopes = [s for s in scopes if s not in ["offline", "offline_access"]]

    # Add both variants so Hydra accepts either in authorization requests
    if has_offline or has_offline_access:
        scopes.extend(["offline", "offline_access"])

    return scopes


def sanitize_registration_response(response_data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize Hydra's registration response for MCP client compatibility.

    Hydra may return fields as null/empty which MCP clients reject.
    Remove these invalid fields from the response.

    Args:
        response_data: Response from Hydra

    Returns:
        Sanitized response safe for MCP client
    """
    # Work on a copy
    sanitized = response_data.copy()

    # Remove invalid URL fields from response
    sanitized = _remove_invalid_url_fields(sanitized)

    # Remove invalid contacts from response
    sanitized = _clean_contacts_field(sanitized)

    logger.info("✨ Sanitized response ready for MCP client")
    return sanitized
