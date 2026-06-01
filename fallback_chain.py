# fallback_chain.py
"""
Fallback chain: nếu provider chính lỗi → tự switch sang provider backup.
"""

from rich.console import Console

from error_handler import parse_provider_error
from providers import LLMProvider, create_provider

console = Console()

# Thứ tự fallback mặc định
DEFAULT_FALLBACK_CHAIN = [
    "claude-sonnet",
    "claude-haiku",
    "groq-llama",
    "gpt-4o-mini",
]


def try_with_fallback(
    func: callable,
    primary_provider: LLMProvider,
    fallback_chain: list[str] | None = None,
) -> tuple[any, LLMProvider]:
    """
    Thử gọi func với primary_provider, nếu lỗi thì lần lượt thử các provider trong chain.

    Args:
        func: callable nhận provider → return result
        primary_provider: Provider chính
        fallback_chain: List preset names để fallback

    Returns:
        (result, provider_used) - result và provider thực sự được dùng
    """
    if fallback_chain is None:
        fallback_chain = DEFAULT_FALLBACK_CHAIN

    # Thử primary trước
    try:
        result = func(primary_provider)
        return result, primary_provider
    except Exception as e:
        parsed = parse_provider_error(e)

        if not parsed.can_fallback:
            raise

        console.print(
            f"[yellow]⚠️  {primary_provider.provider_name} fail: {parsed.user_message}[/yellow]"
        )

    # Thử các fallback
    primary_name = primary_provider.provider_name

    for preset in fallback_chain:
        try:
            fallback_provider = create_provider(preset)

            # Skip nếu cùng provider name (đã thử)
            if fallback_provider.provider_name == primary_name:
                continue

            console.print(
                f"[cyan]🔄 Thử fallback: {fallback_provider.provider_name}/{fallback_provider.model_name}[/cyan]"
            )

            result = func(fallback_provider)
            console.print(
                f"[green]✅ Fallback thành công với {fallback_provider.provider_name}[/green]"
            )
            return result, fallback_provider

        except Exception as e:
            parsed = parse_provider_error(e)
            console.print(f"[dim]  ↳ {preset} cũng fail: {parsed.user_message}[/dim]")
            continue

    raise Exception("Tất cả providers đều fail")
