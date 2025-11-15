"""
Kratos session validator.

Validates Kratos sessions and extracts user identity and traits.
No fallbacks - fail fast with clear errors.
"""

import logging

from ory_kratos_client.exceptions import ApiException

from .ory_config import get_kratos_frontend_api, get_kratos_identity_api
from .retry_utils import retry_with_exponential_backoff

# Session cookie validation constants
MAX_COOKIE_LENGTH = 4096  # Standard HTTP header limit

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================


class KratosSession:
    """Kratos session data with user identity and traits."""

    def __init__(
        self,
        user_id: str,
        email: str,
        organization_id: str,
        project_ids: list[str] | None = None,
        name: str | None = None,
        is_active: bool = True,
    ):
        """
        Initialize Kratos session data.

        Args:
            user_id: Kratos identity ID
            email: User email
            organization_id: Organization ID from traits
            project_ids: List of project IDs from traits
            name: User name (optional)
            is_active: Whether the identity is active
        """
        self.user_id = user_id
        self.email = email
        self.organization_id = organization_id
        self.project_ids = project_ids or []
        self.name = name
        self.is_active = is_active

    def __repr__(self) -> str:
        """String representation for logging."""
        return (
            f"KratosSession(user_id={self.user_id}, email={self.email}, "
            f"org={self.organization_id}, projects={len(self.project_ids)})"
        )


# ============================================================================
# Session Validation
# ============================================================================


def validate_session(session_cookie: str) -> KratosSession:
    """
    Validate Kratos session and extract user identity.

    This function validates a session cookie with Kratos and extracts
    the user's identity and multi-tenant traits (organization_id, project_ids).

    Args:
        session_cookie: Kratos session cookie value (ory_kratos_session)

    Returns:
        KratosSession: Validated session with user identity and traits

    Raises:
        ValueError: If session is invalid, expired, or user is inactive
        ApiException: If Kratos API call fails
    """
    if not session_cookie:
        error_msg = "Session cookie is required"
        logger.warning(error_msg)
        raise ValueError(error_msg)

    # Validate cookie length to prevent header overflow attacks
    if len(session_cookie) > MAX_COOKIE_LENGTH:
        error_msg = f"Session cookie exceeds maximum length: {len(session_cookie)}"
        logger.warning(error_msg)
        raise ValueError(error_msg)

    try:
        # Validate session with Kratos using Cookie header (not x-session-token)
        # This matches how the dashboard validates sessions successfully
        from ory_kratos_client.api_client import ApiClient

        logger.info(f"Validating Kratos session (cookie length: {len(session_cookie)})")

        # Create a custom API client with the Cookie header
        api_client = ApiClient(
            configuration=get_kratos_frontend_api().api_client.configuration
        )

        # Set the Cookie header with the session token
        api_client.set_default_header("Cookie", f"ory_kratos_session={session_cookie}")

        # Create frontend API with our custom client
        from ory_kratos_client import FrontendApi

        frontend_api = FrontendApi(api_client=api_client)

        # Call Kratos to validate session with retry logic for transient failures
        session = retry_with_exponential_backoff(
            lambda: frontend_api.to_session(),
            max_retries=3,
            base_delay=1.0,
        )

        # Check if session is active
        if not session.active:
            error_msg = "Session is not active"
            logger.warning(f"{error_msg}: {session.id}")
            raise ValueError(error_msg)

        # Extract identity
        identity = session.identity
        if not identity:
            error_msg = "Session has no identity"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Check if identity is active
        if identity.state != "active":
            error_msg = f"Identity is not active: state={identity.state}"
            logger.warning(f"{error_msg}, user={identity.id}")
            raise ValueError(error_msg)

        # Extract traits
        traits = identity.traits or {}

        # Get required traits
        email = traits.get("email")
        if not email:
            error_msg = "Identity missing required trait: email"
            logger.error(f"{error_msg}, user={identity.id}")
            raise ValueError(error_msg)

        organization_id = traits.get("organization_id")
        if not organization_id:
            error_msg = "Identity missing required trait: organization_id"
            logger.error(f"{error_msg}, user={identity.id}, email={email}")
            raise ValueError(error_msg)

        # Get optional traits
        project_ids = traits.get("project_ids", [])
        name = traits.get("name")

        # Create session object
        kratos_session = KratosSession(
            user_id=identity.id,
            email=email,
            organization_id=organization_id,
            project_ids=project_ids,
            name=name,
            is_active=True,
        )

        logger.info(f"✅ Kratos session validated: {kratos_session}")

        return kratos_session

    except ApiException as e:
        # Handle Kratos API errors
        # Note: Don't chain exception to prevent internal details leakage
        if e.status == 401:
            error_msg = "Invalid or expired session"
            logger.warning(f"{error_msg}: {e.reason}")
        else:
            error_msg = f"Kratos API error: {e.reason}"
            logger.error(f"{error_msg}, status={e.status}")
        raise ValueError(error_msg) from None
    except Exception as e:
        error_msg = f"Session validation error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg) from e


def get_identity_by_id(identity_id: str) -> KratosSession:
    """
    Get identity from Kratos by ID.

    This uses the Admin API to fetch identity details.
    Useful for syncing user data or verifying identity state.

    Args:
        identity_id: Kratos identity ID

    Returns:
        KratosSession: Identity data with traits

    Raises:
        ValueError: If identity not found or invalid
        ApiException: If Kratos API call fails
    """
    if not identity_id:
        error_msg = "Identity ID is required"
        logger.warning(error_msg)
        raise ValueError(error_msg)

    try:
        identity_api = get_kratos_identity_api()

        logger.info(f"Fetching identity from Kratos: {identity_id}")

        # Get identity from Admin API with retry logic for transient failures
        identity = retry_with_exponential_backoff(
            lambda: identity_api.get_identity(id=identity_id),
            max_retries=3,
            base_delay=1.0,
        )

        # Check if identity is active
        if identity.state != "active":
            error_msg = f"Identity is not active: state={identity.state}"
            logger.warning(f"{error_msg}, user={identity_id}")
            raise ValueError(error_msg)

        # Extract traits
        traits = identity.traits or {}

        email = traits.get("email")
        if not email:
            error_msg = "Identity missing required trait: email"
            logger.error(f"{error_msg}, user={identity_id}")
            raise ValueError(error_msg)

        organization_id = traits.get("organization_id")
        if not organization_id:
            error_msg = "Identity missing required trait: organization_id"
            logger.error(f"{error_msg}, user={identity_id}, email={email}")
            raise ValueError(error_msg)

        project_ids = traits.get("project_ids", [])
        name = traits.get("name")

        kratos_session = KratosSession(
            user_id=identity.id,
            email=email,
            organization_id=organization_id,
            project_ids=project_ids,
            name=name,
            is_active=True,
        )

        logger.info(f"✅ Identity fetched: {kratos_session}")

        return kratos_session

    except ApiException as e:
        if e.status == 404:
            error_msg = f"Identity not found: {identity_id}"
            logger.warning(error_msg)
        else:
            error_msg = f"Kratos API error: {e.reason}"
            logger.error(f"{error_msg}, status={e.status}")
        raise ValueError(error_msg) from None
    except Exception as e:
        error_msg = f"Error fetching identity: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg) from e
