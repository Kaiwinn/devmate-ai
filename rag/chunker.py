# rag/chunker.py
"""
Chunker — chia code thành chunks có nghĩa.

Tại sao KHÔNG dùng fixed-size chunking (vd: cứ 500 chars một chunk)?
- Cắt giữa function → LLM nhận half-function, mất context
- AST-based chunking: mỗi function/class = 1 chunk → coherent unit

Python dùng AST (Abstract Syntax Tree) để parse code structure —
tương tự Java reflection nhưng ở compile time.
"""

import ast
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Chunk:
    """Một unit nội dung đã được chunk."""
    content: str
    source_file: str
    chunk_type: str   # "function", "class", "module_docstring", "top_level"
    name: str         # tên function/class hoặc filename
    start_line: int
    end_line: int

    @property
    def doc_id(self) -> str:
        return f"{self.source_file}::{self.name}::{self.start_line}"


def chunk_python_file(file_path: str) -> list[Chunk]:
    """
    Chunk 1 file Python theo function/class dùng AST.
    Fallback sang fixed-size nếu parse fail (vd: syntax error).
    """
    path = Path(file_path)
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return []

    chunks: list[Chunk] = []

    # Parse AST để tìm function và class definitions
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Fallback: file không parse được → chunk theo 50 dòng
        return _chunk_fixed_size(source, file_path)

    lines = source.splitlines()

    # Module-level docstring
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
    ):
        docstring_node = tree.body[0]
        chunks.append(Chunk(
            content=ast.get_docstring(tree) or "",
            source_file=file_path,
            chunk_type="module_docstring",
            name=path.stem,
            start_line=1,
            end_line=docstring_node.end_lineno,
        ))

    # Mỗi function và class top-level = 1 chunk
    # Lấy top-level defs (trực tiếp trong Module)
    top_level_nodes = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            top_level_nodes.add(id(node))
        elif isinstance(node, ast.ClassDef):
            # Thêm methods của class
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    top_level_nodes.add(id(child))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if id(node) not in top_level_nodes:
            continue

        start = node.lineno - 1
        end = node.end_lineno
        chunk_lines = lines[start:end]

        # Bỏ qua chunk quá ngắn (getter/setter 1-2 dòng)
        if len(chunk_lines) < 3:
            continue

        chunk_type = "class" if isinstance(node, ast.ClassDef) else "function"
        chunks.append(Chunk(
            content="\n".join(chunk_lines),
            source_file=file_path,
            chunk_type=chunk_type,
            name=node.name,
            start_line=node.lineno,
            end_line=node.end_lineno,
        ))

    # Nếu không tìm được gì (file chỉ có imports/constants) → chunk cả file
    if not chunks:
        chunks.append(Chunk(
            content=source[:3000],  # Giới hạn 3000 chars
            source_file=file_path,
            chunk_type="top_level",
            name=path.stem,
            start_line=1,
            end_line=len(lines),
        ))

    return chunks


def chunk_folder(folder_path: str, extensions: list[str] | None = None) -> list[Chunk]:
    """Chunk tất cả files trong folder."""
    if extensions is None:
        extensions = [".py"]

    folder = Path(folder_path)
    all_chunks: list[Chunk] = []

    for ext in extensions:
        for file_path in sorted(folder.rglob(f"*{ext}")):
            # Bỏ qua venv, __pycache__, hidden folders
            if any(part.startswith((".","__")) or part == "venv"
                   for part in file_path.parts):
                continue
            chunks = chunk_python_file(str(file_path))
            all_chunks.extend(chunks)

    return all_chunks


def _chunk_fixed_size(source: str, file_path: str, size: int = 50) -> list[Chunk]:
    """Fallback: chunk theo số dòng cố định."""
    lines = source.splitlines()
    chunks = []
    for i in range(0, len(lines), size):
        block = "\n".join(lines[i:i + size])
        if block.strip():
            chunks.append(Chunk(
                content=block,
                source_file=file_path,
                chunk_type="top_level",
                name=f"lines_{i+1}_{i+size}",
                start_line=i + 1,
                end_line=min(i + size, len(lines)),
            ))
    return chunks
