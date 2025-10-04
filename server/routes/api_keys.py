"""
API Key Management Routes - Project-scoped API keys with team transparency.

This module implements Phase 5: Server - API Key Management (Project-Scoped)

Key Features:
- Project-scoped API keys (each key tied to one project)
- Team transparency (all members can see all project keys)
- Permission inheritance from project roles
- Owner/Admin can delete any key, users can delete their own

Following Uncle Bob's clean code principles:
- No fallback mechanisms
- Clear error messages
- Single responsibility per function
"""

import logging
import secrets
import string
from datetime import timedelta

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import (
    AuthContext,
    authenticate_api_key,
    check_project_access,
    mongo_db,
)
from ..utils.crypto import hash_api_key
from ..utils.datetime_helpers import utc_now
from ..utils.permission_helpers import get_project_member, is_project_admin
from ..utils.validators import validate_object_id

router = APIRouter(prefix="/api/projects", tags=["API Keys"])
logger = logging.getLogger(__name__)


# Pydantic Models
class ApiKeyCreate(BaseModel):
    name: str = Field(..., description="API key name.", min_length=1, max_length=100)
    permissions: list[str] | None = Field(
        default=None,
        description="API key permissions (optional, inherited from role if not specified).",
    )
    expires_in_days: int | None = Field(
        default=None, description="API key expiration in days (optional)."
    )


# Helper Functions
# Note: get_project_member and is_project_admin now imported from utils.permission_helpers


