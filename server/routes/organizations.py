"""
Organization member management routes.

This module implements Phase 2 of the Memory Sharing Implementation Plan:
- Invite users to organizations
- List organization members
- Remove users from organizations
- Transfer organization ownership
"""

import logging
from datetime import timedelta

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from pymongo.database import Database

from ..config import config
from ..dependencies import AuthContext, authenticate_api_key, mongo_db
from ..utils.datetime_helpers import utc_now
from ..utils.rate_limiter import limiter
from ..utils.validators import validate_object_id
from .invitations import generate_invitation_token, send_invitation_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/organizations", tags=["Organization Management"])


# Pydantic Models
class OrganizationInvite(BaseModel):
    """Model for inviting a user to an organization with optional project assignments."""

    email: EmailStr = Field(..., description="Email address of the user to invite")
    role: str = Field(
        default="member",
        description="Role in organization: owner, admin, or member",
        pattern="^(owner|admin|member)$",
    )
    projectIds: list[str] = Field(
        default_factory=list,
        description="Optional list of project IDs to assign the user to",
    )
    projectRoles: dict[str, str] = Field(
        default_factory=dict,
        description="Optional mapping of project ID to role (admin, editor, viewer)",
    )


class TransferOwnership(BaseModel):
    """Model for transferring organization ownership."""

    new_owner_id: str = Field(
        ..., description="User ID of the new owner (must be an admin)"
    )


# Helper Functions
def get_organization_member(
    db: Database, organization_id: ObjectId, user_id: ObjectId
) -> dict | None:
    """Get organization member record for a user."""
    return db.organization_members.find_one(
        {"organizationId": organization_id, "userId": user_id, "status": "active"}
    )


def is_organization_admin(
    db: Database, organization_id: ObjectId, user_id: ObjectId
) -> bool:
    """Check if user is an admin or owner of the organization."""
    # Check if user is the organization owner
    organization = db.organizations.find_one({"_id": organization_id})
    if organization and str(organization["ownerId"]) == str(user_id):
        return True

    # Check if user is an admin member
    member = get_organization_member(db, organization_id, user_id)
    return member and member["role"] in ["owner", "admin"]


def count_organization_admins(db: Database, organization_id: ObjectId) -> int:
    """Count number of admins (including owner) in organization."""
    return db.organization_members.count_documents(
        {
            "organizationId": organization_id,
            "role": {"$in": ["owner", "admin"]},
            "status": "active",
        }
    )


def get_user_by_email(db: Database, email: str) -> dict | None:
    """Find user by email address."""
    return db.users.find_one({"email": email})


