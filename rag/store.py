# rag/store.py
"""
Vector Store — lưu và tìm kiếm embeddings bằng ChromaDB.

ChromaDB là gì?
- Vector database chạy local (không cần server)
- Lưu: embedding vector + metadata (file, line...) + raw text
- Search: cosine similarity → trả về top-k chunks gần nhất với query

Persistent: data lưu trên disk → index 1 lần, dùng mãi.
"""

import chromadb
from pathlib import Path

from rag.chunker import Chunk

DB_PATH = Path("data/rag_db")

# Singleton client — ChromaDB không cho tạo 2 client cùng path với settings khác nhau
_client = None


def _get_client():
    global _client
    if _client is None:
        DB_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(DB_PATH))
    return _client


def get_collection(collection_name: str = "codebase") -> chromadb.Collection:
    """Lấy hoặc tạo ChromaDB collection."""
    return _get_client().get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    """Lưu chunks + embeddings vào ChromaDB. Upsert = insert hoặc update."""
    collection = get_collection()

    collection.upsert(
        ids=[c.doc_id for c in chunks],
        embeddings=embeddings,
        documents=[c.content for c in chunks],
        metadatas=[
            {
                "source_file": c.source_file,
                "chunk_type": c.chunk_type,
                "name": c.name,
                "start_line": c.start_line,
                "end_line": c.end_line,
            }
            for c in chunks
        ],
    )


def semantic_search(
    query_embedding: list[float],
    top_k: int = 20,
) -> list[dict]:
    """
    Semantic search: tìm top-k chunks gần nhất với query embedding.
    Trả về list[dict] với keys: content, metadata, distance, score.
    """
    collection = get_collection()

    if collection.count() == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "content": doc,
            "metadata": meta,
            "distance": dist,
            "score": 1 - dist,  # ChromaDB cosine distance → similarity score
        })

    return hits


def count_indexed() -> int:
    """Số chunks đã index."""
    return get_collection().count()


def clear_collection() -> None:
    """Xóa toàn bộ index — dùng khi cần re-index."""
    global _client
    try:
        _get_client().delete_collection("codebase")
    except Exception:
        pass
