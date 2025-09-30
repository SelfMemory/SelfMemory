from typing import Literal

from openai import OpenAI

from selfmemory.configs.embeddings.base import BaseEmbedderConfig
from selfmemory.embeddings.base import EmbeddingBase


class LMStudioEmbedding(EmbeddingBase):
    def __init__(self, config: BaseEmbedderConfig | None = None):
        super().__init__(config)

        self.config.model = (
            self.config.model
            or "nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf"
        )
        self.config.embedding_dims = self.config.embedding_dims or 1536
        self.config.api_key = self.config.api_key or "lm-studio"

        self.client = OpenAI(
            base_url=self.config.lmstudio_base_url, api_key=self.config.api_key
        )

    def embed(
        self, text, memory_action: Literal["add", "search", "update"] | None = None
    ):
        """
        Get the embedding for the given text using LM Studio.
        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        return (
            self.client.embeddings.create(input=[text], model=self.config.model)
            .data[0]
            .embedding
        )
