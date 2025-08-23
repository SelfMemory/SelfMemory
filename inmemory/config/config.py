"""
Configuration management for InMemory.

This module provides configuration loading, validation, and default configurations
for different deployment modes (file-based, MongoDB enterprise, etc.).
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
    collection_name: str = Field(default="memories", description="Collection name")

    # Qdrant specific
    qdrant_url: str | None = Field(default=None, description="Qdrant URL")
    qdrant_host: str = Field(default="localhost", description="Qdrant host")
    qdrant_port: int = Field(default=6333, description="Qdrant port")
    qdrant_api_key: str | None = Field(default=None, description="Qdrant API key")
    qdrant_path: str | None = Field(
        default=None, description="Qdrant local storage path"
    )

    # ChromaDB specific
    chroma_host: str | None = Field(default=None, description="ChromaDB host")
    chroma_port: int | None = Field(default=None, description="ChromaDB port")
    chroma_path: str | None = Field(
        default=None, description="ChromaDB local storage path"
    )

    @validator("provider")
    def validate_provider(cls, v):
        supported_providers = ["qdrant", "chroma", "chromadb"]
        if v not in supported_providers:
            raise ValueError(
                f"Vector store provider must be one of: {supported_providers}"
            )
        return v


class EmbeddingConfig(BaseModel):
    """Configuration for embedding generation."""

    provider: str = Field(default="ollama", description="Embedding provider")
    embedding_model: str = Field(
        default="nomic-embed-text", description="Embedding model"
    )
    embedding_dims: int = Field(default=512, description="Embedding dimensions")

    # Ollama specific
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama base URL"
    )

    # OpenAI specific
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_base_url: str | None = Field(default=None, description="OpenAI base URL")

    @validator("provider")
    def validate_provider(cls, v):
        supported_providers = ["ollama", "openai"]
        if v not in supported_providers:
            raise ValueError(
                f"Embedding provider must be one of: {supported_providers}"
            )
        return v


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

    # Qdrant configuration
    if os.getenv("QDRANT_HOST"):
        env_config.setdefault("qdrant", {})["host"] = os.getenv("QDRANT_HOST")

    if os.getenv("QDRANT_PORT"):
        env_config.setdefault("qdrant", {})["port"] = int(os.getenv("QDRANT_PORT"))

    # Embedding configuration
    if os.getenv("EMBEDDING_PROVIDER"):
        env_config.setdefault("embedding", {})["provider"] = os.getenv(
            "EMBEDDING_PROVIDER"
        )

    if os.getenv("EMBEDDING_MODEL"):
        env_config.setdefault("embedding", {})["model"] = os.getenv("EMBEDDING_MODEL")

    if os.getenv("OLLAMA_HOST"):
        env_config.setdefault("embedding", {})["ollama_host"] = os.getenv("OLLAMA_HOST")

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


def create_sample_configs():
    """
    Create sample configuration files in ~/.inmemory/ directory.
    Useful for users who want to customize their setup.
    """
    config_dir = Path.home() / ".inmemory"
    config_dir.mkdir(exist_ok=True)

    if not _YAML_AVAILABLE:
        logger.warning("PyYAML not available. Cannot create sample YAML configs.")
        return

    # Simple config
    simple_config_path = config_dir / "config-simple.yaml"
    simple_config = {
        "storage": {"type": "file", "path": "~/.inmemory/data"},
        "auth": {"type": "simple", "default_user": "user123"},
        "qdrant": {"host": "localhost", "port": 6333},
        "embedding": {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "ollama_host": "http://localhost:11434",
        },
    }

    # Enterprise config
    enterprise_config_path = config_dir / "config-enterprise.yaml"
    enterprise_config = {
        "storage": {
            "type": "mongodb",
            "mongodb_uri": "mongodb://localhost:27017/inmemory",
            "database": "inmemory",
        },
        "auth": {
            "type": "oauth",
            "require_api_key": True,
            "google_client_id": "${GOOGLE_CLIENT_ID}",
            "google_client_secret": "${GOOGLE_CLIENT_SECRET}",
        },
        "qdrant": {"host": "localhost", "port": 6333},
        "embedding": {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "ollama_host": "http://localhost:11434",
        },
        "server": {"host": "0.0.0.0", "port": 8081, "debug": False},
    }

    try:
        # Write simple config
        if not simple_config_path.exists():
            with simple_config_path.open("w") as f:
                yaml.dump(simple_config, f, default_flow_style=False, indent=2)
            logger.info(f"Sample simple config created: {simple_config_path}")

        # Write enterprise config
        if not enterprise_config_path.exists():
            with enterprise_config_path.open("w") as f:
                yaml.dump(enterprise_config, f, default_flow_style=False, indent=2)
            logger.info(f"Sample enterprise config created: {enterprise_config_path}")

    except Exception as e:
        logger.error(f"Failed to create sample configs: {e}")


def detect_deployment_mode() -> str:
    """
    Auto-detect the appropriate deployment mode based on environment.

    Returns:
        str: Detected deployment mode ("simple", "server", "enterprise")
    """
    # Check for MongoDB URI
    if os.getenv("MONGODB_URI"):
        return "enterprise"

    # Check for server-specific variables
    if any(os.getenv(var) for var in ["INMEMORY_HOST", "INMEMORY_PORT", "PORT"]):
        return "server"

    # Default to simple mode
    return "simple"


def get_config_for_mode(mode: str) -> InMemoryConfig:
    """
    Get configuration for specific deployment mode.

    Args:
        mode: Deployment mode ("simple", "server", "enterprise")

    Returns:
        InMemoryConfig: Configuration for the specified mode
    """
    if mode == "enterprise":
        return get_enterprise_config()
    if mode == "server":
        return InMemoryConfig(
            storage=StorageConfig(type="file"),
            auth=AuthConfig(type="api_key", require_api_key=True),
            server=ServerConfig(host="0.0.0.0", port=8081),
        )
    # simple
    return get_default_config()


def validate_config(config: InMemoryConfig) -> bool:
    """
    Validate configuration for current environment.

    Args:
        config: Configuration to validate

    Returns:
        bool: True if configuration is valid for current environment
    """
    try:
        # Validate storage backend
        if config.storage.type == "mongodb" and not config.storage.mongodb_uri:
            logger.error("MongoDB URI required for mongodb storage type")
            return False

        # Validate authentication
        if config.auth.type == "oauth" and (
            not config.auth.google_client_id or not config.auth.google_client_secret
        ):
            logger.warning("OAuth configured but Google credentials missing")

        # Validate Qdrant connectivity (optional check)
        # This could be extended to actually test connections

        logger.info("Configuration validation passed")
        return True

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False
