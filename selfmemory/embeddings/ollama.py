import logging
import subprocess
import sys
from typing import Literal

from selfmemory.configs.embeddings.base import BaseEmbedderConfig
from selfmemory.embeddings.base import EmbeddingBase

try:
    from ollama import Client
except ImportError:
    user_input = input("The 'ollama' library is required. Install it now? [y/N]: ")
    if user_input.lower() == "y":
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "ollama"])
            from ollama import Client
        except subprocess.CalledProcessError:
            print(
                "Failed to install 'ollama'. Please install it manually using 'pip install ollama'."
            )
            sys.exit(1)
    else:
        print("The required 'ollama' library is not installed.")
        sys.exit(1)


class OllamaEmbedding(EmbeddingBase):
    def __init__(self, config: BaseEmbedderConfig | None = None):
        super().__init__(config)

        self.config.model = self.config.model or "nomic-embed-text"
        self.config.embedding_dims = self.config.embedding_dims or 512

        self.client = Client(host=self.config.ollama_base_url)
        
        # Track model availability status
        self._model_checked = False
        self._model_available = False
        
        # Try to ensure model exists, but don't fail if Ollama is not available
        self._ensure_model_exists()

    def _ensure_model_exists(self):
        """
        Ensure the specified model exists locally. If not, pull it from Ollama.
        Gracefully handles connection failures by deferring model checks.
        """
        try:
            local_models = self.client.list()["models"]
            model_exists = any(
                model.get("name") == self.config.model
                or model.get("model") == self.config.model
                for model in local_models
            )
            
            if not model_exists:
                logging.info(f"Pulling Ollama model '{self.config.model}'...")
                self.client.pull(self.config.model)
                logging.info(f"Successfully pulled model '{self.config.model}'")
            else:
                logging.info(f"Ollama model '{self.config.model}' is available")
            
            self._model_checked = True
            self._model_available = True
            
        except Exception as e:
            # Log warning but don't fail - allow application to start
            logging.warning(
                f"Could not connect to Ollama to check model '{self.config.model}': {e}. "
                f"Model availability will be checked when embeddings are first used."
            )
            self._model_checked = False
            self._model_available = False

    def _check_model_on_demand(self):
        """
        Check model availability when embedding is first attempted.
        This is a fallback for when the initial check failed during initialization.
        """
        if not self._model_checked:
            try:
                local_models = self.client.list()["models"]
                model_exists = any(
                    model.get("name") == self.config.model
                    or model.get("model") == self.config.model
                    for model in local_models
                )
                
                if not model_exists:
                    logging.info(f"Pulling required Ollama model '{self.config.model}'...")
                    self.client.pull(self.config.model)
                    logging.info(f"Successfully pulled model '{self.config.model}'")
                
                self._model_checked = True
                self._model_available = True
                logging.info(f"Ollama connection established, model '{self.config.model}' is ready")
                
            except Exception as e:
                logging.error(f"Failed to connect to Ollama or pull model '{self.config.model}': {e}")
                raise RuntimeError(
                    f"Ollama is not available or model '{self.config.model}' cannot be accessed. "
                    f"Please ensure Ollama is running and the model is available."
                ) from e

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
        # Check model availability on first use if initial check failed
        if not self._model_available:
            self._check_model_on_demand()
        
        try:
            response = self.client.embeddings(model=self.config.model, prompt=text)
            return response["embedding"]
        except Exception as e:
            # If embedding fails, it might be a connection issue - reset availability flag
            if "connection" in str(e).lower() or "connect" in str(e).lower():
                self._model_available = False
                self._model_checked = False
                logging.error(f"Lost connection to Ollama during embedding: {e}")
            raise
