# providers/openai_provider.py
"""OpenAI GPT provider."""

import os
from typing import Iterator

from openai import OpenAI

from providers.base import CompletionResult, LLMProvider, TokenUsage


class OpenAIProvider(LLMProvider):
    provider_name = "openai"
    # GPT-4o-mini giá rẻ
    price_input_per_mtok = 0.15
    price_output_per_mtok = 0.60

    def __init__(self, model: str = "gpt-4o-mini"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in .env")
        self.client = OpenAI(api_key=api_key)
        self.model_name = model
        self._last_usage = TokenUsage(0, 0)

    def _convert_messages(self, messages: list[dict], system: str) -> list[dict]:
        """OpenAI dùng system message trong array, không phải param riêng."""
        result = [{"role": "system", "content": system}]
        for msg in messages:
            # OpenAI không support tool_result format của Anthropic
            # Bỏ qua những message không phải text
            if isinstance(msg.get("content"), str):
                result.append(msg)
        return result

    def chat(
        self, messages: list[dict], system: str, max_tokens: int = 2048
    ) -> CompletionResult:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self._convert_messages(messages, system),
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        usage = TokenUsage(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
        self._last_usage = usage
        return CompletionResult(text=text, usage=usage)

    def chat_stream(
        self, messages: list[dict], system: str, max_tokens: int = 2048
    ) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=self._convert_messages(messages, system),
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},  # ép trả usage cuối stream
        )
        for chunk in stream:
            # Usage chỉ có ở chunk cuối
            if chunk.usage:
                self._last_usage = TokenUsage(
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                )
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def get_last_usage(self) -> TokenUsage:
        return self._last_usage
