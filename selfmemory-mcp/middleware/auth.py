"""Token validation middleware for SelfMemory MCP Server.

Per MCP 2025-06-18 spec:
- Sessions MUST NOT be used for authentication
- Token passthrough is forbidden
- Validate audience on all tokens
- HTTP transport: Validate MCP-Protocol-Version header
"""

from fastapi import Request
from oauth import errors
from oauth.token_manager import TokenManager


async def validate_request(
    request: Request,
    token_manager: TokenManager,
    required_scopes: list[str] | None = None,
) -> dict:
    """Validate inbound request with OAuth token.

    Args:
        request: FastAPI request object
        token_manager: Token manager instance
        required_scopes: Optional list of required scopes

    Returns:
        Dict with user_id, project_id, scopes

    Raises:
        HTTPException: If validation fails
    """
    # Get authorization header
    authorization = request.headers.get("authorization")

    if not authorization or not authorization.startswith("Bearer "):
        raise errors.invalid_token("Missing or invalid Authorization header")

    # Extract token
    token = authorization.replace("Bearer ", "")

    # Validate token
    try:
        token_data = await token_manager.validate_access_token(
            token=token, required_scopes=required_scopes
        )
        return token_data

    except ValueError as e:
        error_msg = str(e)

        # Check if it's a scope issue
        if "scope" in error_msg.lower():
            raise errors.insufficient_scope(required_scopes or []) from e

        # Otherwise it's an invalid token
        scope = " ".join(required_scopes) if required_scopes else None
        raise errors.invalid_token(error_msg, scope) from e
