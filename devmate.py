# devmate.py - Version 2.0
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from file_handler import read_files_for_review
from tools import TOOLS_SCHEMA, execute_tool
from schemas import CodeReviewReport
from structured_output import call_with_schema
from providers import LLMProvider, PRESETS, create_provider
from context_manager import (
    SUMMARIZE_PROMPT,
    estimate_tokens,
    summarize_history,
    total_tokens,
    trim_history_sliding,
)
from error_handler import parse_provider_error
from retry_helper import retry_with_backoff
from fallback_chain import try_with_fallback
from observability import start_session, log_generation, flush
from rag import RAGPipeline
from chain import run_chain

from prompts import (
    CHAT_PROMPT,
    CODE_REVIEW_PROMPT,
    TEST_GENERATION_PROMPT,
    EXPLAIN_PROMPT,
    AGENT_PROMPT,
    STRUCTURED_REVIEW_PROMPT,
)

# ============================================================
# CONFIG
# ============================================================
load_dotenv()
console = Console()

# Context management
MAX_CONTEXT_TOKENS = 30_000
CONTEXT_STRATEGY = "sliding"  # "summarize" | "sliding" | "off"
KEEP_RECENT_MESSAGES = 6

# Resilience
ENABLE_RETRY = True
ENABLE_FALLBACK = False  # Tắt mặc định, user bật bằng /fallback on
MAX_RETRIES = 2

# Giá Sonnet 4.5 (giả định, cập nhật theo thực tế)
current_provider: LLMProvider = create_provider("claude-sonnet")

# RAG pipeline — lazy init khi user gọi /rag
rag_pipeline: RAGPipeline | None = None


def get_rag() -> RAGPipeline:
    global rag_pipeline
    if rag_pipeline is None:
        rag_pipeline = RAGPipeline(provider=current_provider)
    else:
        rag_pipeline.set_provider(current_provider)
    return rag_pipeline

# Folder lưu chat history
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ============================================================
# STATE — biến global lưu trạng thái session
# ============================================================
conversation_history: list[dict] = []
current_mode: str = "chat"  # chat | code | test | explain
total_input_tokens: int = 0
total_output_tokens: int = 0

# Map mode → system prompt tương ứng
MODE_PROMPTS = {
    "chat": CHAT_PROMPT,
    "code": CODE_REVIEW_PROMPT,
    "test": TEST_GENERATION_PROMPT,
    "explain": EXPLAIN_PROMPT,
    "agent": AGENT_PROMPT,
}


# ============================================================
# CORE: chat function
# ============================================================
def chat_stream(user_message: str) -> str:
    """Stream response từ current provider, với resilience."""
    global total_input_tokens, total_output_tokens, current_provider

    # 🆕 Manage context trước
    manage_context_if_needed()

    conversation_history.append({"role": "user", "content": user_message})

    def do_stream(provider) -> str:
        """Inner function để retry/fallback."""
        full = ""
        for text in provider.chat_stream(
            messages=conversation_history,
            system=MODE_PROMPTS[current_mode],
            max_tokens=2048,
        ):
            console.print(text, end="", style="cyan")
            full += text
        console.print()
        return full

    try:
        # Áp dụng retry và/hoặc fallback
        if ENABLE_FALLBACK:
            full_response, used_provider = try_with_fallback(
                do_stream, current_provider
            )
            # Update current_provider nếu đã fallback
            if used_provider.provider_name != current_provider.provider_name:
                current_provider = used_provider
        elif ENABLE_RETRY:
            full_response = retry_with_backoff(
                lambda: do_stream(current_provider),
                max_retries=MAX_RETRIES,
            )
        else:
            full_response = do_stream(current_provider)

        # Save & track
        conversation_history.append({"role": "assistant", "content": full_response})

        usage = current_provider.get_last_usage()
        total_input_tokens += usage.input_tokens
        total_output_tokens += usage.output_tokens

        cost = current_provider.calculate_cost(usage)
        console.print(
            f"[dim]📊 [{current_provider.provider_name}] "
            f"{usage.input_tokens} in + {usage.output_tokens} out = ${cost:.6f}[/dim]"
        )

        # Log mỗi LLM call vào Langfuse trace
        log_generation(
            name=f"chat:{current_mode}",
            model=current_provider.model_name,
            provider=current_provider.provider_name,
            mode=current_mode,
            input_messages=conversation_history[:-1],  # Exclude response vừa thêm
            output=full_response,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
        )

        return full_response

    except Exception as e:
        # Rollback user message
        if conversation_history and conversation_history[-1]["role"] == "user":
            conversation_history.pop()

        parsed = parse_provider_error(e)
        console.print(f"\n[red]❌ {parsed.user_message}[/red]")
        console.print(f"[yellow]💡 {parsed.suggestion}[/yellow]")
        return ""


