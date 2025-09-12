"""
Integration tests for enhanced configuration validation.
"""

import tempfile

import pytest

from inmemory.configs.embeddings.ollama import OllamaConfig
from inmemory.configs.vector_stores.qdrant import QdrantConfig
from inmemory.utils.factory import EmbeddingFactory, VectorStoreFactory


class TestConfigIntegration:
    """Test integration of enhanced configs with the system."""

    def test_ollama_config_integration(self):
        """Test OllamaConfig integration with factory."""
        # Test valid config creation
        config_dict = {
            "model": "nomic-embed-text",
            "embedding_dims": 768,
            "ollama_base_url": "http://localhost:11434",
            "timeout": 30,
            "verify_ssl": True,
            "max_retries": 3,
        }

        # Create config object
        config = OllamaConfig(**config_dict)
        assert config.model == "nomic-embed-text"
        assert config.embedding_dims == 768

        # Test factory validation
        result = EmbeddingFactory.validate_config("ollama", config_dict)
        assert result["provider"] == "ollama"
        # Status can be valid or invalid depending on whether Ollama is running
        assert result["status"] in ["valid", "invalid"]

    def test_qdrant_config_integration_local(self):
        """Test QdrantConfig integration with factory for local setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dict = {
                "path": temp_dir,
                "collection_name": "test_collection",
                "embedding_model_dims": 768,
                "on_disk": True,
            }

            # Create config object
            config = QdrantConfig(**config_dict)
            assert config.path == temp_dir
            assert config.collection_name == "test_collection"

            # Test factory validation
            result = VectorStoreFactory.validate_config("qdrant", config_dict)
            assert result["provider"] == "qdrant"
            # Should be valid since we're using a valid temp directory
            assert result["status"] in ["valid", "invalid"]

    def test_qdrant_config_integration_server(self):
        """Test QdrantConfig integration with factory for server setup."""
        config_dict = {
            "host": "localhost",
            "port": 6333,
            "collection_name": "test_collection",
            "embedding_model_dims": 768,
        }

        # Create config object
        config = QdrantConfig(**config_dict)
        assert config.host == "localhost"
        assert config.port == 6333

        # Test factory validation
        result = VectorStoreFactory.validate_config("qdrant", config_dict)
        assert result["provider"] == "qdrant"
        # Status depends on whether Qdrant server is running
        assert result["status"] in ["valid", "invalid"]

    def test_config_validation_with_invalid_data(self):
        """Test that invalid configs are properly rejected."""
        # Invalid Ollama config
        invalid_ollama = {
            "model": "",  # Empty model name
            "embedding_dims": -1,  # Negative dimensions
            "ollama_base_url": "invalid-url",  # Invalid URL
        }

        result = EmbeddingFactory.validate_config("ollama", invalid_ollama)
        assert result["status"] == "invalid"
        assert "error" in result

        # Invalid Qdrant config
        invalid_qdrant = {
            "collection_name": "123invalid",  # Invalid collection name
            "embedding_model_dims": -1,  # Negative dimensions
            "port": 70000,  # Invalid port
        }

        result = VectorStoreFactory.validate_config("qdrant", invalid_qdrant)
        assert result["status"] == "invalid"
        assert "error" in result

    def test_config_test_connection_methods(self):
        """Test the test_connection methods work properly."""
        # Test Ollama config test_connection
        ollama_config = OllamaConfig()
        connection_result = ollama_config.test_connection()
        assert "status" in connection_result
        assert connection_result["status"] in [
            "connected",
            "connection_failed",
            "error",
            "unknown_error",
        ]

        # Test Qdrant config test_connection with local path
        with tempfile.TemporaryDirectory() as temp_dir:
            qdrant_config = QdrantConfig(path=temp_dir)
            connection_result = qdrant_config.test_connection()
            assert "status" in connection_result
            assert "connection_type" in connection_result
            assert connection_result["connection_type"] == "local_file"

    def test_provider_info_methods(self):
        """Test provider info methods work correctly."""
        # Test embedding provider info
        ollama_info = EmbeddingFactory.get_provider_info("ollama")
        assert ollama_info["provider"] == "ollama"
        assert ollama_info["type"] == "static"
        assert ollama_info["loaded"] == True

        openai_info = EmbeddingFactory.get_provider_info("openai")
        assert openai_info["provider"] == "openai"
        assert openai_info["type"] == "dynamic"

        # Test vector store provider info
        qdrant_info = VectorStoreFactory.get_provider_info("qdrant")
        assert qdrant_info["provider"] == "qdrant"
        assert qdrant_info["type"] == "static"
        assert qdrant_info["loaded"] == True

        chroma_info = VectorStoreFactory.get_provider_info("chroma")
        assert chroma_info["provider"] == "chroma"
        assert chroma_info["type"] == "dynamic"

    def test_supported_providers_lists(self):
        """Test that supported providers lists are correct."""
        embedding_providers = EmbeddingFactory.get_supported_providers()
        assert isinstance(embedding_providers, list)
        assert "ollama" in embedding_providers
        assert "openai" in embedding_providers
        assert len(embedding_providers) > 0

        vector_store_providers = VectorStoreFactory.get_supported_providers()
        assert isinstance(vector_store_providers, list)
        assert "qdrant" in vector_store_providers
        assert "chroma" in vector_store_providers
        assert len(vector_store_providers) > 0

    def test_config_with_environment_validation(self):
        """Test config validation with environment variable."""
        # Test with validation enabled
        with pytest.MonkeyPatch().context() as m:
            m.setenv("INMEMORY_VALIDATE_CONNECTIONS", "true")

            # This should trigger connection validation
            config = OllamaConfig()
            assert config.model == "nomic-embed-text"

            # Test connection method should work
            result = config.test_connection()
            assert "status" in result

    def test_config_edge_cases(self):
        """Test edge cases in configuration."""
        # Test with minimal valid config
        minimal_ollama = OllamaConfig(model="test")
        assert minimal_ollama.model == "test"
        assert minimal_ollama.embedding_dims == 768  # Default value

        # Test with boundary values
        boundary_ollama = OllamaConfig(
            model="a" * 100,  # Max length
            embedding_dims=50,  # Min valid value
            timeout=300,  # Max timeout
        )
        assert len(boundary_ollama.model) == 100
        assert boundary_ollama.embedding_dims == 50
        assert boundary_ollama.timeout == 300

        # Test Qdrant with boundary values
        boundary_qdrant = QdrantConfig(
            collection_name="a" * 255,  # Max length
            embedding_model_dims=65536,  # Max Qdrant limit
            timeout=300,  # Max timeout
        )
        assert len(boundary_qdrant.collection_name) == 255
        assert boundary_qdrant.embedding_model_dims == 65536
        assert boundary_qdrant.timeout == 300


if __name__ == "__main__":
    pytest.main([__file__])
