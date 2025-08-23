from typing import Literal

from inmemory.config.config import InMemoryConfig
from inmemory.embeddings.base import EmbeddingBase

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
        "Or install the full inmemory package with embedding support:\n"
        "  • pip install 'inmemory[embedding]'\n"
        "  • uv add 'inmemory[embedding]'"
    ) from None


class OllamaEmbedding(EmbeddingBase):
    def __init__(self, config: InMemoryConfig | None = None):
        super().__init__(config)

        self.model = (
            getattr(config, "embedding_model", "nomic-embed-text")
            if config
            else "nomic-embed-text"
        )
        self.ollama_base_url = (
            getattr(config, "ollama_base_url", "http://localhost:11434")
            if config
            else "http://localhost:11434"
        )

        self.client = Client(host=self.ollama_base_url)
        self._ensure_model_exists()

        # Auto-detect actual embedding dimensions from the model
        if config and hasattr(config, "embedding_dims") and config.embedding_dims:
            self.embedding_dims = config.embedding_dims
        else:
            # Auto-detect dimensions by testing the model
            try:
                test_embedding = self.client.embeddings(
                    model=self.model, prompt="test"
                )["embedding"]
                self.embedding_dims = len(test_embedding)
                print(
                    f"🔍 Auto-detected embedding dimensions for {self.model}: {self.embedding_dims}"
                )
            except Exception as e:
                print(f"⚠️  Could not auto-detect dimensions, using default 768: {e}")
                self.embedding_dims = 768  # Default for nomic-embed-text

    def _ensure_model_exists(self):
        """
        Ensure the specified model exists locally. If not, pull it from Ollama.
        """
        local_models = self.client.list()["models"]
        if not any(model.get("name") == self.model for model in local_models):
            self.client.pull(self.model)

    def embed(
        self, text, memory_action: Literal["add", "search", "update"] | None = None
    ):
        """
        Get the embedding for the given text using Ollama.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        response = self.client.embeddings(model=self.model, prompt=text)
        return response["embedding"]