def agent_loop(user_message: str, max_iterations: int = 10):
    global total_input_tokens, total_output_tokens

    # 🆕 Manage context
    manage_context_if_needed()

    conversation_history.append({"role": "user", "content": user_message})

    if not current_provider.supports_tools:
        console.print(
            f"[red]❌ Provider {current_provider.provider_name} không support tools.[/red]"
        )
        console.print("[dim]Switch sang Anthropic: /provider claude-sonnet[/dim]")
        if conversation_history and conversation_history[-1]["role"] == "user":
            conversation_history.pop()
        return

    anthropic_client = current_provider.get_raw_client()

    for iteration in range(max_iterations):
        try:
            response = anthropic_client.messages.create(
                model=current_provider.model_name,
                max_tokens=4096,
                system=MODE_PROMPTS["agent"],
                tools=TOOLS_SCHEMA,
                messages=conversation_history,
            )
        except Exception as e:
            parsed = parse_provider_error(e)
            console.print(f"\n[red]❌ {parsed.user_message}[/red]")
            console.print(f"[yellow]💡 {parsed.suggestion}[/yellow]")
            # Rollback nếu iteration đầu
            if (
                iteration == 0
                and conversation_history
                and conversation_history[-1]["role"] == "user"
            ):
                conversation_history.pop()
            return

        # ... (giữ nguyên phần xử lý response phía sau)
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        cost = calculate_cost(response.usage.input_tokens, response.usage.output_tokens)
        console.print(
            f"[dim]📊 Iter {iteration + 1}: "
            f"{response.usage.input_tokens} in + "
            f"{response.usage.output_tokens} out = ${cost:.6f}[/dim]"
        )

        conversation_history.append({"role": "assistant", "content": response.content})

        tool_uses = []
        text_parts = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if text_parts:
            text = "\n".join(text_parts)
            console.print(f"[cyan]{text}[/cyan]")

        if response.stop_reason == "end_turn" or not tool_uses:
            return

        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input
            console.print(f"\n[yellow]🔧 Tool call: {tool_name}({tool_input})[/yellow]")

            try:
                result = execute_tool(tool_name, tool_input)
            except Exception as e:
                result = f"❌ Tool error: {e}"

            preview = result[:200] + "..." if len(result) > 200 else result
            console.print(f"[dim]{preview}[/dim]")

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                }
            )

        conversation_history.append({"role": "user", "content": tool_results})

    console.print(
        f"[red]⚠️  Đạt max iterations ({max_iterations}), dừng agent loop[/red]"
    )


def structured_code_review(file_pattern: str):
    """
    Review code theo schema, lưu kết quả JSON.
    Demo Structured Output pattern.
    """
    global total_input_tokens, total_output_tokens

    # Đọc file
    file_content = read_files_for_review(file_pattern)
    if not file_content:
        return

    console.print(
        "\n[bold magenta]🔍 DevMate đang review (structured)...[/bold magenta]"
    )

    # Check provider support structured output
    if not current_provider.supports_structured_output:
        console.print(
            f"[red]❌ Provider {current_provider.provider_name} không support structured output.[/red]"
        )
        console.print("[dim]Switch sang Anthropic: /provider claude-sonnet[/dim]")
        return

    # Lấy raw Anthropic client từ provider
    anthropic_client = current_provider.get_raw_client()

    # Gọi LLM với schema
    report, usage = call_with_schema(
        client=anthropic_client,
        model=current_provider.model_name,
        system_prompt=STRUCTURED_REVIEW_PROMPT,
        user_message=f"Review code sau:\n\n{file_content}",
        schema=CodeReviewReport,
        max_tokens=8192,
    )

    # Update tokens
    total_input_tokens += usage["input_tokens"]
    total_output_tokens += usage["output_tokens"]
    cost = calculate_cost(usage["input_tokens"], usage["output_tokens"])
    console.print(
        f"[dim]📊 {usage['input_tokens']} in + {usage['output_tokens']} out = ${cost:.6f}[/dim]"
    )

    if not report:
        return

    # In ra terminal đẹp
    display_review_report(report)

    # Lưu JSON ra file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = DATA_DIR / f"review_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        # Pydantic có method tự dump JSON
        json.dump(report.model_dump(), f, ensure_ascii=False, indent=2, default=str)
    console.print(f"[green]💾 Đã lưu báo cáo vào {output_file}[/green]")