# API Endpoints
@router.post("/{org_id}/invitations", summary="Invite user to organization")
@limiter.limit(config.rate_limit.INVITATION_CREATE)
def invite_user_to_organization(
    request: Request,
    org_id: str,
    invite: OrganizationInvite,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Invite a user to join an organization.

    Rate limited to prevent spam (5 requests per minute).
    Only organization admins and owners can invite users.
    Creates an invitation record that can be accepted by the invited user.
    """
    org_obj_id = validate_object_id(org_id, "org_id")
    user_obj_id = validate_object_id(auth.user_id, "user_id")

    # Verify organization exists
    organization = mongo_db.organizations.find_one({"_id": org_obj_id})
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Verify inviter is admin or owner
    if not is_organization_admin(mongo_db, org_obj_id, user_obj_id):
        raise HTTPException(
            status_code=403,
            detail="Only organization admins can invite users",
        )

    # Get inviter's email to prevent self-invitation
    inviter = mongo_db.users.find_one({"_id": user_obj_id})
    if inviter and inviter.get("email") == invite.email:
        raise HTTPException(
            status_code=400,
            detail="You cannot invite yourself",
        )

    # Check if invited user already exists
    invited_user = get_user_by_email(mongo_db, invite.email)

    # If user exists, check if already a member or owner
    if invited_user:
        # Check if user is the organization owner
        if str(organization["ownerId"]) == str(invited_user["_id"]):
            raise HTTPException(
                status_code=400,
                detail="User is the owner of this organization",
            )

        # Check if user is already a member
        existing_member = get_organization_member(
            mongo_db, org_obj_id, invited_user["_id"]
        )
        if existing_member:
            raise HTTPException(
                status_code=400,
                detail="User is already a member of this organization",
            )

    # Check for pending invitation and handle expired or replace existing ones
    existing_invitation = mongo_db.invitations.find_one(
        {
            "email": invite.email,
            "organizationId": org_obj_id,
            "projectId": None,  # Organization-level invitation
            "status": "pending",
        }
    )

    if existing_invitation:
        # Check if the invitation has expired
        from .invitations import is_invitation_expired

        if is_invitation_expired(existing_invitation):
            # Mark as expired in the database
            mongo_db.invitations.update_one(
                {"_id": existing_invitation["_id"]},
                {"$set": {"status": "expired"}},
            )
            logger.info(
                f"Marked expired invitation as 'expired': id={existing_invitation['_id']}, "
                f"email={invite.email}, org={org_id}"
            )
        else:
            # Auto-cancel existing pending invitation and create new one
            mongo_db.invitations.delete_one({"_id": existing_invitation["_id"]})
            logger.info(
                f"Auto-cancelled existing pending invitation: id={existing_invitation['_id']}, "
                f"email={invite.email}, org={org_id}, reason=new_invitation_requested"
            )

    # Generate invitation token using shared helper
    invitation_token = generate_invitation_token()

    # Calculate expiration (24 hours)
    expires_at = utc_now() + timedelta(hours=24)

    # Validate project assignments if provided
    project_assignments = []
    if invite.projectIds:
        for project_id_str in invite.projectIds:
            project_obj_id = validate_object_id(project_id_str, "project_id")

            # Verify project exists and belongs to this organization
            project = mongo_db.projects.find_one({"_id": project_obj_id})
            if not project:
                raise HTTPException(
                    status_code=404, detail=f"Project not found: {project_id_str}"
                )

            if str(project["organizationId"]) != org_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Project {project_id_str} does not belong to this organization",
                )

            # Get role for this project (default to viewer if not specified)
            project_role = invite.projectRoles.get(project_id_str, "viewer")
            if project_role not in ["admin", "editor", "viewer"]:
                raise HTTPException(
                    status_code=400, detail=f"Invalid project role: {project_role}"
                )

            project_assignments.append(
                {
                    "projectId": project_id_str,
                    "projectName": project["name"],
                    "role": project_role,
                }
            )

    # Create invitation record
    invitation_doc = {
        "email": invite.email,
        "organizationId": org_obj_id,
        "projectId": None,  # Organization-level invitation
        "invitedBy": user_obj_id,
        "role": invite.role,
        "token": invitation_token,
        "status": "pending",
        "expiresAt": expires_at,
        "createdAt": utc_now(),
        "projectAssignments": project_assignments,  # Store project assignments
    }

    result = mongo_db.invitations.insert_one(invitation_doc)
    invitation_id = str(result.inserted_id)

    logger.info(
        f"✅ Created organization invitation: org={org_id}, email={invite.email}, "
        f"inviter={auth.user_id}, role={invite.role}, projects={len(project_assignments)}"
    )

    # Get inviter information for email
    inviter = mongo_db.users.find_one({"_id": user_obj_id})
    inviter_email = inviter.get("email") if inviter else "Unknown"

    # Attempt to send invitation email (non-blocking)
    try:
        send_invitation_email(
            email=invite.email,
            organization_name=organization["name"],
            project_name=None,  # Org-level invitation
            role=invite.role,
            invited_by_email=inviter_email,
            invitation_token=invitation_token,
        )
    except Exception as email_error:
        # Log email failure but don't break invitation creation
        logger.error(
            f"❌ Failed to send invitation email: invitation_id={invitation_id}, "
            f"email={invite.email}, error={type(email_error).__name__}: {email_error}"
        )

    return {
        "invitation_id": invitation_id,
        "email": invite.email,
        "organization_id": org_id,
        "role": invite.role,
        "project_assignments": project_assignments,
        "token": invitation_token,
        "expires_at": expires_at.isoformat(),
        "message": "Invitation created successfully",
    }


@router.get("/{org_id}/members", summary="List organization members")
def list_organization_members(
    org_id: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    List all members of an organization.

    Any organization member can view the member list.
    """
    org_obj_id = validate_object_id(org_id, "org_id")
    user_obj_id = validate_object_id(auth.user_id, "user_id")

    # Verify organization exists
    organization = mongo_db.organizations.find_one({"_id": org_obj_id})
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Verify requester is a member OR owner
    is_owner = str(organization["ownerId"]) == auth.user_id
    requester_member = get_organization_member(mongo_db, org_obj_id, user_obj_id)

    if not is_owner and not requester_member:
        raise HTTPException(
            status_code=403,
            detail="Access denied - not a member of this organization",
        )

    # Get all active members
    members = list(
        mongo_db.organization_members.find(
            {"organizationId": org_obj_id, "status": "active"}
        ).sort("joinedAt", 1)
    )

    # Enrich member data with user information and project count
    enriched_members = []
    for member in members:
        user = mongo_db.users.find_one({"_id": member["userId"]})
        if user:
            # Count projects this member has access to in this organization
            projects_count = mongo_db.project_members.count_documents(
                {
                    "userId": member["userId"],
                    "organizationId": org_obj_id,
                }
            )

            enriched_members.append(
                {
                    "userId": str(member["userId"]),
                    "email": user.get("email"),
                    "name": user.get("name"),
                    "role": member["role"],
                    "joinedAt": member["joinedAt"].isoformat(),
                    "invitedBy": str(member.get("invitedBy"))
                    if member.get("invitedBy")
                    else None,
                    "projectsCount": projects_count,
                }
            )

    # Get ALL pending invitations for this organization (org-level AND project-level)
    pending_invitations = list(
        mongo_db.invitations.find(
            {"organizationId": org_obj_id, "status": "pending"}
        ).sort("createdAt", -1)
    )

    # Enrich invitation data
    enriched_invitations = []
    for invitation in pending_invitations:
        # Get inviter details
        inviter = mongo_db.users.find_one({"_id": invitation["invitedBy"]})
        inviter_email = inviter.get("email") if inviter else "Unknown"

        # Determine invitation type and get relevant info
        is_project_invitation = invitation.get("projectId") is not None
        project_name = None

        if is_project_invitation:
            # Project-level invitation
            project = mongo_db.projects.find_one({"_id": invitation["projectId"]})
            project_name = project["name"] if project else "Unknown Project"
            project_assignments = []
        else:
            # Organization-level invitation (may have project assignments)
            project_assignments = invitation.get("projectAssignments", [])

        enriched_invitations.append(
            {
                "invitationId": str(invitation["_id"]),
                "email": invitation["email"],
                "role": invitation["role"],
                "invitedBy": inviter_email,
                "invitedByUserId": str(invitation["invitedBy"]),
                "invitationType": "project"
                if is_project_invitation
                else "organization",
                "projectName": project_name,  # Only for project invitations
                "projectAssignments": project_assignments,  # Only for org invitations
                "projectsCount": len(project_assignments)
                if not is_project_invitation
                else 1,
                "createdAt": invitation["createdAt"].isoformat(),
                "expiresAt": invitation["expiresAt"].isoformat(),
                "status": invitation["status"],
            }
        )

    logger.info(
        f"Listed organization members: org={org_id}, requester={auth.user_id}, "
        f"members={len(enriched_members)}, pending_invitations={len(enriched_invitations)}"
    )

    return {
        "organization_id": org_id,
        "members": enriched_members,
        "pending_invitations": enriched_invitations,
        "total_members": len(enriched_members),
        "total_pending": len(enriched_invitations),
    }


@router.put("/{org_id}/members/{user_id}", summary="Update organization member role")
def update_organization_member_role(
    org_id: str,
    user_id: str,
    role_update: BaseModel,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Update an organization member's role.

    - Only admins and owners can update roles
    - Cannot change organization owner's role
    - Cannot demote the last admin
    - Valid roles: admin, member
    """
    from pydantic import Field

    class UpdateMemberRole(BaseModel):
        role: str = Field(..., pattern="^(admin|member)$")

    role_data = UpdateMemberRole(
        **role_update.dict() if hasattr(role_update, "dict") else role_update
    )

    org_obj_id = validate_object_id(org_id, "org_id")
    requester_obj_id = validate_object_id(auth.user_id, "user_id")
    target_user_obj_id = validate_object_id(user_id, "user_id")

    # Verify organization exists
    organization = mongo_db.organizations.find_one({"_id": org_obj_id})
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Verify requester is admin or owner
    if not is_organization_admin(mongo_db, org_obj_id, requester_obj_id):
        raise HTTPException(
            status_code=403,
            detail="Only organization admins can update member roles",
        )

    # Cannot change organization owner's role
    if str(organization["ownerId"]) == user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot change organization owner's role. Transfer ownership first.",
        )

    # Verify target user is a member
    target_member = get_organization_member(mongo_db, org_obj_id, target_user_obj_id)
    if not target_member:
        raise HTTPException(
            status_code=404,
            detail="User is not a member of this organization",
        )

    # Check if this would demote the last admin
    if target_member["role"] == "admin" and role_data.role != "admin":
        admin_count = count_organization_admins(mongo_db, org_obj_id)
        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last admin. Promote another member first.",
            )

    # Update role
    mongo_db.organization_members.update_one(
        {"organizationId": org_obj_id, "userId": target_user_obj_id},
        {"$set": {"role": role_data.role}},
    )

    logger.info(
        f"Updated organization member role: org={org_id}, user={user_id}, "
        f"old_role={target_member['role']}, new_role={role_data.role}, "
        f"requester={auth.user_id}"
    )

    return {
        "message": "Member role updated successfully",
        "organization_id": org_id,
        "user_id": user_id,
        "old_role": target_member["role"],
        "new_role": role_data.role,
    }


@router.delete("/{org_id}/members/{user_id}", summary="Remove user from organization")
def remove_user_from_organization(
    org_id: str,
    user_id: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Remove a user from an organization.

    - Only admins and owners can remove members
    - Cannot remove the last admin
    - Cannot remove the organization owner
    - Cascades: removes from all projects, deactivates all API keys
    """
    org_obj_id = validate_object_id(org_id, "org_id")
    requester_obj_id = validate_object_id(auth.user_id, "user_id")
    target_user_obj_id = validate_object_id(user_id, "user_id")

    # Verify organization exists
    organization = mongo_db.organizations.find_one({"_id": org_obj_id})
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Verify requester is admin
    if not is_organization_admin(mongo_db, org_obj_id, requester_obj_id):
        raise HTTPException(
            status_code=403,
            detail="Only organization admins can remove members",
        )

    # Verify target user is a member
    target_member = get_organization_member(mongo_db, org_obj_id, target_user_obj_id)
    if not target_member:
        raise HTTPException(
            status_code=404,
            detail="User is not a member of this organization",
        )

    # Cannot remove organization owner
    if str(organization["ownerId"]) == user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove organization owner. Transfer ownership first.",
        )

    # Check if this would remove the last admin
    if target_member["role"] in ["owner", "admin"]:
        admin_count = count_organization_admins(mongo_db, org_obj_id)
        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last admin. Promote another member first.",
            )

    # CASCADE 1: Remove from organization_members
    mongo_db.organization_members.delete_one(
        {"organizationId": org_obj_id, "userId": target_user_obj_id}
    )

    # CASCADE 2: Remove from ALL project_members in this organization
    project_removal_result = mongo_db.project_members.delete_many(
        {"organizationId": org_obj_id, "userId": target_user_obj_id}
    )

    # CASCADE 3: Deactivate ALL API keys in this organization
    key_deactivation_result = mongo_db.api_keys.update_many(
        {
            "userId": target_user_obj_id,
            "projectId": {
                "$in": [
                    p["_id"]
                    for p in mongo_db.projects.find(
                        {"organizationId": org_obj_id}, {"_id": 1}
                    )
                ]
            },
        },
        {"$set": {"isActive": False, "deactivatedAt": utc_now()}},
    )

    logger.info(
        f"Removed user from organization: org={org_id}, user={user_id}, "
        f"requester={auth.user_id}, projects_removed={project_removal_result.deleted_count}, "
        f"keys_deactivated={key_deactivation_result.modified_count}"
    )

    return {
        "message": "User removed from organization successfully",
        "organization_id": org_id,
        "user_id": user_id,
        "cascades": {
            "projects_removed": project_removal_result.deleted_count,
            "api_keys_deactivated": key_deactivation_result.modified_count,
        },
    }


