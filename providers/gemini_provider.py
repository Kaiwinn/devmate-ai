# providers/gemini_provider.py
"""Google Gemini provider — FREE tier rất hào phóng."""

import os
from typing import Iterator

from google import genai
from google.genai import types

from providers.base import CompletionResult, LLMProvider, TokenUsage


class GeminiProvider(LLMProvider):
    provider_name = "gemini"
    # Gemini 2.0 Flash - rất rẻ + free tier
    price_input_per_mtok = 0.10
    price_output_per_mtok = 0.40

    def __init__(self, model: str = "gemini-2.0-flash"):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in .env")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
        self._last_usage = TokenUsage(0, 0)

    def _convert_messages(self, messages: list[dict]) -> list:
        """Convert sang format Gemini."""
        contents = []
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=content)]))
        return contents

    def chat(
        self, messages: list[dict], system: str, max_tokens: int = 2048
    ) -> CompletionResult:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=self._convert_messages(messages),
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        text = response.text or ""
        usage = TokenUsage(
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
        )
        self._last_usage = usage
        return CompletionResult(text=text, usage=usage)

    def chat_stream(
        self, messages: list[dict], system: str, max_tokens: int = 2048
    ) -> Iterator[str]:
        stream = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=self._convert_messages(messages),
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text
            if chunk.usage_metadata:
                self._last_usage = TokenUsage(
                    input_tokens=chunk.usage_metadata.prompt_token_count or 0,
                    output_tokens=chunk.usage_metadata.candidates_token_count or 0,
                )

    def get_last_usage(self) -> TokenUsage:
        return self._last_usage
