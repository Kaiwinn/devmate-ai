# chain/agents.py
"""
3 agent nodes cho LangGraph code generation chain.

Mỗi node là 1 function nhận state → trả về dict update state.
LangGraph merge dict đó vào state hiện tại (partial update, không replace toàn bộ).
"""

from providers import create_provider
from chain.state import AgentState

# Dùng claude-sonnet cho planner + reviewer (cần reasoning tốt)
# Dùng claude-haiku cho coder (task cụ thể hơn, rẻ hơn)
_sonnet = create_provider("claude-sonnet")
_haiku = create_provider("claude-haiku")


# ── NODE 1: Planner ───────────────────────────────────────────────────────────

PLANNER_SYSTEM = """Bạn là Senior Software Architect. Nhiệm vụ: phân tích task và tạo implementation plan.

OUTPUT FORMAT (bắt buộc):
## Mục tiêu
[1 câu mô tả rõ output cần đạt]

## Approach
[Giải thích ngắn tại sao chọn hướng này]

## Các bước implementation
1. [Bước 1 cụ thể]
2. [Bước 2 cụ thể]
...

## Edge cases cần xử lý
- [Case 1]
- [Case 2]

## Constraints
- Viết Python 3.12, type hints đầy đủ
- Không dùng library bên ngoài trừ khi thực sự cần
- Function ngắn, single responsibility"""


def planner_node(state: AgentState) -> dict:
    """Node 1: Tạo implementation plan từ task."""
    result = _sonnet.chat(
        messages=[{"role": "user", "content": f"Task: {state['task']}"}],
        system=PLANNER_SYSTEM,
        max_tokens=1024,
    )
    return {"plan": result.text}


# ── NODE 2: Coder ─────────────────────────────────────────────────────────────

CODER_SYSTEM = """Bạn là Python developer. Nhiệm vụ: implement code theo plan được cho.

QUY TẮC:
- Chỉ trả về code Python thuần, không có markdown, không có giải thích ngoài comment
- Bắt đầu bằng # filename.py
- Type hints đầy đủ
- Docstring ngắn gọn cho mỗi function
- Xử lý edge cases được nêu trong plan"""

CODER_WITH_FEEDBACK_SYSTEM = """Bạn là Python developer đang sửa code dựa trên feedback của reviewer.

QUY TẮC:
- Đọc kỹ feedback, hiểu VẤN ĐỀ CỤ THỂ trước khi sửa
- Chỉ trả về code đã sửa (không giải thích)
- Giữ nguyên phần code đã đúng, chỉ sửa phần có vấn đề"""


def coder_node(state: AgentState) -> dict:
    """Node 2: Viết code theo plan. Nếu có feedback → sửa code cũ."""
    is_retry = state["iterations"] > 0 and state.get("feedback")

    if is_retry:
        user_msg = f"""PLAN:
{state['plan']}

CODE HIỆN TẠI (cần sửa):
{state['code']}

FEEDBACK CỦA REVIEWER:
{state['feedback']}

Sửa lại code theo feedback."""
        system = CODER_WITH_FEEDBACK_SYSTEM
    else:
        user_msg = f"""PLAN:
{state['plan']}

Implement theo plan trên."""
        system = CODER_SYSTEM

    result = _haiku.chat(
        messages=[{"role": "user", "content": user_msg}],
        system=system,
        max_tokens=2048,
    )

    return {
        "code": result.text,
        "iterations": state["iterations"] + 1,
    }


# ── NODE 3: Reviewer ──────────────────────────────────────────────────────────

REVIEWER_SYSTEM = """Bạn là Senior Code Reviewer khắt khe. Nhiệm vụ: review code theo plan.

TIÊU CHÍ REVIEW:
1. Code có implement đúng yêu cầu trong plan không?
2. Có type hints đầy đủ không?
3. Có xử lý edge cases được nêu trong plan không?
4. Có bug logic rõ ràng không?
5. Code có readable không?

OUTPUT FORMAT (bắt buộc):
VERDICT: PASS hoặc FAIL

NHẬN XÉT:
[Nhận xét cụ thể về từng tiêu chí]

NẾU FAIL — VẤN ĐỀ CỤ THỂ CẦN SỬA:
1. [Vấn đề 1: mô tả rõ, chỉ đúng chỗ cần sửa]
2. [Vấn đề 2...]

QUY TẮC:
- PASS khi code đúng logic, đủ edge cases, readable
- FAIL chỉ khi có vấn đề thực sự — không FAIL vì style preference
- Feedback phải đủ cụ thể để Coder sửa được ngay"""


def reviewer_node(state: AgentState) -> dict:
    """Node 3: Review code, quyết định pass/fail + feedback."""
    user_msg = f"""PLAN (yêu cầu gốc):
{state['plan']}

CODE CẦN REVIEW:
{state['code']}

Review code này theo plan."""

    result = _sonnet.chat(
        messages=[{"role": "user", "content": user_msg}],
        system=REVIEWER_SYSTEM,
        max_tokens=1024,
    )

    review_text = result.text
    passed = "VERDICT: PASS" in review_text.upper()

    return {
        "feedback": review_text,
        "passed": passed,
    }
