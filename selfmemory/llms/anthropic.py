import os

try:
    import anthropic
except ImportError:
    raise ImportError(
        "The 'anthropic' library is required. Please install it using 'pip install anthropic'."
    )

from selfmemory.llms.base import LLMBase
from selfmemory.llms.configs import AnthropicConfig, BaseLlmConfig


class AnthropicLLM(LLMBase):
    def __init__(self, config: BaseLlmConfig | AnthropicConfig | dict | None = None):
        # Convert to AnthropicConfig if needed
        if config is None:
            config = AnthropicConfig()
        elif isinstance(config, dict):
            config = AnthropicConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(
            config, AnthropicConfig
        ):
            # Convert BaseLlmConfig to AnthropicConfig
            config = AnthropicConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=config.enable_vision,
                vision_details=config.vision_details,
                http_client_proxies=config.http_client,
            )

        super().__init__(config)

        if not self.config.model:
            self.config.model = "claude-3-5-sonnet-20240620"

        api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_response(
        self,
        messages: list[dict[str, str]],
        response_format=None,
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        """
        Generate a response based on the given messages using Anthropic.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional Anthropic-specific parameters.

        Returns:
            str: The generated response.
        """
        # Separate system message from other messages
        system_message = ""
        filtered_messages = []
        for message in messages:
            if message["role"] == "system":
                system_message = message["content"]
            else:
                filtered_messages.append(message)

        params = self._get_supported_params(messages=messages, **kwargs)
        params.update(
            {
                "model": self.config.model,
                "messages": filtered_messages,
                "system": system_message,
            }
        )

        if (
            tools
        ):  # TODO: Remove tools if no issues found with new memory addition logic
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.messages.create(**params)
        return response.content[0].text
