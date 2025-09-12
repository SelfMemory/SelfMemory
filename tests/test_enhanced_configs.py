"""
Test enhanced configuration validation.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from inmemory.configs.embeddings.ollama import OllamaConfig
from inmemory.configs.vector_stores.qdrant import QdrantConfig
from inmemory.utils.factory import EmbeddingFactory, VectorStoreFactory


class TestOllamaConfig:
    """Test OllamaConfig validation."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = OllamaConfig(
            model="nomic-embed-text",
            embedding_dims=768,
            ollama_base_url="http://localhost:11434",
        )
        assert config.model == "nomic-embed-text"
        assert config.embedding_dims == 768
        assert config.ollama_base_url == "http://localhost:11434"
        assert config.timeout == 30
        assert config.verify_ssl == True
        assert config.max_retries == 3

    def test_invalid_model_name_empty(self):
        """Test invalid empty model name."""
        with pytest.raises(ValueError, match="Model name cannot be empty"):
            OllamaConfig(model="")

    def test_invalid_model_name_whitespace(self):
        """Test invalid whitespace-only model name."""
        with pytest.raises(ValueError, match="Model name cannot be empty"):
            OllamaConfig(model="   ")

    def test_invalid_model_name_special_chars(self):
        """Test invalid model name with special characters."""
        with pytest.raises(
            ValueError, match="can only contain alphanumeric characters"
        ):
            OllamaConfig(model="model@name")

    def test_invalid_model_name_too_long(self):
        """Test invalid model name that's too long."""
        long_name = "a" * 101
        with pytest.raises(ValueError, match="cannot exceed 100 characters"):
            OllamaConfig(model=long_name)

    def test_valid_model_name_with_allowed_chars(self):
        """Test valid model name with allowed characters."""
        config = OllamaConfig(model="model-name_v1.2")
        assert config.model == "model-name_v1.2"

    def test_invalid_embedding_dims_negative(self):
        """Test invalid negative embedding dimensions."""
        with pytest.raises(ValueError, match="Embedding dimensions must be positive"):
            OllamaConfig(embedding_dims=-1)

    def test_invalid_embedding_dims_zero(self):
        """Test invalid zero embedding dimensions."""
        with pytest.raises(ValueError, match="Embedding dimensions must be positive"):
            OllamaConfig(embedding_dims=0)

    def test_invalid_embedding_dims_too_large(self):
        """Test invalid embedding dimensions that are too large."""
        with pytest.raises(ValueError, match="cannot exceed 10000"):
            OllamaConfig(embedding_dims=20000)

    def test_invalid_embedding_dims_too_small(self):
        """Test invalid embedding dimensions that are too small."""
        with pytest.raises(ValueError, match="should be at least 50"):
            OllamaConfig(embedding_dims=10)

    def test_valid_embedding_dims_boundary(self):
        """Test valid embedding dimensions at boundaries."""
        config1 = OllamaConfig(embedding_dims=50)
        assert config1.embedding_dims == 50

        config2 = OllamaConfig(embedding_dims=10000)
        assert config2.embedding_dims == 10000

    def test_invalid_url_no_protocol(self):
        """Test invalid URL without protocol."""
        with pytest.raises(ValueError, match="must start with http"):
            OllamaConfig(ollama_base_url="localhost:11434")

    def test_invalid_url_no_host(self):
        """Test invalid URL without host."""
        with pytest.raises(ValueError, match="Invalid URL: missing host"):
            OllamaConfig(ollama_base_url="http://")

    def test_valid_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from URL."""
        config = OllamaConfig(ollama_base_url="http://localhost:11434/")
        assert config.ollama_base_url == "http://localhost:11434"

    def test_invalid_timeout_negative(self):
        """Test invalid negative timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            OllamaConfig(timeout=-1)

    def test_invalid_timeout_zero(self):
        """Test invalid zero timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            OllamaConfig(timeout=0)

    def test_invalid_timeout_too_large(self):
        """Test invalid timeout that's too large."""
        with pytest.raises(ValueError, match="cannot exceed 300 seconds"):
            OllamaConfig(timeout=400)

    def test_invalid_max_retries_negative(self):
        """Test invalid negative max retries."""
        with pytest.raises(ValueError, match="Max retries cannot be negative"):
            OllamaConfig(max_retries=-1)

    def test_invalid_max_retries_too_large(self):
        """Test invalid max retries that's too large."""
        with pytest.raises(ValueError, match="cannot exceed 10"):
            OllamaConfig(max_retries=15)

    def test_extra_fields_rejected(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValueError, match="Extra fields not allowed"):
            OllamaConfig(model="test", invalid_field="value")

    @patch("requests.get")
    def test_connection_validation_success(self, mock_get):
        """Test successful connection validation."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "nomic-embed-text"}, {"name": "llama2"}]
        }
        mock_get.return_value = mock_response

        with patch.dict(os.environ, {"INMEMORY_VALIDATE_CONNECTIONS": "true"}):
            config = OllamaConfig(model="nomic-embed-text")
            # Should not raise an exception
            assert config.model == "nomic-embed-text"

    @patch("requests.get")
    def test_connection_validation_model_not_found(self, mock_get):
        """Test connection validation when model is not found."""
        # Mock successful response but model not in list
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama2"}, {"name": "codellama"}]
        }
        mock_get.return_value = mock_response

        with patch.dict(os.environ, {"INMEMORY_VALIDATE_CONNECTIONS": "true"}):
            # Should create config but log warning (not raise exception)
            config = OllamaConfig(model="nomic-embed-text")
            assert config.model == "nomic-embed-text"

    def test_test_connection_method(self):
        """Test the test_connection method."""
        config = OllamaConfig()

        with patch("requests.get") as mock_get:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": [{"name": "nomic-embed-text"}]}
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response

            result = config.test_connection()

            assert result["status"] == "connected"
            assert result["server_url"] == "http://localhost:11434"
            assert result["model_exists"] == True
            assert "response_time_ms" in result


class TestQdrantConfig:
    """Test QdrantConfig validation."""

    def test_valid_local_config(self):
        """Test valid local configuration."""
        config = QdrantConfig(path="/tmp/qdrant")
        assert config.path == "/tmp/qdrant"
        assert config.collection_name == "inmemory_memories"

    def test_valid_server_config(self):
        """Test valid server configuration."""
        config = QdrantConfig(host="localhost", port=6333)
        assert config.host == "localhost"
        assert config.port == 6333

    def test_valid_url_config(self):
        """Test valid URL configuration."""
        config = QdrantConfig(
            url="https://xyz.qdrant.io", api_key="test-key-1234567890"
        )
        assert config.url == "https://xyz.qdrant.io"
        assert config.api_key == "test-key-1234567890"

    def test_default_path_when_no_connection(self):
        """Test that default path is set when no connection method specified."""
        config = QdrantConfig()
        assert config.path == "/tmp/qdrant"

    def test_multiple_connection_methods_rejected(self):
        """Test rejection of multiple connection methods."""
        with pytest.raises(ValueError, match="Only one connection method allowed"):
            QdrantConfig(path="/tmp/qdrant", host="localhost", port=6333)

    def test_invalid_collection_name_empty(self):
        """Test invalid empty collection name."""
        with pytest.raises(ValueError, match="Collection name cannot be empty"):
            QdrantConfig(collection_name="")

    def test_invalid_collection_name_starts_with_number(self):
        """Test invalid collection name starting with number."""
        with pytest.raises(ValueError, match="must start with a letter or underscore"):
            QdrantConfig(collection_name="123invalid")

    def test_invalid_collection_name_special_chars(self):
        """Test invalid collection name with special characters."""
        with pytest.raises(
            ValueError,
            match="can only contain letters, numbers, underscores, and hyphens",
        ):
            QdrantConfig(collection_name="collection@name")

    def test_invalid_collection_name_too_long(self):
        """Test invalid collection name that's too long."""
        long_name = "a" * 256
        with pytest.raises(ValueError, match="cannot exceed 255 characters"):
            QdrantConfig(collection_name=long_name)

    def test_valid_collection_name_with_allowed_chars(self):
        """Test valid collection name with allowed characters."""
        config = QdrantConfig(collection_name="my_collection-v1")
        assert config.collection_name == "my_collection-v1"

    def test_invalid_embedding_dims_negative(self):
        """Test invalid negative embedding dimensions."""
        with pytest.raises(ValueError, match="Embedding dimensions must be positive"):
            QdrantConfig(embedding_model_dims=-1)

    def test_invalid_embedding_dims_too_large(self):
        """Test invalid embedding dimensions exceeding Qdrant limit."""
        with pytest.raises(ValueError, match="cannot exceed 65536"):
            QdrantConfig(embedding_model_dims=70000)

    def test_invalid_port_negative(self):
        """Test invalid negative port."""
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            QdrantConfig(host="localhost", port=-1)

    def test_invalid_port_too_large(self):
        """Test invalid port that's too large."""
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            QdrantConfig(host="localhost", port=70000)

    def test_invalid_url_no_protocol(self):
        """Test invalid URL without protocol."""
        with pytest.raises(ValueError, match="must start with http"):
            QdrantConfig(url="localhost:6333")

    def test_invalid_api_key_too_short(self):
        """Test invalid API key that's too short."""
        with pytest.raises(ValueError, match="API key too short"):
            QdrantConfig(url="https://test.qdrant.io", api_key="short")

    def test_invalid_api_key_too_long(self):
        """Test invalid API key that's too long."""
        long_key = "a" * 501
        with pytest.raises(ValueError, match="API key too long"):
            QdrantConfig(url="https://test.qdrant.io", api_key=long_key)

    def test_cloud_config_requires_https(self):
        """Test that cloud config with API key requires HTTPS."""
        with pytest.raises(ValueError, match="requires HTTPS URL"):
            QdrantConfig(url="http://test.qdrant.io", api_key="test-key-1234567890")

    def test_path_expansion(self):
        """Test that path is expanded properly."""
        config = QdrantConfig(path="~/qdrant")
        assert config.path == os.path.expanduser("~/qdrant")

    def test_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from URL."""
        config = QdrantConfig(url="https://test.qdrant.io/")
        assert config.url == "https://test.qdrant.io"

    def test_extra_fields_rejected(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValueError, match="Extra fields not allowed"):
            QdrantConfig(path="/tmp/qdrant", invalid_field="value")

    def test_test_connection_method_local(self):
        """Test the test_connection method for local path."""
        config = QdrantConfig(path="/tmp/test_qdrant")

        # Test when path doesn't exist
        result = config.test_connection()
        assert result["status"] in ["path_not_exists", "connected"]
        assert result["connection_type"] == "local_file"


class TestFactoryValidation:
    """Test factory validation methods."""

    def test_embedding_factory_validation_valid(self):
        """Test embedding factory validation with valid config."""
        config = {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434",
        }
        result = EmbeddingFactory.validate_config("ollama", config)
        assert result["status"] in ["valid", "invalid"]
        assert result["provider"] == "ollama"

    def test_embedding_factory_validation_invalid(self):
        """Test embedding factory validation with invalid config."""
        config = {"model": "", "ollama_base_url": "invalid-url"}
        result = EmbeddingFactory.validate_config("ollama", config)
        assert result["status"] == "invalid"
        assert "error" in result

    def test_vector_store_factory_validation_valid(self):
        """Test vector store factory validation with valid config."""
        config = {"path": "/tmp/qdrant", "collection_name": "test_collection"}
        result = VectorStoreFactory.validate_config("qdrant", config)
        assert result["status"] in ["valid", "invalid"]
        assert result["provider"] == "qdrant"

    def test_vector_store_factory_validation_invalid(self):
        """Test vector store factory validation with invalid config."""
        config = {"collection_name": "123invalid", "embedding_model_dims": -1}
        result = VectorStoreFactory.validate_config("qdrant", config)
        assert result["status"] == "invalid"
        assert "error" in result

    def test_embedding_factory_provider_info_static(self):
        """Test embedding factory provider info for static provider."""
        info = EmbeddingFactory.get_provider_info("ollama")
        assert info["provider"] == "ollama"
        assert info["type"] == "static"
        assert info["loaded"] == True

    def test_embedding_factory_provider_info_dynamic(self):
        """Test embedding factory provider info for dynamic provider."""
        info = EmbeddingFactory.get_provider_info("openai")
        assert info["provider"] == "openai"
        assert info["type"] == "dynamic"
        assert "loaded" in info

    def test_embedding_factory_provider_info_unknown(self):
        """Test embedding factory provider info for unknown provider."""
        info = EmbeddingFactory.get_provider_info("unknown_provider")
        assert info["provider"] == "unknown_provider"
        assert info["type"] == "unknown"
        assert info["supported"] == False

    def test_vector_store_factory_provider_info_static(self):
        """Test vector store factory provider info for static provider."""
        info = VectorStoreFactory.get_provider_info("qdrant")
        assert info["provider"] == "qdrant"
        assert info["type"] == "static"
        assert info["loaded"] == True

    def test_vector_store_factory_provider_info_dynamic(self):
        """Test vector store factory provider info for dynamic provider."""
        info = VectorStoreFactory.get_provider_info("chroma")
        assert info["provider"] == "chroma"
        assert info["type"] == "dynamic"
        assert "loaded" in info

    def test_get_supported_providers(self):
        """Test getting supported providers."""
        embedding_providers = EmbeddingFactory.get_supported_providers()
        assert "ollama" in embedding_providers
        assert "openai" in embedding_providers

        vector_store_providers = VectorStoreFactory.get_supported_providers()
        assert "qdrant" in vector_store_providers
        assert "chroma" in vector_store_providers


if __name__ == "__main__":
    pytest.main([__file__])
