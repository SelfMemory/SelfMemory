import json

from openai import OpenAI

from selfmemory.llms.base import LLMBase
from selfmemory.llms.configs import BaseLlmConfig, LMStudioConfig
from selfmemory.memory.utils import extract_json


class LMStudioLLM(LLMBase):
    def __init__(self, config: BaseLlmConfig | LMStudioConfig | dict | None = None):
        # Convert to LMStudioConfig if needed
        if config is None:
            config = LMStudioConfig()
        elif isinstance(config, dict):
            config = LMStudioConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(
            config, LMStudioConfig
        ):
            # Convert BaseLlmConfig to LMStudioConfig
            config = LMStudioConfig(
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

        self.config.model = (
            self.config.model
            or "lmstudio-community/Meta-Llama-3.1-70B-Instruct-GGUF/Meta-Llama-3.1-70B-Instruct-IQ2_M.gguf"
        )
        self.config.api_key = self.config.api_key or "lm-studio"

        self.client = OpenAI(
            base_url=self.config.lmstudio_base_url, api_key=self.config.api_key
        )

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        if tools:
            processed_response = {
                "content": response.choices[0].message.content,
                "tool_calls": [],
            }

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    processed_response["tool_calls"].append(
                        {
                            "name": tool_call.function.name,
                            "arguments": json.loads(
                                extract_json(tool_call.function.arguments)
                            ),
                        }
                    )

            return processed_response
        return response.choices[0].message.content

    def generate_response(
        self,
        messages: list[dict[str, str]],
        response_format=None,
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        """
        Generate a response based on the given messages using LM Studio.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional LM Studio-specific parameters.

        Returns:
            str: The generated response.
        """
        params = self._get_supported_params(messages=messages, **kwargs)
        params.update(
            {
                "model": self.config.model,
                "messages": messages,
            }
        )

        if self.config.lmstudio_response_format:
            params["response_format"] = self.config.lmstudio_response_format
        elif response_format:
            params["response_format"] = response_format
        else:
            params["response_format"] = {"type": "json_object"}

        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
