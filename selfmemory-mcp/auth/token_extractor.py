"""Extract and validate OAuth tokens from MCP requests.

This module provides token extraction and validation using Hydra introspection.
It replaces the custom OAuth token validation with Hydra's standards-compliant
OAuth 2.1 token introspection.
"""

import logging
import sys
from pathlib import Path

from server.auth.hydra_validator import HydraToken, validate_token

# Add project root to path to enable importing from server package
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import client cache for performance optimization
from auth.client_cache import get_or_create_client

logger = logging.getLogger(__name__)


def extract_bearer_token(authorization_header: str | None) -> str:
    """Extract Bearer token from Authorization header.

    Args:
        authorization_header: Authorization header value

    Returns:
        Bearer token string

    Raises:
        ValueError: If header invalid or missing token
    """
    if not authorization_header:
        raise ValueError("Missing Authorization header")

    if not authorization_header.startswith("Bearer "):
        raise ValueError(
            "Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    token = authorization_header.replace("Bearer ", "", 1).strip()

    if not token:
        raise ValueError("Empty Bearer token")

    return token


async def extract_token_context(
    request, required_scopes: list[str] | None = None
) -> dict:
    """Extract and validate token from MCP request using Hydra.

    This function:
    1. Extracts Bearer token from Authorization header
    2. Validates token via Hydra introspection
    3. Extracts project context from token claims
    4. Validates required scopes

    Args:
        request: FastAPI/MCP request object
        required_scopes: Optional list of required scopes (e.g., ["memories:read"])

    Returns:
        Dict with user_id, project_id, organization_id, scopes

    Raises:
        ValueError: If token invalid or missing required data
    """
    # Get Authorization header
    auth_header = request.headers.get("authorization")

    # Extract Bearer token
    token = extract_bearer_token(auth_header)

    # Validate with Hydra
    hydra_token: HydraToken = validate_token(token)

    # Check required scopes
    if required_scopes:
        missing_scopes = [s for s in required_scopes if s not in hydra_token.scopes]
        if missing_scopes:
            error_msg = f"Token missing required scopes: {missing_scopes}"
            logger.warning(
                f"{error_msg}: token_scopes={hydra_token.scopes}, "
                f"required={required_scopes}"
            )
            raise ValueError(error_msg)

    # Extract project context
    if not hydra_token.project_id:
        error_msg = "Token missing project context"
        logger.error(
            f"{error_msg}: subject={hydra_token.subject}, scopes={hydra_token.scopes}"
        )
        raise ValueError(error_msg)

    logger.info(
        f"✅ Token context extracted: user={hydra_token.subject}, "
        f"project={hydra_token.project_id}, scopes={hydra_token.scopes}"
    )

    return {
        "user_id": hydra_token.subject,
        "project_id": hydra_token.project_id,
        "organization_id": hydra_token.organization_id,
        "scopes": hydra_token.scopes,
    }


def create_project_client(project_id: str, oauth_token: str, host: str):
    """Create SelfMemory client configured for specific project using OAuth token.
    
    Uses client caching to avoid creating new connections on every request,
    significantly improving performance by reusing TCP/TLS connections.

    Args:
        project_id: Project ID from OAuth token claims
        oauth_token: OAuth 2.1 access token (validated by middleware)
        host: SelfMemory API host

    Returns:
        Configured SelfMemoryClient instance with OAuth authentication (cached)
    """
    from selfmemory import SelfMemoryClient

    # Use helper function to eliminate DRY violation
    def create_client():
        client = SelfMemoryClient(oauth_token=oauth_token, host=host)
        client.project_id = project_id
        logger.info(f"✅ Created new SelfMemoryClient for project {project_id}")
        return client
    
    return get_or_create_client(oauth_token, create_client)
