from typing import Any

from selfmemory.configs.llms.base import BaseLlmConfig


class LMStudioConfig(BaseLlmConfig):
    """
    Configuration class for LM Studio-specific parameters.
    Inherits from BaseLlmConfig and adds LM Studio-specific settings.
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
        # LM Studio-specific parameters
        lmstudio_base_url: str | None = None,
        lmstudio_response_format: dict[str, Any] | None = None,
    ):
        """
        Initialize LM Studio configuration.

        Args:
            model: LM Studio model to use, defaults to None
            temperature: Controls randomness, defaults to 0.1
            api_key: LM Studio API key, defaults to None
            max_tokens: Maximum tokens to generate, defaults to 2000
            top_p: Nucleus sampling parameter, defaults to 0.1
            top_k: Top-k sampling parameter, defaults to 1
            enable_vision: Enable vision capabilities, defaults to False
            vision_details: Vision detail level, defaults to "auto"
            http_client_proxies: HTTP client proxy settings, defaults to None
            lmstudio_base_url: LM Studio base URL, defaults to None
            lmstudio_response_format: LM Studio response format, defaults to None
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

        # LM Studio-specific parameters
        self.lmstudio_base_url = lmstudio_base_url or "http://localhost:1234/v1"
        self.lmstudio_response_format = lmstudio_response_format
