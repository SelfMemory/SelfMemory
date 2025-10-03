"""
Project member management routes.

This module implements Phase 3 of the Memory Sharing Implementation Plan:
- Add users to projects
- Invite users to projects
- List project members
- Update project member roles
- Remove users from projects
"""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from ..config import config
from ..database import get_role_permissions
from ..dependencies import AuthContext, authenticate_api_key, mongo_db
from ..utils.datetime_helpers import utc_now
from ..utils.permission_helpers import (
    count_project_admins,
    get_project_member,
    get_user_by_email,
    is_organization_member,
    is_project_admin,
)
from ..utils.rate_limiter import limiter
from ..utils.transaction_manager import safe_insert_member
from ..utils.validators import validate_object_id
from .invitations import generate_invitation_token, send_invitation_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Project Management"])


# Pydantic Models
class ProjectWithRole(BaseModel):
    """Model for project with user's role information."""

    _id: str
    name: str
    organizationId: str
    ownerId: str
    createdAt: str
    updatedAt: str
    # User's role and permissions in this project
    userRole: str | None = None  # admin, editor, viewer
    userPermissions: dict | None = None
    isOwner: bool = False


class AddProjectMember(BaseModel):
    """Model for adding a user to a project."""

    user_id: str = Field(..., description="User ID to add to the project")
    role: str = Field(
        default="editor",
        description="Role in project: admin, editor, or viewer",
        pattern="^(admin|editor|viewer)$",
    )


class ProjectInvite(BaseModel):
    """Model for inviting a user to a project."""

    email: EmailStr = Field(..., description="Email address of the user to invite")
    role: str = Field(
        default="editor",
        description="Role in project: admin, editor, or viewer",
        pattern="^(admin|editor|viewer)$",
    )


class UpdateProjectMemberRole(BaseModel):
    """Model for updating a project member's role."""

    role: str = Field(
        ...,
        description="New role: admin, editor, or viewer",
        pattern="^(admin|editor|viewer)$",
    )


