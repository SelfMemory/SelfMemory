from abc import ABC, abstractmethod
from typing import Literal

from inmemory.config.config import InMemoryConfig


class EmbeddingBase(ABC):
    """Base class for all embedding providers."""

    def __init__(self, config: InMemoryConfig | None = None):
        """Initialize a base embedding class

        :param config: Embedding configuration option class, defaults to None
        :type config: Optional[InMemoryConfig], optional
        """
        self.config = config or InMemoryConfig()

    @abstractmethod
    def embed(
        self, text, memory_action: Literal["add", "search", "update"] | None = None
    ):
        """
        Get the embedding for the given text.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        pass
