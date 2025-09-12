"""
Authentication module for InMemory MCP server.

This module implements OAuth 2.1 resource server functionality using the existing
InMemory authentication system. API keys are validated using the InmemoryClient,
and user information is extracted for memory isolation.
"""

import logging
import os

from mcp.server.auth.provider import AccessToken, TokenVerifier

from inmemory.client import InmemoryClient

logger = logging.getLogger(__name__)


class InmemoryAccessToken(AccessToken):
    """Access token implementation with InMemory user information."""

    def __init__(
        self,
        token: str,
        user_id: str,
        key_id: str,
        name: str | None = None,
        permissions: list[str] | None = None,
    ):
        # Required AccessToken fields for MCP
        self.token = token
        self.client_id = key_id
        self.scopes = permissions or ["user"]

        # Additional InMemory-specific fields
        self.user_id = user_id
        self.key_id = key_id
        self.name = name
        self.permissions = permissions or []

    @property
    def subject(self) -> str:
        """Return the user ID as the token subject."""
        return self.user_id


class InmemoryTokenVerifier(TokenVerifier):
    """
    Token verifier for InMemory API keys.

    This verifier uses the existing InmemoryClient to validate API keys
    and extract user information for memory operations.
    """

    def __init__(self, host: str | None = None):
        """
        Initialize the token verifier.

        Args:
            host: Optional host URL for the InMemory API. If not provided,
                  will use auto-discovery or environment variables.
        """
        self.host = host or os.getenv("INMEMORY_API_HOST")
        logger.info(f"InmemoryTokenVerifier initialized with host: {self.host}")

    async def verify_token(self, token: str) -> AccessToken | None:
        """
        Verify an API key token using InmemoryClient.

        Args:
            token: The API key to verify

        Returns:
            AccessToken with user information if valid, None if invalid
        """
        try:
            # Use InmemoryClient to validate the API key
            client = InmemoryClient(api_key=token, host=self.host)

            # The client initialization already validates the API key
            # and stores user info in client.user_info
            user_info = client.user_info

            # Clean up the client connection
            client.close()

            # Extract user information
            user_id = user_info.get("user_id")
            if not user_id:
                logger.warning("API key validation succeeded but no user_id found")
                return None

            # Create access token with user information
            access_token = InmemoryAccessToken(
                token=token,
                user_id=str(user_id),
                key_id=user_info.get("key_id", "unknown"),
                name=user_info.get("name"),
                permissions=user_info.get("permissions", []),
            )

            logger.info(f"Successfully validated API key for user: {user_id}")
            return access_token

        except ValueError as e:
            # InmemoryClient raises ValueError for authentication failures
            logger.warning(f"API key validation failed: {e}")
            return None
        except Exception as e:
            # Handle other unexpected errors
            logger.error(f"Unexpected error during token verification: {e}")
            return None


def get_user_id_from_token(access_token: AccessToken) -> str:
    """
    Extract user ID from an access token.

    Args:
        access_token: The validated access token

    Returns:
        User ID string for memory operations
    """
    if isinstance(access_token, InmemoryAccessToken):
        return access_token.user_id
    return access_token.subject
