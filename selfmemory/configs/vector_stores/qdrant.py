from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QdrantConfig(BaseModel):
    from qdrant_client import QdrantClient

    QdrantClient: ClassVar[type] = QdrantClient

    collection_name: str = Field("selfmemory", description="Name of the collection")
    embedding_model_dims: int | None = Field(
        1536, description="Dimensions of the embedding model"
    )
    client: QdrantClient | None = Field(
        None, description="Existing Qdrant client instance"
    )
    host: str | None = Field(None, description="Host address for Qdrant server")
    port: int | None = Field(None, description="Port for Qdrant server")
    path: str | None = Field(
        "/tmp/qdrant", description="Path for local Qdrant database"
    )
    url: str | None = Field(None, description="Full URL for Qdrant server")
    api_key: str | None = Field(None, description="API key for Qdrant server")
    on_disk: bool | None = Field(False, description="Enables persistent storage")

    @model_validator(mode="before")
    @classmethod
    def check_host_port_or_path(cls, values: dict[str, Any]) -> dict[str, Any]:
        host, port, path, url, api_key = (
            values.get("host"),
            values.get("port"),
            values.get("path"),
            values.get("url"),
            values.get("api_key"),
        )
        if not path and not (host and port) and not (url and api_key):
            raise ValueError(
                "Either 'host' and 'port' or 'url' and 'api_key' or 'path' must be provided."
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
