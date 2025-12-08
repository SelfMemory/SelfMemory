import importlib
from typing import Dict, Optional, Union

from selfmemory.configs.embeddings.base import BaseEmbedderConfig
from selfmemory.configs.llms.anthropic import AnthropicConfig
from selfmemory.configs.llms.azure import AzureOpenAIConfig
from selfmemory.configs.llms.base import BaseLlmConfig
from selfmemory.configs.llms.deepseek import DeepSeekConfig
from selfmemory.configs.llms.lmstudio import LMStudioConfig
from selfmemory.configs.llms.ollama import OllamaConfig
from selfmemory.configs.llms.openai import OpenAIConfig
from selfmemory.configs.llms.vllm import VllmConfig
# from selfmemory.configs.rerankers.base import BaseRerankerConfig
# from selfmemory.configs.rerankers.cohere import CohereRerankerConfig
# from selfmemory.configs.rerankers.sentence_transformer import SentenceTransformerRerankerConfig
# from selfmemory.configs.rerankers.zero_entropy import ZeroEntropyRerankerConfig
# from selfmemory.configs.rerankers.llm import LLMRerankerConfig
# from selfmemory.configs.rerankers.huggingface import HuggingFaceRerankerConfig
from selfmemory.embeddings.mock import MockEmbeddings


def load_class(class_type):
    module_path, class_name = class_type.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class LlmFactory:
    """
    Factory for creating LLM instances with appropriate configurations.
    Supports both old-style BaseLlmConfig and new provider-specific configs.
    """

    # Provider mappings with their config classes
    provider_to_class = {
        "ollama": ("selfmemory.llms.ollama.OllamaLLM", OllamaConfig),
        "openai": ("selfmemory.llms.openai.OpenAILLM", OpenAIConfig),
        "groq": ("selfmemory.llms.groq.GroqLLM", BaseLlmConfig),
        "together": ("selfmemory.llms.together.TogetherLLM", BaseLlmConfig),
        "aws_bedrock": ("selfmemory.llms.aws_bedrock.AWSBedrockLLM", BaseLlmConfig),
        "litellm": ("selfmemory.llms.litellm.LiteLLM", BaseLlmConfig),
        "azure_openai": ("selfmemory.llms.azure_openai.AzureOpenAILLM", AzureOpenAIConfig),
        "openai_structured": ("selfmemory.llms.openai_structured.OpenAIStructuredLLM", OpenAIConfig),
        "anthropic": ("selfmemory.llms.anthropic.AnthropicLLM", AnthropicConfig),
        "azure_openai_structured": ("selfmemory.llms.azure_openai_structured.AzureOpenAIStructuredLLM", AzureOpenAIConfig),
        "gemini": ("selfmemory.llms.gemini.GeminiLLM", BaseLlmConfig),
        "deepseek": ("selfmemory.llms.deepseek.DeepSeekLLM", DeepSeekConfig),
        "xai": ("selfmemory.llms.xai.XAILLM", BaseLlmConfig),
        "sarvam": ("selfmemory.llms.sarvam.SarvamLLM", BaseLlmConfig),
        "lmstudio": ("selfmemory.llms.lmstudio.LMStudioLLM", LMStudioConfig),
        "vllm": ("selfmemory.llms.vllm.VllmLLM", VllmConfig),
        "langchain": ("selfmemory.llms.langchain.LangchainLLM", BaseLlmConfig),
    }

    @classmethod
    def create(cls, provider_name: str, config: Optional[Union[BaseLlmConfig, Dict]] = None, **kwargs):
        """
        Create an LLM instance with the appropriate configuration.

        Args:
            provider_name (str): The provider name (e.g., 'openai', 'anthropic')
            config: Configuration object or dict. If None, will create default config
            **kwargs: Additional configuration parameters

        Returns:
            Configured LLM instance

        Raises:
            ValueError: If provider is not supported
        """
        if provider_name not in cls.provider_to_class:
            raise ValueError(f"Unsupported Llm provider: {provider_name}")

        class_type, config_class = cls.provider_to_class[provider_name]
        llm_class = load_class(class_type)

        # Handle configuration
        if config is None:
            # Create default config with kwargs
            config = config_class(**kwargs)
        elif isinstance(config, dict):
            # Merge dict config with kwargs
            config.update(kwargs)
            config = config_class(**config)
        elif isinstance(config, BaseLlmConfig):
            # Convert base config to provider-specific config if needed
            if config_class != BaseLlmConfig:
                # Convert to provider-specific config
                config_dict = {
                    "model": config.model,
                    "temperature": config.temperature,
                    "api_key": config.api_key,
                    "max_tokens": config.max_tokens,
                    "top_p": config.top_p,
                    "top_k": config.top_k,
                    "enable_vision": config.enable_vision,
                    "vision_details": config.vision_details,
                    "http_client_proxies": config.http_client,
                }
                config_dict.update(kwargs)
                config = config_class(**config_dict)
            else:
                # Use base config as-is
                pass
        else:
            # Assume it's already the correct config type
            pass

        return llm_class(config)

    @classmethod
    def register_provider(cls, name: str, class_path: str, config_class=None):
        """
        Register a new provider.

        Args:
            name (str): Provider name
            class_path (str): Full path to LLM class
            config_class: Configuration class for the provider (defaults to BaseLlmConfig)
        """
        if config_class is None:
            config_class = BaseLlmConfig
        cls.provider_to_class[name] = (class_path, config_class)

    @classmethod
    def get_supported_providers(cls) -> list:
        """
        Get list of supported providers.

        Returns:
            list: List of supported provider names
        """
        return list(cls.provider_to_class.keys())


