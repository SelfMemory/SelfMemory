import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PineconeConfig(BaseModel):
    """Configuration for Pinecone vector database."""

    collection_name: str = Field(
        "selfmemory", description="Name of the index/collection"
    )
    embedding_model_dims: int = Field(
        1536, description="Dimensions of the embedding model"
    )
    client: Any | None = Field(None, description="Existing Pinecone client instance")
    api_key: str | None = Field(None, description="API key for Pinecone")
    environment: str | None = Field(None, description="Pinecone environment")
    serverless_config: dict[str, Any] | None = Field(
        None, description="Configuration for serverless deployment"
    )
    pod_config: dict[str, Any] | None = Field(
        None, description="Configuration for pod-based deployment"
    )
    hybrid_search: bool = Field(False, description="Whether to enable hybrid search")
    metric: str = Field("cosine", description="Distance metric for vector similarity")
    batch_size: int = Field(100, description="Batch size for operations")
    extra_params: dict[str, Any] | None = Field(
        None, description="Additional parameters for Pinecone client"
    )
    namespace: str | None = Field(None, description="Namespace for the collection")

    @model_validator(mode="before")
    @classmethod
    def check_api_key_or_client(cls, values: dict[str, Any]) -> dict[str, Any]:
        api_key, client = values.get("api_key"), values.get("client")
        if not api_key and not client and "PINECONE_API_KEY" not in os.environ:
            raise ValueError(
                "Either 'api_key' or 'client' must be provided, or PINECONE_API_KEY environment variable must be set."
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def check_pod_or_serverless(cls, values: dict[str, Any]) -> dict[str, Any]:
        pod_config, serverless_config = (
            values.get("pod_config"),
            values.get("serverless_config"),
        )
        if pod_config and serverless_config:
            raise ValueError(
                "Both 'pod_config' and 'serverless_config' cannot be specified. Choose one deployment option."
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
