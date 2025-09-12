"""
Demonstration of enhanced configuration validation features.

This script showcases the new validation capabilities added in Phase 3.
"""

import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from inmemory.configs.embeddings.ollama import OllamaConfig
from inmemory.configs.vector_stores.qdrant import QdrantConfig
from inmemory.utils.factory import EmbeddingFactory, VectorStoreFactory


def demo_ollama_validation():
    """Demonstrate OllamaConfig validation features."""
    print("🔧 OLLAMA CONFIG VALIDATION DEMO")
    print("=" * 50)

    # Valid configuration
    print("\n✅ Valid Configuration:")
    try:
        config = OllamaConfig(
            model="nomic-embed-text",
            embedding_dims=768,
            ollama_base_url="http://localhost:11434",
            timeout=30,
            verify_ssl=True,
            max_retries=3,
        )
        print(f"   Model: {config.model}")
        print(f"   Embedding Dims: {config.embedding_dims}")
        print(f"   URL: {config.ollama_base_url}")
        print(f"   Timeout: {config.timeout}s")
        print(f"   Verify SSL: {config.verify_ssl}")
        print(f"   Max Retries: {config.max_retries}")

        # Test connection
        print("\n🔗 Testing Connection:")
        connection_result = config.test_connection()
        print(f"   Status: {connection_result['status']}")
        if connection_result["status"] == "connected":
            print(
                f"   Available Models: {len(connection_result.get('available_models', []))}"
            )
            print(f"   Model Exists: {connection_result.get('model_exists', False)}")
            print(
                f"   Response Time: {connection_result.get('response_time_ms', 0):.2f}ms"
            )
        else:
            print(f"   Error: {connection_result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"   Error: {e}")

    # Invalid configurations
    print("\n❌ Invalid Configurations:")

    invalid_configs = [
        {"model": "", "description": "Empty model name"},
        {"model": "model@invalid", "description": "Invalid characters in model name"},
        {"embedding_dims": -1, "description": "Negative embedding dimensions"},
        {"embedding_dims": 20000, "description": "Too large embedding dimensions"},
        {"ollama_base_url": "invalid-url", "description": "Invalid URL format"},
        {"timeout": -1, "description": "Negative timeout"},
        {"max_retries": 15, "description": "Too many retries"},
        {"model": "test", "invalid_field": "value", "description": "Extra fields"},
    ]

    for invalid_config in invalid_configs:
        description = invalid_config.pop("description")
        print(f"\n   {description}:")
        try:
            OllamaConfig(**invalid_config)
            print("     ⚠️  Unexpectedly passed validation!")
        except ValueError as e:
            print(f"     ✅ Correctly rejected: {e}")
        except Exception as e:
            print(f"     ❓ Unexpected error: {e}")


def demo_qdrant_validation():
    """Demonstrate QdrantConfig validation features."""
    print("\n\n🗄️  QDRANT CONFIG VALIDATION DEMO")
    print("=" * 50)

    # Valid configurations
    print("\n✅ Valid Configurations:")

    # Local configuration
    print("\n   Local Configuration:")
    try:
        config = QdrantConfig(path="/tmp/qdrant_demo")
        print(f"     Path: {config.path}")
        print(f"     Collection: {config.collection_name}")
        print(f"     Embedding Dims: {config.embedding_model_dims}")

        # Test connection
        connection_result = config.test_connection()
        print(f"     Connection Status: {connection_result['status']}")
        print(
            f"     Connection Type: {connection_result.get('connection_type', 'unknown')}"
        )

    except Exception as e:
        print(f"     Error: {e}")

    # Server configuration
    print("\n   Server Configuration:")
    try:
        config = QdrantConfig(host="localhost", port=6333)
        print(f"     Host: {config.host}")
        print(f"     Port: {config.port}")
        print(f"     Collection: {config.collection_name}")

        # Test connection
        connection_result = config.test_connection()
        print(f"     Connection Status: {connection_result['status']}")
        if connection_result["status"] == "connected":
            print(f"     Collections: {connection_result.get('collections', 0)}")
            print(
                f"     Response Time: {connection_result.get('response_time_ms', 0):.2f}ms"
            )

    except Exception as e:
        print(f"     Error: {e}")

    # Cloud configuration
    print("\n   Cloud Configuration:")
    try:
        config = QdrantConfig(
            url="https://example.qdrant.io", api_key="test-key-1234567890"
        )
        print(f"     URL: {config.url}")
        print(f"     API Key: {config.api_key[:10]}...")
        print(f"     Collection: {config.collection_name}")

    except Exception as e:
        print(f"     Error: {e}")

    # Invalid configurations
    print("\n❌ Invalid Configurations:")

    invalid_configs = [
        {"collection_name": "", "description": "Empty collection name"},
        {
            "collection_name": "123invalid",
            "description": "Collection name starting with number",
        },
        {
            "collection_name": "collection@name",
            "description": "Invalid characters in collection name",
        },
        {"embedding_model_dims": -1, "description": "Negative embedding dimensions"},
        {
            "embedding_model_dims": 70000,
            "description": "Too large embedding dimensions",
        },
        {"host": "localhost", "port": -1, "description": "Invalid port number"},
        {"url": "invalid-url", "description": "Invalid URL format"},
        {
            "url": "http://test.qdrant.io",
            "api_key": "test-key-1234567890",
            "description": "HTTP URL with API key (should be HTTPS)",
        },
        {
            "path": "/tmp/test",
            "host": "localhost",
            "port": 6333,
            "description": "Multiple connection methods",
        },
        {
            "collection_name": "test",
            "invalid_field": "value",
            "description": "Extra fields",
        },
    ]

    for invalid_config in invalid_configs:
        description = invalid_config.pop("description")
        print(f"\n   {description}:")
        try:
            QdrantConfig(**invalid_config)
            print("     ⚠️  Unexpectedly passed validation!")
        except ValueError as e:
            print(f"     ✅ Correctly rejected: {e}")
        except Exception as e:
            print(f"     ❓ Unexpected error: {e}")


def demo_factory_validation():
    """Demonstrate factory validation features."""
    print("\n\n🏭 FACTORY VALIDATION DEMO")
    print("=" * 50)

    # Embedding factory validation
    print("\n✅ Embedding Factory Validation:")

    valid_config = {
        "model": "nomic-embed-text",
        "ollama_base_url": "http://localhost:11434",
    }

    result = EmbeddingFactory.validate_config("ollama", valid_config)
    print(f"   Provider: {result['provider']}")
    print(f"   Status: {result['status']}")
    if "connection_test" in result:
        print(f"   Connection Test: {result['connection_test']['status']}")

    # Invalid config
    invalid_config = {"model": "", "ollama_base_url": "invalid-url"}
    result = EmbeddingFactory.validate_config("ollama", invalid_config)
    print(f"\n   Invalid Config Status: {result['status']}")
    if "error" in result:
        print(f"   Error: {result['error']}")

    # Vector store factory validation
    print("\n✅ Vector Store Factory Validation:")

    valid_config = {"path": "/tmp/qdrant", "collection_name": "test_collection"}
    result = VectorStoreFactory.validate_config("qdrant", valid_config)
    print(f"   Provider: {result['provider']}")
    print(f"   Status: {result['status']}")

    # Provider information
    print("\n📋 Provider Information:")

    # Embedding providers
    print("\n   Embedding Providers:")
    providers = EmbeddingFactory.get_supported_providers()
    for provider in providers:
        info = EmbeddingFactory.get_provider_info(provider)
        print(
            f"     {provider}: {info['type']} ({'loaded' if info.get('loaded') else 'not loaded'})"
        )

    # Vector store providers
    print("\n   Vector Store Providers:")
    providers = VectorStoreFactory.get_supported_providers()
    for provider in providers:
        info = VectorStoreFactory.get_provider_info(provider)
        print(
            f"     {provider}: {info['type']} ({'loaded' if info.get('loaded') else 'not loaded'})"
        )


def main():
    """Run all validation demos."""
    print("🚀 INMEMORY CONFIG VALIDATION DEMO")
    print("=" * 60)
    print("This demo showcases the enhanced configuration validation")
    print("features implemented in Phase 3 of the project.")
    print("=" * 60)

    try:
        demo_ollama_validation()
        demo_qdrant_validation()
        demo_factory_validation()

        print("\n\n✨ DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("Key Features Demonstrated:")
        print("• Comprehensive input validation")
        print("• Connection testing capabilities")
        print("• Factory pattern with validation")
        print("• Provider information and discovery")
        print("• Proper error handling and reporting")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
