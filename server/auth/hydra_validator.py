"""
Hydra token validator.

Validates OAuth 2.1 tokens via Hydra introspection and extracts claims.
No fallbacks - fail fast with clear errors.
"""

import logging
import os

from ory_hydra_client.exceptions import ApiException

from .ory_config import get_hydra_oauth2_api

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================


class HydraToken:
    """Hydra token data with OAuth claims."""

    def __init__(
        self,
        active: bool,
        subject: str,
        client_id: str,
        scopes: list[str],
        project_id: str | None = None,
        organization_id: str | None = None,
        expires_at: int | None = None,
        issued_at: int | None = None,
    ):
        """
        Initialize Hydra token data.

        Args:
            active: Whether token is active
            subject: Token subject (user ID)
            client_id: OAuth client ID
            scopes: List of granted scopes
            project_id: Project ID from custom claims
            organization_id: Organization ID from custom claims
            expires_at: Token expiration timestamp
            issued_at: Token issued timestamp
        """
        self.active = active
        self.subject = subject
        self.client_id = client_id
        self.scopes = scopes
        self.project_id = project_id
        self.organization_id = organization_id
        self.expires_at = expires_at
        self.issued_at = issued_at

    def __repr__(self) -> str:
        """String representation for logging."""
        return (
            f"HydraToken(active={self.active}, subject={self.subject}, "
            f"client={self.client_id}, scopes={self.scopes}, "
            f"project={self.project_id}, org={self.organization_id})"
        )


# ============================================================================
# Token Validation
# ============================================================================


def validate_token(access_token: str) -> HydraToken:
    """
    Validate OAuth token via Hydra introspection.

    This function introspects an access token with Hydra and extracts
    OAuth claims including multi-tenant context (project_id, organization_id).

    SECURITY: Validates token audience per MCP spec and RFC 8707 to prevent
    token passthrough attacks and confused deputy vulnerabilities.

    Args:
        access_token: OAuth 2.1 access token (Bearer token)

    Returns:
        HydraToken: Validated token with claims and multi-tenant context

    Raises:
        ValueError: If token is invalid, expired, or missing required claims
        ApiException: If Hydra API call fails
    """
    if not access_token:
        error_msg = "Access token is required"
        logger.warning(error_msg)
        raise ValueError(error_msg)

    try:
        oauth2_api = get_hydra_oauth2_api()

        logger.info(f"Introspecting Hydra token (length: {len(access_token)})")

        # Introspect token with Hydra
        introspection = oauth2_api.introspect_o_auth2_token(token=access_token)

        # Check if token is active
        if not introspection.active:
            error_msg = "Token is not active"
            logger.warning(error_msg)
            raise ValueError(error_msg)

        # Extract required claims
        subject = introspection.sub
        if not subject:
            error_msg = "Token missing required claim: sub"
            logger.error(error_msg)
            raise ValueError(error_msg)

        client_id = introspection.client_id
        if not client_id:
            error_msg = "Token missing required claim: client_id"
            logger.error(f"{error_msg}, subject={subject}")
            raise ValueError(error_msg)

        # RFC 8707: Validate audience claim (CRITICAL for security)
        # MCP spec requires tokens to be issued specifically for this server
        aud = introspection.aud
        if not aud:
            error_msg = "Token missing required claim: aud (audience)"
            logger.error(f"{error_msg}, subject={subject}, client={client_id}")
            raise ValueError(error_msg)

        # Audience can be string or list per JWT spec (RFC 7519)
        audiences = aud if isinstance(aud, list) else [aud]

        # Get our MCP server's expected resource URL
        from ..config import config

        expected_resource = config.mcp.SERVER_URL.rstrip("/")
        
        # DIAGNOSTIC: Log audience validation details
        logger.info(f"🔍 AUDIENCE VALIDATION:")
        logger.info(f"   Expected: {expected_resource}")
        logger.info(f"   Received: {audiences}")
        logger.info(f"   MCP_SERVER_URL env: {os.getenv('MCP_SERVER_URL', 'NOT SET')}")

        # Validate token was issued for THIS MCP server
        is_valid_audience = any(
            audience.rstrip("/") == expected_resource for audience in audiences
        )

        if not is_valid_audience:
            error_msg = (
                f"Token audience mismatch: expected '{expected_resource}', "
                f"got {audiences}"
            )
            logger.error(f"{error_msg}, subject={subject}, client={client_id}")
            logger.error(f"💡 FIX: Set MCP_SERVER_URL={expected_resource} and ensure consent flow includes this as grant_access_token_audience")
            raise ValueError(error_msg)

        logger.info(f"✅ Token audience validated: {audiences}, subject={subject}")

        # Extract scopes - handle missing scope attribute gracefully
        try:
            scope_str = introspection.scope if hasattr(introspection, 'scope') else None
            scopes = scope_str.split() if scope_str else []
        except (AttributeError, ApiException):
            # If scope is not available, check the raw response
            scopes = []
            if hasattr(introspection, '_data_store'):
                scope_value = introspection._data_store.get('scope')
                if scope_value:
                    scopes = scope_value.split() if isinstance(scope_value, str) else []
            logger.warning(f"⚠️  Scope not directly accessible, extracted: {scopes}")

        # Extract custom claims (ext contains custom claims)
        ext = introspection.ext or {}
        project_id = ext.get("project_id")
        organization_id = ext.get("organization_id")

        # Get timestamps
        expires_at = introspection.exp
        issued_at = introspection.iat

        # Create token object
        hydra_token = HydraToken(
            active=True,
            subject=subject,
            client_id=client_id,
            scopes=scopes,
            project_id=project_id,
            organization_id=organization_id,
            expires_at=expires_at,
            issued_at=issued_at,
        )

        logger.info(f"✅ Hydra token validated: {hydra_token}")

        return hydra_token

    except ApiException as e:
        # Handle Hydra API errors
        if e.status == 401:
            error_msg = "Invalid or expired token"
            logger.warning(f"{error_msg}: {e.reason}")
        else:
            error_msg = f"Hydra API error: {e.reason}"
            logger.error(f"{error_msg}, status={e.status}")
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"Token validation error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg) from e


