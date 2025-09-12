"""
Ollama embedding configuration following pattern.
"""

import logging
from typing import Any
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, Field, model_validator, validator

logger = logging.getLogger(__name__)


class OllamaConfig(BaseModel):
    """
    Configuration for Ollama embedding provider.

    Follows embedding config pattern with enhanced validation.
    """

    model: str = Field("nomic-embed-text", description="Ollama model name")
    embedding_dims: int | None = Field(
        768, description="Dimensions of the embedding model"
    )
    ollama_base_url: str = Field(
        "http://localhost:11434", description="Ollama server base URL"
    )
    timeout: int = Field(30, description="Request timeout in seconds")
    verify_ssl: bool = Field(True, description="Verify SSL certificates")
    max_retries: int = Field(3, description="Maximum number of retries")

    @validator("model")
    def validate_model(cls, v):
        """Validate model name is not empty and follows naming conventions."""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")

        model_name = v.strip()

        # Check for valid characters (alphanumeric, hyphens, underscores, dots)
        if not all(c.isalnum() or c in "-_." for c in model_name):
            raise ValueError(
                "Model name can only contain alphanumeric characters, hyphens, underscores, and dots"
            )

        # Check length
        if len(model_name) > 100:
            raise ValueError("Model name cannot exceed 100 characters")

        return model_name

    @validator("embedding_dims")
    def validate_embedding_dims(cls, v):
        """Validate embedding dimensions are reasonable."""
        if v is not None:
            if v <= 0:
                raise ValueError("Embedding dimensions must be positive")
            if v > 10000:
                raise ValueError("Embedding dimensions cannot exceed 10000 (too large)")
            if v < 50:
                raise ValueError(
                    "Embedding dimensions should be at least 50 for meaningful embeddings"
                )
        return v

    @validator("ollama_base_url")
    def validate_ollama_url(cls, v):
        """Validate Ollama URL format and accessibility."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Ollama URL must start with http:// or https://")

        try:
            result = urlparse(v)
            if not result.netloc:
                raise ValueError("Invalid URL: missing host")

            # Remove trailing slash for consistency
            return v.rstrip("/")

        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")

    @validator("timeout")
    def validate_timeout(cls, v):
        """Validate timeout is reasonable."""
        if v <= 0:
            raise ValueError("Timeout must be positive")
        if v > 300:  # 5 minutes max
            raise ValueError("Timeout cannot exceed 300 seconds")
        return v

    @validator("max_retries")
    def validate_max_retries(cls, v):
        """Validate max retries is reasonable."""
        if v < 0:
            raise ValueError("Max retries cannot be negative")
        if v > 10:
            raise ValueError("Max retries cannot exceed 10")
        return v

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
    def validate_connection(self) -> "OllamaConfig":
        """Validate connection to Ollama server (optional - can be disabled)."""
        # Only validate connection if explicitly requested via environment variable
        import os

        if os.getenv("SELFMEMORY_VALIDATE_CONNECTIONS", "false").lower() == "true":
            try:
                response = requests.get(
                    f"{self.ollama_base_url}/api/tags",
                    timeout=5,
                    verify=self.verify_ssl,
                )
                if response.status_code != 200:
                    logger.warning(
                        f"Ollama server at {self.ollama_base_url} returned status {response.status_code}"
                    )
                else:
                    # Check if model exists
                    models = response.json().get("models", [])
                    model_names = [model.get("name", "") for model in models]
                    if self.model not in model_names:
                        logger.warning(
                            f"Model '{self.model}' not found in Ollama. Available models: {model_names}"
                        )

            except requests.RequestException as e:
                logger.warning(
                    f"Could not connect to Ollama server at {self.ollama_base_url}: {e}"
                )
            except Exception as e:
                logger.warning(f"Error validating Ollama connection: {e}")

        return self

    model_config = {
        "arbitrary_types_allowed": True,
        "validate_assignment": True,
        "extra": "forbid",
    }

    def test_connection(self) -> dict[str, Any]:
        """Test connection to Ollama server and return status."""
        try:
            response = requests.get(
                f"{self.ollama_base_url}/api/tags",
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]

                return {
                    "status": "connected",
                    "server_url": self.ollama_base_url,
                    "available_models": model_names,
                    "model_exists": self.model in model_names,
                    "response_time_ms": response.elapsed.total_seconds() * 1000,
                }
            return {
                "status": "error",
                "server_url": self.ollama_base_url,
                "error": f"HTTP {response.status_code}: {response.text}",
            }

        except requests.RequestException as e:
            return {
                "status": "connection_failed",
                "server_url": self.ollama_base_url,
                "error": str(e),
            }
        except Exception as e:
            return {
                "status": "unknown_error",
                "server_url": self.ollama_base_url,
                "error": str(e),
            }
