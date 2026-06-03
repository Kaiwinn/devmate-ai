# chain/state.py
"""
AgentState — shared state giữa tất cả nodes trong LangGraph.

Đây là khác biệt cốt lõi so với sequential chain (Pharmacy bậc trước):
- Sequential chain: output của agent A là input của agent B (truyền tay)
- LangGraph: tất cả agents đọc/ghi vào CÙNG 1 state object

Tương tự shared memory trong multi-threading — nhưng không có race condition
vì LangGraph chạy nodes tuần tự theo graph.
"""

from typing import TypedDict


class AgentState(TypedDict):
    """State được share qua toàn bộ agent chain."""

    task: str           # Task gốc từ user — không thay đổi suốt quá trình
    plan: str           # Output của Planner: breakdown thành các bước
    code: str           # Output của Coder: code được viết
    feedback: str       # Output của Reviewer: nhận xét + lý do pass/fail
    passed: bool        # Reviewer verdict: True = chấp nhận, False = cần sửa
    iterations: int     # Số lần Coder đã thử — safety valve tránh infinite loop
    max_iterations: int # Giới hạn tối đa (default: 3)
