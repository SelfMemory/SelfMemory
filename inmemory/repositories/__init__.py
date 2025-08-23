"""
Repositories module for data persistence and user management.

Contains database access layers and user management functionality.
"""

# Always available - Qdrant functionality
from .qdrant_db import (
    delete_user_memory,
    ensure_user_collection_exists,
    get_qdrant_client,
)

# Conditional imports for MongoDB features
try:
    from .mongodb_user_manager import (
        MongoUserManager,
        get_mongo_user_manager,
        initialize_mongo_user_manager,
    )

    _MONGODB_AVAILABLE = True
except ImportError:
    MongoUserManager = None
    get_mongo_user_manager = None
    initialize_mongo_user_manager = None
    _MONGODB_AVAILABLE = False

# Base exports - always available
__all__ = [
    "ensure_user_collection_exists",
    "get_qdrant_client",
    "delete_user_memory",
]

# Add MongoDB exports if available
if _MONGODB_AVAILABLE:
    __all__.extend(
        [
            "MongoUserManager",
            "initialize_mongo_user_manager",
            "get_mongo_user_manager",
        ]
    )
