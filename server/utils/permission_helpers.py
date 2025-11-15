"""
Permission Helper Functions

Shared permission check functions following Uncle Bob's Clean Code principles:
- No duplication (DRY)
- Single responsibility
- Clear, meaningful names
- Explicit error handling

These functions are used across multiple route files to check permissions.
"""

import logging

from bson import ObjectId
from pymongo.database import Database

logger = logging.getLogger(__name__)


def get_project_member(
    db: Database, project_id: ObjectId, user_id: ObjectId
) -> dict | None:
    """
    Get project member record for a user.

    Args:
        db: MongoDB database instance
        project_id: Project ObjectId
        user_id: User ObjectId

    Returns:
        dict: Project member record or None if not found
    """
    return db.project_members.find_one({"projectId": project_id, "userId": user_id})


def is_project_admin(db: Database, project_id: ObjectId, user_id: ObjectId) -> bool:
    """
    Check if user is an admin of the project OR the project owner.

    Project admins and owners have full control over the project.

    Args:
        db: MongoDB database instance
        project_id: Project ObjectId
        user_id: User ObjectId

    Returns:
        bool: True if user is admin or owner, False otherwise
    """
    # First check if user is the project owner (owners have implicit admin rights)
    project = db.projects.find_one({"_id": project_id})
    if project and str(project["ownerId"]) == str(user_id):
        return True

    # Then check if user is a project admin member
    member = get_project_member(db, project_id, user_id)
    return member is not None and member.get("role") == "admin"


def count_project_admins(db: Database, project_id: ObjectId) -> int:
    """
    Count number of admins in a project.

    Note: This only counts admin members, not the project owner.
    Used to ensure we don't remove the last admin.

    Args:
        db: MongoDB database instance
        project_id: Project ObjectId

    Returns:
        int: Number of admin members (excluding owner)
    """
    return db.project_members.count_documents(
        {"projectId": project_id, "role": "admin"}
    )


def get_organization_member(
    db: Database, organization_id: ObjectId, user_id: ObjectId
) -> dict | None:
    """
    Get organization member record for a user.

    Args:
        db: MongoDB database instance
        organization_id: Organization ObjectId
        user_id: User ObjectId

    Returns:
        dict: Organization member record or None if not found
    """
    return db.organization_members.find_one(
        {"organizationId": organization_id, "userId": user_id, "status": "active"}
    )


def is_organization_admin(
    db: Database, organization_id: ObjectId, user_id: ObjectId
) -> bool:
    """
    Check if user is an admin or owner of the organization.

    Organization admins and owners have full control over the organization.

    Args:
        db: MongoDB database instance
        organization_id: Organization ObjectId
        user_id: User ObjectId

    Returns:
        bool: True if user is admin or owner, False otherwise
    """
    # Check if user is the organization owner
    organization = db.organizations.find_one({"_id": organization_id})
    if organization and str(organization["ownerId"]) == str(user_id):
        return True

    # Check if user is an admin member
    member = get_organization_member(db, organization_id, user_id)
    return member is not None and member.get("role") in ["owner", "admin"]


def count_organization_admins(db: Database, organization_id: ObjectId) -> int:
    """
    Count number of admins (including owner) in an organization.

    Used to ensure we don't remove the last admin.

    Args:
        db: MongoDB database instance
        organization_id: Organization ObjectId

    Returns:
        int: Number of admin members
    """
    return db.organization_members.count_documents(
        {
            "organizationId": organization_id,
            "role": {"$in": ["owner", "admin"]},
            "status": "active",
        }
    )


def is_organization_member(
    db: Database, organization_id: ObjectId, user_id: ObjectId
) -> bool:
    """
    Check if user is a member of the organization.

    Args:
        db: MongoDB database instance
        organization_id: Organization ObjectId
        user_id: User ObjectId

    Returns:
        bool: True if user is a member, False otherwise
    """
    member = get_organization_member(db, organization_id, user_id)
    return member is not None


def get_user_by_email(db: Database, email: str) -> dict | None:
    """
    Find user by email address.

    Args:
        db: MongoDB database instance
        email: User email address

    Returns:
        dict: User record or None if not found
    """
    return db.users.find_one({"email": email})


def get_user_object_id_from_kratos_id(db: Database, kratos_id: str) -> ObjectId | str:
    """
    Resolve Kratos identity ID to user's MongoDB document ID.

    After migration, user_id IS the Kratos UUID (stored in _id field).
    During migration transition, this supports both formats:
    - New: _id = Kratos UUID (post-migration)
    - Legacy: kratosId field with separate ObjectId _id (pre-migration)

    Args:
        db: MongoDB database instance
        kratos_id: Kratos identity ID (UUID string)

    Returns:
        ObjectId or str: User's _id (ObjectId for legacy, UUID string for migrated)

    Raises:
        ValueError: If user not found for the given Kratos ID
    """
    # Check both legacy and new formats
    user = db.users.find_one(
        {
            "$or": [
                {"_id": kratos_id},  # Post-migration: _id is Kratos UUID
                {"kratosId": kratos_id},  # Pre-migration: separate kratosId field
            ]
        }
    )

    if not user:
        logger.error(f"User not found for Kratos ID: {kratos_id}")
        raise ValueError(f"User not found for Kratos ID: {kratos_id}")

    return user["_id"]


def get_user_by_kratos_id(db: Database, kratos_id: str) -> dict:
    """
    Get user document by Kratos ID (handles both new and legacy formats).

    During migration period, this checks both kratosId and _id fields to support
    users created before and after the Kratos migration.

    Args:
        db: MongoDB database instance
        kratos_id: Kratos identity ID (UUID string)

    Returns:
        dict: User document

    Raises:
        ValueError: If user not found
    """
    # TODO [MIGRATION]: After production migration complete, simplify to:
    # user = db.users.find_one({"kratosId": kratos_id})
    # This dual-format lookup is temporary for migration compatibility.
    user = db.users.find_one({"$or": [{"kratosId": kratos_id}, {"_id": kratos_id}]})

    if not user:
        logger.error(f"User not found for Kratos ID: {kratos_id}")
        raise ValueError(f"User not found for Kratos ID: {kratos_id}")

    return user


def is_owner(resource: dict, kratos_id: str, mongo_user_id: ObjectId) -> bool:
    """
    Check if user owns a resource (handles both ID formats during migration).

    During the Kratos migration period, ownerId can be either:
    - Kratos UUID string (new format)
    - MongoDB ObjectId (legacy format)

    This helper ensures consistent ownership checks across the codebase.

    Args:
        resource: Resource document (organization, project, etc.) with ownerId field
        kratos_id: User's Kratos identity ID (UUID string)
        mongo_user_id: User's MongoDB ObjectId

    Returns:
        bool: True if user owns the resource, False otherwise
    """
    # TODO [MIGRATION]: After production migration complete, simplify to:
    # return resource.get("ownerId") == kratos_id
    # This dual-format check is temporary for migration compatibility.
    owner_id = resource.get("ownerId")
    return owner_id in (kratos_id, mongo_user_id)
