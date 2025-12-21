from collections.abc import Callable
from typing import Any

from selfmemory.configs.llms.base import BaseLlmConfig


class OpenAIConfig(BaseLlmConfig):
    """
    Configuration class for OpenAI and OpenRouter-specific parameters.
    Inherits from BaseLlmConfig and adds OpenAI-specific settings.
    """

    def __init__(
        self,
        # Base parameters
        model: str | None = None,
        temperature: float = 0.1,
        api_key: str | None = None,
        max_tokens: int = 2000,
        top_p: float = 0.1,
        top_k: int = 1,
        enable_vision: bool = False,
        vision_details: str | None = "auto",
        http_client_proxies: dict | None = None,
        # OpenAI-specific parameters
        openai_base_url: str | None = None,
        models: list[str] | None = None,
        route: str | None = "fallback",
        openrouter_base_url: str | None = None,
        site_url: str | None = None,
        app_name: str | None = None,
        store: bool = False,
        # Response monitoring callback
        response_callback: Callable[[Any, dict, dict], None] | None = None,
    ):
        """
        Initialize OpenAI configuration.

        Args:
            model: OpenAI model to use, defaults to None
            temperature: Controls randomness, defaults to 0.1
            api_key: OpenAI API key, defaults to None
            max_tokens: Maximum tokens to generate, defaults to 2000
            top_p: Nucleus sampling parameter, defaults to 0.1
            top_k: Top-k sampling parameter, defaults to 1
            enable_vision: Enable vision capabilities, defaults to False
            vision_details: Vision detail level, defaults to "auto"
            http_client_proxies: HTTP client proxy settings, defaults to None
            openai_base_url: OpenAI API base URL, defaults to None
            models: List of models for OpenRouter, defaults to None
            route: OpenRouter route strategy, defaults to "fallback"
            openrouter_base_url: OpenRouter base URL, defaults to None
            site_url: Site URL for OpenRouter, defaults to None
            app_name: Application name for OpenRouter, defaults to None
            response_callback: Optional callback for monitoring LLM responses.
        """
        # Initialize base parameters
        super().__init__(
            model=model,
            temperature=temperature,
            api_key=api_key,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            enable_vision=enable_vision,
            vision_details=vision_details,
            http_client_proxies=http_client_proxies,
        )

        # OpenAI-specific parameters
        self.openai_base_url = openai_base_url
        self.models = models
        self.route = route
        self.openrouter_base_url = openrouter_base_url
        self.site_url = site_url
        self.app_name = app_name
        self.store = store

        # Response monitoring
        self.response_callback = response_callback
