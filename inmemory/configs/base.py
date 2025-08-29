"""
Base configuration classes for InMemory.

This module provides the main configuration classes and utilities,
following mem0's configuration structure pattern.
"""

import logging
import os
from pathlib import Path
from typing import Any

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

# Set up the directory path
home_dir = os.path.expanduser("~")
inmemory_dir = os.environ.get("INMEMORY_DIR") or os.path.join(home_dir, ".inmemory")


class StorageConfig(BaseModel):
    """Configuration for storage backend."""

    type: str = Field(default="file", description="Storage backend type")
    path: str | None = Field(
        default="~/.inmemory", description="Data directory for file storage"
    )
    mongodb_uri: str | None = Field(default=None, description="MongoDB connection URI")
    database: str | None = Field(default="inmemory", description="Database name")

    @validator("type")
    def validate_storage_type(cls, v):
        supported_types = ["file", "mongodb"]
        if v not in supported_types:
            raise ValueError(f"Storage type must be one of: {supported_types}")
        return v


class AuthConfig(BaseModel):
    """Configuration for authentication."""

    type: str = Field(default="simple", description="Authentication type")
    default_user: str | None = Field(
        default="default_user", description="Default user for simple auth"
    )
    require_api_key: bool = Field(
        default=False, description="Whether API key is required"
    )

    # OAuth configuration
    google_client_id: str | None = Field(default=None)
    google_client_secret: str | None = Field(default=None)

    @validator("type")
    def validate_auth_type(cls, v):
        supported_types = ["simple", "oauth", "api_key"]
        if v not in supported_types:
            raise ValueError(f"Auth type must be one of: {supported_types}")
        return v


class VectorStoreConfig(BaseModel):
    """Configuration for vector store providers."""

    provider: str = Field(default="qdrant", description="Vector store provider")
    config: dict | None = Field(
        default=None, 
        description="Provider-specific configuration dictionary"
    )

    _provider_configs = {
        "qdrant": "QdrantConfig",
        "chroma": "ChromaConfig",
        "chromadb": "ChromaConfig",
    }

    @validator("provider")
    def validate_provider(cls, v):
        supported_providers = ["qdrant", "chroma", "chromadb"]
        if v not in supported_providers:
            raise ValueError(
                f"Vector store provider must be one of: {supported_providers}"
            )
        return v

    def get_config_with_defaults(self) -> dict:
        """Get configuration with provider-specific defaults."""
        base_config = self.config or {}
        
        if self.provider == "qdrant":
            # Qdrant defaults (following mem0's approach - minimal defaults)
            defaults = {
                "collection_name": "inmemory_memories",
                "embedding_model_dims": 768,
                "on_disk": False,
            }
            
            # Only set path as default if no other connection method is specified
            # This matches mem0's approach where they don't set conflicting defaults
            if not any(key in base_config for key in ["url", "host", "api_key"]):
                defaults["path"] = "/tmp/qdrant"
            
            # Merge user config with defaults (user config takes precedence)
            return {**defaults, **base_config}
        elif self.provider in ["chroma", "chromadb"]:
            # ChromaDB defaults
            defaults = {
                "collection_name": "inmemory_memories",
                "host": "localhost",
                "port": 8000,
                "path": "/tmp/chroma",
            }
            return {**defaults, **base_config}
        
        return base_config


class EmbeddingConfig(BaseModel):
    """Configuration for embedding providers."""

    provider: str = Field(default="ollama", description="Embedding provider")
    config: dict | None = Field(
        default=None,
        description="Provider-specific configuration dictionary"
    )

    _provider_configs = {
        "ollama": "OllamaConfig",
        "openai": "OpenAIConfig",
    }

    @validator("provider")
    def validate_provider(cls, v):
        supported_providers = ["ollama", "openai"]
        if v not in supported_providers:
            raise ValueError(
                f"Embedding provider must be one of: {supported_providers}"
            )
        return v

    def get_config_with_defaults(self) -> dict:
        """Get configuration with provider-specific defaults."""
        base_config = self.config or {}
        
        if self.provider == "ollama":
            # Ollama defaults
            defaults = {
                "model": "nomic-embed-text",
                "embedding_dims": 768,
                "ollama_base_url": "http://localhost:11434",
            }
            return {**defaults, **base_config}
        elif self.provider == "openai":
            # OpenAI defaults
            defaults = {
                "model": "text-embedding-3-small",
                "embedding_dims": 1536,
            }
            return {**defaults, **base_config}
        
        return base_config


class ServerConfig(BaseModel):
    """Configuration for API server."""

    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8081, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")


