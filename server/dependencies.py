"""
Shared dependencies for the server.

This module contains authentication, database connections, and other
shared dependencies to avoid circular imports.
"""

import hashlib
import logging
from typing import NamedTuple

from fastapi import Header, HTTPException

from .config import config
from .database import mongo_db
from .utils.crypto import verify_api_key
from .utils.datetime_helpers import is_expired, utc_now
from .utils.validators import validate_object_id

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================


class ProjectPermissions(NamedTuple):
    """User's permissions in a project."""

    canRead: bool
    canWrite: bool
    canDelete: bool
    canInvite: bool


# Default denied permissions - fail-closed approach
DENIED_PERMISSIONS = ProjectPermissions(
    canRead=False, canWrite=False, canDelete=False, canInvite=False
)


# Full access permissions (for owners and admins)
FULL_PERMISSIONS = ProjectPermissions(
    canRead=True, canWrite=True, canDelete=True, canInvite=True
)


class AuthContext(NamedTuple):
    """Authentication context for multi-tenant support."""

    user_id: str
    project_id: str | None = None
    organization_id: str | None = None
    permissions: ProjectPermissions = (
        DENIED_PERMISSIONS  # User's permissions in the project (defaults to denied)
    )


# ============================================================================
# Permission Checking Helper Functions
# ============================================================================


def check_project_access(user_id: str, project_id: str) -> bool:
    """
    Check if a user has access to a project.

    A user has access if:
    - They are the organization owner (implicit full access), OR
    - They are the project owner, OR
    - They are a member in project_members collection

    Args:
        user_id: User ID string
        project_id: Project ID string

    Returns:
        bool: True if user has access, False otherwise
    """
    try:
        user_obj_id = validate_object_id(user_id, "user_id")
        project_obj_id = validate_object_id(project_id, "project_id")

        # Get project to check organization ownership
        project = mongo_db.projects.find_one({"_id": project_obj_id})
        if not project:
            return False

        # Check if user is the organization owner (implicit full access)
        organization = mongo_db.organizations.find_one(
            {"_id": project["organizationId"]}
        )
        if organization and organization.get("ownerId") == user_obj_id:
            return True

        # Check if user owns the project
        if project.get("ownerId") == user_obj_id:
            return True

        # Check if user is a member
        member = mongo_db.project_members.find_one(
            {"projectId": project_obj_id, "userId": user_obj_id}
        )

        return member is not None

    except Exception as e:
        logger.error(f"Error checking project access: {e}")
        return False


def get_user_permissions(user_id: str, project_id: str) -> ProjectPermissions:
    """
    Get a user's permissions for a specific project.

    FAIL-CLOSED APPROACH: Always returns ProjectPermissions. Returns DENIED_PERMISSIONS
    if user has no access. Never returns None to prevent NoneType errors.

    Returns full permissions for organization owners (implicit admin access),
    or permissions from project_members if user is a member,
    or full permissions if user is the project owner.

    Args:
        user_id: User ID string
        project_id: Project ID string

    Returns:
        ProjectPermissions: User's permissions (DENIED_PERMISSIONS if no access)
    """
    try:
        user_obj_id = validate_object_id(user_id, "user_id")
        project_obj_id = validate_object_id(project_id, "project_id")

        # Get project to check organization ownership
        project = mongo_db.projects.find_one({"_id": project_obj_id})
        if not project:
            logger.warning(f"Project not found: {project_id}")
            return DENIED_PERMISSIONS

        # Check if user is the organization owner (implicit full access)
        organization = mongo_db.organizations.find_one(
            {"_id": project["organizationId"]}
        )
        if organization and organization.get("ownerId") == user_obj_id:
            return FULL_PERMISSIONS

        # Check if user owns the project (owner has all permissions)
        if project.get("ownerId") == user_obj_id:
            return FULL_PERMISSIONS

        # Get permissions from project_members
        member = mongo_db.project_members.find_one(
            {"projectId": project_obj_id, "userId": user_obj_id}
        )

        if not member:
            logger.info(f"User {user_id} is not a member of project {project_id}")
            return DENIED_PERMISSIONS

        perms = member.get("permissions", {})
        return ProjectPermissions(
            canRead=perms.get("canRead", False),
            canWrite=perms.get("canWrite", False),
            canDelete=perms.get("canDelete", False),
            canInvite=perms.get("canInvite", False),
        )

    except Exception as e:
        logger.error(f"Error getting user permissions: {e}")
        return DENIED_PERMISSIONS


