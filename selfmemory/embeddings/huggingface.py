import logging
from typing import Literal

from openai import OpenAI
from sentence_transformers import SentenceTransformer

from selfmemory.configs.embeddings.base import BaseEmbedderConfig
from selfmemory.embeddings.base import EmbeddingBase

logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


class HuggingFaceEmbedding(EmbeddingBase):
    def __init__(self, config: BaseEmbedderConfig | None = None):
        super().__init__(config)

        if config.huggingface_base_url:
            self.client = OpenAI(base_url=config.huggingface_base_url)
        else:
            self.config.model = self.config.model or "multi-qa-MiniLM-L6-cos-v1"

            self.model = SentenceTransformer(
                self.config.model, **self.config.model_kwargs
            )

            self.config.embedding_dims = (
                self.config.embedding_dims
                or self.model.get_sentence_embedding_dimension()
            )

    def embed(
        self, text, memory_action: Literal["add", "search", "update"] | None = None
    ):
        """
        Get the embedding for the given text using Hugging Face.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        if self.config.huggingface_base_url:
            return (
                self.client.embeddings.create(input=text, model="tei").data[0].embedding
            )
        return self.model.encode(text, convert_to_numpy=True).tolist()