class EmbedderFactory:
    provider_to_class = {
        "openai": "selfmemory.embeddings.openai.OpenAIEmbedding",
        "ollama": "selfmemory.embeddings.ollama.OllamaEmbedding",
        "huggingface": "selfmemory.embeddings.huggingface.HuggingFaceEmbedding",
        "azure_openai": "selfmemory.embeddings.azure_openai.AzureOpenAIEmbedding",
        "gemini": "selfmemory.embeddings.gemini.GoogleGenAIEmbedding",
        "vertexai": "selfmemory.embeddings.vertexai.VertexAIEmbedding",
        "together": "selfmemory.embeddings.together.TogetherEmbedding",
        "lmstudio": "selfmemory.embeddings.lmstudio.LMStudioEmbedding",
        "langchain": "selfmemory.embeddings.langchain.LangchainEmbedding",
        "aws_bedrock": "selfmemory.embeddings.aws_bedrock.AWSBedrockEmbedding",
        "fastembed": "selfmemory.embeddings.fastembed.FastEmbedEmbedding",
    }

    @classmethod
    def create(cls, provider_name, config, vector_config: Optional[dict]):
        if provider_name == "upstash_vector" and vector_config and vector_config.enable_embeddings:
            return MockEmbeddings()
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
            embedder_instance = load_class(class_type)
            base_config = BaseEmbedderConfig(**config)
            return embedder_instance(base_config)
        else:
            raise ValueError(f"Unsupported Embedder provider: {provider_name}")


class VectorStoreFactory:
    provider_to_class = {
        "qdrant": "selfmemory.vector_stores.qdrant.Qdrant",
        "chroma": "selfmemory.vector_stores.chroma.ChromaDB",
        "pgvector": "selfmemory.vector_stores.pgvector.PGVector",
        "milvus": "selfmemory.vector_stores.milvus.MilvusDB",
        "upstash_vector": "selfmemory.vector_stores.upstash_vector.UpstashVector",
        "azure_ai_search": "selfmemory.vector_stores.azure_ai_search.AzureAISearch",
        "azure_mysql": "selfmemory.vector_stores.azure_mysql.AzureMySQL",
        "pinecone": "selfmemory.vector_stores.pinecone.PineconeDB",
        "mongodb": "selfmemory.vector_stores.mongodb.MongoDB",
        "redis": "selfmemory.vector_stores.redis.RedisDB",
        "valkey": "selfmemory.vector_stores.valkey.ValkeyDB",
        "databricks": "selfmemory.vector_stores.databricks.Databricks",
        "elasticsearch": "selfmemory.vector_stores.elasticsearch.ElasticsearchDB",
        "vertex_ai_vector_search": "selfmemory.vector_stores.vertex_ai_vector_search.GoogleMatchingEngine",
        "opensearch": "selfmemory.vector_stores.opensearch.OpenSearchDB",
        "supabase": "selfmemory.vector_stores.supabase.Supabase",
        "weaviate": "selfmemory.vector_stores.weaviate.Weaviate",
        "faiss": "selfmemory.vector_stores.faiss.FAISS",
        "langchain": "selfmemory.vector_stores.langchain.Langchain",
        "s3_vectors": "selfmemory.vector_stores.s3_vectors.S3Vectors",
        "baidu": "selfmemory.vector_stores.baidu.BaiduDB",
        "cassandra": "selfmemory.vector_stores.cassandra.CassandraDB",
        "neptune": "selfmemory.vector_stores.neptune_analytics.NeptuneAnalyticsVector",
    }

    @classmethod
    def create(cls, provider_name, config):
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
            if not isinstance(config, dict):
                config = config.model_dump()
            vector_store_instance = load_class(class_type)
            return vector_store_instance(**config)
        else:
            raise ValueError(f"Unsupported VectorStore provider: {provider_name}")

    @classmethod
    def reset(cls, instance):
        instance.reset()
        return instance


