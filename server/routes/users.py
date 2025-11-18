"""
User management routes with cascade deletion logic.

This module implements Phase 8 of the Memory Sharing Implementation Plan:
- User account deletion with complete cascade cleanup
"""

import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from ..dependencies import AuthContext, authenticate_api_key, mongo_db
from ..utils.datetime_helpers import utc_now
from ..utils.permission_helpers import get_user_object_id_from_kratos_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["User Management"])


# Helper Functions
def count_organization_owners(db: Database, organization_id: ObjectId) -> int:
    """Count number of owners in organization."""
    org = db.organizations.find_one({"_id": organization_id})
    return 1 if org else 0


def get_user_owned_organizations(db: Database, user_id: ObjectId) -> list:
    """Get all organizations where user is the owner."""
    return list(db.organizations.find({"ownerId": user_id}))


def get_user_admin_projects(db: Database, user_id: ObjectId) -> list:
    """Get all projects where user is the only admin."""
    projects = list(db.project_members.find({"userId": user_id, "role": "admin"}))

    # Filter to only projects where user is the ONLY admin
    sole_admin_projects = []
    for member in projects:
        admin_count = db.project_members.count_documents(
            {"projectId": member["projectId"], "role": "admin"}
        )
        if admin_count == 1:
            sole_admin_projects.append(member["projectId"])

    return sole_admin_projects


# API Endpoints
@router.delete("/me", summary="Delete user account with cascade cleanup")
def delete_user_account(
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Delete user's account with complete cascade cleanup.

    **Cascade Actions:**
    1. Set user.isActive = false
    2. Deactivate ALL user's API keys
    3. Remove from ALL organization_members
    4. Remove from ALL project_members
    5. Mark invitations as cancelled
    6. Keep memories (project-owned, lose attribution)

    **Restrictions:**
    - User must NOT be the owner of any organization (must transfer first)
    - User must NOT be the sole admin of any project (must promote another)
    """
    # Get MongoDB ObjectId from Kratos ID
    user_obj_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)

    # Verify user exists
    user = mongo_db.users.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user owns any organizations
    owned_orgs = get_user_owned_organizations(mongo_db, user_obj_id)
    if owned_orgs:
        org_names = [org["name"] for org in owned_orgs]
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete account. You are the owner of {len(owned_orgs)} organization(s): {', '.join(org_names)}. Transfer ownership first.",
        )

    # Check if user is sole admin of any projects
    sole_admin_projects = get_user_admin_projects(mongo_db, user_obj_id)
    if sole_admin_projects:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete account. You are the sole admin of {len(sole_admin_projects)} project(s). Promote another admin first.",
        )

    # CASCADE 1: Deactivate user account
    mongo_db.users.update_one(
        {"_id": user_obj_id},
        {
            "$set": {
                "isActive": False,
                "deactivatedAt": utc_now(),
                "deactivatedReason": "user_requested_deletion",
            }
        },
    )

    # CASCADE 2: Deactivate ALL user's API keys
    key_deactivation_result = mongo_db.api_keys.update_many(
        {"userId": user_obj_id, "isActive": True},
        {
            "$set": {
                "isActive": False,
                "deactivatedAt": utc_now(),
                "deactivatedBy": user_obj_id,
                "deactivatedReason": "user_account_deleted",
            }
        },
    )

    # CASCADE 3: Remove from ALL organization_members
    org_removal_result = mongo_db.organization_members.delete_many(
        {"userId": user_obj_id}
    )

    # CASCADE 4: Remove from ALL project_members
    project_removal_result = mongo_db.project_members.delete_many(
        {"userId": user_obj_id}
    )

    # CASCADE 5: Cancel ALL pending invitations sent by this user
    invitation_cancel_result = mongo_db.invitations.update_many(
        {"invitedBy": user_obj_id, "status": "pending"},
        {
            "$set": {
                "status": "cancelled",
                "cancelledAt": utc_now(),
                "cancelledReason": "inviter_account_deleted",
            }
        },
    )

    # CASCADE 6: Cancel ALL pending invitations TO this user
    invitation_to_user_cancel_result = mongo_db.invitations.update_many(
        {"email": user.get("email"), "status": "pending"},
        {
            "$set": {
                "status": "cancelled",
                "cancelledAt": utc_now(),
                "cancelledReason": "invitee_account_deleted",
            }
        },
    )

    # Note: Memories are NOT deleted - they remain in the project
    # Attribution (createdBy) will show the deactivated user ID

    logger.info(
        f"User account deleted: user={auth.user_id}, "
        f"keys_deactivated={key_deactivation_result.modified_count}, "
        f"orgs_removed={org_removal_result.deleted_count}, "
        f"projects_removed={project_removal_result.deleted_count}, "
        f"invitations_cancelled={invitation_cancel_result.modified_count + invitation_to_user_cancel_result.modified_count}"
    )

    return {
        "message": "User account deleted successfully",
        "user_id": auth.user_id,
        "cascades": {
            "api_keys_deactivated": key_deactivation_result.modified_count,
            "organizations_removed": org_removal_result.deleted_count,
            "projects_removed": project_removal_result.deleted_count,
            "invitations_cancelled": invitation_cancel_result.modified_count
            + invitation_to_user_cancel_result.modified_count,
        },
        "note": "Memories created by you remain in their respective projects but attribution is preserved.",
    }


@router.get("/me", summary="Get current user details")
def get_current_user(
    auth: AuthContext = Depends(authenticate_api_key),
):
    """Get details of the currently authenticated user."""
    # Get MongoDB ObjectId from Kratos ID
    user_obj_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)

    user = mongo_db.users.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Remove sensitive fields
    user.pop("_id", None)
    user.pop("password", None)

    # Add user ID as string
    user["user_id"] = auth.user_id

    return user
