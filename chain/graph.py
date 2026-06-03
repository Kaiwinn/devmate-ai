# chain/graph.py
"""
LangGraph definition — graph structure + routing logic.

LangGraph = StateGraph (state machine):
- Nodes: các function xử lý state
- Edges: kết nối tuyến tính
- Conditional edges: routing động dựa trên state

Khác với sequential chain:
  Sequential: A → B → C (cứng)
  LangGraph:  A → B → [C hoặc B lại] tùy state
"""

from langgraph.graph import StateGraph, END
from rich.console import Console

from chain.state import AgentState
from chain.agents import planner_node, coder_node, reviewer_node

console = Console()


def should_continue(state: AgentState) -> str:
    """
    Routing function — quyết định edge tiếp theo sau Reviewer.

    Return value phải match key trong add_conditional_edges dict.
    LangGraph gọi function này sau mỗi lần reviewer chạy.
    """
    if state["passed"]:
        console.print("[bold green]✅ Reviewer: PASS — hoàn thành![/bold green]")
        return "done"

    if state["iterations"] >= state["max_iterations"]:
        console.print(
            f"[bold red]⚠ Đạt max iterations ({state['max_iterations']}), dừng lại.[/bold red]"
        )
        return "done"

    console.print(
        f"[yellow]🔄 Reviewer: FAIL — Coder thử lại "
        f"(lần {state['iterations']}/{state['max_iterations']})[/yellow]"
    )
    return "retry"


def build_graph() -> StateGraph:
    """
    Định nghĩa và compile graph.

    Graph structure:
      START → planner → coder → reviewer
                           ↑        │
                           │  retry─┘
                           │
                          done → END
    """
    builder = StateGraph(AgentState)

    # Thêm nodes
    builder.add_node("planner", planner_node)
    builder.add_node("coder", coder_node)
    builder.add_node("reviewer", reviewer_node)

    # Entry point
    builder.set_entry_point("planner")

    # Edge tuyến tính: planner → coder
    builder.add_edge("planner", "coder")

    # Edge tuyến tính: coder → reviewer
    builder.add_edge("coder", "reviewer")

    # Conditional edge: sau reviewer → done hoặc retry
    builder.add_conditional_edges(
        "reviewer",           # Node nguồn
        should_continue,      # Routing function
        {
            "done": END,      # "done" → kết thúc graph
            "retry": "coder", # "retry" → quay lại coder với feedback
        },
    )

    return builder.compile()


# Compile 1 lần, dùng nhiều lần
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_chain(task: str, max_iterations: int = 3) -> AgentState:
    """
    Chạy toàn bộ chain từ task đến final code.
    Trả về final state để caller hiển thị kết quả.
    """
    graph = get_graph()

    initial_state: AgentState = {
        "task": task,
        "plan": "",
        "code": "",
        "feedback": "",
        "passed": False,
        "iterations": 0,
        "max_iterations": max_iterations,
    }

    console.print(f"\n[bold cyan]🤖 Agent Chain bắt đầu[/bold cyan]")
    console.print(f"[dim]Task: {task[:80]}{'...' if len(task) > 80 else ''}[/dim]\n")

    final_state = graph.invoke(initial_state)
    return final_state