def has_permission(user_id: str, project_id: str, permission: str) -> bool:
    """
    Check if a user has a specific permission in a project.

    FAIL-CLOSED APPROACH: Returns False if permission is not found or user has no access.

    Args:
        user_id: User ID string
        project_id: Project ID string
        permission: Permission to check (e.g., "canRead", "canWrite", "canDelete", "canInvite")

    Returns:
        bool: True if user has the permission, False otherwise
    """
    permissions = get_user_permissions(user_id, project_id)

    # Map permission string to attribute
    permission_map = {
        "canRead": permissions.canRead,
        "canWrite": permissions.canWrite,
        "canDelete": permissions.canDelete,
        "canInvite": permissions.canInvite,
        "read": permissions.canRead,
        "write": permissions.canWrite,
        "delete": permissions.canDelete,
        "invite": permissions.canInvite,
    }

    return permission_map.get(permission, False)


def is_project_admin(user_id: str, project_id: str) -> bool:
    """
    Check if a user is an admin of a project.

    A user is an admin if:
    - They are the project owner, OR
    - They have the "admin" role in project_members

    Args:
        user_id: User ID string
        project_id: Project ID string

    Returns:
        bool: True if user is admin, False otherwise
    """
    try:
        user_obj_id = validate_object_id(user_id, "user_id")
        project_obj_id = validate_object_id(project_id, "project_id")

        # Check if user owns the project
        project = mongo_db.projects.find_one({"_id": project_obj_id})
        if project and project.get("ownerId") == user_obj_id:
            return True

        # Check if user has admin role in project_members
        member = mongo_db.project_members.find_one(
            {"projectId": project_obj_id, "userId": user_obj_id, "role": "admin"}
        )

        return member is not None

    except Exception as e:
        logger.error(f"Error checking project admin status: {e}")
        return False


# ============================================================================
# Authentication Middleware
# ============================================================================


