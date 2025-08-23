"""
Storage abstraction layer for InMemory.

This module provides a unified interface for different storage backends,
enabling the package to work with file-based storage (default) or
enterprise backends like MongoDB without requiring external dependencies.
"""

from .base import MemoryStoreInterface

# Always available - file-based storage
try:
    from .file_store import FileBasedStore

    _FILE_AVAILABLE = True
except ImportError:
    FileBasedStore = None
    _FILE_AVAILABLE = False

# Optional imports (only available with extras)
try:
    from .mongodb_store import MongoDBStore

    _MONGODB_AVAILABLE = True
except ImportError:
    _MONGODB_AVAILABLE = False


def create_store(storage_type: str = None, **config) -> MemoryStoreInterface:
    """
    Factory function to create storage backend instances.

    Args:
        storage_type: Type of storage backend ("file" or "mongodb")
                     If None, will be read from config['type']
        **config: Configuration parameters for the storage backend

    Returns:
        MemoryStoreInterface: Configured storage backend instance

    Raises:
        ImportError: If required dependencies are not installed
        ValueError: If unsupported storage type is specified
    """
    import logging

    logger = logging.getLogger(__name__)

    # Extract storage type from config if not provided as argument
    if storage_type is None:
        storage_type = config.pop("type", "file")
    else:
        # Remove 'type' from config to avoid duplicate
        config.pop("type", None)

    logger.info(
        f"Creating store: type='{storage_type}', MongoDB_available={_MONGODB_AVAILABLE}"
    )
    logger.info(f"Config received: {config}")

    if storage_type == "file":
        # FileBasedStore expects 'data_dir', not 'path'
        if "path" in config:
            config["data_dir"] = config.pop("path")
        # Only pass relevant config to FileBasedStore
        file_config = {k: v for k, v in config.items() if k in ["data_dir"]}
        logger.info(f"Creating FileBasedStore with config: {file_config}")
        return FileBasedStore(**file_config)
    if storage_type == "mongodb":
        if not _MONGODB_AVAILABLE:
            raise ImportError(
                "MongoDB storage requires additional dependencies. "
                "Install with: pip install inmemory[mongodb] or inmemory[enterprise]"
            )
        # Only pass relevant config to MongoDBStore
        mongo_config = {
            k: v for k, v in config.items() if k in ["mongodb_uri", "database"]
        }
        logger.info(f"Creating MongoDBStore with config: {mongo_config}")
        return MongoDBStore(**mongo_config)
    raise ValueError(
        f"Unsupported storage type: {storage_type}. Supported types: file, mongodb"
    )


__all__ = ["MemoryStoreInterface", "FileBasedStore", "create_store"]

# Only export MongoDB store if available
if _MONGODB_AVAILABLE:
    __all__.append("MongoDBStore")
