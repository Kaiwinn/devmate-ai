# devmate.py - Version 2.0
import json
import os
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from file_handler import read_files_for_review
from tools import TOOLS_SCHEMA, execute_tool

from prompts import (
    CHAT_PROMPT,
    CODE_REVIEW_PROMPT,
    TEST_GENERATION_PROMPT,
    EXPLAIN_PROMPT,
    AGENT_PROMPT,
)

# ============================================================
# CONFIG
# ============================================================
load_dotenv()
client = Anthropic()
console = Console()

# Giá Sonnet 4.5: $3/1M input tokens, $15/1M output tokens
PRICE_INPUT_PER_MTOK = 3.0
PRICE_OUTPUT_PER_MTOK = 15.0

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
    """
    Stream response từ Claude.
    - Append user message vào history
    - Gọi API với system prompt theo mode hiện tại
    - Stream từng chunk ra terminal
    - Append response vào history
    - Update token counter
    """
    global total_input_tokens, total_output_tokens

    conversation_history.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    full_response = ""

    # Stream response
    with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        system=MODE_PROMPTS[current_mode],
        messages=conversation_history,
    ) as stream:
        for text in stream.text_stream:
            console.print(text, end="", style="cyan")
            full_response += text

        # Sau khi stream xong, lấy final message để biết usage
        final_message = stream.get_final_message()

    console.print()  # newline

    # Lưu vào history
    conversation_history.append(
        {
            "role": "assistant",
            "content": full_response,
        }
    )

    # Update token counter
    input_tokens = final_message.usage.input_tokens
    output_tokens = final_message.usage.output_tokens
    total_input_tokens += input_tokens
    total_output_tokens += output_tokens

    # In ra cost của câu này
    cost = calculate_cost(input_tokens, output_tokens)
    console.print(
        f"[dim]📊 {input_tokens} in + {output_tokens} out = ${cost:.6f}[/dim]"
    )

    return full_response


def agent_loop(user_message: str, max_iterations: int = 10):
    """
    Agent loop: LLM có thể gọi tools nhiều lần đến khi xong task.

    Flow:
    1. Gửi message + tools schema cho LLM
    2. LLM trả về: text response HOẶC tool_use request
    3. Nếu là tool_use → execute tool → gửi kết quả về LLM
    4. Loop đến khi LLM trả về text cuối (stop_reason='end_turn')
    """
    global total_input_tokens, total_output_tokens

    conversation_history.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    for iteration in range(max_iterations):
        # Gọi API với tools enabled
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            system=MODE_PROMPTS["agent"],
            tools=TOOLS_SCHEMA,
            messages=conversation_history,
        )

        # Update token counter
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        # In token info
        cost = calculate_cost(response.usage.input_tokens, response.usage.output_tokens)
        console.print(
            f"[dim]📊 Iter {iteration + 1}: "
            f"{response.usage.input_tokens} in + "
            f"{response.usage.output_tokens} out = ${cost:.6f}[/dim]"
        )

        # Lưu assistant response vào history
        conversation_history.append(
            {
                "role": "assistant",
                "content": response.content,
            }
        )

        # Phân tích content blocks
        tool_uses = []
        text_parts = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # In text response (nếu có)
        if text_parts:
            text = "\n".join(text_parts)
            console.print(f"[cyan]{text}[/cyan]")

        # Nếu LLM không gọi tool nào → đã xong
        if response.stop_reason == "end_turn" or not tool_uses:
            return

        # Execute từng tool và collect results
        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input

            console.print(f"\n[yellow]🔧 Tool call: {tool_name}({tool_input})[/yellow]")

            result = execute_tool(tool_name, tool_input)

            # In preview kết quả (rút gọn)
            preview = result[:200] + "..." if len(result) > 200 else result
            console.print(f"[dim]{preview}[/dim]")

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                }
            )

        # Gửi tool results về LLM trong lần loop tiếp theo
        conversation_history.append(
            {
                "role": "user",
                "content": tool_results,
            }
        )

    console.print(
        f"[red]⚠️  Đạt max iterations ({max_iterations}), dừng agent loop[/red]"
    )


# ============================================================
# UTILITIES
# ============================================================
def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Tính chi phí USD dựa trên giá Sonnet 4.5."""
    input_cost = (input_tokens / 1_000_000) * PRICE_INPUT_PER_MTOK
    output_cost = (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_MTOK
    return input_cost + output_cost


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
    table.add_row("[bold]/code <file/folder>[/bold]", "Review 1 file hoặc folder")
    table.add_row("[bold]/test <file>[/bold]", "Sinh unit test cho file")
    table.add_row("[bold]/explain <file>[/bold]", "Giải thích code trong file")
    table.add_row("/chat", "Quay về chat thường")

    table.add_section()
    table.add_row("/save", "Lưu lịch sử chat")
    table.add_row("/load", "Load chat đã lưu")
    table.add_row("/clear", "Xóa lịch sử")
    table.add_row("/stats", "Token usage & cost")
    table.add_row("/help", "Hiện bảng này")
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
    console.print(
        Panel.fit(
            "[bold cyan]🤖 DevMate AI v2.0[/bold cyan]\n"
            "Trợ lý lập trình đa năng\n"
            "[dim]Gõ /help để xem commands[/dim]",
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
            cmd = user_input.lower()

            if cmd in ["/quit", "/exit", "/q"]:
                show_stats()
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

            continue

        # Single-line input bình thường → gửi LLM
        console.print(f"\n[bold magenta]DevMate ({current_mode}):[/bold magenta]")
        if current_mode == "agent":
            agent_loop(user_input)
        else:
            chat_stream(user_input)


if __name__ == "__main__":
    main()
