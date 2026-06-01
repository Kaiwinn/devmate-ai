# providers/groq_provider.py
"""Groq provider - FREE, super fast Llama models."""

import os

from openai import OpenAI

from providers.openai_provider import OpenAIProvider
from providers.base import TokenUsage


class GroqProvider(OpenAIProvider):
    """Groq dùng OpenAI-compatible API → reuse hầu hết logic của OpenAIProvider."""

    provider_name = "groq"
    # Groq FREE, set giá = 0 để tracking thấy rõ
    price_input_per_mtok = 0.0
    price_output_per_mtok = 0.0

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env")

        # Groq dùng OpenAI SDK nhưng với base_url khác
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        self.model_name = model
        self._last_usage = TokenUsage(0, 0)
