"""
Permission checking dependencies for FastAPI routes.

This module provides reusable permission checking dependencies to avoid
code duplication across routes. Uses FastAPI's Depends() system.
"""

import logging

from bson import ObjectId
from fastapi import Depends, HTTPException

from ..dependencies import AuthContext, authenticate_api_key, mongo_db
from ..utils.permission_helpers import (
    count_project_admins,
    get_user_object_id_from_kratos_id,
    is_organization_member,
    is_project_admin,
)
from ..utils.validators import validate_object_id

logger = logging.getLogger(__name__)


# ============================================================================
# Permission Check Dependencies
# ============================================================================


class ProjectAdminRequired:
    """
    Dependency to verify user is a project admin.

    Usage:
        @router.post("/{project_id}/members")
        def add_member(
            project_id: str,
            auth: AuthContext = Depends(authenticate_api_key),
            _: None = Depends(ProjectAdminRequired("project_id"))
        ):
            # User is verified as project admin at this point
            ...
    """

    def __init__(self, project_id_param: str = "project_id"):
        """
        Initialize the dependency.

        Args:
            project_id_param: Name of the path parameter containing project_id
        """
        self.project_id_param = project_id_param

    def __call__(
        self,
        project_id: str,
        auth: AuthContext = Depends(authenticate_api_key),
    ) -> None:
        """
        Verify user is a project admin.

        Args:
            project_id: Project ID from path parameter
            auth: Authentication context

        Raises:
            HTTPException: If user is not a project admin
        """
        project_obj_id = validate_object_id(project_id, "project_id")
        user_obj_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)

        if not is_project_admin(mongo_db, project_obj_id, user_obj_id):
            logger.warning(
                f"Permission denied: User {auth.user_id} is not admin of project {project_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Only project admins can perform this action",
            )

        logger.debug(
            f"Permission granted: User {auth.user_id} is admin of project {project_id}"
        )


class OrganizationMemberRequired:
    """
    Dependency to verify user is an organization member.

    Usage:
        @router.get("/organizations/{org_id}/projects")
        def list_projects(
            org_id: str,
            auth: AuthContext = Depends(authenticate_api_key),
            _: None = Depends(OrganizationMemberRequired("org_id"))
        ):
            # User is verified as org member at this point
            ...
    """

    def __init__(self, org_id_param: str = "organization_id"):
        """
        Initialize the dependency.

        Args:
            org_id_param: Name of the path parameter containing organization_id
        """
        self.org_id_param = org_id_param

    def __call__(
        self,
        organization_id: str,
        auth: AuthContext = Depends(authenticate_api_key),
    ) -> None:
        """
        Verify user is an organization member.

        Args:
            organization_id: Organization ID from path parameter
            auth: Authentication context

        Raises:
            HTTPException: If user is not an organization member
        """
        org_obj_id = validate_object_id(organization_id, "organization_id")
        user_obj_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)

        if not is_organization_member(mongo_db, org_obj_id, user_obj_id):
            logger.warning(
                f"Permission denied: User {auth.user_id} is not member of org {organization_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Only organization members can perform this action",
            )

        logger.debug(
            f"Permission granted: User {auth.user_id} is member of org {organization_id}"
        )


class PreventLastAdminRemoval:
    """
    Dependency to prevent removing/demoting the last project admin.

    Usage:
        @router.put("/{project_id}/members/{user_id}")
        def update_member_role(
            project_id: str,
            user_id: str,
            role_update: UpdateRole,
            auth: AuthContext = Depends(authenticate_api_key),
            _: None = Depends(PreventLastAdminRemoval("project_id", "user_id"))
        ):
            # Verified that this won't remove the last admin
            ...
    """

    def __init__(
        self,
        project_id_param: str = "project_id",
        user_id_param: str = "user_id",
    ):
        """
        Initialize the dependency.

        Args:
            project_id_param: Name of the path parameter containing project_id
            user_id_param: Name of the path parameter containing user_id
        """
        self.project_id_param = project_id_param
        self.user_id_param = user_id_param

    def __call__(
        self,
        project_id: str,
        user_id: str,
        auth: AuthContext = Depends(authenticate_api_key),
    ) -> None:
        """
        Verify this action won't remove the last admin.

        Args:
            project_id: Project ID from path parameter
            user_id: User ID being removed/demoted
            auth: Authentication context

        Raises:
            HTTPException: If this would remove the last admin
        """
        project_obj_id = validate_object_id(project_id, "project_id")
        target_user_obj_id = validate_object_id(user_id, "user_id")

        # Check if target user is currently an admin
        from ..utils.permission_helpers import get_project_member

        target_member = get_project_member(mongo_db, project_obj_id, target_user_obj_id)

        if target_member and target_member.get("role") == "admin":
            admin_count = count_project_admins(mongo_db, project_obj_id)
            if admin_count <= 1:
                logger.warning(
                    f"Permission denied: Cannot remove last admin from project {project_id}"
                )
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove or demote the last admin. Promote another member first.",
                )

        logger.debug(
            f"Permission granted: Action won't remove last admin from project {project_id}"
        )


# ============================================================================
# Helper Functions for Complex Permission Checks
# ============================================================================


def require_project_admin(project_id: str, auth: AuthContext) -> ObjectId:
    """
    Helper function to verify project admin permission and return project ObjectId.

    Use this in route handlers when you need the ObjectId for database queries.
    For simple permission checks, use ProjectAdminRequired dependency instead.

    Args:
        project_id: Project ID string
        auth: Authentication context

    Returns:
        ObjectId: Validated project ObjectId

    Raises:
        HTTPException: If user is not a project admin
    """
    project_obj_id = validate_object_id(project_id, "project_id")
    user_obj_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)

    if not is_project_admin(mongo_db, project_obj_id, user_obj_id):
        logger.warning(
            f"Permission denied: User {auth.user_id} is not admin of project {project_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Only project admins can perform this action",
        )

    logger.debug(
        f"Permission granted: User {auth.user_id} is admin of project {project_id}"
    )
    return project_obj_id


def require_organization_member(organization_id: str, auth: AuthContext) -> ObjectId:
    """
    Helper function to verify organization membership and return org ObjectId.

    Use this in route handlers when you need the ObjectId for database queries.
    For simple permission checks, use OrganizationMemberRequired dependency instead.

    Args:
        organization_id: Organization ID string
        auth: Authentication context

    Returns:
        ObjectId: Validated organization ObjectId

    Raises:
        HTTPException: If user is not an organization member
    """
    org_obj_id = validate_object_id(organization_id, "organization_id")
    user_obj_id = get_user_object_id_from_kratos_id(mongo_db, auth.user_id)

    if not is_organization_member(mongo_db, org_obj_id, user_obj_id):
        logger.warning(
            f"Permission denied: User {auth.user_id} is not member of org {organization_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Only organization members can perform this action",
        )

    logger.debug(
        f"Permission granted: User {auth.user_id} is member of org {organization_id}"
    )
    return org_obj_id