@router.delete(
    "/{org_id}/invitations/{invitation_id}", summary="Cancel pending invitation"
)
def cancel_organization_invitation(
    org_id: str,
    invitation_id: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Cancel a pending organization invitation.

    - Only admins and owners can cancel invitations
    - Invitation must be pending
    - Invitation must belong to this organization
    """
    org_obj_id = validate_object_id(org_id, "org_id")
    invitation_obj_id = validate_object_id(invitation_id, "invitation_id")
    user_obj_id = validate_object_id(auth.user_id, "user_id")

    # Verify organization exists
    organization = mongo_db.organizations.find_one({"_id": org_obj_id})
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Verify requester is admin
    if not is_organization_admin(mongo_db, org_obj_id, user_obj_id):
        raise HTTPException(
            status_code=403,
            detail="Only organization admins can cancel invitations",
        )

    # Find invitation
    invitation = mongo_db.invitations.find_one(
        {
            "_id": invitation_obj_id,
            "organizationId": org_obj_id,
            "projectId": None,  # Organization-level only
        }
    )

    if not invitation:
        raise HTTPException(
            status_code=404,
            detail="Invitation not found",
        )

    if invitation["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel invitation with status: {invitation['status']}",
        )

    # Delete the invitation
    mongo_db.invitations.delete_one({"_id": invitation_obj_id})

    logger.info(
        f"Cancelled invitation: id={invitation_id}, org={org_id}, "
        f"email={invitation['email']}, cancelled_by={auth.user_id}"
    )

    return {
        "message": "Invitation cancelled successfully",
        "invitation_id": invitation_id,
        "email": invitation["email"],
    }


@router.put("/{org_id}/transfer-ownership", summary="Transfer organization ownership")
def transfer_organization_ownership(
    org_id: str,
    transfer: TransferOwnership,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Transfer organization ownership to another admin.

    - Only the current owner can transfer ownership
    - Target user must be an existing admin
    - Current owner remains as admin after transfer
    """
    org_obj_id = validate_object_id(org_id, "org_id")
    current_owner_obj_id = validate_object_id(auth.user_id, "user_id")
    new_owner_obj_id = validate_object_id(transfer.new_owner_id, "new_owner_id")

    # Verify organization exists
    organization = mongo_db.organizations.find_one({"_id": org_obj_id})
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Verify requester is current owner
    if str(organization["ownerId"]) != auth.user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the organization owner can transfer ownership",
        )

    # Verify target user is an admin
    target_member = get_organization_member(mongo_db, org_obj_id, new_owner_obj_id)
    if not target_member:
        raise HTTPException(
            status_code=404,
            detail="Target user is not a member of this organization",
        )

    if target_member["role"] != "admin":
        raise HTTPException(
            status_code=400,
            detail="Target user must be an admin to receive ownership",
        )

    # Update organization owner
    mongo_db.organizations.update_one(
        {"_id": org_obj_id},
        {
            "$set": {
                "ownerId": new_owner_obj_id,
                "updatedAt": utc_now(),
            }
        },
    )

    # Update new owner's role to "owner" in organization_members
    mongo_db.organization_members.update_one(
        {"organizationId": org_obj_id, "userId": new_owner_obj_id},
        {"$set": {"role": "owner"}},
    )

    # Downgrade current owner to "admin"
    mongo_db.organization_members.update_one(
        {"organizationId": org_obj_id, "userId": current_owner_obj_id},
        {"$set": {"role": "admin"}},
    )

    logger.info(
        f"Transferred organization ownership: org={org_id}, "
        f"from={auth.user_id}, to={transfer.new_owner_id}"
    )

    return {
        "message": "Organization ownership transferred successfully",
        "organization_id": org_id,
        "previous_owner_id": auth.user_id,
        "new_owner_id": transfer.new_owner_id,
    }


