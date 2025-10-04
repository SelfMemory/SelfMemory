"""
Invitation Helper Functions

Helper functions for invitation acceptance following Uncle Bob's Clean Code principles:
- Small, focused functions (each does one thing)
- Clear, descriptive names
- No side effects hidden in functions
- Explicit error handling
"""

import logging

from bson import ObjectId
from fastapi import HTTPException

from ..database import get_role_permissions
from ..dependencies import mongo_db
from ..utils.database_utils import safe_insert_member
from ..utils.datetime_helpers import utc_now
from ..utils.validators import validate_object_id

logger = logging.getLogger(__name__)


def validate_invitation_for_acceptance(invitation: dict, user_email: str) -> None:
    """
    Validate that an invitation can be accepted by the current user.

    Checks:
    - Invitation not already accepted
    - Invitation not expired
    - User email matches invitation email

    Args:
        invitation: The invitation document
        user_email: The authenticated user's email

    Raises:
        HTTPException: If validation fails
    """
    # Check if already accepted
    if invitation["status"] == "accepted":
        raise HTTPException(
            status_code=410,
            detail="This invitation has already been accepted",
        )

    # Check if expired (will be marked as expired in the calling function)
    from ..utils.datetime_helpers import is_expired

    if is_expired(invitation.get("expiresAt")):
        # Mark as expired
        mongo_db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "expired"}},
        )
        raise HTTPException(
            status_code=410,
            detail="This invitation has expired",
        )

    # Verify email matches invitation
    if user_email != invitation["email"]:
        logger.warning(
            f"❌ Email mismatch: user {user_email} tried to accept "
            f"invitation for {invitation['email']}"
        )
        raise HTTPException(
            status_code=403,
            detail="This invitation was sent to a different email address",
        )


def add_user_to_organization(
    user_id: ObjectId, invitation: dict
) -> tuple[str | None, bool]:
    """
    Add user to organization from invitation.

    Args:
        user_id: The user's ObjectId
        invitation: The invitation document

    Returns:
        tuple: (member_id, already_existed)
    """
    org_member_doc = {
        "organizationId": invitation["organizationId"],
        "userId": user_id,
        "role": invitation["role"],
        "invitedBy": invitation["invitedBy"],
        "joinedAt": utc_now(),
        "status": "active",
    }

    member_id, existed = safe_insert_member(
        mongo_db.organization_members,
        org_member_doc,
        "organization_member",
    )

    if member_id:
        logger.info(
            f"✅ Added user {user_id} to organization {invitation['organizationId']}"
        )
    else:
        logger.info(
            f"ℹ️ User {user_id} already member of organization {invitation['organizationId']}"
        )

    return member_id, existed


def add_user_to_single_project(
    user_id: ObjectId,
    project_id: ObjectId,
    organization_id: ObjectId,
    role: str,
    invited_by: ObjectId,
) -> tuple[str | None, bool]:
    """
    Add user to a single project.

    Checks if user is project owner first - owners don't need project_members entry.

    Args:
        user_id: The user's ObjectId
        project_id: The project's ObjectId
        organization_id: The organization's ObjectId
        role: The role to assign
        invited_by: ObjectId of the inviter

    Returns:
        tuple: (member_id, already_existed) or (None, True) if owner
    """
    # Check if user is the project owner
    project = mongo_db.projects.find_one({"_id": project_id})
    is_owner = project and str(project["ownerId"]) == str(user_id)

    if is_owner:
        logger.info(
            f"ℹ️ User {user_id} is already owner of project {project_id}, "
            "skipping project_members entry"
        )
        return None, True

    # Get permissions for the role
    permissions = get_role_permissions(role)

    # Add user to project
    project_member_doc = {
        "projectId": project_id,
        "userId": user_id,
        "organizationId": organization_id,
        "role": role,
        "permissions": permissions,
        "addedBy": invited_by,
        "addedAt": utc_now(),
    }

    member_id, existed = safe_insert_member(
        mongo_db.project_members, project_member_doc, "project_member"
    )

    if member_id:
        logger.info(f"✅ Added user {user_id} to project {project_id} with role {role}")
    else:
        logger.info(f"ℹ️ User {user_id} already member of project {project_id}")

    return member_id, existed


def add_user_to_projects_from_invitation(
    user_id: ObjectId, invitation: dict
) -> list[str]:
    """
    Add user to all projects specified in the invitation.

    Handles both:
    - Legacy project-specific invitations (single projectId field)
    - New multi-project assignments (projectAssignments array)

    Args:
        user_id: The user's ObjectId
        invitation: The invitation document

    Returns:
        list: Project IDs that were successfully added
    """
    projects_added = []

    # Handle legacy project-specific invitation (single projectId)
    if invitation.get("projectId"):
        member_id, existed = add_user_to_single_project(
            user_id=user_id,
            project_id=invitation["projectId"],
            organization_id=invitation["organizationId"],
            role=invitation["role"],
            invited_by=invitation["invitedBy"],
        )

        if member_id:
            projects_added.append(str(invitation["projectId"]))

    # Handle multi-project assignments (new org-level invitations)
    project_assignments = invitation.get("projectAssignments", [])
    for assignment in project_assignments:
        project_id_obj = validate_object_id(assignment["projectId"], "project_id")
        project_role = assignment["role"]

        member_id, existed = add_user_to_single_project(
            user_id=user_id,
            project_id=project_id_obj,
            organization_id=invitation["organizationId"],
            role=project_role,
            invited_by=invitation["invitedBy"],
        )

        if member_id:
            projects_added.append(assignment["projectId"])

    return projects_added


def mark_invitation_accepted(invitation_id: ObjectId) -> None:
    """
    Mark an invitation as accepted.

    Args:
        invitation_id: The invitation's ObjectId
    """
    mongo_db.invitations.update_one(
        {"_id": invitation_id}, {"$set": {"status": "accepted"}}
    )


def get_invitation_response_details(invitation: dict) -> dict:
    """
    Get organization and project details for invitation acceptance response.

    Args:
        invitation: The invitation document

    Returns:
        dict: Response details with organization and project info
    """
    # Get organization details
    organization = mongo_db.organizations.find_one(
        {"_id": invitation["organizationId"]}
    )

    # Get project details if single project invitation
    project = None
    if invitation.get("projectId"):
        project = mongo_db.projects.find_one({"_id": invitation["projectId"]})

    return {
        "organization_id": str(invitation["organizationId"]),
        "organization_name": organization["name"] if organization else None,
        "project_id": str(invitation["projectId"])
        if invitation.get("projectId")
        else None,
        "project_name": project["name"] if project else None,
        "role": invitation["role"],
    }
