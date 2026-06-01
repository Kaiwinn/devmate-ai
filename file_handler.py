# file_handler.py
"""
Xử lý đọc file/folder để gửi cho LLM review.
"""
import glob
from pathlib import Path
from rich.console import Console

console = Console()

# Map đuôi file → ngôn ngữ (để LLM format syntax highlight đúng)
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".java": "java",
    ".kt": "kotlin",
    ".dart": "dart",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".vue": "vue",
}

# Folder/file cần ignore khi review
IGNORE_PATTERNS = {
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    "dist",
    "build",
    ".next",
    "target",
    ".idea",
    ".vscode",
    "coverage",
    ".DS_Store",
}

# Giới hạn để tránh tốn quá nhiều token
MAX_FILE_SIZE_KB = 100        # File > 100KB sẽ skip
MAX_FILES_PER_REQUEST = 10    # Tối đa 10 file 1 request
MAX_TOTAL_CHARS = 50_000      # Tổng tất cả file ≤ 50K chars


def detect_language(file_path: Path) -> str:
    """Detect ngôn ngữ từ đuôi file."""
    return EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower(), "text")


def should_ignore(path: Path) -> bool:
    """Check xem file/folder có nên bỏ qua không."""
    for part in path.parts:
        if part in IGNORE_PATTERNS:
            return True
    return False


def read_single_file(file_path: Path) -> tuple[str, int]:
    """
    Đọc 1 file, trả về (content_formatted, char_count).
    Format giống markdown code block để LLM hiểu rõ.
    """
    try:
        size_kb = file_path.stat().st_size / 1024
        if size_kb > MAX_FILE_SIZE_KB:
            return (
                f"⚠️ File `{file_path}` quá lớn ({size_kb:.1f}KB > {MAX_FILE_SIZE_KB}KB), đã skip\n",
                0,
            )
        
        content = file_path.read_text(encoding="utf-8")
        language = detect_language(file_path)
        
        formatted = (
            f"## 📄 File: `{file_path}`\n\n"
            f"```{language}\n{content}\n```\n\n"
        )
        return formatted, len(content)
    except UnicodeDecodeError:
        return f"⚠️ File `{file_path}` không phải text file, đã skip\n", 0
    except Exception as e:
        return f"❌ Lỗi đọc `{file_path}`: {e}\n", 0


def resolve_paths(pattern: str) -> list[Path]:
    """
    Convert pattern (file/folder/glob) thành list các file Path.
    
    Examples:
    - "src/auth.py"     → [Path("src/auth.py")]
    - "src/auth/"       → [tất cả file trong src/auth/]
    - "src/**/*.py"     → [tất cả .py trong src/ recursive]
    - "*.py"            → [tất cả .py ở thư mục hiện tại]
    """
    p = Path(pattern)
    
    # Trường hợp 1: là file cụ thể, tồn tại
    if p.is_file():
        return [p]
    
    # Trường hợp 2: là folder → lấy tất cả file trong đó (recursive)
    if p.is_dir():
        files = []
        for f in p.rglob("*"):
            if f.is_file() and not should_ignore(f):
                # Chỉ lấy file có đuôi biết
                if f.suffix.lower() in EXTENSION_TO_LANGUAGE:
                    files.append(f)
        return sorted(files)
    
    # Trường hợp 3: là glob pattern (có * hoặc **)
    if "*" in pattern:
        matched = [Path(f) for f in glob.glob(pattern, recursive=True)]
        return sorted([
            f for f in matched
            if f.is_file() and not should_ignore(f)
        ])
    
    # Không match gì
    return []


def read_files_for_review(pattern: str) -> str | None:
    """
    Đọc file(s) theo pattern, trả về content đã format sẵn để gửi LLM.
    Trả về None nếu không có file nào.
    """
    files = resolve_paths(pattern)
    
    if not files:
        console.print(f"[red]❌ Không tìm thấy file nào match: '{pattern}'[/red]")
        return None
    
    # Áp dụng giới hạn
    if len(files) > MAX_FILES_PER_REQUEST:
        console.print(
            f"[yellow]⚠️  Tìm thấy {len(files)} file, "
            f"chỉ review {MAX_FILES_PER_REQUEST} file đầu tiên[/yellow]"
        )
        files = files[:MAX_FILES_PER_REQUEST]
    
    # In ra danh sách file sẽ review
    console.print(f"\n[bold cyan]📂 Sẽ review {len(files)} file:[/bold cyan]")
    for f in files:
        console.print(f"  • {f}")
    console.print()
    
    # Đọc và gộp
    content_parts = []
    total_chars = 0
    
    for file_path in files:
        formatted, chars = read_single_file(file_path)
        
        # Check tổng chars để không vượt context
        if total_chars + chars > MAX_TOTAL_CHARS:
            console.print(
                f"[yellow]⚠️  Đạt giới hạn {MAX_TOTAL_CHARS} chars, "
                f"các file sau sẽ skip[/yellow]"
            )
            break
        
        content_parts.append(formatted)
        total_chars += chars
    
    return "".join(content_parts)