def manage_context_if_needed():
    """Check & manage context trước khi gửi request."""
    global conversation_history

    if CONTEXT_STRATEGY == "off":
        return

    current_tokens = total_tokens(conversation_history)

    if current_tokens <= MAX_CONTEXT_TOKENS:
        return

    console.print(
        f"\n[yellow]⚠️  Context lớn ({current_tokens:,} tokens), "
        f"đang {CONTEXT_STRATEGY}...[/yellow]"
    )

    if CONTEXT_STRATEGY == "sliding":
        conversation_history = trim_history_sliding(
            conversation_history,
            max_tokens=MAX_CONTEXT_TOKENS,
            keep_recent=KEEP_RECENT_MESSAGES,
        )
    elif CONTEXT_STRATEGY == "summarize":

        def summarize_fn(text: str) -> str:
            result = current_provider.chat(
                messages=[{"role": "user", "content": f"Conversation:\n\n{text}"}],
                system=SUMMARIZE_PROMPT,
                max_tokens=500,
            )
            return result.text

        try:
            conversation_history = summarize_history(
                conversation_history,
                summarize_fn=summarize_fn,
                keep_recent=KEEP_RECENT_MESSAGES,
            )
        except Exception as e:
            console.print(f"[red]❌ Summarize fail, fallback sang sliding: {e}[/red]")
            conversation_history = trim_history_sliding(
                conversation_history,
                max_tokens=MAX_CONTEXT_TOKENS,
                keep_recent=KEEP_RECENT_MESSAGES,
            )

    new_tokens = total_tokens(conversation_history)
    console.print(
        f"[green]✅ Còn {new_tokens:,} tokens "
        f"({len(conversation_history)} messages)[/green]"
    )


def display_review_report(report: CodeReviewReport):
    """In báo cáo review đẹp ra terminal."""
    # Header
    score_color = (
        "green"
        if report.overall_score >= 7
        else "yellow"
        if report.overall_score >= 4
        else "red"
    )

    console.print(
        Panel.fit(
            f"[bold]📊 Code Review Report[/bold]\n\n"
            f"[bold]Score:[/bold] [{score_color}]{report.overall_score}/10[/{score_color}]\n"
            f"[bold]Total Issues:[/bold] {report.total_issues}\n"
            f"[bold]Files:[/bold] {', '.join(report.files_reviewed) if report.files_reviewed else 'N/A'}\n\n"
            f"[italic]{report.summary}[/italic]",
            border_style=score_color,
        )
    )

    # Issues
    if report.issues:
        console.print("\n[bold red]🐛 Issues:[/bold red]")

        severity_colors = {
            "critical": "red",
            "high": "red",
            "medium": "yellow",
            "low": "blue",
            "info": "dim",
        }

        for i, issue in enumerate(report.issues, 1):
            color = severity_colors.get(issue.severity.value, "white")
            console.print(
                f"\n[bold {color}]#{i} [{issue.severity.value.upper()}] {issue.title}[/bold {color}]"
            )
            console.print(f"  📁 {issue.file_path}:{issue.line_start}-{issue.line_end}")
            console.print(f"  🏷️  Category: {issue.category.value}")
            console.print(f"  📝 {issue.description}")
            console.print(f"  💡 Why: {issue.explanation}")
            console.print(f"  ✨ Fix:")
            console.print(Panel(issue.suggested_fix, border_style="dim"))

    # Strengths
    if report.strengths:
        console.print("\n[bold green]✅ Strengths:[/bold green]")
        for s in report.strengths:
            console.print(f"  • {s}")


