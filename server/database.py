"""
Database initialization and schema management for selfmemory-core server.

This module handles:
- MongoDB connection management
- Creation of new collections for memory sharing functionality
- Index creation for optimal query performance
- Database schema validation

Following Uncle Bob's clean code principles:
- Single Responsibility: Each function has one clear purpose
- No mock data or fallback mechanisms
- Clear error handling without hiding failures
"""

import logging

from pymongo import ASCENDING, IndexModel, MongoClient
from pymongo.errors import CollectionInvalid, OperationFailure

from .config import config
from .utils.datetime_helpers import utc_now, utc_to_iso

logger = logging.getLogger(__name__)

# MongoDB client and database connection
# Initialized on module import
mongo_client = MongoClient(
    config.database.URI,
    serverSelectionTimeoutMS=config.database.TIMEOUT * 1000,
    maxPoolSize=config.database.MAX_POOL_SIZE,
    retryWrites=config.database.RETRY_WRITES,
    w=config.database.WRITE_CONCERN,
)

# Get database instance
mongo_db = mongo_client.get_default_database()

logger.info(f"✅ Connected to MongoDB: {config.database.URI}")


def create_organization_members_collection(db) -> bool:
    """
    Create organization_members collection with proper indexes.

    Purpose: Track which users belong to which organizations with their roles.

    Fields:
    - organizationId: ObjectId (reference to organizations)
    - userId: ObjectId (reference to users)
    - role: String enum ["owner", "admin", "member"]
    - invitedBy: ObjectId (reference to users)
    - joinedAt: Date
    - status: String enum ["active"]

    Indexes:
    - Compound unique: {organizationId: 1, userId: 1}
    - Single: {userId: 1}

    Args:
        db: MongoDB database instance

    Returns:
        bool: True if collection created successfully

    Raises:
        OperationFailure: If index creation fails
    """
    collection_name = "organization_members"

    try:
        # Create collection if it doesn't exist
        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name)
            logger.info(f"✅ Created collection: {collection_name}")
        else:
            logger.info(f"ℹ️  Collection already exists: {collection_name}")

        # Define indexes
        indexes = [
            IndexModel(
                [("organizationId", ASCENDING), ("userId", ASCENDING)],
                unique=True,
                name="org_user_unique",
            ),
            IndexModel([("userId", ASCENDING)], name="user_idx"),
        ]

        # Create indexes
        collection = db[collection_name]
        collection.create_indexes(indexes)
        logger.info(f"✅ Created indexes for {collection_name}")

        return True

    except CollectionInvalid as e:
        logger.error(f"❌ Failed to create collection {collection_name}: {e}")
        raise
    except OperationFailure as e:
        logger.error(f"❌ Failed to create indexes for {collection_name}: {e}")
        raise


def create_project_members_collection(db) -> bool:
    """
    Create project_members collection with proper indexes.

    Purpose: Track which users have access to which projects and their roles.

    Fields:
    - projectId: ObjectId (reference to projects)
    - userId: ObjectId (reference to users)
    - organizationId: ObjectId (for quick org-level queries)
    - role: String enum ["admin", "editor", "viewer"]
    - permissions: Object
      - canRead: Boolean
      - canWrite: Boolean
      - canDelete: Boolean
      - canInvite: Boolean
    - addedBy: ObjectId (reference to users)
    - addedAt: Date

    Role Permissions Mapping:
    - Admin:   { canRead: true, canWrite: true, canDelete: true, canInvite: true }
    - Editor:  { canRead: true, canWrite: true, canDelete: true, canInvite: false }
    - Viewer:  { canRead: true, canWrite: false, canDelete: false, canInvite: false }

    Indexes:
    - Compound unique: {projectId: 1, userId: 1}
    - Compound: {userId: 1, organizationId: 1}
    - Single: {projectId: 1}

    Args:
        db: MongoDB database instance

    Returns:
        bool: True if collection created successfully

    Raises:
        OperationFailure: If index creation fails
    """
    collection_name = "project_members"

    try:
        # Create collection if it doesn't exist
        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name)
            logger.info(f"✅ Created collection: {collection_name}")
        else:
            logger.info(f"ℹ️  Collection already exists: {collection_name}")

        # Define indexes
        indexes = [
            IndexModel(
                [("projectId", ASCENDING), ("userId", ASCENDING)],
                unique=True,
                name="project_user_unique",
            ),
            IndexModel(
                [("userId", ASCENDING), ("organizationId", ASCENDING)],
                name="user_org_idx",
            ),
            IndexModel([("projectId", ASCENDING)], name="project_idx"),
        ]

        # Create indexes
        collection = db[collection_name]
        collection.create_indexes(indexes)
        logger.info(f"✅ Created indexes for {collection_name}")

        return True

    except CollectionInvalid as e:
        logger.error(f"❌ Failed to create collection {collection_name}: {e}")
        raise
    except OperationFailure as e:
        logger.error(f"❌ Failed to create indexes for {collection_name}: {e}")
        raise


