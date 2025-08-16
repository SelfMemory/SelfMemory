"""
InMemory - Enhanced Memory Management Package

A comprehensive memory management system with rich metadata, temporal data,
and advanced search capabilities.
"""

__version__ = "0.1.0"
__author__ = "InMemory Team"

# Import main classes for easy access
from .services.add_memory import EnhancedMemoryManager, add_memory_enhanced
from .search.enhanced_search_engine import EnhancedSearchEngine
from .repositories.mongodb_user_manager import MongoUserManager

__all__ = [
    "EnhancedMemoryManager",
    "add_memory_enhanced", 
    "EnhancedSearchEngine",
    "MongoUserManager",
]
