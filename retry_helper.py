# retry_helper.py
"""Retry với exponential backoff cho provider calls."""

import time
from typing import Callable, TypeVar

from rich.console import Console

from error_handler import parse_provider_error

console = Console()

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    on_retry: Callable | None = None,
) -> T:
    """
    Gọi func, retry với exponential backoff nếu lỗi retry-able.

    Delay: base * 2^attempt → 1s, 2s, 4s, 8s...

    Args:
        func: Function không nhận args, return T
        max_retries: Số lần retry tối đa (không tính lần đầu)
        base_delay: Delay đầu tiên (giây)
        on_retry: Callback khi retry, nhận (attempt, error)

    Returns:
        T - result của func

    Raises:
        Exception cuối cùng nếu hết retry
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            parsed = parse_provider_error(e)

            # Lỗi không retry được → raise ngay
            if not parsed.can_retry:
                raise

            # Hết retry → raise
            if attempt >= max_retries:
                raise

            # Tính delay
            delay = base_delay * (2**attempt)

            if on_retry:
                on_retry(attempt + 1, e)
            else:
                console.print(
                    f"[yellow]⚠️  {parsed.user_message}. "
                    f"Retry sau {delay:.1f}s... (lần {attempt + 1}/{max_retries})[/yellow]"
                )

            time.sleep(delay)

    # Theoretically never reach here
    raise last_error  # type: ignore
