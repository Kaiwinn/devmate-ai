# providers/base.py
"""
Abstract base class cho LLM providers.
Mọi provider phải implement interface này.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator


@dataclass
class TokenUsage:
    """Standardized token usage cho mọi provider."""

    input_tokens: int
    output_tokens: int


@dataclass
class CompletionResult:
    """Kết quả từ LLM."""

    text: str
    usage: TokenUsage


class LLMProvider(ABC):
    """Interface chung cho mọi LLM provider."""

    # Mỗi provider tự define price
    price_input_per_mtok: float = 0.0
    price_output_per_mtok: float = 0.0
    provider_name: str = "unknown"
    model_name: str = "unknown"

    supports_tools: bool = False
    supports_structured_output: bool = False

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int = 2048,
    ) -> CompletionResult:
        """Non-streaming chat. Return text + usage."""
        ...

    @abstractmethod
    def chat_stream(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Streaming chat. Yield từng text chunk."""
        ...

    @abstractmethod
    def get_last_usage(self) -> TokenUsage:
        """Lấy usage của lần stream gần nhất (sau khi đã consume xong stream)."""
        ...

    def calculate_cost(self, usage: TokenUsage) -> float:
        """Tính chi phí dựa trên price của provider."""
        input_cost = (usage.input_tokens / 1_000_000) * self.price_input_per_mtok
        output_cost = (usage.output_tokens / 1_000_000) * self.price_output_per_mtok
        return input_cost + output_cost
