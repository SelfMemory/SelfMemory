# Embeddings module for Ollama embedding provider
#
# This module provides the Ollama embedding provider following clean architecture patterns.
# Use direct imports for the embedding provider and configuration.
#
# Example usage:
#   from selfmemory.embeddings.ollama import OllamaEmbedding
#   from selfmemory.embeddings.configs import OllamaEmbedderConfig
#
#   config = OllamaEmbedderConfig(model="nomic-embed-text")
#   embedder = OllamaEmbedding(config)
#   embedding = embedder.embed("Hello world")
