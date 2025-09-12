"""
Base configuration classes for SelfMemory.

This module provides the main configuration classes and utilities,
following selfmemory configuration structure pattern with hybrid dynamic import system.
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

from pydantic import BaseModel, Field, model_validator, validator

# Static imports for core providers (always loaded for performance)

logger = logging.getLogger(__name__)

# Set up the directory path
home_dir = os.path.expanduser("~")
selfmemory_dir = os.environ.get("SELFMEMORY_DIR") or os.path.join(
    home_dir, ".selfmemory"
)


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
    """Configuration for vector store providers following selfmemory pattern."""

    provider: str = Field(default="qdrant", description="Vector store provider")
    config: dict | None = Field(
        default=None, description="Provider-specific configuration dictionary"
    )

    # Simple provider registry (selfmemory style)
    _provider_configs: dict[str, str] = {
        "qdrant": "QdrantConfig",
        "chroma": "ChromaConfig",
        "chromadb": "ChromaConfig",
        "pinecone": "PineconeConfig",
        "weaviate": "WeaviateConfig",
    }

    @model_validator(mode="after")
    def validate_and_create_config(self) -> "VectorStoreConfig":
        """Create provider-specific config object using selfmemory pattern."""
        provider = self.provider
        config = self.config

        if provider not in self._provider_configs:
            raise ValueError(f"Unsupported vector store provider: {provider}")

        # Dynamic import (selfmemory style)
        module = __import__(
            f"selfmemory.configs.vector_stores.{provider}",
            fromlist=[self._provider_configs[provider]],
        )
        config_class = getattr(module, self._provider_configs[provider])

        if config is None:
            config = {}

        if not isinstance(config, dict):
            if not isinstance(config, config_class):
                raise ValueError(f"Invalid config type for provider {provider}")
            return self

        # Only add default path if no other connection method is specified
        has_connection_method = any(
            key in config for key in ["path", "host", "port", "url"]
        )
        if not has_connection_method and "path" in config_class.__annotations__:
            config["path"] = f"/tmp/{provider}"

        # Create provider-specific config object
        self.config = config_class(**config)
        return self


class EmbeddingConfig(BaseModel):
    """Configuration for embedding providers following selfmemory pattern."""

    provider: str = Field(default="ollama", description="Embedding provider")
    config: dict | None = Field(
        default=None, description="Provider-specific configuration dictionary"
    )

    # Simple provider registry (selfmemory style)
    _provider_configs: dict[str, str] = {
        "ollama": "OllamaConfig",
        "openai": "OpenAIConfig",
        "huggingface": "HuggingFaceConfig",
        "cohere": "CohereConfig",
        "azure": "AzureConfig",
    }

    @model_validator(mode="after")
    def validate_and_create_config(self) -> "EmbeddingConfig":
        """Create provider-specific config object using selfmemory pattern."""
        provider = self.provider
        config = self.config

        if provider not in self._provider_configs:
            raise ValueError(f"Unsupported embedding provider: {provider}")

        # Dynamic import (selfmemory style)
        module = __import__(
            f"selfmemory.configs.embeddings.{provider}",
            fromlist=[self._provider_configs[provider]],
        )
        config_class = getattr(module, self._provider_configs[provider])

        if config is None:
            config = {}

        if not isinstance(config, dict):
            if not isinstance(config, config_class):
                raise ValueError(f"Invalid config type for provider {provider}")
            return self

        # Create provider-specific config object
        self.config = config_class(**config)
        return self


class ServerConfig(BaseModel):
    """Configuration for API server."""

    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8081, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")


class SelfMemoryConfig(BaseModel):
    """Main configuration for SelfMemory."""

    auth: AuthConfig = Field(default_factory=AuthConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    history_db_path: str = Field(
        description="Path to the history database",
        default=os.path.join(selfmemory_dir, "history.db"),
    )
    version: str = Field(
        description="The version of the API",
        default="v1.0",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.dict()

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "SelfMemoryConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)


def load_config(config_path: str | None = None) -> SelfMemoryConfig:
    """
    Load configuration from file, environment variables, and defaults.

    Priority order:
    1. Explicit config file path
    2. Environment variables
    3. Default config files (~/.selfmemory/config.yaml, ./config.yaml)
    4. Default values

    Args:
        config_path: Optional path to configuration file

    Returns:
        SelfMemoryConfig: Loaded configuration
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
        config = SelfMemoryConfig.from_dict(config_dict)
        logger.info(
            f"Configuration loaded: vector_store={config.vector_store.provider}, embedding={config.embedding.provider}"
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
            Path.home() / ".selfmemory" / "config.yaml",
            Path.home() / ".selfmemory" / "config.yml",
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

    # Authentication configuration
    if os.getenv("SELFMEMORY_AUTH_TYPE"):
        env_config.setdefault("auth", {})["type"] = os.getenv("SELFMEMORY_AUTH_TYPE")

    if os.getenv("SELFMEMORY_DEFAULT_USER"):
        env_config.setdefault("auth", {})["default_user"] = os.getenv(
            "SELFMEMORY_DEFAULT_USER"
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
    if os.getenv("SELFMEMORY_HOST"):
        env_config.setdefault("server", {})["host"] = os.getenv("SELFMEMORY_HOST")

    if os.getenv("SELFMEMORY_PORT"):
        env_config.setdefault("server", {})["port"] = int(os.getenv("SELFMEMORY_PORT"))

    if os.getenv("SELFMEMORY_DEBUG"):
        env_config.setdefault("server", {})["debug"] = (
            os.getenv("SELFMEMORY_DEBUG").lower() == "true"
        )

    if env_config:
        logger.debug(f"Environment configuration loaded: {list(env_config.keys())}")

    return env_config


def get_default_config() -> SelfMemoryConfig:
    """
    Get default configuration for file-based storage.

    Returns:
        SelfMemoryConfig: Default configuration optimized for ease of use
    """
    return SelfMemoryConfig()


def get_enterprise_config() -> SelfMemoryConfig:
    """
    Get default enterprise configuration with OAuth authentication.

    Returns:
        SelfMemoryConfig: Enterprise configuration with OAuth
    """
    return SelfMemoryConfig(
        auth=AuthConfig(
            type="oauth",
            require_api_key=True,
            google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        ),
    )
