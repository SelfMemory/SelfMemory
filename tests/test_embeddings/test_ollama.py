"""
Unit tests for Ollama embedding provider.

Tests the OllamaEmbedding class following  testing patterns
with comprehensive mocking of external Ollama API calls.
"""

from unittest.mock import Mock, patch

import pytest

from inmemory.embeddings.configs import BaseEmbedderConfig
from inmemory.embeddings.ollama import OllamaEmbedding


@pytest.fixture
def mock_ollama_client():
    """
    Mock Ollama client following  pattern.

    This fixture mocks the Ollama Client to avoid actual API calls
    and provides predictable responses for testing.
    """
    with patch("inmemory.embeddings.ollama.Client") as mock_ollama:
        mock_client = Mock()
        mock_client.list.return_value = {"models": [{"name": "nomic-embed-text"}]}
        mock_ollama.return_value = mock_client
        yield mock_client


class TestOllamaEmbedding:
    """Test the OllamaEmbedding provider implementation."""

    def test_embed_text_success(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Successful text embedding generation

        Mocks used:
        - mock_ollama_client: Returns fake embedding vector

        Expected behavior:
        - Should call Ollama embeddings API with correct parameters
        - Should return the embedding vector from API response
        - Should use configured model name

        How the test works:
        1. Configure mock to return fake embedding
        2. Create OllamaEmbedding instance
        3. Call embed() method
        4. Verify API was called correctly
        5. Verify returned embedding matches mock response
        """
        config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=768)
        embedder = OllamaEmbedding(config)

        # Configure mock response
        mock_response = {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}
        mock_ollama_client.embeddings.return_value = mock_response

        text = "Sample text to embed."
        embedding = embedder.embed(text)

        # Verify API call
        mock_ollama_client.embeddings.assert_called_once_with(
            model="nomic-embed-text", prompt=text
        )

        # Verify result
        assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_embed_with_custom_model(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Embedding with custom model configuration

        Expected behavior:
        - Should use the configured model name in API calls
        - Should work with different model names
        """
        config = BaseEmbedderConfig(model="custom-embed-model", embedding_dims=512)
        embedder = OllamaEmbedding(config)

        mock_response = {"embedding": [0.1, 0.2, 0.3]}
        mock_ollama_client.embeddings.return_value = mock_response

        text = "Test text"
        embedding = embedder.embed(text)

        # Verify custom model was used
        mock_ollama_client.embeddings.assert_called_once_with(
            model="custom-embed-model", prompt=text
        )
        assert embedding == [0.1, 0.2, 0.3]

    def test_embed_empty_text(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Embedding empty or whitespace text

        Expected behavior:
        - Should handle empty strings gracefully
        - Should still call API (let Ollama handle empty input)
        """
        config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=768)
        embedder = OllamaEmbedding(config)

        mock_response = {"embedding": [0.0] * 768}
        mock_ollama_client.embeddings.return_value = mock_response

        # Test empty string
        embedding = embedder.embed("")

        mock_ollama_client.embeddings.assert_called_once_with(
            model="nomic-embed-text", prompt=""
        )
        assert len(embedding) == 768

    def test_embed_long_text(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Embedding long text content

        Expected behavior:
        - Should handle long text without issues
        - Should pass full text to Ollama API
        """
        config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=768)
        embedder = OllamaEmbedding(config)

        mock_response = {"embedding": [0.1] * 768}
        mock_ollama_client.embeddings.return_value = mock_response

        # Create long text (simulate a document)
        long_text = "This is a very long text. " * 100

        embedding = embedder.embed(long_text)

        mock_ollama_client.embeddings.assert_called_once_with(
            model="nomic-embed-text", prompt=long_text
        )
        assert len(embedding) == 768

    def test_ensure_model_exists_model_available(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Model availability check when model exists

        Expected behavior:
        - Should check if model is available in Ollama
        - Should not attempt to pull if model already exists
        """
        config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=768)
        embedder = OllamaEmbedding(config)

        # Model is already in the list (configured in fixture)
        embedder._ensure_model_exists()

        # Should not call pull since model exists
        mock_ollama_client.pull.assert_not_called()

    def test_ensure_model_exists_model_missing(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Model availability check when model is missing

        Expected behavior:
        - Should detect missing model
        - Should attempt to pull the model
        """
        # Configure empty model list (model not available)
        mock_ollama_client.list.return_value = {"models": []}

        config = BaseEmbedderConfig(model="missing-model", embedding_dims=768)
        embedder = OllamaEmbedding(config)

        # Reset the mock to clear the call from __init__
        mock_ollama_client.pull.reset_mock()

        embedder._ensure_model_exists()

        # Should attempt to pull the missing model
        mock_ollama_client.pull.assert_called_once_with("missing-model")

    def test_embed_api_error_handling(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Error handling when Ollama API fails

        Expected behavior:
        - Should propagate API errors appropriately
        - Should not crash silently
        """
        config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=768)
        embedder = OllamaEmbedding(config)

        # Configure API to raise exception
        mock_ollama_client.embeddings.side_effect = Exception("Ollama API unavailable")

        with pytest.raises(Exception) as exc_info:
            embedder.embed("test text")

        assert "Ollama API unavailable" in str(exc_info.value)

    def test_embed_malformed_response(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Handling malformed API responses

        Expected behavior:
        - Should handle cases where API response is missing 'embedding' key
        - Should raise appropriate error
        """
        config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=768)
        embedder = OllamaEmbedding(config)

        # Configure malformed response (missing 'embedding' key)
        mock_response = {"error": "Invalid request"}
        mock_ollama_client.embeddings.return_value = mock_response

        with pytest.raises(KeyError):
            embedder.embed("test text")

    def test_config_validation(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Configuration validation

        Expected behavior:
        - Should accept valid BaseEmbedderConfig
        - Should store config properly
        """
        config = BaseEmbedderConfig(
            model="custom-model",
            embedding_dims=1024,
            ollama_base_url="http://custom:11434",
        )

        embedder = OllamaEmbedding(config)

        assert embedder.config.model == "custom-model"
        assert embedder.config.embedding_dims == 1024
        assert embedder.config.ollama_base_url == "http://custom:11434"

    def test_client_initialization_with_custom_url(self):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Client initialization with custom Ollama URL

        Expected behavior:
        - Should use custom URL from config
        - Should initialize Ollama client with correct host
        """
        config = BaseEmbedderConfig(
            model="nomic-embed-text", ollama_base_url="http://custom-ollama:11434"
        )

        with patch("inmemory.embeddings.ollama.Client") as mock_client_class:
            embedder = OllamaEmbedding(config)

            # Verify client was initialized with custom URL
            mock_client_class.assert_called_once_with(host="http://custom-ollama:11434")


class TestOllamaEmbeddingIntegration:
    """Test integration scenarios and edge cases."""

    def test_multiple_embeds_same_instance(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Multiple embedding calls on same instance

        Expected behavior:
        - Should handle multiple calls correctly
        - Should maintain state between calls
        """
        config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=768)
        embedder = OllamaEmbedding(config)

        # Configure different responses for different calls
        mock_responses = [
            {"embedding": [0.1, 0.2, 0.3]},
            {"embedding": [0.4, 0.5, 0.6]},
        ]
        mock_ollama_client.embeddings.side_effect = mock_responses

        # Make multiple calls
        embedding1 = embedder.embed("First text")
        embedding2 = embedder.embed("Second text")

        # Verify both calls were made
        assert mock_ollama_client.embeddings.call_count == 2
        assert embedding1 == [0.1, 0.2, 0.3]
        assert embedding2 == [0.4, 0.5, 0.6]

    def test_embedding_dimensions_consistency(self, mock_ollama_client):
        """
        TEST EXPLANATION:
        ================
        What I'm testing: Embedding dimension consistency

        Expected behavior:
        - Should return embeddings with expected dimensions
        - Should be consistent across calls
        """
        config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=768)
        embedder = OllamaEmbedding(config)

        # Configure response with correct dimensions
        mock_response = {"embedding": [0.1] * 768}
        mock_ollama_client.embeddings.return_value = mock_response

        embedding = embedder.embed("test text")

        # Verify dimensions match config
        assert len(embedding) == 768
        assert len(embedding) == config.embedding_dims


# Summary of what we've tested:
# =============================
# 1. Successful text embedding generation
# 2. Custom model configuration
# 3. Empty and long text handling
# 4. Model availability checking and pulling
# 5. API error handling and malformed responses
# 6. Configuration validation
# 7. Client initialization with custom URLs
# 8. Multiple embedding calls and dimension consistency
#
# This follows  testing pattern for Ollama embeddings with
# comprehensive mocking and covers all critical functionality.
