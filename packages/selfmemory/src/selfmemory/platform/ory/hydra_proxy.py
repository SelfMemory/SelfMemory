"""
Hydra Admin API Proxy Routes.

This module provides secure proxy endpoints for dashboard to access Hydra admin API.
Hydra admin API is kept localhost-only (not exposed to internet) for security.
Dashboard (Vercel) calls these backend proxy routes instead of Hydra directly.

Security:
- Consent routes require Ory Kratos session authentication (user already logged in)
- Login accept requires a Kratos session; the subject is the session's user
- Consent accept builds token claims and scopes server-side, never from the body
"""

import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from selfmemory.kernel.validators import validate_object_id
from selfmemory.platform.dependencies import (
    AuthContext,
    authenticate_api_key,
    check_project_access,
    mongo_db,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/hydra", tags=["Hydra Admin Proxy"])

# Hydra admin URL (localhost only - not internet accessible)
HYDRA_ADMIN_URL = os.getenv("HYDRA_ADMIN_URL", "http://localhost:4445")

# Hydra public URL (for proxying OAuth flows)
HYDRA_PUBLIC_URL = os.getenv("HYDRA_PUBLIC_URL", "https://auth.selfmemory.com")


class ConsentAcceptRequest(BaseModel):
    """Request body for accepting consent."""

    consent_challenge: str = Field(..., description="Consent challenge from Hydra")
    grant_scope: list[str] = Field(..., description="Scopes to grant")
    grant_access_token_audience: list[str] = Field(
        default_factory=list, description="Token audience"
    )
    project_id: str | None = Field(
        default=None, description="Project to pin the token to (access is checked)"
    )
    session: dict | None = Field(
        default=None,
        description="Deprecated: only access_token.project_id is read, then checked",
    )
    remember: bool = Field(default=True, description="Remember consent decision")
    remember_for: int = Field(default=3600, description="Remember duration in seconds")


class ConsentRejectRequest(BaseModel):
    """Request body for rejecting consent."""

    consent_challenge: str = Field(..., description="Consent challenge from Hydra")
    error: str = Field(default="access_denied", description="OAuth error code")
    error_description: str = Field(
        default="User denied access", description="Error description"
    )


class LoginAcceptRequest(BaseModel):
    """Request body for accepting login."""

    login_challenge: str = Field(..., description="Login challenge from Hydra")
    remember: bool = Field(default=True, description="Remember login decision")
    remember_for: int = Field(default=3600, description="Remember duration in seconds")


class LoginRejectRequest(BaseModel):
    """Request body for rejecting login."""

    login_challenge: str = Field(..., description="Login challenge from Hydra")
    error: str = Field(default="access_denied", description="OAuth error code")
    error_description: str = Field(
        default="User denied login", description="Error description"
    )


# Scope descriptions for user-friendly consent screen
SCOPE_DESCRIPTIONS = {
    "openid": {
        "name": "OpenID Connect",
        "description": "Allows the application to verify your identity",
    },
    "offline": {
        "name": "Offline Access",
        "description": "Allows the application to maintain access when you're not actively using it",
    },
    "offline_access": {
        "name": "Offline Access",
        "description": "Allows the application to maintain access when you're not actively using it",
    },
    "memories:read": {
        "name": "Read your AI memories",
        "description": "Allows the application to search and retrieve your stored memories and conversations",
    },
    "memories:write": {
        "name": "Store new AI memories",
        "description": "Allows the application to save new memories and conversations on your behalf",
    },
    "mcp.read": {
        "name": "MCP Read Access",
        "description": "Allows the application to read MCP server information",
    },
    "mcp.write": {
        "name": "MCP Write Access",
        "description": "Allows the application to write MCP server information",
    },
}


def enrich_scope_metadata(scopes: list[str]) -> list[dict]:
    """
    Enrich raw scope strings with user-friendly names and descriptions.

    This ensures the consent screen always shows meaningful information,
    even for custom scopes that Hydra doesn't know about.

    Args:
        scopes: List of raw scope strings (e.g., ["memories:read", "openid"])

    Returns:
        List of scope objects with name, description, and id fields
    """
    enriched = []

    for scope in scopes:
        if scope in SCOPE_DESCRIPTIONS:
            # Use predefined description
            enriched.append(
                {
                    "id": scope,
                    "name": SCOPE_DESCRIPTIONS[scope]["name"],
                    "description": SCOPE_DESCRIPTIONS[scope]["description"],
                }
            )
        else:
            # Generate fallback description for unknown scopes
            # Convert "my:scope" to "My Scope"
            name = scope.replace(":", " ").replace("_", " ").title()
            enriched.append(
                {
                    "id": scope,
                    "name": name,
                    "description": f"Allows the application to access {name.lower()}",
                }
            )

    return enriched


REQUIRED_MEMORY_SCOPES = ["memories:read", "memories:write"]


async def _allowed_scopes(client: httpx.AsyncClient, consent_data: dict) -> list[str]:
    """Scopes the user may grant: those requested, else the client's registered
    ones, plus the memory scopes MCP tools need."""
    scopes = list(consent_data.get("requested_scope") or [])
    if not scopes:
        client_id = consent_data.get("client", {}).get("client_id")
        try:
            resp = await client.get(
                f"{HYDRA_ADMIN_URL}/admin/clients/{client_id}", timeout=10.0
            )
            if resp.status_code == 200:
                scopes = (resp.json().get("scope") or "").split()
            else:
                logger.error(f"Failed to fetch client details: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching client scopes: {e}")
    for scope in REQUIRED_MEMORY_SCOPES:
        if scope not in scopes:
            scopes.append(scope)
    return scopes


async def _fetch_consent_request(
    client: httpx.AsyncClient, consent_challenge: str
) -> dict:
    response = await client.get(
        f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/consent",
        params={"consent_challenge": consent_challenge},
        timeout=10.0,
    )
    if response.status_code != 200:
        logger.error(
            f"Hydra consent request failed: status={response.status_code}, "
            f"body={response.text}"
        )
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to fetch consent request: {response.text}",
        )
    return response.json()


