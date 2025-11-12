"""
Invitation Management Routes

This module handles invitation creation, acceptance, and management for the
selfmemory project. Supports both organization-level and project-level invitations.

Clean Code Principles:
- No fallback mechanisms (fails explicitly)
- No mock data
- Clear function names and comprehensive error handling
"""

import logging
import os
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..config import config
from ..dependencies import AuthContext, authenticate_api_key, mongo_db
from ..utils.datetime_helpers import is_expired
from ..utils.rate_limiter import limiter
from .invitation_helpers import (
    add_user_to_organization,
    add_user_to_projects_from_invitation,
    get_invitation_response_details,
    mark_invitation_accepted,
    validate_invitation_for_acceptance,
)

router = APIRouter(prefix="/api/invitations", tags=["invitations"])

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================


class InvitationResponse(BaseModel):
    """Response model for invitation details"""

    invitation_id: str
    token: str
    email: str
    organization_id: str
    organization_name: str
    project_id: str | None = None
    project_name: str | None = None
    role: str
    invited_by_email: str
    status: str
    expires_at: str
    created_at: str


class AcceptInvitationRequest(BaseModel):
    """Request model for accepting an invitation"""

    # No fields needed - token is in URL, user info from auth


# ============================================================================
# Helper Functions
# ============================================================================


def generate_invitation_token() -> str:
    """
    Generate a secure random token for invitation links.

    Returns:
        str: A URL-safe random token (32 bytes = 256 bits)
    """
    return secrets.token_urlsafe(32)


def get_invitation_by_token(token: str) -> dict | None:
    """
    Retrieve invitation by token.

    Args:
        token: The invitation token

    Returns:
        dict: The invitation document or None if not found
    """
    return mongo_db.invitations.find_one({"token": token})


def is_invitation_expired(invitation: dict) -> bool:
    """
    Check if an invitation has expired.

    Args:
        invitation: The invitation document

    Returns:
        bool: True if expired, False otherwise
    """
    expires_at = invitation.get("expiresAt")
    if not expires_at:
        return False
    return is_expired(expires_at)


def send_invitation_email(
    email: str,
    organization_name: str,
    project_name: str | None,
    role: str,
    invited_by_email: str,
    invitation_token: str,
) -> None:
    """
    Send invitation email to the user via SMTP.

    Reads SMTP configuration from environment variables:
    - SMTP_HOST: SMTP server hostname
    - SMTP_PORT: SMTP server port
    - SMTP_USERNAME: SMTP username
    - SMTP_PASSWORD: SMTP password
    - SMTP_FROM_EMAIL: From email address
    - SMTP_FROM_NAME: From name
    - SMTP_USE_TLS: Whether to use TLS
    - FRONTEND_URL: Frontend URL for invitation links

    If SMTP is not configured, logs invitation details instead.

    Args:
        email: Recipient email address
        organization_name: Name of the organization
        project_name: Name of the project (if project-specific invite)
        role: Role being offered
        invited_by_email: Email of the person who sent the invite
        invitation_token: Token for the invitation link
    """
    # Get SMTP configuration from environment
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@selfmemory.com")
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "SelfMemory")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    invitation_link = f"{frontend_url}/accept-invitation/{invitation_token}"

    # If SMTP is not configured, log instead
    if not smtp_host or not smtp_username or not smtp_password:
        logger.info(
            f"📧 INVITATION EMAIL (SMTP not configured - logging only):\n"
            f"  To: {email}\n"
            f"  From: {invited_by_email}\n"
            f"  Organization: {organization_name}\n"
            f"  Project: {project_name or 'N/A'}\n"
            f"  Role: {role}\n"
            f"  Link: {invitation_link}\n"
        )
        return

    # Create email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Invitation to join {organization_name}"
    msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
    msg["To"] = email

    # Create plain text version
    text_body = f"""
Hello,

{invited_by_email} has invited you to join {organization_name}{f" - {project_name}" if project_name else ""} as a {role}.

Click the link below to accept the invitation:
{invitation_link}

This invitation will expire in 24 hours.

Best regards,
The SelfMemory Team
"""

    # Create HTML version
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9fafb; padding: 30px; }}
        .button {{ background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 20px 0; }}
        .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>You've Been Invited!</h1>
        </div>
        <div class="content">
            <p>Hello,</p>
            <p><strong>{invited_by_email}</strong> has invited you to join:</p>
            <ul>
                <li><strong>Organization:</strong> {organization_name}</li>
                {f"<li><strong>Project:</strong> {project_name}</li>" if project_name else ""}
                <li><strong>Role:</strong> {role}</li>
            </ul>
            <p>Click the button below to accept the invitation:</p>
            <a href="{invitation_link}" class="button">Accept Invitation</a>
            <p style="color: #6b7280; font-size: 14px;">
                This invitation will expire in 24 hours.
            </p>
        </div>
        <div class="footer">
            <p>This is an automated message from SelfMemory.</p>
        </div>
    </div>