# ============================================================
# UTILITIES
# ============================================================
def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Tính chi phí qua provider hiện tại."""
    from providers.base import TokenUsage

    return current_provider.calculate_cost(
        TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
    )


def show_stats():
    """In bảng tổng kết tokens & cost."""
    total_cost = calculate_cost(total_input_tokens, total_output_tokens)

    table = Table(title="📊 Session Stats", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Mode hiện tại", current_mode)
    table.add_row("Số tin nhắn", str(len(conversation_history)))
    table.add_row("Input tokens", f"{total_input_tokens:,}")
    table.add_row("Output tokens", f"{total_output_tokens:,}")
    table.add_row("Total cost", f"${total_cost:.6f}")

    console.print(table)


def save_chat():
    """Lưu lịch sử chat ra file JSON."""
    if not conversation_history:
        console.print("[yellow]⚠️  Không có gì để lưu (lịch sử rỗng)[/yellow]")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = DATA_DIR / f"chat_{timestamp}.json"

    data = {
        "saved_at": timestamp,
        "mode": current_mode,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "messages": conversation_history,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    console.print(f"[green]✅ Đã lưu vào {filename}[/green]")


def load_chat():
    """Load lịch sử chat từ file JSON gần nhất."""
    global conversation_history, total_input_tokens, total_output_tokens, current_mode

    files = sorted(DATA_DIR.glob("chat_*.json"))
    if not files:
        console.print("[yellow]⚠️  Không có file chat nào để load[/yellow]")
        return

    # Hiển thị list cho user chọn
    console.print("\n[bold]📂 Available chats:[/bold]")
    for i, f in enumerate(files, 1):
        console.print(f"  {i}. {f.name}")

    choice = Prompt.ask("\nChọn số (hoặc Enter để hủy)", default="")
    if not choice:
        return

    try:
        idx = int(choice) - 1
        filename = files[idx]
    except (ValueError, IndexError):
        console.print("[red]❌ Lựa chọn không hợp lệ[/red]")
        return

    with open(filename, encoding="utf-8") as f:
        data = json.load(f)

    conversation_history = data["messages"]
    total_input_tokens = data.get("total_input_tokens", 0)
    total_output_tokens = data.get("total_output_tokens", 0)
    current_mode = data.get("mode", "chat")

    console.print(
        f"[green]✅ Đã load {filename.name} - "
        f"{len(conversation_history)} messages, mode: {current_mode}[/green]"
    )


def switch_mode(mode: str):
    """Đổi mode (chat/code/test/explain)."""
    global current_mode, conversation_history

    if mode not in MODE_PROMPTS:
        console.print(
            f"[red]❌ Mode không tồn tại. Chọn: {list(MODE_PROMPTS.keys())}[/red]"
        )
        return

    current_mode = mode
    # Khi đổi mode, clear history để tránh context cũ ảnh hưởng
    conversation_history.clear()

    mode_descriptions = {
        "chat": "💬 Chat thường",
        "code": "🔍 Code Review - paste code để review",
        "test": "🧪 Test Generation - paste function để sinh unit test",
        "explain": "📖 Code Explain - paste code để giải thích",
        "agent": "🤖 Agent - tự khám phá codebase với tools",
    }

    console.print(
        f"[bold green]✅ Đã chuyển sang mode: {mode_descriptions[mode]}[/bold green]"
    )


def show_help():
    table = Table(title="🛠️  DevMate Commands", show_header=True)
    table.add_column("Command", style="cyan", width=30)
    table.add_column("Mô tả", style="white")

    table.add_section()
    table.add_row(
        "[bold]/agent <task>[/bold]",
        "[bold yellow]Agent tự khám phá & làm task[/bold yellow]",
    )
    table.add_row(
        "[bold]/chain <task>[/bold]",
        "[bold magenta]Multi-agent: planner → coder → reviewer (self-correction)[/bold magenta]",
    )
    table.add_row(
        "[bold]/rag <câu hỏi>[/bold]",
        "[bold cyan]Hỏi về codebase — hybrid search + rerank[/bold cyan]",
    )
    table.add_row("[bold]/rag index[/bold]", "Index codebase vào vector DB")
    table.add_row("[bold]/code <file/folder>[/bold]", "Review 1 file hoặc folder")
    table.add_row(
        "[bold]/review <file>[/bold]",
        "[bold yellow]Code review chuẩn JSON, có lưu file[/bold yellow]",
    )
    table.add_row("[bold]/test <file>[/bold]", "Sinh unit test cho file")
    table.add_row("[bold]/explain <file>[/bold]", "Giải thích code trong file")
    table.add_row("/provider [name]", "Switch LLM provider (claude/gpt/gemini)")
    table.add_row("/chat", "Quay về chat thường")

    table.add_section()
    table.add_row("/save", "Lưu lịch sử chat")
    table.add_row("/load", "Load chat đã lưu")
    table.add_row("/clear", "Xóa lịch sử")
    table.add_row("/stats", "Token usage & cost")
    table.add_row("/help", "Hiện bảng này")
    table.add_row("/context", "Xem thông tin context hiện tại")
    table.add_row("/strategy <mode>", "Strategy: summarize|sliding|off")
    table.add_row("/fallback on|off", "Tự switch provider khi lỗi")
    table.add_row("/quit", "Thoát")

    console.print(table)

    # Examples
    console.print("\n[bold yellow]📚 Ví dụ:[/bold yellow]")
    console.print("  /code src/auth.py              [dim]# review 1 file[/dim]")
    console.print("  /code src/auth/                [dim]# review cả folder[/dim]")
    console.print('  /code "src/**/*.py"            [dim]# glob pattern[/dim]')
    console.print("  /test utils/helper.js          [dim]# sinh test[/dim]")
    console.print("  /explain components/Login.tsx  [dim]# giải thích code[/dim]")


# ============================================================
# MAIN LOOP
# ============================================================
def main():
    global current_provider, current_mode, ENABLE_FALLBACK, CONTEXT_STRATEGY

    # Bắt đầu Langfuse trace cho session này (nếu LANGFUSE keys đã set)
    session_id = start_session("devmate-cli")

    console.print(
        Panel.fit(
            "[bold cyan]🤖 DevMate AI v2.0[/bold cyan]\n"
            "Trợ lý lập trình đa năng\n"
            f"[dim]Session: {session_id} | Gõ /help để xem commands[/dim]",
            border_style="cyan",
        )
    )

    while True:
        try:
            # Hiển thị mode hiện tại trong prompt
            mode_emoji = {
                "chat": "💬",
                "code": "🔍",
                "test": "🧪",
                "explain": "📖",
                "agent": "🤖",
            }[current_mode]

            user_input = Prompt.ask(
                f"\n[bold green]{mode_emoji} Bạn[/bold green]"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Tạm biệt! 👋[/yellow]")
            break

        if not user_input:
            continue

        # Xử lý commands (bắt đầu bằng /)
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else None

            if cmd in ["/quit", "/exit", "/q"]:
                show_stats()
                flush()  # Flush Langfuse events trước khi thoát
                console.print("[yellow]Tạm biệt! 👋[/yellow]")
                break
            elif cmd == "/clear":
                conversation_history.clear()
                console.print("[dim]Đã xóa lịch sử[/dim]")
            elif cmd == "/help":
                show_help()
            elif cmd == "/stats":
                show_stats()
            elif cmd == "/save":
                save_chat()
            elif cmd == "/load":
                load_chat()
            elif cmd == "/provider":
                if not arg:
                    # List available providers
                    console.print("\n[bold]Available providers:[/bold]")
                    for preset in PRESETS:
                        marker = (
                            " ← current"
                            if PRESETS[preset][1] == current_provider.model_name
                            else ""
                        )
                        console.print(f"  • {preset}{marker}")
                    console.print(f"\n[dim]Usage: /provider <preset>[/dim]")
                    console.print(
                        f"[dim]Hiện tại: {current_provider.provider_name}/{current_provider.model_name}[/dim]"
                    )
                else:
                    try:
                        current_provider = create_provider(arg)
                        console.print(
                            f"[green]✅ Đã switch sang {current_provider.provider_name}/{current_provider.model_name}[/green]"
                        )
                    except ValueError as e:
                        console.print(f"[red]❌ {e}[/red]")
            elif cmd == "/context":
                current_tokens = total_tokens(conversation_history)
                pct = (
                    (current_tokens / MAX_CONTEXT_TOKENS * 100)
                    if MAX_CONTEXT_TOKENS > 0
                    else 0
                )
                console.print(f"\n[bold]📊 Context Info:[/bold]")
                console.print(f"  Messages: {len(conversation_history)}")
                console.print(
                    f"  Tokens (estimated): {current_tokens:,} / {MAX_CONTEXT_TOKENS:,} ({pct:.1f}%)"
                )
                console.print(f"  Strategy: [cyan]{CONTEXT_STRATEGY}[/cyan]")
                console.print(f"  Keep recent: {KEEP_RECENT_MESSAGES} messages")

            elif cmd == "/strategy":
                if not arg or arg not in ["summarize", "sliding", "off"]:
                    console.print("[red]Usage: /strategy <summarize|sliding|off>[/red]")
                    console.print(
                        "[dim]  summarize - tóm tắt phần cũ (tốn 1 API call)[/dim]"
                    )
                    console.print(
                        "[dim]  sliding   - chỉ giữ N messages cuối (free)[/dim]"
                    )
                    console.print("[dim]  off       - không quản lý context[/dim]")
                else:
                    CONTEXT_STRATEGY = arg
                    console.print(f"[green]✅ Context strategy: {arg}[/green]")

            elif cmd == "/fallback":
                if not arg:
                    console.print(
                        f"\n[bold]Fallback hiện tại:[/bold] {'ON' if ENABLE_FALLBACK else 'OFF'}"
                    )
                    console.print("[dim]Usage: /fallback on|off[/dim]")
                elif arg.lower() in ["on", "true", "1"]:
                    ENABLE_FALLBACK = True
                    console.print(
                        "[green]✅ Fallback ON - tự switch provider khi lỗi[/green]"
                    )
                elif arg.lower() in ["off", "false", "0"]:
                    ENABLE_FALLBACK = False
                    console.print("[yellow]⚠️  Fallback OFF[/yellow]")

            # Xử lý mode commands — có thể kèm file path
            elif user_input.startswith(
                ("/code", "/test", "/explain", "/chat", "/agent")
            ):
                parts = user_input.split(maxsplit=1)
                mode_cmd = parts[0][1:]
                arg = parts[1] if len(parts) > 1 else None

                # Mode agent dùng agent_loop khác
                if mode_cmd == "agent":
                    switch_mode("agent")
                    if arg:
                        console.print(f"\n[bold magenta]DevMate Agent:[/bold magenta]")
                        agent_loop(arg)
                    continue

                if arg:
                    # Có file path → đọc file và review luôn
                    switch_mode(mode_cmd)
                    file_content = read_files_for_review(arg)

                    if file_content:
                        # Tạo message cho LLM với context rõ ràng
                        instruction_map = {
                            "code": "Hãy review code trong các file sau:",
                            "test": "Hãy viết unit tests cho các function trong file sau:",
                            "explain": "Hãy giải thích code trong các file sau:",
                            "chat": "Hãy phân tích các file sau:",
                        }

                        full_prompt = f"{instruction_map[mode_cmd]}\n\n{file_content}"

                        console.print(
                            f"\n[bold magenta]DevMate ({mode_cmd}):[/bold magenta]"
                        )
                        chat_stream(full_prompt)
                else:
                    # Không có arg → chỉ switch mode (giống cũ)
                    switch_mode(mode_cmd)
            # Command /chain — Multi-Agent LangGraph
            elif cmd == "/chain":
                if not arg:
                    console.print("[red]❌ Cần task. Vd: /chain viết function tính fibonacci với memoization[/red]")
                else:
                    final = run_chain(arg)
                    console.print("\n[bold]📋 PLAN:[/bold]")
                    console.print(final["plan"])
                    console.print("\n[bold]💻 FINAL CODE:[/bold]")
                    console.print(Panel(final["code"], border_style="green"))
                    status = "✅ PASS" if final["passed"] else f"⚠ Stopped after {final['iterations']} iterations"
                    console.print(f"\n[bold]Status:[/bold] {status}")

            # Command /rag — Advanced RAG
            elif cmd == "/rag":
                rag = get_rag()
                if not arg:
                    console.print(
                        "[bold]RAG commands:[/bold]\n"
                        "  [cyan]/rag index[/cyan]          — index codebase hiện tại (.)\n"
                        "  [cyan]/rag index <folder>[/cyan]  — index folder cụ thể\n"
                        "  [cyan]/rag index --force[/cyan]   — xóa index cũ và index lại\n"
                        "  [cyan]/rag <câu hỏi>[/cyan]      — hỏi về codebase"
                    )
                elif arg.startswith("index"):
                    parts = arg.split()
                    force = "--force" in parts
                    folder = next(
                        (p for p in parts[1:] if not p.startswith("--")), "."
                    )
                    rag.index(folder, force=force)
                else:
                    console.print(f"\n[bold magenta]🔍 RAG ({current_provider.provider_name}):[/bold magenta]")
                    answer = rag.query(arg)
                    console.print(Markdown(answer))

            # Command /review (structured output)
            elif cmd.startswith("/review"):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    console.print("[red]❌ Cần file path. Vd: /review devmate.py[/red]")
                else:
                    structured_code_review(parts[1])
            continue

        # Single-line input bình thường → gửi LLM
        console.print(f"\n[bold magenta]DevMate ({current_mode}):[/bold magenta]")
        if current_mode == "agent":
            agent_loop(user_input)
        else:
            chat_stream(user_input)


if __name__ == "__main__":
    main()
