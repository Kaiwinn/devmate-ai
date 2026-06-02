# evals/judge.py
"""
LLM-as-judge: dùng Claude chấm điểm response của DevMate.
"""

from pydantic import BaseModel, Field

from providers import create_provider
from structured_output import call_with_schema


class CriterionScore(BaseModel):
    """Điểm cho từng tiêu chí."""

    criterion: str = Field(description="Tiêu chí gốc")
    passed: bool = Field(description="Đạt hay không")
    reasoning: str = Field(description="Lý do ngắn gọn")


class JudgeResult(BaseModel):
    """Kết quả chấm điểm 1 test case."""

    overall_score: int = Field(description="Điểm tổng 1-10", ge=1, le=10)
    criteria_scores: list[CriterionScore] = Field(default_factory=list)
    summary: str = Field(description="Nhận xét 1-2 câu")
    has_issues: bool = Field(description="Có issue nghiêm trọng không")


JUDGE_PROMPT = """Bạn là LLM Judge — chấm điểm response của AI assistant.

NHIỆM VỤ: 
- Đọc input câu hỏi + response của AI
- Đối chiếu với judge_criteria (các tiêu chí cần đạt)
- Cho điểm từng criterion (pass/fail + reasoning)
- Cho điểm tổng 1-10
- Khách quan, nghiêm túc, không thiên vị

QUY TẮC:
- Mỗi criterion độc lập, không bị ảnh hưởng bởi criterion khác
- passed=True chỉ khi đạt rõ ràng
- overall_score = 10 nếu ALL pass + có thêm value
- overall_score = 1-3 nếu fail hầu hết hoặc có harm
- summary ngắn gọn, không dài dòng
"""


def judge_response(
    test_input: str,
    actual_response: str,
    criteria: list[str],
    expected_contains: str | None = None,
) -> JudgeResult:
    """
    Chấm điểm 1 response với LLM-as-judge.

    Dùng Claude Haiku để tiết kiệm chi phí (judge không cần model mạnh nhất).
    """
    # Build user message cho judge
    criteria_text = "\n".join(f"- {c}" for c in criteria)

    expected_section = ""
    if expected_contains:
        expected_section = f"\nEXPECTED CONTAINS: '{expected_contains}'\n"

    user_msg = f"""TEST INPUT:
{test_input}

AI RESPONSE:
{actual_response}
{expected_section}
JUDGE CRITERIA:
{criteria_text}

Hãy chấm điểm từng criterion và overall."""

    judge_provider = create_provider("claude-haiku")

    result, _ = call_with_schema(
        client=judge_provider.get_raw_client(),
        model=judge_provider.model_name,
        system_prompt=JUDGE_PROMPT,
        user_message=user_msg,
        schema=JudgeResult,
        max_tokens=2000,
    )

    return result
