# providers/anthropic_provider.py
"""Anthropic Claude provider."""

import os
from typing import Iterator

from anthropic import Anthropic

from providers.base import CompletionResult, LLMProvider, TokenUsage


class AnthropicProvider(LLMProvider):
    provider_name = "anthropic"
    price_input_per_mtok = 3.0  # Sonnet 4.5
    price_output_per_mtok = 15.0

    supports_tools = True
    supports_structured_output = True

    # Claude 4.5 hỗ trợ tool calls và structured output
    supports_tools = True
    supports_structured_output = True

    def __init__(self, model: str = "claude-sonnet-4-5"):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = Anthropic(api_key=api_key)
        self.model_name = model
        self._last_usage = TokenUsage(0, 0)

    def get_raw_client(self):
        """Expose raw Anthropic SDK client cho advanced features (tools, structured output)."""
        return self.client

    def chat(
        self, messages: list[dict], system: str, max_tokens: int = 2048
    ) -> CompletionResult:
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        text = response.content[0].text if response.content else ""
        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        self._last_usage = usage
        return CompletionResult(text=text, usage=usage)

    def chat_stream(
        self, messages: list[dict], system: str, max_tokens: int = 2048
    ) -> Iterator[str]:
        with self.client.messages.stream(
            model=self.model_name,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
            # Lưu usage sau khi stream xong
            final = stream.get_final_message()
            self._last_usage = TokenUsage(
                input_tokens=final.usage.input_tokens,
                output_tokens=final.usage.output_tokens,
            )

    def get_last_usage(self) -> TokenUsage:
        return self._last_usage