def _build_session_claims(user_id: str, project_id: str | None) -> dict:
    """Token claims, derived from what the server can verify about the user."""
    claims: dict = {}
    if project_id:
        if not check_project_access(user_id, project_id):
            raise HTTPException(
                status_code=403, detail="You do not have access to this project"
            )
        project = mongo_db.projects.find_one(
            {"_id": validate_object_id(project_id, "project_id")}
        )
        claims["project_id"] = project_id
        if project and project.get("organizationId"):
            claims["organization_id"] = str(project["organizationId"])
    return {"access_token": dict(claims), "id_token": dict(claims)}


@router.get("/consent/request", summary="Get consent request details")
async def get_consent_request(
    consent_challenge: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Get consent request details from Hydra admin API.

    This endpoint proxies the Hydra admin API call securely.
    Only authenticated users can access this endpoint.

    Enhances the response with user-friendly scope descriptions.
    IMPORTANT: Falls back to client's registered scopes if requested_scope is empty.

    Args:
        consent_challenge: The consent challenge from Hydra OAuth flow

    Returns:
        Consent request details including client info and enriched scope metadata
    """
    try:
        logger.info(
            f"Fetching consent request: challenge={consent_challenge}, user={auth.user_id}"
        )

        async with httpx.AsyncClient() as client:
            consent_data = await _fetch_consent_request(client, consent_challenge)

            original = list(consent_data.get("requested_scope") or [])
            requested_scopes = await _allowed_scopes(client, consent_data)
            if not original:
                consent_data["scope_fallback_used"] = True
            consent_data["requested_scope"] = requested_scopes

            # Enrich scope metadata with descriptions
            consent_data["scope_metadata"] = enrich_scope_metadata(requested_scopes)

            logger.info(
                f"✅ Consent request fetched: client={consent_data.get('client', {}).get('client_id')}, "
                f"scopes={requested_scopes}, enriched={len(consent_data['scope_metadata'])} scopes"
            )

            return consent_data

    except httpx.TimeoutException:
        logger.error("Hydra admin API timeout")
        raise HTTPException(status_code=504, detail="Hydra admin API timeout") from None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching consent request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.put("/consent/accept", summary="Accept consent request")
async def accept_consent_request(
    body: ConsentAcceptRequest,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Accept OAuth consent request via Hydra admin API.

    This endpoint proxies the consent accept call to Hydra admin API securely.
    Only authenticated users can accept consent for their own account.

    Args:
        body: Consent accept request with scopes and session data

    Returns:
        Redirect URL to continue OAuth flow
    """
    try:
        logger.info(
            f"Accepting consent: challenge={body.consent_challenge}, "
            f"user={auth.user_id}, scopes={body.grant_scope}"
        )

        # DIAGNOSTIC: Log audience being granted
        logger.info("🔍 CONSENT AUDIENCE:")
        logger.info(f"   Requested audience: {body.grant_access_token_audience}")

        # FIX: Always include the correct MCP server URL as audience
        # This ensures tokens are always issued for the right resource server
        mcp_server_url = os.getenv("MCP_SERVER_URL", "https://mcp.selfmemory.com")

        # Combine requested audiences with the required MCP server URL
        audiences = (
            list(body.grant_access_token_audience)
            if body.grant_access_token_audience
            else []
        )

        # Remove any local development URLs that might have been requested
        audiences = [
            aud
            for aud in audiences
            if not aud.startswith(("http://127.0.0.1", "http://localhost"))
        ]

        # Add the correct MCP server URL if not already present
        if mcp_server_url not in audiences:
            audiences.append(mcp_server_url)

        logger.info(f"   MCP_SERVER_URL from env: {mcp_server_url}")
        logger.info(f"   ✅ Corrected audience: {audiences}")

        # CRITICAL: follow_redirects=False — Hydra returns a redirect_to URL with a
        # one-time consent_verifier. If httpx follows the redirect, it consumes the
        # verifier server-side, and the browser can't use it ("verifier already used").
        async with httpx.AsyncClient(follow_redirects=False) as client:
            consent_data = await _fetch_consent_request(client, body.consent_challenge)
            if consent_data.get("subject") != auth.user_id:
                logger.warning(
                    f"Consent subject mismatch: challenge={body.consent_challenge}, "
                    f"user={auth.user_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Consent request does not belong to this user",
                )

            allowed = await _allowed_scopes(client, consent_data)
            grant_scope = [s for s in body.grant_scope if s in allowed]

            project_id = body.project_id
            if project_id is None and isinstance(body.session, dict):
                legacy = body.session.get("access_token") or {}
                if isinstance(legacy, dict):
                    project_id = legacy.get("project_id")

            accept_payload = {
                "grant_scope": grant_scope,
                "grant_access_token_audience": audiences,
                "session": _build_session_claims(auth.user_id, project_id),
                "remember": body.remember,
                "remember_for": body.remember_for,
            }

            response = await client.put(
                f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/consent/accept",
                params={"consent_challenge": body.consent_challenge},
                json=accept_payload,
                timeout=10.0,
            )

            if response.status_code != 200:
                logger.error(
                    f"Hydra consent accept failed: status={response.status_code}, "
                    f"body={response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to accept consent: {response.text}",
                )

            result = response.json()

            logger.info(
                f"✅ Consent accepted: redirect_to={result.get('redirect_to')}, "
                f"user={auth.user_id}"
            )

            return result

    except httpx.TimeoutException:
        logger.error("Hydra admin API timeout")
        raise HTTPException(status_code=504, detail="Hydra admin API timeout") from None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting consent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.put("/consent/reject", summary="Reject consent request")
async def reject_consent_request(
    body: ConsentRejectRequest,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Reject OAuth consent request via Hydra admin API.

    This endpoint proxies the consent reject call to Hydra admin API securely.

    Args:
        body: Consent reject request with error details

    Returns:
        Redirect URL to continue OAuth flow
    """
    try:
        logger.info(
            f"Rejecting consent: challenge={body.consent_challenge}, "
            f"user={auth.user_id}, reason={body.error}"
        )

        # Build consent reject payload
        reject_payload = {
            "error": body.error,
            "error_description": body.error_description,
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/consent/reject",
                params={"consent_challenge": body.consent_challenge},
                json=reject_payload,
                timeout=10.0,
            )

            if response.status_code != 200:
                logger.error(
                    f"Hydra consent reject failed: status={response.status_code}, "
                    f"body={response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to reject consent: {response.text}",
                )

            result = response.json()

            logger.info(
                f"✅ Consent rejected: redirect_to={result.get('redirect_to')}, "
                f"user={auth.user_id}"
            )

            return result

    except httpx.TimeoutException:
        logger.error("Hydra admin API timeout")
        raise HTTPException(status_code=504, detail="Hydra admin API timeout") from None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting consent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/login/request", summary="Get login request details")
async def get_login_request(
    login_challenge: str,
):
    """
    Get login request details from Hydra admin API.

    This endpoint proxies the Hydra admin API call securely.
    No authentication required - user is in the process of logging in.
    The login_challenge itself acts as a secure token.

    Args:
        login_challenge: The login challenge from Hydra OAuth flow

    Returns:
        Login request details including client info, skip flag, and subject
    """
    try:
        logger.info(f"Fetching login request: challenge={login_challenge}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/login",
                params={"login_challenge": login_challenge},
                timeout=10.0,
            )

            if response.status_code != 200:
                logger.error(
                    f"Hydra login request failed: status={response.status_code}, "
                    f"body={response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch login request: {response.text}",
                )

            login_data = response.json()

            logger.info(
                f"✅ Login request fetched: client={login_data.get('client', {}).get('client_id')}, "
                f"skip={login_data.get('skip', False)}, subject={login_data.get('subject', 'N/A')}"
            )

            return login_data

    except httpx.TimeoutException:
        logger.error("Hydra admin API timeout")
        raise HTTPException(status_code=504, detail="Hydra admin API timeout") from None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching login request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.put("/login/accept", summary="Accept login request")
async def accept_login_request(
    body: LoginAcceptRequest,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Accept OAuth login request via Hydra admin API.

    This endpoint proxies the login accept call to Hydra admin API securely.
    Requires a Kratos session; the subject is always the session's user.

    Args:
        body: Login accept request with remember settings

    Returns:
        Redirect URL to continue OAuth flow (usually to consent page)
    """
    if auth.auth_type != "session":
        raise HTTPException(
            status_code=403, detail="Login must be accepted with a browser session"
        )
    subject = auth.user_id
    try:
        logger.info(
            f"Accepting login: challenge={body.login_challenge}, subject={subject}"
        )

        # Build login accept payload
        accept_payload = {
            "subject": subject,
            "remember": body.remember,
            "remember_for": body.remember_for,
            "context": {
                "login_time": __import__("datetime").datetime.utcnow().isoformat(),
            },
        }

        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.put(
                f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/login/accept",
                params={"login_challenge": body.login_challenge},
                json=accept_payload,
                timeout=10.0,
            )

            if response.status_code != 200:
                logger.error(
                    f"Hydra login accept failed: status={response.status_code}, "
                    f"body={response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to accept login: {response.text}",
                )

            result = response.json()

            logger.info(
                f"✅ Login accepted: redirect_to={result.get('redirect_to')}, "
                f"subject={subject}"
            )

            return result

    except httpx.TimeoutException:
        logger.error("Hydra admin API timeout")
        raise HTTPException(status_code=504, detail="Hydra admin API timeout") from None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting login: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.put("/login/reject", summary="Reject login request")
async def reject_login_request(
    body: LoginRejectRequest,
):
    """
    Reject OAuth login request via Hydra admin API.

    This endpoint proxies the login reject call to Hydra admin API securely.
    No authentication required - user rejected the login.
    The login_challenge itself acts as a secure token.

    Args:
        body: Login reject request with error details

    Returns:
        Redirect URL to continue OAuth flow
    """
    try:
        logger.info(
            f"Rejecting login: challenge={body.login_challenge}, reason={body.error}"
        )

        # Build login reject payload
        reject_payload = {
            "error": body.error,
            "error_description": body.error_description,
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/login/reject",
                params={"login_challenge": body.login_challenge},
                json=reject_payload,
                timeout=10.0,
            )

            if response.status_code != 200:
                logger.error(
                    f"Hydra login reject failed: status={response.status_code}, "
                    f"body={response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to reject login: {response.text}",
                )

            result = response.json()

            logger.info(f"✅ Login rejected: redirect_to={result.get('redirect_to')}")

            return result

    except httpx.TimeoutException:
        logger.error("Hydra admin API timeout")
        raise HTTPException(status_code=504, detail="Hydra admin API timeout") from None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting login: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None