def create_invitations_collection(db) -> bool:
    """
    Create invitations collection with proper indexes.

    Purpose: Manage email invitations to organizations and projects.

    Fields:
    - email: String (email address being invited)
    - organizationId: ObjectId (reference to organizations)
    - projectId: ObjectId | null (null = org-only invite, value = project invite)
    - invitedBy: ObjectId (reference to users)
    - role: String enum ["admin", "editor", "viewer"]
    - token: String (secure random token for invitation link)
    - status: String enum ["pending", "accepted", "expired"]
    - expiresAt: Date (24 hours from creation)
    - createdAt: Date

    Indexes:
    - Single unique: {token: 1}
    - Compound: {email: 1, status: 1}
    - Single: {expiresAt: 1} (for cleanup)

    Args:
        db: MongoDB database instance

    Returns:
        bool: True if collection created successfully

    Raises:
        OperationFailure: If index creation fails
    """
    collection_name = "invitations"

    try:
        # Create collection if it doesn't exist
        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name)
            logger.info(f"✅ Created collection: {collection_name}")
        else:
            logger.info(f"ℹ️  Collection already exists: {collection_name}")

        # Define indexes
        indexes = [
            IndexModel([("token", ASCENDING)], unique=True, name="token_unique"),
            IndexModel(
                [("email", ASCENDING), ("status", ASCENDING)], name="email_status_idx"
            ),
            IndexModel([("expiresAt", ASCENDING)], name="expiration_idx"),
        ]

        # Create indexes
        collection = db[collection_name]
        collection.create_indexes(indexes)
        logger.info(f"✅ Created indexes for {collection_name}")

        return True

    except CollectionInvalid as e:
        logger.error(f"❌ Failed to create collection {collection_name}: {e}")
        raise
    except OperationFailure as e:
        logger.error(f"❌ Failed to create indexes for {collection_name}: {e}")
        raise


def create_api_keys_indexes(db) -> bool:
    """
    Create indexes for api_keys collection to optimize authentication queries.

    Purpose: Improve API key verification performance by indexing key prefix lookups.

    Indexes:
    - Compound: {keyPrefix: 1, isActive: 1} - Optimizes auth query with both fields
    - Single: {userId: 1} - For user-specific key queries
    - Single: {projectId: 1} - For project-specific key queries

    Args:
        db: MongoDB database instance

    Returns:
        bool: True if indexes created successfully

    Raises:
        OperationFailure: If index creation fails
    """
    collection_name = "api_keys"

    try:
        if collection_name not in db.list_collection_names():
            logger.warning(f"⚠️  Collection {collection_name} does not exist yet")
            return False

        # Define indexes
        indexes = [
            IndexModel(
                [("keyPrefix", ASCENDING), ("isActive", ASCENDING)],
                name="keyprefix_active_idx",
            ),
            IndexModel([("userId", ASCENDING)], name="user_idx"),
            IndexModel([("projectId", ASCENDING)], name="project_idx"),
        ]

        # Create indexes
        collection = db[collection_name]
        collection.create_indexes(indexes)
        logger.info(f"✅ Created indexes for {collection_name}")

        return True

    except OperationFailure as e:
        logger.error(f"❌ Failed to create indexes for {collection_name}: {e}")
        raise