def validate_token_with_project(
    access_token: str, required_project_id: str
) -> HydraToken:
    """
    Validate token and ensure it has access to a specific project.

    This validates the token and checks that the token's project_id claim
    matches the required project ID for project-scoped operations.

    Args:
        access_token: OAuth 2.1 access token
        required_project_id: Required project ID for access

    Returns:
        HydraToken: Validated token with matching project context

    Raises:
        ValueError: If token invalid or doesn't have access to project
    """
    # Validate token first
    hydra_token = validate_token(access_token)

    # Check project access
    if not hydra_token.project_id:
        error_msg = "Token has no project context"
        logger.warning(
            f"{error_msg}: subject={hydra_token.subject}, "
            f"required_project={required_project_id}"
        )
        raise ValueError(error_msg)

    if hydra_token.project_id != required_project_id:
        error_msg = "Token project mismatch"
        logger.warning(
            f"{error_msg}: token_project={hydra_token.project_id}, "
            f"required_project={required_project_id}, "
            f"subject={hydra_token.subject}"
        )
        raise ValueError(error_msg)

    logger.info(
        f"✅ Token validated with project access: "
        f"subject={hydra_token.subject}, project={required_project_id}"
    )

    return hydra_token


def validate_token_scope(access_token: str, required_scope: str) -> HydraToken:
    """
    Validate token and ensure it has a specific scope.

    This validates the token and checks that it has the required scope
    for performing specific operations.

    Args:
        access_token: OAuth 2.1 access token
        required_scope: Required scope (e.g., "memories:read", "memories:write")

    Returns:
        HydraToken: Validated token with required scope

    Raises:
        ValueError: If token invalid or doesn't have required scope
    """
    # Validate token first
    hydra_token = validate_token(access_token)

    # Check scope
    if required_scope not in hydra_token.scopes:
        error_msg = f"Token missing required scope: {required_scope}"
        logger.warning(
            f"{error_msg}: subject={hydra_token.subject}, "
            f"token_scopes={hydra_token.scopes}"
        )
        raise ValueError(error_msg)

    logger.info(
        f"✅ Token validated with scope: "
        f"subject={hydra_token.subject}, scope={required_scope}"
    )

    return hydra_token
