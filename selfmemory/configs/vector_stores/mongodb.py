from typing import Any

from pydantic import BaseModel, Field, model_validator


class MongoDBConfig(BaseModel):
    """Configuration for MongoDB vector database."""

    db_name: str = Field("selfmemory_db", description="Name of the MongoDB database")
    collection_name: str = Field(
        "selfmemory", description="Name of the MongoDB collection"
    )
    embedding_model_dims: int | None = Field(
        1536, description="Dimensions of the embedding vectors"
    )
    mongo_uri: str = Field(
        "mongodb://localhost:27017",
        description="MongoDB URI. Default is mongodb://localhost:27017",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please provide only the following fields: {', '.join(allowed_fields)}."
            )
        return values
