"""
InMemory - Enhanced Memory Management Package

A comprehensive memory management system with rich metadata, temporal data,
and advanced search capabilities.
"""

__version__ = "0.1.1"
__author__ = "InMemory Team"

# Import main SDK classes - following mem0 pattern
from .client import (
    AsyncInmemoryClient,
    InmemoryClient,
)  # Managed solutions (like mem0.MemoryClient, mem0.AsyncMemoryClient)

# Import configuration classes
from .config import InMemoryConfig, load_config
from .memory import (
    AsyncMemory,
    Memory,
)  # Self-hosted solutions (like mem0.Memory, mem0.AsyncMemory)
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
    MongoUserManager = None
    _MONGODB_AVAILABLE = False

# Main SDK exports - following mem0 pattern exactly
__all__ = [
    # Primary SDK interfaces (mem0 pattern)
    "Memory",  # Self-hosted solution (like mem0.Memory)
    "AsyncMemory",  # Async self-hosted solution (like mem0.AsyncMemory)
    "InmemoryClient",  # Managed solution (like mem0.MemoryClient)
    "AsyncInmemoryClient",  # Async managed solution (like mem0.AsyncMemoryClient)
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
