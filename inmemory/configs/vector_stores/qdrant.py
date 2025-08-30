"""
Qdrant vector store configuration following  pattern.
"""

from typing import Any, ClassVar, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class QdrantConfig(BaseModel):
    """
    Configuration for Qdrant vector store.
    
    Follows  QdrantConfig pattern exactly.
    """
    
    collection_name: str = Field("inmemory_memories", description="Name of the collection")
    embedding_model_dims: Optional[int] = Field(768, description="Dimensions of the embedding model")
    host: Optional[str] = Field(None, description="Host address for Qdrant server")
    port: Optional[int] = Field(None, description="Port for Qdrant server")
    path: Optional[str] = Field("/tmp/qdrant", description="Path for local Qdrant database")
    url: Optional[str] = Field(None, description="Full URL for Qdrant server")
    api_key: Optional[str] = Field(None, description="API key for Qdrant server")
    on_disk: Optional[bool] = Field(False, description="Enables persistent storage")

    @model_validator(mode="before")
    @classmethod
    def check_host_port_or_path(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that either host+port, url+api_key, or path is provided."""
        host, port, path, url, api_key = (
            values.get("host"),
            values.get("port"),
            values.get("path"),
            values.get("url"),
            values.get("api_key"),
        )
        if not path and not (host and port) and not (url and api_key):
            # Set default path if no connection method specified
            values["path"] = "/tmp/qdrant"
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
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

    model_config = {
        "arbitrary_types_allowed": True,
    }