def get_user_project_permissions(project_id: ObjectId, user_id: ObjectId) -> dict:
    """Get user's permissions for a project."""
    member = get_project_member(project_id, user_id)
    if not member:
        raise HTTPException(
            status_code=403, detail="User does not have access to this project"
        )
    return member.get("permissions", {})


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a secure API key with Argon2 hash and prefix.

    Returns:
        tuple: (api_key, key_hash, key_prefix)
    """
    alphabet = string.ascii_letters + string.digits
    api_key = "sk_im_" + "".join(secrets.choice(alphabet) for _ in range(40))
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:10] + "..."
    return api_key, key_hash, key_prefix


# API Endpoints
@router.post("/{project_id}/api-keys", summary="Create project-scoped API key")
def create_project_api_key(
    project_id: str,
    key_create: ApiKeyCreate,
    auth: AuthContext = Depends(authenticate_api_key),
):
    """
    Create a new project-scoped API key.

    - API key is scoped to a single project
    - Permissions are inherited from user's project role if not specified
    - Key is returned only once (on creation)
    - User can create multiple keys for the same project
    """
    user_obj_id = validate_object_id(auth.user_id, "user_id")
    project_obj_id = validate_object_id(project_id, "project_id")

    # Get project to verify it exists and get organizationId
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    organization_id = project["organizationId"]

    # Check if user has access to the project (owner or member)
    if not check_project_access(auth.user_id, project_id):
        logger.warning(
            f"❌ User {auth.user_id} attempted to create API key for project {project_id} without access"
        )
        raise HTTPException(
            status_code=403, detail="You do not have access to this project"
        )

    # Get user's project membership to check permissions
    member = get_project_member(mongo_db, project_obj_id, user_obj_id)
    if not member:
        # User is project/org owner but not in project_members, give them full permissions
        user_permissions = {"canRead": True, "canWrite": True, "canDelete": True}
    else:
        user_permissions = member.get("permissions", {})

    # Check if user has ANY permissions (even read-only viewers can create API keys)
    # They can only create keys with permissions they have (no escalation)
    if not user_permissions.get("canRead", False):
        member_role = member.get("role") if member else "unknown"
        logger.warning(
            f"❌ User {auth.user_id} (role: {member_role}) attempted to create API key without any permissions"
        )
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to create API keys for this project",
        )

    # Determine permissions for the API key
    if key_create.permissions:
        # User specified custom permissions - validate they don't exceed their own permissions
        requested_perms = set(key_create.permissions)
        allowed_perms = set()
        if user_permissions.get("canRead"):
            allowed_perms.add("read")
        if user_permissions.get("canWrite"):
            allowed_perms.add("write")
        if user_permissions.get("canDelete"):
            allowed_perms.add("delete")

        if not requested_perms.issubset(allowed_perms):
            raise HTTPException(
                status_code=403,
                detail="Cannot create API key with permissions you don't have",
            )
        api_key_permissions = list(key_create.permissions)
    else:
        # Inherit permissions from user's project role
        api_key_permissions = []
        if user_permissions.get("canRead"):
            api_key_permissions.append("read")
        if user_permissions.get("canWrite"):
            api_key_permissions.append("write")
        if user_permissions.get("canDelete"):
            api_key_permissions.append("delete")

    # Generate API key
    api_key, key_hash, key_prefix = generate_api_key()

    logger.info(
        f"🔑 Generated API key for user={auth.user_id}, project={project_id}, name={key_create.name}"
    )

    # Calculate expiration if specified
    expires_at = None
    if key_create.expires_in_days:
        expires_at = utc_now() + timedelta(days=key_create.expires_in_days)

    # Create API key document with project and organization context
    key_doc = {
        "name": key_create.name,
        "userId": user_obj_id,
        "projectId": project_obj_id,
        "organizationId": organization_id,
        "keyHash": key_hash,
        "keyPrefix": key_prefix,
        "permissions": api_key_permissions,
        "isActive": True,
        "autoGenerated": False,
        "expiresAt": expires_at,
        "createdAt": utc_now(),
        "lastUsed": None,
    }

    logger.info("🔑 Storing API key document")

    result = mongo_db.api_keys.insert_one(key_doc)
    key_id = str(result.inserted_id)

    logger.info(
        f"✅ Created API key '{key_create.name}' (id={key_id}) for user {auth.user_id} in project {project_id}"
    )

    return {
        "api_key_id": key_id,
        "name": key_create.name,
        "api_key": api_key,  # Only returned on creation
        "key_prefix": key_prefix,
        "permissions": api_key_permissions,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "project_id": project_id,
        "organization_id": str(organization_id),
        "message": "API key created successfully. Store this key securely - it won't be shown again.",
    }


@router.get("/{project_id}/api-keys", summary="List all project API keys")
def list_project_api_keys(
    project_id: str, auth: AuthContext = Depends(authenticate_api_key)
):
    """
    List ALL API keys for a project (all team members' keys).

    This provides transparency - all project members can see all keys.
    Actual key values are never shown, only metadata.

    User must have project access to view keys.
    """
    project_obj_id = validate_object_id(project_id, "project_id")

    # Verify project exists
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user has access to the project (owner or member)
    if not check_project_access(auth.user_id, project_id):
        logger.warning(
            f"❌ User {auth.user_id} attempted to list API keys for project {project_id} without access"
        )
        raise HTTPException(
            status_code=403, detail="You do not have access to this project"
        )

    # Get ALL API keys for this project (team transparency)
    api_keys = list(mongo_db.api_keys.find({"projectId": project_obj_id}))

    # Enrich with user information and remove sensitive data
    result_keys = []
    for key in api_keys:
        # Get user info for owner email
        user = mongo_db.users.find_one({"_id": key["userId"]})
        owner_email = user.get("email", "Unknown") if user else "Unknown"

        result_keys.append(
            {
                "id": str(key["_id"]),
                "name": key.get("name", "Unnamed Key"),
                "key_prefix": key.get("keyPrefix", "sk_im_..."),
                "owner_id": str(key["userId"]),
                "owner_email": owner_email,
                "permissions": key.get("permissions", []),
                "is_active": key.get("isActive", True),
                "created_at": key.get("createdAt").isoformat()
                if key.get("createdAt")
                else None,
                "last_used": key.get("lastUsed").isoformat()
                if key.get("lastUsed")
                else None,
                "expires_at": key.get("expiresAt").isoformat()
                if key.get("expiresAt")
                else None,
            }
        )

    logger.info(
        f"✅ User {auth.user_id} listed {len(result_keys)} API keys for project {project_id}"
    )

    return {"api_keys": result_keys, "total": len(result_keys)}


@router.delete("/{project_id}/api-keys/{key_id}", summary="Delete project API key")
def delete_project_api_key(
    project_id: str, key_id: str, auth: AuthContext = Depends(authenticate_api_key)
):
    """
    Delete a project API key.

    Rules:
    - User can delete their own keys
    - Project admin can delete any key in the project
    - Key is deactivated (not physically deleted) for audit purposes
    """
    user_obj_id = validate_object_id(auth.user_id, "user_id")
    project_obj_id = validate_object_id(project_id, "project_id")
    key_obj_id = validate_object_id(key_id, "key_id")

    # Verify project exists
    project = mongo_db.projects.find_one({"_id": project_obj_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user has access to the project (owner or member)
    if not check_project_access(auth.user_id, project_id):
        logger.warning(
            f"❌ User {auth.user_id} attempted to delete API key for project {project_id} without access"
        )
        raise HTTPException(
            status_code=403, detail="You do not have access to this project"
        )

    # Get the API key
    api_key = mongo_db.api_keys.find_one(
        {"_id": key_obj_id, "projectId": project_obj_id}
    )

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found in this project")

    # Check permission: user must be key owner OR project admin
    is_owner = api_key["userId"] == user_obj_id
    is_admin = is_project_admin(mongo_db, project_obj_id, user_obj_id)

    if not (is_owner or is_admin):
        logger.warning(
            f"❌ User {auth.user_id} attempted to delete API key {key_id} without permission"
        )
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own API keys (or admin can delete any key)",
        )

    # Deactivate the API key (soft delete for audit trail)
    mongo_db.api_keys.update_one(
        {"_id": key_obj_id},
        {
            "$set": {
                "isActive": False,
                "deactivatedAt": utc_now(),
                "deactivatedBy": user_obj_id,
            }
        },
    )

    logger.info(
        f"✅ User {auth.user_id} deactivated API key {key_id} in project {project_id}"
    )

    return {
        "message": "API key deleted successfully",
        "key_id": key_id,
        "key_prefix": api_key.get("keyPrefix", "sk_im_..."),
    }
