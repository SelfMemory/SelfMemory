import os

from openai import OpenAI

from selfmemory.llms.base import LLMBase
from selfmemory.llms.configs import BaseLlmConfig


class XAILLM(LLMBase):
    def __init__(self, config: BaseLlmConfig | None = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "grok-2-latest"

        api_key = self.config.api_key or os.getenv("XAI_API_KEY")
        base_url = (
            self.config.xai_base_url
            or os.getenv("XAI_API_BASE")
            or "https://api.x.ai/v1"
        )
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate_response(
        self,
        messages: list[dict[str, str]],
        response_format=None,
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using XAI.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """
        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if response_format:
            params["response_format"] = response_format

        response = self.client.chat.completions.create(**params)
        return response.choices[0].message.content
