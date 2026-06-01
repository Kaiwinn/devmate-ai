# schemas.py
"""
Pydantic schemas cho structured output từ LLM.
Mỗi schema = một "format" mà LLM phải tuân theo.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================
class Severity(str, Enum):
    """Mức độ nghiêm trọng của issue."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(str, Enum):
    """Loại issue tìm được."""

    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    CODE_SMELL = "code_smell"
    BEST_PRACTICE = "best_practice"


# ============================================================
# SCHEMAS
# ============================================================
class CodeIssue(BaseModel):
    """Một issue cụ thể tìm được trong code."""

    severity: Severity = Field(description="Mức độ nghiêm trọng")
    category: IssueCategory = Field(description="Loại issue")
    title: str = Field(description="Tên ngắn gọn của issue, < 80 ký tự")
    description: str = Field(description="Mô tả chi tiết vấn đề")
    file_path: str = Field(description="Đường dẫn file chứa issue")
    line_start: int = Field(description="Dòng bắt đầu (1-indexed)", ge=1)
    line_end: int = Field(description="Dòng kết thúc (1-indexed)", ge=1)
    suggested_fix: str = Field(description="Code gợi ý fix, có thể là snippet")
    explanation: str = Field(description="Giải thích tại sao đây là vấn đề")


class CodeReviewReport(BaseModel):
    """Báo cáo review code hoàn chỉnh."""

    summary: str = Field(description="Tóm tắt 2-3 câu về chất lượng code")
    overall_score: int = Field(
        description="Điểm tổng từ 1-10 (1 tệ nhất, 10 hoàn hảo)",
        ge=1,
        le=10,
    )
    total_issues: int = Field(description="Tổng số issues tìm được", ge=0)
    issues: list[CodeIssue] = Field(
        description="Danh sách chi tiết các issues",
        default_factory=list,
    )
    strengths: list[str] = Field(
        description="2-5 điểm code đã làm tốt",
        default_factory=list,
    )
    files_reviewed: list[str] = Field(
        description="Danh sách file đã review",
        default_factory=list,
    )
