# observability.py
"""
Langfuse v4 tracing integration cho DevMate.

v4 API khác v2/v3:
- Không còn lf.trace() — thay bằng TraceContext (grouping ID)
- Mỗi LLM call → lf.start_observation(as_type="generation") → gen.end()
- Tất cả observations cùng trace_id → hiển thị chung 1 trace trên dashboard
"""

import os
from langfuse import Langfuse
from langfuse.types import TraceContext

_client: Langfuse | None = None
_trace_ctx: TraceContext | None = None
_session_id: str = ""


def get_client() -> Langfuse | None:
    """Lazy init — return None nếu chưa set LANGFUSE keys (app vẫn chạy bình thường)."""
    global _client
    if _client is not None:
        return _client

    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        return None

    _client = Langfuse(
        public_key=pk,
        secret_key=sk,
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    return _client


def start_session(name: str = "devmate-cli") -> str:
    """
    Bắt đầu session mới — tạo trace_id để group toàn bộ LLM calls trong session này.
    Gọi 1 lần khi khởi động CLI.
    """
    global _trace_ctx, _session_id

    lf = get_client()
    if not lf:
        return "no-langfuse"

    # trace_id = unique ID cho 1 session CLI
    # session_id = group nhiều trace lại (vd: cùng user dùng nhiều lần)
    trace_id = Langfuse.create_trace_id(seed=name)
    _session_id = trace_id[:8]
    _trace_ctx = TraceContext(trace_id=trace_id, session_id=trace_id)

    return _session_id


def log_generation(
    name: str,
    model: str,
    provider: str,
    mode: str,
    input_messages: list[dict],
    output: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    """Ghi lại 1 LLM call. Nếu Langfuse chưa config → skip silently."""
    lf = get_client()
    if not lf or not _trace_ctx:
        return

    gen = lf.start_observation(
        trace_context=_trace_ctx,
        name=name,
        as_type="generation",
        model=f"{provider}/{model}",
        input=input_messages,
        output=output,
        usage_details={
            "input": input_tokens,
            "output": output_tokens,
        },
        cost_details={"total": cost_usd},
        metadata={"mode": mode},
    )
    gen.end()


def flush() -> None:
    """Flush pending events trước khi thoát CLI."""
    lf = get_client()
    if lf:
        lf.flush()
