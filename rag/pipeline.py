# rag/pipeline.py
"""
RAGPipeline — high-level interface cho toàn bộ RAG system.

Flow:
  index_folder(path) → chunk → embed → store in ChromaDB
  query(question)    → retrieve (hybrid) → format context → LLM → answer
"""

from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from rag.chunker import Chunk, chunk_folder
from rag.embedder import embed_texts, embed_single
from rag.store import upsert_chunks, semantic_search, count_indexed, clear_collection
from rag.retriever import hybrid_retrieve

console = Console()

# Cache toàn bộ chunks trong memory để BM25 search (không cần re-read disk)
_indexed_chunks: list[Chunk] = []


class RAGPipeline:
    """Orchestrate indexing và querying."""

    def __init__(self, provider=None):
        # Provider để gọi LLM sau khi retrieve
        self._provider = provider

    def set_provider(self, provider) -> None:
        self._provider = provider

    def index(self, folder_path: str, force: bool = False) -> int:
        """
        Index toàn bộ Python files trong folder.
        force=True: xóa index cũ và index lại.
        """
        global _indexed_chunks

        if force:
            clear_collection()
            console.print("[yellow]🗑  Đã xóa index cũ[/yellow]")

        existing = count_indexed()
        if existing > 0 and not force:
            console.print(
                f"[dim]ℹ  Đã có {existing} chunks trong index. "
                f"Dùng /rag index --force để index lại.[/dim]"
            )
            # Load lại chunks vào memory cho BM25
            _indexed_chunks = chunk_folder(folder_path)
            return existing

        console.print(f"\n[bold cyan]📂 Indexing: {folder_path}[/bold cyan]")

        # Chunk
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task("Chunking files...", total=None)
            chunks = chunk_folder(folder_path)

        if not chunks:
            console.print("[red]❌ Không tìm thấy Python file nào[/red]")
            return 0

        console.print(f"[dim]✓ {len(chunks)} chunks từ {_count_unique_files(chunks)} files[/dim]")

        # Embed (batch)
        console.print("[dim]Embedding chunks...[/dim]")
        batch_size = 32
        all_embeddings = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            embeddings = embed_texts([c.content for c in batch])
            all_embeddings.extend(embeddings)

        # Store in ChromaDB
        upsert_chunks(chunks, all_embeddings)
        _indexed_chunks = chunks

        console.print(f"[green]✅ Đã index {len(chunks)} chunks[/green]")
        return len(chunks)

    def query(self, question: str, top_k: int = 5) -> str:
        """
        Query RAG: retrieve relevant chunks → format context → LLM → answer.
        Trả về answer string.
        """
        global _indexed_chunks

        if count_indexed() == 0:
            return "❌ Chưa có index. Chạy `/rag index` trước."

        # Lazy load chunks nếu memory cache rỗng
        if not _indexed_chunks:
            console.print("[dim]Loading chunks for BM25...[/dim]")
            # Không có folder path lưu lại → dùng semantic only
            query_embedding = embed_single(question)
            hits = semantic_search(query_embedding, top_k=top_k)
        else:
            hits = hybrid_retrieve(question, _indexed_chunks, top_k_final=top_k)

        if not hits:
            return "❌ Không tìm thấy context liên quan."

        # Format context cho LLM
        context_parts = []
        for i, hit in enumerate(hits, 1):
            meta = hit["metadata"]
            score = hit.get("rerank_score") or hit.get("rrf_score") or hit.get("score", 0)
            context_parts.append(
                f"[Source {i}: {meta.get('source_file', '?')} "
                f"| {meta.get('name', '?')} | line {meta.get('start_line', '?')}]"
                f"\n{hit['content']}"
            )

        context = "\n\n---\n\n".join(context_parts)

        # Gọi LLM với context
        if not self._provider:
            # Nếu chưa có provider, trả về raw context
            return f"Context retrieved (no LLM):\n\n{context}"

        system = """Bạn là AI assistant trợ lý lập trình.
Trả lời câu hỏi DỰA TRÊN CODE CONTEXT được cung cấp.
- Trích dẫn file và line number khi có thể
- Nếu context không đủ để trả lời → nói rõ "Không tìm thấy trong codebase"
- Không bịa thêm thông tin ngoài context"""

        user_msg = f"""CONTEXT TỪ CODEBASE:
{context}

---

CÂU HỎI: {question}"""

        result = self._provider.chat(
            messages=[{"role": "user", "content": user_msg}],
            system=system,
            max_tokens=2048,
        )
        return result.text


def _count_unique_files(chunks: list[Chunk]) -> int:
    return len({c.source_file for c in chunks})