def verify_api_keys_schema(db) -> bool:
    """
    Verify api_keys collection has required fields for project-scoped keys.

    The api_keys collection should have:
    - projectId: ObjectId (REQUIRED - makes key project-specific)
    - organizationId: ObjectId (for quick org-level queries)

    This function doesn't modify existing data, only verifies schema expectations.

    Args:
        db: MongoDB database instance

    Returns:
        bool: True if schema is valid
    """
    collection_name = "api_keys"

    try:
        if collection_name not in db.list_collection_names():
            logger.warning(f"⚠️  Collection {collection_name} does not exist yet")
            return False

        collection = db[collection_name]

        # Check if any documents have the required fields
        sample_doc = collection.find_one({"projectId": {"$exists": True}})

        if sample_doc:
            logger.info(f"✅ Collection {collection_name} has projectId field")
        else:
            logger.info(
                f"ℹ️  Collection {collection_name} exists but no documents with projectId yet"
            )

        return True

    except Exception as e:
        logger.error(f"❌ Error verifying {collection_name} schema: {e}")
        raise


def initialize_database_schema(db) -> dict:
    """
    Initialize all required collections and indexes for memory sharing.

    This is the main entry point for Phase 1: Database Foundation.
    Creates all new collections with proper indexes.

    Args:
        db: MongoDB database instance

    Returns:
        dict: Status report of initialization

    Raises:
        Exception: If any critical operation fails
    """
    results = {
        "timestamp": utc_to_iso(utc_now()),
        "collections_created": [],
        "collections_existed": [],
        "indexes_created": True,
        "errors": [],
    }

    logger.info("🚀 Starting database schema initialization for Phase 1...")

    try:
        # Create organization_members collection
        create_organization_members_collection(db)
        results["collections_created"].append("organization_members")

        # Create project_members collection
        create_project_members_collection(db)
        results["collections_created"].append("project_members")

        # Create invitations collection
        create_invitations_collection(db)
        results["collections_created"].append("invitations")

        # Create indexes for api_keys collection
        create_api_keys_indexes(db)

        # Verify api_keys schema
        verify_api_keys_schema(db)

        logger.info("✅ Database schema initialization completed successfully")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        results["errors"].append(str(e))
        raise

    return results


def get_role_permissions(role: str) -> dict:
    """
    Get permission mapping for a given project role.

    Role Permissions Mapping:
    - Admin:   { canRead: true, canWrite: true, canDelete: true, canInvite: true }
    - Editor:  { canRead: true, canWrite: true, canDelete: true, canInvite: false }
    - Viewer:  { canRead: true, canWrite: false, canDelete: false, canInvite: false }

    Args:
        role: Role string (admin, editor, or viewer)

    Returns:
        dict: Permission mapping

    Raises:
        ValueError: If role is invalid
    """
    permissions_map = {
        "admin": {
            "canRead": True,
            "canWrite": True,
            "canDelete": True,
            "canInvite": True,
        },
        "editor": {
            "canRead": True,
            "canWrite": True,
            "canDelete": True,
            "canInvite": False,
        },
        "viewer": {
            "canRead": True,
            "canWrite": False,
            "canDelete": False,
            "canInvite": False,
        },
    }

    role_lower = role.lower()
    if role_lower not in permissions_map:
        raise ValueError(f"Invalid role: {role}. Must be one of: admin, editor, viewer")

    return permissions_map[role_lower]
