import os
from typing import Literal

from together import Together

from selfmemory.configs.embeddings.base import BaseEmbedderConfig
from selfmemory.embeddings.base import EmbeddingBase


class TogetherEmbedding(EmbeddingBase):
    def __init__(self, config: BaseEmbedderConfig | None = None):
        super().__init__(config)

        self.config.model = (
            self.config.model or "togethercomputer/m2-bert-80M-8k-retrieval"
        )
        api_key = self.config.api_key or os.getenv("TOGETHER_API_KEY")
        # TODO: check if this is correct
        self.config.embedding_dims = self.config.embedding_dims or 768
        self.client = Together(api_key=api_key)

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

        return (
            self.client.embeddings.create(model=self.config.model, input=text)
            .data[0]
            .embedding
        )