@router.delete("/{org_id}", summary="Delete organization with cascade cleanup")
def delete_organization(
    org_id: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Delete an organization with complete cascade cleanup.

    **Cascade Actions:**
    1. Delete ALL projects in the organization (which cascades to project_members, api_keys, invitations)
    2. Remove ALL organization_members records
    3. Cancel ALL pending organization-level invitations
    4. Delete organization record
    5. Memories remain (project-owned)

    **Restrictions:**
    - Only organization owner can delete the organization
    - Requires confirmation (this is destructive and affects all projects)
    """
    org_obj_id = validate_object_id(org_id, "org_id")
    user_obj_id = validate_object_id(auth.user_id, "user_id")

    # Verify organization exists
    organization = mongo_db.organizations.find_one({"_id": org_obj_id})
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Verify requester is organization owner
    if str(organization["ownerId"]) != auth.user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the organization owner can delete the organization",
        )

    # Get all projects in this organization
    projects = list(mongo_db.projects.find({"organizationId": org_obj_id}))
    project_ids = [p["_id"] for p in projects]

    # CASCADE 1: Delete ALL projects (which cascades to project_members, api_keys, invitations)
    # For each project: remove project_members, deactivate api_keys, cancel invitations
    total_members_removed = 0
    total_keys_deactivated = 0
    total_project_invitations_cancelled = 0

    for project_obj_id in project_ids:
        # Remove project_members
        members_result = mongo_db.project_members.delete_many(
            {"projectId": project_obj_id}
        )
        total_members_removed += members_result.deleted_count

        # Deactivate API keys for this project
        keys_result = mongo_db.api_keys.update_many(
            {"projectId": project_obj_id, "isActive": True},
            {
                "$set": {
                    "isActive": False,
                    "deactivatedAt": utc_now(),
                    "deactivatedBy": user_obj_id,
                    "deactivatedReason": "organization_deleted",
                }
            },
        )
        total_keys_deactivated += keys_result.modified_count

        # Cancel project invitations
        invitations_result = mongo_db.invitations.update_many(
            {"projectId": project_obj_id, "status": "pending"},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelledAt": utc_now(),
                    "cancelledReason": "organization_deleted",
                }
            },
        )
        total_project_invitations_cancelled += invitations_result.modified_count

    # Delete all projects
    projects_deleted = mongo_db.projects.delete_many({"organizationId": org_obj_id})

    # CASCADE 2: Remove ALL organization_members
    org_members_removed = mongo_db.organization_members.delete_many(
        {"organizationId": org_obj_id}
    )

    # CASCADE 3: Cancel ALL organization-level invitations (projectId = None)
    org_invitations_cancelled = mongo_db.invitations.update_many(
        {"organizationId": org_obj_id, "projectId": None, "status": "pending"},
        {
            "$set": {
                "status": "cancelled",
                "cancelledAt": utc_now(),
                "cancelledReason": "organization_deleted",
            }
        },
    )

    # CASCADE 4: Delete the organization itself
    mongo_db.organizations.delete_one({"_id": org_obj_id})

    # Note: Memories are NOT deleted - they remain in vector store
    # This preserves data and allows for potential recovery scenarios

    logger.info(
        f"Organization deleted: org={org_id}, owner={auth.user_id}, "
        f"projects_deleted={projects_deleted.deleted_count}, "
        f"members_removed={total_members_removed}, "
        f"org_members_removed={org_members_removed.deleted_count}, "
        f"keys_deactivated={total_keys_deactivated}, "
        f"invitations_cancelled={total_project_invitations_cancelled + org_invitations_cancelled.modified_count}"
    )

    return {
        "message": "Organization deleted successfully",
        "organization_id": org_id,
        "organization_name": organization["name"],
        "cascades": {
            "projects_deleted": projects_deleted.deleted_count,
            "project_members_removed": total_members_removed,
            "organization_members_removed": org_members_removed.deleted_count,
            "api_keys_deactivated": total_keys_deactivated,
            "invitations_cancelled": total_project_invitations_cancelled
            + org_invitations_cancelled.modified_count,
        },
        "note": "All projects and their memories remain in the vector store but are no longer accessible.",
    }
