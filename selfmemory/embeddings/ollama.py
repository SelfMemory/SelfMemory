from typing import Literal

from selfmemory.embeddings.base import EmbeddingBase
from selfmemory.embeddings.configs import BaseEmbedderConfig

try:
    from ollama import Client
except ImportError:
    raise ImportError(
        "The 'ollama' library is required. Please install it using your package manager:\n"
        "  • pip: pip install ollama\n"
        "  • uv: uv add ollama\n"
        "  • poetry: poetry add ollama\n"
        "  • pipenv: pipenv install ollama\n"
        "  • conda: conda install -c conda-forge ollama\n"
    ) from None


class OllamaEmbedding(EmbeddingBase):
    def __init__(self, config: BaseEmbedderConfig | None = None):
        super().__init__(config)

        # Use config or defaults
        if config is None:
            self.config = BaseEmbedderConfig()
        else:
            self.config = config

        # Set defaults if not provided
        self.config.model = self.config.model or "nomic-embed-text"
        self.config.embedding_dims = self.config.embedding_dims or 768

        self.client = Client(host=self.config.ollama_base_url)
        self._ensure_model_exists()

    def _ensure_model_exists(self):
        """
        Ensure the specified model exists locally. If not, pull it from Ollama.
        """
        local_models = self.client.list()["models"]
        if not any(
            model.get("name") == self.config.model
            or model.get("model") == self.config.model
            for model in local_models
        ):
            self.client.pull(self.config.model)

    def embed(
        self,
        text: str,
        memory_action: Literal["add", "search", "update"] | None = None,
    ) -> list[float]:
        """
        Get the embedding for the given text using Ollama.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list[float]: The embedding vector.
        """
        response = self.client.embeddings(model=self.config.model, prompt=text)
        return response["embedding"]
