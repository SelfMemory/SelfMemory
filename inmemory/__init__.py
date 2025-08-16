"""
InMemory - Enhanced Memory Management Package

A comprehensive memory management system with rich metadata, temporal data,
and advanced search capabilities.
"""

__version__ = "0.1.0"
__author__ = "InMemory Team"

# Import main SDK classes
from .client import AsyncInmry, Inmry  # Managed solution

# Import configuration classes
from .config import InMemoryConfig, load_config
from .memory import Memory  # Self-hosted solution
from .search.enhanced_search_engine import EnhancedSearchEngine

# Import existing classes for backward compatibility
from .services.add_memory import EnhancedMemoryManager, add_memory_enhanced

# Import storage interfaces (for advanced usage)
from .stores import MemoryStoreInterface, create_store

# Conditional imports for enterprise features
try:
    from .repositories.mongodb_user_manager import MongoUserManager

    _MONGODB_AVAILABLE = True
except ImportError:
    _MONGODB_AVAILABLE = False

# Main SDK exports
__all__ = [
    # Primary SDK interfaces
    "Memory",  # Self-hosted solution
    "Inmry",  # Managed solution
    "AsyncInmry",  # Async managed solution
    # Configuration
    "InMemoryConfig",
    "load_config",
    # Storage abstraction
    "MemoryStoreInterface",
    "create_store",
    # Backward compatibility
    "EnhancedMemoryManager",
    "add_memory_enhanced",
    "EnhancedSearchEngine",
]

# Add MongoDB exports if available
if _MONGODB_AVAILABLE:
    __all__.append("MongoUserManager")