# class GraphStoreFactory:
#     """
#     Factory for creating MemoryGraph instances for different graph store providers.
#     Usage: GraphStoreFactory.create(provider_name, config)
#     """

#     provider_to_class = {
#         "memgraph": "selfmemory.memory.memgraph_memory.MemoryGraph",
#         "neptune": "selfmemory.graphs.neptune.neptunegraph.MemoryGraph",
#         "neptunedb": "selfmemory.graphs.neptune.neptunedb.MemoryGraph",
#         "kuzu": "selfmemory.memory.kuzu_memory.MemoryGraph",
#         "default": "selfmemory.memory.graph_memory.MemoryGraph",
#     }

#     @classmethod
#     def create(cls, provider_name, config):
#         class_type = cls.provider_to_class.get(provider_name, cls.provider_to_class["default"])
#         try:
#             GraphClass = load_class(class_type)
#         except (ImportError, AttributeError) as e:
#             raise ImportError(f"Could not import MemoryGraph for provider '{provider_name}': {e}")
#         return GraphClass(config)


# class RerankerFactory:
#     """
#     Factory for creating reranker instances with appropriate configurations.
#     Supports provider-specific configs following the same pattern as other factories.
#     """

#     # Provider mappings with their config classes
#     provider_to_class = {
#         "cohere": ("selfmemory.reranker.cohere_reranker.CohereReranker", CohereRerankerConfig),
#         "sentence_transformer": ("selfmemory.reranker.sentence_transformer_reranker.SentenceTransformerReranker", SentenceTransformerRerankerConfig),
#         "zero_entropy": ("selfmemory.reranker.zero_entropy_reranker.ZeroEntropyReranker", ZeroEntropyRerankerConfig),
#         "llm_reranker": ("selfmemory.reranker.llm_reranker.LLMReranker", LLMRerankerConfig),
#         "huggingface": ("selfmemory.reranker.huggingface_reranker.HuggingFaceReranker", HuggingFaceRerankerConfig),
#     }

#     @classmethod
#     def create(cls, provider_name: str, config: Optional[Union[BaseRerankerConfig, Dict]] = None, **kwargs):
#         """
#         Create a reranker instance based on the provider and configuration.

#         Args:
#             provider_name: The reranker provider (e.g., 'cohere', 'sentence_transformer')
#             config: Configuration object or dictionary
#             **kwargs: Additional configuration parameters

#         Returns:
#             Reranker instance configured for the specified provider

#         Raises:
#             ImportError: If the provider class cannot be imported
#             ValueError: If the provider is not supported
#         """
#         if provider_name not in cls.provider_to_class:
#             raise ValueError(f"Unsupported reranker provider: {provider_name}")

#         class_path, config_class = cls.provider_to_class[provider_name]

#         # Handle configuration
#         if config is None:
#             config = config_class(**kwargs)
#         elif isinstance(config, dict):
#             config = config_class(**config, **kwargs)
#         elif not isinstance(config, BaseRerankerConfig):
#             raise ValueError(f"Config must be a {config_class.__name__} instance or dict")

#         # Import and create the reranker class
#         try:
#             reranker_class = load_class(class_path)
#         except (ImportError, AttributeError) as e:
#             raise ImportError(f"Could not import reranker for provider '{provider_name}': {e}")

#         return reranker_class(config)
