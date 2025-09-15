"""
Qdrant vector store configuration following pattern.
"""

import logging
import os
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, Field, model_validator, validator

logger = logging.getLogger(__name__)


class QdrantConfig(BaseModel):
    """
    Configuration for Qdrant vector store.

    Follows QdrantConfig pattern with enhanced validation.
    """

    collection_name: str = Field(
        "selfmemory_memories", description="Name of the collection"
    )
    embedding_model_dims: int | None = Field(
        768, description="Dimensions of the embedding model"
    )
    host: str | None = Field(None, description="Host address for Qdrant server")
    port: int | None = Field(None, description="Port for Qdrant server")
    path: str | None = Field(None, description="Path for local Qdrant database")
    url: str | None = Field(None, description="Full URL for Qdrant server")
    api_key: str | None = Field(None, description="API key for Qdrant cloud")
    timeout: int = Field(30, description="Request timeout in seconds")
    https: bool | None = Field(None, description="Use HTTPS connection")
    on_disk: bool = Field(False, description="Store vectors on disk")
    prefer_grpc: bool = Field(True, description="Prefer gRPC over HTTP")

    @validator("collection_name")
    def validate_collection_name(cls, v):
        """Validate collection name follows Qdrant naming rules."""
        if not v or not v.strip():
            raise ValueError("Collection name cannot be empty")

        name = v.strip()

        # Qdrant collection name rules
        if len(name) > 255:
            raise ValueError("Collection name cannot exceed 255 characters")

        # Must start with letter or underscore
        if not (name[0].isalpha() or name[0] == "_"):
            raise ValueError("Collection name must start with a letter or underscore")

        # Can only contain alphanumeric, underscores, and hyphens
        if not all(c.isalnum() or c in "_-" for c in name):
            raise ValueError(
                "Collection name can only contain letters, numbers, underscores, and hyphens"
            )

        return name

    @validator("embedding_model_dims")
    def validate_embedding_dims(cls, v):
        """Validate embedding dimensions."""
        if v is not None:
            if v <= 0:
                raise ValueError("Embedding dimensions must be positive")
            if v > 65536:  # Qdrant limit
                raise ValueError(
                    "Embedding dimensions cannot exceed 65536 (Qdrant limit)"
                )
            if v < 50:
                raise ValueError("Embedding dimensions should be at least 50")
        return v

    @validator("host")
    def validate_host(cls, v):
        """Validate host format."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Basic hostname validation
            if len(v) > 253:
                raise ValueError("Host name too long")
        return v

    @validator("port")
    def validate_port(cls, v):
        """Validate port number."""
        if v is not None:
            if v <= 0 or v > 65535:
                raise ValueError("Port must be between 1 and 65535")
        return v

    @validator("path")
    def validate_path(cls, v):
        """Validate local database path."""
        if v is not None:
            v = v.strip()
            if not v:
                return None

            # Expand user home directory
            expanded_path = os.path.expanduser(v)

            # Check if parent directory exists or can be created
            parent_dir = Path(expanded_path).parent
            if not parent_dir.exists():
                try:
                    parent_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise ValueError(f"Cannot create directory {parent_dir}: {e}")

            return expanded_path
        return v

    @validator("url")
    def validate_url(cls, v):
        """Validate Qdrant server URL."""
        if v is not None:
            v = v.strip()
            if not v:
                return None

            if not v.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")

            # Remove trailing slash
            return v.rstrip("/")
        return v

    @validator("api_key")
    def validate_api_key(cls, v):
        """Validate API key format."""
        if v is not None:
            v = v.strip()
            if not v:
                return None

            if len(v) < 10:
                raise ValueError("API key too short (minimum 10 characters)")
            if len(v) > 500:
                raise ValueError("API key too long (maximum 500 characters)")
        return v

    @validator("timeout")
    def validate_timeout(cls, v):
        """Validate timeout value."""
        if v <= 0:
            raise ValueError("Timeout must be positive")
        if v > 300:
            raise ValueError("Timeout cannot exceed 300 seconds")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_connection_params(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate connection parameter combinations."""
        path = values.get("path")
        host = values.get("host")
        port = values.get("port")
        url = values.get("url")
        api_key = values.get("api_key")

        # Count connection methods
        connection_methods = sum([bool(path), bool(host and port), bool(url)])

        if connection_methods == 0:
            # Set default path if no connection method specified
            values["path"] = "/tmp/qdrant"
        elif connection_methods > 1:
            raise ValueError(
                "Only one connection method allowed: either 'path' for local, "
                "'host'+'port' for server, or 'url' for full URL"
            )

        # Validate cloud configuration
        if url and api_key:
            if not url.startswith("https://"):
                raise ValueError("Cloud Qdrant (with API key) requires HTTPS URL")

        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate that no extra fields are provided."""
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

    @model_validator(mode="after")
    def validate_connection(self) -> "QdrantConfig":
        """Test connection to Qdrant server if requested."""
        import os

        if os.getenv("SELFMEMORY_VALIDATE_CONNECTIONS", "false").lower() == "true":
            connection_info = self.test_connection()
            if connection_info["status"] != "connected":
                logger.warning(
                    f"Qdrant connection test failed: {connection_info.get('error', 'Unknown error')}"
                )

        return self

    model_config = {
        "arbitrary_types_allowed": True,
        "validate_assignment": True,
        "extra": "forbid",
    }

    def test_connection(self) -> dict[str, Any]:
        """Test connection to Qdrant and return status."""
        try:
            if self.path:
                # Local file-based Qdrant
                path_obj = Path(self.path)
                if path_obj.exists():
                    return {
                        "status": "connected",
                        "connection_type": "local_file",
                        "path": str(path_obj),
                        "writable": os.access(path_obj.parent, os.W_OK),
                    }
                return {
                    "status": "path_not_exists",
                    "connection_type": "local_file",
                    "path": str(path_obj),
                    "can_create": os.access(path_obj.parent, os.W_OK)
                    if path_obj.parent.exists()
                    else False,
                }

            if self.url:
                # URL-based connection
                test_url = f"{self.url}/collections"
                headers = {}
                if self.api_key:
                    headers["api-key"] = self.api_key

                response = requests.get(test_url, headers=headers, timeout=5)

                if response.status_code == 200:
                    return {
                        "status": "connected",
                        "connection_type": "url",
                        "server_url": self.url,
                        "response_time_ms": response.elapsed.total_seconds() * 1000,
                        "collections": len(
                            response.json().get("result", {}).get("collections", [])
                        ),
                    }
                return {
                    "status": "error",
                    "connection_type": "url",
                    "server_url": self.url,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }

            if self.host and self.port:
                # Host + port connection
                protocol = "https" if self.https else "http"
                test_url = f"{protocol}://{self.host}:{self.port}/collections"

                response = requests.get(test_url, timeout=5)

                if response.status_code == 200:
                    return {
                        "status": "connected",
                        "connection_type": "host_port",
                        "server_url": f"{protocol}://{self.host}:{self.port}",
                        "response_time_ms": response.elapsed.total_seconds() * 1000,
                        "collections": len(
                            response.json().get("result", {}).get("collections", [])
                        ),
                    }
                return {
                    "status": "error",
                    "connection_type": "host_port",
                    "server_url": f"{protocol}://{self.host}:{self.port}",
                    "error": f"HTTP {response.status_code}: {response.text}",
                }

            return {
                "status": "no_connection_method",
                "error": "No valid connection method configured",
            }

        except requests.RequestException as e:
            return {"status": "connection_failed", "error": str(e)}
        except Exception as e:
            return {"status": "unknown_error", "error": str(e)}
