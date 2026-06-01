# providers/__init__.py
"""Factory để tạo provider theo config."""

from providers.anthropic_provider import AnthropicProvider
from providers.base import CompletionResult, LLMProvider, TokenUsage
from providers.gemini_provider import GeminiProvider
from providers.groq_provider import GroqProvider
from providers.openai_provider import OpenAIProvider

PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
}

# Preset cho các models hay dùng
PRESETS = {
    # Anthropic
    "claude-sonnet": ("anthropic", "claude-sonnet-4-5"),
    "claude-haiku": ("anthropic", "claude-haiku-4-5"),
    # OpenAI
    "gpt-4o-mini": ("openai", "gpt-4o-mini"),
    "gpt-4o": ("openai", "gpt-4o"),
    # Gemini — dùng alias 'latest' để Google tự pick model mới nhất
    "gemini-flash": ("gemini", "gemini-flash-latest"),
    "gemini-flash-lite": ("gemini", "gemini-flash-lite-latest"),
    "gemini-3.5-flash": ("gemini", "gemini-3.5-flash"),
    "gemini-3-flash": ("gemini", "gemini-3-flash-preview"),
    "gemini-2.5-flash": ("gemini", "gemini-2.5-flash"),
    # Groq - FREE, super fast
    "groq-llama": ("groq", "llama-3.3-70b-versatile"),
    "groq-llama-fast": ("groq", "llama-3.1-8b-instant"),
    "groq-mixtral": ("groq", "mixtral-8x7b-32768"),
}


def create_provider(preset: str) -> LLMProvider:
    """
    Tạo provider từ preset name.

    Examples:
        create_provider("claude-sonnet")
        create_provider("gpt-4o-mini")
        create_provider("gemini-flash")
    """
    if preset not in PRESETS:
        raise ValueError(
            f"Preset không tồn tại: {preset}. Available: {list(PRESETS.keys())}"
        )

    provider_name, model_name = PRESETS[preset]
    provider_class = PROVIDERS[provider_name]
    return provider_class(model=model_name)


__all__ = [
    "LLMProvider",
    "CompletionResult",
    "TokenUsage",
    "create_provider",
    "PRESETS",
]