def authenticate_api_key(authorization: str = Header(None)) -> AuthContext:
    """Database-based authentication - supports both API key (Bearer) and Session auth.

    - Bearer token: For SDK/API users with project-scoped API keys
    - Session auth: For dashboard users authenticated via NextAuth
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Handle Session authentication (dashboard users)
    if authorization.startswith("Session "):
        user_id = authorization.replace("Session ", "")

        # Validate and convert user_id
        user_obj_id = validate_object_id(user_id, "user_id")

        # Validate user exists and is active
        user = mongo_db.users.find_one({"_id": user_obj_id})

        if not user:
            logger.warning(f"❌ Session auth: User not found: {user_id}")
            raise HTTPException(
                status_code=401, detail="Invalid session - user not found"
            )

        if not user.get("isActive", True):
            logger.warning(
                f"❌ Session auth: Inactive user attempted access: {user_id}"
            )
            raise HTTPException(status_code=401, detail="User account inactive")

        logger.info(f"✅ Session auth validated for user: {user.get('email', user_id)}")

        # For session auth, project context comes from request parameters
        # Return AuthContext without project context - will be extracted by endpoint
        return AuthContext(
            user_id=user_id,
            project_id=None,  # Will be set by endpoint from request params
            organization_id=None,  # Will be set by endpoint from request params
        )

    # Handle API Key authentication (SDK users)
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must start with 'Bearer ' or 'Session '",
        )

    api_key = authorization.replace("Bearer ", "")

    # Accept only format: sk_im_
    if not api_key.startswith("sk_im_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    try:
        # Find all active API keys with matching prefix for efficiency
        key_prefix = api_key[:10] + "..."
        potential_keys_cursor = mongo_db.api_keys.find(
            {"keyPrefix": key_prefix, "isActive": True}
        ).limit(100)

        # Convert cursor to list and check count for monitoring
        potential_keys = list(potential_keys_cursor)

        # Security: Hash prefix before logging to avoid leaking sensitive info
        # Note: SHA256 is appropriate here as it's only for logging collision warnings,
        # not for password hashing. API key verification uses Argon2.
        if len(potential_keys) > config.auth.COLLISION_WARNING_THRESHOLD:
            hashed_prefix = hashlib.sha256(key_prefix.encode()).hexdigest()[:8]
            logger.warning(
                f"⚠️  High API key prefix collision: {len(potential_keys)} keys (prefix hash: {hashed_prefix})"
            )

        # Performance: Limit expensive Argon2 hash verifications
        checked_count = 0
        stored_key = None
        for candidate in potential_keys[: config.auth.MAX_HASH_VERIFICATIONS]:
            checked_count += 1
            if verify_api_key(api_key, candidate["keyHash"]):
                stored_key = candidate
                break

        if not stored_key:
            if len(potential_keys) > config.auth.MAX_HASH_VERIFICATIONS:
                logger.error(
                    f"❌ Auth failed after {checked_count} hash verifications. "
                    f"Total candidates: {len(potential_keys)}. Possible attack or system issue."
                )
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Check if key is expired
        if stored_key.get("expiresAt") and is_expired(stored_key["expiresAt"]):
            logger.warning(
                f"❌ Expired API key attempted: {stored_key.get('keyPrefix', 'unknown')}"
            )
            raise HTTPException(status_code=401, detail="API key expired")

        # Get user to verify it's active
        user = mongo_db.users.find_one({"_id": stored_key["userId"]})

        if not user or not user.get("isActive", True):
            logger.warning(
                f"❌ API key belongs to inactive user: {stored_key['userId']}"
            )
            raise HTTPException(status_code=401, detail="User account inactive")

        # Extract multi-tenant context from API key
        user_id = str(stored_key["userId"])
        project_id = None
        organization_id = None

        # Get project context if API key has projectId (Phase 6 enhancement)
        permissions = None
        if stored_key.get("projectId"):
            project = mongo_db.projects.find_one({"_id": stored_key["projectId"]})
            if project:
                project_id = str(project["_id"])
                organization_id = str(project["organizationId"])

                # PHASE 6 ENHANCEMENT: Verify user still has project access
                # Check project membership (not just ownership)
                if not check_project_access(user_id, project_id):
                    logger.warning(
                        f"❌ User {user_id} no longer has access to project {project_id}"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Access denied - project membership revoked",
                    )

                # PHASE 6 ENHANCEMENT: Get user's permissions from project_members
                permissions = get_user_permissions(user_id, project_id)
                # Check if user has any permissions (not all denied)
                if permissions == DENIED_PERMISSIONS:
                    logger.warning(
                        f"❌ User {user_id} has no permissions for project {project_id}"
                    )
                    raise HTTPException(
                        status_code=403, detail="Access denied - no project permissions"
                    )

                logger.info(
                    f"✅ Multi-tenant auth: user={user.get('email', user_id)}, "
                    f"project={project_id}, org={organization_id}, "
                    f"permissions={permissions}"
                )
            else:
                logger.warning(
                    f"❌ API key references non-existent project: {stored_key['projectId']}"
                )
                raise HTTPException(status_code=404, detail="Project not found")
        else:
            # Backward compatibility: API key without project context
            logger.info(
                f"✅ Legacy context: user={user.get('email', user_id)} (no project context)"
            )

        # Update last used timestamp
        mongo_db.api_keys.update_one(
            {"_id": stored_key["_id"]}, {"$set": {"lastUsed": utc_now()}}
        )

        return AuthContext(
            user_id=user_id,
            project_id=project_id,
            organization_id=organization_id,
            permissions=permissions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API key authentication error: {e}")
        raise HTTPException(status_code=500, detail="Authentication error") from e