</body>
</html>
"""

    # Attach both versions
    part1 = MIMEText(text_body, "plain")
    part2 = MIMEText(html_body, "html")
    msg.attach(part1)
    msg.attach(part2)

    # Connect to SMTP server and send email
    # Port 465 uses SSL, port 587 uses STARTTLS
    # Timeout set to 10 seconds to fail fast if SMTP unreachable
    if smtp_port == 465:
        # Use SMTP_SSL for port 465
        with smtplib.SMTP_SSL(
            smtp_host, smtp_port, timeout=config.email.SMTP_TIMEOUT
        ) as server:
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
    else:
        # Use SMTP with STARTTLS for port 587
        with smtplib.SMTP(
            smtp_host, smtp_port, timeout=config.email.SMTP_TIMEOUT
        ) as server:
            if smtp_use_tls:
                server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)

    logger.info(f"✅ Invitation email sent to {email}")


# ============================================================================
# Public Endpoints (No Authentication Required)
# ============================================================================


@router.get("/{token}", response_model=InvitationResponse)
def get_invitation_details(token: str):
    """
    Get invitation details by token (PUBLIC endpoint - no auth required).

    This endpoint allows anyone with the invitation link to view the details
    before deciding whether to accept.

    Scenarios:
    - Valid token, pending invitation → Return invitation details
    - Expired invitation → Return 410 Gone
    - Already accepted invitation → Return 410 Gone
    - Invalid token → Return 404 Not Found
    """
    # Look up invitation by token
    invitation = get_invitation_by_token(token)

    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    # Check if already accepted
    if invitation["status"] == "accepted":
        raise HTTPException(
            status_code=410,
            detail="This invitation has already been accepted",
        )

    # Check if expired
    if is_invitation_expired(invitation):
        # Mark as expired
        mongo_db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "expired"}},
        )
        raise HTTPException(
            status_code=410,
            detail="This invitation has expired",
        )

    # Get organization details
    organization = mongo_db.organizations.find_one(
        {"_id": invitation["organizationId"]}
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Get project details if project-specific invitation
    project_name = None
    if invitation.get("projectId"):
        project = mongo_db.projects.find_one({"_id": invitation["projectId"]})
        if project:
            project_name = project["name"]

    # Get inviter details
    inviter = mongo_db.users.find_one({"_id": invitation["invitedBy"]})
    inviter_email = inviter["email"] if inviter else "Unknown"

    logger.info(f"✅ Retrieved invitation details for token: {token[:10]}...")

    return InvitationResponse(
        invitation_id=str(invitation["_id"]),
        token=invitation["token"],
        email=invitation["email"],
        organization_id=str(invitation["organizationId"]),
        organization_name=organization["name"],
        project_id=str(invitation["projectId"])
        if invitation.get("projectId")
        else None,
        project_name=project_name,
        role=invitation["role"],
        invited_by_email=inviter_email,
        status=invitation["status"],
        expires_at=invitation["expiresAt"].isoformat(),
        created_at=invitation["createdAt"].isoformat(),
    )


# ============================================================================
# Authenticated Endpoints
# ============================================================================


@router.post("/{token}/accept")
@limiter.limit(config.rate_limit.INVITATION_ACCEPT)
def accept_invitation(
    request: Request,
    token: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Accept an invitation (authenticated endpoint).

    Rate limited to prevent abuse (3 requests per minute).

    Scenarios:
    - User accepts pending invitation → Add to org/project, mark as accepted
    - User's email doesn't match invitation → Return 403 Forbidden
    - Invitation expired → Return 410 Gone
    - Invitation already accepted → Return 410 Gone
    - Invalid token → Return 404 Not Found
    """
    # Look up invitation by token
    invitation = get_invitation_by_token(token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    # auth.user_id is Kratos identity_id (UUID string)
    # Look up MongoDB user document to get ObjectId for internal references
    user = mongo_db.users.find_one({
        "$or": [
            {"kratosId": auth.user_id},
            {"_id": auth.user_id}
        ]
    })
    if not user:
        logger.error(f"User not found: {auth.user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    user_obj_id = user["_id"]

    # Validate invitation (checks expiry, status, email match)
    validate_invitation_for_acceptance(invitation, user.get("email"))

    # Add user to organization
    add_user_to_organization(user_obj_id, invitation)

    # Add user to projects (handles both single project and multi-project invitations)
    projects_added = add_user_to_projects_from_invitation(user_obj_id, invitation)

    # Mark invitation as accepted
    mark_invitation_accepted(invitation["_id"])

    # Get response details
    response_details = get_invitation_response_details(invitation)

    logger.info(
        f"✅ Invitation accepted by user {auth.user_id}, "
        f"added to {len(projects_added)} projects"
    )

    return {
        "message": "Invitation accepted successfully",
        **response_details,
        "projects_added": len(projects_added),
    }


@router.get("/pending", response_model=list[InvitationResponse])
def list_pending_invitations(auth: AuthContext = Depends(authenticate_api_key)):
    """
    List pending invitations for the authenticated user.

    Returns all invitations sent to the user's email that haven't been
    accepted yet and haven't expired.
    """
    # auth.user_id is Kratos identity_id (UUID string)
    # Look up MongoDB user document to get ObjectId for internal references
    user = mongo_db.users.find_one({
        "$or": [
            {"kratosId": auth.user_id},
            {"_id": auth.user_id}
        ]
    })
    if not user:
        logger.error(f"User not found: {auth.user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    user_email = user.get("email")

    if not user_email:
        return []

    # Find all pending invitations for this email
    invitations = list(
        mongo_db.invitations.find(
            {
                "email": user_email,
                "status": "pending",
            }
        )
    )

    # Filter out expired invitations and mark them
    valid_invitations = []
    for invitation in invitations:
        if is_invitation_expired(invitation):
            # Mark as expired
            mongo_db.invitations.update_one(
                {"_id": invitation["_id"]},
                {"$set": {"status": "expired"}},
            )
            continue

        # Get organization details
        organization = mongo_db.organizations.find_one(
            {"_id": invitation["organizationId"]}
        )
        if not organization:
            continue

        # Get project details if project-specific invitation
        project_name = None
        if invitation.get("projectId"):
            project = mongo_db.projects.find_one({"_id": invitation["projectId"]})
            if project:
                project_name = project["name"]

        # Get inviter details
        inviter = mongo_db.users.find_one({"_id": invitation["invitedBy"]})
        inviter_email = inviter["email"] if inviter else "Unknown"

        valid_invitations.append(
            InvitationResponse(
                invitation_id=str(invitation["_id"]),
                token=invitation["token"],
                email=invitation["email"],
                organization_id=str(invitation["organizationId"]),
                organization_name=organization["name"],
                project_id=str(invitation["projectId"])
                if invitation.get("projectId")
                else None,
                project_name=project_name,
                role=invitation["role"],
                invited_by_email=inviter_email,
                status=invitation["status"],
                expires_at=invitation["expiresAt"].isoformat(),
                created_at=invitation["createdAt"].isoformat(),
            )
        )

    logger.info(
        f"✅ Retrieved {len(valid_invitations)} pending invitations for user {auth.user_id}"
    )

    return valid_invitations
