from typing import Literal

from selfmemory.configs.embeddings.base import BaseEmbedderConfig
from selfmemory.embeddings.base import EmbeddingBase

try:
    from langchain.embeddings.base import Embeddings
except ImportError:
    raise ImportError(
        "langchain is not installed. Please install it using `pip install langchain`"
    )


class LangchainEmbedding(EmbeddingBase):
    def __init__(self, config: BaseEmbedderConfig | None = None):
        super().__init__(config)

        if self.config.model is None:
            raise ValueError("`model` parameter is required")

        if not isinstance(self.config.model, Embeddings):
            raise ValueError("`model` must be an instance of Embeddings")

        self.langchain_model = self.config.model

    def embed(
        self, text, memory_action: Literal["add", "search", "update"] | None = None
    ):
        """
        Get the embedding for the given text using Langchain.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """

        return self.langchain_model.embed_query(text)
