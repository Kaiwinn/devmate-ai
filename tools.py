# tools.py
"""
Tools mà LLM có thể gọi.
Mỗi tool có 2 phần:
1. Schema (mô tả cho LLM hiểu khi nào dùng)
2. Implementation (code thật sự chạy)
"""

import subprocess
from pathlib import Path

# ============================================================
# TOOL IMPLEMENTATIONS (code chạy thật)
# ============================================================


def read_file(path: str) -> str:
    """Đọc nội dung file."""
    try:
        p = Path(path)
        if not p.exists():
            return f"❌ File không tồn tại: {path}"
        if not p.is_file():
            return f"❌ Đây không phải file: {path}"

        # Giới hạn 100KB để tránh tốn token
        if p.stat().st_size > 100_000:
            return f"❌ File quá lớn (> 100KB): {path}"

        content = p.read_text(encoding="utf-8")
        return f"📄 Content của {path}:\n\n{content}"
    except Exception as e:
        return f"❌ Lỗi đọc file: {e}"


def list_files(directory: str = ".") -> str:
    """List file và folder trong directory."""
    try:
        p = Path(directory)
        if not p.exists():
            return f"❌ Thư mục không tồn tại: {directory}"
        if not p.is_dir():
            return f"❌ Đây không phải thư mục: {directory}"

        IGNORE = {"venv", "node_modules", "__pycache__", ".git", "data", "test_code"}
        items = []
        for item in sorted(p.iterdir()):
            if item.name in IGNORE or item.name.startswith("."):
                continue
            prefix = "📁" if item.is_dir() else "📄"
            items.append(f"{prefix} {item.name}")

        return f"Nội dung của {directory}:\n" + "\n".join(items)
    except Exception as e:
        return f"❌ Lỗi list: {e}"


def search_in_code(pattern: str, directory: str = ".") -> str:
    """Search text trong code (giống grep)."""
    try:
        # Dùng grep system (nhanh hơn Python)
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "--include=*.py",
                "--include=*.js",
                "--include=*.ts",
                "--include=*.java",
                "--include=*.dart",
                "--include=*.go",
                "--exclude-dir=venv",
                "--exclude-dir=node_modules",
                "--exclude-dir=__pycache__",
                "--exclude-dir=.git",
                pattern,
                directory,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        output = result.stdout.strip()
        if not output:
            return f"🔍 Không tìm thấy '{pattern}' trong {directory}"

        # Giới hạn 30 dòng output
        lines = output.split("\n")
        if len(lines) > 30:
            lines = lines[:30] + [
                f"... (và {len(output.split('chr(10)')) - 30} dòng nữa)"
            ]

        return f"🔍 Kết quả search '{pattern}':\n" + "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "❌ Search timeout (> 10s)"
    except FileNotFoundError:
        return "❌ Không có lệnh `grep` trên hệ thống"
    except Exception as e:
        return f"❌ Lỗi search: {e}"


def run_command(command: str) -> str:
    """Chạy shell command. CẨN THẬN: tool này nguy hiểm."""
    # Whitelist các lệnh an toàn
    SAFE_COMMANDS = ["ls", "pwd", "cat", "head", "tail", "wc", "find", "tree", "git"]

    first_word = command.strip().split()[0] if command.strip() else ""
    if first_word not in SAFE_COMMANDS:
        return (
            f"❌ Command '{first_word}' không được phép. "
            f"Allowed: {', '.join(SAFE_COMMANDS)}"
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout + result.stderr
        if len(output) > 5000:
            output = output[:5000] + "\n... (truncated)"
        return f"$ {command}\n{output}"
    except subprocess.TimeoutExpired:
        return "❌ Command timeout (> 10s)"
    except Exception as e:
        return f"❌ Lỗi run command: {e}"


# ============================================================
# SCHEMA cho LLM hiểu
# ============================================================
# Đây là cách Anthropic định nghĩa tool, theo JSON Schema
TOOLS_SCHEMA = [
    {
        "name": "read_file",
        "description": (
            "Đọc nội dung của một file. Dùng khi cần xem code, "
            "review file, hoặc tìm thông tin trong file cụ thể."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Đường dẫn đến file, vd: 'src/auth.py'",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "List file và folder trong directory. Dùng để khám phá cấu trúc project."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Đường dẫn thư mục, mặc định là '.'",
                }
            },
        },
    },
    {
        "name": "search_in_code",
        "description": (
            "Search text/keyword trong code (giống grep). "
            "Dùng để tìm function, class, hoặc pattern trong codebase."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text cần tìm",
                },
                "directory": {
                    "type": "string",
                    "description": "Thư mục để search, mặc định '.'",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Chạy shell command an toàn. Chỉ cho phép: "
            "ls, pwd, cat, head, tail, wc, find, tree, git."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Lệnh shell cần chạy",
                }
            },
            "required": ["command"],
        },
    },
]

# Mapping tên tool → function thật
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_files": list_files,
    "search_in_code": search_in_code,
    "run_command": run_command,
}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute tool với input từ LLM."""
    if tool_name not in TOOL_FUNCTIONS:
        return f"❌ Tool không tồn tại: {tool_name}"

    func = TOOL_FUNCTIONS[tool_name]
    try:
        return func(**tool_input)
    except TypeError as e:
        return f"❌ Sai input cho tool {tool_name}: {e}"
    except Exception as e:
        return f"❌ Lỗi execute tool: {e}"
