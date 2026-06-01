# error_handler.py
"""
Phân loại lỗi từ LLM provider và đưa ra user-friendly message.
Pattern: Centralized error handling.
"""

from dataclasses import dataclass
from enum import Enum


class ErrorType(Enum):
    RATE_LIMIT = "rate_limit"  # 429 rate
    QUOTA_EXCEEDED = "quota_exceeded"  # 429 quota (hết tiền)
    AUTH = "auth"  # 401, 403
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"  # 5xx (server overload)
    MODEL_NOT_FOUND = "model_not_found"  # 404 (model deprecated)
    INVALID_REQUEST = "invalid_request"  # 400
    UNKNOWN = "unknown"


@dataclass
class ParsedError:
    error_type: ErrorType
    user_message: str
    suggestion: str
    can_retry: bool  # Có nên thử lại không
    can_fallback: bool  # Có nên switch provider khác không
    raw_error: str


def parse_provider_error(exception: Exception) -> ParsedError:
    """Phân loại exception thành ParsedError có actionable info."""
    error_str = str(exception)
    error_lower = error_str.lower()
    raw = error_str[:300]

    # Quota exceeded - hết tiền, không thể retry
    if (
        "insufficient_quota" in error_lower
        or "exceeded your current quota" in error_lower
    ):
        return ParsedError(
            error_type=ErrorType.QUOTA_EXCEEDED,
            user_message="Hết quota / hết tiền",
            suggestion="Nạp thêm credit hoặc switch provider khác",
            can_retry=False,
            can_fallback=True,
            raw_error=raw,
        )

    # Rate limit - đợi xíu là OK
    if "429" in error_str or "rate" in error_lower:
        return ParsedError(
            error_type=ErrorType.RATE_LIMIT,
            user_message="Bị rate limit (gọi quá nhanh)",
            suggestion="Đợi 30-60s rồi thử lại",
            can_retry=True,
            can_fallback=True,
            raw_error=raw,
        )

    # Auth - key sai
    if (
        "401" in error_str
        or "403" in error_str
        or "api key" in error_lower
        or "unauthorized" in error_lower
    ):
        return ParsedError(
            error_type=ErrorType.AUTH,
            user_message="Lỗi xác thực API key",
            suggestion="Check .env xem key đúng/còn hạn không",
            can_retry=False,
            can_fallback=True,
            raw_error=raw,
        )

    # Server error - retry được
    if (
        any(code in error_str for code in ["500", "502", "503", "504"])
        or "unavailable" in error_lower
    ):
        return ParsedError(
            error_type=ErrorType.SERVER_ERROR,
            user_message="Server provider đang quá tải",
            suggestion="Đợi vài phút thử lại, hoặc switch provider",
            can_retry=True,
            can_fallback=True,
            raw_error=raw,
        )

    # Model not found
    if "404" in error_str or "not found" in error_lower or "not_found" in error_lower:
        return ParsedError(
            error_type=ErrorType.MODEL_NOT_FOUND,
            user_message="Model không tồn tại / đã deprecated",
            suggestion="Update PRESETS với model name mới",
            can_retry=False,
            can_fallback=True,
            raw_error=raw,
        )

    # Timeout
    if "timeout" in error_lower or "timed out" in error_lower:
        return ParsedError(
            error_type=ErrorType.TIMEOUT,
            user_message="Request timeout",
            suggestion="Thử lại, hoặc giảm max_tokens",
            can_retry=True,
            can_fallback=False,
            raw_error=raw,
        )

    # 400 - invalid
    if "400" in error_str or "invalid" in error_lower:
        return ParsedError(
            error_type=ErrorType.INVALID_REQUEST,
            user_message="Request không hợp lệ",
            suggestion="Có thể message quá dài, gõ /clear để xóa history",
            can_retry=False,
            can_fallback=False,
            raw_error=raw,
        )

    # Unknown
    return ParsedError(
        error_type=ErrorType.UNKNOWN,
        user_message="Lỗi không xác định",
        suggestion="Check log để debug",
        can_retry=True,
        can_fallback=True,
        raw_error=raw,
    )