class InMemoryConfig(BaseModel):
    """Main configuration for InMemory."""

    storage: StorageConfig = Field(default_factory=StorageConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    
    history_db_path: str = Field(
        description="Path to the history database",
        default=os.path.join(inmemory_dir, "history.db"),
    )
    version: str = Field(
        description="The version of the API",
        default="v1.0",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.dict()

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "InMemoryConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)


def load_config(config_path: str | None = None) -> InMemoryConfig:
    """
    Load configuration from file, environment variables, and defaults.

    Priority order:
    1. Explicit config file path
    2. Environment variables
    3. Default config files (~/.inmemory/config.yaml, ./config.yaml)
    4. Default values

    Args:
        config_path: Optional path to configuration file

    Returns:
        InMemoryConfig: Loaded configuration
    """
    config_dict = {}

    # Try to load from YAML file
    yaml_config = _load_yaml_config(config_path)
    if yaml_config:
        config_dict.update(yaml_config)

    # Override with environment variables
    env_config = _load_env_config()
    config_dict.update(env_config)

    # Create and validate configuration
    try:
        config = InMemoryConfig.from_dict(config_dict)
        logger.info(
            f"Configuration loaded: storage={config.storage.type}, auth={config.auth.type}"
        )
        return config
    except Exception as e:
        logger.warning(f"Configuration validation failed: {e}. Using defaults.")
        return get_default_config()


def _load_yaml_config(config_path: str | None = None) -> dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Optional explicit config file path

    Returns:
        Dict: Configuration dictionary from YAML, empty if not found
    """
    if not _YAML_AVAILABLE:
        logger.debug("PyYAML not available, skipping YAML config loading")
        return {}

    # Determine config file path
    if config_path:
        config_file = Path(config_path)
    else:
        # Try default locations
        possible_paths = [
            Path.home() / ".inmemory" / "config.yaml",
            Path.home() / ".inmemory" / "config.yml",
            Path("config.yaml"),
            Path("config.yml"),
        ]

        config_file = None
        for path in possible_paths:
            if path.exists():
                config_file = path
                break

    if not config_file or not config_file.exists():
        logger.debug("No YAML config file found")
        return {}

    try:
        with config_file.open(encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
        logger.info(f"Configuration loaded from: {config_file}")
        return config_data
    except Exception as e:
        logger.warning(f"Failed to load config from {config_file}: {e}")
        return {}


def _load_env_config() -> dict[str, Any]:
    """
    Load configuration from environment variables.

    Returns:
        Dict: Configuration dictionary from environment variables
    """
    env_config = {}

    # Storage configuration
    if os.getenv("INMEMORY_STORAGE_TYPE"):
        env_config.setdefault("storage", {})["type"] = os.getenv(
            "INMEMORY_STORAGE_TYPE"
        )

    if os.getenv("INMEMORY_DATA_DIR"):
        env_config.setdefault("storage", {})["path"] = os.getenv("INMEMORY_DATA_DIR")

    if os.getenv("MONGODB_URI"):
        env_config.setdefault("storage", {})["mongodb_uri"] = os.getenv("MONGODB_URI")

    if os.getenv("INMEMORY_DATABASE"):
        env_config.setdefault("storage", {})["database"] = os.getenv(
            "INMEMORY_DATABASE"
        )

    # Authentication configuration
    if os.getenv("INMEMORY_AUTH_TYPE"):
        env_config.setdefault("auth", {})["type"] = os.getenv("INMEMORY_AUTH_TYPE")

    if os.getenv("INMEMORY_DEFAULT_USER"):
        env_config.setdefault("auth", {})["default_user"] = os.getenv(
            "INMEMORY_DEFAULT_USER"
        )

    if os.getenv("GOOGLE_CLIENT_ID"):
        env_config.setdefault("auth", {})["google_client_id"] = os.getenv(
            "GOOGLE_CLIENT_ID"
        )

    if os.getenv("GOOGLE_CLIENT_SECRET"):
        env_config.setdefault("auth", {})["google_client_secret"] = os.getenv(
            "GOOGLE_CLIENT_SECRET"
        )

    # Server configuration
    if os.getenv("INMEMORY_HOST"):
        env_config.setdefault("server", {})["host"] = os.getenv("INMEMORY_HOST")

    if os.getenv("INMEMORY_PORT"):
        env_config.setdefault("server", {})["port"] = int(os.getenv("INMEMORY_PORT"))

    if os.getenv("INMEMORY_DEBUG"):
        env_config.setdefault("server", {})["debug"] = (
            os.getenv("INMEMORY_DEBUG").lower() == "true"
        )

    if env_config:
        logger.debug(f"Environment configuration loaded: {list(env_config.keys())}")

    return env_config


def get_default_config() -> InMemoryConfig:
    """
    Get default configuration for file-based storage.

    Returns:
        InMemoryConfig: Default configuration optimized for ease of use
    """
    return InMemoryConfig()


def get_enterprise_config() -> InMemoryConfig:
    """
    Get default enterprise configuration for MongoDB + OAuth.

    Returns:
        InMemoryConfig: Enterprise configuration with MongoDB backend
    """
    return InMemoryConfig(
        storage=StorageConfig(
            type="mongodb",
            mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017/inmemory"),
        ),
        auth=AuthConfig(
            type="oauth",
            require_api_key=True,
            google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        ),
    )
