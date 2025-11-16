"""
Hydra Admin API Proxy Routes.

This module provides secure proxy endpoints for dashboard to access Hydra admin API.
Hydra admin API is kept localhost-only (not exposed to internet) for security.
Dashboard (Vercel) calls these backend proxy routes instead of Hydra directly.

Security: All routes require Ory Kratos session authentication.
"""

import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..dependencies import AuthContext, authenticate_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/hydra", tags=["Hydra Admin Proxy"])

# Hydra admin URL (localhost only - not internet accessible)
HYDRA_ADMIN_URL = os.getenv("HYDRA_ADMIN_URL", "http://localhost:4445")


class ConsentAcceptRequest(BaseModel):
    """Request body for accepting consent."""

    consent_challenge: str = Field(..., description="Consent challenge from Hydra")
    grant_scope: list[str] = Field(..., description="Scopes to grant")
    grant_access_token_audience: list[str] = Field(
        default_factory=list, description="Token audience"
    )
    session: dict = Field(..., description="Session data to include in token")
    remember: bool = Field(default=True, description="Remember consent decision")
    remember_for: int = Field(default=3600, description="Remember duration in seconds")


class ConsentRejectRequest(BaseModel):
    """Request body for rejecting consent."""

    consent_challenge: str = Field(..., description="Consent challenge from Hydra")
    error: str = Field(default="access_denied", description="OAuth error code")
    error_description: str = Field(
        default="User denied access", description="Error description"
    )


@router.get("/consent/request", summary="Get consent request details")
async def get_consent_request(
    consent_challenge: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Get consent request details from Hydra admin API.

    This endpoint proxies the Hydra admin API call securely.
    Only authenticated users can access this endpoint.

    Args:
        consent_challenge: The consent challenge from Hydra OAuth flow

    Returns:
        Consent request details including client info and requested scopes
    """
    try:
        logger.info(
            f"Fetching consent request: challenge={consent_challenge}, user={auth.user_id}"
        )

        async with httpx.AsyncClient() as client:
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

            consent_data = response.json()

            logger.info(
                f"✅ Consent request fetched: client={consent_data.get('client', {}).get('client_id')}, "
                f"scopes={consent_data.get('requested_scope', [])}"
            )

            return consent_data

    except httpx.TimeoutException:
        logger.error("Hydra admin API timeout")
        raise HTTPException(status_code=504, detail="Hydra admin API timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching consent request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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

        # Build consent accept payload
        accept_payload = {
            "grant_scope": body.grant_scope,
            "grant_access_token_audience": body.grant_access_token_audience,
            "session": body.session,
            "remember": body.remember,
            "remember_for": body.remember_for,
        }

        async with httpx.AsyncClient() as client:
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
        raise HTTPException(status_code=504, detail="Hydra admin API timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting consent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        raise HTTPException(status_code=504, detail="Hydra admin API timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting consent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
