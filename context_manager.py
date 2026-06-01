# context_manager.py
"""
Quản lý conversation history để tránh context overflow & tiết kiệm token.
"""

from typing import Callable

# Ước lượng tokens: tiếng Việt + code ~3 chars/token
CHARS_PER_TOKEN_ESTIMATE = 3


def estimate_tokens(text: str) -> int:
    """Estimate token count từ text length."""
    return len(text) // CHARS_PER_TOKEN_ESTIMATE


def estimate_message_tokens(message: dict) -> int:
    """Estimate tokens cho 1 message."""
    content = message.get("content", "")
    if isinstance(content, str):
        return estimate_tokens(content)
    return estimate_tokens(str(content))


def total_tokens(messages: list[dict]) -> int:
    """Tổng tokens ước lượng."""
    return sum(estimate_message_tokens(m) for m in messages)


def trim_history_sliding(
    messages: list[dict],
    max_tokens: int = 30_000,
    keep_recent: int = 6,
) -> list[dict]:
    """
    Sliding window: nếu vượt max_tokens, giữ N messages cuối.

    ƯU: Nhanh, không tốn API call thêm
    NHƯỢC: Mất context cũ hoàn toàn
    """
    if total_tokens(messages) <= max_tokens:
        return messages
    return messages[-keep_recent:] if len(messages) > keep_recent else messages


def summarize_history(
    messages: list[dict],
    summarize_fn: Callable[[str], str],
    keep_recent: int = 4,
) -> list[dict]:
    """
    Auto-summarize: tóm tắt phần cũ thành 1 message.

    ƯU: Giữ được context quan trọng
    NHƯỢC: Tốn thêm 1 API call để summarize

    Returns:
        [summary_message] + recent_messages
    """
    if len(messages) <= keep_recent:
        return messages

    # Tách
    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]

    # Convert old_messages thành text
    old_text_parts = []
    for msg in old_messages:
        role = msg["role"]
        content = msg.get("content", "")
        if isinstance(content, str):
            old_text_parts.append(f"[{role}]: {content}")
        else:
            old_text_parts.append(f"[{role}]: (tool calls/results)")

    old_text = "\n\n".join(old_text_parts)

    # Gọi LLM để summarize
    summary = summarize_fn(old_text)

    # Tạo summary message
    summary_message = {
        "role": "user",
        "content": (
            f"[CONVERSATION SUMMARY - các message trước]:\n{summary}\n\n"
            f"[Tiếp tục cuộc trò chuyện từ đây...]"
        ),
    }

    return [summary_message] + recent_messages


SUMMARIZE_PROMPT = """Bạn là assistant chuyên tóm tắt conversation.
Tóm tắt cuộc trò chuyện sau thành 3-5 bullet points NGẮN GỌN, giữ:
- Các quyết định/kết luận quan trọng
- Context kỹ thuật (file, function, biến quan trọng)
- Câu hỏi/vấn đề chưa giải quyết

Không cần lịch sự, viết ngắn gọn nhất có thể."""
