import os
from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

load_dotenv()
client = Anthropic()
console = Console()

conversation_history = []

SYSTEM_PROMPT = """Bạn là DevMate, trợ lý AI cho lập trình viên.
- Trả lời ngắn gọn, thẳng vào vấn đề
- Có ví dụ code khi giải thích kỹ thuật
- Dùng markdown để format (code block với syntax highlight)
- Nếu không chắc, hãy nói "tôi không chắc" thay vì bịa
"""


def chat_stream(user_message: str) -> str:
    """Stream response từ Claude, in từng chunk ra terminal."""
    conversation_history.append({
        "role": "user",
        "content": user_message
    })
    
    full_response = ""
    
    with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=conversation_history,
    ) as stream:
        for text in stream.text_stream:
            console.print(text, end="", style="cyan")
            full_response += text
    
    console.print()
    
    conversation_history.append({
        "role": "assistant",
        "content": full_response
    })
    
    return full_response


def main():
    console.print(Panel.fit(
        "[bold cyan]🤖 DevMate AI[/bold cyan]\n"
        "Trợ lý lập trình của bạn\n"
        "[dim]Gõ 'quit' để thoát, 'clear' để xóa lịch sử[/dim]",
        border_style="cyan"
    ))
    
    while True:
        try:
            user_input = Prompt.ask("\n[bold green]Bạn[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Tạm biệt! 👋[/yellow]")
            break
        
        if user_input.lower() in ["quit", "exit", "q"]:
            console.print("[yellow]Tạm biệt! 👋[/yellow]")
            break
        
        if user_input.lower() == "clear":
            conversation_history.clear()
            console.print("[dim]Đã xóa lịch sử conversation[/dim]")
            continue
        
        if not user_input:
            continue
        
        console.print("\n[bold magenta]DevMate:[/bold magenta]")
        chat_stream(user_input)


if __name__ == "__main__":
    main()