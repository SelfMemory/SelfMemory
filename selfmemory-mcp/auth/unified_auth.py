"""Unified authentication supporting both OAuth 2.1 and API key methods.

This module provides authentication detection and validation that works with:
1. OAuth 2.1 tokens from Hydra (JWT format)
2. Legacy API keys from SelfMemory dashboard (simple format)

Both authentication methods result in a unified token context structure that
tools can use transparently without knowing which auth method was used.
"""

import logging
from typing import Literal

from server.auth.hydra_validator import HydraToken, validate_token

from .token_extractor import extract_bearer_token

logger = logging.getLogger(__name__)


# Type for authentication methods
AuthType = Literal["oauth", "api_key"]


class TokenContext:
    """Unified token context from either OAuth or API key authentication."""

    def __init__(
        self,
        auth_type: AuthType,
        user_id: str,
        project_id: str | None,
        organization_id: str | None,
        scopes: list[str],
        raw_token: str,
    ):
        self.auth_type = auth_type
        self.user_id = user_id
        self.project_id = project_id
        self.organization_id = organization_id
        self.scopes = scopes
        self.raw_token = raw_token

    def to_dict(self) -> dict:
        """Convert to dictionary for context storage."""
        return {
            "auth_type": self.auth_type,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "organization_id": self.organization_id,
            "scopes": self.scopes,
            "raw_token": self.raw_token,
        }

    def has_scope(self, scope: str) -> bool:
        """Check if token has required scope."""
        return scope in self.scopes


def looks_like_jwt(token: str) -> bool:
    """Check if token looks like a JWT (OAuth token from Hydra).

    JWTs have the format: header.payload.signature (3 parts separated by dots)
    API keys typically have a different format (e.g., sk_im_xxx or im_xxx)

    Args:
        token: Token string to check

    Returns:
        True if token appears to be a JWT, False otherwise
    """
    return token.count(".") == 2


def validate_oauth_token(token: str, core_server_host: str) -> TokenContext:
    """Validate OAuth token via Hydra and create token context.

    Args:
        token: OAuth token (JWT format)
        core_server_host: Core server URL (not used for OAuth validation)

    Returns:
        TokenContext with OAuth authentication details

    Raises:
        ValueError: If token is invalid or missing required claims
    """
    try:
        # Validate with Hydra introspection
        hydra_token: HydraToken = validate_token(token)

        # Validate project context exists
        if not hydra_token.project_id:
            raise ValueError("OAuth token missing project context")

        logger.info(
            f"✅ OAuth token validated: user={hydra_token.subject}, "
            f"project={hydra_token.project_id}, scopes={hydra_token.scopes}"
        )

        return TokenContext(
            auth_type="oauth",
            user_id=hydra_token.subject,
            project_id=hydra_token.project_id,
            organization_id=hydra_token.organization_id,
            scopes=hydra_token.scopes,
            raw_token=token,
        )
    except Exception as e:
        logger.debug(f"OAuth token validation failed: {e}")
        raise ValueError(f"Invalid OAuth token: {e}") from e


def validate_api_key(token: str, core_server_host: str) -> TokenContext:
    """Validate API key via Core server and create token context.

    Args:
        token: API key string
        core_server_host: Core server URL for validation

    Returns:
        TokenContext with API key authentication details

    Raises:
        ValueError: If API key is invalid
    """
    try:
        # Validate API key by making a test request to Core server
        import httpx

        # Use /api/v1/ping endpoint to validate API key and get user context
        response = httpx.get(
            f"{core_server_host}/api/v1/ping",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )

        if response.status_code != 200:
            raise ValueError(
                f"API key validation returned status {response.status_code}"
            )

        user_info = response.json()

        # API keys have full access to memories
        scopes = ["memories:read", "memories:write"]

        logger.info(
            f"✅ API key validated: user={user_info.get('user_id')}, "
            f"project={user_info.get('project_id')}"
        )

        return TokenContext(
            auth_type="api_key",
            user_id=user_info["user_id"],
            project_id=user_info.get("project_id"),
            organization_id=user_info.get("organization_id"),
            scopes=scopes,
            raw_token=token,
        )
    except httpx.HTTPError as e:
        logger.debug(f"API key validation failed (HTTP error): {e}")
        raise ValueError(f"Invalid API key: {e}") from e
    except Exception as e:
        logger.debug(f"API key validation failed: {e}")
        raise ValueError(f"Invalid API key: {e}") from e


async def detect_and_validate_auth(
    authorization_header: str,
    core_server_host: str,
) -> TokenContext:
    """Detect authentication method and validate token accordingly.

    This function intelligently detects whether the provided token is:
    1. OAuth token (JWT format) - validates via Hydra
    2. API key (other format) - validates via Core server

    Args:
        authorization_header: Full Authorization header value
        core_server_host: Core server URL for API key validation

    Returns:
        TokenContext with unified authentication details

    Raises:
        ValueError: If authentication fails with both methods
    """
    # Extract Bearer token
    token = extract_bearer_token(authorization_header)

    # Try OAuth validation first if token looks like JWT
    if looks_like_jwt(token):
        try:
            return validate_oauth_token(token, core_server_host)
        except ValueError as e:
            logger.debug(f"JWT token validation failed, trying API key: {e}")

    # Try API key validation
    try:
        return validate_api_key(token, core_server_host)
    except ValueError as api_error:
        # Both validations failed
        if looks_like_jwt(token):
            error_msg = "Token validation failed for both OAuth and API key"
        else:
            error_msg = f"Invalid API key: {api_error}"

        logger.warning(f"❌ Authentication failed: {error_msg}")
        raise ValueError(error_msg) from None
