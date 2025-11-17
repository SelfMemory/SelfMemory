"""
MCP (Model Context Protocol) Authentication Module

Implements OAuth 2.1 authentication for MCP clients using Ory Hydra.
Follows RFC 9728 (Protected Resource Metadata) and MCP authorization specification.
"""

import logging
from typing import Any

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from .config import config

logger = logging.getLogger(__name__)


class BearerTokenInfo:
    """Information extracted from a validated bearer token."""

    def __init__(
        self,
        token: str,
        user_id: str,
        scopes: list[str],
        client_id: str,
        expires_at: int | None = None,
    ):
        self.token = token
        self.user_id = user_id
        self.scopes = scopes
        self.client_id = client_id
        self.expires_at = expires_at

    def has_scope(self, required_scope: str) -> bool:
        """Check if token has required scope."""
        return required_scope in self.scopes


async def verify_bearer_token(token: str) -> BearerTokenInfo:
    """
    Verify bearer token using Ory Hydra's introspection endpoint.

    Args:
        token: The access token to verify

    Returns:
        BearerTokenInfo: Information about the validated token

    Raises:
        HTTPException: If token is invalid or introspection fails
    """
    introspection_url = f"{config.mcp.HYDRA_ADMIN_URL}/oauth2/introspect"

    logger.info(f"🔍 [MCP Auth] Verifying token via introspection: {introspection_url}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                introspection_url,
                data={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(
                    f"❌ [MCP Auth] Introspection failed: {response.status_code} - {error_text}"
                )
                raise HTTPException(
                    status_code=401,
                    detail="Token introspection failed",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            data = response.json()
            logger.info(
                f"🔍 [MCP Auth] Introspection response: active={data.get('active')}"
            )

            # Check if token is active
            if not data.get("active", False):
                logger.warning("⚠️ [MCP Auth] Token is not active")
                raise HTTPException(
                    status_code=401,
                    detail="Token is not active",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Extract token information
            user_id = data.get("sub")
            if not user_id:
                logger.error("❌ [MCP Auth] No subject (user_id) in token")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token: missing subject",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Extract scopes
            scope_str = data.get("scope", "")
            scopes = scope_str.split() if scope_str else []

            # Verify audience matches our server
            audiences = data.get("aud", [])
            if isinstance(audiences, str):
                audiences = [audiences]

            # Check if our server URL is in the audience
            server_url_normalized = config.mcp.SERVER_URL.rstrip("/")
            audience_match = any(
                aud.rstrip("/") == server_url_normalized for aud in audiences
            )

            if not audience_match:
                logger.error(
                    f"❌ [MCP Auth] Audience mismatch: expected {server_url_normalized}, got {audiences}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Token not intended for this resource server",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            logger.info(
                f"✅ [MCP Auth] Token verified successfully: user={user_id}, scopes={scopes}, client={data.get('client_id')}"
            )

            return BearerTokenInfo(
                token=token,
                user_id=user_id,
                scopes=scopes,
                client_id=data.get("client_id", "unknown"),
                expires_at=data.get("exp"),
            )

    except httpx.RequestError as e:
        logger.error(f"❌ [MCP Auth] Network error during introspection: {e}")
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f"❌ [MCP Auth] Unexpected error during token verification: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="Internal authentication error",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def require_mcp_auth(request: Request) -> BearerTokenInfo:
    """
    FastAPI dependency that requires MCP bearer token authentication.

    Args:
        request: FastAPI request object

    Returns:
        BearerTokenInfo: Validated token information

    Raises:
        HTTPException: If authentication fails
    """
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        logger.warning("⚠️ [MCP Auth] No Authorization header provided")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
            headers={
                "WWW-Authenticate": f'Bearer realm="mcp", resource_metadata="{config.mcp.SERVER_URL}/.well-known/oauth-protected-resource"'
            },
        )

    # Parse bearer token
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning(
            f"⚠️ [MCP Auth] Invalid Authorization header format: {auth_header}"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Verify token
    return await verify_bearer_token(token)


def get_protected_resource_metadata() -> dict[str, Any]:
    """
    Get Protected Resource Metadata (PRM) document per RFC 9728.

    This document tells MCP clients:
    - What authorization servers to use
    - What scopes are supported
    - Where to find more documentation
    """
    return {
        "resource": config.mcp.SERVER_URL,
        "authorization_servers": [config.mcp.HYDRA_PUBLIC_URL],
        "scopes_supported": config.mcp.SCOPES_SUPPORTED,
        "bearer_methods_supported": ["header"],
        "resource_signing_alg_values_supported": ["RS256"],
        "resource_documentation": config.mcp.RESOURCE_DOCUMENTATION_URL,
    }


def create_unauthorized_response(request: Request) -> JSONResponse:
    """
    Create a 401 Unauthorized response with proper WWW-Authenticate header.

    This tells MCP clients where to find authorization information.
    """
    prm_url = f"{config.mcp.SERVER_URL}/.well-known/oauth-protected-resource"

    return JSONResponse(
        status_code=401,
        content={
            "error": "unauthorized",
            "error_description": "Valid OAuth 2.0 access token required",
        },
        headers={
            "WWW-Authenticate": f'Bearer realm="mcp", resource_metadata="{prm_url}"'
        },
    )
