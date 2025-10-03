import os
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

try:
    from upstash_vector import Index
except ImportError as err:
    raise ImportError(
        "The 'upstash_vector' library is required. Please install it using 'pip install upstash_vector'."
    ) from err


class UpstashVectorConfig(BaseModel):
    Index: ClassVar[type] = Index

    url: str | None = Field(None, description="URL for Upstash Vector index")
    token: str | None = Field(None, description="Token for Upstash Vector index")
    client: Index | None = Field(
        None, description="Existing `upstash_vector.Index` client instance"
    )
    collection_name: str = Field(
        "selfmemory", description="Namespace to use for the index"
    )
    enable_embeddings: bool = Field(
        False,
        description="Whether to use built-in upstash embeddings or not. Default is True.",
    )

    @model_validator(mode="before")
    @classmethod
    def check_credentials_or_client(cls, values: dict[str, Any]) -> dict[str, Any]:
        client = values.get("client")
        url = values.get("url") or os.environ.get("UPSTASH_VECTOR_REST_URL")
        token = values.get("token") or os.environ.get("UPSTASH_VECTOR_REST_TOKEN")

        if not client and not (url and token):
            raise ValueError("Either a client or URL and token must be provided.")
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
