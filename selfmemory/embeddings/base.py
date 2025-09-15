from abc import ABC, abstractmethod
from typing import Literal

from selfmemory.embeddings.configs import BaseEmbedderConfig


class EmbeddingBase(ABC):
    """Base class for all embedding providers."""

    def __init__(self, config: BaseEmbedderConfig | None = None):
        """Initialize a base embedding class

        :param config: Embedding configuration option class, defaults to None
        :type config: Optional[BaseEmbedderConfig], optional
        """
        if config is None:
            self.config = BaseEmbedderConfig()
        else:
            self.config = config

    @abstractmethod
    def embed(
        self,
        text: str,
        memory_action: Literal["add", "search", "update"] | None = None,
    ) -> list[float]:
        """
        Get the embedding for the given text.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list[float]: The embedding vector.
        """
        pass
