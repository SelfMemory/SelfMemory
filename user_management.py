"""
User Management for Multi-User Memory MCP Server.
Handles user validation, collection naming, and user-specific operations.
"""

import json
import logging
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class UserManager:
    """Manages user validation and collection naming for multi-user support."""
    
    def __init__(self, users_file: str = "users.json"):
        """
        Initialize user manager with users file.
        
        Args:
            users_file: Path to JSON file containing approved users
        """
        self.users_file = Path(users_file)
        self._load_users()
    
    def _load_users(self) -> None:
        """Load approved users from JSON file."""
        try:
            if not self.users_file.exists():
                logger.error(f"Users file not found: {self.users_file}")
                self.approved_users = []
                return
            
            with open(self.users_file, 'r') as f:
                data = json.load(f)
                self.approved_users = data.get('alpha_users', [])
            
            logger.info(f"Loaded {len(self.approved_users)} approved users")
        except Exception as e:
            logger.error(f"Failed to load users file: {str(e)}")
            self.approved_users = []
    
    def is_valid_user(self, user_id: str) -> bool:
        """
        Check if user_id is in approved users list.
        
        Args:
            user_id: User identifier to validate
            
        Returns:
            bool: True if user is approved for alpha testing
        """
        if not user_id or not isinstance(user_id, str):
            return False
        
        # Basic validation: alphanumeric and underscores only
        if not user_id.replace('_', '').isalnum():
            logger.warning(f"Invalid user_id format: {user_id}")
            return False
        
        is_valid = user_id.lower() in [u.lower() for u in self.approved_users]
        if not is_valid:
            logger.warning(f"Unauthorized user_id: {user_id}")
        
        return is_valid
    
    def get_collection_name(self, user_id: str) -> str:
        """
        Get Qdrant collection name for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            str: Collection name for this user
        """
        if not self.is_valid_user(user_id):
            raise ValueError(f"Invalid or unauthorized user_id: {user_id}")
        
        return f"memories_{user_id.lower()}"
    
    def get_approved_users(self) -> List[str]:
        """
        Get list of all approved users.
        
        Returns:
            List[str]: List of approved user IDs
        """
        return self.approved_users.copy()
    
    def add_user(self, user_id: str) -> bool:
        """
        Add new user to approved list (for future web-based registration).
        
        Args:
            user_id: User identifier to add
            
        Returns:
            bool: True if user was added successfully
        """
        try:
            if user_id.lower() in [u.lower() for u in self.approved_users]:
                logger.info(f"User {user_id} already exists")
                return True
            
            # Basic validation
            if not user_id.replace('_', '').isalnum():
                logger.error(f"Invalid user_id format: {user_id}")
                return False
            
            self.approved_users.append(user_id.lower())
            
            # Save back to file
            data = {
                "alpha_users": self.approved_users,
                "description": "Static list of approved alpha testers. Each user gets their own Qdrant collection: memories_{user_id}",
                "created": "2025-01-31", 
                "version": "1.0"
            }
            
            with open(self.users_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Added new user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add user {user_id}: {str(e)}")
            return False
    
    def reload_users(self) -> None:
        """Reload users from file (for runtime updates)."""
        self._load_users()


# Global user manager instance
user_manager = UserManager()
