"""
Repositories module for data persistence and user management.

Contains database access layers and user management functionality.
"""

from .mongodb_user_manager import MongoUserManager, initialize_mongo_user_manager, get_mongo_user_manager
from .qdrant_db import ensure_user_collection_exists, get_qdrant_client, delete_user_memory

__all__ = [
    "MongoUserManager",
    "initialize_mongo_user_manager",
    "get_mongo_user_manager",
    "ensure_user_collection_exists",
    "get_qdrant_client",
    "delete_user_memory",
]
