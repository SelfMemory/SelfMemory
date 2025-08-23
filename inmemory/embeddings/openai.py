import os
import warnings
from typing import Literal

from inmemory.config.config import InMemoryConfig
from inmemory.embeddings.base import EmbeddingBase

try:
    from openai import OpenAI
except ImportError:
    raise ImportError(
        "The 'openai' library is required. Please install it using 'pip install openai'."
    ) from None


class OpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: InMemoryConfig | None = None):
        super().__init__(config)

        self.model = (
            getattr(config, "embedding_model", "text-embedding-3-small")
            if config
            else "text-embedding-3-small"
        )
        self.embedding_dims = (
            getattr(config, "embedding_dims", 1536) if config else 1536
        )

        api_key = getattr(config, "openai_api_key", None) if config else None
        api_key = api_key or os.getenv("OPENAI_API_KEY")

        base_url = getattr(config, "openai_base_url", None) if config else None
        base_url = (
            base_url
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        )

        if os.environ.get("OPENAI_API_BASE"):
            warnings.warn(
                "The environment variable 'OPENAI_API_BASE' is deprecated and will be removed in a future version. "
                "Please use 'OPENAI_BASE_URL' instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def embed(
        self, text, memory_action: Literal["add", "search", "update"] | None = None
    ):
        """
        Get the embedding for the given text using OpenAI.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        return (
            self.client.embeddings.create(
                input=[text], model=self.model, dimensions=self.embedding_dims
            )
            .data[0]
            .embedding
        )