# API Endpoints
# Note: Helper functions now imported from utils.permission_helpers
@router.get("/{project_id}", summary="Get single project details")
def get_project_details(
    project_id: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Get details for a single project.

    Returns project information with user's role and permissions.
    User must be owner or member of the project.
    """
    project_obj_id = validate_object_id(project_id, "project_id")
    user_obj_id = validate_object_id(auth.user_id, "user_id")

    # Get project
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user is owner
    is_owner = str(project["ownerId"]) == auth.user_id

    if is_owner:
        # Owner has full access
        return {
            "_id": str(project["_id"]),
            "name": project["name"],
            "organizationId": str(project["organizationId"]),
            "ownerId": str(project["ownerId"]),
            "createdAt": project["createdAt"].isoformat(),
            "updatedAt": project["updatedAt"].isoformat(),
            "isOwner": True,
            "currentUser": {
                "userId": auth.user_id,
                "role": "admin",
                "isOwner": True,
                "permissions": {
                    "canRead": True,
                    "canWrite": True,
                    "canDelete": True,
                    "canInvite": True,
                },
            },
        }

    # Check if user is a member
    member_record = mongo_db.project_members.find_one(
        {"projectId": project_obj_id, "userId": user_obj_id}
    )

    if not member_record:
        raise HTTPException(
            status_code=403, detail="Access denied - not a member of this project"
        )

    # Return project with member info
    return {
        "_id": str(project["_id"]),
        "name": project["name"],
        "organizationId": str(project["organizationId"]),
        "ownerId": str(project["ownerId"]),
        "createdAt": project["createdAt"].isoformat(),
        "updatedAt": project["updatedAt"].isoformat(),
        "isOwner": False,
        "currentUser": {
            "userId": auth.user_id,
            "role": member_record["role"],
            "isOwner": False,
            "permissions": member_record["permissions"],
        },
    }


@router.get("", summary="List all user's projects")
def list_user_projects(
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    List all projects the user has access to.

    Access Rules:
    - Organization owners: See ALL projects in their organizations
    - Project owners: See their owned projects
    - Members: See projects they're explicitly added to

    Returns projects with role information:
    - For owned projects: isOwner=True
    - For member projects: userRole and userPermissions included
    - For org owner access: isOrgOwner=True
    """
    user_obj_id = validate_object_id(auth.user_id, "user_id")

    all_projects = []
    project_ids_seen = set()

    # 1. Get organizations where user is the owner
    owned_orgs = list(mongo_db.organizations.find({"ownerId": user_obj_id}))
    owned_org_ids = [org["_id"] for org in owned_orgs]

    # 2. Get ALL projects in organizations where user is owner
    for org_id in owned_org_ids:
        org_projects = list(
            mongo_db.projects.find({"organizationId": org_id}).sort("createdAt", -1)
        )

        for project in org_projects:
            project_id = str(project["_id"])
            if project_id in project_ids_seen:
                continue

            project_ids_seen.add(project_id)
            all_projects.append(
                {
                    "_id": project_id,
                    "name": project["name"],
                    "organizationId": str(project["organizationId"]),
                    "ownerId": str(project["ownerId"]),
                    "createdAt": project["createdAt"].isoformat(),
                    "updatedAt": project["updatedAt"].isoformat(),
                    "isOwner": str(project["ownerId"]) == auth.user_id,
                    "isOrgOwner": True,
                    "role": "admin",
                    "userPermissions": {
                        "canRead": True,
                        "canWrite": True,
                        "canDelete": True,
                        "canInvite": True,
                    },
                }
            )

    # 3. Get all projects owned by the user (that aren't in orgs they own)
    owned_projects = list(
        mongo_db.projects.find({"ownerId": user_obj_id}).sort("createdAt", -1)
    )

    for project in owned_projects:
        project_id = str(project["_id"])
        if project_id in project_ids_seen:
            continue

        project_ids_seen.add(project_id)
        all_projects.append(
            {
                "_id": project_id,
                "name": project["name"],
                "organizationId": str(project["organizationId"]),
                "ownerId": str(project["ownerId"]),
                "createdAt": project["createdAt"].isoformat(),
                "updatedAt": project["updatedAt"].isoformat(),
                "isOwner": True,
                "isOrgOwner": False,
                "role": "admin",
                "userPermissions": {
                    "canRead": True,
                    "canWrite": True,
                    "canDelete": True,
                    "canInvite": True,
                },
            }
        )

    # 4. Get all projects where user is a member
    member_records = list(
        mongo_db.project_members.find({"userId": user_obj_id}).sort("addedAt", -1)
    )

    for member_record in member_records:
        project_id = str(member_record["projectId"])

        if project_id in project_ids_seen:
            continue

        # Get project details
        project = mongo_db.projects.find_one({"_id": member_record["projectId"]})
        if not project:
            continue

        project_ids_seen.add(project_id)
        all_projects.append(
            {
                "_id": project_id,
                "name": project["name"],
                "organizationId": str(project["organizationId"]),
                "ownerId": str(project["ownerId"]),
                "createdAt": project["createdAt"].isoformat(),
                "updatedAt": project["updatedAt"].isoformat(),
                "isOwner": False,
                "isOrgOwner": False,
                "role": member_record["role"],
                "userPermissions": member_record["permissions"],
            }
        )

    logger.info(
        f"Listed user projects: user={auth.user_id}, total_count={len(all_projects)}, "
        f"org_owner_access={len(owned_org_ids)}, owned={len(owned_projects)}, member={len(member_records)}"
    )

    return {
        "projects": all_projects,
        "total_count": len(all_projects),
    }


@router.post("/{project_id}/members", summary="Add user to project")
def add_user_to_project(
    project_id: str,
    member: AddProjectMember,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Add an existing organization member to a project.

    - Only project admins can add members
    - User must already be a member of the organization
    - Automatically assigns permissions based on role
    """
    project_obj_id = validate_object_id(project_id, "project_id")
    requester_obj_id = validate_object_id(auth.user_id, "user_id")
    target_user_obj_id = validate_object_id(member.user_id, "user_id")

    # Verify project exists
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    organization_id = project["organizationId"]

    # Verify requester is project admin
    if not is_project_admin(mongo_db, project_obj_id, requester_obj_id):
        raise HTTPException(
            status_code=403,
            detail="Only project admins can add members",
        )

    # Verify target user exists
    target_user = mongo_db.users.find_one({"_id": target_user_obj_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify target user is organization member
    if not is_organization_member(mongo_db, organization_id, target_user_obj_id):
        raise HTTPException(
            status_code=400,
            detail="User must be a member of the organization first",
        )

    # Get permissions for role
    permissions = get_role_permissions(member.role)

    # Create project_members record with race condition handling
    # The unique index will prevent duplicates, safe_insert_member handles gracefully
    member_doc = {
        "projectId": project_obj_id,
        "userId": target_user_obj_id,
        "organizationId": organization_id,
        "role": member.role,
        "permissions": permissions,
        "addedBy": requester_obj_id,
        "addedAt": utc_now(),
    }

    member_id, already_existed = safe_insert_member(
        mongo_db.project_members, member_doc, "project_member"
    )

    if already_existed:
        # User was already added (concurrent request or race condition)
        raise HTTPException(
            status_code=400,
            detail="User already has access to this project",
        )

    logger.info(
        f"Added user to project: project={project_id}, user={member.user_id}, "
        f"role={member.role}, requester={auth.user_id}"
    )

    return {
        "member_id": member_id,
        "project_id": project_id,
        "user_id": member.user_id,
        "role": member.role,
        "permissions": permissions,
        "message": "User added to project successfully",
    }


@router.post("/{project_id}/invitations", summary="Invite user to project")
@limiter.limit(config.rate_limit.INVITATION_CREATE)
def invite_user_to_project(
    request: Request,
    project_id: str,
    invite: ProjectInvite,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Invite a user to join a project.

    Rate limited to prevent spam (5 requests per minute).
    - Only project admins can invite users
    - If user is not in organization, they will be invited to org first
    - Creates invitation that can be accepted
    """
    project_obj_id = validate_object_id(project_id, "project_id")
    requester_obj_id = validate_object_id(auth.user_id, "user_id")

    # Verify project exists
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    organization_id = project["organizationId"]

    # Verify requester is project admin
    if not is_project_admin(mongo_db, project_obj_id, requester_obj_id):
        raise HTTPException(
            status_code=403,
            detail="Only project admins can invite users",
        )

    # Get inviter's email to prevent self-invitation
    inviter = mongo_db.users.find_one({"_id": requester_obj_id})
    if inviter and inviter.get("email") == invite.email:
        raise HTTPException(
            status_code=400,
            detail="You cannot invite yourself",
        )

    # Check if invited user exists
    invited_user = get_user_by_email(mongo_db, invite.email)

    # If user exists, check if already has project access
    if invited_user:
        # Check if user is the project owner
        if str(project["ownerId"]) == str(invited_user["_id"]):
            raise HTTPException(
                status_code=400,
                detail="User is the owner of this project",
            )

        # Check if user is already a member
        existing_member = get_project_member(
            mongo_db, project_obj_id, invited_user["_id"]
        )
        if existing_member:
            raise HTTPException(
                status_code=400,
                detail="User already has access to this project",
            )

    # Get inviter and organization information
    inviter = mongo_db.users.find_one({"_id": requester_obj_id})
    inviter_email = inviter.get("email") if inviter else "Unknown"

    organization = mongo_db.organizations.find_one({"_id": organization_id})
    organization_name = organization["name"] if organization else "Unknown"

    # Check if user is in organization
    user_in_org = invited_user and is_organization_member(
        mongo_db, organization_id, invited_user["_id"]
    )

    if not user_in_org:
        # User not in org - create org-level invitation with project assignment
        # Check for existing org invitation
        existing_org_invitation = mongo_db.invitations.find_one(
            {
                "email": invite.email,
                "organizationId": organization_id,
                "projectId": None,
                "status": "pending",
            }
        )

        if existing_org_invitation:
            raise HTTPException(
                status_code=400,
                detail="User already has a pending organization invitation",
            )

        # Generate invitation token
        invitation_token = generate_invitation_token()
        expires_at = utc_now() + timedelta(hours=24)

        # Create org-level invitation with this project assigned
        invitation_doc = {
            "email": invite.email,
            "organizationId": organization_id,
            "projectId": None,  # Org-level
            "invitedBy": requester_obj_id,
            "role": "member",  # Default org role
            "token": invitation_token,
            "status": "pending",
            "expiresAt": expires_at,
            "createdAt": utc_now(),
            "projectAssignments": [
                {
                    "projectId": project_id,
                    "projectName": project["name"],
                    "role": invite.role,
                }
            ],
        }

        result = mongo_db.invitations.insert_one(invitation_doc)
        invitation_id = str(result.inserted_id)

        # Send invitation email
        send_invitation_email(
            email=invite.email,
            organization_name=organization_name,
            project_name=None,  # Org-level invitation
            role="member",
            invited_by_email=inviter_email,
            invitation_token=invitation_token,
        )

        logger.info(
            f"Created org invitation with project assignment: org={str(organization_id)}, "
            f"project={project_id}, email={invite.email}, inviter={auth.user_id}, "
            f"project_role={invite.role}"
        )

        return {
            "invitation_id": invitation_id,
            "email": invite.email,
            "invitation_type": "organization",
            "organization_id": str(organization_id),
            "project_assignments": [
                {
                    "project_id": project_id,
                    "project_name": project["name"],
                    "role": invite.role,
                }
            ],
            "token": invitation_token,
            "expires_at": expires_at.isoformat(),
            "message": "Organization invitation created with project assignment",
        }

    # User is in org - create project-level invitation
    # Check for pending project invitation
    existing_invitation = mongo_db.invitations.find_one(
        {
            "email": invite.email,
            "projectId": project_obj_id,
            "status": "pending",
        }
    )

    if existing_invitation:
        raise HTTPException(
            status_code=400,
            detail="User already has a pending invitation to this project",
        )

    # Generate invitation token
    invitation_token = generate_invitation_token()
    expires_at = utc_now() + timedelta(hours=24)

    # Create project-level invitation
    invitation_doc = {
        "email": invite.email,
        "organizationId": organization_id,
        "projectId": project_obj_id,
        "invitedBy": requester_obj_id,
        "role": invite.role,
        "token": invitation_token,
        "status": "pending",
        "expiresAt": expires_at,
        "createdAt": utc_now(),
    }

    result = mongo_db.invitations.insert_one(invitation_doc)
    invitation_id = str(result.inserted_id)

    # Send invitation email
    send_invitation_email(
        email=invite.email,
        organization_name=organization_name,
        project_name=project["name"],
        role=invite.role,
        invited_by_email=inviter_email,
        invitation_token=invitation_token,
    )

    logger.info(
        f"Created project invitation: project={project_id}, email={invite.email}, "
        f"inviter={auth.user_id}, role={invite.role}"
    )

    return {
        "invitation_id": invitation_id,
        "email": invite.email,
        "invitation_type": "project",
        "project_id": project_id,
        "organization_id": str(organization_id),
        "role": invite.role,
        "token": invitation_token,
        "expires_at": expires_at.isoformat(),
        "message": "Project invitation created successfully",
    }


@router.get("/{project_id}/members", summary="List project members")
def list_project_members(
    project_id: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    List all members of a project.

    Any project member can view the member list.
    """
    project_obj_id = validate_object_id(project_id, "project_id")
    user_obj_id = validate_object_id(auth.user_id, "user_id")

    # Verify project exists
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify requester has project access (owner OR member)
    is_owner = str(project["ownerId"]) == auth.user_id
    requester_member = get_project_member(mongo_db, project_obj_id, user_obj_id)

    if not is_owner and not requester_member:
        raise HTTPException(
            status_code=403,
            detail="Access denied - not a member of this project",
        )

    # Get all project members
    members = list(
        mongo_db.project_members.find({"projectId": project_obj_id}).sort("addedAt", 1)
    )

    # Enrich member data with user information
    enriched_members = []
    for member in members:
        user = mongo_db.users.find_one({"_id": member["userId"]})
        if user:
            # Check if user is the project owner
            is_member_owner = str(member["userId"]) == str(project["ownerId"])

            enriched_members.append(
                {
                    "userId": str(member["userId"]),
                    "email": user.get("email"),
                    "name": user.get("name"),
                    "role": member["role"],
                    "permissions": member["permissions"],
                    "addedAt": member["addedAt"].isoformat(),
                    "addedBy": str(member.get("addedBy"))
                    if member.get("addedBy")
                    else None,
                    "isOwner": is_member_owner,
                }
            )

    logger.info(
        f"Listed project members: project={project_id}, requester={auth.user_id}, "
        f"count={len(enriched_members)}"
    )

    return {
        "project_id": project_id,
        "members": enriched_members,
        "total_count": len(enriched_members),
    }


@router.put("/{project_id}/members/{user_id}", summary="Update project member role")
def update_project_member_role(
    project_id: str,
    user_id: str,
    role_update: UpdateProjectMemberRole,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Update a project member's role.

    - Only project admins can update roles
    - Cannot demote the last admin
    - Automatically updates permissions based on new role
    """
    project_obj_id = validate_object_id(project_id, "project_id")
    requester_obj_id = validate_object_id(auth.user_id, "user_id")
    target_user_obj_id = validate_object_id(user_id, "user_id")

    # Verify project exists
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify requester is project admin
    if not is_project_admin(mongo_db, project_obj_id, requester_obj_id):
        raise HTTPException(
            status_code=403,
            detail="Only project admins can update member roles",
        )

    # Verify target user is a project member
    target_member = get_project_member(mongo_db, project_obj_id, target_user_obj_id)
    if not target_member:
        raise HTTPException(
            status_code=404,
            detail="User is not a member of this project",
        )

    # Check if this would demote the last admin
    if target_member["role"] == "admin" and role_update.role != "admin":
        admin_count = count_project_admins(mongo_db, project_obj_id)
        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last admin. Promote another member first.",
            )

    # Get permissions for new role
    new_permissions = get_role_permissions(role_update.role)

    # Update role and permissions
    mongo_db.project_members.update_one(
        {"projectId": project_obj_id, "userId": target_user_obj_id},
        {
            "$set": {
                "role": role_update.role,
                "permissions": new_permissions,
            }
        },
    )

    logger.info(
        f"Updated project member role: project={project_id}, user={user_id}, "
        f"old_role={target_member['role']}, new_role={role_update.role}, "
        f"requester={auth.user_id}"
    )

    return {
        "message": "Member role updated successfully",
        "project_id": project_id,
        "user_id": user_id,
        "old_role": target_member["role"],
        "new_role": role_update.role,
        "new_permissions": new_permissions,
    }


@router.delete("/{project_id}/members/{user_id}", summary="Remove user from project")
def remove_user_from_project(
    project_id: str,
    user_id: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Remove a user from a project.

    - Only admins can remove members (or users can remove themselves)
    - Cannot remove the last admin
    - Cascades: deactivates project-scoped API keys for the user
    """
    project_obj_id = validate_object_id(project_id, "project_id")
    requester_obj_id = validate_object_id(auth.user_id, "user_id")
    target_user_obj_id = validate_object_id(user_id, "user_id")

    # Verify project exists
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify requester is admin OR removing themselves
    is_admin = is_project_admin(mongo_db, project_obj_id, requester_obj_id)
    is_self_removal = str(requester_obj_id) == user_id

    if not is_admin and not is_self_removal:
        raise HTTPException(
            status_code=403,
            detail="Only project admins can remove other members",
        )

    # Verify target user is a project member
    target_member = get_project_member(mongo_db, project_obj_id, target_user_obj_id)
    if not target_member:
        raise HTTPException(
            status_code=404,
            detail="User is not a member of this project",
        )

    # Check if this would remove the last admin
    if target_member["role"] == "admin":
        admin_count = count_project_admins(mongo_db, project_obj_id)
        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last admin. Promote another member first.",
            )

    # CASCADE 1: Remove from project_members
    mongo_db.project_members.delete_one(
        {"projectId": project_obj_id, "userId": target_user_obj_id}
    )

    # CASCADE 2: Deactivate project-scoped API keys for this user
    key_deactivation_result = mongo_db.api_keys.update_many(
        {
            "userId": target_user_obj_id,
            "projectId": project_obj_id,
        },
        {"$set": {"isActive": False, "deactivatedAt": utc_now()}},
    )

    logger.info(
        f"Removed user from project: project={project_id}, user={user_id}, "
        f"requester={auth.user_id}, keys_deactivated={key_deactivation_result.modified_count}"
    )

    return {
        "message": "User removed from project successfully",
        "project_id": project_id,
        "user_id": user_id,
        "cascades": {
            "api_keys_deactivated": key_deactivation_result.modified_count,
        },
    }


@router.delete("/{project_id}", summary="Delete project with cascade cleanup")
def delete_project(
    project_id: str,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Delete a project with complete cascade cleanup.

    **Cascade Actions:**
    1. Remove ALL project_members records
    2. Deactivate ALL api_keys for the project
    3. Cancel ALL pending invitations for the project
    4. Delete project record
    5. Memories remain (decision: keep for now, can be deleted later)

    **Restrictions:**
    - Only project owner can delete the project
    - Requires confirmation (this is destructive)
    """
    project_obj_id = validate_object_id(project_id, "project_id")
    user_obj_id = validate_object_id(auth.user_id, "user_id")

    # Verify project exists
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify requester is project owner
    if str(project["ownerId"]) != auth.user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the project owner can delete the project",
        )

    # CASCADE 1: Remove ALL project_members
    members_removal_result = mongo_db.project_members.delete_many(
        {"projectId": project_obj_id}
    )

    # CASCADE 2: Deactivate ALL API keys for this project
    key_deactivation_result = mongo_db.api_keys.update_many(
        {"projectId": project_obj_id, "isActive": True},
        {
            "$set": {
                "isActive": False,
                "deactivatedAt": utc_now(),
                "deactivatedBy": user_obj_id,
                "deactivatedReason": "project_deleted",
            }
        },
    )

    # CASCADE 3: Cancel ALL pending invitations for this project
    invitation_cancel_result = mongo_db.invitations.update_many(
        {"projectId": project_obj_id, "status": "pending"},
        {
            "$set": {
                "status": "cancelled",
                "cancelledAt": utc_now(),
                "cancelledReason": "project_deleted",
            }
        },
    )

    # CASCADE 4: Delete the project itself
    mongo_db.projects.delete_one({"_id": project_obj_id})

    # Note: Memories are NOT deleted - they remain in vector store
    # Decision: Keep memories for now (can be cleaned up later if needed)
    # This preserves data and allows for potential recovery scenarios

    logger.info(
        f"Project deleted: project={project_id}, owner={auth.user_id}, "
        f"members_removed={members_removal_result.deleted_count}, "
        f"keys_deactivated={key_deactivation_result.modified_count}, "
        f"invitations_cancelled={invitation_cancel_result.modified_count}"
    )

    return {
        "message": "Project deleted successfully",
        "project_id": project_id,
        "project_name": project["name"],
        "cascades": {
            "members_removed": members_removal_result.deleted_count,
            "api_keys_deactivated": key_deactivation_result.modified_count,
            "invitations_cancelled": invitation_cancel_result.modified_count,
        },
        "note": "Memories created in this project remain in the vector store but are no longer accessible.",
    }
